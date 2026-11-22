# -*- coding: utf-8 -*-
"""Testes sintéticos para cálculos da avaliação nutricional."""
import unittest
import avaliacao_nutri as av

class TestCalculosNutri(unittest.TestCase):
    def test_aj_por_altura_para_amputado(self):
        self.assertAlmostEqual(av.aj_da_altura(146, 89, "Homem")[0], 42.26237623762376, 9)
        self.assertAlmostEqual(av.aj_da_altura(146, 89, "Mulher")[0], 45.07103825136612, 9)

    def test_peso_seco_com_edema_ascite_e_amputacao(self):
        pct = av.pct_amputacao({"Perna abaixo do joelho": 1, "Antebraço + mão": 1})
        self.assertAlmostEqual(pct, 8.2)
        self.assertAlmostEqual(av.peso_ajustado(70, 7.7, pct), (70 - 7.7) / (1 - 0.082))

    def test_limite_amputacoes(self):
        with self.assertRaises(ValueError):
            av.pct_amputacao({"Mão": 1, "Antebraço + mão": 1, "Braço inteiro": 1})

    def test_dri_e_dados_insuficientes(self):
        self.assertAlmostEqual(av.eer_dri("Homem", 40, 80, 1.8, 0, imc=24.7), 2524.88, 2)
        self.assertIsNone(av.eer_dri("Homem", 2, 12, 0.85))
        self.assertIsNone(av.eer_dri("Homem", 40, None, 1.8))

    def test_calculo_peso_ajustado_meta_calorica_e_dri(self):
        r = av.calcular({"sexo": "Homem", "cor": "Branca", "idade": "50", "peso": "90", "altura": "175",
                         "ascite": "Moderada (6 kg)", "kcalkg": "25", "ptnkg": "1,2", "atividade": 0})
        self.assertAlmostEqual(r["ajustado"], 84.0)
        self.assertAlmostEqual(r["kcal"], 2100.0)
        self.assertIsNotNone(r["dri"])
        self.assertIsNotNone(r["dif_dri_pct"])

if __name__ == "__main__":
    unittest.main()
