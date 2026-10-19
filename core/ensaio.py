"""Controle do ensaio a partir das linhas da balança (Módulo 1) e dos comandos
do operador.

O Módulo 1 apenas mede: não sabe quando um ensaio começa nem quando a ponte
rompe. O ciclo fica aqui:

1. ``novo`` (operador) → envia ``t`` ao Arduino → TARANDO;
2. ``Tara concluida`` → início do ensaio: cronômetro em 0, evento NOVO_ENSAIO;
3. a cada medida: carga = |MEDIA_KG|, pico = PICO_ABS_KG (calculado pelo
   Arduino sobre todas as leituras do HX711, não só as enviadas);
4. colapso: pico >= 2 kg e carga <= 20% do pico por pelo menos 1 s → COLAPSO;
   o operador também pode encerrar com ``fim`` → FIM_MANUAL.

Uma tara que o Módulo 2 não pediu durante o ensaio (Arduino reiniciado ou
cabo reconectado) interrompe o ensaio sem enviar ``completed``.
"""

import time

from core.system_state import (
    BROKEN,
    ERRO_SENSOR,
    FINALIZADO,
    IDLE,
    INACTIVE,
    RUNNING,
    TARANDO,
)
from protocol.balanca import ErroSensor, Medida, TaraConcluida, TaraIniciada, TaraProgresso

NOVO_ENSAIO = "novo_ensaio"
COLAPSO = "colapso"
FIM_MANUAL = "fim_manual"
INTERROMPIDO = "interrompido"

PESO_MINIMO_COLAPSO_KG = 2.0
FRACAO_COLAPSO = 0.20
CONFIRMACAO_COLAPSO_S = 1.0
INATIVIDADE_S = 5.0          # o Arduino imprime uma linha a cada 0,5 s
TEMPO_MAXIMO_RESPOSTA_TARA_S = 5.0

_EPSILON = 1e-9


class ControleEnsaio:
    def __init__(
        self,
        state,
        clock=time.monotonic,
        peso_minimo_colapso_kg=PESO_MINIMO_COLAPSO_KG,
        fracao_colapso=FRACAO_COLAPSO,
        confirmacao_colapso_s=CONFIRMACAO_COLAPSO_S,
        inatividade_s=INATIVIDADE_S,
    ):
        self.state = state
        self._clock = clock
        self._peso_minimo = peso_minimo_colapso_kg
        self._fracao = fracao_colapso
        self._confirmacao_s = confirmacao_colapso_s
        self._inatividade_s = inatividade_s

        self.em_ensaio = False
        self._equipe_pendente = None    # equipe que começa quando a tara terminar
        self._tara_pedida_em = None     # aguardando o Arduino confirmar a tara
        self._inicio = None
        self._inicio_tara = None        # base do gráfico fora de ensaio
        self._ultima_linha = clock()
        self._colapso_desde = None
        self._status_antes_da_tara = IDLE

    # ---- comandos do operador ----

    def novo_ensaio(self, equipe) -> bool:
        """Pede a tara; o ensaio começa quando o Arduino confirmar. False se já há ensaio."""
        if self.em_ensaio:
            return False
        self._equipe_pendente = equipe
        self._pedir_tara()
        return True

    def tarar(self) -> bool:
        """Tara avulsa (fora de ensaio), só para zerar a balança."""
        if self.em_ensaio:
            return False
        self._equipe_pendente = None
        self._pedir_tara()
        return True

    def finalizar(self) -> list:
        """Encerra o ensaio em andamento como concluído (ruptura sem queda clara)."""
        if not self.em_ensaio:
            return []
        self._encerrar(FINALIZADO)
        return [FIM_MANUAL]

    def cancelar(self) -> bool:
        """Descarta o ensaio em andamento ou pendente, sem enviar ``completed``."""
        if not self.em_ensaio and self._equipe_pendente is None:
            return False
        self._equipe_pendente = None
        self._encerrar(IDLE)
        return True

    def tempo_ensaio(self) -> float:
        return 0.0 if self._inicio is None else self._clock() - self._inicio

    # ---- linhas do Arduino ----

    def processar(self, evento) -> list:
        agora = self._clock()
        self._ultima_linha = agora

        if isinstance(evento, (TaraIniciada, TaraProgresso)):
            return self._tara_em_andamento()
        if isinstance(evento, TaraConcluida):
            return self._tara_concluida(agora)
        if isinstance(evento, ErroSensor):
            if self.state.status != TARANDO:
                self.state.set_status(ERRO_SENSOR, evento.mensagem)
            return []
        if isinstance(evento, Medida):
            return self._medida(evento, agora)
        return []

    def verificar(self):
        """Chamada periodicamente: inatividade do cabo e tara sem resposta."""
        agora = self._clock()
        if (
            self._tara_pedida_em is not None
            and agora - self._tara_pedida_em >= TEMPO_MAXIMO_RESPOSTA_TARA_S
        ):
            print("⚠️  O Arduino não confirmou a tara — confira o cabo USB e tente de novo.")
            self._tara_pedida_em = None
            self._equipe_pendente = None
            self.state.set_status(self._status_antes_da_tara)
        if (
            self.state.status not in (INACTIVE, BROKEN, FINALIZADO)
            and agora - self._ultima_linha >= self._inatividade_s
        ):
            self.state.set_status(INACTIVE, "Sem dados da balança — confira o cabo USB.")

    # ---- internos ----

    def _pedir_tara(self):
        self._status_antes_da_tara = self.state.status
        self._tara_pedida_em = self._clock()
        self.state.set_status(TARANDO, "Tarando: mantenha a balança sem carga.")

    def _tara_em_andamento(self):
        eventos = []
        if self.em_ensaio:
            print("⚠️  Tara inesperada durante o ensaio (Arduino reiniciado?). Ensaio interrompido.")
            self._encerrar(IDLE)
            eventos.append(INTERROMPIDO)
        self._tara_pedida_em = None
        self._inicio_tara = None
        self.state.set_status(TARANDO, "Tarando: mantenha a balança sem carga.")
        return eventos

    def _tara_concluida(self, agora):
        self._tara_pedida_em = None
        self.state.reset()
        self.state.peso_atual = 0.0
        self._inicio_tara = agora
        if self._equipe_pendente is None:
            self.state.set_status(IDLE)
            return []

        self.state.equipe = self._equipe_pendente
        self._equipe_pendente = None
        self.em_ensaio = True
        self._inicio = agora
        self._colapso_desde = None
        self.state.set_status(RUNNING)
        self.state.registrar_ponto(0.0)
        return [NOVO_ENSAIO]

    def _medida(self, medida, agora):
        status = self.state.status
        if status == TARANDO:
            return []  # a tara pedida ainda não começou no Arduino
        if status in (ERRO_SENSOR, INACTIVE):
            self.state.set_status(RUNNING if self.em_ensaio else IDLE)

        self.state.atualizar_carga(medida.carga_kg, medida.pico_kg)
        if not self.em_ensaio:
            # Fora de ensaio o gráfico segue a balança desde a última tara.
            if self.state.status == IDLE and self._inicio_tara is not None:
                self.state.registrar_ponto(agora - self._inicio_tara)
            return []

        self.state.registrar_ponto(agora - self._inicio)
        if self._colapsou(medida, agora):
            self._encerrar(BROKEN)
            return [COLAPSO]
        return []

    def _colapsou(self, medida, agora) -> bool:
        condicao = (
            medida.pico_kg >= self._peso_minimo - _EPSILON
            and medida.carga_kg <= medida.pico_kg * self._fracao + _EPSILON
        )
        if not condicao:
            self._colapso_desde = None
            return False
        if self._colapso_desde is None:
            self._colapso_desde = agora
        return agora - self._colapso_desde >= self._confirmacao_s

    def _encerrar(self, status):
        if self.em_ensaio:
            self.state.tempo = self.tempo_ensaio()
        self.em_ensaio = False
        self._inicio = None
        self._inicio_tara = None  # congela o gráfico até a próxima tara
        self._colapso_desde = None
        self.state.set_status(status)
