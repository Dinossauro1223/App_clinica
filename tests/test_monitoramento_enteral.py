import unittest
import tempfile
from pathlib import Path

import monitoramento_enteral as me


class TestMonitoramentoEnteral(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "clinica.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_registra_evento_com_inicio_fim_volume_taxa_pausa(self):
        rid = me.salvar_administracao(
            self.db, 7, "2026-11-27 08:00", "2026-11-27 12:00",
            volume_prescrito_ml=640, volume_administrado_ml=600,
            taxa_ml_h=160, pausado_min=15, via_administracao="bomba",
        )
        itens = me.listar_administracoes(self.db, 7)
        self.assertEqual(itens[0]["id_administracao"], rid)
        self.assertEqual(itens[0]["volume_administrado_ml"], 600)
        self.assertEqual(itens[0]["pausado_min"], 15)

    def test_nao_inventa_fator_de_gotejamento(self):
        self.assertIsNone(me.gotas_por_minuto(120, None))
        self.assertAlmostEqual(me.gotas_por_minuto(120, 0.05), 40)

    def test_classifica_hgt_antes_durante_e_apos_fim(self):
        adm = {"inicio_em":"2026-11-27 08:00","fim_em":"2026-11-27 10:00"}
        self.assertEqual(me.classificar_hgt_em_relacao_a_administracao(
            "2026-11-27 07:40", adm)["classificacao"], "antes")
        self.assertEqual(me.classificar_hgt_em_relacao_a_administracao(
            "2026-11-27 09:00", adm)["classificacao"], "durante")
        self.assertEqual(me.classificar_hgt_em_relacao_a_administracao(
            "2026-11-27 11:00", adm)["classificacao"], "apos_fim")

    def test_resume_volume_real_do_dia_sem_ratear_evento_incompleto(self):
        me.salvar_administracao(
            self.db, 7, "2026-11-27 08:00", "2026-11-27 10:00",
            volume_prescrito_ml=500, volume_administrado_ml=450,
            via_administracao="bomba",
        )
        me.salvar_administracao(
            self.db, 7, "2026-11-27 23:30", "2026-11-28 01:00",
            volume_prescrito_ml=300, volume_administrado_ml=300,
            via_administracao="bomba",
        )
        me.salvar_administracao(
            self.db, 7, "2026-11-26 22:00", None,
            volume_prescrito_ml=200, volume_administrado_ml=None,
            via_administracao="bomba",
        )
        resumo = me.resumir_administracoes_dia(self.db, 7, "2026-11-27")
        self.assertEqual(resumo["volume_administrado_ml"], 450)
        self.assertEqual(resumo["volume_prescrito_ml"], 500)
        self.assertAlmostEqual(resumo["cobertura_volume_pct"], 90.0)
        self.assertFalse(resumo["volume_calculavel"])
        self.assertEqual(len(resumo["administracoes_pendentes"]), 2)

    def test_volume_real_sem_registro_nao_vira_zero(self):
        resumo = me.resumir_administracoes_dia(self.db, 7, "2026-11-27")
        self.assertEqual(resumo["volume_administrado_ml"], 0)
        self.assertEqual(resumo["administracoes_completas"], [])
        self.assertEqual(resumo["administracoes_pendentes"], [])
        self.assertFalse(resumo["volume_calculavel"])

    def test_rejeita_fim_antes_do_inicio(self):
        with self.assertRaises(ValueError):
            me.salvar_administracao(
                self.db, 7, "2026-11-27 12:00", "2026-11-27 11:00",
            )


if __name__ == "__main__":
    unittest.main()
