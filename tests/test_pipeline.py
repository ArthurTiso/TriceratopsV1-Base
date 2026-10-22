"""Fluxos do Módulo 2 com o Módulo 3: início pelo M3 ou pelo M2, modo local,
encerramento pelo M3 e confirmações do envio."""

import csv
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from apoio import RelogioFalso
from app.pipeline import Pipeline
from core.system_state import BROKEN, FINALIZADO, IDLE, RUNNING, RUPTURA_DETECTADA
from protocol.balanca import formatar_medida
from sender.ensaio_ativo import EnsaioArmado

RUN = "0b6f8a3e-7c1e-4a55-9d3a-2f6c1c9e8b10"


class ConsultaFalsa:
    def __init__(self):
        self.resposta = False   # sem ensaio ativo
        self.esta_online = True

    def atual(self):
        return self.resposta if self.esta_online else None

    def online(self):
        return self.esta_online


class ReceiverFalso:
    conectado = True

    def __init__(self):
        self.comandos = []

    def enviar_comando(self, comando):
        self.comandos.append(comando)


class SenderFalso:
    def __init__(self):
        self.payloads = []
        self.ao_concluir = None

    def enviar(self, payload):
        self.payloads.append(payload)

    def confirmar(self, evento, ok=True, detalhe="confirmado"):
        payload = next(p for p in reversed(self.payloads) if p["event"] == evento)
        self.ao_concluir(payload, ok, detalhe)


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.relogio = RelogioFalso()
        self.consulta = ConsultaFalsa()
        self.receiver = ReceiverFalso()
        self.sender = SenderFalso()
        self.csv = Path(tempfile.mkdtemp()) / "resultados.csv"
        patcher = mock.patch("builtins.print")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.pipeline = Pipeline(
            "M2-01", self.receiver, self.sender, consulta=self.consulta,
            arquivo_resultados=self.csv, clock=self.relogio,
        )

    # ---- auxiliares ----

    def m3(self, status, run_id=RUN, equipe=("EQ01", "Ponte Forte")):
        self.consulta.resposta = EnsaioArmado(run_id, status, *equipe) if status else False
        self.pipeline.verificar()

    def linha(self, texto, avancar=0.5):
        self.pipeline.processar_linha(texto)
        self.relogio.avancar(avancar)

    def tara_do_arduino(self):
        self.linha("Tarando: deixe a balanca sem carga (20 amostras).")
        self.linha("TARA=10/20 | BRUTO=1")
        self.linha("Tara concluida. Offset=1")

    def carregar_e_romper(self, pico=8.0, confirmar=True):
        for kg in range(1, int(pico) + 1):
            self.linha(formatar_medida(kg, kg, kg, 0))
        for _ in range(3):
            self.linha(formatar_medida(0.1, 0.1, pico, 0))
        if confirmar:  # botão "Confirmar ruptura" do painel
            self.pipeline.executar_comando("fim")

    def eventos(self):
        return [p["event"] for p in self.sender.payloads]

    def resultados_csv(self):
        if not self.csv.exists():
            return []
        with open(self.csv, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f, delimiter=";"))

    # ---- início pelo Módulo 3 ----

    def test_iniciar_in_module_3_starts_the_test_in_module_2(self):
        self.m3("armed")
        self.assertEqual(self.receiver.comandos, [])

        self.m3("running")  # botão "Iniciar" no Módulo 3
        self.assertEqual(self.receiver.comandos, ["t"])

        self.tara_do_arduino()
        self.assertEqual(self.pipeline.state.status, RUNNING)
        self.assertEqual(self.eventos(), ["started"])
        self.assertEqual(self.sender.payloads[0]["test_run_id"], RUN)

    def test_a_run_already_running_when_m2_opens_is_not_tared_automatically(self):
        self.m3("running")  # M2 reaberto no meio do ensaio: a ponte pode estar carregada

        self.assertEqual(self.receiver.comandos, [])
        self.assertEqual(self.pipeline.state.status, IDLE)

    def test_novo_in_module_2_does_not_tare_twice_when_module_3_goes_running(self):
        self.m3("armed")
        self.pipeline.executar_comando("novo")
        self.tara_do_arduino()

        self.m3("running")  # consequência do "started" do próprio M2

        self.assertEqual(self.receiver.comandos, ["t"])
        self.assertEqual(self.pipeline.state.status, RUNNING)

    def test_unconfirmed_tare_frees_the_run_for_a_new_start(self):
        self.m3("armed")
        self.pipeline.executar_comando("novo")
        self.relogio.avancar(6)  # Arduino não respondeu ao "t"
        self.pipeline.verificar()

        self.m3("running")

        self.assertEqual(self.receiver.comandos, ["t", "t"])

    # ---- início pelo Módulo 2 ----

    def test_typed_team_must_match_the_armed_run(self):
        self.m3("armed")

        self.pipeline.executar_comando("novo OUTRA")
        self.assertEqual(self.receiver.comandos, [])
        self.pipeline.executar_comando("novo ponte forte")
        self.assertEqual(self.receiver.comandos, ["t"])

    def test_without_armed_run_and_without_team_nothing_starts(self):
        self.pipeline.executar_comando("novo")

        self.assertEqual(self.receiver.comandos, [])

    # ---- modo local ----

    def test_local_mode_when_module_3_is_offline(self):
        self.m3("armed")
        self.consulta.esta_online = False
        self.relogio.avancar(1)
        self.pipeline.verificar()

        self.pipeline.executar_comando("novo equipe 07")
        self.tara_do_arduino()
        self.carregar_e_romper(pico=8)

        self.assertEqual(self.pipeline.state.status, BROKEN)
        self.assertEqual(self.sender.payloads, [])  # nada vai para o Módulo 3
        linhas = self.resultados_csv()
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]["equipe_nome"], "EQUIPE 07")
        self.assertEqual(linhas[0]["carga_ruptura_kg"], "8,0")
        self.assertEqual(linhas[0]["modo"], "local")

    def test_local_mode_also_works_with_module_3_online_but_no_armed_run(self):
        self.pipeline.executar_comando("novo equipe 07")
        self.tara_do_arduino()

        self.assertEqual(self.pipeline.state.status, RUNNING)
        self.assertEqual(self.sender.payloads, [])

    # ---- fim ----

    def test_detected_rupture_waits_for_the_operator_before_telling_module_3(self):
        self.m3("armed")
        self.m3("running")
        self.tara_do_arduino()
        self.carregar_e_romper(pico=8, confirmar=False)

        self.assertEqual(self.pipeline.state.status, RUPTURA_DETECTADA)
        self.assertTrue(self.pipeline.state.extras["ruptura_detectada"])
        self.assertNotIn("completed", self.eventos())
        self.linha(formatar_medida(0.1, 0.1, 8, 0), avancar=1)
        self.linha(formatar_medida(0.1, 0.1, 8, 0))
        self.assertEqual(self.eventos()[-1], "sample")  # o ensaio segue aberto no Módulo 3
        self.assertEqual(self.resultados_csv(), [])

        self.pipeline.executar_comando("fim")

        self.assertEqual(self.pipeline.state.status, BROKEN)
        self.assertEqual(self.eventos().count("completed"), 1)
        self.assertEqual(self.sender.payloads[-1]["load_grams"], 8000)

    def test_rupture_result_is_written_after_module_3_confirms(self):
        self.m3("armed")
        self.m3("running")
        self.tara_do_arduino()
        self.carregar_e_romper(pico=8)
        self.assertEqual(self.eventos()[-1], "completed")
        self.assertEqual(self.resultados_csv(), [])  # aguardando confirmação

        self.sender.confirmar("completed")
        self.pipeline.verificar()

        linhas = self.resultados_csv()
        self.assertEqual(linhas[0]["registro_modulo3"], "confirmado")
        self.assertEqual(self.pipeline.state.extras["resultado"]["registro"], "confirmado")

    def test_rejected_result_is_flagged_for_manual_entry(self):
        self.m3("armed")
        self.m3("running")
        self.tara_do_arduino()
        self.carregar_e_romper(pico=8)

        self.sender.confirmar("completed", ok=False, detalhe="O ensaio não está aceitando novas leituras.")
        self.pipeline.verificar()

        self.assertIn("não registrado", self.resultados_csv()[0]["registro_modulo3"])

    def test_encerrar_in_module_3_keeps_the_peak_locally(self):
        self.m3("armed")
        self.m3("running")
        self.tara_do_arduino()
        for kg in (2, 4, 6):
            self.linha(formatar_medida(kg, kg, kg, 0))

        self.m3(None)  # "Encerrar" ou "Cancelar" no Módulo 3

        self.assertEqual(self.pipeline.state.status, FINALIZADO)
        self.assertNotIn("completed", self.eventos())
        linha = self.resultados_csv()[0]
        self.assertEqual(linha["carga_ruptura_kg"], "6,0")
        self.assertIn("lance 6.0 kg em Rupturas", linha["registro_modulo3"])

    def test_pending_confirmation_is_saved_on_exit(self):
        self.m3("armed")
        self.m3("running")
        self.tara_do_arduino()
        self.carregar_e_romper(pico=8)

        self.pipeline.finalizar()

        self.assertIn("sem confirmação", self.resultados_csv()[0]["registro_modulo3"])

    # ---- painel ----

    def test_panel_snapshot_has_module_3_and_armed_run(self):
        self.m3("armed")
        self.pipeline.salvar_estado()
        extras = self.pipeline.state.extras

        self.assertTrue(extras["m3_online"])
        self.assertEqual(extras["armado"]["equipe_nome"], "Ponte Forte")
        self.assertFalse(extras["em_ensaio"])
        self.assertTrue(any("armado" in e["texto"] for e in extras["eventos"]))


if __name__ == "__main__":
    unittest.main()
