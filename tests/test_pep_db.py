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


if __name__ == "__main__":
    unittest.main()
