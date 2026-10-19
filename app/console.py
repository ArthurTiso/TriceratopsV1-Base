"""Comandos do operador digitados no terminal do Módulo 2."""

import queue
import threading

AJUDA = """
Comandos (digite e tecle Enter):
  novo [EQUIPE]   tara a balança SEM CARGA e inicia o ensaio (ex.: novo MOCK002)
  fim             encerra o ensaio atual como concluído
  cancelar        descarta o ensaio atual sem registrar resultado
  tara            zera a balança fora de ensaio
  ajuda           mostra esta lista
  sair            encerra o Módulo 2 (ou Ctrl+C)
"""

ALIASES = {
    "n": "novo", "novo": "novo",
    "f": "fim", "fim": "fim",
    "c": "cancelar", "cancelar": "cancelar",
    "t": "tara", "tara": "tara",
    "?": "ajuda", "h": "ajuda", "ajuda": "ajuda",
    "s": "sair", "q": "sair", "sair": "sair",
}


def interpretar_comando(texto: str):
    """'novo mock002' -> ('novo', 'MOCK002'); comando desconhecido -> (None, texto)."""
    partes = texto.strip().split()
    if not partes:
        return None, None
    comando = ALIASES.get(partes[0].lower())
    argumento = partes[1].upper() if len(partes) > 1 else None
    return (comando, argumento) if comando else (None, texto.strip())


class Console:
    """Lê o teclado numa thread para não travar a leitura da balança."""

    def __init__(self):
        self._fila = queue.Queue()
        threading.Thread(target=self._ler, daemon=True).start()

    def proximo(self):
        try:
            return self._fila.get_nowait()
        except queue.Empty:
            return None

    def _ler(self):
        while True:
            try:
                linha = input()
            except (EOFError, KeyboardInterrupt):
                return
            self._fila.put(linha)
