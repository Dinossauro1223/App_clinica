# -*- coding: utf-8 -*-
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import suplementos_calculos as sc


class TestCalculoOfertaSuplementos(unittest.TestCase):
    def test_formula_liquida_calcula_aporte_e_percentuais(self):
        r = sc.calcular_oferta([
            {"nome": "Fórmula A", "qtd_dia": 400, "unidade": "ml",
             "kcal_100": 150, "ptn_100": 6, "lip_100": 5, "carb_100": 20, "sod_100": 90}
        ], peso_kg=60, meta_kcal=1800, meta_proteina_g=90)
        self.assertEqual(r["totais"], {"kcal_100": 600, "ptn_100": 24, "lip_100": 20, "carb_100": 80, "sod_100": 360})
        self.assertEqual(r["percentual_meta_kcal"], 33.33)
        self.assertEqual(r["percentual_meta_proteina"], 26.67)
        self.assertEqual(r["proteina_g_kg"], 0.4)
        self.assertTrue(r["completo"])

    def test_modulo_em_gramas_e_soma_de_itens(self):
        r = sc.calcular_oferta([
            {"nome": "Fórmula", "qtd_dia": 200, "unidade": "ml", "kcal_100": 100, "ptn_100": 4,
             "lip_100": 3, "carb_100": 12, "sod_100": 50},
            {"nome": "Proteína", "qtd_dia": 20, "unidade": "g", "kcal_100": 360, "ptn_100": 85,
             "lip_100": 1, "carb_100": 2, "sod_100": 100},
        ], peso_kg=50, meta_kcal=1500, meta_proteina_g=75)
        self.assertEqual(r["totais"]["kcal_100"], 272)
        self.assertEqual(r["totais"]["ptn_100"], 25)
        self.assertAlmostEqual(r["percentual_meta_proteina"], 33.33, places=2)
        self.assertTrue(r["completo"])

    def test_ficha_pendente_nao_inventa_nem_esconde_total_parcial(self):
        r = sc.calcular_oferta([
            {"nome": "Ficha pendente", "qtd_dia": 200, "unidade": "ml",
             "kcal_100": None, "ptn_100": 4, "lip_100": None, "carb_100": None, "sod_100": None}
        ], peso_kg=60, meta_kcal=1800, meta_proteina_g=90)
        self.assertIsNone(r["totais"]["kcal_100"])
        self.assertIsNone(r["percentual_meta_kcal"])
        self.assertEqual(r["totais"]["ptn_100"], 8)
        self.assertAlmostEqual(r["percentual_meta_proteina"], 8.89, places=2)
        self.assertFalse(r["completo"])
        self.assertEqual(r["pendencias"][0]["nome"], "Ficha pendente")

    def test_dose_ou_unidade_ausente_impede_calculo(self):
        for item in (
            {"nome": "Sem dose", "unidade": "ml", "kcal_100": 100, "ptn_100": 5},
            {"nome": "Unidade inválida", "qtd_dia": 100, "unidade": "L", "kcal_100": 100, "ptn_100": 5},
        ):
            r = sc.calcular_oferta([item], peso_kg=60, meta_kcal=1800, meta_proteina_g=90)
            self.assertIsNone(r["totais"]["kcal_100"])
            self.assertFalse(r["completo"])

    def test_meta_e_peso_invalidos_nao_geram_divisao_por_zero(self):
        r = sc.calcular_oferta([
            {"nome": "A", "qtd_dia": 100, "unidade": "g", "kcal_100": 100, "ptn_100": 10,
             "lip_100": 1, "carb_100": 2, "sod_100": 3}
        ], peso_kg=0, meta_kcal=0, meta_proteina_g=-1)
        self.assertIsNone(r["percentual_meta_kcal"])
        self.assertIsNone(r["percentual_meta_proteina"])
        self.assertIsNone(r["proteina_g_kg"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
