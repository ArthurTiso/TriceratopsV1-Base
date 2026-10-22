"""Integração Módulo 1 (simulado) -> Módulo 2 -> Módulo 3 (mock HTTP real).

O simulador reproduz o firmware da balança com um relógio acelerado; o mock
aplica as regras de ensaio armado do Módulo 3. Consulta do ensaio ativo,
comandos do operador e envios passam pelos mesmos caminhos do programa real.
"""

import csv
import random
import tempfile
import threading
import time
import unittest
from unittest import mock

from pathlib import Path

from apoio import RelogioFalso
from app.pipeline import Pipeline
from receiver.simulated_receiver import SimulatedReceiver
from sender.api_sender import ApiSender
from sender.ensaio_ativo import ConsultaEnsaioAtivo
from sender.mock_modulo3_server import criar_servidor
from sender.modulo3_payload import url_captura, url_ensaio_ativo

TOKEN = "token-de-teste"
DEVICE = "M2-01"


class IntegracaoModulo3Test(unittest.TestCase):
    def setUp(self):
        self.subir_mock(token=None)  # o Módulo 3 atual não exige token
        self.relogio = RelogioFalso()
        self.receiver = SimulatedReceiver(clock=self.relogio, rng=random.Random(11))

        patcher = mock.patch("builtins.print")
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.derrubar_mock()

    def subir_mock(self, token):
        self.servidor, self.banco = criar_servidor(0, token, device_padrao=DEVICE, verbose=False)
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.servidor.server_address[1]}"

    def derrubar_mock(self):
        self.servidor.shutdown()
        self.servidor.server_close()

    def criar_pipeline(self, token=None):
        self.sender = ApiSender(url_captura(self.base), token)
        self.consulta = ConsultaEnsaioAtivo(
            url_ensaio_ativo(self.base, DEVICE), token, iniciar=False, clock=self.relogio
        )
        self.csv = Path(tempfile.mkdtemp()) / "resultados.csv"
        return Pipeline(DEVICE, self.receiver, self.sender, consulta=self.consulta,
                        arquivo_resultados=self.csv, clock=self.relogio)

    def resultados_csv(self):
        if not self.csv.exists():
            return []
        with open(self.csv, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f, delimiter=";"))

    def rodar(self, pipeline, segundos, passo=0.05):
        for passo_n in range(int(segundos / passo)):
            if passo_n % 40 == 0:  # consulta do ensaio ativo a cada 2 s
                self.consulta.consultar()
            linha = self.receiver.receber()
            while linha:
                pipeline.processar_linha(linha)
                linha = self.receiver.receber()
            pipeline.verificar()
            while not self.sender._fila.empty():  # mock no ritmo do relógio acelerado
                time.sleep(0.001)
            self.relogio.avancar(passo)

    def eventos(self, equipe=None):
        return [e for e in self.banco.eventos if equipe is None or e[0] == equipe]

    def test_new_test_requires_a_run_armed_in_module_3(self):
        pipeline = self.criar_pipeline()
        self.rodar(pipeline, 3)

        pipeline.executar_comando("novo")
        self.rodar(pipeline, 20)
        self.sender.parar(timeout=10)

        self.assertFalse(pipeline.controle.em_ensaio)
        self.assertEqual(self.eventos(), [])

    def test_two_armed_tests_until_rupture(self):
        pipeline = self.criar_pipeline()
        self.rodar(pipeline, 3)

        picos = {}
        for equipe in ("MOCK002", "MOCK003"):
            run_id = self.banco.armar(equipe, DEVICE)
            self.rodar(pipeline, 3)  # M2 descobre o ensaio armado
            self.assertEqual(pipeline.armado.run_id, run_id)
            pipeline.executar_comando("novo")
            self.rodar(pipeline, 60)
            picos[equipe] = (run_id, pipeline.state.peso_max)
        self.sender.parar(timeout=10)

        for equipe, (run_id, pico) in picos.items():
            with self.subTest(equipe=equipe):
                eventos = self.eventos(equipe)
                nomes = [e[1] for e in eventos]
                self.assertEqual(nomes[0], "started")
                self.assertGreater(nomes.count("sample"), 5)
                self.assertEqual(nomes.count("completed"), 1)
                self.assertEqual(nomes[-1], "completed")
                self.assertEqual({e[4] for e in eventos}, {run_id})
                self.assertEqual(eventos[-1][3], round(pico * 1000))
                self.assertEqual(self.banco.ensaios[run_id]["status"], "finished")
                self.assertEqual(self.banco.equipes[equipe]["actual_load_grams"], round(pico * 1000))

    def test_typed_team_must_match_the_armed_run(self):
        pipeline = self.criar_pipeline()
        self.rodar(pipeline, 3)
        self.banco.armar("MOCK002", DEVICE)
        self.rodar(pipeline, 3)

        pipeline.executar_comando("novo MOCK003")
        self.rodar(pipeline, 5)

        self.assertFalse(pipeline.controle.em_ensaio)

    def test_cancel_in_module_3_stops_the_test(self):
        pipeline = self.criar_pipeline()
        self.rodar(pipeline, 3)
        self.banco.armar("MOCK002", DEVICE)
        self.rodar(pipeline, 3)
        pipeline.executar_comando("novo")
        self.rodar(pipeline, 6)
        self.assertTrue(pipeline.controle.em_ensaio)

        self.banco.cancelar_ativos()
        self.rodar(pipeline, 60)
        self.sender.parar(timeout=10)

        self.assertFalse(pipeline.controle.em_ensaio)
        self.assertNotIn("completed", [e[1] for e in self.eventos()])

    def test_resuming_the_same_run_after_an_arduino_reset(self):
        pipeline = self.criar_pipeline()
        self.rodar(pipeline, 3)
        run_id = self.banco.armar("MOCK002", DEVICE)
        self.rodar(pipeline, 3)

        with mock.patch("app.pipeline.base_sequencia", side_effect=[1000, 5000]):
            pipeline.executar_comando("novo")
            self.rodar(pipeline, 8)
            self.receiver.enviar_comando("t")  # Arduino reiniciou: tara inesperada
            self.rodar(pipeline, 3)
            self.assertFalse(pipeline.controle.em_ensaio)

            pipeline.executar_comando("novo")  # mesmo ensaio armado, ainda "running"
            self.rodar(pipeline, 60)
        self.sender.parar(timeout=10)

        nomes = [e[1] for e in self.eventos("MOCK002")]
        self.assertEqual(nomes.count("started"), 2)
        self.assertEqual(nomes.count("completed"), 1)
        self.assertEqual(self.banco.ensaios[run_id]["status"], "finished")

    def test_wrong_token_sends_nothing_when_module_3_requires_one(self):
        self.derrubar_mock()
        self.subir_mock(token=TOKEN)
        pipeline = self.criar_pipeline(token="errado")
        self.banco.armar("MOCK002", DEVICE)
        self.rodar(pipeline, 3)

        pipeline.executar_comando("novo")
        self.rodar(pipeline, 10)
        self.sender.parar(timeout=10)

        self.assertIsNone(pipeline.armado)
        self.assertEqual(self.eventos(), [])

    def test_iniciar_button_in_module_3_runs_the_whole_test(self):
        pipeline = self.criar_pipeline()
        self.rodar(pipeline, 3)
        run_id = self.banco.armar("MOCK002", DEVICE)
        self.rodar(pipeline, 3)

        self.banco.iniciar_armados()  # só o botão "Iniciar" do Módulo 3, sem "novo"
        self.rodar(pipeline, 60)
        self.sender.parar(timeout=10)
        pipeline.finalizar()

        nomes = [e[1] for e in self.eventos("MOCK002")]
        self.assertEqual(nomes[0], "started")
        self.assertEqual(nomes[-1], "completed")
        self.assertEqual(self.banco.ensaios[run_id]["status"], "finished")
        linha = self.resultados_csv()[0]
        self.assertEqual(linha["registro_modulo3"], "confirmado")
        self.assertEqual(linha["carga_ruptura_kg"].replace(",", "."),
                         f"{self.banco.equipes['MOCK002']['actual_load_grams'] / 1000:.1f}")

    def test_encerrar_in_module_3_mid_test_keeps_the_peak_in_the_csv(self):
        pipeline = self.criar_pipeline()
        self.rodar(pipeline, 3)
        self.banco.armar("MOCK002", DEVICE)
        self.rodar(pipeline, 3)
        self.banco.iniciar_armados()
        self.rodar(pipeline, 10)

        self.banco.encerrar_ativos()
        self.rodar(pipeline, 5)
        self.sender.parar(timeout=10)

        self.assertNotIn("completed", [e[1] for e in self.eventos()])
        linha = self.resultados_csv()[0]
        self.assertIn("em Rupturas", linha["registro_modulo3"])
        self.assertGreater(float(linha["carga_ruptura_kg"].replace(",", ".")), 0)

    def test_module_3_down_allows_a_local_test(self):
        pipeline = self.criar_pipeline()
        self.rodar(pipeline, 3)
        self.banco.armar("MOCK002", DEVICE)
        self.rodar(pipeline, 3)

        self.derrubar_mock()
        self.rodar(pipeline, 20)  # 15 s sem resposta: Módulo 3 fora do ar
        self.assertFalse(pipeline.state.extras["m3_online"])
        pipeline.executar_comando("novo EQUIPE 07")
        self.rodar(pipeline, 60)
        self.sender.parar(timeout=5)

        linha = self.resultados_csv()[0]
        self.assertEqual(linha["equipe_nome"], "EQUIPE 07")
        self.assertEqual(linha["modo"], "local")
        self.subir_mock(token=None)  # para o tearDown


if __name__ == "__main__":
    unittest.main()
