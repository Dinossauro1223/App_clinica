# -*- coding: utf-8 -*-
"""Testes unitários do módulo tema.py: funções puras de data."""
import unittest

import tema


class TestTemaDatas(unittest.TestCase):
    def test_data_valida_reconhece_datas_validas(self):
        self.assertTrue(tema.data_valida("01/01/2026"))
        self.assertTrue(tema.data_valida("29/02/2024"))

    def test_data_valida_rejeita_datas_invalidas(self):
        self.assertFalse(tema.data_valida("31/02/2026"))
        self.assertFalse(tema.data_valida("2026-01-01"))
        self.assertFalse(tema.data_valida(""))

    def test_mascara_data(self):
        self.assertEqual(tema.CampoData.formatar("01012026"), "01/01/2026")
        self.assertEqual(tema.CampoData.formatar("0101"), "01/01")
        self.assertEqual(tema.CampoData.formatar("01/01/2026"), "01/01/2026")
        self.assertEqual(tema.CampoData.formatar("01a01b2026extra"), "01/01/2026")


if __name__ == "__main__":
    unittest.main()
