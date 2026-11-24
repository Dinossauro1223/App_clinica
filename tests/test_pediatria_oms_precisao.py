"""Testes TDD de precisão para o motor LMS pediátrico.

Os números LMS abaixo são sintéticos e usados exclusivamente para verificar
interpolação e correção das caudas; não são referências antropométricas.
"""
import unittest

from pediatria_oms import calcular_escore_z, calcular_idade_dias, interpolar_lms


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


if __name__ == "__main__":
    unittest.main()
