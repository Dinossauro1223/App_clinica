"""Testes de persistência e integração da avaliação OMS pediátrica no prontuário."""
import json
import os
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import mapa_db as mdb
import main as app_main
import pediatria_oms as oms



class _LabelFalso:
    def __init__(self):
        self.text = ""

    def configure(self, **kwargs):
        self.text = kwargs.get("text", self.text)


class TestIntegracaoOMSNaConsultaAmbulatorial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raiz = Path(__file__).resolve().parents[1]
        cls.tabela = oms.TabelaReferenciaOMS.de_csv(raiz / "dados" / "oms_lms_pediatricos.csv")

    def _consulta(self, nascimento, sexo="Masculino"):
        fake = SimpleNamespace(
            paciente_atual_nasc=nascimento,
            paciente_atual_sexo=sexo,
            _tabela_oms_pediatria=self.tabela,
            lbl_oms_pediatria=_LabelFalso(),
            _resultado_pediatria_consulta={},
        )
        fake._idade_exata_oms_consulta = lambda: app_main.AppClinica._idade_exata_oms_consulta(fake)
        fake._tabela_referencia_oms = lambda: self.tabela
        return fake

    def test_consulta_calcula_oms_2006_com_idade_exata_em_dias(self):
        fake = self._consulta("01/01/2024")
        resultado = app_main.AppClinica._atualizar_oms_pediatria_consulta(fake, 15.0, 14.0, 95.0)
        self.assertEqual(resultado["resultados"]["imc_idade"]["status"], "calculado")
        self.assertEqual(resultado["resultados"]["imc_idade"]["referencia"], "oms_2006")
        self.assertIsNotNone(resultado["idade_dias"])
        self.assertIn("Referência OMS 2006", fake.lbl_oms_pediatria.text)

    def test_consulta_calcula_oms_2007_e_respeita_limite_peso_10_anos(self):
        fake = self._consulta("15/02/2015")
        resultado = app_main.AppClinica._atualizar_oms_pediatria_consulta(fake, 19.0, 40.0, 145.0)
        self.assertEqual(resultado["resultados"]["imc_idade"]["status"], "calculado")
        self.assertEqual(resultado["resultados"]["imc_idade"]["referencia"], "oms_2007")
        self.assertEqual(resultado["resultados"]["peso_idade"]["status"], "fora_faixa")
        self.assertIn("Peso/idade: não aplicável", fake.lbl_oms_pediatria.text)

    def test_consulta_sem_data_de_nascimento_fica_pendente(self):
        fake = self._consulta("")
        resultado = app_main.AppClinica._atualizar_oms_pediatria_consulta(fake, 18.0, 30.0, 130.0)
        self.assertEqual(resultado["status"], "pendente")
        self.assertIn("Data de nascimento ausente", fake.lbl_oms_pediatria.text)

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
