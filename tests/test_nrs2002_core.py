# -*- coding: utf-8 -*-
"""Cobertura dos cálculos puros da triagem NRS-2002."""
import unittest
from datetime import date
import nrs2002 as nrs

class TestNRS2002Core(unittest.TestCase):
    def test_triagem_incompleta(self):
        r = nrs.classificar({"imc": None, "perda": False, "ingestao": False, "grave": False})
        self.assertFalse(r["completo"])
        self.assertEqual(r["etapa"], 1)

    def test_triagem_negativa_finaliza_sem_etapa_dois(self):
        r = nrs.classificar({k: False for k, _ in nrs.PERGUNTAS})
        self.assertTrue(r["completo"])
        self.assertEqual(r["grau"], "triagem_negativa")
        self.assertIsNone(r["escore"])

    def test_triagem_positiva_pede_segunda_etapa(self):
        r = nrs.classificar({"imc": True, "perda": False, "ingestao": False, "grave": False})
        self.assertFalse(r["completo"])
        self.assertEqual(r["etapa"], 2)

    def test_classifica_limites_de_escore(self):
        respostas = {"imc": True, "perda": False, "ingestao": False, "grave": False}
        self.assertEqual(nrs.classificar(respostas, 1, 1, 40)["grau"], "sem_risco")
        self.assertEqual(nrs.classificar(respostas, 2, 1, 40)["grau"], "risco")
        self.assertEqual(nrs.classificar(respostas, 3, 2, 40)["grau"], "risco")

    def test_adicional_de_idade_70_anos(self):
        respostas = {"imc": True, "perda": False, "ingestao": False, "grave": False}
        self.assertEqual(nrs.classificar(respostas, 1, 1, 69)["escore"], 2)
        self.assertEqual(nrs.classificar(respostas, 1, 1, 70)["escore"], 3)

    def test_rejeita_pontuacao_fora_da_faixa(self):
        respostas = {"imc": True, "perda": False, "ingestao": False, "grave": False}
        for valor in (-1, 4, True):
            with self.assertRaises(ValueError):
                nrs.classificar(respostas, valor, 1, 40)

    def test_intervalo_e_proxima_data(self):
        self.assertEqual(nrs.dias_para("risco"), 7)
        self.assertEqual(nrs.proxima_reavaliacao(date(2026, 11, 22), "risco"), date(2026, 11, 29))

if __name__ == "__main__":
    unittest.main()
