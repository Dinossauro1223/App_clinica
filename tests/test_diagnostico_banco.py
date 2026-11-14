"""Testes de tools/diagnostico_banco.py — bancos sintéticos; o diagnóstico nunca pode vazar conteúdo de linhas."""
import contextlib
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import db_migracoes as mig
from tools import diagnostico_banco as diag

SENTINELA = "SENTINELA-SINTETICA-123"     # texto que jamais deve aparecer em relatório


class BaseTmp(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.raiz = Path(tmp.name)

    def banco(self, rel, linhas=3):
        caminho = self.raiz / rel
        caminho.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(caminho))
        conn.execute("CREATE TABLE Pacientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT)")
        conn.execute('CREATE TABLE "Tabela ""estranha""" (x)')
        conn.executemany("INSERT INTO Pacientes (nome) VALUES (?)", [(SENTINELA,)] * linhas)
        conn.commit()
        conn.close()
        return caminho

    def executar(self, *argv):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            codigo = diag.main([str(a) for a in argv])
        return codigo, saida.getvalue()


class TestProcura(BaseTmp):
    def test_encontra_por_nome_e_ignora_pastas_de_ferramentas_e_backups(self):
        esperados = {self.banco("dist/app/clinica.db"), self.banco("dist/app/_internal/clinica.db")}
        self.banco(".venv/lib/clinica.db")
        self.banco("dist/app/backups/clinica.backup_20261109-200000_manual.db")
        self.assertEqual(set(diag.procurar_bancos([self.raiz])), esperados)

    def test_opcao_todos_inclui_qualquer_banco(self):
        outro = self.banco("dados/outro.sqlite3")
        self.assertIn(outro, diag.procurar_bancos([self.raiz], todos=True))
        self.assertNotIn(outro, diag.procurar_bancos([self.raiz]))


class TestInspecao(BaseTmp):
    def test_conta_linhas_sem_ler_conteudo_e_nao_altera_o_arquivo(self):
        db = self.banco("clinica.db", linhas=3)
        antes = hashlib.sha256(db.read_bytes()).hexdigest()
        info = diag.inspecionar(db)
        self.assertEqual(info["tabelas"], {'Tabela "estranha"': 0, "Pacientes": 3})
        self.assertEqual((info["integridade_rapida"], info["versao_esquema"], info["erro"]), ("ok", None, None))
        self.assertNotIn(SENTINELA, json.dumps(info))
        self.assertEqual(hashlib.sha256(db.read_bytes()).hexdigest(), antes)

    def test_le_a_versao_do_esquema(self):
        db = self.banco("clinica.db")
        mig.aplicar_migracoes(db)
        self.assertEqual(diag.inspecionar(db)["versao_esquema"], 1)

    def test_arquivo_corrompido_nao_derruba_o_diagnostico(self):
        ruim = self.raiz / "clinica.db"
        ruim.write_bytes(b"isto nao e um banco sqlite " * 100)
        info = diag.inspecionar(ruim)
        self.assertIsNotNone(info["erro"])
        codigo, saida = self.executar(self.raiz)
        self.assertEqual(codigo, 1)
        self.assertIn("ERRO ao ler", saida)


class TestDivisao(BaseTmp):
    def test_detecta_divisao_com_pasta_interna_do_pyinstaller(self):
        self.banco("app/clinica.db", linhas=5)
        self.banco("app/_internal/clinica.db", linhas=2)
        inspecoes = [diag.inspecionar(p) for p in diag.procurar_bancos([self.raiz])]
        avisos = diag.detectar_divisao(inspecoes)
        self.assertEqual(len(avisos), 1)
        self.assertIn("DIVISÃO DE BANCO", avisos[0])
        self.assertIn("_internal", avisos[0])
        self.assertIn("NÃO apague", avisos[0])

    def test_banco_unico_nao_e_divisao(self):
        self.banco("app/clinica.db")
        self.assertEqual(diag.detectar_divisao([diag.inspecionar(self.raiz / "app" / "clinica.db")]), [])

    def test_main_em_texto_e_json_sem_vazar_conteudo(self):
        self.banco("app/clinica.db", linhas=5)
        self.banco("app/_internal/clinica.db", linhas=2)
        destino = self.raiz / "relatorio.json"
        codigo, saida = self.executar(self.raiz, "--json", destino)
        self.assertEqual(codigo, 1)
        self.assertIn("[ALERTA] DIVISÃO DE BANCO", saida)
        self.assertIn("Pacientes: 5 linhas", saida)
        self.assertIn("Pacientes: 2 linhas", saida)
        self.assertNotIn(SENTINELA, saida)
        dados = json.loads(destino.read_text(encoding="utf-8"))
        self.assertEqual(len(dados["bancos"]), 2)
        self.assertNotIn(SENTINELA, json.dumps(dados))

    def test_sem_problemas_retorna_zero_e_sem_banco_so_informa(self):
        self.banco("app/clinica.db")
        self.assertEqual(self.executar(self.raiz)[0], 0)
        codigo, saida = self.executar(self.raiz / "app" / "vazio")
        self.assertEqual(codigo, 0)
        self.assertIn("Nenhum banco encontrado", saida)


if __name__ == "__main__":
    unittest.main()
