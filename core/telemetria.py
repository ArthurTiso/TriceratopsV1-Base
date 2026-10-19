"""Decide quais eventos devem ser enviados ao Módulo 3.

* ``started``   — uma vez, no início de cada ensaio;
* ``sample``    — no máximo um por intervalo (1 s por padrão, abaixo do
  limite de 120 req/min da API), e imediatamente quando a carga supera o
  maior valor já enviado;
* ``completed`` — uma única vez, no colapso ou no encerramento manual. Depois
  disso nada mais é enviado até o próximo ensaio: no Módulo 3, qualquer
  amostra após o ``completed`` voltaria a equipe para "running".
"""

import time

from core.ensaio import COLAPSO, FIM_MANUAL, INTERROMPIDO, NOVO_ENSAIO
from core.system_state import RUNNING

STARTED = "started"
SAMPLE = "sample"
COMPLETED = "completed"


class PoliticaEnvio:
    def __init__(self, intervalo_s=1.0, clock=time.monotonic):
        self._intervalo_s = intervalo_s
        self._clock = clock
        self._ultimo_envio = None
        self._maior_carga_enviada = None
        self._encerrado = True  # nada a enviar antes do primeiro ensaio

    def decidir(self, eventos, status, carga_kg) -> list:
        agora = self._clock()
        envios = []

        if NOVO_ENSAIO in eventos:
            self._encerrado = False
            self._maior_carga_enviada = None
            envios.append(STARTED)

        if self._encerrado:
            return envios

        if COLAPSO in eventos or FIM_MANUAL in eventos:
            self._encerrado = True
            envios.append(COMPLETED)
        elif INTERROMPIDO in eventos:
            self._encerrado = True
        elif not envios and status == RUNNING:
            novo_pico = (
                self._maior_carga_enviada is not None
                and carga_kg > self._maior_carga_enviada
            )
            intervalo_cumprido = (
                self._ultimo_envio is None
                or agora - self._ultimo_envio >= self._intervalo_s
            )
            if novo_pico or intervalo_cumprido:
                envios.append(SAMPLE)

        if envios:
            self._ultimo_envio = agora
            if self._maior_carga_enviada is None or carga_kg > self._maior_carga_enviada:
                self._maior_carga_enviada = carga_kg

        return envios
