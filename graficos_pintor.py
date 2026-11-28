# -*- coding: utf-8 -*-
"""Pintor dos gráficos animados: desenha, num tk.Canvas, a cena que o graficos_nativos monta.

A cena é uma lista de formas simples (retângulo, polígono, linha, texto, círculo, arco). O pintor cria cada forma uma
única vez e, a cada quadro da animação, só atualiza o que mudou (posição, texto, visibilidade). Quem decide o que
desenhar é o graficos_nativos (Python puro, testado sem janela); aqui só se fala com o Tk.
"""

# O Tk refaz o contorno de cada polígono suave (os cantos arredondados) a CADA repintura, com `splinesteps` segmentos
# por curva (padrão do Tk: 12). Menos passos mexem em menos pontos, mas deslocam o contorno uma fração de pixel.
# tools/medir_desempenho_graficos.py mede o ganho de verdade, no Windows e no Linux, e o valor só muda se valer a pena.
PASSOS_DA_CURVA = 12


def familia_padrao(raiz):
    """A mesma letra do resto do programa (a do CustomTkinter); se não houver, a padrão do Tk."""
    import tkinter.font as tkfont     # aqui dentro: o módulo importa sem Tk (os testes trocam o tkinter por um falso)
    try:
        import customtkinter as ctk
        familia = ctk.CTkFont(size=12).actual("family")
        if familia:
            return familia
    except Exception:  # noqa: BLE001  (sem CustomTkinter, ou fonte indisponível: cai na padrão)
        pass
    try:
        return tkfont.nametofont("TkDefaultFont", root=raiz).actual("family")
    except Exception:  # noqa: BLE001
        return "TkDefaultFont"


class Fontes:
    """Fontes do Tk usadas nos gráficos. A mesma fonte mede e desenha o texto, então o que a cena
    calculou como "cabe" é o que aparece. As medidas ficam guardadas: medir texto é a parte mais cara."""

    def __init__(self, raiz, familia=None):
        self.raiz = raiz
        self.familia = familia or familia_padrao(raiz)
        self._fontes = {}
        self._medidas = {}

    def fonte(self, tam_px, negrito=False):
        import tkinter.font as tkfont
        chave = (max(1, int(round(tam_px))), bool(negrito))
        fonte = self._fontes.get(chave)
        if fonte is None:
            fonte = tkfont.Font(root=self.raiz, family=self.familia, size=-chave[0],
                                weight="bold" if negrito else "normal")
            self._fontes[chave] = fonte
        return fonte

    def medir(self, texto, tam_px, negrito=False):
        chave = (texto, int(round(tam_px)), bool(negrito))
        largura = self._medidas.get(chave)
        if largura is None:
            largura = self._medidas[chave] = float(self.fonte(tam_px, negrito).measure(texto))
        return largura


def _deslocar(coords, dx, dy):
    return tuple(v + (dx if i % 2 == 0 else dy) for i, v in enumerate(coords))


class PintorCanvas:
    """Desenha uma cena de graficos_nativos num canvas, deslocada em (dx, dy) (a posição do gráfico na faixa)."""

    def __init__(self, canvas, fontes, dicas=None, passos_da_curva=PASSOS_DA_CURVA):
        self.canvas = canvas
        self.fontes = fontes
        self.dicas = {} if dicas is None else dicas   # número do item no canvas -> texto do balão
        self.passos_da_curva = int(passos_da_curva)
        self.itens = []        # [(tipo, número do item)] na ordem da cena
        self._ultimo = []      # por item: [coordenadas da cena, coordenadas deslocadas, extras, visível] do último quadro
        self._desloc = None    # (dx, dy) do último desenho

    def desenhar(self, formas, dx=0.0, dy=0.0):
        tipos = [f["t"] for f in formas]
        if [t for t, _ in self.itens] != tipos:     # primeira vez (ou a cena mudou de forma): cria tudo
            self.apagar()
            for f in formas:
                self.itens.append((f["t"], self._criar(f, dx, dy)))
                self._ultimo.append(self._estado(f, dx, dy))
            self._desloc = (dx, dy)
            return
        mesmo = self._desloc == (dx, dy)
        self._desloc = (dx, dy)
        for i, (f, (_, item)) in enumerate(zip(formas, self.itens)):
            self._atualizar(self._ultimo[i], f, item, dx, dy, mesmo)

    def apagar(self):
        for _, item in self.itens:
            self.dicas.pop(item, None)
            self.canvas.delete(item)
        self.itens, self._ultimo, self._desloc = [], [], None

    # ------------------------------------------------------------------ criação
    def _criar(self, f, dx, dy):
        cv, t = self.canvas, f["t"]
        co = _deslocar(f["c"], dx, dy)
        if t == "ret":
            item = cv.create_rectangle(*co, fill=f["fill"], outline="", width=0)
        elif t == "poli":
            suave = bool(f.get("suave"))
            extra = {"splinesteps": self.passos_da_curva} if suave else {}
            item = cv.create_polygon(*co, fill=f["fill"], outline=f.get("outline") or "", smooth=suave, **extra)
        elif t == "linha":
            extra = {"dash": tuple(f["tracejado"])} if f.get("tracejado") else {}
            item = cv.create_line(*co, fill=f["fill"], width=f["largura"], capstyle="round", joinstyle="round", **extra)
        elif t == "texto":
            item = cv.create_text(*co, text=f["texto"], fill=f["fill"], anchor=f["ancora"],
                                  font=self.fontes.fonte(f["tam"], f["negrito"]))
        elif t == "oval":
            item = cv.create_oval(*co, fill=f["fill"], outline="")
        elif t == "arco":
            item = cv.create_arc(*co, start=f["inicio"], extent=f["extensao"], style="arc", outline=f["fill"],
                                 width=f["largura"])
        else:
            raise ValueError(f"forma desconhecida: {t!r}")
        if f.get("visivel") is False:
            cv.itemconfigure(item, state="hidden")
        if f.get("dica"):
            self.dicas[item] = f["dica"]
        return item

    # ------------------------------------------------------------------ atualização
    @staticmethod
    def _extras(f):
        t = f["t"]
        return (f["texto"],) if t == "texto" else (f["inicio"], f["extensao"]) if t == "arco" else ()

    @classmethod
    def _estado(cls, f, dx, dy):
        bruto = tuple(f["c"])
        return [bruto, _deslocar(bruto, dx, dy), cls._extras(f), f.get("visivel", True)]

    def _atualizar(self, antigo, f, item, dx, dy, mesmo_deslocamento):
        """Leva ao Tk só o que mudou desde o último quadro. As coordenadas da cena são comparadas ANTES de somar o
        deslocamento: a maioria das formas (moldura, grade, textos fixos) não muda de um quadro para o outro, e somar
        o deslocamento em Python é a parte mais cara da comparação."""
        cv = self.canvas
        bruto = tuple(f["c"])
        if not (mesmo_deslocamento and bruto == antigo[0]):
            antigo[0] = bruto
            deslocado = _deslocar(bruto, dx, dy)
            if deslocado != antigo[1]:
                antigo[1] = deslocado
                cv.coords(item, *deslocado)
        extras = self._extras(f)
        if extras != antigo[2]:
            antigo[2] = extras
            if f["t"] == "texto":
                cv.itemconfigure(item, text=f["texto"])
            else:
                cv.itemconfigure(item, start=f["inicio"], extent=f["extensao"])
        visivel = f.get("visivel", True)
        if visivel != antigo[3]:
            antigo[3] = visivel
            cv.itemconfigure(item, state="normal" if visivel else "hidden")
