"""Validação estrutural das tabelas LMS oficiais OMS incluídas no aplicativo."""
from pathlib import Path
import unittest

from pediatria_oms import TabelaReferenciaOMS, avaliar_indicador


RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO = RAIZ / "dados" / "oms_lms_pediatricos.csv"


class TestDadosOficiaisOMS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tabela = TabelaReferenciaOMS.de_csv(ARQUIVO)

    def test_tabelas_diarias_oms_2006_cobrem_nascimento_a_60_meses(self):
        for indicador in ("imc_idade", "peso_idade", "estatura_idade"):
            curva = self.tabela.curva(indicador, "H", "oms_2006")
            # WHO Anthro 1.1.0 disponibiliza 0..1826 dias; a partir de 60
            # meses completos a referência passa para OMS 2007.
            self.assertEqual(len(curva), 1827)
            self.assertEqual(curva[0]["idade"], 0)
            self.assertEqual(curva[-1]["idade"], 1826)

    def test_tabelas_oms_2007_incluem_ancoras_de_interpolacao(self):
        bmi = self.tabela.curva("imc_idade", "M", "oms_2007")
        altura = self.tabela.curva("estatura_idade", "H", "oms_2007")
        peso = self.tabela.curva("peso_idade", "M", "oms_2007")
        self.assertEqual((bmi[0]["idade"], bmi[-1]["idade"]), (60, 228))
        self.assertEqual((altura[0]["idade"], altura[-1]["idade"]), (60, 228))
        self.assertEqual((peso[0]["idade"], peso[-1]["idade"]), (60, 120))
        # As linhas superiores permanecem na curva bruta para interpolação;
        # a camada de visualização as filtra para não exibi-las clinicamente.
        self.assertIn(229, self.tabela._dados_meses[("imc_idade", "oms_2007", "M")])
        self.assertIn(229, self.tabela._dados_meses[("estatura_idade", "oms_2007", "H")])
        self.assertIn(121, self.tabela._dados_meses[("peso_idade", "oms_2007", "M")])

    def test_interpolacao_oficial_entre_meses_retorna_escore_z_zero_na_mediana(self):
        curva = self.tabela.curva("imc_idade", "H", "oms_2007")
        m60 = next(p["z_zero"] for p in curva if p["idade"] == 60)
        m61 = next(p["z_zero"] for p in curva if p["idade"] == 61)
        resultado = self.tabela.calcular("imc_idade", "H", 60.5, (m60 + m61) / 2,
                                         idade_meses_completos=60)
        self.assertAlmostEqual(resultado, 0.0, places=6)

    def test_peso_por_idade_fica_fora_da_faixa_depois_de_10_anos(self):
        resultado = avaliar_indicador("peso_idade", 35.0, "H", 121, self.tabela,
                                      idade_meses_completos=121)
        self.assertEqual(resultado["status"], "fora_faixa")
        self.assertIsNone(resultado["escore_z"])

    def test_curvas_preservam_as_duas_referencias_e_os_dois_sexos(self):
        for referencia in ("oms_2006", "oms_2007"):
            for sexo in ("H", "M"):
                curva = self.tabela.curva("imc_idade", sexo, referencia)
                self.assertTrue(curva)
                self.assertTrue(all(p["z_menos3"] < p["z_zero"] < p["z_mais3"] for p in curva))


if __name__ == "__main__":
    unittest.main()
