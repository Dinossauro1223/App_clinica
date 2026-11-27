"""Testes do registro HGT e sua persistência; somente dados sintéticos."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from datetime import datetime

import monitoramento_glicemico as mg


class TestMonitoramentoGlicemico(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "teste.db")

    def test_insere_lista_e_preserva_contexto(self):
        rid = mg.salvar_hgt(self.db, 7, 126, "2026-11-27 08:15", "Pós-prandial", "teste sintético")
        rows = mg.listar_hgt(self.db, 7)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], rid)
        self.assertEqual(rows[0][1], 126)
        self.assertEqual(rows[0][3], "Pós-prandial")
        self.assertEqual(rows[0][4], "teste sintético")

    def test_corrige_sem_criar_nova_medicao(self):
        rid = mg.salvar_hgt(self.db, 7, 126, "2026-11-27 08:15", "Jejum")
        mg.salvar_hgt(self.db, 7, 119, "2026-11-27 08:20", "Jejum", id_hgt=rid)
        rows = mg.listar_hgt(self.db, 7)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], 119)

    def test_inativacao_preserva_registro_no_banco(self):
        rid = mg.salvar_hgt(self.db, 7, 126, "2026-11-27 08:15", "Jejum")
        self.assertTrue(mg.inativar_hgt(self.db, 7, rid))
        self.assertEqual(mg.listar_hgt(self.db, 7), [])
        with closing(sqlite3.connect(self.db)) as conn, conn:
            self.assertEqual(conn.execute(
                "SELECT ativo FROM HGT_Registros WHERE id_hgt=?", (rid,)
            ).fetchone()[0], 0)

    def test_rejeita_valor_e_contexto_invalidos(self):
        with self.assertRaises(ValueError):
            mg.salvar_hgt(self.db, 7, 0, "2026-11-27 08:15", "Jejum")
        with self.assertRaises(ValueError):
            mg.salvar_hgt(self.db, 7, 100, "2026-11-27 08:15", "Depois")

    def test_separa_pacientes(self):
        mg.salvar_hgt(self.db, 7, 100, "2026-11-27 08:15", "Jejum")
        mg.salvar_hgt(self.db, 8, 140, "2026-11-27 08:15", "Jejum")
        self.assertEqual(len(mg.listar_hgt(self.db, 7)), 1)
        self.assertEqual(len(mg.listar_hgt(self.db, 8)), 1)

    def test_relaciona_hgt_a_oferta_real_com_composicao_e_horario(self):
        import json
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("CREATE TABLE Mapa_Registros (id_registro INTEGER PRIMARY KEY, data TEXT, id_paciente INTEGER)")
            conn.execute("""CREATE TABLE Mapa_Registro_Suplementos (
                id_registro INTEGER, nome TEXT, preparacoes_json TEXT, carb_100 REAL,
                fibra_g_100 REAL, tipo_fibra TEXT, unidade TEXT)""")
            conn.execute("INSERT INTO Mapa_Registros VALUES (1,'2026-11-27',7)")
            conn.execute("INSERT INTO Mapa_Registro_Suplementos VALUES (1,?,?,?,?,?,?)",(
                "Fórmula sintética",
                json.dumps([
                    {"refeicao":"Desjejum","horario":"08:00","dose":200,
                     "agua_adicionada_ml":100,"agua_separada_ml":50},
                    {"refeicao":"Lanche","dose":100}
                ]),
                12,3,"mista","ml"))
        eventos=mg.listar_ofertas_nutricionais(self.db,7)
        self.assertEqual(len(eventos),1)
        self.assertEqual(eventos[0]["instante"].strftime("%H:%M"),"08:00")
        self.assertEqual(eventos[0]["carboidratos_g"],24)
        self.assertEqual(eventos[0]["fibras_g"],6)
        self.assertEqual(eventos[0]["agua_misturada_ml"],100)

    def test_intervalo_temporal_assinado(self):
        self.assertEqual(
            mg.intervalo_relativo_hora("2026-11-27 10:00", "2026-11-27 08:00"), 120
        )
        self.assertEqual(
            mg.intervalo_relativo_hora("2026-11-27 07:30", "2026-11-27 08:00"), -30
        )


if __name__ == "__main__":
    unittest.main()
