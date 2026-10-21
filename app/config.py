"""Configuração do Módulo 2, lida de variáveis de ambiente.

Um arquivo `.env` na raiz do projeto é carregado automaticamente (veja
`.env.example`). Variáveis já definidas no terminal têm prioridade sobre ele.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from sender.modulo3_payload import TAMANHO_MAXIMO_TEAM_CODE

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
ARQUIVO_ENV = RAIZ_PROJETO / ".env"
ARQUIVO_ESTADO = RAIZ_PROJETO / "data.json"

RECEPTORES = ("serial", "simulador")


def carregar_env(caminho=ARQUIVO_ENV):
    """Carrega CHAVE=valor de um arquivo .env sem sobrescrever o ambiente."""
    caminho = Path(caminho)
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Config:
    team_code: str
    modulo3_url: str
    modulo3_token: str
    intervalo_envio_s: float
    receptor: str
    porta_serial: str
    baud_serial: int
    peso_minimo_colapso_kg: float
    fracao_colapso: float
    confirmacao_colapso_s: float


def carregar_config() -> Config:
    carregar_env()

    config = Config(
        team_code=os.getenv("SPINO_TEAM_CODE", "").strip().upper(),
        modulo3_url=os.getenv("SPINO_MODULO3_URL", "http://127.0.0.1:8000/api/v1/sensors/capture"),
        modulo3_token=os.getenv("SPINO_MODULO3_TOKEN", ""),
        intervalo_envio_s=float(os.getenv("SPINO_SEND_INTERVAL_SECONDS", "1")),
        receptor=os.getenv("SPINO_RECEIVER", "serial").strip().lower(),
        porta_serial=os.getenv("SPINO_SERIAL_PORT", "").strip(),
        baud_serial=int(os.getenv("SPINO_SERIAL_BAUD", "115200")),
        peso_minimo_colapso_kg=float(os.getenv("SPINO_COLAPSO_PESO_MINIMO_KG", "2.0")),
        fracao_colapso=float(os.getenv("SPINO_COLAPSO_FRACAO", "0.20")),
        confirmacao_colapso_s=float(os.getenv("SPINO_COLAPSO_CONFIRMACAO_S", "1.0")),
    )

    if len(config.team_code) > TAMANHO_MAXIMO_TEAM_CODE:
        raise RuntimeError(f"SPINO_TEAM_CODE tem mais de {TAMANHO_MAXIMO_TEAM_CODE} caracteres")
    if not config.modulo3_token:
        print("⚠️  SPINO_MODULO3_TOKEN vazio — o Módulo 3 vai recusar os envios (401)")
    if config.receptor not in RECEPTORES:
        raise RuntimeError(f"SPINO_RECEIVER deve ser um de {RECEPTORES}")
    if config.receptor == "serial" and not config.porta_serial:
        raise RuntimeError("Defina SPINO_SERIAL_PORT com a porta do Arduino (ex.: COM3)")
    if not 0 < config.fracao_colapso < 1:
        raise RuntimeError("SPINO_COLAPSO_FRACAO deve estar entre 0 e 1")

    return config
