"""Contrato de telemetria entre o Módulo 2 e o Módulo 3."""


def build_capture_payload(team_code: str, dados: dict, event: str = "sample") -> dict:
    """Converte a leitura do protocolo RF para o contrato HTTP do Módulo 3.

    O Módulo 2 trabalha e exibe carga em quilogramas. O Módulo 3 armazena a
    carga em gramas para preservar a unidade adotada no banco e no placar.
    """
    if not team_code:
        raise ValueError("SPINO_TEAM_CODE deve identificar a equipe em ensaio")

    return {
        "team_code": team_code,
        "elapsed_ms": int(dados["tempo"]) * 1000,
        "load_grams": round(float(dados["peso_atual"]) * 1000),
        "event": event,
    }
