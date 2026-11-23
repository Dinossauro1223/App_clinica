"""Testes do banco inicial de distribuição; usam apenas bancos temporários sem dados reais."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
import sys
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from tools import gerar_banco_modelo as gm


class TestBancoModelo(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.destino = self.tmp / "modelo_banco" / "clinica.db"

    def _abrir(self):
        return sqlite3.connect(str(self.destino))

    def test_gera_sem_precisar_de_clinica_db_de_origem(self):
        # O diretório temporário não contém clinica.db nem qualquer banco prévio.
        self.assertFalse((self.tmp / "clinica.db").exists())
        resumo = gm.gerar(self.destino)
        self.assertTrue(self.destino.is_file())
        self.assertGreater(resumo["versao_migracoes"], 0)
        self.assertGreater(resumo["exames_catalogo"], 0)
        self.assertGreater(resumo["mapa_modulos"], 0)
        self.assertGreater(resumo["mapa_suplementos"], 0)

    def test_tabelas_clinicas_ficam_vazias(self):
        gm.gerar(self.destino)
        with self._abrir() as conn:
            for tabela in gm.TABELAS_QUE_DEVEM_FICAR_VAZIAS:
                existe = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabela,)
                ).fetchone()
                if existe:
                    total = conn.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0]
                    self.assertEqual(total, 0, tabela)

    def test_mapa_e_catalogos_iniciais_sao_criados(self):
        gm.gerar(self.destino)
        with self._abrir() as conn:
            tabelas = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            self.assertIn("Mapa_Registros", tabelas)
            self.assertIn("Exames_Catalogo", tabelas)
            self.assertIn("schema_migrations", tabelas)
            self.assertGreater(conn.execute("SELECT COUNT(*) FROM Exames_Catalogo").fetchone()[0], 0)
            self.assertGreater(conn.execute("SELECT COUNT(*) FROM Mapa_Suplementos").fetchone()[0], 0)
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_nao_sobrescreve_destino_sem_autorizacao(self):
        gm.gerar(self.destino)
        antes = self.destino.read_bytes()
        with self.assertRaises(gm.ErroModelo):
            gm.gerar(self.destino)
        self.assertEqual(self.destino.read_bytes(), antes)

    def test_sobrescrever_substitui_modelo(self):
        gm.gerar(self.destino)
        gm.gerar(self.destino, sobrescrever=True)
        with self._abrir() as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_cli_nao_exige_origem(self):
        codigo = gm.main_cli(["--destino", str(self.destino)])
        self.assertEqual(codigo, 0)
        self.assertTrue(self.destino.is_file())

    def test_spec_nao_usa_caminho_local_fixo_ou_banco_real(self):
        spec = (RAIZ / "app_clinica.spec").read_text(encoding="utf-8")
        self.assertNotIn("D:/app_clinica/venv", spec)
        self.assertIn("customtkinter.__file__", spec)
        self.assertIn("(MODELO_BANCO, 'modelo_banco')", spec)
        self.assertNotIn("('clinica.db', '.')", spec)

    def test_launcher_procura_exe_antes_de_compilar_e_gera_banco_sem_origem(self):
        launcher = (RAIZ / "Gerar_e_Abrir_NutriLab.bat").read_text(encoding="utf-8")
        busca_dist = launcher.index('if exist "%~dp0dist\\NutriLab\\NutriLab.exe"')
        busca_raiz = launcher.index('if not defined EXE if exist "%~dp0NutriLab.exe"')
        compilacao = launcher.index('call %PY_CMD% -m PyInstaller')
        geracao_banco = launcher.index('tools\\gerar_banco_modelo.py --sobrescrever')
        self.assertLess(busca_dist, busca_raiz)
        self.assertLess(busca_raiz, compilacao)
        self.assertLess(geracao_banco, compilacao)
        self.assertIn('dist\\NutriLab\\_internal\\python312.dll', launcher)
        self.assertIn(':ERRO_DLL_AUSENTE', launcher)
        self.assertIn('call %PY_CMD% -m pip install -r requirements-build.txt', launcher)
        self.assertNotIn('python -m venv', launcher.lower())
        self.assertIn('nao e necessario possuir clinica.db previamente', launcher.lower())

    def test_build_windows_verifica_dll_e_icone_do_pacote(self):
        workflow = (RAIZ / ".github" / "workflows" / "build-windows.yml").read_text(encoding="utf-8")
        self.assertIn('dist/NutriLab/_internal/python312.dll', workflow)
        self.assertIn('assets/identidade/nutrilab.ico', workflow)


if __name__ == "__main__":
    unittest.main()
