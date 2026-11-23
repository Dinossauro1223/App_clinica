import os
import sqlite3
import tempfile
import unittest
from contextlib import closing

import db_migracoes
import pep_db as pep

class TestPepDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "pep.db")
        db_migracoes.aplicar_migracoes(self.db, backup=False)

    def tearDown(self):
        self.tmp.cleanup()

    def _user(self):
        return pep.criar_usuario(self.db, "nutri1", "Nutricionista Teste", "CRN-6 1234", "passphrase-example", b"img")

    def test_autenticacao(self):
        uid = self._user()
        self.assertIsNotNone(pep.autenticar(self.db, uid, "passphrase-example"))
        self.assertIsNone(pep.autenticar(self.db, uid, "wrong-pass"))
        pep.desativar_usuario(self.db, uid)
        self.assertIsNone(pep.autenticar(self.db, uid, "passphrase-example"))

    def test_rejeita_id_paciente_invalido(self):
        uid = self._user()
        with self.assertRaises(ValueError):
            pep.salvar_evolucao(self.db, 0, "Paciente", "15/11/2026", {}, "texto", uid)

    def test_migracao_cria_travas_append_only(self):
        with closing(sqlite3.connect(self.db)) as conn:
            nomes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        self.assertIn("tr_pep_evolucoes_update_imutavel", nomes)
        self.assertIn("tr_pep_evolucoes_delete_imutavel", nomes)

    def _paciente(self, nome="Paciente Sintético"):
        with closing(sqlite3.connect(self.db)) as conn:
            # A migração PEP não cria o esquema clínico legado; os testes precisam
            # simular explicitamente a tabela Pacientes em seu banco temporário.
            conn.execute("""CREATE TABLE IF NOT EXISTS Pacientes (
                id_paciente INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL, data_nascimento TEXT, sexo TEXT
            )""")
            cur = conn.execute("INSERT INTO Pacientes (nome, data_nascimento, sexo) VALUES (?, ?, ?)",
                               (nome, "01/01/1990", "F"))
            conn.commit()
            return cur.lastrowid

    def test_evolucao_persistida_com_dados_de_assinatura_e_data_formatada(self):
        uid = self._user()
        pid = self._paciente()
        eid = pep.salvar_evolucao(self.db, pid, "Paciente Sintético", "22/11/2026",
                                  {"peso": 60}, "Texto clínico sintético", uid)
        item = pep.listar_evolucoes(self.db, pid)[0]
        self.assertEqual(item["id_evolucao"], eid)
        self.assertEqual(item["data_evolucao"], "22/11/2026")
        self.assertEqual(item["cabecalho"], {"peso": 60})
        self.assertEqual(item["texto"], "Texto clínico sintético")
        self.assertEqual(item["assinante"], "Nutricionista Teste")
        self.assertEqual(item["crn"], "CRN-6 1234")
        self.assertIsNone(item["adendo_de"])

    def test_evolucao_nao_pode_ser_editada_ou_apagada(self):
        uid = self._user()
        pid = self._paciente()
        eid = pep.salvar_evolucao(self.db, pid, "Paciente Sintético", "22/11/2026",
                                  {}, "Registro imutável", uid)
        with closing(sqlite3.connect(self.db)) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE Pep_Evolucoes SET texto='alterado' WHERE id_evolucao=?", (eid,))
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM Pep_Evolucoes WHERE id_evolucao=?", (eid,))
            conn.rollback()
            row = conn.execute("SELECT texto FROM Pep_Evolucoes WHERE id_evolucao=?", (eid,)).fetchone()
        self.assertEqual(row[0], "Registro imutável")

    def test_adendo_deve_vincular_evolucao_do_mesmo_paciente(self):
        uid = self._user()
        paciente_a = self._paciente("Paciente A")
        paciente_b = self._paciente("Paciente B")
        original = pep.salvar_evolucao(self.db, paciente_a, "Paciente A", "01/11/2026",
                                       {}, "Evolução inicial", uid)
        adendo = pep.salvar_evolucao(self.db, paciente_a, "Paciente A", "02/11/2026",
                                     {}, "Complemento", uid, adendo_de=original)
        self.assertEqual(pep.ultima_evolucao(self.db, paciente_a)["id_evolucao"], original)
        self.assertEqual(pep.listar_evolucoes(self.db, paciente_a)[0]["id_evolucao"], adendo)
        with self.assertRaises(ValueError):
            pep.salvar_evolucao(self.db, paciente_b, "Paciente B", "03/11/2026",
                                {}, "Adendo indevido", uid, adendo_de=original)


if __name__ == "__main__":
    unittest.main()
