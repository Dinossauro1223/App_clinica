import unittest

import progressao_nutricional as pn


class TestProgressaoNutricional(unittest.TestCase):
    def test_variacao_maior_ou_igual_um_kg_em_datas_consecutivas_nao_finge_horario(self):
        resultado = pn.analisar_progressao_peso([
            {"data": "2026-11-26", "peso_kg": 70, "peso_origem": "R"},
            {"data": "2026-11-27", "peso_kg": 68.8, "peso_origem": "R"},
        ], idade_anos=69)
        alerta = resultado["alertas"][0]
        self.assertEqual(alerta["tipo"], "variacao_em_dias_consecutivos")
        self.assertIsNone(alerta["intervalo_horas"])
        self.assertIn("não está registrado", alerta["texto"])
        self.assertIn("Não diagnostica desnutrição", alerta["texto"])

    def test_variacao_com_horarios_reais_em_24h_sinaliza_balanco_hidrico(self):
        resultado = pn.analisar_progressao_peso([
            {"medido_em": "2026-11-26 07:00", "peso_kg": 70},
            {"medido_em": "2026-11-27 07:00", "peso_kg": 68.9},
        ])
        self.assertEqual(resultado["alertas"][0]["tipo"], "variacao_aguda_24h")
        self.assertEqual(resultado["alertas"][0]["intervalo_horas"], 24.0)
        self.assertIn("balanço hídrico", resultado["alertas"][0]["texto"])

    def test_perda_ponderal_em_seis_meses_marca_criterio_fenotipico_glim(self):
        resultado = pn.analisar_progressao_peso([
            {"data": "2026-05-01", "peso_kg": 70},
            {"data": "2026-11-01", "peso_kg": 66},
        ], idade_anos=69)
        self.assertTrue(any("GLIM" in x for x in resultado["criterios_fenotipicos"]))
        self.assertFalse(resultado["diagnostico_automatico"])
        self.assertIn("etiológico", resultado["nota"])

    def test_imc_baixo_para_idade_e_criterio_fenotipico_sem_diagnostico(self):
        resultado = pn.analisar_progressao_peso([
            {"data": "2026-11-27", "peso_kg": 50, "altura_cm": 167}
        ], idade_anos=69)
        self.assertIsNotNone(resultado["criterio_bmi_glim"])
        self.assertFalse(resultado["diagnostico_automatico"])

    def test_sem_historico_nao_cria_valor_zero(self):
        resultado = pn.analisar_progressao_peso([])
        self.assertEqual(resultado["status"], "sem_dados")
        self.assertEqual(resultado["comparacoes"], [])


if __name__ == "__main__":
    unittest.main()
