import unittest

from apoio import RelogioFalso, dados
from core.processor import COLAPSO, NOVO_ENSAIO
from core.system_state import BROKEN, RUNNING
from core.telemetria import COMPLETED, SAMPLE, STARTED, PoliticaEnvio


class PoliticaEnvioTest(unittest.TestCase):
    def setUp(self):
        self.relogio = RelogioFalso()
        self.politica = PoliticaEnvio(intervalo_s=1.0, clock=self.relogio)

    def decidir(self, carga, eventos=(), status=RUNNING, avancar=0.5):
        envios = self.politica.decidir(list(eventos), status, dados(carga, carga, 0))
        self.relogio.avancar(avancar)
        return envios

    def test_sends_started_on_a_new_test(self):
        self.assertEqual(self.decidir(0.0, [NOVO_ENSAIO]), [STARTED])

    def test_nothing_is_sent_before_the_first_test(self):
        self.assertEqual(self.decidir(5.0), [])

    def test_samples_are_limited_to_one_per_interval(self):
        self.decidir(1.0, [NOVO_ENSAIO])

        envios = [self.decidir(1.0) for _ in range(6)]  # 3 s de quadros com a mesma carga

        self.assertEqual(envios, [[], [SAMPLE], [], [SAMPLE], [], [SAMPLE]])

    def test_a_new_peak_is_sent_immediately(self):
        self.decidir(1.0, [NOVO_ENSAIO])

        self.assertEqual(self.decidir(1.5), [SAMPLE])  # 0,5 s depois, mas carga maior

    def test_completed_is_sent_once_and_then_nothing(self):
        self.decidir(1.0, [NOVO_ENSAIO])

        self.assertEqual(self.decidir(0.5, [COLAPSO], status=BROKEN), [COMPLETED])
        for _ in range(10):
            self.assertEqual(self.decidir(0.5, status=BROKEN), [])

    def test_a_new_test_after_completed_starts_again(self):
        self.decidir(9.0, [NOVO_ENSAIO])
        self.decidir(1.0, [COLAPSO], status=BROKEN)

        self.assertEqual(self.decidir(0.0, [NOVO_ENSAIO]), [STARTED])
        self.relogio.avancar(1)
        self.assertEqual(self.decidir(0.0), [SAMPLE])


if __name__ == "__main__":
    unittest.main()
