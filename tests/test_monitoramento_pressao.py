import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime

import monitoramento_pressao as mp
import monitoramento_glicemico as mg
import db_migracoes as mig


class TestMonitoramentoPressao(unittest.TestCase):
    def setUp(self):
        fd,self.db=tempfile.mkstemp(suffix=".db"); os.close(fd)
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("""CREATE TABLE HGT_Registros (
                id_hgt INTEGER PRIMARY KEY, id_paciente INTEGER, valor_mg_dl REAL, medido_em TEXT,
                contexto TEXT, observacoes TEXT, criado_em TEXT, atualizado_em TEXT,
                ativo INTEGER DEFAULT 1)""")
            mg.criar_tabela(c)
            mp.criar_tabelas(c)

    def tearDown(self):
        os.unlink(self.db)

    def test_migracoes_hgt_e_pressao_criam_esquema_integrado(self):
        with sqlite3.connect(":memory:") as conn:
            mig.MIGRACOES[9].up[0](conn)
            mig.MIGRACOES[10].up[0](conn)
            tabelas={r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn("HGT_Registros",tabelas)
            self.assertIn("PA_Registros",tabelas)
            self.assertIn("Suplemento_Substituicoes",tabelas)
            colunas={r[1] for r in conn.execute("PRAGMA table_info(Suplemento_Substituicoes)")}
            self.assertIn("snapshot_anterior_json",colunas)
            self.assertIn("snapshot_novo_json",colunas)
            self.assertIn("autor",{r[1] for r in conn.execute("PRAGMA table_info(HGT_Registros)")})

    def test_salvar_listar_e_inativar_pressao(self):
        rid=mp.salvar_pressao(self.db,7,130,80,"2026-11-20 08:00",posicao="Sentado",braco="Esquerdo")
        rows=mp.listar_pressao(self.db,7)
        self.assertEqual((rows[0][1],rows[0][2]),(130,80))
        self.assertTrue(mp.inativar_pressao(self.db,7,rid))
        self.assertEqual(mp.listar_pressao(self.db,7),[])

    def test_rejeita_pressao_incoerente(self):
        with self.assertRaises(ValueError):
            mp.salvar_pressao(self.db,7,80,120,"2026-11-20 08:00")

    def test_comparacao_tres_dias_separa_janelas_e_calcula_medias(self):
        for valor,data in [(100,"2026-11-18 08:00"),(110,"2026-11-19 08:00"),
                           (150,"2026-11-20 08:00"),(160,"2026-11-21 08:00")]:
            mg.salvar_hgt(self.db,7,valor,data,"Aleatória")
        mp.salvar_pressao(self.db,7,120,80,"2026-11-19 08:00")
        mp.salvar_pressao(self.db,7,140,90,"2026-11-21 08:00")
        res=mp.comparar_tres_dias(self.db,7,"2026-11-20 00:00")
        self.assertEqual(res["periodo_antes"]["hgt"]["media"],105)
        self.assertEqual(res["periodo_depois"]["hgt"]["media"],155)
        self.assertEqual(res["periodo_antes"]["sistolica"]["media"],120)
        self.assertEqual(res["periodo_depois"]["diastolica"]["media"],90)

    def test_paciente_isolado_e_dado_ausente_nao_vira_zero(self):
        res=mp.comparar_tres_dias(self.db,99,"2026-11-20 00:00")
        self.assertIsNone(res["periodo_antes"]["hgt"]["media"])
        self.assertEqual(res["periodo_antes"]["hgt"]["afericoes"],0)

    def test_substituicao_guarda_ids_e_snapshot_e_pode_ser_listada(self):
        rid=mp.registrar_substituicao(
            self.db,7,"2026-11-20 10:00","Fórmula A","Fórmula B",
            id_suplemento_anterior=11,id_suplemento_novo=12,
            snapshot_anterior={"kcal_100":100},snapshot_novo={"kcal_100":150})
        eventos=mp.listar_substituicoes(self.db,7)
        self.assertEqual(eventos[0][0],rid)
        self.assertEqual((eventos[0][4],eventos[0][5]),(11,12))
        self.assertEqual(__import__("json").loads(eventos[0][6]),{"kcal_100":100})
        self.assertEqual(__import__("json").loads(eventos[0][7]),{"kcal_100":150})

    def test_cobertura_dos_periodos_e_calculada_em_blocos_de_24_horas(self):
        for valor,data in [(100,"2026-11-17 13:00"),(110,"2026-11-18 13:00"),
                           (120,"2026-11-19 13:00"),(130,"2026-11-20 13:00"),
                           (140,"2026-11-21 13:00"),(150,"2026-11-22 13:00")]:
            mg.salvar_hgt(self.db,7,valor,data,"Aleatória")
        res=mp.comparar_tres_dias(self.db,7,"2026-11-20 13:00")
        self.assertEqual(res["periodo_antes"]["hgt"]["dias_com_dados"],3)
        self.assertFalse(res["periodo_antes"]["hgt"]["amostra_insuficiente"])
        self.assertEqual(res["periodo_depois"]["hgt"]["dias_com_dados"],3)


if __name__ == "__main__":
    unittest.main()
