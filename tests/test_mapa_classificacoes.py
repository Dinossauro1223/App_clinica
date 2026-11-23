"""Persistência das classificações NRS-2002 e avaliação nutricional no mapa."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import mapa_db as mdb
import nrs2002
import avaliacao_nutri


class TestMapaClassificacoes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "mapa.db")
        mdb.inicializar(self.db)
        self.setor = mdb.listar_setores(self.db)[0]["id_setor"]
        self.leito = mdb.criar_leito(self.db, self.setor, "T-01")

    def tearDown(self):
        self.tmp.cleanup()

    def test_migracao_adiciona_campos_de_classificacao(self):
        conn = sqlite3.connect(self.db)
        try:
            colunas = {r[1] for r in conn.execute("PRAGMA table_info(Mapa_Registros)")}
        finally:
            conn.close()
        self.assertTrue({"nrs2002_json", "nrs2002_classificacao",
                         "avaliacao_json", "avaliacao_classificacao"}.issubset(colunas))

    def test_classificacoes_sao_persistidas_com_o_registro(self):
        resultado_nrs = nrs2002.classificar(
            {"imc": True, "perda": False, "ingestao": False, "grave": False},
            estado=2, gravidade=1, idade=72,
        )
        resultado_av = avaliacao_nutri.calcular({
            "sexo": "Homem", "cor": "Branco", "idade": 72, "peso": 68,
            "altura": 170, "aj": 55, "pb": 28, "edema": "Ausente",
            "ascite": "Ausente", "amputacoes": {},
        })
        reg = {
            "data": "2026-11-22", "id_leito": self.leito, "nome_paciente": "Paciente teste",
            "idade_anos": 72, "sexo": "H", "peso_kg": 68, "altura_cm": 170,
            "nrs2002_json": json.dumps(resultado_nrs), "nrs2002_classificacao": resultado_nrs["rotulo"],
            "avaliacao_json": json.dumps(resultado_av), "avaliacao_classificacao": resultado_av["classe"],
        }
        mdb.salvar_registro(self.db, reg)
        conn = sqlite3.connect(self.db)
        try:
            row = conn.execute(
                "SELECT nrs2002_classificacao, avaliacao_classificacao FROM Mapa_Registros"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row[0], resultado_nrs["rotulo"])
        self.assertEqual(row[1], resultado_av["classe"])


if __name__ == "__main__":
    unittest.main()
