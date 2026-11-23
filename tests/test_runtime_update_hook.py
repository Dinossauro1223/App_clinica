"""Testes específicos do contrato do verificador de atualizações."""
from pathlib import Path
import unittest

RAIZ = Path(__file__).resolve().parent.parent


class TestRuntimeUpdateHook(unittest.TestCase):
    def setUp(self):
        self.hook = (RAIZ / "runtime_update_check.py").read_text(encoding="utf-8")
        self.spec = (RAIZ / "app_clinica.spec").read_text(encoding="utf-8")

    def test_hook_e_empacotado_e_roda_antes_da_aplicacao(self):
        self.assertIn("runtime_hooks=['runtime_update_check.py']", self.spec)
        self.assertIn("verificar_e_atualizar()", self.hook)

    def test_api_e_commit_sha_sao_consultados(self):
        self.assertIn("api.github.com", self.hook)
        self.assertIn("commits/main", self.hook)
        self.assertIn("remote_sha", self.hook)
        self.assertIn("local_sha", self.hook)

    def test_falha_de_rede_nao_bloqueia_programa(self):
        self.assertIn("except Exception:", self.hook)
        self.assertIn("return", self.hook)

    def test_atualizador_e_chamado_e_programa_atual_nao_continua(self):
        self.assertIn("Atualizar_NutriLab.bat", self.hook)
        self.assertIn("subprocess.Popen", self.hook)
        self.assertIn("os._exit(0)", self.hook)


if __name__ == "__main__":
    unittest.main()
