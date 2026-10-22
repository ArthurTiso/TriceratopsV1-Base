import csv
import tempfile
import unittest
from pathlib import Path

from app.comandos import FilaComandos, enviar_comando
from core.resultados import RegistroResultados, novo_resultado


class FilaComandosTest(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())

    def test_commands_are_delivered_in_order_and_removed(self):
        fila = FilaComandos(self.pasta)
        enviar_comando("novo", self.pasta)
        enviar_comando("fim", self.pasta)

        self.assertEqual(fila.proximos(), ["novo", "fim"])
        self.assertEqual(fila.proximos(), [])
        self.assertEqual(list(self.pasta.glob("*")), [])

    def test_leftovers_from_before_startup_are_discarded(self):
        enviar_comando("tara", self.pasta)

        self.assertEqual(FilaComandos(self.pasta).proximos(), [])

    def test_old_commands_are_ignored(self):
        agora = [1000.0]
        fila = FilaComandos(self.pasta, relogio=lambda: agora[0])
        enviar_comando("novo", self.pasta)
        agora[0] = 10**12  # muito depois

        self.assertEqual(fila.proximos(), [])


class RegistroResultadosTest(unittest.TestCase):
    def test_writes_an_excel_friendly_csv(self):
        caminho = Path(tempfile.mkdtemp()) / "resultados.csv"
        registro = RegistroResultados(caminho)
        for carga in (16.24, 9.0):
            registro.gravar(novo_resultado("EQ01", "Ponte Forte", carga, 27.5, "ruptura detectada",
                                           "Módulo 3", "uuid-1", "confirmado"))

        with open(caminho, encoding="utf-8-sig", newline="") as f:
            linhas = list(csv.DictReader(f, delimiter=";"))
        self.assertEqual(len(linhas), 2)
        self.assertEqual(linhas[0]["carga_ruptura_kg"], "16,2")
        self.assertEqual(linhas[0]["duracao_s"], "27,5")
        self.assertEqual(linhas[1]["registro_modulo3"], "confirmado")


if __name__ == "__main__":
    unittest.main()
