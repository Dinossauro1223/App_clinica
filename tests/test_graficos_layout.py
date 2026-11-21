# -*- coding: utf-8 -*-
"""Regras de posição dos gráficos agrupados (graficos_layout): Python puro, sem janela."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import graficos_layout as gl  # noqa: E402


class TestConfiguracao(unittest.TestCase):
    def test_disposicao_valida(self):
        self.assertEqual(gl.disposicao_valida("vertical"), gl.DISPOSICAO_VERTICAL)
        self.assertEqual(gl.disposicao_valida("lado_a_lado"), gl.DISPOSICAO_LADO_A_LADO)
        # valor gravado errado, vazio ou de uma versão futura: volta para o padrão (lado a lado)
        for ruim in ("", None, "grade", "VERTICAL", 3):
            self.assertEqual(gl.disposicao_valida(ruim), gl.DISPOSICAO_LADO_A_LADO, repr(ruim))

    def test_rotulos_ida_e_volta(self):
        self.assertEqual(set(gl.ROTULOS_DISPOSICAO), {gl.DISPOSICAO_LADO_A_LADO, gl.DISPOSICAO_VERTICAL})
        for chave, rotulo in gl.ROTULOS_DISPOSICAO.items():
            self.assertEqual(gl.rotulo_para_disposicao(rotulo), chave)
        self.assertEqual(gl.rotulo_para_disposicao("texto que não existe"), gl.DISPOSICAO_LADO_A_LADO)
        self.assertEqual(len(set(gl.ROTULOS_DISPOSICAO.values())), 2)


class TestMedidas(unittest.TestCase):
    def test_largura_do_card(self):
        # um gráfico só: usa a janela toda, até o máximo
        self.assertEqual(gl.largura_do_card(500, 1), 500)
        self.assertEqual(gl.largura_do_card(2000, 1), gl.LARGURA_MAX_CARD)
        # vários: sobra uma espiada do próximo gráfico, para mostrar que dá para arrastar
        self.assertEqual(gl.largura_do_card(500, 3), 500 - gl.ESPIADA)
        self.assertEqual(gl.largura_do_card(2000, 3), gl.LARGURA_MAX_CARD)
        # janela minúscula: não passa do mínimo
        self.assertEqual(gl.largura_do_card(100, 3), gl.LARGURA_MIN_CARD)
        # valores do Windows com escala maior
        self.assertEqual(gl.largura_do_card(1000, 2, maximo=1260, espiada=84), 916)

    def test_tamanho_do_card_mantem_proporcao(self):
        self.assertEqual(gl.tamanho_do_card(900, 450, 450), (450, 225))
        # nunca estica além do tamanho original
        self.assertEqual(gl.tamanho_do_card(400, 200, 840), (400, 200))
        # altura nunca chega a zero
        self.assertEqual(gl.tamanho_do_card(1000, 1, 10), (10, 1))
        # imagem sem tamanho: cai numa proporção segura, sem dividir por zero
        for ruim in ((0, 0), (0, 100), (100, 0)):
            largura, altura = gl.tamanho_do_card(*ruim, 300)
            self.assertEqual((largura, altura), (300, 120))

    def test_suavizar(self):
        self.assertEqual(gl.suavizar(0.0), 0.0)
        self.assertEqual(gl.suavizar(1.0), 1.0)
        self.assertEqual(gl.suavizar(-5), 0.0)
        self.assertEqual(gl.suavizar(7), 1.0)
        valores = [gl.suavizar(i / 20) for i in range(21)]
        self.assertEqual(valores, sorted(valores))               # só sobe
        self.assertGreater(gl.suavizar(0.5), 0.5)                # começa rápido e desacelera
        passos = [b - a for a, b in zip(valores, valores[1:])]
        self.assertEqual(passos, sorted(passos, reverse=True))   # cada passo menor que o anterior

    def test_pontos(self):
        self.assertEqual(gl.pontos(3, 0), "● ○ ○")
        self.assertEqual(gl.pontos(3, 2), "○ ○ ●")
        self.assertEqual(gl.pontos(1, 0), "●")
        self.assertEqual(gl.pontos(0, 0), "")


class TestCarrossel(unittest.TestCase):
    def setUp(self):
        # 3 gráficos de 840 px, espaço de 16, janela de 1100 px
        self.c = gl.Carrossel(3, 840, 1100, 16)

    def test_medidas(self):
        self.assertEqual(self.c.passo, 856)
        self.assertEqual(self.c.largura_total, 3 * 840 + 2 * 16)
        self.assertEqual(self.c.deslocamento_maximo, 3 * 840 + 2 * 16 - 1100)
        self.assertEqual([self.c.x_do_card(i) for i in range(3)], [0, 856, 1712])
        self.assertFalse(self.c.cabe_sem_rolar())

    def test_limitar_e_alvo(self):
        self.assertEqual(self.c.limitar(-50), 0.0)
        self.assertEqual(self.c.limitar(10_000), self.c.deslocamento_maximo)
        self.assertEqual(self.c.limitar(300), 300.0)
        self.assertEqual(self.c.alvo(0), 0.0)
        self.assertEqual(self.c.alvo(1), 856.0)
        self.assertEqual(self.c.alvo(2), self.c.deslocamento_maximo)   # o último encosta no fim, não passa dele
        self.assertEqual(self.c.alvo(-4), 0.0)
        self.assertEqual(self.c.alvo(99), self.c.deslocamento_maximo)

    def test_posicoes_quase_sempre_uma_por_grafico(self):
        self.assertEqual(self.c.posicoes, [0.0, 856.0, 1452.0])
        self.assertEqual(self.c.n_posicoes, 3)
        self.assertEqual(self.c.x_da_posicao(1), 856.0)
        self.assertEqual(self.c.x_da_posicao(-1), 0.0)
        self.assertEqual(self.c.x_da_posicao(50), 1452.0)

    def test_janela_larga_junta_os_ultimos_encaixes(self):
        # 3 gráficos de 400 px numa janela de 1000: os dois últimos terminam no mesmo lugar (fim da faixa)
        c = gl.Carrossel(3, 400, 1000, 16)
        self.assertEqual(c.posicoes, [0.0, 232.0])
        self.assertEqual(c.n_posicoes, 2)
        # ao chegar no fim, a posição ativa é a última: "próximo" nunca fica parado sem andar
        self.assertEqual(c.mais_proximo(232.0), 1)
        self.assertEqual(c.mais_proximo(0.0), 0)

    def test_cabe_sem_rolar(self):
        c = gl.Carrossel(2, 300, 1000, 16)
        self.assertTrue(c.cabe_sem_rolar())
        self.assertEqual(c.deslocamento_maximo, 0.0)
        self.assertEqual(c.posicoes, [0.0])
        self.assertEqual(c.mais_proximo(500), 0)
        self.assertEqual(c.depois_de_soltar(0, 0, 9000), 0)   # arremesso sem ter para onde ir

    def test_sem_graficos_e_com_um(self):
        vazio = gl.Carrossel(0, 840, 1100, 16)
        self.assertEqual((vazio.largura_total, vazio.posicoes, vazio.alvo(0), vazio.mais_proximo(3)), (0.0, [0.0], 0.0, 0))
        um = gl.Carrossel(1, 840, 1100, 16)
        self.assertTrue(um.cabe_sem_rolar())
        self.assertEqual(um.posicoes, [0.0])

    def test_mais_proximo(self):
        self.assertEqual(self.c.mais_proximo(0), 0)
        self.assertEqual(self.c.mais_proximo(300), 0)
        self.assertEqual(self.c.mais_proximo(500), 1)
        self.assertEqual(self.c.mais_proximo(1200), 2)
        self.assertEqual(self.c.mais_proximo(99999), 2)

    def test_depois_de_soltar_lento_encaixa_no_mais_perto(self):
        self.assertEqual(self.c.depois_de_soltar(300, 0, 10.0), 0)
        self.assertEqual(self.c.depois_de_soltar(500, 0, 10.0), 1)
        self.assertEqual(self.c.depois_de_soltar(900, 856, -10.0), 1)

    def test_depois_de_soltar_rapido_vai_para_o_vizinho(self):
        rapido = gl.VELOCIDADE_DE_ARREMESSO * 2
        # arraste curto, mas jogado para a esquerda (conteúdo andou para a esquerda): próxima posição
        self.assertEqual(self.c.depois_de_soltar(100, 0, rapido), 1)
        # jogado para a direita: posição anterior
        self.assertEqual(self.c.depois_de_soltar(756, 856, -rapido), 0)
        # nos extremos não passa
        self.assertEqual(self.c.depois_de_soltar(1452, 1452, rapido), 2)
        self.assertEqual(self.c.depois_de_soltar(0, 0, -rapido), 0)

    def test_depois_de_soltar_so_olha_a_velocidade_acima_do_limite(self):
        quase = gl.VELOCIDADE_DE_ARREMESSO - 1
        self.assertEqual(self.c.depois_de_soltar(100, 0, quase), 0)
        self.assertEqual(self.c.depois_de_soltar(100, 0, gl.VELOCIDADE_DE_ARREMESSO), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
