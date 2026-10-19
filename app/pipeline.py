"""Fluxo do Módulo 2:

linha do Arduino -> protocol/balanca -> core/ensaio (ciclo do ensaio) -> data.json (interface local)
comando do operador ----------------^                                -> política de envio -> Módulo 3
"""

import json
import os
import time

from app.console import AJUDA, interpretar_comando
from core.ensaio import COLAPSO, FIM_MANUAL, NOVO_ENSAIO, ControleEnsaio
from core.system_state import SystemState
from core.telemetria import COMPLETED, PoliticaEnvio
from protocol.balanca import COMANDO_TARA, Medida, interpretar_linha
from sender.modulo3_payload import TAMANHO_MAXIMO_TEAM_CODE, build_capture_payload


class Pipeline:
    def __init__(
        self,
        equipe_padrao,
        receiver,
        sender,
        arquivo_estado=None,
        intervalo_envio_s=1.0,
        clock=time.monotonic,
        **regras_colapso,
    ):
        self.equipe_padrao = equipe_padrao
        self.receiver = receiver
        self.sender = sender
        self.arquivo_estado = arquivo_estado
        self.state = SystemState(equipe=equipe_padrao)
        self.controle = ControleEnsaio(self.state, clock=clock, **regras_colapso)
        self.politica = PoliticaEnvio(intervalo_envio_s, clock=clock)
        self._ultima_linha_impressa = None
        self.salvar_estado()

    # ---- linhas do Arduino ----

    def processar_linha(self, linha: str) -> list:
        evento = interpretar_linha(linha)
        if evento is None:
            print(f"   [Arduino] {linha}")
            return []

        eventos = self.controle.processar(evento)
        envios = self._enviar(eventos)

        if isinstance(evento, Medida):
            self._imprimir_medida(envios)
        elif self._ultima_linha_impressa != linha:
            print(f"   [Arduino] {linha}")
        self._ultima_linha_impressa = linha

        self.salvar_estado()
        return envios

    def verificar(self):
        status = self.state.status
        self.controle.verificar()
        if self.state.status != status:
            if self.state.mensagem:
                print(f"⚠️  {self.state.mensagem}")
            self.salvar_estado()

    # ---- comandos do operador ----

    def executar_comando(self, texto: str) -> bool:
        """Executa um comando do operador. Devolve False para encerrar o programa."""
        comando, argumento = interpretar_comando(texto)
        if comando is None:
            if argumento:
                print(f"Comando desconhecido: {argumento}. Digite 'ajuda'.")
            return True

        if comando == "sair":
            return False
        if comando == "ajuda":
            print(AJUDA)
        elif comando == "novo":
            equipe = argumento or self.state.equipe or self.equipe_padrao
            if not equipe:
                print("Informe a equipe: novo CODIGO")
            elif len(equipe) > TAMANHO_MAXIMO_TEAM_CODE:
                print(f"Código de equipe com mais de {TAMANHO_MAXIMO_TEAM_CODE} caracteres: {equipe}")
            elif self.controle.novo_ensaio(equipe):
                self.receiver.enviar_comando(COMANDO_TARA)
                print(f"⚖️  Tarando para o ensaio da equipe {equipe} — mantenha a balança SEM CARGA.")
            else:
                print("Já há um ensaio em andamento. Use 'fim' ou 'cancelar' antes.")
        elif comando == "fim":
            eventos = self.controle.finalizar()
            if eventos:
                self._enviar(eventos)
                print(f"🏁 Ensaio encerrado pelo operador — carga máxima {self.state.peso_max:.1f} kg")
            else:
                print("Nenhum ensaio em andamento.")
        elif comando == "cancelar":
            if self.controle.cancelar():
                print("🚫 Ensaio cancelado sem registrar resultado no Módulo 3.")
            else:
                print("Nenhum ensaio para cancelar.")
        elif comando == "tara":
            if self.controle.tarar():
                self.receiver.enviar_comando(COMANDO_TARA)
                print("⚖️  Tarando — mantenha a balança SEM CARGA.")
            else:
                print("Não é possível tarar durante um ensaio.")

        self.salvar_estado()
        return True

    # ---- internos ----

    def _enviar(self, eventos) -> list:
        envios = self.politica.decidir(eventos, self.state.status, self.state.peso_atual)
        for evento in envios:
            # A ruptura registra o pico calculado pelo Arduino sobre todas as
            # leituras do HX711, não apenas as enviadas a cada 0,5 s.
            carga = self.state.peso_max if evento == COMPLETED else self.state.peso_atual
            payload = build_capture_payload(self.state.equipe, self.state.tempo, carga, evento)
            self.sender.enviar(payload)

        if NOVO_ENSAIO in eventos:
            print(f"\n▶️  Ensaio iniciado — equipe {self.state.equipe}")
        if COLAPSO in eventos:
            print(f"💥 Colapso detectado — carga máxima {self.state.peso_max:.1f} kg\n")
        return envios

    def _imprimir_medida(self, envios):
        tempo = f"t={self.state.tempo:6.1f}s  " if self.controle.em_ensaio else ""
        print(
            f"{tempo}carga={self.state.peso_atual:6.1f} kg  pico={self.state.peso_max:6.1f} kg  "
            f"{self.state.status:8s} {' '.join(envios)}"
        )

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
            # nesse instante; a próxima linha grava de novo.
            print(f"⚠️  Não foi possível gravar {self.arquivo_estado}: {e}")
