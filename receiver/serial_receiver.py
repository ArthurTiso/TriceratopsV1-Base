"""Comunicação com o Arduino do Módulo 1 pela USB serial.

Ao abrir a porta, o Arduino reinicia e faz a tara automática de inicialização:
a balança deve estar sem carga quando o Módulo 2 conectar.
"""

import time

from receiver.base_receiver import BaseReceiver

ESPERA_RECONEXAO_SEGUNDOS = 2.0


class SerialReceiver(BaseReceiver):
    def __init__(self, porta, baud=115200, timeout=0.2, abrir_serial=None, clock=time.monotonic):
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
        texto = linha.decode("utf-8", errors="ignore").strip()
        return texto or None

    def enviar_comando(self, comando: str):
        if self._serial is None:
            print(f"⚠️  Comando '{comando}' não enviado: Arduino desconectado")
            return False
        try:
            self._serial.write(comando.encode("ascii"))
            self._serial.flush()
            return True
        except Exception as e:
            print(f"⚠️  Erro ao enviar '{comando}' pela serial: {e}")
            self.cleanup()
            return False

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
            print(f"🔌 Arduino conectado em {self.porta} ({self.baud} baud)")
            return True
        except Exception as e:
            print(f"⚠️  Não foi possível abrir {self.porta}: {e}")
            self._serial = None
            return False

    @staticmethod
    def _abrir_pyserial(porta, baud, timeout):
        import serial  # pyserial; importado aqui para o simulador não depender dele

        return serial.Serial(porta, baud, timeout=timeout)
