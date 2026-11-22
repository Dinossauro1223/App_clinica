# -*- coding: utf-8 -*-
"""Testes da equação de estatura da planilha do setor para idosos."""
import unittest

import nutri_calculos as nc


class TestAlturaIdosoPlanilha(unittest.TestCase):
    def test_equacao_para_mulher_branca(self):
        resultado = nc.estimar_altura(50, "Mulher", "Branco", 68, metodo_idoso="planilha")
        self.assertAlmostEqual(resultado.valor, 158.9, places=1)
        self.assertIn("Planilha do setor", resultado.equacao)

    def test_equacao_exige_cor(self):
        with self.assertRaises(nc.EstimativaIndisponivel):
            nc.estimar_altura(50, "Mulher", "", 68, metodo_idoso="planilha")

    def test_avisa_quando_idade_excede_80_anos(self):
        resultado = nc.estimar_altura(50, "Homem", "Negro", 82, metodo_idoso="planilha")
        self.assertTrue(any("acima da faixa" in aviso.lower() for aviso in resultado.avisos))


if __name__ == "__main__":
    unittest.main()
