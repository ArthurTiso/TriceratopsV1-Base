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

RECEPTORES = ("simulador", "serial")
FIRMWARES_SIMULADOS = ("atual", "corrigido")


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
    firmware_simulado: str
    perda_rf_simulada: float


def carregar_config() -> Config:
    carregar_env()

    config = Config(
        team_code=os.getenv("SPINO_TEAM_CODE", "").strip(),
        modulo3_url=os.getenv("SPINO_MODULO3_URL", "http://localhost:8000/api/v1/sensors/capture"),
        modulo3_token=os.getenv("SPINO_MODULO3_TOKEN", ""),
        intervalo_envio_s=float(os.getenv("SPINO_SEND_INTERVAL_SECONDS", "1")),
        receptor=os.getenv("SPINO_RECEIVER", "simulador").strip().lower(),
        porta_serial=os.getenv("SPINO_SERIAL_PORT", "").strip(),
        baud_serial=int(os.getenv("SPINO_SERIAL_BAUD", "9600")),
        firmware_simulado=os.getenv("SPINO_SIM_FIRMWARE", "atual").strip().lower(),
        perda_rf_simulada=float(os.getenv("SPINO_SIM_PERDA_RF", "0")),
    )

    if not config.team_code:
        raise RuntimeError("Defina SPINO_TEAM_CODE antes de iniciar o Módulo 2")
    if len(config.team_code) > TAMANHO_MAXIMO_TEAM_CODE:
        raise RuntimeError(f"SPINO_TEAM_CODE tem mais de {TAMANHO_MAXIMO_TEAM_CODE} caracteres")
    if not config.modulo3_token:
        print("⚠️  SPINO_MODULO3_TOKEN vazio — o Módulo 3 vai recusar os envios (401)")
    if config.receptor not in RECEPTORES:
        raise RuntimeError(f"SPINO_RECEIVER deve ser um de {RECEPTORES}")
    if config.receptor == "serial" and not config.porta_serial:
        raise RuntimeError("Defina SPINO_SERIAL_PORT (ex.: COM3 no Windows, /dev/ttyACM0 no Pi)")
    if config.firmware_simulado not in FIRMWARES_SIMULADOS:
        raise RuntimeError(f"SPINO_SIM_FIRMWARE deve ser um de {FIRMWARES_SIMULADOS}")

    return config
