import os
import sqlite3
import tempfile
import unittest
from datetime import datetime

import monitoramento_pressao as mp
import monitoramento_glicemico as mg


class TestMonitoramentoPressao(unittest.TestCase):
    def setUp(self):
        fd,self.db=tempfile.mkstemp(suffix=".db"); os.close(fd)
        with sqlite3.connect(self.db) as c:
            c.execute("""CREATE TABLE HGT_Registros (
                id_hgt INTEGER PRIMARY KEY, id_paciente INTEGER, valor_mg_dl REAL, medido_em TEXT,
                contexto TEXT, observacoes TEXT, criado_em TEXT, atualizado_em TEXT,
                ativo INTEGER DEFAULT 1)""")
            mg.criar_tabela(c)
            mp.criar_tabelas(c)

    def tearDown(self):
        os.unlink(self.db)

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


if __name__ == "__main__":
    unittest.main()
