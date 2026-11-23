"""Testes da busca prefixada e da listagem da TBCA."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

import gestao_alimentar_db as ga


class TestBuscaPrefixadaTBCA(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "tbca.db")
        ga.inicializar(self.db)
        with sqlite3.connect(self.db) as conn:
            conn.executemany(
                "INSERT INTO GA_TBCA_Alimentos (id_tbca, alimento, importado_em) VALUES (?, ?, ?)",
                [
                    ("A001", "Arroz branco cozido", "2026-11-22"),
                    ("A002", "Arroz integral cozido", "2026-11-22"),
                    ("B001", "Farinha de arroz", "2026-11-22"),
                    ("C001", "Feijão carioca", "2026-11-22"),
                ],
            )
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_retorna_todos_os_alimentos_que_comecam_com_o_termo(self):
        encontrados = ga.listar_alimentos(self.db, "arroz")
        self.assertEqual(
            [item["id_tbca"] for item in encontrados],
            ["A001", "A002"],
        )

    def test_nao_retorna_ocorrencia_no_meio_do_nome(self):
        encontrados = ga.listar_alimentos(self.db, "arroz")
        self.assertNotIn("B001", [item["id_tbca"] for item in encontrados])

    def test_rotulo_tbca_e_id_manual_sao_convertidos_sem_perda(self):
        from gestao_alimentar_ui import _extrair_id_tbca
        self.assertEqual(_extrair_id_tbca("A001 | Arroz branco cozido"), "A001")
        self.assertEqual(_extrair_id_tbca("A001"), "A001")
        self.assertIsNone(_extrair_id_tbca("— selecionar alimento da TBCA —"))

    def test_id_tbca_exato_continua_pesquisavel(self):
        encontrados = ga.listar_alimentos(self.db, "B001")
        self.assertEqual([item["id_tbca"] for item in encontrados], ["B001"])


if __name__ == "__main__":
    unittest.main()
