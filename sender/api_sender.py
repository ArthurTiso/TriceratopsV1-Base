import threading
import queue
import time
from datetime import datetime, timezone

import requests

#

# 🔧 CONFIGURAÇÃO — preencher quando o endpoint real do Módulo 3 estiver pronto
MODULO3_URL = "http://localhost:8000/api/v1/sensors/capture"  # TODO: URL real
MODULO3_TOKEN = None  # TODO: token de autenticação, quando existir

MAX_TENTATIVAS = 3
TIMEOUT_SEGUNDOS = 3
ESPERA_ENTRE_TENTATIVAS = 1.0  # segundos
TAMANHO_MAXIMO_FILA = 200


class ApiSender:
    """
    Envia leituras para o Módulo 3 em background, sem travar a leitura de
    pacotes do Arduino no loop principal.

    - Cada leitura enfileirada passa por até MAX_TENTATIVAS antes de ser
      descartada (com uma pequena espera entre tentativas).
    - Se a fila encher (Módulo 3 fora do ar por tempo demais), leituras
      novas são descartadas silenciosamente — a leitura ao vivo do
      Módulo 1 nunca espera pelo envio.
    """

    def __init__(self, url=MODULO3_URL, token=MODULO3_TOKEN):
        self.url = url
        self.token = token
        self._fila = queue.Queue(maxsize=TAMANHO_MAXIMO_FILA)
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._processar_fila, daemon=True)
        self._thread.start()

    def enviar(self, dados: dict):
        """Enfileira uma leitura para envio. Nunca bloqueia o chamador."""
        payload = dict(dados)
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        try:
            self._fila.put_nowait(payload)
        except queue.Full:
            print("⚠️  Fila de envio ao Módulo 3 cheia — leitura descartada")

    def parar(self):
        """Sinaliza para a thread de envio parar e espera ela finalizar."""
        self._parar.set()
        self._thread.join(timeout=2)

    # ---- internos ----

    def _processar_fila(self):
        while not self._parar.is_set():
            try:
                payload = self._fila.get(timeout=0.5)
            except queue.Empty:
                continue

            self._enviar_com_retentativa(payload)

    def _enviar_com_retentativa(self, payload):
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        for tentativa in range(1, MAX_TENTATIVAS + 1):
            try:
                resposta = requests.post(
                    self.url, json=payload, headers=headers, timeout=TIMEOUT_SEGUNDOS
                )
                if resposta.status_code < 300:
                    return
                print(
                    f"⚠️  Módulo 3 respondeu {resposta.status_code} "
                    f"(tentativa {tentativa}/{MAX_TENTATIVAS})"
                )
            except requests.RequestException as e:
                print(
                    f"⚠️  Falha ao enviar pro Módulo 3 (tentativa {tentativa}/{MAX_TENTATIVAS}): {e}"
                )

            if tentativa < MAX_TENTATIVAS:
                time.sleep(ESPERA_ENTRE_TENTATIVAS)

        print("❌ Desisti de enviar essa leitura pro Módulo 3 após esgotar as tentativas")
