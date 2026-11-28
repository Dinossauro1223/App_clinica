# -*- coding: utf-8 -*-
"""Mede quanto custa desenhar e animar os gráficos do Mapa NESTE computador. Só usa dados inventados.

    python tools/medir_desempenho_graficos.py              # medição completa (cerca de 30 segundos)
    python tools/medir_desempenho_graficos.py --rapido     # menos repetições (é o que o CI usa)
    python tools/medir_desempenho_graficos.py --sem-tk     # só a parte em Python puro, sem abrir janela
    python tools/medir_desempenho_graficos.py --json saida.json

O que mede:
  1. Python puro (sem janela): montar a cena de cada gráfico e o que o pintor gasta por quadro.
  2. Tk de verdade (se houver tela): o custo de UM QUADRO INTEIRO (cena + pedidos ao Tk + pintura na tela),
     comparando o pintor de antes (PintorAntigo, a referência) com o atual e a quantidade de segmentos das curvas.
  3. O que o modo automático escolheria neste computador (usa a mesma classe Ritmo do programa).

É uma medida, não um teste: não falha por lentidão. Se não houver Tk ou tela, a parte 2 é pulada e a saída diz isso.
Janela de teste: aparece por alguns segundos no canto da tela (a pintura só custa de verdade com a janela visível).
"""
import argparse
import json
import os
import platform
import statistics
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _pasta in (RAIZ, os.path.join(RAIZ, "tools")):
    if _pasta not in sys.path:
        sys.path.insert(0, _pasta)

import graficos_layout as gl  # noqa: E402
import graficos_nativos as gn  # noqa: E402
import graficos_pintor as gp  # noqa: E402

QUADROS = 30             # quadros de cada gráfico por repetição (progresso de 1/30 até 1)
LARGURA_DO_GRAFICO = 840


class PintorAntigo(gp.PintorCanvas):
    """Referência: o pintor de antes da otimização (comparava coordenadas JÁ deslocadas, forma por forma).

    Serve para dois fins: provar que o pintor atual pede ao Tk as mesmas coisas (tests/test_graficos_ui.py) e comparar
    os tempos aqui. Não é usado pelo programa."""

    def desenhar(self, formas, dx=0.0, dy=0.0):
        tipos = [f["t"] for f in formas]
        if [t for t, _ in self.itens] != tipos:
            self.apagar()
            for f in formas:
                self.itens.append((f["t"], self._criar(f, dx, dy)))
                self._ultimo.append(self._estado_antigo(f, dx, dy))
            return
        cv = self.canvas
        for i, (f, (_, item)) in enumerate(zip(formas, self.itens)):
            novo, antigo = self._estado_antigo(f, dx, dy), self._ultimo[i]
            if novo == antigo:
                continue
            self._ultimo[i] = novo
            if novo[0] != antigo[0]:
                cv.coords(item, *novo[0])
            if novo[1] != antigo[1]:
                if f["t"] == "texto":
                    cv.itemconfigure(item, text=f["texto"])
                else:
                    cv.itemconfigure(item, start=f["inicio"], extent=f["extensao"])
            if novo[2] != antigo[2]:
                cv.itemconfigure(item, state="normal" if novo[2] else "hidden")

    @staticmethod
    def _estado_antigo(f, dx, dy):
        t = f["t"]
        extra = (f["texto"],) if t == "texto" else (f["inicio"], f["extensao"]) if t == "arco" else ()
        return gp._deslocar(f["c"], dx, dy), extra, f.get("visivel", True)


class TelaContadora:
    """Canvas que só conta os pedidos: mede o trabalho em Python sem abrir janela."""

    def __init__(self):
        self.pedidos = 0
        self._n = 0

    def _criar(self, *a, **k):
        self.pedidos += 1
        self._n += 1
        return self._n

    create_rectangle = create_polygon = create_line = create_text = create_oval = create_arc = _criar

    def coords(self, *a):
        self.pedidos += 1

    def itemconfigure(self, *a, **k):
        self.pedidos += 1

    def delete(self, *a):
        pass


class FontesDeMentira:
    """Medida de texto sem Tk (cada letra mede 0,55 do tamanho): basta para medir o custo em Python."""

    def fonte(self, tam, negrito=False):
        return ("fonte", round(tam), bool(negrito))

    def medir(self, texto, tam, negrito=False):
        return len(texto) * tam * (0.6 if negrito else 0.55)


def graficos_sinteticos():
    """[(nome, especificação)] de todos os gráficos de um mês inventado (nenhum dado de paciente)."""
    import verificar_interface_tk as vit
    return [(nome, spec) for grupo in vit.especificacoes_sinteticas() for nome, _titulo, spec in grupo["graficos"]]


def estatisticas(valores):
    v = sorted(valores)
    return {"n": len(v), "media": statistics.fmean(v), "mediana": statistics.median(v),
            "p95": v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))], "max": v[-1]}


# --------------------------------------------------------------------------------------------- 1. Python puro
def medir_python(graficos, repeticoes):
    fontes = FontesDeMentira()
    progressos = [i / QUADROS for i in range(1, QUADROS + 1)]
    linhas = []
    for nome, spec in graficos:
        altura = gn.altura_natural(spec, LARGURA_DO_GRAFICO, fontes.medir)

        def construir(p):
            return gn.construir(spec, LARGURA_DO_GRAFICO, p, fontes.medir, 1.0, altura)[0]
        inicial, cenas = construir(0.0), [construir(p) for p in progressos]
        melhor = {"cena": 1e9, "novo": 1e9, "antigo": 1e9}
        pedidos = 0
        for _ in range(repeticoes):
            t0 = time.perf_counter()
            for p in progressos:
                construir(p)
            melhor["cena"] = min(melhor["cena"], (time.perf_counter() - t0) / QUADROS)
            for rotulo, classe in (("novo", gp.PintorCanvas), ("antigo", PintorAntigo)):
                tela = TelaContadora()
                pintor = classe(tela, fontes)
                pintor.desenhar(inicial)
                antes = tela.pedidos
                t0 = time.perf_counter()
                for cena in cenas:
                    pintor.desenhar(cena)
                melhor[rotulo] = min(melhor[rotulo], (time.perf_counter() - t0) / QUADROS)
                if rotulo == "novo":
                    pedidos = (tela.pedidos - antes) / QUADROS
        linhas.append({"grafico": nome, "formas": len(inicial), "cena_ms": melhor["cena"] * 1000,
                       "pintor_novo_ms": melhor["novo"] * 1000, "pintor_antigo_ms": melhor["antigo"] * 1000,
                       "pedidos_por_quadro": pedidos})
    return linhas


def imprimir_python(linhas):
    print("\n[1] Python puro (sem janela), por quadro de animação, melhor de várias repetições")
    print(f"    {'gráfico':<22}{'formas':>7}{'cena ms':>9}{'pintor atual ms':>17}{'pintor antigo ms':>18}{'pedidos ao Tk':>15}")
    for x in linhas:
        print(f"    {x['grafico']:<22}{x['formas']:>7}{x['cena_ms']:>9.3f}{x['pintor_novo_ms']:>17.3f}"
              f"{x['pintor_antigo_ms']:>18.3f}{x['pedidos_por_quadro']:>15.1f}")
    soma = lambda chave: sum(x[chave] for x in linhas)  # noqa: E731
    print(f"    {'SOMA (todos juntos)':<22}{soma('formas'):>7}{soma('cena_ms'):>9.3f}{soma('pintor_novo_ms'):>17.3f}"
          f"{soma('pintor_antigo_ms'):>18.3f}{soma('pedidos_por_quadro'):>15.1f}")
    if soma("pintor_antigo_ms") > 0:
        print(f"    O pintor atual gasta {100 * soma('pintor_novo_ms') / soma('pintor_antigo_ms'):.0f}% do tempo "
              f"de Python do pintor antigo, com os mesmos pedidos ao Tk.")


# --------------------------------------------------------------------------------------------- 2. Tk de verdade
VARIANTES = (
    ("antes (pintor antigo, curvas de 12 passos)", PintorAntigo, 12),
    ("agora (pintor atual, curvas de 12 passos)", gp.PintorCanvas, 12),
    ("pintor atual, curvas de 6 passos", gp.PintorCanvas, 6),
    ("pintor atual, curvas de 4 passos", gp.PintorCanvas, 4),
)


def abrir_tk():
    """(raiz, tk) ou (None, motivo)."""
    try:
        import tkinter as tk
    except Exception as e:  # noqa: BLE001
        return None, f"sem tkinter ({e})"
    try:
        try:
            import customtkinter as ctk
            raiz = ctk.CTk()
        except ImportError:
            raiz = tk.Tk()
    except tk.TclError as e:
        return None, f"sem tela para abrir a janela ({e})"
    return raiz, tk


def medir_tk(graficos, repeticoes):
    raiz, tk = abrir_tk()
    if raiz is None:
        return None, tk
    try:
        raiz.geometry("1000x640+0+0")
        raiz.update()
        canvas = tk.Canvas(raiz, width=LARGURA_DO_GRAFICO, height=400, highlightthickness=0, background="#ffffff")
        canvas.pack(anchor="nw")
        raiz.update()
        fontes = gp.Fontes(raiz)
        x11 = raiz.tk.call("tk", "windowingsystem") == "x11"

        def sincronizar():
            """Pintar no X11 é assíncrono: uma pergunta ao servidor só volta depois dele terminar o que já foi pedido."""
            if x11:
                canvas.winfo_pointerx()

        progressos = [i / QUADROS for i in range(1, QUADROS + 1)]
        preparados = []
        for nome, spec in graficos:
            altura = gn.altura_natural(spec, LARGURA_DO_GRAFICO, fontes.medir)
            preparados.append((nome, spec, altura))

        def passar_por_todos(classe, passos, amostras=None):
            for nome, spec, altura in preparados:
                canvas.delete("all")
                canvas.configure(height=altura)
                raiz.update()
                pintor = classe(canvas, fontes, {}, passos)
                pintor.desenhar(gn.construir(spec, LARGURA_DO_GRAFICO, 0.0, fontes.medir, 1.0, altura)[0])
                canvas.update_idletasks()
                sincronizar()
                for p in progressos:
                    t0 = time.perf_counter()
                    formas = gn.construir(spec, LARGURA_DO_GRAFICO, p, fontes.medir, 1.0, altura)[0]
                    pintor.desenhar(formas)
                    t1 = time.perf_counter()
                    canvas.update_idletasks()
                    sincronizar()
                    t2 = time.perf_counter()
                    if amostras is not None:
                        amostras["trabalho"].append((t1 - t0) * 1000)
                        amostras["total"].append((t2 - t0) * 1000)
                pintor.apagar()

        passar_por_todos(gp.PintorCanvas, 12)         # aquecimento: fontes, caches e primeira pintura
        resultado = {rotulo: {"trabalho": [], "total": []} for rotulo, _, _ in VARIANTES}
        for repeticao in range(repeticoes):
            giro = repeticao % len(VARIANTES)         # muda a ordem a cada repetição: nenhuma variante fica sempre no começo
            for rotulo, classe, passos in VARIANTES[giro:] + VARIANTES[:giro]:
                passar_por_todos(classe, passos, resultado[rotulo])
        informacoes = {"tk": tk.TkVersion, "sistema_de_janelas": raiz.tk.call("tk", "windowingsystem"),
                       "tela": f"{raiz.winfo_screenwidth()}x{raiz.winfo_screenheight()}",
                       "escala_tk": float(raiz.tk.call("tk", "scaling"))}
        return {"informacoes": informacoes,
                "variantes": {rotulo: {"trabalho": estatisticas(v["trabalho"]), "total": estatisticas(v["total"]),
                                       "amostras_trabalho_ms": v["trabalho"]} for rotulo, v in resultado.items()}}, None
    finally:
        try:
            raiz.destroy()
        except Exception:  # noqa: BLE001
            pass


def imprimir_tk(r):
    print(f"\n[2] Tk de verdade ({r['informacoes']['sistema_de_janelas']}, Tk {r['informacoes']['tk']}, "
          f"tela {r['informacoes']['tela']}): um quadro inteiro, em milissegundos")
    print("    trabalho = cena + pedidos ao Tk (é o que o ritmo automático mede); total = trabalho + pintura na tela")
    print(f"    {'variante':<46}{'trabalho':>10}{'':>8}{'total':>9}{'':>8}{'':>8}")
    print(f"    {'':<46}{'mediana':>10}{'p95':>8}{'mediana':>9}{'p95':>8}{'máximo':>8}")
    base = r["variantes"][VARIANTES[0][0]]["total"]["mediana"]
    for rotulo, _, _ in VARIANTES:
        v = r["variantes"][rotulo]
        t, g = v["trabalho"], v["total"]
        print(f"    {rotulo:<46}{t['mediana']:>10.3f}{t['p95']:>8.3f}{g['mediana']:>9.3f}{g['p95']:>8.3f}{g['max']:>8.3f}"
              f"   ({100 * g['mediana'] / base:.0f}% do antes)")


# --------------------------------------------------------------------------------------------- 3. o que o automático faria
def escolha_do_automatico(r):
    atual = r["variantes"][VARIANTES[1][0]]
    ritmo = gl.Ritmo()
    for ms in atual["amostras_trabalho_ms"]:
        ritmo.registrar_quadro(ms / 1000.0)
    limite = gl.LIMITE_CUSTO_S[gl.NIVEL_COMPLETO] * 1000
    total = atual["total"]["mediana"]
    print("\n[3] O que o modo automático escolheria neste computador")
    print(f"    trabalho por quadro (mediana): {atual['trabalho']['mediana']:.2f} ms, limite para reduzir: {limite:.0f} ms")
    print(f"    quadro inteiro com a pintura (mediana): {total:.2f} ms; a 60 quadros por segundo cada quadro tem 16,7 ms")
    print(f"    Resultado: {gl.NOMES_NIVEL[ritmo.nivel]}. {ritmo.motivo}".rstrip())
    return ritmo.nivel


def descrever_computador():
    nivel, motivo = gl.sistema_pede_economia()
    info = {"sistema": platform.platform(), "python": platform.python_version(), "processadores": os.cpu_count(),
            "o_sistema_pede": gl.NOMES_NIVEL[nivel] + (f" ({motivo})" if motivo else "")}
    print(f"Computador: {info['sistema']} | Python {info['python']} | {info['processadores']} processadores")
    print(f"O sistema operacional pede: {info['o_sistema_pede']}")
    print(f"Passos das curvas usados pelo programa: {gp.PASSOS_DA_CURVA}")
    return info


def main(argv=None):
    ap = argparse.ArgumentParser(description="Mede o custo dos gráficos do Mapa neste computador (dados inventados).")
    ap.add_argument("--rapido", action="store_true", help="menos repetições (usado no CI)")
    ap.add_argument("--sem-tk", action="store_true", help="só a parte em Python puro, sem abrir janela")
    ap.add_argument("--json", metavar="CAMINHO", help="grava os números num arquivo JSON")
    args = ap.parse_args(argv)

    print("Medição do desempenho dos gráficos (dados inventados; nada de paciente)")
    saida = {"computador": descrever_computador()}
    graficos = graficos_sinteticos()
    print(f"{len(graficos)} gráficos, {QUADROS} quadros cada, largura de {LARGURA_DO_GRAFICO} px")

    saida["python"] = medir_python(graficos, 3 if args.rapido else 7)
    imprimir_python(saida["python"])

    if args.sem_tk:
        print("\n[2] Tk de verdade: pulado (--sem-tk)")
    else:
        resultado, motivo = medir_tk(graficos, 2 if args.rapido else 4)
        if resultado is None:
            print(f"\n[2] Tk de verdade: PULOU, {motivo}")
        else:
            saida["tk"] = resultado
            imprimir_tk(resultado)
            saida["nivel_do_automatico"] = escolha_do_automatico(resultado)

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(saida, f, ensure_ascii=False, indent=1)
        print(f"\nNúmeros gravados em {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
