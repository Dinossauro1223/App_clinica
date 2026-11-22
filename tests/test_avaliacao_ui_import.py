import unittest
from datetime import date
from avaliacao_ui import AvaliacaoUI

class TestAvaliacaoUIImport(unittest.TestCase):
    def test_age_helper(self):
        hoje = date.today()
        self.assertEqual(AvaliacaoUI.idade("01/01/2000"), hoje.year - 2000)
    def test_invalid_birthdate(self):
        self.assertIsNone(AvaliacaoUI.idade("invalida"))

if __name__ == "__main__":
    unittest.main()
