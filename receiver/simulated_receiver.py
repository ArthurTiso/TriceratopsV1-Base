"""Simula o Arduino do Módulo 1 (firmware/modulo1_balanca_usb) na USB serial.

Reproduz o mesmo comportamento do firmware:

* ao "conectar", imprime o cabeçalho e faz a tara de inicialização;
* HX711 a 10 leituras/s; tara com 20 leituras (~2 s);
* MEDIA_KG = média móvel das últimas 10 leituras; PICO_ABS_KG = maior
  magnitude da média desde a tara;
* uma linha a cada 500 ms;
* comando "t" refaz a tara e zera média e pico.

Para simular um ensaio, cada tara pedida pelo operador inicia um carregamento:
a carga sobe até um ponto de ruptura aleatório e então cai para perto de zero.
"""

import random
import time
from collections import deque

from protocol.balanca import COMANDO_TARA, formatar_medida
from receiver.base_receiver import BaseReceiver

TAXA_HX711_HZ = 10
INTERVALO_SERIAL_S = 0.5
TOTAL_AMOSTRAS_TARA = 20
TAMANHO_MEDIA = 10
ESCALA = -26422.05
OFFSET = 8423190

CABECALHO = (
    "SPINO - balanca no PC via USB",
    "HX711: DT=46 | SCK=47 | Monitor Serial=115200 baud",
    "Escala de calibracao: -26422.05",
    "MEDIA_KG: media movel das ultimas 10 amostras, mantendo o sinal.",
    "PICO_ABS_KG: maior magnitude da media desde a tara.",
    "Comando: t + Enviar, sem carga, para tarar e zerar o pico.",
)


class SimulatedReceiver(BaseReceiver):
    def __init__(self, clock=time.monotonic, rng=None, espera_carga_s=3.0, ruido_kg=0.03):
        self._clock = clock
        self._rng = rng or random.Random()
        self.espera_carga_s = espera_carga_s
        self.ruido_kg = ruido_kg

        self._fila = deque(CABECALHO)
        self._ultima_leitura = self._clock()
        self._ultima_linha = self._clock()
        self._carregamento = None
        self._iniciar_tara(com_carregamento=False)

    conectado = True

    def receber(self):
        agora = self._clock()
        while agora - self._ultima_leitura >= 1 / TAXA_HX711_HZ:
            self._ultima_leitura += 1 / TAXA_HX711_HZ
            self._ler_hx711(self._ultima_leitura)

        if not self._fila and agora - self._ultima_linha >= INTERVALO_SERIAL_S:
            self._ultima_linha = agora
            self._fila.append(self._linha_periodica())

        return self._fila.popleft() if self._fila else None

    def enviar_comando(self, comando: str):
        if comando.lower() == COMANDO_TARA:
            self._iniciar_tara(com_carregamento=True)
        return True

    # ---- firmware simulado ----

    def _iniciar_tara(self, com_carregamento):
        self.tarando = True
        self._contador_tara = 0
        self._com_carregamento = com_carregamento
        self._carregamento = None
        self.amostra_kg = 0.0
        self.pico_kg = 0.0
        self._amostras = deque(maxlen=TAMANHO_MEDIA)
        self._fila.append("Tarando: deixe a balanca sem carga (20 amostras).")

    def _ler_hx711(self, instante):
        if self.tarando:
            self._contador_tara += 1
            if self._contador_tara >= TOTAL_AMOSTRAS_TARA:
                self.tarando = False
                self._fila.append(f"Tara concluida. Offset={OFFSET}")
                if self._com_carregamento:
                    self._carregamento = Carregamento(instante + self.espera_carga_s, self._rng)
            return

        carga = self._carregamento.carga(instante) if self._carregamento else 0.0
        self.amostra_kg = carga + self._rng.gauss(0, self.ruido_kg)
        self._amostras.append(self.amostra_kg)
        self.pico_kg = max(self.pico_kg, abs(self.media_kg))

    @property
    def media_kg(self):
        return sum(self._amostras) / len(self._amostras) if self._amostras else 0.0

    @property
    def rompeu(self):
        return self._carregamento is not None and self._carregamento.rompeu

    def _linha_periodica(self):
        if self.tarando:
            return f"TARA={self._contador_tara}/{TOTAL_AMOSTRAS_TARA} | BRUTO={OFFSET}"
        bruto = OFFSET + self.amostra_kg * ESCALA
        return formatar_medida(self.amostra_kg, self.media_kg, self.pico_kg, bruto)


class Carregamento:
    """Carga aplicada à ponte: sobe em rampa e despenca na ruptura."""

    def __init__(self, inicio, rng):
        self.inicio = inicio
        self.taxa_kg_s = rng.uniform(0.4, 1.2)
        self.carga_ruptura_kg = rng.uniform(4.0, 20.0)
        self.residual_kg = rng.uniform(0.0, 0.3)
        self.rompeu = False

    def carga(self, instante):
        if instante < self.inicio:
            return 0.0
        carga = (instante - self.inicio) * self.taxa_kg_s
        if carga >= self.carga_ruptura_kg:
            self.rompeu = True
        return self.residual_kg if self.rompeu else carga
