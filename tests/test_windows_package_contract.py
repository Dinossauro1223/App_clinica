from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.verificar_pacote_windows import verificar_pacote


ROOT = Path(__file__).resolve().parents[1]


class TestWindowsPackageContract(unittest.TestCase):
    def criar_zip(self, caminho, nomes):
        with zipfile.ZipFile(caminho, "w") as arquivo:
            for nome, dados in nomes:
                arquivo.writestr(nome, dados)

    def test_aceita_somente_modelo_interno_e_html_canonico(self):
        with tempfile.TemporaryDirectory() as pasta:
            pacote = Path(pasta) / "bom.zip"
            self.criar_zip(pacote, [
                ("NutriLab.exe", b"exe"),
                ("_internal/clinica.db", b"modelo"),
                ("_internal/mobile/static/index.html", b"html"),
            ])
            verificar_pacote(pacote)

    def test_rejeita_banco_gravavel_na_raiz(self):
        with tempfile.TemporaryDirectory() as pasta:
            pacote = Path(pasta) / "banco-duplicado.zip"
            self.criar_zip(pacote, [
                ("_internal/clinica.db", b"modelo"),
                ("clinica.db", b"banco do usuario"),
                ("_internal/mobile/static/index.html", b"html"),
            ])
            with self.assertRaisesRegex(ValueError, "somente o modelo"):
                verificar_pacote(pacote)

    def test_rejeita_mais_de_uma_fonte_html(self):
        with tempfile.TemporaryDirectory() as pasta:
            pacote = Path(pasta) / "html-duplicado.zip"
            self.criar_zip(pacote, [
                ("_internal/clinica.db", b"modelo"),
                ("_internal/mobile/static/index.html", b"html"),
                ("_internal/mobile/apk/app/assets/index.html", b"copia"),
            ])
            with self.assertRaisesRegex(ValueError, "uma única fonte HTML"):
                verificar_pacote(pacote)

    def test_workflow_limpa_o_banco_antes_de_compactar_e_valida_o_zip(self):
        workflow = (ROOT / ".github" / "workflows" / "build-windows.yml").read_text(encoding="utf-8")
        self.assertIn("Remover banco gravável criado pelo smoke test", workflow)
        self.assertIn("$bancoUsuario-wal", workflow)
        self.assertIn("$bancoUsuario-shm", workflow)
        self.assertIn("tools/verificar_pacote_windows.py", workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
