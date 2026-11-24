# -*- coding: utf-8 -*-
"""Gráficos desenhados direto na tela, a partir da especificação de mapa_graficos (sem matplotlib e sem imagens).

Este módulo NÃO usa Tk: monta uma "cena" (lista de formas com coordenadas, cores e textos) para uma largura e um
progresso de animação (0 a 1). Quem desenha de verdade é graficos_ui.PintorCanvas. Assim a geometria inteira (margens,
eixos, barras, rosca, legenda, quebra de texto) é testada sem abrir janela.

Regras da cena (o pintor depende delas):

* a lista de formas tem sempre a MESMA ESTRUTURA (mesmos tipos, na mesma ordem) para qualquer progresso: só mudam
  coordenadas, textos e visibilidade. O pintor cria as formas uma vez e depois só as atualiza a cada quadro;
* todas as medidas saem em pixels da tela, já multiplicadas pela escala do Windows (125%, 150%...);
* cada forma é um dict: "t" (tipo), "c" (coordenadas) e os atributos do tipo.

    ret   c=(x0, y0, x1, y1)  fill
    poli  c=[x, y, ...]       fill, outline, suave   (retângulo arredondado: pontos_arredondados)
    linha c=[x, y, ...]       fill, largura, tracejado
    texto c=(x, y)            texto, fill, tam, negrito, ancora
    oval  c=(x0, y0, x1, y1)  fill
    arco  c=(x0, y0, x1, y1)  inicio, extensao, fill (cor do traço), largura

Qualquer forma pode ter "visivel" (False esconde) e "dica" (texto do balão ao passar o mouse).
"""
import math

import graficos_layout as gl

BRANCO, BORDA, GRADE, BASE = "#ffffff", "#dfeee3", "#e9f0ea", "#cfd8dc"
TEXTO, TEXTO_SUAVE, TITULO = "#37474f", "#78909c", "#1b5e20"

PAD = 18               # margem interna do cartão
TAM_TITULO, TAM_SUB, TAM_TEXTO, TAM_EIXO = 15, 11, 11, 10
TOPO_CONTEUDO = PAD + TAM_TITULO + 6 + TAM_SUB + 14   # onde começa o conteúdo, abaixo do título e do subtítulo
RAIO_CARTAO = 14


# ----------------------------------------------------------------------------- utilidades
def limitar01(t):
    return max(0.0, min(1.0, t))


def escala_agradavel(maximo, max_marcas=5):
    """(topo, passo) inteiros para um eixo de contagens: marcas em 0, passo, 2*passo ... topo (topo >= maximo)."""
    maximo = max(1, int(math.ceil(maximo)))
    potencia = 1
    while True:
        for base in (1, 2, 5):
            passo = base * potencia
            if math.ceil(maximo / passo) <= max_marcas:
                return int(math.ceil(maximo / passo)) * passo, passo
        potencia *= 10


def pontos_arredondados(x0, y0, x1, y1, r):
    """Pontos de um retângulo de cantos arredondados, para create_polygon(smooth=True) (arestas ficam retas)."""
    r = max(0.0, min(r, (x1 - x0) / 2.0, (y1 - y0) / 2.0))
    return [x0 + r, y0, x0 + r, y0, x1 - r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y0 + r, x1, y1 - r, x1, y1 - r,
            x1, y1, x1 - r, y1, x1 - r, y1, x0 + r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y1 - r, x0, y0 + r,
            x0, y0 + r, x0, y0]


def escurecer(cor, fator=0.78):
    """'#4caf50' -> versão mais escura (fator < 1)."""
    r, g, b = (int(cor[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(int(round(v * fator)) for v in (r, g, b))


def cortar_texto(medir, texto, tam, negrito, largura_max):
    """Corta o texto com reticências para caber em `largura_max` pixels."""
    if medir(texto, tam, negrito) <= largura_max:
        return texto
    while len(texto) > 1 and medir(texto + "…", tam, negrito) > largura_max:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def porcentagem(valor, total):
    return 100.0 * valor / total if total else 0.0


def _int_animado(valor, progresso):
    return int(round(valor * progresso))


# ----------------------------------------------------------------------------- cena
class _Cena:
    def __init__(self, largura, esc, medir, p):
        self.largura, self.esc, self.medir, self.p = float(largura), float(esc), medir, limitar01(p)
        self.itens = []

    def px(self, v):
        return v * self.esc

    def add(self, tipo, c, **atributos):
        self.itens.append({"t": tipo, "c": c, **atributos})
        return self.itens[-1]

    def texto(self, x, y, texto, tam, cor=TEXTO, negrito=False, ancora="nw", **extra):
        return self.add("texto", (x, y), texto=texto, tam=self.px(tam), fill=cor, negrito=negrito, ancora=ancora,
                        **extra)

    def moldura(self, spec, altura, extra_sub=""):
        """Fundo arredondado, título e subtítulo. Devolve a altura final do cartão."""
        pad = self.px(PAD)
        self.add("poli", pontos_arredondados(0.5, 0.5, self.largura - 0.5, altura - 0.5, self.px(RAIO_CARTAO)),
                 fill=BRANCO, outline=BORDA, suave=True)
        util = self.largura - 2 * pad
        self.texto(pad, pad, cortar_texto(self.medir, spec["titulo"], self.px(TAM_TITULO), True, util), TAM_TITULO,
                   TITULO, True)
        sub = spec["periodo"][:1].upper() + spec["periodo"][1:]
        if extra_sub:
            sub += "  ·  " + extra_sub
        self.texto(pad, pad + self.px(TAM_TITULO + 6), cortar_texto(self.medir, sub, self.px(TAM_SUB), False, util),
                   TAM_SUB, TEXTO_SUAVE)
        return altura

    def topo(self):
        return self.px(TOPO_CONTEUDO)


def _passo_dos_rotulos(c, slot, maior_texto):
    """De quantos em quantos itens do eixo X mostrar o rótulo para eles não se encostarem."""
    largura = c.medir(maior_texto, c.px(TAM_EIXO), False) + c.px(6)
    return max(1, int(math.ceil(largura / max(slot, 1.0))))


def _eixo_y(c, x0, x1, y_base, altura_plot, topo, passo):
    """Linhas de grade e números do eixo Y (contagens inteiras)."""
    marcas = list(range(0, topo + 1, passo))
    for m in marcas:
        y = y_base - altura_plot * m / topo
        c.add("linha", [x0, y, x1, y], fill=BASE if m == 0 else GRADE, largura=1, tracejado=None)
        c.texto(x0 - c.px(8), y, str(m), TAM_EIXO, TEXTO_SUAVE, False, "e")


def _largura_rotulos_y(c, topo):
    return max(c.medir(str(m), c.px(TAM_EIXO), False) for m in (0, topo)) + c.px(8)


def _rotulos_x(c, xs, x0, slot, y):
    passo = _passo_dos_rotulos(c, slot, str(max(xs)))
    for i, valor in enumerate(xs):
        c.texto(x0 + slot * (i + 0.5), y, str(valor), TAM_EIXO, TEXTO_SUAVE, False, "n",
                visivel=(i % passo == 0))


# ----------------------------------------------------------------------------- construtores por tipo
def _vazio(c, spec, minima):
    altura = max(c.px(150), minima)
    c.moldura(spec, altura)
    c.texto(c.largura / 2, c.topo() + (altura - c.topo()) / 2 - c.px(4), spec["mensagem"], TAM_TEXTO + 1,
            TEXTO_SUAVE, False, "center")
    return altura


def _barras_v(c, spec, minima):
    xs, ys, cor = spec["x"], spec["y"], spec["cor"]
    n = len(xs)
    topo, passo = escala_agradavel(max(ys))
    pad, e = c.px(PAD), c.esc
    x0 = pad + _largura_rotulos_y(c, topo)
    x1 = c.largura - pad
    y_cima = c.topo() + 16 * e                       # espaço para o número em cima da barra mais alta
    altura_plot = 190 * e
    y_base = y_cima + altura_plot
    altura = max(y_base + (6 + 14 + 4 + 12) * e + pad, minima)
    c.moldura(spec, altura, spec["rotulo_y"])
    _eixo_y(c, x0, x1, y_base, altura_plot, topo, passo)
    slot = (x1 - x0) / n
    _rotulos_x(c, xs, x0, slot, y_base + 6 * e)
    c.texto((x0 + x1) / 2, y_base + (6 + 14 + 2) * e, spec["rotulo_x"], TAM_EIXO, TEXTO_SUAVE, False, "n")
    largura_barra = max(2 * e, min(slot * 0.62, 34 * e))
    todos = slot >= c.medir("88", c.px(TAM_EIXO), True) + 6 * e
    maior = max(ys)
    for i, (x, v) in enumerate(zip(xs, ys)):
        pi = gl.suavizar(limitar01((c.p - 0.35 * i / n) / 0.65))
        h = altura_plot * v / topo * pi
        cx = x0 + slot * (i + 0.5)
        esquerda, direita = cx - largura_barra / 2, cx + largura_barra / 2
        r = min(4 * e, largura_barra / 2, h / 2)
        cor_barra = cor if v < maior else _escurecer_se_ha_mais_de_um(cor, ys)
        dica = spec["dicas"][i] if v else None
        visivel = h >= 0.5
        c.add("poli", pontos_arredondados(esquerda, y_base - h, direita, y_base, r), fill=cor_barra, outline="",
              suave=True, visivel=visivel, dica=dica)
        c.add("ret", (esquerda, y_base - min(h, r), direita, y_base), fill=cor_barra, visivel=visivel, dica=dica)
        c.texto(cx, y_base - h - 3 * e, str(_int_animado(v, pi)), TAM_EIXO, TEXTO, True, "s",
                visivel=bool(v) and pi > 0.02 and (todos or v == maior))
    return altura


def _escurecer_se_ha_mais_de_um(cor, valores):
    """A barra mais alta ganha um tom mais escuro (só faz sentido destacar quando os valores diferem)."""
    return escurecer(cor) if min(valores) != max(valores) else cor


def _linhas(c, spec, minima):
    xs, series = spec["x"], spec["series"]
    n = len(xs)
    pad, e = c.px(PAD), c.esc
    maximo = max(max(s["valores"]) for s in series)
    topo, passo = escala_agradavel(maximo)
    # legenda: uma linha de amostras (quebra para a de baixo se não couber)
    y_leg = c.topo()
    x_leg, linhas_leg = pad, 1
    posicoes = []
    for s in series:
        w = 22 * e + 6 * e + c.medir(s["nome"], c.px(TAM_TEXTO), False) + 18 * e
        if x_leg + w - 18 * e > c.largura - pad and x_leg > pad:
            x_leg, linhas_leg = pad, linhas_leg + 1
        posicoes.append((x_leg, y_leg + (linhas_leg - 1) * 18 * e))
        x_leg += w
    x0 = pad + _largura_rotulos_y(c, topo)
    x1 = c.largura - pad
    y_cima = c.topo() + linhas_leg * 18 * e + 12 * e
    altura_plot = 170 * e
    y_base = y_cima + altura_plot
    altura = max(y_base + (6 + 14 + 4 + 12) * e + pad, minima)
    c.moldura(spec, altura, spec["rotulo_y"])
    for s, (lx, ly) in zip(series, posicoes):
        c.add("linha", [lx, ly + 7 * e, lx + 22 * e, ly + 7 * e], fill=s["cor"], largura=2.2 * e,
              tracejado=(5, 3) if s["tracejado"] else None)
        c.texto(lx + 28 * e, ly + 7 * e, s["nome"], TAM_TEXTO, TEXTO, False, "w")
    _eixo_y(c, x0, x1, y_base, altura_plot, topo, passo)
    slot = (x1 - x0) / n
    _rotulos_x(c, xs, x0, slot, y_base + 6 * e)
    c.texto((x0 + x1) / 2, y_base + (6 + 14 + 2) * e, spec["rotulo_x"], TAM_EIXO, TEXTO_SUAVE, False, "n")
    # índice (fracionário) até onde a linha já foi desenhada; antes de começar (p = 0) nada aparece
    avanco = gl.suavizar(c.p) * (n - 1) if c.p > 0 else -1.0
    for s in series:
        pts = [(x0 + slot * (i + 0.5), y_base - altura_plot * v / topo) for i, v in enumerate(s["valores"])]
        trecho = []
        for i, (px_, py_) in enumerate(pts):
            if i <= avanco:
                trecho.append((px_, py_))
            elif i - 1 <= avanco and i > 0:               # ponta da linha, entre dois pontos
                f = avanco - (i - 1)
                a = pts[i - 1]
                trecho.append((a[0] + (px_ - a[0]) * f, a[1] + (py_ - a[1]) * f))
                break
        visivel = len(trecho) >= 2
        if not visivel:
            trecho = [pts[0], pts[0]]
        c.add("linha", [v for ponto in trecho for v in ponto], fill=s["cor"], largura=2.2 * e,
              tracejado=(5, 3) if s["tracejado"] else None, visivel=visivel)
        for i, ((px_, py_), v) in enumerate(zip(pts, s["valores"])):
            r = 2.6 * e
            c.add("oval", (px_ - r, py_ - r, px_ + r, py_ + r), fill=s["cor"], visivel=i <= avanco,
                  dica=f"{s['nome']}, dia {xs[i]}: {v}")
    return altura


def _roscas(c, spec, minima):
    blocos = spec["blocos"]
    pad, e = c.px(PAD), c.esc
    larg_bloco = (c.largura - 2 * pad) / len(blocos)
    raio = max(10 * e, min(66 * e, larg_bloco / 2 - 14 * e))
    espessura = raio * 0.36
    mais_linhas = max(len(b["itens"]) for b in blocos)
    altura = max(c.topo() + (22 + 8) * e + 2 * raio + 12 * e + mais_linhas * 18 * e + pad, minima)
    c.moldura(spec, altura)
    for k, bloco in enumerate(blocos):
        cx = pad + larg_bloco * (k + 0.5)
        cy = c.topo() + (22 + 8) * e + raio
        c.texto(cx, c.topo(), cortar_texto(c.medir, bloco["nome"], c.px(TAM_TEXTO + 1), True, larg_bloco - 8 * e),
                TAM_TEXTO + 1, TITULO, True, "n")
        itens = bloco["itens"]
        total = sum(i["valor"] for i in itens)
        if not itens or total <= 0:
            c.texto(cx, cy, "Sem dados", TAM_TEXTO, TEXTO_SUAVE, False, "center")
            continue
        varrido = 360.0 * gl.suavizar(c.p)
        r_meio = raio - espessura / 2
        acumulado, maior = 0.0, max(itens, key=lambda i: i["valor"])
        for i in itens:
            fatia = 360.0 * i["valor"] / total
            vis = max(0.0, min(fatia, varrido - acumulado))
            folga = 1.2 if len(itens) > 1 else 0.0       # frestinha branca entre as fatias
            c.add("arco", (cx - r_meio, cy - r_meio, cx + r_meio, cy + r_meio), inicio=90.0 - acumulado - folga / 2,
                  extensao=-max(0.0, vis - folga) if vis > folga else -0.01, fill=i["cor"], largura=espessura,
                  visivel=vis > folga,
                  dica=f"{i['rotulo']}: {i['valor']} ({porcentagem(i['valor'], total):.0f}%)")
            acumulado += fatia
        pct = porcentagem(maior["valor"], total) * gl.suavizar(c.p)
        c.texto(cx, cy - 6 * e, f"{pct:.0f}%", 16, TEXTO, True, "center")
        c.texto(cx, cy + 11 * e, cortar_texto(c.medir, maior["rotulo"], c.px(TAM_EIXO), False,
                                              2 * (raio - espessura) - 6 * e), TAM_EIXO, TEXTO_SUAVE, False, "center")
        # legenda: quadradinho colorido, nome e valor
        linhas = [f"{i['rotulo']}  {i['valor']}" for i in itens]
        larg_leg = max(c.medir(t, c.px(TAM_EIXO + 1), False) for t in linhas) + 15 * e
        lx = cx - larg_leg / 2
        for j, (i, texto) in enumerate(zip(itens, linhas)):
            ly = cy + raio + 12 * e + j * 18 * e
            c.add("ret", (lx, ly + 3 * e, lx + 9 * e, ly + 12 * e), fill=i["cor"])
            c.texto(lx + 15 * e, ly + 7.5 * e, texto, TAM_EIXO + 1, TEXTO, False, "w")
    return altura


def _barras_h(c, spec, minima):
    itens, total, cor = spec["itens"], spec["total"], spec["cor"]
    n = len(itens)
    pad, e = c.px(PAD), c.esc
    altura_linha = 32 * e
    maior = max(max(i["valor"] for i in itens), 1)
    rotulo_valor = f"{maior}  (100%)"
    largura_valor = c.medir(rotulo_valor, c.px(TAM_TEXTO), True) + 10 * e
    util = c.largura - 2 * pad
    largura_nome = min(max(c.medir(i["nome"], c.px(TAM_TEXTO + 1), False) for i in itens) + 16 * e, util * 0.42)
    x0 = pad + largura_nome
    largura_max = max(40 * e, c.largura - pad - largura_valor - x0)
    y0 = c.topo() + 4 * e
    altura = max(y0 + n * altura_linha + 8 * e + pad, minima)
    c.moldura(spec, altura, spec["rotulo_x"])
    c.add("linha", [x0, y0, x0, y0 + n * altura_linha], fill=BASE, largura=1, tracejado=None)
    maior_pos = max(range(n), key=lambda k: itens[k]["valor"])
    for k, item in enumerate(itens):
        v = item["valor"]
        pi = gl.suavizar(limitar01((c.p - 0.4 * k / n) / 0.6))
        yc = y0 + altura_linha * (k + 0.5)
        h = 14 * e
        w = largura_max * v / maior * pi
        c.texto(pad, yc, cortar_texto(c.medir, item["nome"], c.px(TAM_TEXTO + 1), False, largura_nome - 10 * e),
                TAM_TEXTO + 1, TEXTO, False, "w")
        cor_barra = item.get("cor") or (_escurecer_se_ha_mais_de_um(cor, [i["valor"] for i in itens]) if k == maior_pos else cor)
        dica = f"{item['nome']}: {v} ({porcentagem(v, total):.0f}%)"
        visivel = w >= 0.5
        r = min(5 * e, h / 2, w / 2)
        c.add("poli", pontos_arredondados(x0, yc - h / 2, x0 + w, yc + h / 2, r), fill=cor_barra, outline="",
              suave=True, visivel=visivel, dica=dica)
        c.add("ret", (x0, yc - h / 2, x0 + min(w, r), yc + h / 2), fill=cor_barra, visivel=visivel, dica=dica)
        c.texto(x0 + w + 8 * e, yc, f"{_int_animado(v, pi)}  ({porcentagem(v, total) * pi:.0f}%)", TAM_TEXTO, TEXTO,
                True, "w", visivel=pi > 0.02)
    return altura


_CONSTRUTORES = {"vazio": _vazio, "barras_v": _barras_v, "linhas": _linhas, "roscas": _roscas,
                 "barras_h": _barras_h}


# ----------------------------------------------------------------------------- interface
def construir(spec, largura, p, medir, esc=1.0, altura_minima=0):
    """Cena do gráfico `spec` para um cartão de `largura` pixels, no progresso `p` (0 a 1) da animação.

    `medir(texto, tam_px, negrito)` devolve a largura do texto em pixels. Devolve (formas, altura_do_cartao).
    """
    c = _Cena(largura, esc, medir, p)
    altura = _CONSTRUTORES[spec["tipo"]](c, spec, altura_minima)
    return c.itens, altura


def altura_natural(spec, largura, medir, esc=1.0):
    """Altura que o cartão precisa (sem animação). Usada para igualar a altura dos cartões de um grupo."""
    return construir(spec, largura, 1.0, medir, esc)[1]
