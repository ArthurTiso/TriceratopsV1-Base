"""Fluxo de um quadro dentro do Módulo 2:

quadro -> decoder -> processor (ciclo do ensaio) -> data.json (interface local)
                                                 -> política de envio -> ApiSender (Módulo 3)
"""

import json
import os
import time

from core.processor import COLAPSO, NOVO_ENSAIO, Processor
from core.system_state import SystemState
from core.telemetria import PoliticaEnvio
from protocol.decoder import ProtocolDecoder
from sender.modulo3_payload import build_capture_payload


class Pipeline:
    def __init__(self, team_code, sender, arquivo_estado=None, intervalo_envio_s=1.0, clock=time.monotonic):
        self.team_code = team_code
        self.sender = sender
        self.arquivo_estado = arquivo_estado
        self.decoder = ProtocolDecoder()
        self.state = SystemState(equipe=team_code)
        self.processor = Processor(self.state, clock=clock)
        self.politica = PoliticaEnvio(intervalo_envio_s, clock=clock)
        self.salvar_estado()

    def processar_quadro(self, pacote: str) -> list:
        """Processa um quadro recebido e devolve os eventos enviados ao Módulo 3."""
        try:
            dados = self.decoder.decodificar(pacote)
        except ValueError as e:
            print(f"ERRO: {e} — quadro {pacote!r} descartado")
            return []

        eventos = self.processor.processar(dados)
        envios = self.politica.decidir(eventos, self.state.status, dados)
        for evento in envios:
            self.sender.enviar(build_capture_payload(self.team_code, dados, evento))

        if NOVO_ENSAIO in eventos:
            print(f"\n▶️  Novo ensaio — equipe {self.team_code}")
        print(
            f"t={dados['tempo']:4d}s  carga={dados['peso_atual']:6.1f} kg  "
            f"máx={dados['peso_max']:6.1f} kg  flag={dados['flag']}  "
            f"{self.state.status:8s} {' '.join(envios)}"
        )
        if COLAPSO in eventos:
            print(f"💥 Colapso detectado — carga máxima {self.state.peso_max:.1f} kg\n")

        self.salvar_estado()
        return envios

    def verificar_inatividade(self):
        if self.processor.verificar_inatividade():
            print("⚠️  Sem quadros do Módulo 1 — ensaio marcado como INATIVO")
            self.salvar_estado()

    def salvar_estado(self):
        """Grava o snapshot lido pela interface local (Streamlit)."""
        if not self.arquivo_estado:
            return
        temporario = f"{self.arquivo_estado}.tmp"
        try:
            with open(temporario, "w", encoding="utf-8") as f:
                json.dump(self.state.get_snapshot(), f)
            # Troca atômica: o painel nunca lê um arquivo pela metade.
            os.replace(temporario, self.arquivo_estado)
        except OSError as e:
            # No Windows a troca falha se o painel estiver lendo o arquivo
            # nesse instante; o próximo quadro grava de novo.
            print(f"⚠️  Não foi possível gravar {self.arquivo_estado}: {e}")
