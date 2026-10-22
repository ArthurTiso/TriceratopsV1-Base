import unittest
from unittest import mock

import requests

from sender.ensaio_ativo import ConsultaEnsaioAtivo, EnsaioArmado

RUN_ID = "0b6f8a3e-7c1e-4a55-9d3a-2f6c1c9e8b10"


class RespostaFalsa:
    def __init__(self, status_code, corpo=None):
        self.status_code = status_code
        self._corpo = corpo

    def json(self):
        if self._corpo is None:
            raise ValueError("sem JSON")
        return self._corpo


class SessaoFalsa:
    def __init__(self, resposta):
        self.resposta = resposta
        self.headers = None

    def get(self, url, headers, timeout):
        self.headers = headers
        if isinstance(self.resposta, Exception):
            raise self.resposta
        return self.resposta


class ConsultaEnsaioAtivoTest(unittest.TestCase):
    def consultar(self, resposta):
        sessao = SessaoFalsa(resposta)
        consulta = ConsultaEnsaioAtivo("http://m3/active-run", "tok", session=sessao, iniciar=False)
        with mock.patch("builtins.print"):
            resultado = consulta.consultar()
        self.assertEqual(sessao.headers["Authorization"], "Bearer tok")
        self.assertEqual(consulta.atual(), resultado)
        return resultado

    def test_armed_run(self):
        resultado = self.consultar(RespostaFalsa(200, {
            "active": True, "run_id": RUN_ID, "status": "armed",
            "team": {"code": "EQ01", "name": "Ponte Forte"},
        }))

        self.assertEqual(resultado, EnsaioArmado(RUN_ID, "armed", "EQ01", "Ponte Forte"))

    def test_no_active_run(self):
        self.assertIs(self.consultar(RespostaFalsa(200, {"active": False})), False)

    def test_device_never_armed_is_the_same_as_no_run(self):
        self.assertIs(self.consultar(RespostaFalsa(404, {"message": "Dispositivo não cadastrado"})), False)

    def test_failures_are_unknown_not_inactive(self):
        for resposta in (
            requests.ConnectionError("sem rede"),
            RespostaFalsa(401, {"message": "Não autorizado."}),
            RespostaFalsa(500),
            RespostaFalsa(200),
        ):
            with self.subTest(resposta=resposta):
                self.assertIsNone(self.consultar(resposta))

    def test_without_token_no_authorization_header_is_sent(self):
        sessao = SessaoFalsa(RespostaFalsa(200, {"active": False}))
        consulta = ConsultaEnsaioAtivo("http://m3/active-run", session=sessao, iniciar=False)

        self.assertIs(consulta.consultar(), False)
        self.assertNotIn("Authorization", sessao.headers)

    def test_online_is_unknown_until_first_answer_or_timeout(self):
        relogio = [0.0]
        sessao = SessaoFalsa(requests.ConnectionError())
        consulta = ConsultaEnsaioAtivo("http://m3", session=sessao, iniciar=False, clock=lambda: relogio[0])
        with mock.patch("builtins.print"):
            consulta.consultar()
            self.assertIsNone(consulta.online())
            relogio[0] = 16
            self.assertIs(consulta.online(), False)
            sessao.resposta = RespostaFalsa(200, {"active": False})
            consulta.consultar()
        self.assertIs(consulta.online(), True)

    def test_repeated_warnings_are_printed_once(self):
        consulta = ConsultaEnsaioAtivo(
            "http://m3", "tok", session=SessaoFalsa(requests.ConnectionError()), iniciar=False
        )
        with mock.patch("builtins.print") as impressao:
            for _ in range(5):
                consulta.consultar()

        self.assertEqual(impressao.call_count, 1)


if __name__ == "__main__":
    unittest.main()
