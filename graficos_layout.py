# -*- coding: utf-8 -*-
"""Regras de posição dos gráficos agrupados (Python puro, sem Tk): carrossel que se arrasta para o lado.

A tela de gráficos junta os gráficos por assunto (atendimentos, dieta, suplementos, doenças crônicas). Cada grupo
pode aparecer de dois jeitos, escolhidos em Configurações do Mapa:

* "lado_a_lado": uma faixa por grupo, com os gráficos um ao lado do outro. Arrasta-se com o mouse (ou usam-se as
  setas); ao soltar, a faixa encaixa no gráfico mais próximo. Um pedaço do próximo gráfico fica à vista para mostrar
  que há mais para o lado.
* "vertical": os gráficos de cada grupo ficam um embaixo do outro, como a tela era antes, mas ainda agrupados.

Aqui ficam só as contas (larguras, deslocamento, encaixe, efeito de suavização), para testar sem abrir janela.
"""

DISPOSICAO_LADO_A_LADO = "lado_a_lado"
DISPOSICAO_VERTICAL = "vertical"
CHAVE_CONFIG = "graficos_disposicao"
ROTULOS_DISPOSICAO = {
    DISPOSICAO_LADO_A_LADO: "Agrupados, arrastar para o lado",
    DISPOSICAO_VERTICAL: "Agrupados, de cima para baixo",
}

ESTILO_ANIMADO = "animado"
ESTILO_IMAGEM = "imagem"
CHAVE_ESTILO = "graficos_estilo"
ROTULOS_ESTILO = {
    ESTILO_ANIMADO: "Animados (desenhados na tela)",
    ESTILO_IMAGEM: "Imagens simples, sem animação",
}

LARGURA_MAX_CARD = 840      # largura máxima de um gráfico, em pixels lógicos (a mesma de antes)
ESPACO_ENTRE_CARDS = 16
ESPIADA = 56                # pedaço do próximo gráfico que fica à vista, para sugerir que dá para arrastar
LARGURA_MIN_CARD = 160
VELOCIDADE_DE_ARREMESSO = 500.0   # px/s: soltar mais rápido que isso passa para o gráfico seguinte
DURACAO_ENCAIXE = 0.28            # segundos
DURACAO_ENTRADA = 0.9
ATRASO_ENTRE_CARDS = 0.12
FRACAO_PARA_ANIMAR = 0.3


def disposicao_valida(valor):
    """Valor gravado na configuração -> disposição conhecida (padrão: lado a lado)."""
    return valor if valor in ROTULOS_DISPOSICAO else DISPOSICAO_LADO_A_LADO


def rotulo_para_disposicao(rotulo):
    for chave, texto in ROTULOS_DISPOSICAO.items():
        if texto == rotulo:
            return chave
    return DISPOSICAO_LADO_A_LADO


def estilo_valido(valor):
    return valor if valor in ROTULOS_ESTILO else ESTILO_ANIMADO


def rotulo_para_estilo(rotulo):
    for chave, texto in ROTULOS_ESTILO.items():
        if texto == rotulo:
            return chave
    return ESTILO_ANIMADO


def largura_do_card(largura_visivel, n_cards, maximo=LARGURA_MAX_CARD, espiada=ESPIADA):
    """Largura de cada gráfico na faixa. Com mais de um, sobra uma `espiada` para o próximo aparecer."""
    util = largura_visivel - (espiada if n_cards > 1 else 0)
    return max(LARGURA_MIN_CARD, min(maximo, util))


def tamanho_do_card(largura_original, altura_original, largura_card):
    """Largura e altura do gráfico na faixa, mantendo a proporção e sem esticar além do tamanho original."""
    if largura_original <= 0 or altura_original <= 0:
        return largura_card, int(largura_card * 0.4)
    largura = min(largura_card, largura_original)
    return largura, max(1, round(altura_original * largura / largura_original))


def suavizar(t):
    """Desacelera no fim (cúbica de saída): 0 -> 0, 1 -> 1."""
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def pontos(n, ativo):
    """Indicador de posição: '● ○ ○' (o cheio é o gráfico à esquerda da faixa)."""
    return " ".join("●" if i == ativo else "○" for i in range(n))


class Carrossel:
    """Posições de uma faixa com `n` gráficos de mesma largura, vistos por uma janela de `largura_visivel`."""

    def __init__(self, n, largura_card, largura_visivel, espaco=ESPACO_ENTRE_CARDS):
        self.n = max(0, int(n))
        self.largura_card = float(largura_card)
        self.largura_visivel = float(largura_visivel)
        self.espaco = float(espaco)

    @property
    def passo(self):
        return self.largura_card + self.espaco

    @property
    def largura_total(self):
        return self.n * self.largura_card + max(0, self.n - 1) * self.espaco

    @property
    def deslocamento_maximo(self):
        return max(0.0, self.largura_total - self.largura_visivel)

    def x_do_card(self, i):
        """Posição (na faixa inteira) onde começa o gráfico `i`."""
        return i * self.passo

    def limitar(self, deslocamento):
        return max(0.0, min(float(deslocamento), self.deslocamento_maximo))

    def alvo(self, i):
        """Deslocamento que deixa o gráfico `i` encostado à esquerda (limitado pelo fim da faixa)."""
        if self.n == 0:
            return 0.0
        return self.limitar(max(0, min(int(i), self.n - 1)) * self.passo)

    @property
    def posicoes(self):
        """Deslocamentos onde a faixa encaixa, em ordem e sem repetir.

        Quase sempre há um por gráfico. Em janela larga os últimos gráficos já cabem juntos: o fim da faixa vale por
        vários encaixes e eles se juntam em um só (assim "próximo" nunca fica parado sem andar).
        """
        vistos = []
        for i in range(max(1, self.n)):
            a = self.alvo(i)
            if not vistos or a > vistos[-1] + 0.5:
                vistos.append(a)
        return vistos

    @property
    def n_posicoes(self):
        return len(self.posicoes)

    def x_da_posicao(self, p):
        pos = self.posicoes
        return pos[max(0, min(int(p), len(pos) - 1))]

    def mais_proximo(self, deslocamento):
        """Índice da posição de encaixe mais perto do deslocamento atual (em empate, a mais adiante)."""
        pos = self.posicoes
        return min(range(len(pos)), key=lambda p: (abs(pos[p] - deslocamento), -p))

    def depois_de_soltar(self, deslocamento, deslocamento_inicial, velocidade):
        """Posição de encaixe ao soltar o mouse. `velocidade` é a do conteúdo em px/s (positiva = foi para a esquerda).

        Um arremesso rápido passa para a posição vizinha da que a faixa tinha ao começar o arraste; arraste lento
        encaixa na posição mais perto de onde a faixa parou.
        """
        if abs(velocidade) >= VELOCIDADE_DE_ARREMESSO:
            base = self.mais_proximo(deslocamento_inicial)
            return max(0, min(self.n_posicoes - 1, base + (1 if velocidade > 0 else -1)))
        return self.mais_proximo(deslocamento)

    def cabe_sem_rolar(self):
        return self.deslocamento_maximo <= 0.0
