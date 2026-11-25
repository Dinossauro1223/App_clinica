"""Contrato TDD do núcleo antropométrico pediátrico OMS.

Os dados de referência usados aqui são sintéticos e servem somente para testar
matemática, validação e fronteiras; não são tabelas clínicas da OMS.
"""
import unittest

from pediatria_oms import (
    calcular_escore_z,
    calcular_idade_meses,
    classificar_escore_z,
    TabelaReferenciaOMS,
    avaliar_indicador,
)


class TestCalculoEscoreZ(unittest.TestCase):
    def test_lms_com_l_diferente_de_zero(self):
        self.assertAlmostEqual(calcular_escore_z(12.0, 1.0, 10.0, 0.1), 2.0)

    def test_lms_com_l_igual_a_zero(self):
        import math
        self.assertAlmostEqual(calcular_escore_z(10.0 * math.e, 0.0, 10.0, 1.0), 1.0)

    def test_rejeita_valores_nao_positivos_e_parametros_invalidos(self):
        for args in ((0, 1, 10, .1), (10, 1, 0, .1), (10, 1, 10, 0)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                calcular_escore_z(*args)


class TestIdadeEmMeses(unittest.TestCase):
    def test_meses_completos_entre_datas(self):
        self.assertEqual(calcular_idade_meses("2020-01-31", "2020-02-29"), 0)
        self.assertEqual(calcular_idade_meses("2020-01-15", "2020-02-15"), 1)
        self.assertEqual(calcular_idade_meses("2020-01-15", "2021-01-14"), 11)

    def test_rejeita_data_invalida_e_referencia_anterior(self):
        for nascimento, referencia in (("2020-02-30", "2020-03-01"),
                                        ("2021-01-01", "2020-12-31")):
            with self.subTest(nascimento=nascimento), self.assertRaises(ValueError):
                calcular_idade_meses(nascimento, referencia)


class TestClassificacaoPorIndicador(unittest.TestCase):
    def test_imc_menor_de_cinco_anos_tem_risco_de_sobrepeso(self):
        self.assertEqual(classificar_escore_z("imc_idade", 1.5, 59),
                         "Risco de sobrepeso")
        self.assertEqual(classificar_escore_z("imc_idade", 2.5, 59),
                         "Sobrepeso")
        self.assertEqual(classificar_escore_z("imc_idade", 3.5, 59),
                         "Obesidade")

    def test_imc_a_partir_de_cinco_anos_usa_referencia_2007(self):
        self.assertEqual(classificar_escore_z("imc_idade", 1.5, 60),
                         "Sobrepeso")
        self.assertEqual(classificar_escore_z("imc_idade", 1.5, 61),
                         "Sobrepeso")
        self.assertEqual(classificar_escore_z("imc_idade", 2.5, 61),
                         "Obesidade")
        self.assertEqual(classificar_escore_z("imc_idade", -2.5, 61),
                         "Magreza")

    def test_imc_usa_referencia_2007_a_partir_de_60_meses(self):
        self.assertEqual(classificar_escore_z("imc_idade", 1.5, 60), "Sobrepeso")
        self.assertEqual(classificar_escore_z("imc_idade", 2.5, 60), "Obesidade")

    def test_peso_por_idade_nao_classifica_excesso_de_peso_e_limita_a_10_anos(self):
        self.assertEqual(classificar_escore_z("peso_idade", -2.5, 60),
                         "Peso baixo para a idade")
        self.assertEqual(classificar_escore_z("peso_idade", -2.5, 120),
                         "Peso baixo para a idade")
        self.assertEqual(classificar_escore_z("peso_idade", -1.0, 120),
                         "Sem baixo peso pelo indicador")
        with self.assertRaises(ValueError):
            classificar_escore_z("peso_idade", -2.5, 121)

    def test_estatura_por_idade_classifica_deficit_linear(self):
        self.assertEqual(classificar_escore_z("estatura_idade", -3.5, 180),
                         "Estatura muito baixa para idade")
        self.assertEqual(classificar_escore_z("estatura_idade", -2.5, 180),
                         "Estatura baixa para idade")
        self.assertEqual(classificar_escore_z("estatura_idade", 0, 180),
                         "Estatura dentro da faixa de referência")
        self.assertEqual(classificar_escore_z("estatura_idade", 3.5, 180),
                         "Estatura muito elevada para a idade — avaliar contexto clínico")


class TestTabelaReferenciaOMS(unittest.TestCase):
    def setUp(self):
        self.tabela = TabelaReferenciaOMS.de_linhas([
            {"indicador": "imc_idade", "referencia": "oms_2006", "sexo": "H",
             "idade_meses": "0", "L": "1", "M": "10", "S": "0.1"},
            {"indicador": "imc_idade", "referencia": "oms_2006", "sexo": "H",
             "idade_meses": "1", "L": "1", "M": "11", "S": "0.1"},
            {"indicador": "imc_idade", "referencia": "oms_2007", "sexo": "H",
             "idade_meses": "61", "L": "1", "M": "12", "S": "0.1"},
        ])

    def test_busca_lms_exata_por_indicador_sexo_e_idade(self):
        z = self.tabela.calcular("imc_idade", "H", 1, 13.2)
        self.assertAlmostEqual(z, 2.0)

    def test_nao_extrapola_fora_da_tabela(self):
        self.assertIsNone(self.tabela.calcular("imc_idade", "H", 2, 12))
        self.assertIsNone(self.tabela.calcular("imc_idade", "M", 1, 12))

    def test_avaliacao_sem_referencia_fica_pendente_sem_inventar_classe(self):
        resultado = avaliar_indicador("imc_idade", 12.0, "H", 2, self.tabela)
        self.assertEqual(resultado["status"], "pendente")
        self.assertIsNone(resultado["escore_z"])
        self.assertIsNone(resultado["classificacao"])

    def test_avaliacao_com_referencia_retorna_escore_e_classe(self):
        resultado = avaliar_indicador("imc_idade", 13.2, "H", 1, self.tabela)
        self.assertEqual(resultado["status"], "calculado")
        self.assertAlmostEqual(resultado["escore_z"], 2.0)
        self.assertEqual(resultado["classificacao"], "Risco de sobrepeso")


if __name__ == "__main__":
    unittest.main()
