"""Utilitários compartilhados pelos testes."""

from protocol.balanca import Medida


class RelogioFalso:
    """Substitui time.monotonic para controlar o tempo nos testes."""

    def __init__(self, inicio=1000.0):
        self.agora = inicio

    def __call__(self):
        return self.agora

    def avancar(self, segundos):
        self.agora += segundos


def medida(media_kg, pico_kg=None):
    """Linha de medida já interpretada, como o Arduino envia a cada 0,5 s."""
    pico = abs(media_kg) if pico_kg is None else pico_kg
    return Medida(amostra_kg=media_kg, media_kg=media_kg, pico_kg=pico, bruto=0)
