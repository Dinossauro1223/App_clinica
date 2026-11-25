"""Testes de persistência e integração da avaliação OMS pediátrica no prontuário."""
import json
import os
import sqlite3
from contextlib import closing
import tempfile
import unittest
from datetime import date
from pathlib import Path

import mapa_db as mdb
import pediatria_oms as oms



class TestIntegracaoOMSNaConsultaAmbulatorial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raiz = Path(__file__).resolve().parents[1]
        cls.tabela = oms.TabelaReferenciaOMS.de_csv(raiz / "dados" / "oms_lms_pediatricos.csv")

    def test_consulta_calcula_oms_2006_com_idade_exata_em_dias(self):
        resultado = oms.avaliar_paciente("H", 14.0, 95.0, "01/01/2024",
                                         date.today(), self.tabela, imc=15.0)
        self.assertEqual(resultado["resultados"]["imc_idade"]["status"], "calculado")
        self.assertEqual(resultado["resultados"]["imc_idade"]["referencia"], "oms_2006")
        self.assertIsNotNone(resultado["idade_dias"])

    def test_consulta_calcula_oms_2007_e_respeita_limite_peso_10_anos(self):
        resultado = oms.avaliar_paciente("H", 40.0, 145.0, "15/02/2015",
                                         date.today(), self.tabela, imc=19.0)
        self.assertEqual(resultado["resultados"]["imc_idade"]["status"], "calculado")
        self.assertEqual(resultado["resultados"]["imc_idade"]["referencia"], "oms_2007")
        self.assertEqual(resultado["resultados"]["peso_idade"]["status"], "fora_faixa")

    def test_consulta_sem_data_de_nascimento_fica_pendente(self):
        resultado = oms.avaliar_paciente("H", 30.0, 130.0, "",
                                         date.today(), self.tabela, imc=18.0)
        self.assertEqual(resultado["status"], "pendente")
        self.assertIn("Data de nascimento ausente", resultado["aviso"])


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
        with closing(sqlite3.connect(self.db)) as conn:
            colunas = {r[1] for r in conn.execute("PRAGMA table_info(Mapa_Registros)")}
        self.assertIn("pediatria_oms_json", colunas)

    def test_obter_paciente_retorna_data_de_nascimento(self):
        with closing(sqlite3.connect(self.db)) as conn:
            cur = conn.execute(
                "INSERT INTO Pacientes (nome, data_nascimento, sexo) VALUES (?, ?, ?)",
                ("Paciente teste", "15/02/2015", "Masculino"))
            id_paciente = cur.lastrowid
            conn.commit()
        paciente = mdb.obter_paciente(self.db, id_paciente)
        self.assertEqual(paciente["data_nascimento"], "15/02/2015")
        self.assertEqual(paciente["sexo"], "Masculino")


if __name__ == "__main__":
    unittest.main()
