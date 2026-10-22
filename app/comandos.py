"""Canal de comandos do painel (Streamlit) para o Módulo 2.

O painel grava cada comando como um arquivo em ``comandos/``; o Módulo 2 lê,
executa e apaga. Comandos antigos (de quando o Módulo 2 estava fechado) são
descartados para nunca dispararem uma tara inesperada.
"""

import json
import os
import time
import uuid
from pathlib import Path

VALIDADE_S = 30.0


def enviar_comando(texto: str, pasta) -> Path:
    """Usado pelo painel: grava o comando de forma atômica."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    nome = f"{time.time_ns()}-{uuid.uuid4().hex[:8]}"
    temporario = pasta / f"{nome}.tmp"
    temporario.write_text(json.dumps({"comando": texto, "criado": time.time()}), encoding="utf-8")
    destino = pasta / f"{nome}.json"
    os.replace(temporario, destino)
    return destino


class FilaComandos:
    """Usada pelo Módulo 2: entrega os comandos do painel em ordem."""

    def __init__(self, pasta, relogio=time.time):
        self.pasta = Path(pasta)
        self._relogio = relogio
        self.pasta.mkdir(parents=True, exist_ok=True)
        for antigo in self.pasta.glob("*"):  # nada do que ficou de antes vale
            antigo.unlink(missing_ok=True)

    def proximos(self) -> list:
        comandos = []
        for arquivo in sorted(self.pasta.glob("*.json")):
            try:
                dados = json.loads(arquivo.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue  # ainda sendo gravado: tenta no próximo ciclo
            try:
                arquivo.unlink()
            except OSError:
                continue
            if self._relogio() - float(dados.get("criado", 0)) <= VALIDADE_S:
                comandos.append(str(dados.get("comando", "")))
        return comandos
