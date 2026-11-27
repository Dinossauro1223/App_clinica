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

    def test_nutrison_energy_15_composicao_oficial_por_100ml(self):
        # Dados transcritos da página/ficha oficial Danone Nutricia, sem conversão de apresentação.
        r = sc.calcular_oferta([
            {"nome": "Nutrison Energy 1.5", "qtd_dia": 250, "unidade": "ml",
             "kcal_100": 149, "ptn_100": 6, "lip_100": 5.8, "carb_100": 18, "sod_100": 134}
        ], peso_kg=60, meta_kcal=1800, meta_proteina_g=90)
        self.assertEqual(r["totais"]["kcal_100"], 372.5)
        self.assertEqual(r["totais"]["ptn_100"], 15)
        self.assertEqual(r["totais"]["lip_100"], 14.5)
        self.assertEqual(r["totais"]["carb_100"], 45)
        self.assertEqual(r["totais"]["sod_100"], 335)
        self.assertEqual(r["percentual_meta_kcal"], 20.69)
        self.assertEqual(r["percentual_meta_proteina"], 16.67)
        self.assertTrue(r["completo"])

    def test_fichas_oficiais_de_outras_formulas_enterais(self):
        r = sc.calcular_oferta([
            {"nome": "Nutrison Protein Plus Energy", "qtd_dia": 100, "unidade": "ml",
             "kcal_100": 150, "ptn_100": 7.5, "lip_100": 5.8, "carb_100": 17, "sod_100": 100},
            {"nome": "Nutrison advanced Diason", "qtd_dia": 100, "unidade": "ml",
             "kcal_100": 102, "ptn_100": 4.3, "lip_100": 4.2, "carb_100": 11, "sod_100": 100},
            {"nome": "Nutrison advanced Cubison", "qtd_dia": 100, "unidade": "ml",
             "kcal_100": 103, "ptn_100": 5.5, "lip_100": 3.3, "carb_100": 13, "sod_100": 100},
        ], peso_kg=60, meta_kcal=1800, meta_proteina_g=90)
        self.assertEqual(r["totais"], {
            "kcal_100": 355, "ptn_100": 17.3, "lip_100": 13.3, "carb_100": 41, "sod_100": 300
        })
        self.assertEqual(r["percentual_meta_kcal"], 19.72)
        self.assertEqual(r["percentual_meta_proteina"], 19.22)
        self.assertTrue(r["completo"])

    def test_formulas_com_indicacao_oral_e_enteral(self):
        r = sc.calcular_oferta([
            {"nome": "Nutri R 2.0", "qtd_dia": 100, "unidade": "ml",
             "kcal_100": 200, "ptn_100": 3.3, "lip_100": 6.7, "carb_100": 32, "sod_100": 131},
            {"nome": "Nutri Enteral Soya", "qtd_dia": 100, "unidade": "ml",
             "kcal_100": 120, "ptn_100": 4.4, "lip_100": 4, "carb_100": 17, "sod_100": 55},
        ], peso_kg=60, meta_kcal=1800, meta_proteina_g=90)
        self.assertEqual(r["totais"], {
            "kcal_100": 320, "ptn_100": 7.7, "lip_100": 10.7, "carb_100": 49, "sod_100": 186
        })
        self.assertEqual(r["percentual_meta_kcal"], 17.78)
        self.assertEqual(r["percentual_meta_proteina"], 8.56)
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


class TestCalculoOsmolaridadeDiluicao(unittest.TestCase):
    def setUp(self):
        self.ficha = {"osmolaridade_ref": 300, "unidade_osmolaridade": "mOsm/L", "dose_ref": 100,
                      "unidade_dose_ref": "ml", "volume_final_ref_ml": 100, "unidade": "ml"}

    def test_calcula_osmolaridade_com_agua_adicionada(self):
        r = sc.calcular_osmolaridade_diluicao(self.ficha, 100, 100)
        self.assertEqual(r["status"], "estimada")
        self.assertEqual(r["valor"], 150)
        self.assertEqual(r["volume_final_ml"], 200)

    def test_escalona_dose_e_volume_de_referencia(self):
        r = sc.calcular_osmolaridade_diluicao(self.ficha, 50, 0)
        self.assertEqual(r["valor"], 300)
        self.assertEqual(r["volume_final_ml"], 50)
        self.assertEqual(r["status"], "estimada")

    def test_nao_calcula_sem_referencia_completa(self):
        r = sc.calcular_osmolaridade_diluicao(dict(self.ficha, dose_ref=None), 100, 50)
        self.assertIsNone(r["valor"])
        self.assertEqual(r["status"], "referencia_incompleta")

    def test_nao_converte_osmolalidade(self):
        r = sc.calcular_osmolaridade_diluicao(dict(self.ficha, unidade_osmolaridade="mOsm/kg"), 100, 50)
        self.assertIsNone(r["valor"])
        self.assertEqual(r["status"], "unidade_incompativel")

    def test_unidade_da_dose_deve_corresponder(self):
        r = sc.calcular_osmolaridade_diluicao(dict(self.ficha, unidade_dose_ref="g"), 100, 50)
        self.assertIsNone(r["valor"])
        self.assertEqual(r["status"], "unidade_dose_incompativel")
    def test_comparacao_substituicao_calcula_energia_proteina_e_peso(self):
        atual = {"id_suplemento": 1, "nome": "A", "qtd_dia": 200, "unidade": "ml",
                 "kcal_100": 100, "ptn_100": 4, "lip_100": 2, "carb_100": 10, "sod_100": 50,
                 "agua_ml": 100, "agua_separada_ml": 200}
        novo = {"id_suplemento": 2, "nome": "B", "qtd_dia": 200, "unidade": "ml",
                "kcal_100": 150, "ptn_100": 6, "lip_100": 3, "carb_100": 15, "sod_100": 80,
                "agua_ml": 50, "agua_separada_ml": 200}
        r = sc.comparar_substituicao([atual], 1, novo, peso_kg=60,
                                     meta_kcal=1800, meta_proteina_g=90)
        self.assertEqual(r["antes"]["energia_kcal_dia"], 200)
        self.assertEqual(r["depois"]["energia_kcal_dia"], 300)
        self.assertEqual(r["comparacoes"]["energia_kcal_dia"]["diferenca"], 100)
        self.assertEqual(r["depois"]["energia_kcal_kg_dia"], 5)
        self.assertEqual(r["depois"]["proteina_g_kg_dia"], 0.2)
        self.assertEqual(r["agua_misturada_ml_dia"]["diferenca"], -50)
        self.assertEqual(r["agua_separada_ml_dia"]["diferenca"], 0)
        self.assertEqual(r["osmolaridade_atual"]["status"], "preparacoes_nao_informadas")

    def test_comparacao_osmolaridade_individual_por_preparacao(self):
        ficha = {"id_suplemento": 1, "nome": "A", "qtd_dia": 100, "unidade": "ml",
                 "kcal_100": 100, "ptn_100": 5, "lip_100": 1, "carb_100": 2, "sod_100": 3,
                 "osmolaridade_ref": 300, "unidade_osmolaridade": "mOsm/L",
                 "dose_ref": 100, "unidade_dose_ref": "ml", "volume_final_ref_ml": 100,
                 "preparacoes": [{"dose": 50, "agua_adicionada_ml": 0},
                                  {"dose": 50, "agua_adicionada_ml": 50, "agua_separada_ml": 100}]}
        novo = dict(ficha, id_suplemento=2, nome="B", preparacoes=[
            {"dose": 100, "agua_adicionada_ml": 100}])
        r = sc.comparar_substituicao([ficha], 1, novo, peso_kg=50)
        self.assertEqual(r["osmolaridade_atual"]["status"], "calculada")
        self.assertEqual([p["valor"] for p in r["osmolaridade_atual"]["preparacoes"]], [300, 150])
        self.assertEqual(r["osmolaridade_atual"]["agua_separada_total_ml"], 100)
        self.assertEqual(r["osmolaridade_substituto"]["preparacoes"][0]["valor"], 150)
        self.assertEqual(r["agua_misturada_ml_dia"]["atual"], 50)
        self.assertEqual(r["agua_misturada_ml_dia"]["substituto"], 100)
        self.assertEqual(r["agua_separada_ml_dia"]["atual"], 100)


    def test_volume_final_por_preparacao_nao_depende_de_osmolaridade_disponivel(self):
        ficha = {"id_suplemento": 1, "nome": "Pó", "qtd_dia": 10, "unidade": "g",
                 "osmolaridade_ref": None, "unidade_osmolaridade": "mOsm/L",
                 "dose_ref": 10, "unidade_dose_ref": "g", "volume_final_ref_ml": 100,
                 "preparacoes": [{"dose": 5, "agua_adicionada_ml": 20}]}
        resumo = sc._resumo_preparacoes_osmolaridade(ficha)
        self.assertEqual(resumo["status"], "dados_incompletos")
        self.assertEqual(resumo["volume_final_total_ml"], 70)

    def test_comparacao_exige_item_e_dose_substituta(self):
        with self.assertRaises(ValueError):
            sc.comparar_substituicao([], 1, {"qtd_dia": 100, "unidade": "ml"})
        with self.assertRaises(ValueError):
            sc.comparar_substituicao([{"id_suplemento": 1}], 1,
                                     {"qtd_dia": 0, "unidade": "ml"})


