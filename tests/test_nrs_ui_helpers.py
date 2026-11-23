import unittest
from datetime import date
from nrs_ui import NRSUI

class TestNRSUIHelpers(unittest.TestCase):
    def test_age_from_birthdate(self):
        self.assertEqual(NRSUI._idade("01/01/2000"), date.today().year - 2000 - (1 if (date.today().month, date.today().day) < (1, 1) else 0))
    def test_invalid_birthdate(self):
        self.assertIsNone(NRSUI._idade("invalid"))
        self.assertIsNone(NRSUI._idade(""))

if __name__ == "__main__":
    unittest.main()
