"""Testes de tools/gerar_banco_modelo.py e do .spec — bancos SINTÉTICOS; nenhum dado real."""
import contextlib
import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from tools import gerar_banco_modelo as gm

SENTINELA = "SENTINELA-PACIENTE-XYZ"


def criar_origem(caminho):
    conn = sqlite3.connect(str(caminho))
    conn.executescript("""
        CREATE TABLE Pacientes (id_paciente INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL);
        CREATE TABLE Consultas (id_consulta INTEGER PRIMARY KEY AUTOINCREMENT, id_paciente INTEGER, anamnese TEXT);
        CREATE TABLE Exames_Catalogo (id_exame INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, unidade TEXT);
        CREATE TABLE Regras_Complementares (id_regra INTEGER PRIMARY KEY AUTOINCREMENT, exame TEXT, regra TEXT);
        CREATE TABLE Resultados_Exames (id INTEGER PRIMARY KEY AUTOINCREMENT, id_paciente INTEGER, valor TEXT);
        CREATE INDEX idx_consultas_paciente ON Consultas(id_paciente);
        CREATE TRIGGER trg_catalogo AFTER INSERT ON Exames_Catalogo
            BEGIN INSERT INTO Pacientes (nome) VALUES ('criado-por-gatilho'); END;
    """)
    conn.execute("DROP TRIGGER trg_catalogo")                  # o gatilho só atrapalha a semeadura da origem
    conn.executemany("INSERT INTO Exames_Catalogo (nome, unidade) VALUES (?, ?)", [("Glicose", "mg/dL"), ("Ureia", "mg/dL")])
    conn.executemany("INSERT INTO Regras_Complementares (exame, regra) VALUES (?, ?)", [("Glicose", "r1"), ("Ureia", "r2"), ("Ureia", "r3")])
    conn.executemany("INSERT INTO Pacientes (nome) VALUES (?)", [(f"{SENTINELA}-{i}",) for i in range(200)])
    conn.executemany("INSERT INTO Consultas (id_paciente, anamnese) VALUES (?, ?)", [(i, f"{SENTINELA} anamnese {i}") for i in range(1, 200)])
    conn.executemany("INSERT INTO Resultados_Exames (id_paciente, valor) VALUES (?, ?)", [(i, SENTINELA) for i in range(1, 100)])
    conn.commit()
    conn.execute("DELETE FROM Pacientes WHERE id_paciente > 50")  # deixa resíduos em páginas livres do arquivo de origem
    conn.execute("""CREATE TRIGGER trg_catalogo AFTER INSERT ON Exames_Catalogo
                    BEGIN INSERT INTO Pacientes (nome) VALUES ('criado-por-gatilho'); END""")
    conn.commit()
    conn.close()
    return Path(caminho)


def contar(caminho, tabela):
    conn = sqlite3.connect(str(caminho))
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
    finally:
        conn.close()


def ddl(caminho):
    conn = sqlite3.connect(str(caminho))
    try:
        return sorted((t, n, " ".join(s.split())) for t, n, s in conn.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'"))
    finally:
        conn.close()


class BaseTmp(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.origem = criar_origem(self.tmp / "clinica.db")
        self.destino = self.tmp / "modelo_banco" / "clinica.db"


class TestGerar(BaseTmp):
    def test_copia_o_catalogo_e_zera_o_resto(self):
        resumo = gm.gerar(self.origem, self.destino)
        self.assertEqual(contar(self.destino, "Exames_Catalogo"), 2)
        self.assertEqual(contar(self.destino, "Regras_Complementares"), 3)
        for tabela in ("Pacientes", "Consultas", "Resultados_Exames"):
            self.assertEqual(contar(self.destino, tabela), 0, tabela)
        self.assertEqual(resumo["Pacientes"], {"linhas": 0, "copiadas": False})
        self.assertEqual(resumo["Exames_Catalogo"], {"linhas": 2, "copiadas": True})

    def test_estrutura_identica_inclusive_indices_e_gatilhos(self):
        gm.gerar(self.origem, self.destino)
        self.assertEqual(ddl(self.destino), ddl(self.origem))

    def test_nenhum_dado_de_paciente_no_arquivo_gerado_nem_residuos_de_linhas_apagadas(self):
        self.assertIn(SENTINELA.encode(), self.origem.read_bytes())          # a origem TEM os dados (e resíduos)
        gm.gerar(self.origem, self.destino)
        self.assertNotIn(SENTINELA.encode(), self.destino.read_bytes())
        self.assertEqual(contar(self.destino, "Pacientes"), 0)               # o gatilho (copiado como estrutura) não disparou

    def test_ids_de_pacientes_recomecam_em_1(self):
        gm.gerar(self.origem, self.destino)
        conn = sqlite3.connect(str(self.destino))
        conn.execute("INSERT INTO Pacientes (nome) VALUES ('novo')")
        self.assertEqual(conn.execute("SELECT id_paciente FROM Pacientes").fetchall(), [(1,)])
        conn.close()

    def test_tabelas_de_catalogo_personalizadas(self):
        resumo = gm.gerar(self.origem, self.destino, copiar_linhas=["Exames_Catalogo"])
        self.assertEqual(contar(self.destino, "Regras_Complementares"), 0)
        self.assertFalse(resumo["Regras_Complementares"]["copiadas"])

    def test_origem_nao_e_alterada(self):
        antes = self.origem.read_bytes()
        gm.gerar(self.origem, self.destino)
        self.assertEqual(self.origem.read_bytes(), antes)


class TestRecusas(BaseTmp):
    def test_destino_existente_exige_sobrescrever(self):
        gm.gerar(self.origem, self.destino)
        with self.assertRaises(gm.ErroModelo):
            gm.gerar(self.origem, self.destino)
        gm.gerar(self.origem, self.destino, sobrescrever=True)

    def test_origem_igual_ao_destino_inexistente_ou_invalida(self):
        with self.assertRaises(gm.ErroModelo):
            gm.gerar(self.origem, self.origem, sobrescrever=True)
        with self.assertRaises(gm.ErroModelo):
            gm.gerar(self.tmp / "nao-existe.db", self.destino)
        ruim = self.tmp / "ruim.db"
        ruim.write_bytes(b"isto nao e um banco sqlite " * 100)
        with self.assertRaises(gm.ErroModelo):
            gm.gerar(ruim, self.destino)

    def test_tabela_de_catalogo_inexistente_nao_deixa_arquivos_pela_metade(self):
        with self.assertRaises(gm.ErroModelo):
            gm.gerar(self.origem, self.destino, copiar_linhas=["Nao_Existe"])
        self.assertFalse(self.destino.exists())
        self.assertFalse(self.destino.with_name(self.destino.name + ".gerando").exists())


class TestMainEEspec(BaseTmp):
    def _main(self, *argv):
        saida, erro = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
            codigo = gm.main([str(a) for a in argv])
        return codigo, saida.getvalue(), erro.getvalue()

    def test_cli_imprime_so_contagens(self):
        codigo, saida, _ = self._main("--origem", self.origem, "--destino", self.destino)
        self.assertEqual(codigo, 0)
        self.assertIn("Exames_Catalogo: 2 linha(s) (catálogo copiado)", saida)
        self.assertIn("Pacientes: 0 linha(s) (somente estrutura)", saida)
        self.assertNotIn(SENTINELA, saida)
        self.assertEqual(self._main("--origem", self.tmp / "x.db", "--destino", self.destino)[0], 2)

    def test_spec_nao_embute_mais_o_banco_real(self):
        spec = (RAIZ / "app_clinica.spec").read_text(encoding="utf-8")
        self.assertNotIn("('clinica.db', '.')", spec)
        self.assertIn("(MODELO_BANCO, '.')", spec)
        self.assertIn("modelo_banco", spec)
        self.assertIn("gerar_banco_modelo", spec)


if __name__ == "__main__":
    unittest.main()
