"""Contrato de telemetria entre o Módulo 2 e o Módulo 3."""

EVENTOS_VALIDOS = ("sample", "started", "completed")
TAMANHO_MAXIMO_TEAM_CODE = 12  # coluna teams.code no Módulo 3


def build_capture_payload(team_code: str, elapsed_s: float, load_kg: float, event: str = "sample") -> dict:
    """Monta o corpo do POST /api/v1/sensors/capture.

    O Módulo 2 trabalha e exibe carga em quilogramas. O Módulo 3 armazena a
    carga em gramas para preservar a unidade adotada no banco e no placar.
    """
    if not team_code:
        raise ValueError("Informe o código da equipe em ensaio")
    if event not in EVENTOS_VALIDOS:
        raise ValueError(f"Evento desconhecido para o Módulo 3: {event}")

    return {
        "team_code": team_code,
        "elapsed_ms": max(0, round(float(elapsed_s) * 1000)),
        "load_grams": max(0, round(float(load_kg) * 1000)),
        "event": event,
    }
