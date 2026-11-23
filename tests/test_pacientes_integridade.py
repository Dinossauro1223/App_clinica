"""Testes de proteção à exclusão do cadastro de pacientes, usando dados sintéticos."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from pacientes_integridade import registros_vinculados, paciente_pode_ser_excluido


class TestProtecaoExclusaoPaciente(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "clinica.db"
        self.conn = sqlite3.connect(self.db)
        self.addCleanup(self.conn.close)
        self.conn.execute("CREATE TABLE Pacientes (id_paciente INTEGER PRIMARY KEY, nome TEXT)")
        self.conn.execute("INSERT INTO Pacientes VALUES (1, 'Paciente Sintético')")
        self.conn.commit()

    def test_paciente_sem_historico_pode_ser_excluido(self):
        self.assertEqual(registros_vinculados(self.conn, 1), {})
        self.assertTrue(paciente_pode_ser_excluido(self.conn, 1))

    def test_consulta_clinica_bloqueia_exclusao(self):
        self.conn.execute("CREATE TABLE Consultas (id_consulta INTEGER PRIMARY KEY, id_paciente INTEGER, anamnese TEXT)")
        self.conn.execute("INSERT INTO Consultas VALUES (1, 1, 'Dados fictícios')")
        self.conn.commit()
        self.assertEqual(registros_vinculados(self.conn, 1), {"Consultas": 1})
        self.assertFalse(paciente_pode_ser_excluido(self.conn, 1))

    def test_pep_mapa_e_documentos_bloqueiam_exclusao(self):
        self.conn.executescript("""
            CREATE TABLE Pep_Evolucoes (id_evolucao INTEGER PRIMARY KEY, id_paciente INTEGER);
            CREATE TABLE Mapa_Registros (id_registro INTEGER PRIMARY KEY, id_paciente INTEGER);
            CREATE TABLE Condutas_Alta_Docs (id_doc INTEGER PRIMARY KEY, id_paciente INTEGER);
            INSERT INTO Pep_Evolucoes VALUES (1, 1);
            INSERT INTO Mapa_Registros VALUES (1, 1);
            INSERT INTO Condutas_Alta_Docs VALUES (1, 1);
        """)
        self.conn.commit()
        self.assertEqual(registros_vinculados(self.conn, 1), {"Mapa_Registros": 1, "Condutas_Alta_Docs": 1, "Pep_Evolucoes": 1})
        self.assertFalse(paciente_pode_ser_excluido(self.conn, 1))

    def test_pasta_de_documentos_com_arquivo_bloqueia_exclusao(self):
        pasta = Path(self.temp.name) / "arquivos_pacientes" / "paciente_1"
        pasta.mkdir(parents=True)
        (pasta / "documento_sintetico.txt").write_text("Arquivo de teste", encoding="utf-8")
        self.assertEqual(registros_vinculados(self.conn, 1, pasta), {"Arquivos físicos": 1})
        self.assertFalse(paciente_pode_ser_excluido(self.conn, 1, pasta))

    def test_pasta_vazia_nao_bloqueia_exclusao(self):
        pasta = Path(self.temp.name) / "paciente_1"
        pasta.mkdir()
        self.assertTrue(paciente_pode_ser_excluido(self.conn, 1, pasta))

    def test_id_invalido_rejeitado(self):
        for valor in (0, -1, True, "1", None):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                registros_vinculados(self.conn, valor)


if __name__ == "__main__":
    unittest.main()
