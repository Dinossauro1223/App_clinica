import os
import tempfile
import unittest
import db_migracoes
import pep_db as pep

class TestPepDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "pep.db")
        db_migracoes.aplicar_migracoes(self.db, backup=False)

    def tearDown(self):
        self.tmp.cleanup()

    def test_hospital_authentication(self):
        self.assertFalse(pep.hospital_configurado(self.db))
        pep.definir_senha_hospital(self.db, "hospital-pass-example")
        self.assertTrue(pep.hospital_configurado(self.db))
        self.assertTrue(pep.entrar_hospital(self.db, "hospital-pass-example"))
        self.assertFalse(pep.entrar_hospital(self.db, "wrong-pass"))

    def test_professional_login(self):
        uid = pep.criar_usuario(self.db, "nutri", "Profissional Teste", "CRN-6 1234", "user-pass-example", b"sig")
        self.assertIsNotNone(pep.autenticar(self.db, uid, "user-pass-example"))
        self.assertIsNone(pep.autenticar(self.db, uid, "wrong-pass"))
        pep.desativar_usuario(self.db, uid)
        self.assertIsNone(pep.autenticar(self.db, uid, "user-pass-example"))

if __name__ == "__main__":
    unittest.main()
