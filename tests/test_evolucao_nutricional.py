import unittest

import evolucao_nutricional as ev


class TestEvolucaoNutricional(unittest.TestCase):
    def test_idade_considera_aniversario(self):
        self.assertEqual(ev.idade_em_anos("26/11/1954", "25/11/2026"), 71)
        self.assertEqual(ev.idade_em_anos("25/11/1954", "25/11/2026"), 72)

    def test_metas_e_adequacao(self):
        metas = ev.calcular_metas(62, 30, 1.2)
        self.assertEqual(metas["kcal_dia"], 1860)
        self.assertAlmostEqual(metas["proteina_g_dia"], 74.4)
        adeq = ev.calcular_adequacao(1620, 68, 1860, 74.4)
        self.assertAlmostEqual(adeq["adequacao_kcal_pct"], 87.09677, places=4)
        self.assertAlmostEqual(adeq["adequacao_proteina_pct"], 91.3978, places=3)

    def test_tne_prioriza_vomito_ou_diarreia(self):
        self.assertEqual(ev.classificar_tne(["retrolimentação"]), ("Regular", ["retrolimentação"]))
        self.assertEqual(ev.classificar_tne(["retrolimentação", "vômitos"]), ("Ruim", ["vômitos", "retrolimentação"]))
        self.assertEqual(ev.classificar_tne([]), ("Ótima", []))

    def test_tno_percentuais(self):
        self.assertEqual(ev.TNO_PERCENTUAIS["Regular"], 75)
        self.assertEqual(ev.TNO_PERCENTUAIS["Ótima"], 100)

    def test_volume_e_progressao_sem_ultrapassar_meta(self):
        meta = ev.volume_meta_enteral(1800, 1.5)
        self.assertEqual(meta, 1200)
        plano = ev.planejar_progressao_enteral(900, meta, 50, dias_alvo=4)
        self.assertEqual([p["volume_total_ml"] for p in plano["passos"]], [950, 1000, 1050, 1100])
        self.assertFalse(plano["atinge_meta_no_prazo"])
        plano = ev.planejar_progressao_enteral(1050, meta, 50, dias_alvo=4)
        self.assertEqual(plano["passos"][-1]["volume_total_ml"], 1200)
        self.assertTrue(plano["atinge_meta_no_prazo"])

    def test_estimativa_bomba_nao_e_prescricao(self):
        self.assertEqual(ev.estimar_tempo_bomba(300), 30)

    def test_antropometria_nao_mostra_auxiliares_quando_aferidos(self):
        texto = ev.formatar_antropometria({
            "data": "25/11/2026", "idade_anos": 72, "altura_m": 1.65, "altura_origem": "A",
            "peso_kg": 62, "peso_origem": "A", "aj_cm": 52, "pp_cm": 32, "pb_cm": 24,
            "imc_class": "Eutrofia"})
        self.assertIn("Antropometria 25/11/2026:", texto)
        self.assertNotIn("AJ:", texto)
        self.assertIn("ALT: 1.65 m (A)", texto)

    def test_estimativas_exibem_medidas_auxiliares(self):
        texto = ev.formatar_antropometria({
            "data": "25/11/2026", "idade_anos": 72, "altura_m": 1.65, "altura_origem": "E",
            "peso_kg": 62, "peso_origem": "E", "aj_cm": 52, "pp_cm": 32, "pb_cm": 24,
            "imc_class": "Eutrofia"})
        self.assertIn("AJ: 52 cm", texto)
        self.assertIn("PP: 32 cm", texto)
        self.assertIn("PB: 24 cm", texto)

    def test_adequacao_ausente_para_via_oral(self):
        dados = {"antropometria": {"idade_anos": 30, "altura_m": 1.7, "altura_origem": "A",
                 "peso_kg": 70, "peso_origem": "A"}, "via": "Oral",
                 "metas": ev.calcular_metas(70, 25, 1.0),
                 "oferta": {"kcal_dia": 1000, "proteina_g_dia": 40}}
        self.assertNotIn("Adequação da meta", ev.gerar_evolucao(dados))

    def test_rejeita_parametros_invalidos(self):
        with self.assertRaises(ValueError):
            ev.calcular_metas(0, 30, 1.2)
        with self.assertRaises(ValueError):
            ev.classificar_tne(["desconhecido"])
        with self.assertRaises(ValueError):
            ev.planejar_progressao_enteral(1200, 1000, 30)


if __name__ == "__main__":
    unittest.main()
