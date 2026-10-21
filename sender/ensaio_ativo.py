"""Consulta periódica do ensaio armado para este M2 no Módulo 3."""

import threading
import time
from dataclasses import dataclass

import requests

INTERVALO_CONSULTA_S = 2.0  # a rota aceita 60 consultas por minuto
TIMEOUT_SEGUNDOS = 10  # rede do campus pode responder devagar


@dataclass(frozen=True)
class EnsaioArmado:
    run_id: str
    status: str        # "armed" ou "running"
    equipe_codigo: str
    equipe_nome: str


class ConsultaEnsaioAtivo:
    """Consulta o Módulo 3 numa thread e guarda a última resposta.

    ``atual()`` devolve:
    * ``EnsaioArmado`` — há um ensaio armado/em andamento para este M2;
    * ``False``        — o Módulo 3 respondeu que não há ensaio ativo;
    * ``None``         — ainda sem resposta ou falha de rede (estado desconhecido).
    """

    def __init__(self, url, token=None, intervalo_s=INTERVALO_CONSULTA_S, session=None, iniciar=True):
        self.url = url
        self.token = token
        self.intervalo_s = intervalo_s
        self._session = session or requests.Session()
        self._lock = threading.Lock()
        self._atual = None
        self._ultimo_aviso = None
        self._parar = threading.Event()
        if iniciar:
            threading.Thread(target=self._rodar, daemon=True).start()

    def atual(self):
        with self._lock:
            return self._atual

    def parar(self):
        self._parar.set()

    def consultar(self):
        """Faz uma consulta e atualiza o resultado (usado pela thread e pelos testes)."""
        resultado, aviso = self._consultar()
        with self._lock:
            self._atual = resultado
        if aviso != self._ultimo_aviso:
            if aviso:
                print(aviso)
            self._ultimo_aviso = aviso
        return resultado

    # ---- internos ----

    def _rodar(self):
        while not self._parar.is_set():
            self.consultar()
            self._parar.wait(self.intervalo_s)

    def _consultar(self):
        headers = {"Accept": "application/json"}
        if self.token:  # o Módulo 3 atual não exige token; enviado só se configurado
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            resposta = self._session.get(self.url, headers=headers, timeout=TIMEOUT_SEGUNDOS)
        except requests.RequestException as e:
            return None, f"⚠️  Módulo 3 inacessível ({e.__class__.__name__}) — tentando de novo"

        if resposta.status_code == 401:
            return None, "❌ Módulo 3 exigiu autenticação (401) — confira SPINO_MODULO3_TOKEN"
        if resposta.status_code == 404:
            return False, (
                "ℹ️  Este M2 ainda não foi usado no Módulo 3 — arme um ensaio para ele "
                "em Administração → Ensaios"
            )
        if resposta.status_code != 200:
            return None, f"⚠️  Módulo 3 respondeu {resposta.status_code} na consulta do ensaio"

        try:
            dados = resposta.json()
        except ValueError:
            return None, "⚠️  Resposta inválida do Módulo 3 na consulta do ensaio"

        if not dados.get("active"):
            return False, None
        equipe = dados.get("team") or {}
        return EnsaioArmado(
            run_id=dados["run_id"],
            status=dados.get("status", "armed"),
            equipe_codigo=equipe.get("code", ""),
            equipe_nome=equipe.get("name", ""),
        ), None
