"""Testes de contrato para o launcher de distribuição e atualização do NutriLab."""
from pathlib import Path
import unittest

RAIZ = Path(__file__).resolve().parent.parent


class TestLauncherPortaDeEntrada(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.launcher = (RAIZ / "Gerar_e_Abrir_NutriLab.bat").read_text(encoding="utf-8")
        cls.atualizador = (
            (RAIZ / "Atualizar_NutriLab.bat").read_text(encoding="utf-8")
            if (RAIZ / "Atualizar_NutriLab.bat").exists()
            else ""
        )
        cls.ps_atualizador = (
            (RAIZ / "tools" / "atualizar_nutrilab.ps1").read_text(encoding="utf-8")
            if (RAIZ / "tools" / "atualizar_nutrilab.ps1").exists()
            else ""
        )

    def _texto(self):
        return (self.launcher + "\n" + self.atualizador + "\n" + self.ps_atualizador).lower()

    def test_instala_python_quando_ausente(self):
        launcher = self.launcher.lower()
        self.assertIn("python.org", launcher)
        self.assertRegex(launcher, r"python.*(installer|instalador|download)")
        self.assertTrue("python-3.12.10" in launcher or "python 3.12" in launcher or "3.12.10" in launcher)

    def test_reutiliza_python_existente_antes_de_baixar_instalador(self):
        launcher = self.launcher.lower()
        pos_verificacao = launcher.find("where python")
        pos_download = launcher.find("python.org")
        self.assertGreaterEqual(pos_verificacao, 0)
        self.assertGreaterEqual(pos_download, 0)
        self.assertLess(pos_verificacao, pos_download)

    def test_saida_padrao_tem_nome_simples(self):
        texto = self._texto()
        self.assertIn("executavel do programa", texto)
        self.assertNotIn('set "pasta_saida=dist"', texto)

    def test_atualizacao_consulta_github(self):
        texto = self._texto()
        self.assertIn("api.github.com", texto)
        self.assertIn("github.com", texto)
        self.assertTrue("git" in texto and ("rev-parse" in texto or "commit" in texto or "sha" in texto))

    def test_atualizacao_exige_confirmacao_antes_de_fechar_programa(self):
        texto = self._texto()
        self.assertRegex(texto, r"choice|set /p|messageboxw")
        self.assertRegex(texto, r"atualiza|update")
        self.assertRegex(texto, r"taskkill|stop-process")

    def test_atualizacao_preserva_banco_do_usuario(self):
        texto = self._texto()
        self.assertIn("clinica.db", texto)
        self.assertRegex(texto, r"preserv|backup|nao.*sobres|não.*sobres")

    def test_atualizacao_recompila_e_reabre(self):
        texto = self._texto()
        self.assertIn("pyinstaller", texto)
        self.assertRegex(texto, r"gerar_e_abrir_nutrilab\.bat|/apos-atualizacao|pyinstaller")
        self.assertRegex(texto, r"start(?:-process)? .*nutrilab|start.*executavel")

    def test_atualizacao_nao_executa_codigo_remoto_sem_validacao(self):
        texto = self._texto()
        self.assertNotIn("powershell -command iex", texto)
        self.assertNotIn("invoke-expression", texto)


if __name__ == "__main__":
    unittest.main()
