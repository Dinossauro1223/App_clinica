# -*- coding: utf-8 -*-
"""Regras de posição dos gráficos agrupados (graficos_layout): Python puro, sem janela."""
import ctypes
import os
import sys
import unittest
from unittest import mock

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


class TestDesempenhoConfiguracao(unittest.TestCase):
    def test_desempenho_valido(self):
        for chave in (gl.DESEMPENHO_AUTOMATICO, gl.DESEMPENHO_COMPLETO, gl.DESEMPENHO_ECONOMICO):
            self.assertEqual(gl.desempenho_valido(chave), chave)
        # valor gravado errado, vazio ou de uma versão futura: volta para o padrão (automático)
        for ruim in ("", None, "turbo", "AUTOMATICO", 7):
            self.assertEqual(gl.desempenho_valido(ruim), gl.DESEMPENHO_AUTOMATICO, repr(ruim))

    def test_rotulos_ida_e_volta(self):
        self.assertEqual(set(gl.ROTULOS_DESEMPENHO),
                         {gl.DESEMPENHO_AUTOMATICO, gl.DESEMPENHO_COMPLETO, gl.DESEMPENHO_ECONOMICO})
        self.assertEqual(len(set(gl.ROTULOS_DESEMPENHO.values())), 3)
        for chave, rotulo in gl.ROTULOS_DESEMPENHO.items():
            self.assertEqual(gl.rotulo_para_desempenho(rotulo), chave)
        self.assertEqual(gl.rotulo_para_desempenho("texto que não existe"), gl.DESEMPENHO_AUTOMATICO)

    def test_o_padrao_e_o_primeiro_da_lista(self):
        self.assertEqual(next(iter(gl.ROTULOS_DESEMPENHO)), gl.DESEMPENHO_AUTOMATICO)
        self.assertEqual(gl.CHAVE_DESEMPENHO, "graficos_desempenho")

    def test_textos_sem_travessao(self):
        """Os textos que aparecem na tela seguem a regra de escrita do projeto: sem travessão."""
        textos = list(gl.ROTULOS_DESEMPENHO.values()) + list(gl.NOMES_NIVEL.values())
        for modo in gl.ROTULOS_DESEMPENHO:
            textos.append(gl.Ritmo(modo).descricao())
        lento = gl.Ritmo()
        for _ in range(gl.AMOSTRAS_PARA_DECIDIR):
            lento.registrar_quadro(0.05, 0.2)
        textos.append(lento.descricao())
        textos.append(gl.Ritmo(nivel_do_sistema=gl.NIVEL_REDUZIDO, motivo_do_sistema="o Windows está com as animações "
                                                                                    "desligadas").descricao())
        for texto in textos:
            self.assertNotIn("\u2014", texto, texto)
            self.assertNotIn("\u2013", texto, texto)


class TestRitmo(unittest.TestCase):
    N = gl.AMOSTRAS_PARA_DECIDIR

    def alimentar(self, ritmo, custo, periodo=None, vezes=None):
        for _ in range(self.N if vezes is None else vezes):
            ritmo.registrar_quadro(custo, periodo)

    def test_comeca_completo(self):
        r = gl.Ritmo()
        self.assertEqual(r.modo, gl.DESEMPENHO_AUTOMATICO)
        self.assertEqual(r.nivel, gl.NIVEL_COMPLETO)
        self.assertTrue(r.anima)
        self.assertEqual(r.intervalo_ms, 16)
        self.assertEqual(r.duracao(0.9), 0.9)
        self.assertEqual(r.motivo, "")
        self.assertEqual(r.descricao(), "Agora: animação completa.")

    def test_modo_invalido_vira_automatico(self):
        self.assertEqual(gl.Ritmo("turbo").modo, gl.DESEMPENHO_AUTOMATICO)

    def test_modo_completo_nunca_muda(self):
        r = gl.Ritmo(gl.DESEMPENHO_COMPLETO)
        self.alimentar(r, 0.5, 1.0, vezes=200)
        self.assertEqual(r.nivel, gl.NIVEL_COMPLETO)
        self.assertEqual(r.intervalo_ms, 16)
        self.assertEqual(r.duracao(gl.DURACAO_ENTRADA), gl.DURACAO_ENTRADA)
        self.assertEqual(r.descricao(), "Animação completa em qualquer computador.")

    def test_modo_economico_nunca_anima(self):
        r = gl.Ritmo(gl.DESEMPENHO_ECONOMICO)
        self.assertEqual(r.nivel, gl.NIVEL_SEM_ANIMACAO)
        self.assertFalse(r.anima)
        self.assertEqual(r.duracao(gl.DURACAO_ENTRADA), 0.0)
        self.assertIn("Sem animação", r.descricao())

    def test_poucas_medidas_nao_decidem(self):
        r = gl.Ritmo()
        self.alimentar(r, 0.5, 1.0, vezes=self.N - 1)       # lentíssimo, mas só N-1 quadros
        self.assertEqual(r.nivel, gl.NIVEL_COMPLETO)
        r.registrar_quadro(0.5, 1.0)                        # o quadro N decide
        self.assertEqual(r.nivel, gl.NIVEL_REDUZIDO)

    def test_quadros_caros_descem_para_reduzido(self):
        r = gl.Ritmo()
        self.alimentar(r, gl.LIMITE_CUSTO_S[gl.NIVEL_COMPLETO] + 0.004)
        self.assertEqual(r.nivel, gl.NIVEL_REDUZIDO)
        self.assertEqual(r.intervalo_ms, 33)
        self.assertAlmostEqual(r.duracao(1.0), gl.FATOR_DURACAO[gl.NIVEL_REDUZIDO])
        self.assertTrue(r.anima)
        self.assertIn("cada quadro levou 12 ms", r.motivo)
        self.assertIn("Motivo: cada quadro levou 12 ms", r.descricao())

    def test_quadros_baratos_nao_mudam_nada(self):
        r = gl.Ritmo()
        self.alimentar(r, 0.001, 0.017, vezes=500)
        self.assertEqual(r.nivel, gl.NIVEL_COMPLETO)

    def test_quadro_no_limite_ainda_passa(self):
        r = gl.Ritmo()
        self.alimentar(r, gl.LIMITE_CUSTO_S[gl.NIVEL_COMPLETO], vezes=50)     # igual ao limite: não passa dele
        self.assertEqual(r.nivel, gl.NIVEL_COMPLETO)

    def test_um_tranco_isolado_nao_estraga_a_animacao(self):
        r = gl.Ritmo()
        for _ in range(20):
            for custo in (0.001, 0.001, 0.001, 0.001, 0.3, 0.001, 0.001, 0.001, 0.001):   # 1 quadro em 9 trava
                r.registrar_quadro(custo, 0.017)
        self.assertEqual(r.nivel, gl.NIVEL_COMPLETO)

    def test_minoria_lenta_nao_decide_mas_maioria_decide(self):
        r = gl.Ritmo()
        for _ in range(10):         # 4 lentos em cada 9: a mediana continua rápida
            for custo in (0.05, 0.05, 0.05, 0.05, 0.001, 0.001, 0.001, 0.001, 0.001):
                r.registrar_quadro(custo)
        self.assertEqual(r.nivel, gl.NIVEL_COMPLETO)
        for _ in range(self.N):     # 5 lentos em 9: agora sim
            for custo in (0.05, 0.05, 0.05, 0.05, 0.05, 0.001, 0.001, 0.001, 0.001):
                r.registrar_quadro(custo)
        self.assertGreater(r.nivel, gl.NIVEL_COMPLETO)

    def test_intervalo_entre_quadros_tambem_conta(self):
        """O custo do nosso código pode ser baixo e a tela mesmo assim não acompanhar (acesso remoto, placa fraca)."""
        r = gl.Ritmo()
        lento = 3.5 * gl.INTERVALO_QUADROS_MS[gl.NIVEL_COMPLETO] / 1000.0 + 0.01
        self.alimentar(r, 0.001, lento)
        self.assertEqual(r.nivel, gl.NIVEL_REDUZIDO)
        self.assertIn("os quadros chegaram a cada", r.motivo)
        self.assertIn("o previsto era 16 ms", r.motivo)

    def test_intervalo_normal_do_windows_nao_assusta(self):
        """O relógio do Windows costuma dar 16 ou 31 ms para um pedido de 16 ms: isso não é computador lento."""
        r = gl.Ritmo()
        for _ in range(60):
            r.registrar_quadro(0.0015, 0.0312)
            r.registrar_quadro(0.0015, 0.0156)
        self.assertEqual(r.nivel, gl.NIVEL_COMPLETO)

    def test_o_intervalo_so_vale_com_medidas_suficientes(self):
        r = gl.Ritmo()
        r.registrar_quadro(0.001, None)                      # 1º quadro de uma sequência: sem quadro anterior
        for _ in range(gl.AMOSTRAS_DE_INTERVALO - 1):
            r.registrar_quadro(0.001, 5.0)                    # 4 intervalos absurdos
        for _ in range(self.N - gl.AMOSTRAS_DE_INTERVALO):
            r.registrar_quadro(0.001, None)                   # completa os 9 custos sem mais intervalos
        self.assertEqual(r.nivel, gl.NIVEL_COMPLETO)

    def test_desce_de_novo_ate_sem_animacao_e_para(self):
        r = gl.Ritmo()
        self.alimentar(r, 0.02)
        self.assertEqual(r.nivel, gl.NIVEL_REDUZIDO)
        self.alimentar(r, 0.02)                              # 20 ms ainda cabe no limite do nível reduzido (25 ms)
        self.assertEqual(r.nivel, gl.NIVEL_REDUZIDO)
        self.alimentar(r, 0.04)
        self.assertEqual(r.nivel, gl.NIVEL_SEM_ANIMACAO)
        self.assertFalse(r.anima)
        self.assertEqual(r.duracao(gl.DURACAO_ENTRADA), 0.0)
        self.alimentar(r, 1.0, 5.0, vezes=100)               # não há nível abaixo de "sem animação"
        self.assertEqual(r.nivel, gl.NIVEL_SEM_ANIMACAO)

    def test_o_limite_do_nivel_reduzido_usa_o_intervalo_dele(self):
        r = gl.Ritmo()
        self.alimentar(r, 0.02)                              # completo -> reduzido
        previsto = gl.INTERVALO_QUADROS_MS[gl.NIVEL_REDUZIDO] / 1000.0
        self.alimentar(r, 0.001, 3.4 * previsto)             # 112 ms entre quadros: ainda dentro de 3,5 x 33 ms
        self.assertEqual(r.nivel, gl.NIVEL_REDUZIDO)
        self.alimentar(r, 0.001, 3.6 * previsto)             # 119 ms: passou
        self.assertEqual(r.nivel, gl.NIVEL_SEM_ANIMACAO)

    def test_nao_sobe_sozinho(self):
        r = gl.Ritmo()
        self.alimentar(r, 0.02)
        self.assertEqual(r.nivel, gl.NIVEL_REDUZIDO)
        self.alimentar(r, 0.0005, 0.034, vezes=1000)
        self.assertEqual(r.nivel, gl.NIVEL_REDUZIDO)

    def test_apos_descer_recomeca_a_contar(self):
        r = gl.Ritmo()
        self.alimentar(r, 0.5)                               # completo -> reduzido
        self.alimentar(r, 0.5, vezes=self.N - 1)             # faltou 1 quadro: ainda reduzido
        self.assertEqual(r.nivel, gl.NIVEL_REDUZIDO)
        r.registrar_quadro(0.5)
        self.assertEqual(r.nivel, gl.NIVEL_SEM_ANIMACAO)

    def test_valores_estranhos_nao_quebram(self):
        r = gl.Ritmo()
        self.alimentar(r, -1.0, -1.0)
        self.assertEqual(r.nivel, gl.NIVEL_COMPLETO)

    def test_trocar_de_modo_recomeca(self):
        r = gl.Ritmo()
        self.alimentar(r, 0.02)
        self.assertEqual(r.nivel, gl.NIVEL_REDUZIDO)
        r.modo = gl.DESEMPENHO_AUTOMATICO                    # o mesmo modo: não esquece o que aprendeu
        self.assertEqual(r.nivel, gl.NIVEL_REDUZIDO)
        r.modo = gl.DESEMPENHO_COMPLETO
        self.assertEqual(r.nivel, gl.NIVEL_COMPLETO)
        r.modo = gl.DESEMPENHO_ECONOMICO
        self.assertEqual(r.nivel, gl.NIVEL_SEM_ANIMACAO)
        r.modo = gl.DESEMPENHO_AUTOMATICO                    # voltar ao automático mede tudo de novo
        self.assertEqual(r.nivel, gl.NIVEL_COMPLETO)
        self.assertEqual(r.motivo, "")

    def test_modo_invalido_na_troca_vira_automatico(self):
        r = gl.Ritmo(gl.DESEMPENHO_COMPLETO)
        r.modo = "turbo"
        self.assertEqual(r.modo, gl.DESEMPENHO_AUTOMATICO)

    def test_sistema_que_pede_economia_comeca_reduzido(self):
        r = gl.Ritmo(nivel_do_sistema=gl.NIVEL_REDUZIDO, motivo_do_sistema="o programa está em acesso remoto")
        self.assertEqual(r.nivel, gl.NIVEL_REDUZIDO)
        self.assertEqual(r.intervalo_ms, 33)
        self.assertIn("acesso remoto", r.descricao())
        self.alimentar(r, 0.001, 0.034, vezes=100)           # quadros bons: continua reduzido, não "melhora"
        self.assertEqual(r.nivel, gl.NIVEL_REDUZIDO)
        self.alimentar(r, 0.05)                              # e ainda pode descer
        self.assertEqual(r.nivel, gl.NIVEL_SEM_ANIMACAO)

    def test_modo_completo_ignora_o_que_o_sistema_pede(self):
        r = gl.Ritmo(gl.DESEMPENHO_COMPLETO, gl.NIVEL_REDUZIDO, "acesso remoto")
        self.assertEqual(r.nivel, gl.NIVEL_COMPLETO)
        r.modo = gl.DESEMPENHO_AUTOMATICO
        self.assertEqual(r.nivel, gl.NIVEL_REDUZIDO)         # no automático, o pedido do sistema volta a valer

    def test_do_sistema_usa_o_que_o_sistema_informa(self):
        with mock.patch.object(gl, "sistema_pede_economia", return_value=(gl.NIVEL_REDUZIDO, "motivo de teste")):
            self.assertEqual(gl.Ritmo.do_sistema().nivel, gl.NIVEL_REDUZIDO)
            self.assertEqual(gl.Ritmo.do_sistema().motivo, "motivo de teste")
            self.assertEqual(gl.Ritmo.do_sistema(gl.DESEMPENHO_COMPLETO).nivel, gl.NIVEL_COMPLETO)

    def test_contagem_de_quadros(self):
        r = gl.Ritmo(gl.DESEMPENHO_COMPLETO)
        self.alimentar(r, 0.001, vezes=7)
        self.assertEqual(r.quadros, 7)

    def test_niveis_em_ordem_e_com_tabelas_completas(self):
        self.assertLess(gl.NIVEL_COMPLETO, gl.NIVEL_REDUZIDO)
        self.assertLess(gl.NIVEL_REDUZIDO, gl.NIVEL_SEM_ANIMACAO)
        for nivel in (gl.NIVEL_COMPLETO, gl.NIVEL_REDUZIDO, gl.NIVEL_SEM_ANIMACAO):
            self.assertIn(nivel, gl.NOMES_NIVEL)
            self.assertIn(nivel, gl.INTERVALO_QUADROS_MS)
            self.assertIn(nivel, gl.FATOR_DURACAO)
        self.assertEqual(gl.FATOR_DURACAO[gl.NIVEL_COMPLETO], 1.0)
        self.assertEqual(gl.FATOR_DURACAO[gl.NIVEL_SEM_ANIMACAO], 0.0)
        self.assertGreater(gl.INTERVALO_QUADROS_MS[gl.NIVEL_REDUZIDO], gl.INTERVALO_QUADROS_MS[gl.NIVEL_COMPLETO])
        self.assertGreater(gl.LIMITE_CUSTO_S[gl.NIVEL_REDUZIDO], gl.LIMITE_CUSTO_S[gl.NIVEL_COMPLETO])


class _User32Falso:
    """user32.dll falso: o que o Windows diria sobre acesso remoto e animações."""

    def __init__(self, remoto=0, animacoes=1, spi_ok=1, erro=None):
        self.remoto, self.animacoes, self.spi_ok, self.erro = remoto, animacoes, spi_ok, erro
        self.chamadas = []

    def GetSystemMetrics(self, indice):  # noqa: N802  (nome da API do Windows)
        self.chamadas.append(("metricas", indice))
        if self.erro:
            raise self.erro
        return self.remoto if indice == gl.SM_REMOTESESSION else 0

    def SystemParametersInfoW(self, acao, parametro, ponteiro, flags):  # noqa: N802
        self.chamadas.append(("spi", acao))
        if self.erro:
            raise self.erro
        if acao == gl.SPI_GETCLIENTAREAANIMATION:
            ponteiro._obj.value = self.animacoes     # byref(c_int): o valor que o Windows escreveria
        return self.spi_ok


class TestSistemaPedeEconomia(unittest.TestCase):
    def consultar(self, user32=None, plataforma="win32"):
        falso = type("Windll", (), {"user32": user32})()
        with mock.patch.object(gl.sys, "platform", plataforma), \
                mock.patch.object(ctypes, "windll", falso, create=True):
            return gl.sistema_pede_economia()

    def test_fora_do_windows_nao_ha_o_que_declarar(self):
        u = _User32Falso(remoto=1, animacoes=0)
        for plataforma in ("linux", "darwin"):
            self.assertEqual(self.consultar(u, plataforma), (gl.NIVEL_COMPLETO, ""))
        self.assertEqual(u.chamadas, [])          # nem consulta o sistema

    def test_windows_normal(self):
        u = _User32Falso()
        self.assertEqual(self.consultar(u), (gl.NIVEL_COMPLETO, ""))
        self.assertEqual(u.chamadas, [("metricas", gl.SM_REMOTESESSION), ("spi", gl.SPI_GETCLIENTAREAANIMATION)])

    def test_acesso_remoto_comeca_reduzido(self):
        nivel, motivo = self.consultar(_User32Falso(remoto=1))
        self.assertEqual(nivel, gl.NIVEL_REDUZIDO)
        self.assertIn("acesso remoto", motivo)

    def test_animacoes_desligadas_no_windows_comeca_reduzido(self):
        nivel, motivo = self.consultar(_User32Falso(animacoes=0))
        self.assertEqual(nivel, gl.NIVEL_REDUZIDO)       # reduzido, não "sem animação": o gráfico continua animado
        self.assertIn("animações desligadas", motivo)

    def test_consulta_que_falha_vale_por_nada_a_declarar(self):
        self.assertEqual(self.consultar(_User32Falso(animacoes=0, spi_ok=0)), (gl.NIVEL_COMPLETO, ""))
        self.assertEqual(self.consultar(_User32Falso(erro=OSError("sem permissão"))), (gl.NIVEL_COMPLETO, ""))
        self.assertEqual(self.consultar(None), (gl.NIVEL_COMPLETO, ""))     # user32 ausente

    def test_constantes_da_api_do_windows(self):
        self.assertEqual(gl.SM_REMOTESESSION, 0x1000)
        self.assertEqual(gl.SPI_GETCLIENTAREAANIMATION, 0x1042)


if __name__ == "__main__":
    unittest.main(verbosity=2)
