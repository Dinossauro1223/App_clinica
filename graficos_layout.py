# -*- coding: utf-8 -*-
"""Regras de posição dos gráficos agrupados (Python puro, sem Tk): carrossel que se arrasta para o lado.

A tela de gráficos junta os gráficos por assunto (atendimentos, dieta, suplementos, doenças crônicas). Cada grupo
pode aparecer de dois jeitos, escolhidos em Configurações do Mapa:

* "lado_a_lado": uma faixa por grupo, com os gráficos um ao lado do outro. Arrasta-se com o mouse (ou usam-se as
  setas); ao soltar, a faixa encaixa no gráfico mais próximo. Um pedaço do próximo gráfico fica à vista para mostrar
  que há mais para o lado.
* "vertical": os gráficos de cada grupo ficam um embaixo do outro, como a tela era antes, mas ainda agrupados.

Aqui ficam só as contas (larguras, deslocamento, encaixe, efeito de suavização), para testar sem abrir janela.
Também fica aqui o `Ritmo`, que decide quanta animação o computador aguenta (completa, reduzida ou nenhuma), medindo
o tempo dos quadros. O desenho final do gráfico é sempre o mesmo; só o movimento até chegar nele muda.
"""
import sys

DISPOSICAO_LADO_A_LADO = "lado_a_lado"
DISPOSICAO_VERTICAL = "vertical"
CHAVE_CONFIG = "graficos_disposicao"
ROTULOS_DISPOSICAO = {
    DISPOSICAO_LADO_A_LADO: "Agrupados, arrastar para o lado",
    DISPOSICAO_VERTICAL: "Agrupados, de cima para baixo",
}

# Como cada gráfico é mostrado: desenhado na tela, com animação, ou como imagem simples (matplotlib), igual a antes.
ESTILO_ANIMADO = "animado"
ESTILO_IMAGEM = "imagem"
CHAVE_ESTILO = "graficos_estilo"
ROTULOS_ESTILO = {
    ESTILO_ANIMADO: "Animados (desenhados na tela)",
    ESTILO_IMAGEM: "Imagens simples, sem animação",
}

# Quanta animação o computador aguenta. No automático o programa mede os quadros e decide sozinho (classe Ritmo).
DESEMPENHO_AUTOMATICO = "automatico"
DESEMPENHO_COMPLETO = "completo"
DESEMPENHO_ECONOMICO = "economico"
CHAVE_DESEMPENHO = "graficos_desempenho"
ROTULOS_DESEMPENHO = {
    DESEMPENHO_AUTOMATICO: "Automático (recomendado): se adapta ao computador",
    DESEMPENHO_COMPLETO: "Completo: sempre com animação",
    DESEMPENHO_ECONOMICO: "Econômico: sem animação, o gráfico já aparece pronto",
}

LARGURA_MAX_CARD = 840     # largura máxima de um gráfico, em pixels lógicos (a mesma de antes)
ESPACO_ENTRE_CARDS = 16
ESPIADA = 56                # pedaço do próximo gráfico que fica à vista, para sugerir que dá para arrastar
LARGURA_MIN_CARD = 160
VELOCIDADE_DE_ARREMESSO = 500.0   # px/s: soltar mais rápido que isso passa para o gráfico seguinte
DURACAO_ENCAIXE = 0.28            # segundos
DURACAO_ENTRADA = 0.9             # segundos: tempo da animação com que cada gráfico "entra" (barras crescem, linhas se desenham)
ATRASO_ENTRE_CARDS = 0.12         # segundos: um gráfico começa um pouquinho depois do anterior
FRACAO_PARA_ANIMAR = 0.3          # o gráfico começa a animar quando pelo menos essa parte dele aparece na faixa


def disposicao_valida(valor):
    """Valor gravado na configuração -> disposição conhecida (padrão: lado a lado)."""
    return valor if valor in ROTULOS_DISPOSICAO else DISPOSICAO_LADO_A_LADO


def rotulo_para_disposicao(rotulo):
    for chave, texto in ROTULOS_DISPOSICAO.items():
        if texto == rotulo:
            return chave
    return DISPOSICAO_LADO_A_LADO


def estilo_valido(valor):
    """Valor gravado na configuração -> estilo conhecido (padrão: animado)."""
    return valor if valor in ROTULOS_ESTILO else ESTILO_ANIMADO


def rotulo_para_estilo(rotulo):
    for chave, texto in ROTULOS_ESTILO.items():
        if texto == rotulo:
            return chave
    return ESTILO_ANIMADO


def desempenho_valido(valor):
    """Valor gravado na configuração -> modo de desempenho conhecido (padrão: automático)."""
    return valor if valor in ROTULOS_DESEMPENHO else DESEMPENHO_AUTOMATICO


def rotulo_para_desempenho(rotulo):
    for chave, texto in ROTULOS_DESEMPENHO.items():
        if texto == rotulo:
            return chave
    return DESEMPENHO_AUTOMATICO


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


# ----------------------------------------------------------------------------- ritmo das animações
NIVEL_COMPLETO, NIVEL_REDUZIDO, NIVEL_SEM_ANIMACAO = 0, 1, 2
NOMES_NIVEL = {
    NIVEL_COMPLETO: "animação completa",
    NIVEL_REDUZIDO: "animação reduzida (mais curta, com menos quadros)",
    NIVEL_SEM_ANIMACAO: "sem animação (o gráfico aparece pronto)",
}
INTERVALO_QUADROS_MS = {NIVEL_COMPLETO: 16, NIVEL_REDUZIDO: 33, NIVEL_SEM_ANIMACAO: 16}   # 60 e 30 quadros por segundo
FATOR_DURACAO = {NIVEL_COMPLETO: 1.0, NIVEL_REDUZIDO: 0.6, NIVEL_SEM_ANIMACAO: 0.0}       # multiplica entrada e encaixe
AMOSTRAS_PARA_DECIDIR = 9          # quadros medidos antes de trocar de nível (a mediana ignora um tranco isolado)
AMOSTRAS_DE_INTERVALO = 5          # quantos intervalos entre quadros bastam para usar essa medida
LIMITE_CUSTO_S = {NIVEL_COMPLETO: 0.008, NIVEL_REDUZIDO: 0.025}   # trabalho de um quadro acima disso = computador lento
LIMITE_PERIODO_VEZES = 3.5         # tempo entre quadros acima de 3,5 vezes o previsto = a tela não acompanha
SM_REMOTESESSION = 0x1000          # GetSystemMetrics: 1 quando o programa roda em acesso remoto (Windows)
SPI_GETCLIENTAREAANIMATION = 0x1042   # SystemParametersInfo: 0 quando "mostrar animações" está desligado (Windows)


def sistema_pede_economia():
    """(nível, motivo) que o sistema pede ANTES de medir qualquer coisa.

    Só o Windows informa algo: acesso remoto (cada quadro viaja pela rede) e animações desligadas nas opções do
    sistema. Nos dois casos o programa começa com a animação reduzida, não sem animação: o gráfico continua
    animado, só mais curto e leve (quem quer o completo ou nenhum escolhe em Configurações). Qualquer falha na
    consulta vale por "nada a declarar".
    """
    if not sys.platform.startswith("win"):
        return NIVEL_COMPLETO, ""
    try:
        import ctypes
        usuario = ctypes.windll.user32
        if usuario.GetSystemMetrics(SM_REMOTESESSION):
            return NIVEL_REDUZIDO, "o programa está em acesso remoto (área de trabalho remota)"
        ligado = ctypes.c_int(1)
        if usuario.SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(ligado), 0) and not ligado.value:
            return NIVEL_REDUZIDO, "o Windows está com as animações desligadas"
    except Exception:  # noqa: BLE001  (sem ctypes, sem a função, sem permissão: não há o que declarar)
        pass
    return NIVEL_COMPLETO, ""


def _mediana(valores):
    return sorted(valores)[len(valores) // 2]


class Ritmo:
    """Quanta animação o computador aguenta: completa, reduzida ou nenhuma. Python puro (os testes dão as medidas).

    Três modos (Configurações do Mapa):

    * completo: sempre animação completa;
    * econômico: nunca anima, cada gráfico já aparece pronto;
    * automático (padrão): começa no que o sistema pede (`sistema_pede_economia`) e, a cada quadro de animação,
      recebe do desenho o custo do quadro e o tempo desde o quadro anterior. Se a MEDIANA dos últimos quadros passa
      do limite, desce um nível (completa, reduzida, nenhuma). Só desce, e só com quadros demais lentos de uma vez,
      então um tranco isolado (antivírus, outro programa) não estraga a animação. Não sobe sozinho: quem quiser
      voltar escolhe "Completo", ou reabre o programa.

    O gráfico final é igual em todos os níveis; o que muda é o caminho até ele: intervalo entre quadros (16 ou 33 ms),
    duração da animação (100% ou 60%) ou nenhuma.
    """

    def __init__(self, modo=DESEMPENHO_AUTOMATICO, nivel_do_sistema=NIVEL_COMPLETO, motivo_do_sistema=""):
        self._modo = desempenho_valido(modo)
        self._nivel_sistema, self._motivo_sistema = nivel_do_sistema, motivo_do_sistema
        self.quadros = 0               # quadros medidos desde o início (só para conferência)
        self.reiniciar()

    @classmethod
    def do_sistema(cls, modo=DESEMPENHO_AUTOMATICO):
        """Ritmo que já parte do que o sistema operacional informa (acesso remoto, animações desligadas)."""
        nivel, motivo = sistema_pede_economia()
        return cls(modo, nivel, motivo)

    def reiniciar(self):
        """Volta ao que o sistema pede e esquece as medidas."""
        self._nivel_auto = self._nivel_sistema
        self.motivo = self._motivo_sistema
        self._custos, self._periodos = [], []

    @property
    def modo(self):
        return self._modo

    @modo.setter
    def modo(self, novo):
        novo = desempenho_valido(novo)
        if novo != self._modo:
            self._modo = novo
            self.reiniciar()           # trocar de modo recomeça a medir do zero

    @property
    def nivel(self):
        if self._modo == DESEMPENHO_COMPLETO:
            return NIVEL_COMPLETO
        if self._modo == DESEMPENHO_ECONOMICO:
            return NIVEL_SEM_ANIMACAO
        return self._nivel_auto

    @property
    def anima(self):
        return self.nivel != NIVEL_SEM_ANIMACAO

    @property
    def intervalo_ms(self):
        """Espera entre dois quadros da animação."""
        return INTERVALO_QUADROS_MS[self.nivel]

    def duracao(self, segundos):
        """Duração de uma animação neste nível (0 quando não há animação)."""
        return segundos * FATOR_DURACAO[self.nivel]

    def registrar_quadro(self, custo, periodo=None):
        """Informa um quadro de animação: `custo` = segundos gastos desenhando; `periodo` = segundos desde o início
        do quadro anterior (None no primeiro quadro de uma sequência)."""
        self.quadros += 1
        if self._modo != DESEMPENHO_AUTOMATICO or self._nivel_auto >= NIVEL_SEM_ANIMACAO:
            return
        self._custos.append(max(0.0, float(custo)))
        if periodo is not None:
            self._periodos.append(max(0.0, float(periodo)))
        del self._custos[:-AMOSTRAS_PARA_DECIDIR]
        del self._periodos[:-AMOSTRAS_PARA_DECIDIR]
        if len(self._custos) < AMOSTRAS_PARA_DECIDIR:
            return
        nivel = self._nivel_auto
        custo_tipico = _mediana(self._custos)
        previsto = INTERVALO_QUADROS_MS[nivel] / 1000.0
        periodo_tipico = _mediana(self._periodos) if len(self._periodos) >= AMOSTRAS_DE_INTERVALO else None
        if custo_tipico > LIMITE_CUSTO_S[nivel]:
            motivo = (f"cada quadro levou {custo_tipico * 1000:.0f} ms "
                      f"(o ideal é menos de {LIMITE_CUSTO_S[nivel] * 1000:.0f} ms)")
        elif periodo_tipico is not None and periodo_tipico > LIMITE_PERIODO_VEZES * previsto:
            motivo = f"os quadros chegaram a cada {periodo_tipico * 1000:.0f} ms (o previsto era {previsto * 1000:.0f} ms)"
        else:
            return
        self._nivel_auto = nivel + 1
        self.motivo = motivo
        self._custos, self._periodos = [], []

    def descricao(self):
        """Frase simples para a janela de Configurações: o que o programa está fazendo agora."""
        if self._modo == DESEMPENHO_COMPLETO:
            return "Animação completa em qualquer computador."
        if self._modo == DESEMPENHO_ECONOMICO:
            return "Sem animação: cada gráfico aparece pronto. É o jeito mais leve para o computador."
        texto = "Agora: " + NOMES_NIVEL[self._nivel_auto] + "."
        if self.motivo:
            texto += " Motivo: " + self.motivo + "."
        return texto
