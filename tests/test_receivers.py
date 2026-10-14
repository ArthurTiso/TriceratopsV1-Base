import random
import unittest
from unittest import mock

from apoio import RelogioFalso
from protocol.decoder import ProtocolDecoder
from receiver.serial_receiver import SerialReceiver
from receiver.simulated_receiver import COLAPSO, INICIO, MONITORANDO, SimulatedReceiver


class SerialFalsa:
    def __init__(self, linhas):
        self.linhas = list(linhas)
        self.fechada = False

    def readline(self):
        return self.linhas.pop(0) if self.linhas else b""

    def close(self):
        self.fechada = True


class SerialReceiverTest(unittest.TestCase):
    def criar(self, linhas):
        self.serial = SerialFalsa(linhas)
        with mock.patch("builtins.print"):
            return SerialReceiver("COM3", abrir_serial=lambda porta, baud, timeout: self.serial)

    def test_reads_one_frame_per_line(self):
        receiver = self.criar([b"***000012301230000006107###\r\n"])

        self.assertEqual(receiver.receber(), "***000012301230000006107###")

    def test_ignores_boot_messages_noise_and_timeouts(self):
        receiver = self.criar([b"Receptor SPINO pronto\r\n", b"\xff\x00lixo\r\n", b""])

        self.assertEqual([receiver.receber() for _ in range(3)], [None, None, None])

    def test_reconnects_after_the_cable_is_unplugged(self):
        relogio = RelogioFalso()
        tentativas = []

        def abrir(porta, baud, timeout):
            tentativas.append(relogio())
            if len(tentativas) == 2:
                raise OSError("porta ocupada")
            return SerialFalsa([b"***000012301230000006107###\n"])

        with mock.patch("builtins.print"):
            receiver = SerialReceiver("COM3", abrir_serial=abrir, clock=relogio)
            receiver._serial.readline = mock.Mock(side_effect=OSError("desconectado"))

            self.assertIsNone(receiver.receber())       # erro: fecha a porta
            relogio.avancar(2)
            self.assertIsNone(receiver.receber())       # 2ª tentativa falha
            self.assertIsNone(receiver.receber())       # espera antes de tentar de novo
            relogio.avancar(2)
            self.assertEqual(receiver.receber(), "***000012301230000006107###")

        self.assertEqual(len(tentativas), 3)


class SimulatedReceiverTest(unittest.TestCase):
    def setUp(self):
        self.relogio = RelogioFalso()
        self.decoder = ProtocolDecoder()

    def coletar(self, receiver, segundos, passo=0.1):
        quadros = []
        for _ in range(int(segundos / passo)):
            with mock.patch("builtins.print"):
                quadro = receiver.receber()
            if quadro:
                quadros.append((self.relogio(), receiver.estado, self.decoder.decodificar(quadro)))
            self.relogio.avancar(passo)
        return quadros

    def criar(self, firmware="atual", seed=1):
        return SimulatedReceiver(firmware=firmware, clock=self.relogio, rng=random.Random(seed))

    def test_silent_before_the_tare_finishes(self):
        receiver = self.criar()

        self.assertEqual(self.coletar(receiver, 4.9), [])
        self.assertIn(receiver.estado, (INICIO, "TARANDO"))

    def test_sends_two_frames_per_second_during_the_test(self):
        receiver = self.criar()
        self.coletar(receiver, 5.0)

        quadros = [q for q in self.coletar(receiver, 4.0) if q[1] == MONITORANDO]

        self.assertGreaterEqual(len(quadros), 7)
        self.assertLessEqual(len(quadros), 9)

    def test_current_firmware_sends_flag_one_during_the_whole_test(self):
        quadros = self.coletar(self.criar("atual"), 120)

        self.assertTrue(quadros)
        self.assertTrue(all(d["flag"] == 1 for _, _, d in quadros))

    def test_corrected_firmware_sends_flag_one_only_on_collapse(self):
        quadros = self.coletar(self.criar("corrigido"), 120)

        for _, estado, d in quadros:
            self.assertEqual(d["flag"], 1 if estado == COLAPSO else 0)

    def test_collapse_freezes_time_and_follows_the_arduino_rule(self):
        quadros = self.coletar(self.criar(), 120)
        colapso = [d for _, estado, d in quadros if estado == COLAPSO]

        self.assertTrue(colapso, "o ensaio simulado deveria colapsar em 2 minutos")
        primeiro = colapso[0]
        self.assertGreaterEqual(primeiro["peso_max"], 2.0)
        self.assertLessEqual(primeiro["peso_atual"], primeiro["peso_max"] * 0.2 + 1e-9)
        self.assertEqual({d["tempo"] for d in colapso[:10]}, {primeiro["tempo"]})

    def test_restarts_with_a_new_test_after_the_collapse(self):
        quadros = self.coletar(self.criar(), 240)
        tempos = [d["tempo"] for _, _, d in quadros]

        reinicios = sum(1 for a, b in zip(tempos, tempos[1:]) if b < a)
        self.assertGreaterEqual(reinicios, 1)


if __name__ == "__main__":
    unittest.main()
