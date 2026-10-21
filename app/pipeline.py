"""Fluxo do Módulo 2:

linha do Arduino -> protocol/balanca -> core/ensaio (ciclo do ensaio) -> data.json (interface local)
comando do operador ----------------^                                -> política de envio -> Módulo 3
ensaio armado no Módulo 3 (consulta periódica) -----------------------^
"""

import json
import os
import time

from app.console import AJUDA, interpretar_comando
from core.ensaio import COLAPSO, FIM_MANUAL, INTERROMPIDO, NOVO_ENSAIO, ControleEnsaio
from core.system_state import BROKEN, FINALIZADO, IDLE, SystemState
from core.telemetria import COMPLETED, PoliticaEnvio
from protocol.balanca import COMANDO_TARA, Medida, interpretar_linha
from sender.modulo3_payload import base_sequencia, build_capture_payload


class Pipeline:
    def __init__(
        self,
        device_code,
        receiver,
        sender,
        consulta=None,
        arquivo_estado=None,
        intervalo_envio_s=1.0,
        clock=time.monotonic,
        **regras_colapso,
    ):
        self.device_code = device_code
        self.receiver = receiver
        self.sender = sender
        self.consulta = consulta
        self.arquivo_estado = arquivo_estado
        self.state = SystemState()
        self.controle = ControleEnsaio(self.state, clock=clock, **regras_colapso)
        self.politica = PoliticaEnvio(intervalo_envio_s, clock=clock)

        self.armado = None       # ensaio armado no Módulo 3 para este M2
        self._run = None         # ensaio do Módulo 3 ao qual as leituras atuais pertencem
        self._sequencia = 0
        self._ultima_linha_impressa = None
        self.salvar_estado()

    # ---- linhas do Arduino ----

    def processar_linha(self, linha: str) -> list:
        evento = interpretar_linha(linha)
        if evento is None:
            print(f"   [Arduino] {linha}")
            return []

        if not isinstance(evento, Medida) and self._ultima_linha_impressa != linha:
            print(f"   [Arduino] {linha}")
        self._ultima_linha_impressa = linha

        eventos = self.controle.processar(evento)
        envios = self._enviar(eventos)
        if isinstance(evento, Medida):
            self._imprimir_medida(envios)

        self._atualizar_aviso()
        self.salvar_estado()
        return envios

    def verificar(self):
        status = self.state.status
        self.controle.verificar()
        mudou = self.atualizar_ensaio_remoto()
        if self.state.status != status or mudou:
            if self.state.status != status and self.state.mensagem:
                print(f"⚠️  {self.state.mensagem}")
            self.salvar_estado()

    # ---- ensaio armado no Módulo 3 ----

    def atualizar_ensaio_remoto(self) -> bool:
        """Acompanha o ensaio armado para este M2. Devolve True se algo mudou."""
        if self.consulta is None:
            return False
        atual = self.consulta.atual()
        if atual is None:
            return False  # sem resposta do Módulo 3: mantém o que já se sabe

        novo = atual or None
        anterior = self.armado
        if (novo and novo.run_id) == (anterior and anterior.run_id):
            self.armado = novo
            return False
        self.armado = novo

        # O ensaio em andamento foi cancelado ou encerrado no Módulo 3
        if self._run is not None and (novo is None or novo.run_id != self._run.run_id):
            if self.controle.cancelar():
                print("🚫 Ensaio cancelado/encerrado no Módulo 3 — leituras deste ensaio interrompidas.")
            self._run = None

        if novo is not None:
            print(
                f"\n📋 Ensaio armado no Módulo 3: {novo.equipe_nome} ({novo.equipe_codigo}).\n"
                "   Com a balança SEM CARGA, digite: novo\n"
            )
        self._atualizar_aviso()
        return True

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
            self._novo(argumento)
        elif comando == "fim":
            eventos = self.controle.finalizar()
            if eventos:
                self._enviar(eventos)
                print(f"🏁 Ensaio encerrado pelo operador — carga máxima {self.state.peso_max:.1f} kg")
            else:
                print("Nenhum ensaio em andamento.")
        elif comando == "cancelar":
            if self.controle.cancelar():
                self._run = None
                print("🚫 Ensaio cancelado no Módulo 2. Cancele também em Administração → Ensaios no Módulo 3.")
            else:
                print("Nenhum ensaio para cancelar.")
        elif comando == "tara":
            if self.controle.tarar():
                self.receiver.enviar_comando(COMANDO_TARA)
                print("⚖️  Tarando — mantenha a balança SEM CARGA.")
            else:
                print("Não é possível tarar durante um ensaio.")

        self._atualizar_aviso()
        self.salvar_estado()
        return True

    # ---- internos ----

    def _novo(self, equipe_digitada):
        armado = self.armado
        if armado is None:
            print(
                f"Nenhum ensaio armado para {self.device_code} no Módulo 3. "
                "Arme em Administração → Ensaios e aguarde a confirmação aqui."
            )
            return
        if equipe_digitada and equipe_digitada != armado.equipe_codigo.upper():
            print(
                f"O ensaio armado é da equipe {armado.equipe_codigo}, não {equipe_digitada}. "
                "Digite apenas: novo"
            )
            return
        if not self.controle.novo_ensaio(armado.equipe_codigo):
            print("Já há um ensaio em andamento. Use 'fim' ou 'cancelar' antes.")
            return

        self._run = armado
        self._sequencia = base_sequencia()
        self.receiver.enviar_comando(COMANDO_TARA)
        print(f"⚖️  Tarando para o ensaio de {armado.equipe_nome} — mantenha a balança SEM CARGA.")

    def _enviar(self, eventos) -> list:
        envios = self.politica.decidir(eventos, self.state.status, self.state.peso_atual)
        if self._run is None:
            envios = []  # ensaio cancelado/encerrado no Módulo 3
        for evento in envios:
            # A ruptura registra o pico calculado pelo Arduino sobre todas as
            # leituras do HX711, não apenas as enviadas a cada 0,5 s.
            carga = self.state.peso_max if evento == COMPLETED else self.state.peso_atual
            self._sequencia += 1
            payload = build_capture_payload(
                self._run.run_id, self.device_code, self._sequencia, self.state.tempo, carga, evento
            )
            self.sender.enviar(payload)

        if NOVO_ENSAIO in eventos and self._run is not None:
            print(f"\n▶️  Ensaio iniciado — {self._run.equipe_nome} ({self._run.equipe_codigo})")
        if COLAPSO in eventos:
            print(f"💥 Colapso detectado — carga máxima {self.state.peso_max:.1f} kg\n")
        if COLAPSO in eventos or FIM_MANUAL in eventos or INTERROMPIDO in eventos:
            self._run = None
        return envios

    def _atualizar_aviso(self):
        """Mensagem do painel quando há um ensaio armado aguardando o operador."""
        if self.controle.em_ensaio or self.state.status not in (IDLE, BROKEN, FINALIZADO):
            return
        if self.armado is not None and self._run is None:
            self.state.equipe = self.armado.equipe_codigo
            self.state.mensagem = f"Ensaio armado: {self.armado.equipe_nome} — aguardando 'novo' no Módulo 2"
        elif self.state.status == IDLE:
            self.state.mensagem = None

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
