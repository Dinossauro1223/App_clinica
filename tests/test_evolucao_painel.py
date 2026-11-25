import unittest

import evolucao_nutricional as regras


class TestPainelEvolucao(unittest.TestCase):
    def registro(self, **progressao):
        dados = {
            "data_evolucao": "2026-11-20",
            "via": "Enteral",
            "metas": {"kcal_dia": 1800, "proteina_g_dia": 80},
            "dieta_enteral": {"nome": "Fórmula 1.5", "kcal_100": 150, "ptn_100": 6,
                              "volume_por_etapa_ml": 150, "etapas": 6},
            "oferta": {"volume_meta_ml": 1200},
            "progressao_enteral": {
                "solicitada": True, "autorizada": True, "volume_etapa_atual_ml": 150,
                "etapas": 6, "volume_meta_ml": 1200, "tolerancia": True, "restricao": False,
                "plano": {"passos": [
                    {"dia": 1, "volume_etapa_ml": 160},
                    {"dia": 2, "volume_etapa_ml": 170},
                    {"dia": 3, "volume_etapa_ml": 180},
                    {"dia": 4, "volume_etapa_ml": 190},
                    {"dia": 5, "volume_etapa_ml": 200},
                ]},
            },
        }
        dados["progressao_enteral"].update(progressao)
        return {"data": "2026-11-20", "via": "Enteral", "evolucao": dados}

    def test_progressao_autorizada_calcula_oferta_atual_e_incremento(self):
        resumo = regras.resumo_painel_evolucao(self.registro(), "2026-11-22")
        self.assertEqual(resumo["volume_inicial_ml"], 900)
        self.assertEqual(resumo["volume_atual_ml"], 1020)
        self.assertEqual(resumo["incremento_ml"], 120)
        self.assertAlmostEqual(resumo["energia_kcal"], 1530)
        self.assertAlmostEqual(resumo["adequacao_kcal_pct"], 85)
        self.assertEqual(resumo["deficit_kcal"], 270)
        self.assertEqual(resumo["volume_adicional_ml"], 180)
        self.assertTrue(resumo["evoluiu"])

    def test_sem_autorizacao_nao_aplica_passos_e_exibe_motivo(self):
        resumo = regras.resumo_painel_evolucao(
            self.registro(autorizada=False, plano={}), "2026-11-22")
        self.assertEqual(resumo["volume_atual_ml"], 900)
        self.assertFalse(resumo["evoluiu"])
        self.assertEqual(resumo["motivo_nao_evolucao"], "Aguardando autorização do nutricionista")

    def test_progressao_desativada_tem_motivo_especifico(self):
        resumo = regras.resumo_painel_evolucao(
            self.registro(solicitada=False, autorizada=False, plano={}), "2026-11-20")
        self.assertEqual(resumo["motivo_nao_evolucao"], "Progressão automática desativada")

    def test_vomitos_ou_diarreia_bloqueiam_progressao_automatica(self):
        self.assertFalse(regras.tolerancia_enteral_permite_progressao(["vômitos"], True))
        self.assertFalse(regras.tolerancia_enteral_permite_progressao(["diarreia"], True))
        self.assertFalse(regras.tolerancia_enteral_permite_progressao(["retrolimentação"], False))
        self.assertTrue(regras.tolerancia_enteral_permite_progressao(["retrolimentação"], True))
        self.assertTrue(regras.tolerancia_enteral_permite_progressao([], True))

    def test_progressao_oral_configuravel_exige_cinco_valores_crescentes(self):
        self.assertEqual(regras.validar_progressao_oral([60, 90, 120, 150, 180]),
                         [60, 90, 120, 150, 180])
        with self.assertRaises(ValueError):
            regras.validar_progressao_oral([70, 100, 100, 160, 200])
        with self.assertRaises(ValueError):
            regras.validar_progressao_oral([70, 100, 130, 160])

    def test_sem_bomba_apresenta_orientacao_sem_calcular_tempo(self):
        dados = {
            "antropometria": {"data": "25/11/2026", "idade_anos": 72, "altura_m": 1.65,
                              "altura_origem": "A", "peso_kg": 62, "peso_origem": "A",
                              "imc_class": "Eutrofia"},
            "metas": {"kcal_dia": 1800, "proteina_g_dia": 80, "kcal_kg": 29, "proteina_g_kg": 1.3},
            "via": "Enteral", "dva": False, "tne_motivos": [],
            "dieta_enteral": {"nome": "Fórmula 1.5", "volume_por_etapa_ml": 150,
                              "etapas": 6, "kcal_100": 150, "ptn_100": 6},
            "oferta": {"volume_total_ml": 900, "kcal_dia": 1350, "proteina_g_dia": 54,
                       "volume_meta_ml": 1200},
            "bomba": {"usa_bomba": False}, "orientacao_progressao": True,
        }
        texto = regras.gerar_evolucao(dados)
        self.assertIn("Orientação operacional", texto)
        self.assertNotIn("horas adicionais", texto)

    def test_com_bomba_apresenta_estimativa_sem_transformar_em_prescricao(self):
        dados = {
            "antropometria": {"data": "25/11/2026", "idade_anos": 72, "altura_m": 1.65,
                              "altura_origem": "A", "peso_kg": 62, "peso_origem": "A",
                              "imc_class": "Eutrofia"},
            "metas": {"kcal_dia": 1800, "proteina_g_dia": 80, "kcal_kg": 29, "proteina_g_kg": 1.3},
            "via": "Enteral", "dva": False, "tne_motivos": [],
            "dieta_enteral": {"nome": "Fórmula 1.5", "volume_por_etapa_ml": 150,
                              "etapas": 6, "kcal_100": 150, "ptn_100": 6},
            "oferta": {"volume_total_ml": 900, "kcal_dia": 1350, "proteina_g_dia": 54,
                       "volume_meta_ml": 1200},
            "bomba": {"usa_bomba": True, "taxa_estimativa_ml_h": 10},
            "orientacao_progressao": False,
        }
        texto = regras.gerar_evolucao(dados)
        self.assertIn("Estimativa de bomba", texto)
        self.assertIn("30.0 horas estimadas", texto)
        self.assertNotIn("Orientação operacional", texto)

    def test_paciente_oral_nao_entra_no_painel_enteral(self):
        self.assertIsNone(regras.resumo_painel_evolucao(
            {"via": "Oral", "evolucao": {"via": "Oral"}}, "2026-11-22"))


if __name__ == "__main__":
    unittest.main()
