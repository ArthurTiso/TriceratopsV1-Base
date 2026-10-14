"""Utilitários compartilhados pelos testes."""


class RelogioFalso:
    """Substitui time.monotonic para controlar o tempo nos testes."""

    def __init__(self, inicio=1000.0):
        self.agora = inicio

    def __call__(self):
        return self.agora

    def avancar(self, segundos):
        self.agora += segundos


def dados(peso_atual, peso_max, tempo, flag=1):
    """Quadro já decodificado, como o ProtocolDecoder devolve."""
    return {
        "bateria": 0,
        "peso_max": peso_max,
        "peso_atual": peso_atual,
        "angulo": 0,
        "tempo": tempo,
        "flag": flag,
    }
