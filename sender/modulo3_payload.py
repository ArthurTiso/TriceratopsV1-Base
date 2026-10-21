"""Contrato de telemetria entre o Módulo 2 e o Módulo 3.

A comissão arma cada ensaio no Módulo 3 (Administração → Ensaios), escolhendo
a equipe e o M2. O Módulo 2 descobre o ensaio armado em

    GET  {base}/api/v1/sensors/devices/{device_code}/active-run

e envia cada leitura vinculada a ele em

    POST {base}/api/v1/sensors/capture
"""

import time

EVENTOS_VALIDOS = ("sample", "started", "completed")


def url_base(url: str) -> str:
    """Aceita a raiz do site ou qualquer URL da API e devolve a raiz."""
    url = url.strip().rstrip("/")
    return url.split("/api/", 1)[0]


def url_ensaio_ativo(base: str, device_code: str) -> str:
    return f"{url_base(base)}/api/v1/sensors/devices/{device_code}/active-run"


def url_captura(base: str) -> str:
    return f"{url_base(base)}/api/v1/sensors/capture"


def base_sequencia(agora=None) -> int:
    """Primeira sequência de um ensaio local.

    O Módulo 3 recusa uma sequência repetida com outra leitura. Se o mesmo
    ensaio armado for retomado (Arduino reiniciado, Módulo 2 reaberto), a
    contagem precisa continuar acima da anterior: a base cresce 10 por
    segundo, mais rápido do que as ~2 leituras/s enviadas.
    """
    agora = time.time() if agora is None else agora
    return (int(agora) - 1_700_000_000) * 10


def build_capture_payload(
    test_run_id: str,
    device_code: str,
    sequence: int,
    elapsed_s: float,
    load_kg: float,
    event: str = "sample",
) -> dict:
    """Monta o corpo do POST /api/v1/sensors/capture.

    O Módulo 2 trabalha e exibe carga em quilogramas. O Módulo 3 armazena a
    carga em gramas para preservar a unidade adotada no banco e no placar.
    """
    if not test_run_id:
        raise ValueError("Nenhum ensaio armado no Módulo 3")
    if event not in EVENTOS_VALIDOS:
        raise ValueError(f"Evento desconhecido para o Módulo 3: {event}")

    return {
        "test_run_id": test_run_id,
        "device_code": device_code,
        "sequence": int(sequence),
        "elapsed_ms": max(0, round(float(elapsed_s) * 1000)),
        "load_grams": max(0, round(float(load_kg) * 1000)),
        "event": event,
    }
