import os
import sqlite3
import tempfile
import unittest

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

    def test_evolucao_imutavel_e_adendo(self):
        uid = self._user()
        eid = pep.salvar_evolucao(self.db, 42, "Paciente", "15/11/2026", {"peso": 62.5}, "Evolução inicial", uid)
        with sqlite3.connect(self.db) as conn:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE Pep_Evolucoes SET texto='alterado' WHERE id_evolucao=?", (eid,))
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM Pep_Evolucoes WHERE id_evolucao=?", (eid,))
        aid = pep.salvar_evolucao(self.db, 42, "Paciente", "16/11/2026", {}, "Adendo", uid, adendo_de=eid)
        self.assertEqual(pep.ultima_evolucao(self.db, 42)["id_evolucao"], eid)
        self.assertEqual(pep.listar_evolucoes(self.db, 42)[0]["id_evolucao"], aid)

if __name__ == "__main__":
    unittest.main()
