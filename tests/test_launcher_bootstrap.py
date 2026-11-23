"""Testes específicos do contrato de bootstrap do launcher."""
from pathlib import Path
import unittest

RAIZ = Path(__file__).resolve().parent.parent


class TestLauncherBootstrap(unittest.TestCase):
    def setUp(self):
        self.launcher = (RAIZ / "Gerar_e_Abrir_NutriLab.bat").read_text(encoding="utf-8")

    def test_fluxo_python_existente_precede_download(self):
        texto = self.launcher.lower()
        self.assertLess(texto.index("where py"), texto.index("python.org"))
        self.assertIn("py -3.12", texto)
        self.assertIn("python -c", texto)

    def test_instalador_python_tem_hash_fixado(self):
        texto = self.launcher
        self.assertIn("PYTHON_VERSION=3.12.10", texto)\n        self.assertIn("python-%PYTHON_VERSION%-amd64.exe", texto)
        self.assertIn("PYTHON_SHA256=", texto)
        self.assertIn("Get-FileHash", texto)

    def test_saida_e_exatamente_a_pasta_solicitada(self):
        self.assertIn('set "SAIDA=%~dp0Executavel do programa"', self.launcher)
        self.assertIn('move /Y "dist\\NutriLab" "%SAIDA%"', self.launcher)


if __name__ == "__main__":
    unittest.main()
