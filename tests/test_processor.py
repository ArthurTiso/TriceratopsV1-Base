import unittest

from apoio import RelogioFalso, dados
from core.processor import COLAPSO, NOVO_ENSAIO, Processor
from core.system_state import BROKEN, IDLE, INACTIVE, RUNNING, SystemState


class ProcessorTest(unittest.TestCase):
    def setUp(self):
        self.relogio = RelogioFalso()
        self.state = SystemState("MOCK001")
        self.processor = Processor(self.state, clock=self.relogio)

    def quadro(self, peso_atual, peso_max, tempo, flag=1, avancar=0.5):
        eventos = self.processor.processar(dados(peso_atual, peso_max, tempo, flag))
        self.relogio.avancar(avancar)
        return eventos

    def ensaio_ate(self, segundos, flag=1, carga_por_segundo=1.0):
        """Ensaio em andamento: 2 quadros por segundo, carga subindo."""
        for meio_segundo in range(segundos * 2):
            tempo = meio_segundo // 2
            carga = tempo * carga_por_segundo
            self.quadro(carga, carga, tempo, flag)

    # ---- início de ensaio ----

    def test_first_frame_starts_a_test(self):
        self.assertEqual(self.state.status, IDLE)

        eventos = self.quadro(0.0, 0.0, 0)

        self.assertEqual(eventos, [NOVO_ENSAIO])
        self.assertEqual(self.state.status, RUNNING)

    def test_flag_one_during_the_test_is_not_a_collapse(self):
        # Firmware atual: flag 1 durante todo o ensaio
        self.ensaio_ate(20)

        self.assertEqual(self.state.status, RUNNING)

    # ---- regra combinada A + B ----

    def test_low_load_alone_is_not_a_collapse(self):
        self.ensaio_ate(10)

        # A verdadeira (1 kg <= 20% de 9 kg), mas o tempo continua avançando
        eventos = self.quadro(1.0, 9.0, 10) + self.quadro(1.0, 9.0, 10) + self.quadro(1.0, 9.0, 11)

        self.assertNotIn(COLAPSO, eventos)
        self.assertEqual(self.state.status, RUNNING)

    def test_frozen_time_alone_is_not_a_collapse(self):
        self.ensaio_ate(10)

        # B verdadeira (tempo parado), mas a carga continua alta
        eventos = []
        for _ in range(8):
            eventos += self.quadro(9.0, 9.0, 10)

        self.assertNotIn(COLAPSO, eventos)
        self.assertEqual(self.state.status, RUNNING)

    def test_low_load_with_frozen_time_is_a_collapse(self):
        self.ensaio_ate(10)

        eventos = []
        for _ in range(6):  # 3 s de quadros com o tempo congelado em 10
            eventos += self.quadro(1.0, 9.0, 10)

        self.assertEqual(eventos.count(COLAPSO), 1)
        self.assertEqual(self.state.status, BROKEN)

    def test_collapse_is_detected_about_two_seconds_after_time_freezes(self):
        self.ensaio_ate(10)

        self.assertEqual(self.quadro(1.0, 9.0, 10), [])  # tempo mudou agora
        self.assertEqual(self.quadro(1.0, 9.0, 10), [])  # 0,5 s
        self.assertEqual(self.quadro(1.0, 9.0, 10), [])  # 1,0 s
        self.assertEqual(self.quadro(1.0, 9.0, 10), [])  # 1,5 s
        self.assertEqual(self.quadro(1.0, 9.0, 10), [COLAPSO])  # 2,0 s

    def test_small_bridges_below_two_kg_never_collapse(self):
        # Mesma regra do Arduino: só há colapso se a máxima passou de 2 kg
        self.quadro(0.0, 0.0, 0)
        eventos = []
        for _ in range(10):
            eventos += self.quadro(0.1, 1.5, 3)

        self.assertNotIn(COLAPSO, eventos)

    # ---- firmware com a flag corrigida ----

    def test_corrected_flag_triggers_an_immediate_collapse(self):
        self.ensaio_ate(10, flag=0)

        eventos = self.quadro(1.0, 9.0, 10, flag=1)

        self.assertEqual(eventos, [COLAPSO])

    # ---- reensaio ----

    def test_new_test_after_collapse_when_time_restarts(self):
        self.ensaio_ate(10)
        for _ in range(6):
            self.quadro(1.0, 9.0, 10)
        self.assertEqual(self.state.status, BROKEN)

        # Arduino continua repetindo o quadro final: nada acontece
        self.assertEqual(self.quadro(1.0, 9.0, 10), [])
        # Operador tocou em REINICIAR, fez a tara e o tempo voltou a 0
        self.relogio.avancar(10)
        eventos = self.quadro(0.0, 0.0, 0)

        self.assertEqual(eventos, [NOVO_ENSAIO])
        self.assertEqual(self.state.status, RUNNING)
        self.assertEqual(self.state.peso_max, 0.0)
        self.assertEqual(self.state.historico, [(0, 0.0)])

    def test_arduino_reset_mid_test_starts_a_new_test(self):
        self.ensaio_ate(10)

        eventos = self.quadro(0.0, 0.0, 0)

        self.assertEqual(eventos, [NOVO_ENSAIO])

    def test_starting_after_the_collapse_waits_for_the_next_test(self):
        # Módulo 2 ligado com o Arduino já mostrando o colapso
        eventos = self.quadro(1.0, 9.0, 30) + self.quadro(1.0, 9.0, 30)

        self.assertEqual(eventos, [])
        self.assertEqual(self.state.status, BROKEN)
        self.assertEqual(self.quadro(0.0, 0.0, 0), [NOVO_ENSAIO])

    # ---- inatividade ----

    def test_inactive_after_ten_seconds_without_frames(self):
        self.ensaio_ate(5)

        self.relogio.avancar(9)
        self.assertFalse(self.processor.verificar_inatividade())
        self.relogio.avancar(1)
        self.assertTrue(self.processor.verificar_inatividade())
        self.assertEqual(self.state.status, INACTIVE)

        # O rádio voltou: o ensaio continua, sem novo ensaio nem falso colapso
        eventos = self.quadro(16.0, 16.0, 16)
        self.assertEqual(eventos, [])
        self.assertEqual(self.state.status, RUNNING)

    def test_silence_after_collapse_is_not_inactivity(self):
        self.ensaio_ate(10)
        for _ in range(6):
            self.quadro(1.0, 9.0, 10)

        self.relogio.avancar(60)

        self.assertFalse(self.processor.verificar_inatividade())
        self.assertEqual(self.state.status, BROKEN)

    def test_history_keeps_one_point_per_second(self):
        self.ensaio_ate(5)

        self.assertEqual([t for t, _ in self.state.historico], [0, 1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
