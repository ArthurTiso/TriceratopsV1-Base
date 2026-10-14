"""Integração Módulo 1 (simulado) -> Módulo 2 -> Módulo 3 (mock HTTP real).

O simulador reproduz o firmware do Arduino com um relógio acelerado; os envios
passam por HTTP de verdade até o mock, que aplica as regras do
SensorCaptureController do Módulo 3.
"""

import random
import threading
import time
import unittest
from unittest import mock

from apoio import RelogioFalso
from app.pipeline import Pipeline
from protocol.encoder import carga_para_campo
from receiver.simulated_receiver import COLAPSO, SimulatedReceiver
from sender.api_sender import ApiSender
from sender.mock_modulo3_server import ROTA, criar_servidor

TOKEN = "token-de-teste"


class IntegracaoModulo3Test(unittest.TestCase):
    def setUp(self):
        self.servidor, self.banco = criar_servidor(0, TOKEN, verbose=False)
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.servidor.server_address[1]}{ROTA}"

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()

    def executar(self, segundos, firmware="atual", perda_rf=0.0, team_code="MOCK001", token=TOKEN):
        relogio = RelogioFalso()
        receiver = SimulatedReceiver(
            firmware=firmware, perda_rf=perda_rf, clock=relogio, rng=random.Random(7)
        )
        sender = ApiSender(self.url, token)
        pipeline = Pipeline(team_code, sender, clock=relogio)
        picos = []  # carga máxima de cada ensaio, segundo o "Arduino"

        with mock.patch("builtins.print"):
            for _ in range(int(segundos / 0.05)):
                quadro = receiver.receber()
                if receiver.estado == COLAPSO and (not picos or picos[-1][0] != id(receiver._inicio_ensaio)):
                    picos.append((id(receiver._inicio_ensaio), receiver.peso_max))
                if quadro and pipeline.processar_quadro(quadro):
                    while not sender._fila.empty():  # mantém o mock no ritmo do relógio acelerado
                        time.sleep(0.001)
                else:
                    pipeline.verificar_inatividade()
                relogio.avancar(0.05)
            sender.parar(timeout=10)

        return [pico for _, pico in picos]

    def eventos(self, team_code="MOCK001"):
        return [(e, ms, g) for codigo, e, ms, g in self.banco.eventos if codigo == team_code]

    def ensaios(self, team_code="MOCK001"):
        """Agrupa os eventos recebidos pelo Módulo 3 por ensaio (cada um começa em started)."""
        ensaios = []
        for evento in self.eventos(team_code):
            if evento[0] == "started":
                ensaios.append([])
            ensaios[-1].append(evento)
        return ensaios

    def test_full_test_cycle_reaches_module_3(self):
        picos = self.executar(240)
        ensaios = self.ensaios()

        self.assertGreaterEqual(len(ensaios), 2, "deveria haver pelo menos dois ensaios em 4 minutos")
        for ensaio, pico in zip(ensaios, picos):
            nomes = [e for e, _, _ in ensaio]
            self.assertEqual(nomes[0], "started")
            self.assertGreater(nomes.count("sample"), 5)
            # completed uma única vez e por último: nada depois do colapso
            self.assertEqual(nomes.count("completed"), 1)
            self.assertEqual(nomes[-1], "completed")
            # pico do Arduino (resolução 0,1 kg) chegou ao Módulo 3 em gramas
            self.assertEqual(max(g for _, _, g in ensaio), carga_para_campo(pico) * 100)

        self.assertIn(self.banco.equipes["MOCK001"]["test_status"], ("completed", "running"))

    def test_last_completed_test_records_the_peak(self):
        self.executar(240)
        ultimo_completo = [e for e in self.ensaios() if e[-1][0] == "completed"][-1]

        # O mock acumula amostras de todos os ensaios da equipe (como o Módulo 3
        # hoje); o pico registrado é o maior entre eles.
        pico_total = max(g for _, _, g in self.eventos())
        self.assertEqual(self.banco.equipes["MOCK001"]["actual_load_grams"], pico_total)
        self.assertGreater(max(g for _, _, g in ultimo_completo), 0)

    def test_corrected_firmware_flag_gives_the_same_cycle(self):
        picos = self.executar(120, firmware="corrigido")
        completos = [e for e in self.ensaios() if e[-1][0] == "completed"]

        self.assertGreaterEqual(len(completos), 2)
        for ensaio, pico in zip(completos, picos):
            nomes = [e for e, _, _ in ensaio]
            self.assertEqual(nomes[0], "started")
            self.assertEqual(nomes.count("completed"), 1)
            self.assertEqual(max(g for _, _, g in ensaio), carga_para_campo(pico) * 100)

    def test_radio_losses_do_not_break_the_cycle(self):
        self.executar(240, perda_rf=0.3)

        completos = [e for e in self.ensaios() if e[-1][0] == "completed"]
        self.assertGreaterEqual(len(completos), 1)
        for ensaio in completos:
            self.assertEqual([e for e, _, _ in ensaio].count("completed"), 1)

    def test_wrong_token_is_rejected_without_retries(self):
        self.executar(30, token="errado")

        self.assertEqual(self.banco.eventos, [])

    def test_unknown_team_is_rejected(self):
        self.executar(30, team_code="NAOEXISTE")

        self.assertEqual(self.banco.eventos, [])


if __name__ == "__main__":
    unittest.main()
