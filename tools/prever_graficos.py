# -*- coding: utf-8 -*-
"""Pré-visualização dos gráficos animados SEM abrir o programa: desenha a cena (graficos_nativos) com o Pillow.

É uma aproximação para conferir layout, textos e proporções com dados sintéticos; o Tk real desenha um pouco
diferente (fontes e serrilhado). Uso:

    python tools/prever_graficos.py PASTA_DE_SAIDA [largura_em_pixels ...]

Grava um PNG por gráfico e largura, no fim da animação (p = 1), e um deles no meio dela (p = 0.5) para conferir a
animação. Só usa dados sintéticos (os mesmos dos testes).
"""
import math
import os
import sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for pasta in (RAIZ, os.path.join(RAIZ, "tests")):
    if pasta not in sys.path:
        sys.path.insert(0, pasta)

import graficos_nativos as gn  # noqa: E402
import mapa_db as mdb  # noqa: E402
import mapa_graficos as mgr  # noqa: E402

SUPER = 2   # desenha em 2x e reduz (serrilhado menor)
ANCORAS = {"nw": "la", "w": "lm", "e": "rm", "n": "ma", "s": "ms", "center": "mm", "sw": "ls"}


def _fonte(tam, negrito):
    from PIL import ImageFont
    import matplotlib
    pasta = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
    return ImageFont.truetype(os.path.join(pasta, "DejaVuSans-Bold.ttf" if negrito else "DejaVuSans.ttf"),
                              max(1, int(round(tam))))


def medidor():
    cache = {}

    def medir(texto, tam, negrito):
        chave = (round(tam), bool(negrito))
        if chave not in cache:
            cache[chave] = _fonte(tam, negrito)
        return cache[chave].getlength(texto)
    return medir


def _tracejar(draw, pontos, cor, largura, padrao):
    sobra, ligado = 0.0, True
    atual = padrao[0] * largura
    for (x0, y0), (x1, y1) in zip(pontos, pontos[1:]):
        d = math.hypot(x1 - x0, y1 - y0)
        pos = 0.0
        while pos < d:
            passo = min(atual - sobra, d - pos)
            if ligado:
                ax, ay = x0 + (x1 - x0) * pos / d, y0 + (y1 - y0) * pos / d
                bx, by = x0 + (x1 - x0) * (pos + passo) / d, y0 + (y1 - y0) * (pos + passo) / d
                draw.line([(ax, ay), (bx, by)], fill=cor, width=max(1, int(largura)))
            pos += passo
            sobra += passo
            if sobra >= atual - 1e-9:
                ligado = not ligado
                sobra = 0.0
                atual = padrao[0 if ligado else 1] * largura


def desenhar(formas, largura, altura):
    from PIL import Image, ImageDraw
    s = SUPER
    img = Image.new("RGB", (int(largura * s), int(altura * s)), "#f7fbf8")
    d = ImageDraw.Draw(img)
    for f in formas:
        if f.get("visivel") is False:
            continue
        c, t = f["c"], f["t"]
        if t == "ret":
            d.rectangle([v * s for v in c], fill=f["fill"])
        elif t == "poli":
            if f.get("suave"):   # sempre um retângulo arredondado (gn.pontos_arredondados): o raio é o recuo do 1º ponto
                x0, y0, x1, y1 = min(c[0::2]), min(c[1::2]), max(c[0::2]), max(c[1::2])
                d.rounded_rectangle([x0 * s, y0 * s, x1 * s, y1 * s], radius=(c[0] - x0) * s, fill=f["fill"],
                                    outline=f["outline"] or None)
            else:
                d.polygon([(x * s, y * s) for x, y in zip(c[0::2], c[1::2])], fill=f["fill"],
                          outline=f["outline"] or None)
        elif t == "linha":
            pts = [(c[i] * s, c[i + 1] * s) for i in range(0, len(c), 2)]
            if f.get("tracejado"):
                _tracejar(d, pts, f["fill"], f["largura"] * s, f["tracejado"])
            else:
                d.line(pts, fill=f["fill"], width=max(1, int(round(f["largura"] * s))), joint="curve")
        elif t == "oval":
            d.ellipse([v * s for v in c], fill=f["fill"])
        elif t == "arco":
            x0, y0, x1, y1 = (v * s for v in c)
            ini, ext = f["inicio"], f["extensao"]
            d.arc([x0, y0, x1, y1], start=-ini, end=-(ini + ext), fill=f["fill"], width=max(1, int(f["largura"] * s)))
        elif t == "texto":
            fonte = _fonte(f["tam"] * s, f["negrito"])
            d.text((c[0] * s, c[1] * s), f["texto"], fill=f["fill"], font=fonte, anchor=ANCORAS[f["ancora"]])
    return img.resize((int(largura), int(altura)))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    saida = argv[1]
    larguras = [int(a) for a in argv[2:]] or [840]
    os.makedirs(saida, exist_ok=True)
    from test_mapa import novo_banco, popular_mes
    db = novo_banco()
    try:
        popular_mes(db, n_leitos=10)
        agg = mgr.agregar_mes(mdb.registros_do_mes(db, 2026, 10), 2026, 10)
    finally:
        os.remove(db)
    medir = medidor()
    graficos = mgr.especificar_todos(agg) + [("vazio", "Sem dados", mgr.especificar_todos(mgr.agregar_mes([], 2026, 2))[0][2])]
    for largura in larguras:
        natural = max(gn.altura_natural(spec, largura, medir) for _, _, spec in graficos[:-1])
        for chave, _, spec in graficos:
            for p in ((1.0, 0.5) if chave == "atendimentos_dia" else (1.0,)):
                formas, altura = gn.construir(spec, largura, p, medir, 1.0, natural)
                caminho = os.path.join(saida, f"{chave}_{largura}_p{int(p * 100):03d}.png")
                desenhar(formas, largura, altura).save(caminho)
                print(caminho)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
