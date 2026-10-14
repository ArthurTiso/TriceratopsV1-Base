"""Monta quadros SPINO exatamente como o Arduino transmissor (montarQuadro()).

Usado pelo simulador e pelos testes, para que ambos falem o mesmo protocolo
do hardware real.
"""

from protocol.decoder import (
    DELIMITADOR_FIM,
    DELIMITADOR_INICIO,
    ESCALA_CARGA,
    calcular_checksum,
)


def carga_para_campo(kg: float) -> int:
    """Equivalente a pesoParaCampo() do Arduino: kg -> inteiro x10, 0..9999."""
    valor = max(kg, 0.0) * ESCALA_CARGA
    valor = min(valor, 9999.0)
    return int(valor + 0.5)


def montar_quadro(
    carga_max_kg: float,
    carga_atual_kg: float,
    tempo_s: int,
    flag: int,
    bateria: int = 0,
    deflexao: int = 0,
) -> str:
    corpo = (
        f"{bateria:03d}"
        f"{carga_para_campo(carga_max_kg):04d}"
        f"{carga_para_campo(carga_atual_kg):04d}"
        f"{deflexao:03d}"
        f"{min(int(tempo_s), 9999):04d}"
        f"{flag:1d}"
    )
    return f"{DELIMITADOR_INICIO}{corpo}{calcular_checksum(corpo)}{DELIMITADOR_FIM}"
