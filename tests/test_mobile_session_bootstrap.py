"""Tests for the mobile login/session bootstrap shown in the WebView."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "mobile" / "static" / "index.html"


class TestMobileSessionBootstrap(unittest.TestCase):
    def test_first_open_without_token_shows_login_without_false_session_error(self):
        source = HTML.read_text(encoding="utf-8")
        self.assertIn("if(!S.tok){telaLogin();return}", source)
        self.assertNotIn("telaLogin('Não foi possível validar a sessão. Conecte-se ao servidor", source)

    def test_expired_session_and_connection_failure_have_distinct_messages(self):
        source = HTML.read_text(encoding="utf-8")
        self.assertIn("Sua sessão expirou. Entre novamente para continuar.", source)
        self.assertIn("Não foi possível conectar ao servidor.", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
