"""Testes da exportação/importação isolada de bases do NutriLab."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import base_testes


class TestBasesTeste(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nutrilab-base-teste-")
        self.raiz = Path(self.tmp.name)
        self.producao = self.raiz / "clinica.db"
        conn = sqlite3.connect(self.producao)
        conn.executescript("""
            CREATE TABLE pacientes (id INTEGER PRIMARY KEY, nome TEXT NOT NULL);
            CREATE TABLE consultas (id INTEGER PRIMARY KEY, paciente_id INTEGER,
                FOREIGN KEY(paciente_id) REFERENCES pacientes(id));
            INSERT INTO pacientes VALUES (1, 'Paciente Sintético');
            INSERT INTO consultas VALUES (10, 1);
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_exporta_copia_consistente_sem_alterar_origem(self):
        destino = self.raiz / "exportado.db"
        base_testes.exportar_base_teste(self.producao, destino)
        conn = sqlite3.connect(destino)
        try:
            self.assertEqual(conn.execute("SELECT nome FROM pacientes").fetchone()[0], "Paciente Sintético")
            self.assertEqual(conn.execute("SELECT paciente_id FROM consultas").fetchone()[0], 1)
        finally:
            conn.close()
        self.assertTrue(self.producao.is_file())

    def test_importacao_cria_arquivo_isolado_sem_sobrescrever(self):
        exportado = self.raiz / "exportado.db"
        base_testes.exportar_base_teste(self.producao, exportado)
        importado = base_testes.importar_base_teste(exportado, self.raiz / "dados")
        self.assertTrue(importado.is_file())
        self.assertEqual(importado.parent.name, "bases_teste")
        self.assertNotEqual(importado.resolve(), self.producao.resolve())
        with self.assertRaises(FileExistsError):
            base_testes._copiar_consistente(exportado, importado)

    def test_recusa_arquivo_que_nao_e_banco_nutrilab(self):
        invalido = self.raiz / "invalido.db"
        invalido.write_bytes(b"nao e sqlite")
        with self.assertRaises(base_testes.ErroBaseTeste):
            base_testes.exportar_base_teste(invalido, self.raiz / "saida.db")

    def test_nao_abre_banco_de_producao_em_modo_de_testes(self):
        with self.assertRaises(base_testes.ErroBaseTeste):
            base_testes.abrir_base_teste(self.producao, banco_producao=self.producao)

    def test_abre_copia_com_variavel_de_banco_isolada(self):
        copia = self.raiz / "copia.db"
        base_testes.exportar_base_teste(self.producao, copia)
        with mock.patch.object(base_testes.subprocess, "Popen") as executar:
            base_testes.abrir_base_teste(copia, banco_producao=self.producao)
        args, kwargs = executar.call_args
        self.assertIn("NUTRILAB_DB_PATH", kwargs["env"])
        self.assertEqual(kwargs["env"]["NUTRILAB_DB_PATH"], str(copia.resolve()))
        self.assertEqual(kwargs["env"]["NUTRILAB_MODO_TESTE"], "1")
        self.assertEqual(kwargs["env"]["NUTRILAB_DB_PRODUCAO"], str(self.producao.resolve()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
