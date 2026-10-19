"""Linhas que o Módulo 1 (firmware/modulo1_balanca_usb) imprime na USB serial.

A cada 500 ms o Arduino envia uma destas linhas:

    AMOSTRA_KG=12.3 | MEDIA_KG=12.1 | PICO_ABS_KG=12.4 | BRUTO=-325112
    TARA=7/20 | BRUTO=8423311
    ERRO: HX711 sem dados ha pelo menos 2 s. Confira DT, SCK, alimentacao e GND.

e, nos eventos de tara:

    Tarando: deixe a balanca sem carga (20 amostras).
    Tara concluida. Offset=8423190

MEDIA_KG é a média móvel das últimas 10 leituras do HX711 (com sinal) e
PICO_ABS_KG a maior magnitude dessa média desde a última tara. Qualquer
outra linha (cabeçalho da inicialização) é ignorada.
"""

import re
from dataclasses import dataclass

COMANDO_TARA = "t"

_NUMERO = r"(-?\d+(?:\.\d+)?)"
_MEDIDA = re.compile(
    rf"AMOSTRA_KG={_NUMERO} \| MEDIA_KG={_NUMERO} \| PICO_ABS_KG={_NUMERO} \| BRUTO=(-?\d+)"
)
_TARA_PROGRESSO = re.compile(r"TARA=(\d+)/(\d+)")
_TARA_CONCLUIDA = re.compile(r"Tara concluida\. Offset=(-?\d+)")


@dataclass(frozen=True)
class Medida:
    amostra_kg: float
    media_kg: float
    pico_kg: float
    bruto: int

    @property
    def carga_kg(self) -> float:
        """Carga da média móvel, em magnitude (como o pico do Arduino)."""
        return abs(self.media_kg)


@dataclass(frozen=True)
class TaraIniciada:
    pass


@dataclass(frozen=True)
class TaraProgresso:
    contador: int
    total: int


@dataclass(frozen=True)
class TaraConcluida:
    offset: int


@dataclass(frozen=True)
class ErroSensor:
    mensagem: str


def interpretar_linha(linha: str):
    """Converte uma linha do Arduino em evento; devolve None para as demais."""
    linha = linha.strip()

    encontrado = _MEDIDA.search(linha)
    if encontrado:
        amostra, media, pico, bruto = encontrado.groups()
        return Medida(float(amostra), float(media), float(pico), int(bruto))

    encontrado = _TARA_PROGRESSO.search(linha)
    if encontrado:
        return TaraProgresso(int(encontrado.group(1)), int(encontrado.group(2)))

    encontrado = _TARA_CONCLUIDA.search(linha)
    if encontrado:
        return TaraConcluida(int(encontrado.group(1)))

    if linha.startswith("Tarando"):
        return TaraIniciada()

    if linha.startswith("ERRO"):
        return ErroSensor(linha)

    return None


def formatar_medida(amostra_kg, media_kg, pico_kg, bruto) -> str:
    """Mesma linha que mostrarNoPC() imprime (usado pelo simulador e testes)."""
    return (
        f"AMOSTRA_KG={amostra_kg:.1f} | MEDIA_KG={media_kg:.1f} | "
        f"PICO_ABS_KG={pico_kg:.1f} | BRUTO={int(bruto)}"
    )
