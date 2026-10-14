"""Simula o Arduino transmissor do Módulo 1, com o mesmo comportamento do firmware:

* INICIO      — tela inicial, sem transmissão (operador ainda não tocou INICIAR);
* TARANDO     — 20 leituras do HX711 (~2 s), sem transmissão;
* MONITORANDO — carga média em janelas de 2 s, quadro a cada 500 ms,
                quadro imediato logo após a tara;
* COLAPSO     — carga <= 20% da máxima (com máxima >= 2 kg); quadro imediato e
                repetição do quadro final, com o tempo congelado, até o
                operador tocar em REINICIAR, que volta para INICIO.

Os quadros saem de protocol.encoder.montar_quadro, igual a montarQuadro().
"""

import random
import time

from protocol.encoder import montar_quadro
from receiver.base_receiver import BaseReceiver

INICIO = "INICIO"
TARANDO = "TARANDO"
MONITORANDO = "MONITORANDO"
COLAPSO = "COLAPSO"

# Mesmos valores do firmware do Módulo 1
INTERVALO_RF_S = 0.5
JANELA_PESO_S = 2.0
PESO_MINIMO_COLAPSO_KG = 2.0
FRACAO_COLAPSO = 0.20


class SimulatedReceiver(BaseReceiver):
    def __init__(
        self,
        firmware="atual",
        perda_rf=0.0,
        clock=time.monotonic,
        rng=None,
        pausa_inicio_s=3.0,
        duracao_tara_s=2.0,
        duracao_colapso_s=8.0,
    ):
        """
        firmware: "atual"     → flag 1 durante todo o ensaio (firmware de hoje);
                  "corrigido" → flag 0 durante o ensaio e 1 só no colapso.
        perda_rf: fração de quadros perdidos no rádio (0.0 a 1.0).
        """
        self.firmware = firmware
        self.perda_rf = perda_rf
        self._clock = clock
        self._rng = rng or random.Random()
        self.pausa_inicio_s = pausa_inicio_s
        self.duracao_tara_s = duracao_tara_s
        self.duracao_colapso_s = duracao_colapso_s

        self.estado = INICIO
        self._inicio_estado = self._clock()
        self._ultimo_quadro = None
        self._reiniciar_medicao()

    def receber(self):
        agora = self._clock()
        enviar_agora = self._avancar(agora)

        if self.estado not in (MONITORANDO, COLAPSO):
            return None
        if not enviar_agora and agora - self._ultimo_quadro < INTERVALO_RF_S:
            return None

        self._ultimo_quadro = agora
        if self._rng.random() < self.perda_rf:
            return None
        return self.quadro_atual(agora)

    def quadro_atual(self, agora=None):
        agora = self._clock() if agora is None else agora
        if self.estado == MONITORANDO:
            tempo = int(agora - self._inicio_ensaio)
        else:
            tempo = int(self._tempo_colapso)

        if self.firmware == "corrigido":
            flag = 1 if self.estado == COLAPSO else 0
        else:
            flag = 1 if self.estado in (MONITORANDO, COLAPSO) else 0

        return montar_quadro(self.peso_max, self.peso_atual, tempo, flag)

    # ---- máquina de estados ----

    def _avancar(self, agora) -> bool:
        """Avança os estados; devolve True quando o firmware enviaria um quadro imediato."""
        if self.estado == INICIO and agora - self._inicio_estado >= self.pausa_inicio_s:
            self._mudar_estado(TARANDO, agora)

        if self.estado == TARANDO and agora - self._inicio_estado >= self.duracao_tara_s:
            self._mudar_estado(MONITORANDO, agora)
            self._reiniciar_medicao()
            self._inicio_ensaio = agora
            self._inicio_janela = agora
            return True  # processarTara() envia imediatamente

        if self.estado == MONITORANDO:
            while agora - self._inicio_janela >= JANELA_PESO_S:
                self._inicio_janela += JANELA_PESO_S
                self._fechar_janela()
                if self._entrou_em_colapso():
                    self._tempo_colapso = self._inicio_janela - self._inicio_ensaio
                    self._mudar_estado(COLAPSO, agora)
                    return True  # entrarEmColapso() envia imediatamente

        if self.estado == COLAPSO and agora - self._inicio_estado >= self.duracao_colapso_s:
            self._mudar_estado(INICIO, agora)  # operador tocou em REINICIAR

        return False

    def _mudar_estado(self, estado, agora):
        self.estado = estado
        self._inicio_estado = agora

    def _reiniciar_medicao(self):
        self.peso_atual = 0.0
        self.peso_max = 0.0
        self._inicio_ensaio = None
        self._inicio_janela = None
        self._tempo_colapso = 0.0
        self._janelas = 0
        self._rompendo = False
        self._rompeu = False

    def _fechar_janela(self):
        """Gera a média da janela de 2 s, como processarJanelaPeso()."""
        self._janelas += 1
        if self._rompeu:
            media = self.peso_max * self._rng.uniform(0.0, 0.1)
        elif self._rompendo:
            # A ponte rompe no meio da janela: a média mistura antes e depois.
            self._rompeu = True
            media = self.peso_atual * self._rng.uniform(0.15, 0.6)
        else:
            media = self.peso_atual + self._rng.uniform(0.2, 1.5)
            chance_ruptura = min(0.03 + 0.01 * self._janelas, 0.3)
            if self.peso_max >= PESO_MINIMO_COLAPSO_KG and self._rng.random() < chance_ruptura:
                self._rompendo = True

        self.peso_atual = round(max(media, 0.0), 2)
        self.peso_max = max(self.peso_max, self.peso_atual)

    def _entrou_em_colapso(self):
        return (
            self.peso_max >= PESO_MINIMO_COLAPSO_KG
            and self.peso_atual <= self.peso_max * FRACAO_COLAPSO
        )
