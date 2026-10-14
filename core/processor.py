"""Ciclo de vida do ensaio a partir dos quadros do Módulo 1.

O Arduino transmite a cada 500 ms enquanto está em MONITORANDO ou COLAPSO e
fica em silêncio na tela inicial e durante a tara. Cada quadro traz a média
de uma janela de 2 s, a carga máxima e o tempo de ensaio, que congela no
colapso.

Detecção de colapso (qualquer uma basta):

* Flag: firmware corrigido envia flag 0 durante o ensaio e 1 no colapso.
  Só é considerada depois de ver uma flag 0 no mesmo ensaio; o firmware
  antigo envia sempre 1 e cai automaticamente na regra combinada.
* Regra combinada A + B:
    A) carga atual <= 20% da máxima, com máxima >= 2 kg (mesma regra do
       Arduino);
    B) o tempo do ensaio parou de avançar por >= 2 s enquanto os quadros
       continuam chegando (durante o ensaio ele avança a cada 1 s).

Novo ensaio:

* primeiro quadro recebido (exceto se já chegar em colapso);
* após um colapso, um quadro com tempo diferente do tempo congelado
  (o operador tocou em REINICIAR e fez nova tara);
* durante um ensaio, o tempo voltar (Arduino reiniciado).
"""

import time

from core.system_state import BROKEN, IDLE, INACTIVE, RUNNING

NOVO_ENSAIO = "novo_ensaio"
COLAPSO = "colapso"

# Mesmos valores de PESO_MINIMO_COLAPSO e FRACAO_COLAPSO no Arduino.
PESO_MINIMO_COLAPSO_KG = 2.0
FRACAO_COLAPSO = 0.20

TEMPO_CONGELADO_SEGUNDOS = 2.0
INATIVIDADE_SEGUNDOS = 10.0

_EPSILON = 1e-9


class Processor:
    def __init__(
        self,
        state,
        clock=time.monotonic,
        tempo_congelado_s=TEMPO_CONGELADO_SEGUNDOS,
        inatividade_s=INATIVIDADE_SEGUNDOS,
    ):
        self.state = state
        self._clock = clock
        self._tempo_congelado_s = tempo_congelado_s
        self._inatividade_s = inatividade_s

        self._ultimo_quadro = None          # instante (monotonic) do último quadro
        self._ultimo_tempo = None           # campo "tempo" do último quadro
        self._instante_mudanca_tempo = None  # quando o campo "tempo" mudou
        self._viu_flag_zero = False
        self._tempo_colapso = None

    def processar(self, dados: dict) -> list:
        """Atualiza o estado com um quadro decodificado e devolve os eventos."""
        agora = self._clock()
        eventos = []
        tempo = dados["tempo"]

        if self._eh_novo_ensaio(dados):
            if self.state.status in (RUNNING, INACTIVE):
                print("⚠️  Tempo do ensaio voltou sem colapso — Arduino reiniciado? Iniciando novo ensaio.")
            self._iniciar_ensaio(agora)
            eventos.append(NOVO_ENSAIO)
        elif self.state.status == IDLE:
            # Módulo 2 ligado com o Arduino já em colapso: aguarda o próximo ensaio
            self.state.set_status(BROKEN)
            self._tempo_colapso = tempo

        if self.state.status == INACTIVE:
            self.state.set_status(RUNNING)

        if tempo != self._ultimo_tempo:
            self._instante_mudanca_tempo = agora
        self._ultimo_tempo = tempo
        self._ultimo_quadro = agora

        self.state.atualizar(dados)

        if self.state.status == RUNNING:
            if dados["flag"] == 0:
                self._viu_flag_zero = True
            if self._colapsou(dados, agora):
                self.state.set_status(BROKEN)
                self._tempo_colapso = tempo
                eventos.append(COLAPSO)

        return eventos

    def verificar_inatividade(self) -> bool:
        """Marca INACTIVE se o ensaio parou de receber quadros. Devolve True se mudou."""
        if self.state.status != RUNNING or self._ultimo_quadro is None:
            return False
        if self._clock() - self._ultimo_quadro >= self._inatividade_s:
            self.state.set_status(INACTIVE)
            return True
        return False

    # ---- internos ----

    def _eh_novo_ensaio(self, dados) -> bool:
        status = self.state.status
        tempo = dados["tempo"]
        if status == IDLE:
            return not self._aparenta_colapso(dados)
        if status == BROKEN:
            return tempo != self._tempo_colapso
        return self._ultimo_tempo is not None and tempo < self._ultimo_tempo

    def _iniciar_ensaio(self, agora):
        self.state.reset()
        self.state.set_status(RUNNING)
        self._viu_flag_zero = False
        self._tempo_colapso = None
        self._ultimo_tempo = None
        self._instante_mudanca_tempo = agora

    def _colapsou(self, dados, agora) -> bool:
        if dados["flag"] == 1 and self._viu_flag_zero:
            return True
        tempo_parado = agora - self._instante_mudanca_tempo >= self._tempo_congelado_s
        return tempo_parado and self._aparenta_colapso(dados)

    @staticmethod
    def _aparenta_colapso(dados) -> bool:
        """Regra A: a mesma condição que o Arduino usa para entrar em COLAPSO."""
        peso_max = dados["peso_max"]
        return (
            peso_max >= PESO_MINIMO_COLAPSO_KG - _EPSILON
            and dados["peso_atual"] <= peso_max * FRACAO_COLAPSO + _EPSILON
        )
