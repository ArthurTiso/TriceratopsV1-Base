"""Contrato de telemetria entre o Módulo 2 e o Módulo 3."""

EVENTOS_VALIDOS = ("sample", "started", "completed")
TAMANHO_MAXIMO_TEAM_CODE = 12  # coluna teams.code no Módulo 3


def build_capture_payload(team_code: str, dados: dict, event: str = "sample") -> dict:
    """Converte a leitura decodificada para o contrato HTTP do Módulo 3.

    O Módulo 2 trabalha e exibe carga em quilogramas. O Módulo 3 armazena a
    carga em gramas para preservar a unidade adotada no banco e no placar.
    """
    if not team_code:
        raise ValueError("SPINO_TEAM_CODE deve identificar a equipe em ensaio")
    if event not in EVENTOS_VALIDOS:
        raise ValueError(f"Evento desconhecido para o Módulo 3: {event}")

    return {
        "team_code": team_code,
        "elapsed_ms": int(dados["tempo"]) * 1000,
        "load_grams": max(0, round(float(dados["peso_atual"]) * 1000)),
        "event": event,
    }
