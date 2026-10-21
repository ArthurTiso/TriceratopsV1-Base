import queue
import threading
import time
from datetime import datetime, timezone

import requests

MAX_TENTATIVAS = 3
TIMEOUT_SEGUNDOS = 3
ESPERA_ENTRE_TENTATIVAS = 1.0  # segundos
TAMANHO_MAXIMO_FILA = 200
TEMPO_MAXIMO_ENCERRAMENTO = 10.0  # segundos para esvaziar a fila ao parar

# Respostas que podem dar certo numa nova tentativa. Os demais erros 4xx
# (401 token, 404 equipe, 422 validação) não mudam ao repetir.
STATUS_TEMPORARIOS = {408, 429}

MENSAGENS_ERRO = {
    401: "token recusado — confira SPINO_MODULO3_TOKEN e SENSORS_API_TOKEN do Módulo 3",
    404: "equipe não encontrada — confira SPINO_TEAM_CODE",
    422: "dados recusados (equipe não aprovada para ensaio ou payload inválido)",
}

_FIM = object()  # sentinela para encerrar a thread


class ApiSender:
    """
    Envia leituras para o Módulo 3 em background, sem travar a leitura de
    pacotes do Arduino no loop principal.

    - Falhas de rede, 5xx, 408 e 429 são tentadas até MAX_TENTATIVAS vezes.
    - Outros erros 4xx são descartados na hora, com a causa no log.
    - Se a fila encher (Módulo 3 fora do ar por tempo demais), leituras
      novas são descartadas — a leitura ao vivo do Módulo 1 nunca espera
      pelo envio.
    - parar() envia o que ainda está na fila antes de encerrar, para não
      perder o evento "completed" ao fechar o programa logo após o colapso.
    """

    def __init__(self, url, token=None, session=None):
        self.url = url
        self.token = token
        self._session = session or requests.Session()
        self._fila = queue.Queue(maxsize=TAMANHO_MAXIMO_FILA)
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

    def parar(self, timeout=TEMPO_MAXIMO_ENCERRAMENTO):
        """Envia o que restou na fila (até `timeout` segundos) e encerra a thread."""
        try:
            self._fila.put(_FIM, timeout=timeout)
        except queue.Full:
            pass
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            print("⚠️  Encerrado com leituras ainda não enviadas ao Módulo 3")

    # ---- internos ----

    def _processar_fila(self):
        while True:
            payload = self._fila.get()
            if payload is _FIM:
                return
            self._enviar_com_retentativa(payload)

    def _enviar_com_retentativa(self, payload):
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        evento = payload.get("event", "sample")
        for tentativa in range(1, MAX_TENTATIVAS + 1):
            try:
                resposta = self._session.post(
                    self.url, json=payload, headers=headers, timeout=TIMEOUT_SEGUNDOS
                )
                if resposta.status_code < 300:
                    if evento != "sample":
                        print(f"📤 Módulo 3 confirmou '{evento}' ({resposta.status_code})")
                    return
                if resposta.status_code < 500 and resposta.status_code not in STATUS_TEMPORARIOS:
                    motivo = MENSAGENS_ERRO.get(resposta.status_code, resposta.text[:200])
                    print(f"❌ Módulo 3 recusou '{evento}' ({resposta.status_code}): {motivo}")
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

        print(f"❌ Desisti de enviar '{evento}' pro Módulo 3 após esgotar as tentativas")
