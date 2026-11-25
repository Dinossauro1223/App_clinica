import unittest

import pep_evolucao_ui


class TestPepEvolucaoUIImport(unittest.TestCase):
    def test_editor_existe_sem_criar_janela_no_import(self):
        self.assertTrue(hasattr(pep_evolucao_ui, "FormEvolucaoUI"))


if __name__ == "__main__":
    unittest.main()
