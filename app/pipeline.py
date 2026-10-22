"""Fluxo do Módulo 2:

linha do Arduino -> protocol/balanca -> core/ensaio (ciclo do ensaio) -> data.json (painel)
comandos (terminal ou painel) ------^                                -> política de envio -> Módulo 3
ensaio armado no Módulo 3 (consulta periódica) -----------------------^

Formas de iniciar um ensaio (todas fazem a tara e começam a medir):
* "Iniciar" no Módulo 3 — o M2 percebe o ensaio passar de armado para em
  andamento e começa sozinho;
* "novo" no terminal ou "Iniciar ensaio" no painel, com um ensaio armado;
* "novo EQUIPE" sem ensaio armado (ou com o Módulo 3 fora do ar): modo local,
  sem envio; o resultado fica em resultados.csv.

O fim do ensaio só chega ao Módulo 3 quando o operador confirma a ruptura
("Confirmar ruptura" no painel ou "fim" no terminal). A queda de carga
detectada apenas avisa o operador; até a confirmação o ensaio segue medindo.
"""

import json
import os
import queue
import time
from collections import deque
from datetime import datetime

from app.console import AJUDA, interpretar_comando
from core.ensaio import COLAPSO, COLAPSO_DESFEITO, FIM_MANUAL, INTERROMPIDO, NOVO_ENSAIO, ControleEnsaio
from core.resultados import CONFIRMADO, ENVIANDO, LOCAL, RegistroResultados, novo_resultado
from core.system_state import BROKEN, FINALIZADO, IDLE, INACTIVE, TARANDO, SystemState
from core.telemetria import COMPLETED, STARTED, PoliticaEnvio
from protocol.balanca import COMANDO_TARA, Medida, interpretar_linha
from sender.ensaio_ativo import EnsaioArmado
from sender.modulo3_payload import base_sequencia, build_capture_payload

TAMANHO_MAXIMO_EQUIPE = 32
INTERVALO_SALVAMENTO_S = 1.0


class Pipeline:
    def __init__(
        self,
        device_code,
        receiver,
        sender,
        consulta=None,
        arquivo_estado=None,
        arquivo_resultados=None,
        intervalo_envio_s=1.0,
        clock=time.monotonic,
        **regras_colapso,
    ):
        self.device_code = device_code
        self.receiver = receiver
        self.sender = sender
        self.consulta = consulta
        self.arquivo_estado = arquivo_estado
        self.resultados = RegistroResultados(arquivo_resultados)
        self.state = SystemState()
        self.controle = ControleEnsaio(self.state, clock=clock, **regras_colapso)
        self.politica = PoliticaEnvio(intervalo_envio_s, clock=clock)
        self._clock = clock

        self.armado = None       # ensaio armado no Módulo 3 para este M2
        self._run = None         # ensaio ao qual as leituras atuais pertencem
        self._sequencia = 0
        self._resultado = None   # último resultado (exibido no painel)
        self._retornos = queue.Queue()  # confirmações do envio (thread do ApiSender)
        self._eventos = deque(maxlen=8)
        self._ultimo_erro_amostra = None
        self._ultimo_salvamento = None
        self._m3_online = None
        self._ultima_linha_impressa = None

        if hasattr(sender, "ao_concluir"):
            sender.ao_concluir = self._retorno_envio
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
        envios = self._tratar_eventos(eventos)
        if isinstance(evento, Medida):
            self._imprimir_medida(envios)

        self._processar_retornos()
        self._atualizar_aviso()
        self.salvar_estado()
        return envios

    def verificar(self):
        """Chamada a cada ciclo sem linha nova: inatividade, Módulo 3 e confirmações."""
        status = self.state.status
        self.controle.verificar()
        if self._run is not None and not self.controle.em_ensaio and not self.controle.aguardando_tara:
            self._run = None  # o Arduino não confirmou a tara: o pedido de ensaio foi descartado
        mudou = self.atualizar_ensaio_remoto()
        mudou = self._processar_retornos() or mudou
        if self.state.status != status and self.state.mensagem:
            print(f"⚠️  {self.state.mensagem}")
        if (
            mudou
            or self.state.status != status
            or self._ultimo_salvamento is None
            or self._clock() - self._ultimo_salvamento >= INTERVALO_SALVAMENTO_S
        ):
            self.salvar_estado()

    def finalizar(self):
        """No encerramento do programa, depois de esvaziar a fila de envio."""
        self._processar_retornos()
        if self._resultado is not None and self._resultado["registro"] == ENVIANDO:
            self._resultado["registro"] = "sem confirmação (programa encerrado)"
            self.resultados.gravar(self._resultado)
        self.salvar_estado()

    # ---- ensaio armado no Módulo 3 ----

    def atualizar_ensaio_remoto(self) -> bool:
        """Acompanha o ensaio armado para este M2. Devolve True se algo mudou."""
        if self.consulta is None:
            return False
        online = self.consulta.online()
        mudou = online != self._m3_online
        if mudou and online is True:
            self._evento("Módulo 3 respondeu novamente" if self._m3_online is False
                         else "Módulo 3 conectado", "ok")
        elif mudou and online is False:
            self._evento("Módulo 3 sem resposta — controle manual liberado", "aviso")
        self._m3_online = online

        atual = self.consulta.atual()
        if atual is None:
            return mudou  # sem resposta do Módulo 3: mantém o que já se sabe

        novo = atual or None
        anterior = self.armado
        self.armado = novo
        mesmo_ensaio = (novo and novo.run_id) == (anterior and anterior.run_id)

        if mesmo_ensaio:
            if (
                novo is not None
                and anterior.status == "armed"
                and novo.status == "running"
                and self._run is None
                and not self.controle.em_ensaio
            ):
                self._evento("Iniciado pelo Módulo 3", "info")
                self._iniciar(novo, origem="Módulo 3")
                return True
            return mudou

        # O ensaio em andamento foi encerrado ou cancelado no Módulo 3
        if self._run is not None and self._run.run_id and (novo is None or novo.run_id != self._run.run_id):
            self._encerrado_no_modulo3()

        if novo is not None:
            self._evento(f"Ensaio armado no Módulo 3: {novo.equipe_nome}", "info")
            print(
                f"\n📋 Ensaio armado no Módulo 3: {novo.equipe_nome} ({novo.equipe_codigo}).\n"
                "   Inicie pelo Módulo 3 (Iniciar) ou aqui, com a balança SEM CARGA: novo\n"
            )
        self._atualizar_aviso()
        return True

    # ---- comandos do operador (terminal ou painel) ----

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
                self._evento(f"Ruptura confirmada: {self.state.peso_max:.1f} kg", "ruptura")
                self._tratar_eventos(eventos)
            else:
                self._aviso("Nenhum ensaio em andamento para confirmar a ruptura.")
        elif comando == "cancelar":
            if self.controle.cancelar():
                remoto = self._run is not None and self._run.run_id
                self._run = None
                self._evento("Ensaio cancelado no Módulo 2", "aviso")
                if remoto:
                    print("   Cancele também em Administração → Ensaios no Módulo 3.")
            else:
                self._aviso("Nenhum ensaio para cancelar.")
        elif comando == "tara":
            if self.controle.tarar():
                self.receiver.enviar_comando(COMANDO_TARA)
                self._evento("Tara pedida — mantenha a balança sem carga", "info")
            else:
                self._aviso("Não é possível tarar durante um ensaio.")

        self._atualizar_aviso()
        self.salvar_estado()
        return True

    # ---- início e fim de ensaio ----

    def _novo(self, equipe_digitada):
        if self.controle.em_ensaio or self.state.status == TARANDO:
            self._aviso("Já há um ensaio em andamento. Use 'fim' ou 'cancelar' antes.")
            return

        armado = self.armado if self._m3_disponivel() else None
        if armado is not None:
            if equipe_digitada and equipe_digitada not in (
                armado.equipe_codigo.upper(), armado.equipe_nome.upper()
            ):
                self._aviso(
                    f"O ensaio armado no Módulo 3 é da equipe {armado.equipe_nome} "
                    f"({armado.equipe_codigo}), não {equipe_digitada}."
                )
                return
            self._iniciar(armado, origem="Módulo 2")
            return

        if not equipe_digitada:
            self._aviso(
                "Nenhum ensaio armado no Módulo 3. Arme lá ou informe a equipe para o modo local "
                "(ex.: novo EQUIPE07)."
            )
            return
        if len(equipe_digitada) > TAMANHO_MAXIMO_EQUIPE:
            self._aviso("Nome de equipe muito longo.")
            return
        if self._m3_disponivel():
            self._evento("Módulo 3 sem ensaio armado — resultado só local", "aviso")
        local = EnsaioArmado(run_id=None, status="local", equipe_codigo=equipe_digitada,
                             equipe_nome=equipe_digitada)
        self._iniciar(local, origem="modo local")

    def _iniciar(self, ensaio, origem):
        if not self.controle.novo_ensaio(ensaio.equipe_codigo):
            self._aviso("Já há um ensaio em andamento.")
            return
        self._run = ensaio
        self._sequencia = base_sequencia()
        self._resultado = None
        self._ultimo_erro_amostra = None
        self.state.equipe_nome = ensaio.equipe_nome
        self.receiver.enviar_comando(COMANDO_TARA)
        self._evento(f"Tarando para {ensaio.equipe_nome} ({origem}) — não toque na ponte", "info")

    def _encerrado_no_modulo3(self):
        """O ensaio foi encerrado/cancelado no Módulo 3 enquanto este M2 o acompanhava."""
        run = self._run
        self._run = None
        if self.controle.encerrar_sem_resultado():  # congela o pico; o Módulo 3 já não aceita leituras
            self._registrar_resultado(
                run, "encerrado/cancelado no Módulo 3",
                f"não registrado — lance {self.state.peso_max:.1f} kg em Rupturas se for o caso",
            )
            self.state.set_status(FINALIZADO, "Ensaio encerrado no Módulo 3 sem a carga do M2")
            self._evento(
                f"Encerrado/cancelado no Módulo 3 — pico {self.state.peso_max:.1f} kg não registrado",
                "aviso",
            )
        elif self.controle.cancelar():
            self._evento("Ensaio cancelado no Módulo 3 antes de começar", "aviso")

    def _tratar_eventos(self, eventos) -> list:
        run = self._run
        envios = self.politica.decidir(eventos, self.state.status, self.state.peso_atual)
        if run is None or run.run_id is None:
            envios = []  # modo local ou ensaio encerrado no Módulo 3: nada a enviar
        for evento in envios:
            # A ruptura registra o pico calculado pelo Arduino sobre todas as
            # leituras do HX711, não apenas as enviadas a cada 0,5 s.
            carga = self.state.peso_max if evento == COMPLETED else self.state.peso_atual
            self._sequencia += 1
            payload = build_capture_payload(
                run.run_id, self.device_code, self._sequencia, self.state.tempo, carga, evento
            )
            self.sender.enviar(payload)

        if NOVO_ENSAIO in eventos and run is not None:
            self._evento(f"Ensaio iniciado — {run.equipe_nome}", "ok")
        if COLAPSO in eventos:
            self._evento(f"Ruptura detectada: {self.state.peso_max:.1f} kg — confirme no painel", "ruptura")
            print(
                f"💥 Queda de carga detectada — carga máxima {self.state.peso_max:.1f} kg.\n"
                "   Confirme a ruptura no painel (Confirmar ruptura) ou digite: fim\n"
            )
        if COLAPSO_DESFEITO in eventos:
            self._evento("A carga voltou a subir — ensaio continua", "aviso")
        if FIM_MANUAL in eventos and run is not None:
            self._registrar_resultado(run, "ruptura confirmada no Módulo 2", ENVIANDO if run.run_id else LOCAL)
        if INTERROMPIDO in eventos:
            self._evento("Ensaio interrompido (Arduino reiniciou)", "aviso")
        if FIM_MANUAL in eventos or INTERROMPIDO in eventos:
            self._run = None
        return envios

    def _registrar_resultado(self, run, motivo, registro):
        self._resultado = novo_resultado(
            equipe_codigo=run.equipe_codigo,
            equipe_nome=run.equipe_nome,
            carga_kg=self.state.peso_max,
            duracao_s=self.state.tempo,
            motivo=motivo,
            modo="Módulo 3" if run.run_id else "local",
            run_id=run.run_id,
            registro=registro,
        )
        if registro != ENVIANDO:  # aguardando a confirmação do Módulo 3 para gravar
            self.resultados.gravar(self._resultado)
            if registro == LOCAL:
                self._evento("Resultado salvo em resultados.csv", "info")

    # ---- confirmações do Módulo 3 ----

    def _retorno_envio(self, payload, ok, detalhe):
        """Chamado pela thread do ApiSender; processado no ciclo principal."""
        self._retornos.put((payload, ok, detalhe))

    def _processar_retornos(self) -> bool:
        mudou = False
        while True:
            try:
                payload, ok, detalhe = self._retornos.get_nowait()
            except queue.Empty:
                return mudou
            mudou = True
            evento = payload.get("event")
            if evento == STARTED:
                self._evento("Módulo 3 confirmou o início" if ok else f"Módulo 3 recusou o início: {detalhe}",
                             "ok" if ok else "erro")
            elif evento == COMPLETED:
                resultado = self._resultado
                if resultado is not None and resultado.get("run_id") == payload.get("test_run_id"):
                    resultado["registro"] = CONFIRMADO if ok else f"não registrado ({detalhe})"
                    self.resultados.gravar(resultado)
                self._evento("Módulo 3 registrou o resultado" if ok else f"Resultado NÃO registrado: {detalhe}",
                             "ok" if ok else "erro")
            elif not ok and detalhe != self._ultimo_erro_amostra:
                self._ultimo_erro_amostra = detalhe
                self._evento(f"Leitura recusada pelo Módulo 3: {detalhe}", "erro")

    # ---- painel e terminal ----

    def _m3_disponivel(self) -> bool:
        return self.consulta is not None and self._m3_online is True

    def _evento(self, texto, tipo="info"):
        self._eventos.append({"hora": datetime.now().strftime("%H:%M:%S"), "texto": texto, "tipo": tipo})
        print(f"• {texto}")

    def _aviso(self, texto):
        self._evento(texto, "aviso")

    def _atualizar_aviso(self):
        """Mensagem do painel quando há um ensaio armado aguardando o operador."""
        if self.controle.em_ensaio or self.state.status not in (IDLE, BROKEN, FINALIZADO):
            return
        if self.armado is not None and self._run is None and self._m3_disponivel():
            self.state.equipe = self.armado.equipe_codigo
            self.state.equipe_nome = self.armado.equipe_nome
            self.state.mensagem = f"Pronto: {self.armado.equipe_nome} — inicie pelo Módulo 3 ou pelo Módulo 2"
        elif self.state.status == IDLE or (self.state.mensagem or "").startswith("Pronto:"):
            self.state.mensagem = None

    def _imprimir_medida(self, envios):
        tempo = f"t={self.state.tempo:6.1f}s  " if self.controle.em_ensaio else ""
        print(
            f"{tempo}carga={self.state.peso_atual:6.1f} kg  pico={self.state.peso_max:6.1f} kg  "
            f"{self.state.status:8s} {' '.join(envios)}"
        )

    def _extras(self):
        armado = self.armado if self._m3_disponivel() else None
        conectado = getattr(self.receiver, "conectado", True)
        return {
            "device_code": self.device_code,
            "em_ensaio": self.controle.em_ensaio,
            "ruptura_detectada": self.controle.ruptura_detectada,
            "modo": None if self._run is None else ("local" if self._run.run_id is None else "Módulo 3"),
            "m3_online": self._m3_online,
            "balanca_online": bool(conectado) and self.state.status != INACTIVE,
            "armado": None if armado is None else {
                "equipe_codigo": armado.equipe_codigo,
                "equipe_nome": armado.equipe_nome,
                "status": armado.status,
            },
            "resultado": None if self._resultado is None else {
                "carga_kg": self._resultado["carga_kg"],
                "registro": self._resultado["registro"],
                "modo": self._resultado["modo"],
            },
            "eventos": list(self._eventos),
        }

    def salvar_estado(self):
        """Grava o snapshot lido pelo painel (Streamlit)."""
        self._ultimo_salvamento = self._clock()
        self.state.extras = self._extras()
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
            # nesse instante; o próximo ciclo grava de novo.
            print(f"⚠️  Não foi possível gravar {self.arquivo_estado}: {e}")
