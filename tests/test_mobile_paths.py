import os
import tempfile
import unittest
from unittest import mock

import db_migracoes
import integracao_mobile as im


class TestCaminhoMobileDB(unittest.TestCase):
    def test_executavel_usa_pasta_gravavel_compartilhada(self):
        with tempfile.TemporaryDirectory() as pasta:
            banco_clinico = os.path.join(pasta, "clinica.db")
            db_migracoes.aplicar_migracoes(banco_clinico, backup=False)
            raiz_local = os.path.join(pasta, "LocalAppData")
            with mock.patch.object(im.sys, "frozen", True, create=True), mock.patch.dict(
                os.environ, {"LOCALAPPDATA": raiz_local}
            ):
                esperado = os.path.join(raiz_local, "NutriLab", "mobile", "mobile.db")
                self.assertEqual(im.caminho_mobile_db(banco_clinico, os.path.join(pasta, "_internal")), esperado)


if __name__ == "__main__":
    unittest.main(verbosity=2)
