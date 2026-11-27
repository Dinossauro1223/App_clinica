import unittest
from contextlib import closing

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
            {"medido_em": "2026-11-26 07:00", "peso_kg": 70, "peso_origem": "R"},
            {"medido_em": "2026-11-27 07:00", "peso_kg": 68.9, "peso_origem": "R"},
        ], idade_anos=69)
        self.assertEqual(resultado["alertas"][0]["tipo"], "variacao_aguda_24h")
        self.assertEqual(resultado["alertas"][0]["intervalo_horas"], 24.0)
        self.assertIn("balanço hídrico", resultado["alertas"][0]["texto"])

    def test_perda_ponderal_em_seis_meses_marca_criterio_fenotipico_glim(self):
        resultado = pn.analisar_progressao_peso([
            {"data": "2026-05-05", "peso_kg": 70, "peso_origem": "R"},
            {"data": "2026-11-01", "peso_kg": 66, "peso_origem": "R"},
        ], idade_anos=69)
        self.assertTrue(any("GLIM" in x for x in resultado["criterios_fenotipicos"]))
        self.assertFalse(resultado["diagnostico_automatico"])
        self.assertIn("etiológico", resultado["nota"])

    def test_imc_baixo_para_idade_e_criterio_fenotipico_sem_diagnostico(self):
        resultado = pn.analisar_progressao_peso([
            {"data": "2026-11-27", "peso_kg": 50, "peso_origem": "R", "altura_cm": 167, "altura_origem": "R"}
        ], idade_anos=69)
        self.assertIsNotNone(resultado["criterio_bmi_glim"])
        self.assertFalse(resultado["diagnostico_automatico"])


    def test_faixa_de_uma_semana_distingue_moderada_de_elevada(self):
        moderada = pn.analisar_progressao_peso([
            {"data": "2026-11-20", "peso_kg": 70, "peso_origem": "R"},
            {"data": "2026-11-27", "peso_kg": 69, "peso_origem": "R"},
        ])
        elevada = pn.analisar_progressao_peso([
            {"data": "2026-11-20", "peso_kg": 70, "peso_origem": "R"},
            {"data": "2026-11-27", "peso_kg": 68.5, "peso_origem": "R"},
        ])
        self.assertIn("moderada", moderada["comparacoes"][0]["faixa"])
        self.assertIn("elevada", elevada["comparacoes"][0]["faixa"])

    def test_le_horario_real_salvo_no_mapa(self):
        import os
        import sqlite3
        import tempfile

        with tempfile.TemporaryDirectory() as pasta:
            db = os.path.join(pasta, "mapa.db")
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute("""CREATE TABLE Mapa_Registros (
                    id_registro INTEGER PRIMARY KEY, data TEXT, id_paciente INTEGER,
                    peso_kg REAL, peso_origem TEXT, peso_metodo TEXT, peso_medido_em TEXT,
                    altura_cm REAL, altura_origem TEXT, pp_cm REAL, pb_cm REAL, aj_cm REAL,
                    imc REAL, avaliacao_json TEXT, atualizado_em TEXT
                )""")
                conn.executemany(
                    """INSERT INTO Mapa_Registros
                    (id_registro,data,id_paciente,peso_kg,peso_origem,peso_medido_em,atualizado_em)
                    VALUES (?,?,?,?,?,?,?)""",
                    [
                        (1,"2026-11-26",7,70,"R","2026-11-26 07:00","2026-11-26 07:05"),
                        (2,"2026-11-27",7,68.8,"R","2026-11-27 07:00","2026-11-27 07:05"),
                    ],
                )
            historico = pn.listar_pesos_historicos(db, 7)
            resultado = pn.analisar_progressao_peso(historico, idade_anos=69)
            self.assertEqual(resultado["alertas"][0]["tipo"], "variacao_aguda_24h")


    def test_glim_considera_perda_acima_de_dez_por_cento_em_periodo_maior_que_seis_meses(self):
        resultado = pn.analisar_progressao_peso([
            {"data": "2026-04-01", "peso_kg": 70, "peso_origem": "R"},
            {"data": "2026-11-01", "peso_kg": 62, "peso_origem": "R"},
        ], idade_anos=69)
        self.assertTrue(any("limiar quantitativo GLIM" in x for x in resultado["criterios_fenotipicos"]))

    def test_faixas_adultas_nao_sao_aplicadas_a_menores(self):
        resultado = pn.analisar_progressao_peso([
            {"data": "2026-11-20", "peso_kg": 40, "peso_origem": "R"},
            {"data": "2026-11-27", "peso_kg": 38, "peso_origem": "R"},
        ], idade_anos=12)
        self.assertEqual(resultado["comparacoes"], [])
        self.assertEqual(resultado["criterios_fenotipicos"], [])
        self.assertIn("menores de 18 anos", resultado["nota"])

    def test_peso_estimado_nao_recebe_classificacao_aspen(self):
        resultado = pn.analisar_progressao_peso([
            {"data": "2026-11-20", "peso_kg": 70, "peso_origem": "E"},
            {"data": "2026-11-27", "peso_kg": 68, "peso_origem": "E"},
        ], idade_anos=69)
        self.assertIn("estimado", resultado["comparacoes"][0]["faixa"])
        self.assertEqual(resultado["criterios_fenotipicos"], [])

    def test_sem_historico_nao_cria_valor_zero(self):
        resultado = pn.analisar_progressao_peso([])
        self.assertEqual(resultado["status"], "sem_dados")
        self.assertEqual(resultado["comparacoes"], [])


if __name__ == "__main__":
    unittest.main()
