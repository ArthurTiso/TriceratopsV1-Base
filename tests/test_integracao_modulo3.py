"""Integração Módulo 1 (simulado) -> Módulo 2 -> Módulo 3 (mock HTTP real).

O simulador reproduz o firmware da balança com um relógio acelerado; os
comandos do operador passam pelo mesmo caminho do terminal e os envios vão
por HTTP de verdade até o mock, que aplica as regras do SensorCaptureController
do Módulo 3.
"""

import random
import threading
import time
import unittest
from unittest import mock

from apoio import RelogioFalso
from app.pipeline import Pipeline
from receiver.simulated_receiver import SimulatedReceiver
from sender.api_sender import ApiSender
from sender.mock_modulo3_server import ROTA, criar_servidor

TOKEN = "token-de-teste"


class IntegracaoModulo3Test(unittest.TestCase):
    def setUp(self):
        self.servidor, self.banco = criar_servidor(0, TOKEN, verbose=False)
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.servidor.server_address[1]}{ROTA}"
        self.relogio = RelogioFalso()
        self.receiver = SimulatedReceiver(clock=self.relogio, rng=random.Random(11))

        patcher = mock.patch("builtins.print")
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()

    def criar_pipeline(self, token=TOKEN):
        self.sender = ApiSender(self.url, token)
        return Pipeline("MOCK001", self.receiver, self.sender, clock=self.relogio)

    def rodar(self, pipeline, segundos, passo=0.05):
        for _ in range(int(segundos / passo)):
            linha = self.receiver.receber()
            while linha:
                if pipeline.processar_linha(linha):
                    while not self.sender._fila.empty():  # mock no ritmo do relógio acelerado
                        time.sleep(0.001)
                linha = self.receiver.receber()
            pipeline.verificar()
            self.relogio.avancar(passo)

    def eventos(self, equipe):
        return [(e, ms, g) for codigo, e, ms, g in self.banco.eventos if codigo == equipe]

    def test_operator_runs_two_tests_until_rupture(self):
        pipeline = self.criar_pipeline()
        self.rodar(pipeline, 3)  # tara de inicialização

        picos = {}
        for equipe in ("MOCK002", "MOCK003"):
            pipeline.executar_comando(f"novo {equipe}")
            self.rodar(pipeline, 60)
            picos[equipe] = pipeline.state.peso_max
        self.sender.parar(timeout=10)

        for equipe, pico in picos.items():
            with self.subTest(equipe=equipe):
                eventos = self.eventos(equipe)
                nomes = [e for e, _, _ in eventos]
                self.assertEqual(nomes[0], "started")
                self.assertGreater(nomes.count("sample"), 5)
                self.assertEqual(nomes.count("completed"), 1)
                self.assertEqual(nomes[-1], "completed")
                # tempo do ensaio crescente, em ms
                tempos = [ms for _, ms, _ in eventos]
                self.assertEqual(tempos, sorted(tempos))
                # ruptura registrada com o pico calculado pelo Arduino
                self.assertEqual(eventos[-1][2], round(pico * 1000))
                self.assertEqual(self.banco.equipes[equipe]["test_status"], "completed")
                self.assertEqual(self.banco.equipes[equipe]["actual_load_grams"], round(pico * 1000))

        self.assertEqual(self.eventos("MOCK001"), [])  # equipe padrão não foi usada

    def test_manual_finish_sends_completed(self):
        pipeline = self.criar_pipeline()
        self.rodar(pipeline, 3)
        pipeline.executar_comando("novo")
        self.rodar(pipeline, 8)  # carga ainda subindo

        pipeline.executar_comando("fim")
        self.rodar(pipeline, 5)
        self.sender.parar(timeout=10)

        nomes = [e for e, _, _ in self.eventos("MOCK001")]
        self.assertEqual(nomes[0], "started")
        self.assertEqual(nomes[-1], "completed")
        self.assertEqual(nomes.count("completed"), 1)

    def test_cancel_sends_nothing_more(self):
        pipeline = self.criar_pipeline()
        self.rodar(pipeline, 3)
        pipeline.executar_comando("novo")
        self.rodar(pipeline, 5)

        pipeline.executar_comando("cancelar")
        self.rodar(pipeline, 60)
        self.sender.parar(timeout=10)

        self.assertNotIn("completed", [e for e, _, _ in self.eventos("MOCK001")])

    def test_wrong_token_is_rejected(self):
        pipeline = self.criar_pipeline(token="errado")
        self.rodar(pipeline, 3)
        pipeline.executar_comando("novo")
        self.rodar(pipeline, 10)
        self.sender.parar(timeout=10)

        self.assertEqual(self.banco.eventos, [])


if __name__ == "__main__":
    unittest.main()
