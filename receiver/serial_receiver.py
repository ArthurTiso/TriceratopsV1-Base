"""Lê os quadros SPINO do Arduino receptor (RH_ASK -> USB serial).

O receptor imprime cada quadro válido em uma linha. Qualquer outra linha
(mensagem de inicialização, ruído) é ignorada.
"""

import re
import time

from receiver.base_receiver import BaseReceiver

PADRAO_QUADRO = re.compile(r"\*\*\*\d{21}###")
ESPERA_RECONEXAO_SEGUNDOS = 2.0


class SerialReceiver(BaseReceiver):
    def __init__(self, porta, baud=9600, timeout=0.2, abrir_serial=None, clock=time.monotonic):
        self.porta = porta
        self.baud = baud
        self.timeout = timeout
        self._abrir_serial = abrir_serial or self._abrir_pyserial
        self._clock = clock
        self._serial = None
        self._ultima_tentativa = None
        self._conectar()

    def receber(self):
        if self._serial is None and not self._conectar():
            return None

        try:
            linha = self._serial.readline()
        except Exception as e:  # serial.SerialException: cabo desconectado etc.
            print(f"⚠️  Erro na serial {self.porta}: {e} — tentando reconectar")
            self.cleanup()
            return None

        if not linha:
            return None
        encontrado = PADRAO_QUADRO.search(linha.decode("ascii", errors="ignore"))
        return encontrado.group(0) if encontrado else None

    def cleanup(self):
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None

    # ---- internos ----

    def _conectar(self) -> bool:
        agora = self._clock()
        if (
            self._ultima_tentativa is not None
            and agora - self._ultima_tentativa < ESPERA_RECONEXAO_SEGUNDOS
        ):
            return False
        self._ultima_tentativa = agora
        try:
            self._serial = self._abrir_serial(self.porta, self.baud, self.timeout)
            print(f"🔌 Receptor serial conectado em {self.porta} ({self.baud} baud)")
            return True
        except Exception as e:
            print(f"⚠️  Não foi possível abrir {self.porta}: {e}")
            self._serial = None
            return False

    @staticmethod
    def _abrir_pyserial(porta, baud, timeout):
        import serial  # pyserial; importado aqui para o simulador não depender dele

        return serial.Serial(porta, baud, timeout=timeout)
