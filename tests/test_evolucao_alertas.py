import unittest

import evolucao_nutricional as ev


class TestAlertasEvolucaoMapa(unittest.TestCase):
    def _linha(self, nome="Paciente Teste", *, via="Enteral", status="fechada",
               autorizada=True, solicitada=True, volume_inicial_etapa=150,
               passos=None, volume_meta=1200):
        progressao = {
            "solicitada": solicitada,
            "autorizada": autorizada,
            "volume_meta_ml": volume_meta,
            "plano": {"ativa": autorizada, "passos": passos or [
                {"dia": 1, "volume_total_ml": 935},
                {"dia": 2, "volume_total_ml": 970},
            ]},
        }
        return {
            "leito": {"codigo": "CM-01"},
            "registro": {
                "id_leito": 1, "data": "2026-11-24", "via": via,
                "nome_paciente": nome,
                "evolucao": {
                    "status_evolucao": status,
                    "fechada": status == "fechada",
                    "data_evolucao": "2026-11-24",
                    "metas": {"kcal_dia": 1800, "proteina_g_dia": 90},
                    "dieta_enteral": {
                        "nome": "Fórmula sintética",
                        "volume_por_etapa_ml": volume_inicial_etapa,
                        "etapas": 6, "kcal_100": 150, "ptn_100": 7.5,
                    },
                    "progressao_enteral": progressao,
                    "oferta": {
                        "volume_total_ml": 900,
                        "kcal_100ml": 150,
                        "proteina_100ml": 7.5,
                        "volume_meta_ml": volume_meta,
                    },
                },
            },
        }

    def test_progressao_autorizada_aparece_com_incremento_e_adequacao(self):
        grupos = ev.gerar_alertas_mapa(
            [self._linha()], data_referencia="2026-11-25"
        )
        self.assertEqual(len(grupos["evoluiram"]), 1)
        alerta = grupos["evoluiram"][0]
        self.assertEqual(alerta["incremento_ml"], 35)
        self.assertEqual(alerta["volume_atual_ml"], 935)
        self.assertAlmostEqual(alerta["adequacao_kcal_pct"], 77.9166667)
        self.assertAlmostEqual(alerta["adequacao_proteina_pct"], 77.9166667)
        self.assertEqual(len(grupos["abaixo_meta"]), 1)
        self.assertAlmostEqual(grupos["abaixo_meta"][0]["volume_adicional_ml"], 265)

    def test_progressao_nao_autorizada_nao_e_contada_como_evolucao(self):
        linha = self._linha(autorizada=False, solicitada=True)
        grupos = ev.gerar_alertas_mapa([linha], data_referencia="2026-11-25")
        self.assertEqual(grupos["evoluiram"], [])
        self.assertEqual(len(grupos["nao_evoluiram"]), 1)
        self.assertIn("autorização", grupos["nao_evoluiram"][0]["motivo"])
        self.assertEqual(len(grupos["abaixo_meta"]), 1)

    def test_rascunho_nao_gera_alerta_de_adequacao_como_evolucao_fechada(self):
        linha = self._linha(status="rascunho")
        grupos = ev.gerar_alertas_mapa([linha], data_referencia="2026-11-25")
        self.assertEqual(grupos["evoluiram"], [])
        self.assertEqual(len(grupos["nao_evoluiram"]), 1)
        self.assertEqual(grupos["nao_evoluiram"][0]["motivo"], "evolução ainda não fechada")
        self.assertEqual(grupos["abaixo_meta"], [])

    def test_paciente_em_via_oral_nao_entra_nos_alertas_enterais(self):
        grupos = ev.gerar_alertas_mapa(
            [self._linha(via="Oral")], data_referencia="2026-11-25"
        )
        self.assertEqual(grupos, {
            "evoluiram": [], "nao_evoluiram": [], "abaixo_meta": []
        })


if __name__ == "__main__":
    unittest.main()
