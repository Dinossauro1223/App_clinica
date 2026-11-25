"""Testes TDD de precisão para o motor LMS pediátrico.

Os números LMS abaixo são sintéticos e usados exclusivamente para verificar
interpolação e correção das caudas; não são referências antropométricas.
"""
import unittest
from pathlib import Path

from pediatria_oms import (calcular_escore_z, calcular_idade_dias, interpolar_lms,
                            TabelaReferenciaOMS, avaliar_indicador)


class TestIdadeExataEmDias(unittest.TestCase):
    def test_calcula_dias_corridos_sem_arredondar_para_mes_completo(self):
        self.assertEqual(calcular_idade_dias("2020-01-01", "2020-01-31"), 30)
        self.assertEqual(calcular_idade_dias("2020-02-28", "2020-03-01"), 2)

    def test_rejeita_data_de_referencia_anterior_ao_nascimento(self):
        with self.assertRaises(ValueError):
            calcular_idade_dias("2020-02-01", "2020-01-31")


class TestCorrecaoCaudasLMS(unittest.TestCase):
    def test_corrige_escore_acima_de_tres_desvios(self):
        # LMS sintético: z bruto = 5; correção WHO de cauda = 6.2.
        self.assertAlmostEqual(calcular_escore_z(20.0, -1.0, 10.0, 0.1), 6.2, places=6)

    def test_corrige_escore_abaixo_de_menos_tres_desvios(self):
        # LMS sintético: z bruto = -10; correção WHO de cauda = -7.2.
        self.assertAlmostEqual(calcular_escore_z(5.0, -1.0, 10.0, 0.1), -7.2, places=6)

    def test_preserva_escore_dentro_de_menos_tres_a_mais_tres(self):
        self.assertAlmostEqual(calcular_escore_z(12.0, 1.0, 10.0, 0.1), 2.0)


class TestInterpolacaoLMS(unittest.TestCase):
    def test_interpola_l_m_s_linearmente_entre_idades(self):
        tabela = {0: (1.0, 10.0, 0.1), 10: (3.0, 20.0, 0.3)}
        self.assertEqual(interpolar_lms(5, tabela), (2.0, 15.0, 0.2))

    def test_retorna_parametros_exatos_quando_idade_existe(self):
        tabela = {0: (1.0, 10.0, 0.1), 10: (3.0, 20.0, 0.3)}
        self.assertEqual(interpolar_lms(10, tabela), (3.0, 20.0, 0.3))

    def test_nao_extrapola_fora_das_idades_disponiveis(self):
        tabela = {0: (1.0, 10.0, 0.1), 10: (3.0, 20.0, 0.3)}
        self.assertIsNone(interpolar_lms(-1, tabela))
        self.assertIsNone(interpolar_lms(11, tabela))



class TestLMSPorDiasEMeses(unittest.TestCase):
    def test_oms_2006_usa_idade_exata_em_dias(self):
        tabela = TabelaReferenciaOMS.de_linhas([
            {"indicador": "imc_idade", "referencia": "oms_2006", "sexo": "H",
             "idade_dias": "30", "L": "1", "M": "10", "S": "0.1"},
            {"indicador": "imc_idade", "referencia": "oms_2006", "sexo": "H",
             "idade_dias": "31", "L": "1", "M": "11", "S": "0.1"},
        ])
        self.assertAlmostEqual(tabela.calcular("imc_idade", "H", 1, 13.2, idade_dias=31), 2.0)
        self.assertIsNone(tabela.calcular("imc_idade", "H", 1, 13.2, idade_dias=32))

    def test_oms_2007_interpola_meses_decimais(self):
        tabela = TabelaReferenciaOMS.de_linhas([
            {"indicador": "imc_idade", "referencia": "oms_2007", "sexo": "H",
             "idade_meses": "61", "L": "1", "M": "12", "S": "0.1"},
            {"indicador": "imc_idade", "referencia": "oms_2007", "sexo": "H",
             "idade_meses": "62", "L": "1", "M": "13", "S": "0.1"},
        ])
        self.assertAlmostEqual(tabela.calcular("imc_idade", "H", 61.5, 15.0), 2.0)

    def test_avaliacao_classifica_por_meses_completos_e_calcula_por_dias(self):
        tabela = TabelaReferenciaOMS.de_linhas([
            {"indicador": "imc_idade", "referencia": "oms_2006", "sexo": "H",
             "idade_dias": "300", "L": "1", "M": "10", "S": "0.1"},
        ])
        resultado = avaliar_indicador("imc_idade", 12.0, "H", 9, tabela, idade_dias=300)
        self.assertEqual(resultado["status"], "calculado")
        self.assertEqual(resultado["classificacao"], "Risco de sobrepeso")


    def test_oms_2007_aceita_idade_completa_60_com_mes_decimal_abaixo_de_60(self):
        tabela = TabelaReferenciaOMS.de_linhas([
            {"indicador": "imc_idade", "referencia": "oms_2007", "sexo": "H",
             "idade_meses": "60", "L": "1", "M": "10", "S": "0.1"},
            {"indicador": "imc_idade", "referencia": "oms_2007", "sexo": "H",
             "idade_meses": "61", "L": "1", "M": "11", "S": "0.1"},
        ])
        resultado = avaliar_indicador("imc_idade", 11.5, "H", 59.99, tabela,
                                      idade_meses_completos=60)
        self.assertEqual(resultado["status"], "calculado")
        self.assertEqual(resultado["referencia"], "oms_2007")
        self.assertEqual(resultado["classificacao"], "Sobrepeso")

    def test_interpolacao_usa_ancora_superior_229_sem_classificar_229(self):
        tabela = TabelaReferenciaOMS.de_linhas([
            {"indicador": "imc_idade", "referencia": "oms_2007", "sexo": "M",
             "idade_meses": "228", "L": "1", "M": "20", "S": "0.1"},
            {"indicador": "imc_idade", "referencia": "oms_2007", "sexo": "M",
             "idade_meses": "229", "L": "1", "M": "21", "S": "0.1"},
        ])
        self.assertIsNotNone(tabela.calcular("imc_idade", "M", 228.5, 25.0,
                                             idade_meses_completos=228))
        resultado = avaliar_indicador("imc_idade", 25.0, "M", 229, tabela,
                                      idade_meses_completos=229)
        self.assertEqual(resultado["status"], "fora_faixa")

    def test_curva_expoe_centros_e_limites_da_tabela(self):
        tabela = TabelaReferenciaOMS.de_linhas([
            {"indicador": "estatura_idade", "referencia": "oms_2007", "sexo": "M",
             "idade_meses": "61", "L": "1", "M": "100", "S": "0.1"},
        ])
        curva = tabela.curva("estatura_idade", "M", "oms_2007")
        self.assertEqual(len(curva), 1)
        self.assertEqual(curva[0]["z_zero"], 100.0)
        self.assertGreater(curva[0]["z_mais3"], curva[0]["z_mais2"])


class TestLimitesEAncoraOMS2007(unittest.TestCase):
    def test_avaliacao_inicia_referencia_2007_aos_60_meses(self):
        tabela = TabelaReferenciaOMS.de_linhas([
            {"indicador": "imc_idade", "referencia": "oms_2006", "sexo": "H",
             "idade_dias": "1826", "L": "1", "M": "10", "S": "0.1"},
            {"indicador": "imc_idade", "referencia": "oms_2007", "sexo": "H",
             "idade_meses": "60", "L": "1", "M": "20", "S": "0.1"},
        ])
        resultado = avaliar_indicador(
            "imc_idade", 20.0, "H", 60.0, tabela,
            idade_dias=1827, idade_meses_completos=60,
        )
        self.assertEqual(resultado["status"], "calculado")
        self.assertEqual(resultado["referencia"], "oms_2007")
        self.assertAlmostEqual(resultado["escore_z"], 0.0)

    def test_ancoras_superiores_permitem_interpolacao_sem_extrapolar(self):
        tabela = TabelaReferenciaOMS.de_linhas([
            {"indicador": "imc_idade", "referencia": "oms_2007", "sexo": "H",
             "idade_meses": "228", "L": "1", "M": "20", "S": "0.1"},
            {"indicador": "imc_idade", "referencia": "oms_2007", "sexo": "H",
             "idade_meses": "229", "L": "1", "M": "21", "S": "0.1"},
            {"indicador": "peso_idade", "referencia": "oms_2007", "sexo": "H",
             "idade_meses": "120", "L": "1", "M": "30", "S": "0.1"},
            {"indicador": "peso_idade", "referencia": "oms_2007", "sexo": "H",
             "idade_meses": "121", "L": "1", "M": "31", "S": "0.1"},
        ])
        self.assertAlmostEqual(
            tabela.calcular("imc_idade", "H", 228.5, 20.5, idade_meses_completos=228), 0.0
        )
        self.assertAlmostEqual(
            tabela.calcular("peso_idade", "H", 120.5, 30.5, idade_meses_completos=120), 0.0
        )
        self.assertEqual(
            [p["idade"] for p in tabela.curva("imc_idade", "H", "oms_2007")], [228]
        )
        self.assertEqual(
            [p["idade"] for p in tabela.curva("peso_idade", "H", "oms_2007")], [120]
        )

    def test_csv_oficial_contem_ancoras_superiores_de_interpolacao(self):
        base = Path(__file__).resolve().parents[1]
        tabela = TabelaReferenciaOMS.carregar_padrao(base)
        self.assertIsNotNone(tabela)
        self.assertIn(229, tabela._dados_meses[("imc_idade", "oms_2007", "H")])
        self.assertIn(121, tabela._dados_meses[("peso_idade", "oms_2007", "H")])
        self.assertIn(
            229, [p["idade"] for p in tabela.curva("imc_idade", "H", "oms_2007")]
        )
        self.assertIn(
            121, [p["idade"] for p in tabela.curva("peso_idade", "H", "oms_2007")]
        )

if __name__ == "__main__":
    unittest.main()
