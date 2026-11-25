"""Testes de persistência e integração da avaliação OMS pediátrica no prontuário."""
import json
import os
import sqlite3
import tempfile
import unittest

import mapa_db as mdb


class TestClassificacaoPediatricaNoRegistro(unittest.TestCase):
    def test_completar_registro_usa_classificacao_oms_salva(self):
        reg = {
            "idade_anos": 8, "idade_meses": 2, "peso_kg": 24, "altura_cm": 125,
            "pediatria_oms_json": json.dumps({
                "resultados": {"imc_idade": {
                    "status": "calculado", "escore_z": 0.4, "classificacao": "Eutrofia"
                }}
            }),
        }
        mdb.completar_registro(reg)
        self.assertEqual(reg["imc_class"], "Eutrofia")

    def test_pediatria_pendente_nao_cai_em_classificacao_adulta_de_imc(self):
        reg = {
            "idade_anos": 8, "peso_kg": 24, "altura_cm": 125,
            "pediatria_oms_json": json.dumps({
                "resultados": {"imc_idade": {"status": "pendente", "classificacao": None}}
            }),
        }
        mdb.completar_registro(reg)
        self.assertEqual(reg["imc_class"], "OMS pendente")

    def test_adulto_mantem_classificacao_adulta(self):
        reg = {
            "idade_anos": 25, "peso_kg": 70, "altura_cm": 175,
            "pediatria_oms_json": "{}",
        }
        mdb.completar_registro(reg)
        self.assertNotEqual(reg["imc_class"], "OMS pendente")


class TestPersistenciaDaAvaliacaoOMS(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        mdb.inicializar(self.db)

    def tearDown(self):
        if os.path.exists(self.db):
            os.remove(self.db)

    def test_migracao_adiciona_coluna_pediatria_oms_json(self):
        with sqlite3.connect(self.db) as conn:
            colunas = {r[1] for r in conn.execute("PRAGMA table_info(Mapa_Registros)")}
        self.assertIn("pediatria_oms_json", colunas)

    def test_obter_paciente_retorna_data_de_nascimento(self):
        with sqlite3.connect(self.db) as conn:
            cur = conn.execute(
                "INSERT INTO Pacientes (nome, data_nascimento, sexo) VALUES (?, ?, ?)",
                ("Paciente teste", "15/02/2015", "Masculino"))
            id_paciente = cur.lastrowid
        paciente = mdb.obter_paciente(self.db, id_paciente)
        self.assertEqual(paciente["data_nascimento"], "15/02/2015")
        self.assertEqual(paciente["sexo"], "Masculino")


if __name__ == "__main__":
    unittest.main()
