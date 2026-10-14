"""Protocolo SPINO entre o Módulo 1 (Arduino transmissor) e o Módulo 2.

Quadro de 27 caracteres, idêntico ao montado por montarQuadro() no Arduino:

    *** BAT CM   CA   DEF TEM  F CHK ###
        3   4    4    3   4    1 2

BAT = bateria (%)            - ainda fixo em 0 no Módulo 1
CM  = carga máxima em kg x10 (0123 = 12,3 kg)
CA  = carga atual  em kg x10
DEF = deflexão               - ainda fixo em 0 no Módulo 1
TEM = segundos desde o início do ensaio (congela no colapso)
F   = flag do ensaio
CHK = soma dos 3 últimos dígitos do corpo, módulo 100
"""

DELIMITADOR_INICIO = "***"
DELIMITADOR_FIM = "###"
TAMANHO_CORPO = 3 + 4 + 4 + 3 + 4 + 1  # 19
TAMANHO_CONTEUDO = TAMANHO_CORPO + 2   # 21 (corpo + checksum)

# O Arduino envia as cargas multiplicadas por 10 (resolução de 0,1 kg).
ESCALA_CARGA = 10


def calcular_checksum(corpo: str) -> str:
    """Soma dos 3 últimos dígitos do corpo, módulo 100 (mesma regra do Arduino)."""
    soma = sum(int(c) for c in corpo[-3:] if c.isdigit())
    return f"{soma % 100:02d}"


class ProtocolDecoder:

    def decodificar(self, pacote: str) -> dict:
        # 1. Validar delimitadores
        if not pacote.startswith(DELIMITADOR_INICIO) or not pacote.endswith(DELIMITADOR_FIM):
            raise ValueError("Pacote inválido: delimitadores incorretos")

        # 2. Remover delimitadores
        conteudo = pacote[len(DELIMITADOR_INICIO):-len(DELIMITADOR_FIM)]

        # 3. Validar tamanho e caracteres
        if len(conteudo) != TAMANHO_CONTEUDO:
            raise ValueError("Pacote inválido: tamanho incorreto")
        if not conteudo.isdigit():
            raise ValueError("Pacote inválido: caracteres não numéricos")

        # 4. Validar checksum
        corpo = conteudo[:TAMANHO_CORPO]
        checksum_recebido = conteudo[TAMANHO_CORPO:]
        checksum_calculado = calcular_checksum(corpo)
        if checksum_calculado != checksum_recebido:
            raise ValueError(
                f"Checksum inválido: esperado {checksum_calculado}, recebido {checksum_recebido}"
            )

        flag = int(corpo[18:19])
        if flag not in (0, 1):
            raise ValueError(f"Pacote inválido: flag {flag} fora do protocolo")

        # 5. Separar partes e converter para unidades físicas
        return {
            "bateria": int(corpo[0:3]),
            "peso_max": int(corpo[3:7]) / ESCALA_CARGA,    # kg
            "peso_atual": int(corpo[7:11]) / ESCALA_CARGA,  # kg
            "angulo": int(corpo[11:14]),
            "tempo": int(corpo[14:18]),                     # s
            "flag": flag,
        }
