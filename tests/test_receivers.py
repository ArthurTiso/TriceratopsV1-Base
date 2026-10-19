import random
import unittest
from unittest import mock

from apoio import RelogioFalso
from protocol.balanca import Medida, TaraConcluida, TaraIniciada, interpretar_linha
from receiver.serial_receiver import SerialReceiver
from receiver.simulated_receiver import SimulatedReceiver


class SerialFalsa:
    def __init__(self, linhas):
        self.linhas = list(linhas)
        self.escrito = b""

    def readline(self):
        return self.linhas.pop(0) if self.linhas else b""

    def write(self, dados):
        self.escrito += dados

    def flush(self):
        pass

    def close(self):
        pass


class SerialReceiverTest(unittest.TestCase):
    def criar(self, linhas):
        self.serial = SerialFalsa(linhas)
        with mock.patch("builtins.print"):
            return SerialReceiver("COM3", abrir_serial=lambda porta, baud, timeout: self.serial)

    def test_returns_each_line_without_line_breaks(self):
        receiver = self.criar([b"AMOSTRA_KG=1.0 | MEDIA_KG=1.0 | PICO_ABS_KG=1.0 | BRUTO=5\r\n"])

        self.assertEqual(receiver.receber(), "AMOSTRA_KG=1.0 | MEDIA_KG=1.0 | PICO_ABS_KG=1.0 | BRUTO=5")

    def test_timeouts_and_blank_lines_return_none(self):
        receiver = self.criar([b"", b"\r\n"])

        self.assertEqual([receiver.receber(), receiver.receber()], [None, None])

    def test_sends_the_tare_command(self):
        receiver = self.criar([])

        self.assertTrue(receiver.enviar_comando("t"))
        self.assertEqual(self.serial.escrito, b"t")

    def test_reconnects_after_the_cable_is_unplugged(self):
        relogio = RelogioFalso()
        tentativas = []

        def abrir(porta, baud, timeout):
            tentativas.append(baud)
            if len(tentativas) == 2:
                raise OSError("porta ocupada")
            return SerialFalsa([b"Tara concluida. Offset=1\n"])

        with mock.patch("builtins.print"):
            receiver = SerialReceiver("COM3", abrir_serial=abrir, clock=relogio)
            receiver._serial.readline = mock.Mock(side_effect=OSError("desconectado"))

            self.assertIsNone(receiver.receber())       # erro: fecha a porta
            self.assertFalse(receiver.enviar_comando("t"))
            relogio.avancar(2)
            self.assertIsNone(receiver.receber())       # 2ª tentativa falha
            relogio.avancar(2)
            self.assertEqual(receiver.receber(), "Tara concluida. Offset=1")

        self.assertEqual(tentativas, [115200] * 3)


class SimulatedReceiverTest(unittest.TestCase):
    def setUp(self):
        self.relogio = RelogioFalso()
        self.receiver = SimulatedReceiver(clock=self.relogio, rng=random.Random(3))

    def coletar(self, segundos, passo=0.05):
        eventos = []
        for _ in range(int(segundos / passo)):
            linha = self.receiver.receber()
            while linha:
                eventos.append(interpretar_linha(linha))
                linha = self.receiver.receber()
            self.relogio.avancar(passo)
        return [e for e in eventos if e is not None]

    def test_boots_with_header_and_automatic_tare(self):
        eventos = self.coletar(3)

        self.assertIsInstance(eventos[0], TaraIniciada)
        self.assertTrue(any(isinstance(e, TaraConcluida) for e in eventos))

    def test_idle_scale_reads_about_zero_twice_per_second(self):
        self.coletar(3)

        medidas = [e for e in self.coletar(5) if isinstance(e, Medida)]

        self.assertIn(len(medidas), (9, 10, 11))
        self.assertTrue(all(m.carga_kg < 0.2 for m in medidas))

    def test_tare_command_starts_a_load_until_rupture(self):
        self.coletar(3)

        self.receiver.enviar_comando("t")
        medidas = [e for e in self.coletar(60) if isinstance(e, Medida)]

        pico = max(m.pico_kg for m in medidas)
        self.assertGreaterEqual(pico, 4.0)
        self.assertTrue(self.receiver.rompeu)
        self.assertLess(medidas[-1].carga_kg, pico * 0.2)
        # O pico do Arduino acompanha a maior média, inclusive entre as linhas
        self.assertGreaterEqual(pico, max(m.carga_kg for m in medidas))


if __name__ == "__main__":
    unittest.main()
