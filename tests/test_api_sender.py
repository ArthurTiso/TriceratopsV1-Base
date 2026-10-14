import threading
import unittest
from unittest import mock

import requests

from sender import api_sender
from sender.api_sender import ApiSender


class RespostaFalsa:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class SessaoFalsa:
    """Substitui requests.Session: devolve as respostas na ordem dada."""

    def __init__(self, respostas):
        self._respostas = list(respostas)
        self.chamadas = []
        self.lock = threading.Lock()

    def post(self, url, json, headers, timeout):
        with self.lock:
            self.chamadas.append({"url": url, "json": json, "headers": headers})
            resposta = self._respostas.pop(0) if self._respostas else RespostaFalsa(202)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


@mock.patch.object(api_sender, "ESPERA_ENTRE_TENTATIVAS", 0)
class ApiSenderTest(unittest.TestCase):
    def enviar(self, respostas, payloads=({"event": "sample"},), token="tok"):
        sessao = SessaoFalsa(respostas)
        sender = ApiSender("http://m3/api/v1/sensors/capture", token, session=sessao)
        with mock.patch("builtins.print"):
            for payload in payloads:
                sender.enviar(payload)
            sender.parar(timeout=5)
        return sessao.chamadas

    def test_sends_the_bearer_token_and_a_timestamp(self):
        chamadas = self.enviar([RespostaFalsa(202)])

        self.assertEqual(len(chamadas), 1)
        self.assertEqual(chamadas[0]["headers"]["Authorization"], "Bearer tok")
        self.assertIn("timestamp", chamadas[0]["json"])

    def test_permanent_errors_are_not_retried(self):
        for status in (401, 404, 422):
            with self.subTest(status=status):
                self.assertEqual(len(self.enviar([RespostaFalsa(status)])), 1)

    def test_network_errors_and_5xx_are_retried(self):
        chamadas = self.enviar([requests.ConnectionError("fora do ar"), RespostaFalsa(500), RespostaFalsa(202)])

        self.assertEqual(len(chamadas), 3)

    def test_rate_limit_is_retried(self):
        self.assertEqual(len(self.enviar([RespostaFalsa(429), RespostaFalsa(202)])), 2)

    def test_gives_up_after_max_attempts(self):
        chamadas = self.enviar([RespostaFalsa(503)] * 5)

        self.assertEqual(len(chamadas), api_sender.MAX_TENTATIVAS)

    def test_stop_flushes_the_queue_in_order(self):
        payloads = [{"event": "sample", "n": n} for n in range(5)] + [{"event": "completed"}]

        chamadas = self.enviar([], payloads=payloads)

        self.assertEqual([c["json"]["event"] for c in chamadas][-1], "completed")
        self.assertEqual(len(chamadas), 6)


if __name__ == "__main__":
    unittest.main()
