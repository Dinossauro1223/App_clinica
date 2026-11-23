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


    def test_paleta_tem_contraste_independente_do_modo(self):
        self.assertNotEqual(tema.BRANCO[0], tema.BRANCO[1])
        self.assertNotEqual(tema.FUNDO[0], tema.FUNDO[1])
        self.assertNotEqual(tema.TEXTO[0], tema.TEXTO[1])

    def test_cor_atual_resolve_tupla_para_tk(self):
        self.assertEqual(tema.cor_atual(("#ffffff", "#111111"), "Light"), "#ffffff")
        self.assertEqual(tema.cor_atual(("#ffffff", "#111111"), "Dark"), "#111111")

    def test_mascara_data(self):
        self.assertEqual(tema.CampoData.formatar("01012026"), "01/01/2026")
        self.assertEqual(tema.CampoData.formatar("0101"), "01/01")
        self.assertEqual(tema.CampoData.formatar("01/01/2026"), "01/01/2026")
        self.assertEqual(tema.CampoData.formatar("01a01b2026extra"), "01/01/2026")


if __name__ == "__main__":
    unittest.main()
