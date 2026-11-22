"""Integração da migração ambulatorial com um banco legado sintético."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

import db_migracoes as mig


class TestMigracaoAmbulatorial(unittest.TestCase):
    def test_v4_cria_tabelas_e_reverte_sem_tocar_esquema_legado(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "clinica.db"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE Pacientes (id_paciente INTEGER PRIMARY KEY, nome TEXT)")
            conn.execute("CREATE TABLE Consultas (id_consulta INTEGER PRIMARY KEY, id_paciente INTEGER, anamnese TEXT)")
            conn.execute("INSERT INTO Pacientes VALUES (7, 'Paciente sintético')")
            conn.execute("INSERT INTO Consultas VALUES (11, 7, 'Anamnese antiga')")
            conn.commit()
            conn.close()

            resultado = mig.aplicar_migracoes(db, migracoes=mig.MIGRACOES[:4], backup=False)
            self.assertEqual(resultado.versao_final, 4)
            self.assertEqual(resultado.aplicadas, [1, 2, 3, 4])
            conn = sqlite3.connect(db)
            try:
                tabelas = {r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                for tabela in (
                    "Consulta_Dados_Estruturados", "Consulta_Medicamentos", "Consulta_Metas",
                    "Recomendacoes_Docs", "Consulta_Recomendacoes", "Exames_Associacoes",
                    "Consulta_Triagens",
                ):
                    self.assertIn(tabela, tabelas)
                self.assertEqual(conn.execute("SELECT nome FROM Pacientes WHERE id_paciente=7").fetchone()[0],
                                 "Paciente sintético")
                self.assertEqual(conn.execute("SELECT anamnese FROM Consultas WHERE id_consulta=11").fetchone()[0],
                                 "Anamnese antiga")
            finally:
                conn.close()

            reversao = mig.reverter_migracoes(db, 3, backup=False)
            self.assertEqual(reversao.revertidas, [4])
            conn = sqlite3.connect(db)
            try:
                tabelas = {r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertNotIn("Consulta_Dados_Estruturados", tabelas)
                self.assertNotIn("Consulta_Triagens", tabelas)
                self.assertEqual(conn.execute("SELECT nome FROM Pacientes WHERE id_paciente=7").fetchone()[0],
                                 "Paciente sintético")
                self.assertEqual(mig.versao_atual(conn), 3)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
