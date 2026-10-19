import unittest

from apoio import RelogioFalso
from core.ensaio import COLAPSO, FIM_MANUAL, INTERROMPIDO, NOVO_ENSAIO
from core.system_state import BROKEN, IDLE, RUNNING
from core.telemetria import COMPLETED, SAMPLE, STARTED, PoliticaEnvio


class PoliticaEnvioTest(unittest.TestCase):
    def setUp(self):
        self.relogio = RelogioFalso()
        self.politica = PoliticaEnvio(intervalo_s=1.0, clock=self.relogio)

    def decidir(self, carga, eventos=(), status=RUNNING, avancar=0.5):
        envios = self.politica.decidir(list(eventos), status, carga)
        self.relogio.avancar(avancar)
        return envios

    def test_sends_started_on_a_new_test(self):
        self.assertEqual(self.decidir(0.0, [NOVO_ENSAIO]), [STARTED])

    def test_nothing_is_sent_outside_a_test(self):
        self.assertEqual(self.decidir(5.0, status=IDLE), [])

    def test_samples_are_limited_to_one_per_interval(self):
        self.decidir(1.0, [NOVO_ENSAIO])

        envios = [self.decidir(1.0) for _ in range(6)]  # 3 s de linhas com a mesma carga

        self.assertEqual(envios, [[], [SAMPLE], [], [SAMPLE], [], [SAMPLE]])

    def test_a_new_peak_is_sent_immediately(self):
        self.decidir(1.0, [NOVO_ENSAIO])

        self.assertEqual(self.decidir(1.5), [SAMPLE])

    def test_completed_is_sent_once_and_then_nothing(self):
        for fim in (COLAPSO, FIM_MANUAL):
            with self.subTest(fim=fim):
                self.decidir(1.0, [NOVO_ENSAIO])
                self.assertEqual(self.decidir(0.5, [fim], status=BROKEN), [COMPLETED])
                for _ in range(10):
                    self.assertEqual(self.decidir(0.5, status=BROKEN), [])

    def test_interrupted_test_sends_nothing_more(self):
        self.decidir(1.0, [NOVO_ENSAIO])

        self.assertEqual(self.decidir(0.0, [INTERROMPIDO], status=IDLE), [])
        self.assertEqual(self.decidir(3.0, avancar=2), [])


if __name__ == "__main__":
    unittest.main()
