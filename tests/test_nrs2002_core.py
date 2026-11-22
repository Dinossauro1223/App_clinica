# -*- coding: utf-8 -*-
"""NRS 2002 conforme a calculadora Avante e agenda de reavaliacao."""
import os
import tempfile
import unittest
from datetime import date
import nrs2002 as nrs

NAO = {"imc": False, "perda": False, "ingestao": False, "grave": False}

class TestNRS2002(unittest.TestCase):
    def test_triagem_inicial_negativa(self):
        r = nrs.classificar(NAO)
        self.assertEqual((r["grau"], r["etapa"], r["escore"], r["completo"]), ("triagem_negativa", 1, None, True))

    def test_triagem_incompleta(self):
        r = nrs.classificar({"imc": False, "perda": None, "ingestao": False, "grave": False})
        self.assertFalse(r["completo"])
        self.assertIsNone(r["grau"])

    def test_um_sim_exige_escores_da_etapa_dois(self):
        r = nrs.classificar({**NAO, "perda": True})
        self.assertEqual((r["etapa"], r["completo"]), (2, False))

    def test_escore_e_classificacao(self):
        sim = {**NAO, "ingestao": True}
        self.assertEqual(nrs.classificar(sim, 1, 1, 50)["grau"], "sem_risco")
        self.assertEqual(nrs.classificar(sim, 2, 1, 50)["grau"], "risco")
        self.assertEqual(nrs.classificar(sim, 2, 2, 50)["grau"], "risco")
        self.assertEqual(nrs.classificar(sim, 3, 2, 50)["grau"], "alto_risco")
        self.assertEqual(nrs.classificar(sim, 3, 3, 50)["escore"], 6)

    def test_idade_70_soma_um_ponto(self):
        sim = {**NAO, "grave": True}
        self.assertEqual(nrs.classificar(sim, 1, 1, 69)["escore"], 2)
        r = nrs.classificar(sim, 1, 1, 70)
        self.assertEqual((r["escore"], r["grau"]), (3, "risco"))

    def test_respostas_invalidas(self):
        for invalida in (1, "sim", [], {}):
            with self.assertRaises(ValueError):
                nrs.classificar({**NAO, "imc": invalida})

    def test_data_reavaliacao(self):
        base = date(2026, 11, 16)
        self.assertEqual(nrs.proxima_reavaliacao(base, "sem_risco"), date(2026, 11, 23))
        self.assertEqual(nrs.proxima_reavaliacao(base, "risco", {"risco": 3}), date(2026, 11, 19))
        self.assertEqual(nrs.dias_para("alto_risco", {}), 7)

    def test_persistencia_intervalos_config(self):
        with tempfile.TemporaryDirectory() as d:
            db = os.path.join(d, "nrs.db")
            self.assertEqual(nrs.ler_intervalos(db), nrs.DIAS_PADRAO)
            salvo = nrs.salvar_intervalos(db, {"triagem_negativa": 7, "sem_risco": 7, "risco": 5, "alto_risco": 3})
            self.assertEqual(nrs.ler_intervalos(db)["alto_risco"], 3)
            self.assertEqual(salvo["risco"], 5)
            with self.assertRaises(ValueError):
                nrs.salvar_intervalos(db, {"triagem_negativa": 7, "sem_risco": 7, "risco": 0, "alto_risco": 3})

if __name__ == "__main__":
    unittest.main()
