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


    def test_peso_corrigido_rastreavel(self):
        r = ev.calcular_peso_corrigido(70, liquidos_a_retirar_kg=6, percentual_amputacao=5)
        self.assertAlmostEqual(r["peso_nutricional_kg"], 67.368421, places=5)
        self.assertTrue(r["corrigido"])
        with self.assertRaises(ValueError):
            ev.calcular_peso_corrigido(5, liquidos_a_retirar_kg=6, percentual_amputacao=0)

    def test_oferta_enteral_calcula_energia_e_proteina_da_ficha(self):
        r = ev.calcular_oferta_enteral(180, 6, 150, 7.5)
        self.assertEqual(r["volume_total_ml"], 1080)
        self.assertEqual(r["kcal_dia"], 1620)
        self.assertEqual(r["proteina_g_dia"], 81)

    def test_progressao_por_etapa_respeita_meta_e_autorizacao(self):
        sem_autorizacao = ev.planejar_progressao_por_etapa(150, 6, 200, autorizada=False)
        self.assertFalse(sem_autorizacao["ativa"])
        self.assertEqual(sem_autorizacao["motivo"], "aguarda autorização")
        plano = ev.planejar_progressao_por_etapa(150, 6, 200, autorizada=True)
        self.assertEqual([p["volume_etapa_ml"] for p in plano["passos"]], [160, 170, 180, 190, 200])
        self.assertEqual(plano["passos"][0]["incremento_total_ml"], 60)
        self.assertEqual(plano["passos"][-1]["volume_total_ml"], 1200)
        self.assertEqual(plano["dias_estimados"], 5)
        self.assertFalse(plano["atinge_meta_no_prazo"])

    def test_bomba_apenas_com_bomba(self):
        self.assertIsNone(ev.aviso_bomba(900, 1200, False))
        aviso = ev.aviso_bomba(900, 1200, True)
        self.assertEqual(aviso["volume_adicional_ml"], 300)
        self.assertEqual(aviso["horas_estimadas"], 30)
        self.assertIn("estimadas", aviso["texto"])

    def test_antropometria_decimal_ptbr_e_peso_corrigido(self):
        texto = ev.formatar_antropometria({
            "data": "25/11/2026", "idade_anos": 72, "altura_m": 1.65, "altura_origem": "R",
            "peso_kg": 62, "peso_origem": "R", "peso_corrigido": True, "imc_class": "Eutrofia"})
        self.assertIn("ALT: 1,65 m (A)", texto)
        self.assertIn("PESO: 62 kg (A; corrigido)", texto)
        self.assertIn("IMC: 22,8 kg/m²", texto)
        self.assertNotIn("AJ:", texto)

    def test_geracao_enteral_com_dieta_e_sem_tempo_de_bomba_sem_bomba(self):
        dados = {
            "antropometria": {"data": "25/11/2026", "idade_anos": 72, "altura_m": 1.65,
                "altura_origem": "A", "peso_kg": 62, "peso_origem": "A", "imc_class": "Eutrofia"},
            "via": "Enteral", "metas": ev.calcular_metas(62, 30, 1.2),
            "oferta": {"kcal_dia": 1620, "proteina_g_dia": 68, "volume_total_ml": 1080, "volume_meta_ml": 1240},
            "dieta_enteral": {"nome": "Fórmula sintética", "volume_por_etapa_ml": 180, "etapas": 6},
            "tne_motivos": [], "bomba": {"usa_bomba": False}}
        texto = ev.gerar_evolucao(dados)
        self.assertIn("Fórmula sintética — 180 mL/etapa × 6 etapas, totalizando 1080 mL/dia", texto)
        self.assertIn("Adequação da meta", texto)
        self.assertNotIn("horas adicionais", texto)

    def test_proxima_antropometria_reusa_periodicidade_nrs_configurada(self):
        self.assertEqual(ev.calcular_proxima_antropometria("25/11/2026", "risco",
            {"risco": 7, "sem_risco": 30, "alto_risco": 7, "triagem_negativa": 30}), "02/12/2026")


if __name__ == "__main__":
    unittest.main()
