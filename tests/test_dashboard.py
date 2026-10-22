"""Carrega o painel de verdade (Streamlit AppTest) para pegar erros de import
e de renderização. Pulado se o Streamlit não estiver instalado."""

import unittest
from pathlib import Path

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover - ambiente sem as dependências do painel
    AppTest = None

PAINEL = Path(__file__).resolve().parent.parent / "dashboard" / "app.py"


@unittest.skipIf(AppTest is None, "streamlit não instalado")
class PainelTest(unittest.TestCase):
    def test_dashboard_renders_without_errors(self):
        app = AppTest.from_file(str(PAINEL), default_timeout=30).run()

        self.assertEqual(list(app.exception), [])


if __name__ == "__main__":
    unittest.main()
