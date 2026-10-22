import unittest
from unittest import mock

from apoio import RelogioFalso, medida
from core.ensaio import COLAPSO, COLAPSO_DESFEITO, FIM_MANUAL, INTERROMPIDO, NOVO_ENSAIO, ControleEnsaio
from core.system_state import (
    BROKEN,
    ERRO_SENSOR,
    FINALIZADO,
    IDLE,
    INACTIVE,
    RUPTURA_DETECTADA,
    RUNNING,
    TARANDO,
    SystemState,
)
from protocol.balanca import ErroSensor, TaraConcluida, TaraIniciada, TaraProgresso


class ControleEnsaioTest(unittest.TestCase):
    def setUp(self):
        self.relogio = RelogioFalso()
        self.state = SystemState("MOCK001")
        self.controle = ControleEnsaio(self.state, clock=self.relogio)
        patcher = mock.patch("builtins.print")
        patcher.start()
        self.addCleanup(patcher.stop)

    def linha(self, evento, avancar=0.5):
        eventos = self.controle.processar(evento)
        self.relogio.avancar(avancar)
        return eventos

    def tara_do_arduino(self):
        eventos = self.linha(TaraIniciada(), avancar=0)
        for n in range(4):
            eventos += self.linha(TaraProgresso(n * 5, 20))
        return eventos + self.linha(TaraConcluida(8423190))

    def iniciar_ensaio(self, equipe="MOCK002"):
        self.assertTrue(self.controle.novo_ensaio(equipe))
        return self.tara_do_arduino()

    def carregar_ate(self, kg, passo_kg=1.0):
        eventos = []
        carga = 0.0
        while carga < kg:
            carga = min(carga + passo_kg, kg)
            eventos += self.linha(medida(carga))
        return eventos

    # ---- início ----

    def test_boot_tare_does_not_start_a_test(self):
        eventos = self.tara_do_arduino()
        eventos += self.linha(medida(0.0))

        self.assertEqual(eventos, [])
        self.assertEqual(self.state.status, IDLE)
        self.assertFalse(self.controle.em_ensaio)

    def test_chart_follows_the_peak_since_the_last_tare_outside_a_test(self):
        self.tara_do_arduino()
        self.linha(medida(3.0))
        self.linha(medida(1.0, pico_kg=3.0))

        self.assertEqual([p[2] for p in self.state.historico], [3.0, 3.0])
        self.assertEqual(self.state.status, IDLE)

    def test_new_test_starts_when_the_requested_tare_finishes(self):
        self.assertTrue(self.controle.novo_ensaio("MOCK002"))
        self.assertEqual(self.state.status, TARANDO)

        eventos = self.tara_do_arduino()

        self.assertEqual(eventos, [NOVO_ENSAIO])
        self.assertEqual(self.state.status, RUNNING)
        self.assertEqual(self.state.equipe, "MOCK002")

    def test_elapsed_time_counts_from_the_end_of_the_tare(self):
        self.iniciar_ensaio()
        for _ in range(6):
            self.linha(medida(1.0))

        self.assertAlmostEqual(self.state.tempo, 3.0)
        self.assertEqual(self.state.historico[0], (0.0, 0.0, 0.0))

    def test_cannot_start_two_tests_at_once(self):
        self.iniciar_ensaio()

        self.assertFalse(self.controle.novo_ensaio("MOCK003"))
        self.assertFalse(self.controle.tarar())

    # ---- colapso ----

    def test_collapse_needs_the_drop_to_last_one_second(self):
        self.iniciar_ensaio()
        self.carregar_ate(10.0)

        self.assertEqual(self.linha(medida(1.0, pico_kg=10.0)), [])  # queda percebida agora
        self.assertEqual(self.linha(medida(1.0, pico_kg=10.0)), [])  # 0,5 s
        self.assertEqual(self.linha(medida(1.0, pico_kg=10.0)), [COLAPSO])  # 1,0 s
        self.assertEqual(self.state.status, RUPTURA_DETECTADA)
        self.assertTrue(self.controle.em_ensaio)  # só termina quando o operador confirmar
        self.assertEqual(self.state.peso_max, 10.0)

    def test_a_momentary_dip_is_not_a_collapse(self):
        self.iniciar_ensaio()
        self.carregar_ate(10.0)

        eventos = self.linha(medida(1.0, pico_kg=10.0)) + self.linha(medida(9.0, pico_kg=10.0))
        eventos += self.linha(medida(1.0, pico_kg=10.0)) + self.linha(medida(9.5, pico_kg=10.0))

        self.assertNotIn(COLAPSO, eventos)
        self.assertEqual(self.state.status, RUNNING)

    def test_unloading_above_twenty_percent_is_not_a_collapse(self):
        self.iniciar_ensaio()
        self.carregar_ate(10.0)

        eventos = [e for _ in range(6) for e in self.linha(medida(2.5, pico_kg=10.0))]

        self.assertNotIn(COLAPSO, eventos)

    def test_small_loads_below_two_kg_never_collapse(self):
        self.iniciar_ensaio()
        self.carregar_ate(1.5, passo_kg=0.5)

        eventos = [e for _ in range(6) for e in self.linha(medida(0.0, pico_kg=1.5))]

        self.assertNotIn(COLAPSO, eventos)

    def test_inverted_load_cell_sign_still_detects_the_collapse(self):
        # MEDIA_KG negativa (célula montada ao contrário): o pico é em magnitude
        self.iniciar_ensaio()
        for kg in (2.0, 5.0, 8.0):
            self.linha(medida(-kg, pico_kg=kg))

        eventos = [e for _ in range(3) for e in self.linha(medida(-0.5, pico_kg=8.0))]

        self.assertEqual(eventos, [COLAPSO])

    def test_detected_collapse_is_reported_once_until_confirmed(self):
        self.iniciar_ensaio()
        self.carregar_ate(10.0)
        for _ in range(3):
            self.linha(medida(1.0, pico_kg=10.0))
        tempo_ruptura = self.state.tempo_ruptura

        eventos = [e for _ in range(10) for e in self.linha(medida(0.2, pico_kg=10.0))]

        self.assertEqual(eventos, [])
        self.assertEqual(self.state.status, RUPTURA_DETECTADA)
        self.assertEqual(self.controle.finalizar(), [FIM_MANUAL])
        self.assertEqual(self.state.status, BROKEN)
        self.assertEqual(self.state.tempo_ruptura, tempo_ruptura)  # instante da queda, não do clique
        self.assertEqual(self.state.peso_max, 10.0)

    def test_load_rising_again_undoes_the_detection(self):
        self.iniciar_ensaio()
        self.carregar_ate(10.0)
        for _ in range(3):
            self.linha(medida(1.0, pico_kg=10.0))

        self.assertEqual(self.linha(medida(9.0, pico_kg=10.0)), [COLAPSO_DESFEITO])
        self.assertEqual(self.state.status, RUNNING)
        self.assertIsNone(self.state.tempo_ruptura)

    def test_detection_survives_a_cable_hiccup(self):
        self.iniciar_ensaio()
        self.carregar_ate(10.0)
        for _ in range(3):
            self.linha(medida(1.0, pico_kg=10.0))
        self.relogio.avancar(6)
        self.controle.verificar()
        self.assertEqual(self.state.status, INACTIVE)

        self.assertEqual(self.linha(medida(0.5, pico_kg=10.0)), [])
        self.assertEqual(self.state.status, RUPTURA_DETECTADA)

    # ---- comandos do operador ----

    def test_manual_finish(self):
        self.iniciar_ensaio()
        self.carregar_ate(6.0)

        self.assertEqual(self.controle.finalizar(), [FIM_MANUAL])
        self.assertEqual(self.state.status, BROKEN)
        self.assertIsNotNone(self.state.tempo_ruptura)
        self.assertEqual(self.controle.finalizar(), [])

    def test_closed_elsewhere_freezes_without_a_result(self):
        self.iniciar_ensaio()
        self.carregar_ate(6.0)

        self.assertTrue(self.controle.encerrar_sem_resultado())
        self.assertEqual(self.state.status, FINALIZADO)
        self.assertFalse(self.controle.encerrar_sem_resultado())

    def test_cancel_discards_the_test(self):
        self.iniciar_ensaio()

        self.assertTrue(self.controle.cancelar())
        self.assertEqual(self.state.status, IDLE)
        self.assertFalse(self.controle.em_ensaio)

    def test_standalone_tare_does_not_start_a_test(self):
        self.assertTrue(self.controle.tarar())

        self.assertEqual(self.tara_do_arduino(), [])
        self.assertEqual(self.state.status, IDLE)

    def test_unanswered_tare_request_times_out(self):
        self.controle.novo_ensaio("MOCK002")
        for _ in range(12):  # Arduino ignora o "t" e segue medindo
            self.linha(medida(0.0))
            self.controle.verificar()

        self.assertEqual(self.state.status, IDLE)
        self.assertEqual(self.tara_do_arduino(), [])  # pedido já descartado

    # ---- falhas ----

    def test_unexpected_tare_during_a_test_interrupts_it(self):
        self.iniciar_ensaio()
        self.carregar_ate(5.0)

        eventos = self.linha(TaraIniciada())

        self.assertEqual(eventos, [INTERROMPIDO])
        self.assertFalse(self.controle.em_ensaio)
        self.assertEqual(self.tara_do_arduino(), [])

    def test_sensor_error_pauses_and_recovers(self):
        self.iniciar_ensaio()
        self.carregar_ate(5.0)

        self.linha(ErroSensor("ERRO: HX711 sem dados"))
        self.assertEqual(self.state.status, ERRO_SENSOR)
        self.linha(medida(5.5))
        self.assertEqual(self.state.status, RUNNING)

    def test_no_lines_marks_the_scale_as_inactive(self):
        self.iniciar_ensaio()
        self.carregar_ate(3.0)

        self.relogio.avancar(4.0)
        self.controle.verificar()
        self.assertEqual(self.state.status, RUNNING)
        self.relogio.avancar(1.0)
        self.controle.verificar()
        self.assertEqual(self.state.status, INACTIVE)

        self.linha(medida(3.5))
        self.assertEqual(self.state.status, RUNNING)


if __name__ == "__main__":
    unittest.main()
