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
        self.assertIn("PYTHON_VERSION=3.12.10", texto)
        self.assertIn("python-%PYTHON_VERSION%-amd64.exe", texto)
        self.assertIn("PYTHON_SHA256=", texto)
        self.assertIn("Get-FileHash", texto)

    def test_saida_e_exatamente_a_pasta_solicitada(self):
        self.assertIn('set "SAIDA=%~dp0Executavel do programa"', self.launcher)
        self.assertIn('move /Y "dist\\NutriLab" "%SAIDA%"', self.launcher)


    def test_identidade_visual_e_gerada_antes_dos_testes_e_do_pyinstaller(self):
        texto = self.launcher
        normalizado = texto.replace(chr(92), "/")
        gerador = 'call %PY_CMD% tools/gerar_identidade_visual.py'
        self.assertIn(gerador, normalizado)
        self.assertIn('if not exist "tools/gerar_identidade_visual.py" goto ERRO_FONTE', texto)
        self.assertIn('if not exist "assets/identidade/renderizados/folhas.json" goto ERRO_IDENTIDADE', normalizado)
        self.assertLess(normalizado.index(gerador), normalizado.index('PyInstaller'))
        self.assertLess(normalizado.index(gerador), normalizado.index('test_svg_pipeline.py'))
        self.assertLess(normalizado.index('pip install -r requirements-build.txt'), normalizado.index(gerador))

    def test_compilacao_conjunta_gera_apk_antes_do_executavel(self):
        texto = self.launcher
        normalizado = texto.replace(chr(92), "/")
        chamada_apk = 'call "%RAIZ%mobile/apk/Gerar_APK.bat" /integrado'
        self.assertIn(chamada_apk, normalizado)
        self.assertLess(normalizado.index(chamada_apk), normalizado.index("PyInstaller"))
        self.assertIn('if errorlevel 1 goto ERRO_APK', texto)
        self.assertIn('"%SAIDA%/_internal/mobile/apk/saida/NutriLab-Mobile.apk"', normalizado)
        self.assertIn("Compress-Archive", texto)
        self.assertIn("NutriLab-Desktop.zip", texto)
        self.assertIn('if /I "%~1"=="/recompilar-sem-abrir" goto COMPILAR', texto)
        self.assertIn('if /I "%~1"=="/recompilar-sem-abrir" exit /b 0', texto)

    def test_gerador_apk_tem_modo_integrado_sem_interacao(self):
        apk = (RAIZ / "mobile" / "apk" / "Gerar_APK.bat").read_text(encoding="utf-8")
        self.assertIn('if /I "%~1"=="/integrado"', apk)
        self.assertIn("if defined MODO_INTEGRADO goto :fim_integrado", apk)
        self.assertIn("if defined MODO_INTEGRADO exit /b 1", apk)

if __name__ == "__main__":
    unittest.main()
