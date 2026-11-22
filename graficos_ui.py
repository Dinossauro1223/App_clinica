# -*- coding: utf-8 -*-
"""Tela dos gráficos agrupados (CustomTkinter).

Cada grupo (atendimentos, dieta, suplementos, doenças crônicas) vira uma seção com título. Dois jeitos de mostrar,
escolhidos em Configurações do Mapa (graficos_layout.DISPOSICAO_*):

* lado a lado: os gráficos do grupo ficam numa faixa que se arrasta com o mouse, com setas e um indicador de posição.
  Ao soltar, a faixa encaixa no gráfico mais próximo. Shift + roda do mouse e as setas do teclado também andam.
* de cima para baixo: os gráficos de cada grupo um embaixo do outro, como a tela era antes, mas ainda agrupados.

Cada gráfico é uma "carta" da faixa. Há dois tipos (graficos_layout.ESTILO_*):

* CardNativo: desenhado direto no canvas (graficos_nativos + graficos_pintor), com animação de entrada e um balão
  com o valor ao passar o mouse. É o padrão.
* CardImagem: imagem PNG do matplotlib, como era antes, sem animação.

As contas (larguras, encaixe, suavização) estão em graficos_layout.py e a geometria dos gráficos em
graficos_nativos.py; ambas são testadas sem janela. Aqui só há widgets.
"""
import io
import time
import tkinter as tk

import customtkinter as ctk

import graficos_layout as gl
import graficos_nativos as gn
from graficos_pintor import Fontes, PintorCanvas

VERDE, VERDE_HOVER, VERDE_ESC = "#4caf50", "#388e3c", "#1b5e20"
CINZA_BTN, CINZA_TEXTO, FUNDO_SECAO = "#b0bec5", "#546e7a", "#f7fbf8"
INTERVALO_QUADROS_MS = 16          # cerca de 60 quadros por segundo no encaixe e na animação de entrada
PAUSA_ENTRE_ROLAGENS = 0.25        # segundos: Shift + roda anda uma posição por vez, mesmo girando rápido
LIMIAR_ARRASTE = 3                 # pixels: menos que isso é um clique, não um arraste
FUNDO_DICA, TEXTO_DICA, TAM_DICA = "#263238", "#ffffff", 11   # balão que mostra o valor ao passar o mouse
_agora = time.perf_counter         # os testes trocam por um relógio falso


def escala_da_tela(widget):
    """Fator de escala do Windows (125%, 150%...) que o CustomTkinter aplica aos seus widgets."""
    rastreador = getattr(ctk, "ScalingTracker", None)
    if rastreador is not None:
        try:
            return max(0.5, float(rastreador.get_widget_scaling(widget)))
        except Exception:  # noqa: BLE001
            pass
    try:
        return max(1.0, float(widget.winfo_fpixels("1i")) / 96.0)
    except Exception:  # noqa: BLE001  (widget simulado, ou Tk sem essa informação)
        return 1.0


def abrir_png(png):
    from PIL import Image
    return Image.open(io.BytesIO(png)).convert("RGB")


def _redimensionar(imagem, largura, altura):
    from PIL import Image
    filtro = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
    return imagem.resize((int(largura), int(altura)), filtro)


def foto_tk(imagem_pil):
    """PIL -> imagem do Tk. Fica numa função própria para os testes trocarem por um simulador."""
    from PIL import ImageTk
    return ImageTk.PhotoImage(imagem_pil)


def _tolerante(metodo):
    """Evento de mouse/teclado nunca deve estourar erro na tela: um widget já destruído gera TclError."""
    def interno(self, *args):
        if self._morto:
            return None
        try:
            return metodo(self, *args)
        except tk.TclError:
            return None
    interno.__name__ = metodo.__name__
    return interno


class CardImagem:
    """Gráfico em imagem PNG (estilo "Imagens simples"): redimensionada para a faixa, sem animação."""
    animado = False
    pronto, p, inicio = True, 1.0, None     # mesma interface do CardNativo: já nasce "pronto", nunca anima

    def __init__(self, imagem):
        self.imagem = imagem      # PIL.Image no tamanho original
        self.x = self.largura = self.altura = 0

    def desenhar(self):
        """Imagem não muda quadro a quadro."""

    def _tamanho(self, faixa, largura):
        return gl.tamanho_do_card(self.imagem.width * faixa.escala, self.imagem.height * faixa.escala, largura)

    def altura_para(self, faixa, largura):
        return self._tamanho(faixa, largura)[1]

    def montar(self, faixa, x, largura, altura):
        self.x, self.largura, self.altura = x, largura, altura
        w, h = self._tamanho(faixa, largura)
        foto = foto_tk(_redimensionar(self.imagem, w, h))
        faixa.fotos.append(foto)      # o Tk apaga a imagem que ninguém referencia
        faixa.canvas.create_image(x, 0, image=foto, anchor="nw")


class CardNativo:
    """Gráfico desenhado direto no canvas, com animação de entrada (estilo "Animados")."""
    animado = True

    def __init__(self, spec):
        self.spec = spec          # dicionário do mapa_graficos (tipo, título, dados)
        self.p = 0.0              # progresso da entrada: 0 = só a moldura, 1 = completo
        self.inicio = None        # instante em que a entrada começa (None = ainda não apareceu na faixa)
        self.faixa = self.pintor = None
        self.x = self.largura = self.altura = 0

    @property
    def pronto(self):
        return self.p >= 1.0

    def altura_para(self, faixa, largura):
        return gn.altura_natural(self.spec, largura, faixa.fontes.medir, faixa.escala)

    def montar(self, faixa, x, largura, altura):
        self.faixa, self.x, self.largura, self.altura = faixa, x, largura, altura
        self.pintor = PintorCanvas(faixa.canvas, faixa.fontes, faixa.dicas)
        self.desenhar()

    def desenhar(self):
        f = self.faixa
        if f is None or self.pintor is None:      # ainda não foi montado na faixa
            return
        formas, _ = gn.construir(self.spec, self.largura, self.p, f.fontes.medir, f.escala, self.altura)
        self.pintor.desenhar(formas, self.x, 0)


class FaixaHorizontal:
    """Os gráficos de um grupo lado a lado num tk.Canvas que se arrasta com o mouse e encaixa ao soltar."""

    def __init__(self, pai, itens, cor_fundo=FUNDO_SECAO, escala=1.0, ao_mudar=None, ao_montar=None, fontes=None,
                 atraso=0.0, centralizar=False):
        # cada item é uma carta (CardNativo, CardImagem) ou uma PIL.Image (vira CardImagem)
        self.cards = [i if hasattr(i, "montar") else CardImagem(i) for i in itens]
        self.escala = max(0.5, float(escala))
        self.ao_mudar, self.ao_montar = ao_mudar, ao_montar
        self.atraso = float(atraso)           # segundos a esperar antes de animar o primeiro gráfico
        self.centralizar = centralizar        # um gráfico só, no meio da faixa (disposição de cima para baixo)
        self._fontes = fontes
        self.carrossel = None
        self.deslocamento, self.ativo = 0.0, 0   # `ativo` é o índice da posição de encaixe (não do gráfico)
        self.fotos = []                       # o Tk apaga a imagem que ninguém referencia: guardamos aqui
        self.dicas = {}                       # item do canvas -> texto do balão (preenchido pelo pintor)
        self._dica = None                     # (retângulo, texto) do balão, criado na primeira vez que aparece
        self._largura_montada = 0
        self._job_ajuste = self._job_animacao = self._job_entrada = None
        self._anim = self._arraste = None
        self._ultima_rolagem = 0.0
        self._morto = False
        c = self.canvas = tk.Canvas(pai, height=10, bg=cor_fundo, highlightthickness=0, bd=0, takefocus=1)
        c.bind("<Configure>", self._ao_configurar)
        c.bind("<ButtonPress-1>", self._pressionar)
        c.bind("<B1-Motion>", self._arrastar)
        c.bind("<ButtonRelease-1>", self._soltar)
        c.bind("<Motion>", self._mover)
        c.bind("<Leave>", lambda ev: self._esconder_dica())
        c.bind("<MouseWheel>", lambda ev: self._esconder_dica(), add="+")   # a tela rola por baixo do balão
        c.bind("<Shift-MouseWheel>", self._rolar)
        c.bind("<Shift-Button-4>", lambda ev: self._rolar_para(-1))   # Linux
        c.bind("<Shift-Button-5>", lambda ev: self._rolar_para(1))
        c.bind("<Left>", lambda ev: self.anterior())
        c.bind("<Right>", lambda ev: self.proximo())
        c.bind("<Destroy>", self._ao_destruir)

    @property
    def fontes(self):
        if self._fontes is None:
            self._fontes = Fontes(self.canvas)
        return self._fontes

    @property
    def imagens(self):
        """As imagens (PIL) dos gráficos que são imagem; os gráficos nativos não têm."""
        return [c.imagem for c in self.cards if isinstance(c, CardImagem)]

    # ------------------------------------------------------------------ montagem
    @_tolerante
    def _ao_configurar(self, ev):
        largura = int(getattr(ev, "width", 0))
        if largura < 50:
            return
        if self.carrossel is None:
            self.ajustar(largura)
        elif abs(largura - self._largura_montada) >= 12:   # a barra de rolagem da tela aparece e some: ignora o balanço
            if self._job_ajuste:
                self._cancelar(self._job_ajuste)
            self._job_ajuste = self.canvas.after(120, lambda: self.ajustar(largura))

    @_tolerante
    def ajustar(self, largura_px):
        """Desenha os gráficos para uma faixa de `largura_px` pixels (refeito quando a janela muda de largura)."""
        self._job_ajuste = None
        self._cancelar_animacao()
        self._cancelar_entrada()
        n = len(self.cards)
        card = gl.largura_do_card(largura_px, n, gl.LARGURA_MAX_CARD * self.escala, gl.ESPIADA * self.escala)
        self.carrossel = gl.Carrossel(n, card, largura_px, round(gl.ESPACO_ENTRE_CARDS * self.escala))
        self._largura_montada = largura_px
        c = self.canvas
        c.delete("all")
        self.fotos, self.dicas, self._dica = [], {}, None
        # todos os gráficos da faixa ficam com a altura do mais alto
        altura = max([1] + [cd.altura_para(self, card) for cd in self.cards])
        margem = round((largura_px - card) / 2) if self.centralizar and n == 1 else 0
        for i, cd in enumerate(self.cards):
            cd.montar(self, margem + round(self.carrossel.x_do_card(i)), card, altura)
        c.configure(height=altura, scrollregion=(0, 0, round(max(self.carrossel.largura_total, largura_px)), altura),
                    cursor=self._cursor_de_repouso())
        self.ativo = min(self.ativo, self.carrossel.n_posicoes - 1)
        self._definir_deslocamento(self.carrossel.x_da_posicao(self.ativo), notificar=False)
        self._agendar_entrada()     # o que já estava animando continua; o que apareceu agora é iniciado acima
        if self.ao_montar:
            self.ao_montar(self)

    @property
    def n_posicoes(self):
        return 1 if self.carrossel is None else self.carrossel.n_posicoes

    def cabe_sem_rolar(self):
        return self.carrossel is None or self.carrossel.cabe_sem_rolar()

    def _cursor_de_repouso(self):
        return "" if self.cabe_sem_rolar() else "hand2"

    # ------------------------------------------------------------------ posição
    def _definir_deslocamento(self, x, notificar=True):
        if self.carrossel is None:
            return
        x = self.carrossel.limitar(x)
        self.deslocamento = x
        total = self.carrossel.largura_total
        self.canvas.xview_moveto(x / total if total > 0 else 0.0)
        novo = self.carrossel.mais_proximo(x)
        if novo != self.ativo:
            self.ativo = novo
            if notificar and self.ao_mudar:
                self.ao_mudar(novo)
        self._iniciar_visiveis()

    def ir_para(self, posicao):
        """Anda (com animação) até a posição de encaixe `posicao`."""
        if self.carrossel is None or self._morto:
            return
        self._cancelar_animacao()
        alvo = self.carrossel.x_da_posicao(posicao)
        if abs(alvo - self.deslocamento) < 0.5:
            self._definir_deslocamento(alvo)
            return
        self._anim = (_agora(), self.deslocamento, alvo)
        self._passo_animacao()

    def anterior(self):
        self.ir_para(self.ativo - 1)

    def proximo(self):
        self.ir_para(self.ativo + 1)

    @_tolerante
    def _passo_animacao(self):
        if not self._anim:
            return
        inicio, de, para = self._anim
        t = (_agora() - inicio) / gl.DURACAO_ENCAIXE
        if t >= 1.0:
            self._anim = self._job_animacao = None
            self._definir_deslocamento(para)
            return
        self._definir_deslocamento(de + (para - de) * gl.suavizar(t))
        self._job_animacao = self.canvas.after(INTERVALO_QUADROS_MS, self._passo_animacao)

    # ------------------------------------------------------------------ animação de entrada
    def _iniciar_visiveis(self):
        """Um gráfico começa a animar na primeira vez em que boa parte dele aparece na faixa."""
        if self.carrossel is None or self._morto:
            return
        de, ate = self.deslocamento, self.deslocamento + self.carrossel.largura_visivel
        esperando = [cd for cd in self.cards if cd.animado and cd.inicio is None
                     and min(cd.x + cd.largura, ate) - max(cd.x, de) >= gl.FRACAO_PARA_ANIMAR * cd.largura]
        if not esperando:
            return
        agora = _agora()
        for k, cd in enumerate(esperando):
            cd.inicio = agora + self.atraso + k * gl.ATRASO_ENTRE_CARDS
        self._agendar_entrada()

    def _agendar_entrada(self):
        if self._job_entrada or self._morto:
            return
        if any(cd.animado and cd.inicio is not None and not cd.pronto for cd in self.cards):
            self._job_entrada = self.canvas.after(INTERVALO_QUADROS_MS, self._passo_entrada)

    @_tolerante
    def _passo_entrada(self):
        self._job_entrada = None
        agora = _agora()
        for cd in self.cards:
            if not cd.animado or cd.inicio is None or cd.pronto:
                continue
            p = max(0.0, min(1.0, (agora - cd.inicio) / gl.DURACAO_ENTRADA))
            if p != cd.p:
                cd.p = p
                cd.desenhar()
        self._agendar_entrada()

    def _cancelar_entrada(self):
        if self._job_entrada:
            self._cancelar(self._job_entrada)
        self._job_entrada = None

    # ------------------------------------------------------------------ balão com o valor
    def _dica_em(self, x, y):
        """Texto do balão do item sob o ponteiro (x e y em coordenadas do canvas), ou None."""
        c, raio = self.canvas, max(2, round(4 * self.escala))
        melhor, distancia = None, None
        for item in c.find_overlapping(x - raio, y - raio, x + raio, y + raio):
            texto = self.dicas.get(item)
            if not texto or c.itemcget(item, "state") == "hidden":
                continue
            x0, y0, x1, y1 = c.bbox(item)
            d = (x - (x0 + x1) / 2) ** 2 + (y - (y0 + y1) / 2) ** 2
            if distancia is None or d <= distancia:      # empate: o de cima (os itens vêm de baixo para cima)
                melhor, distancia = texto, d
        return melhor

    def _mostrar_dica(self, texto, x, y):
        c, e = self.canvas, self.escala
        tam, pad = round(TAM_DICA * e), round(6 * e)
        if self._dica is None:
            fonte = self.fontes.fonte(tam, False)
            self._dica = (c.create_rectangle(0, 0, 1, 1, fill=FUNDO_DICA, outline=""),
                          c.create_text(0, 0, text="", fill=TEXTO_DICA, anchor="nw", font=fonte))
        fundo, rotulo = self._dica
        w, h = self.fontes.medir(texto, tam, False) + 2 * pad, tam + 2 * pad
        esquerda, direita = c.canvasx(0), c.canvasx(c.winfo_width())
        bx = x + 14 * e
        if bx + w > direita:                           # não cabe à direita do ponteiro: vai para a esquerda
            bx = max(esquerda, x - 14 * e - w)
        by = y + 16 * e
        if by + h > c.canvasy(c.winfo_height()):       # nem embaixo: vai para cima
            by = max(c.canvasy(0), y - 16 * e - h)
        c.coords(fundo, bx, by, bx + w, by + h)
        c.coords(rotulo, bx + pad, by + pad)
        c.itemconfigure(rotulo, text=texto, state="normal")
        c.itemconfigure(fundo, state="normal")
        c.tag_raise(fundo)
        c.tag_raise(rotulo)

    def _esconder_dica(self):
        if self._dica is None or self._morto:
            return
        try:
            for item in self._dica:
                self.canvas.itemconfigure(item, state="hidden")
        except tk.TclError:
            pass

    @_tolerante
    def _mover(self, ev):
        if self._arraste or not self.dicas:
            return
        x, y = self.canvas.canvasx(ev.x), self.canvas.canvasy(ev.y)
        texto = self._dica_em(x, y)
        if texto:
            self._mostrar_dica(texto, x, y)
        else:
            self._esconder_dica()

    # ------------------------------------------------------------------ mouse e teclado
    @_tolerante
    def _pressionar(self, ev):
        if self.carrossel is None:
            return
        self.canvas.focus_set()
        self._cancelar_animacao()
        self._esconder_dica()
        self._arraste = {"x0": ev.x_root, "d0": self.deslocamento, "t": _agora(), "x": ev.x_root, "v": 0.0,
                         "mexeu": False}
        if not self.cabe_sem_rolar():
            self.canvas.configure(cursor="fleur")

    @_tolerante
    def _arrastar(self, ev):
        a = self._arraste
        if not a:
            return
        agora = _agora()
        dt = agora - a["t"]
        if dt > 0:   # velocidade do conteúdo (positiva = foi para a esquerda), suavizada para não oscilar
            a["v"] = 0.6 * a["v"] + 0.4 * (-(ev.x_root - a["x"]) / dt)
        a["x"], a["t"] = ev.x_root, agora
        if abs(ev.x_root - a["x0"]) > LIMIAR_ARRASTE:
            a["mexeu"] = True
        if a["mexeu"]:   # uma tremida de poucos pixels num clique não desloca a faixa do encaixe
            self._definir_deslocamento(a["d0"] - (ev.x_root - a["x0"]))

    @_tolerante
    def _soltar(self, ev):
        a, self._arraste = self._arraste, None
        self.canvas.configure(cursor=self._cursor_de_repouso())
        if not a or not a["mexeu"]:
            return
        velocidade = a["v"] if _agora() - a["t"] <= 0.08 else 0.0   # parou antes de soltar: sem arremesso
        self.ir_para(self.carrossel.depois_de_soltar(self.deslocamento, a["d0"], velocidade))

    def _rolar(self, ev):
        self._rolar_para(-1 if getattr(ev, "delta", 0) > 0 else 1)
        return "break"

    @_tolerante
    def _rolar_para(self, direcao):
        agora = _agora()
        if self.carrossel is not None and agora - self._ultima_rolagem >= PAUSA_ENTRE_ROLAGENS:
            self._ultima_rolagem = agora
            self.ir_para(self.ativo + direcao)
        return "break"

    # ------------------------------------------------------------------ limpeza
    def _cancelar(self, job):
        try:
            self.canvas.after_cancel(job)
        except tk.TclError:
            pass

    def _cancelar_animacao(self):
        if self._job_animacao:
            self._cancelar(self._job_animacao)
        self._anim = self._job_animacao = None

    def _ao_destruir(self, _ev=None):
        self._morto = True
        self._cancelar_animacao()
        self._cancelar_entrada()
        if self._job_ajuste:
            self._cancelar(self._job_ajuste)
            self._job_ajuste = None


class PainelGraficos:
    """Monta as seções dos grupos dentro de `pai`. Cada gráfico do grupo é um dicionário (desenhado na tela, com
    animação) ou bytes PNG (imagem, como antes): o conteúdo decide o tipo da carta."""

    def __init__(self, pai, grupos, disposicao=gl.DISPOSICAO_LADO_A_LADO, fontes=None):
        self.pai = pai
        self.disposicao = gl.disposicao_valida(disposicao)
        self.imagens = []        # uma por gráfico em imagem: PIL.Image (lado a lado) ou CTkImage (de cima para baixo)
        self.faixas = []         # FaixaHorizontal, na disposição lado a lado
        self.faixas_empilhadas = []   # um gráfico por faixa, na disposição de cima para baixo (estilo animado)
        self.controles = []      # setas e pontos de cada faixa (mesma ordem de `faixas`)
        self.escala = escala_da_tela(pai)
        self._fontes = fontes
        for grupo in grupos:
            self._criar_secao(grupo)

    @property
    def fontes(self):
        """Fontes dos gráficos animados, criadas só quando há algum (e repartidas entre todas as faixas)."""
        if self._fontes is None:
            self._fontes = Fontes(self.pai)
        return self._fontes

    # ------------------------------------------------------------------ seções
    def _criar_secao(self, grupo):
        itens = grupo["graficos"]
        lado_a_lado = self.disposicao == gl.DISPOSICAO_LADO_A_LADO
        quadro = ctk.CTkFrame(self.pai, fg_color=FUNDO_SECAO, corner_radius=10)
        quadro.pack(fill="x", padx=6, pady=(8, 10))
        cabecalho = ctk.CTkFrame(quadro, fg_color="transparent")
        cabecalho.pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkFrame(cabecalho, width=6, height=30, fg_color=grupo["cor"], corner_radius=3).pack(side="left",
                                                                                                padx=(0, 10))
        textos = ctk.CTkFrame(cabecalho, fg_color="transparent")
        textos.pack(side="left")
        ctk.CTkLabel(textos, text=grupo["titulo"], font=ctk.CTkFont(size=17, weight="bold"), text_color=VERDE_ESC,
                     anchor="w").pack(anchor="w")
        legenda = grupo.get("descricao") or ""
        if legenda:
            ctk.CTkLabel(textos, text=legenda, font=ctk.CTkFont(size=11), text_color=CINZA_TEXTO,
                         anchor="w").pack(anchor="w")
        if lado_a_lado:
            self._faixa(quadro, cabecalho, itens)
        else:
            self._empilhar(quadro, itens)

    def _carta(self, conteudo):
        if isinstance(conteudo, dict):
            return CardNativo(conteudo)
        imagem = abrir_png(conteudo)
        self.imagens.append(imagem)
        return CardImagem(imagem)

    def _faixa(self, quadro, cabecalho, itens):
        cartas = [self._carta(conteudo) for _, _, conteudo in itens]
        controles = _Controles(cabecalho)
        fontes = self.fontes if any(c.animado for c in cartas) else None
        faixa = FaixaHorizontal(quadro, cartas, FUNDO_SECAO, self.escala, controles.mostrar_posicao,
                                lambda f: controles.configurar(f), fontes=fontes)
        controles.ligar(faixa)
        faixa.canvas.pack(fill="x", padx=12, pady=(2, 12))
        self.faixas.append(faixa)
        self.controles.append(controles)

    def _empilhar(self, quadro, itens):
        for k, (_, _, conteudo) in enumerate(itens):
            if isinstance(conteudo, dict):    # desenhado na tela: uma faixa de um gráfico só, no meio
                faixa = FaixaHorizontal(quadro, [CardNativo(conteudo)], FUNDO_SECAO, self.escala, fontes=self.fontes,
                                        atraso=k * gl.ATRASO_ENTRE_CARDS, centralizar=True)
                faixa.canvas.pack(fill="x", padx=12, pady=6)
                self.faixas_empilhadas.append(faixa)
                continue
            img = abrir_png(conteudo)
            largura = min(img.width, gl.LARGURA_MAX_CARD)
            ci = ctk.CTkImage(light_image=img, dark_image=img, size=(largura, int(img.height * largura / img.width)))
            self.imagens.append(ci)
            ctk.CTkLabel(quadro, text="", image=ci).pack(pady=6)

    def ajustar_todas(self, largura_px):
        """Desenha todas as faixas para essa largura (usado nos testes; no programa o Tk avisa o tamanho)."""
        for faixa in self.faixas + self.faixas_empilhadas:
            faixa.ajustar(largura_px)


class _Controles:
    """Setas e pontos do cabeçalho de uma faixa. Só aparecem quando há mais de uma posição para onde ir."""

    def __init__(self, cabecalho):
        self.caixa = ctk.CTkFrame(cabecalho, fg_color="transparent")
        self.faixa = None
        self.visivel = False
        botao = dict(width=32, height=28, fg_color=VERDE, hover_color=VERDE_HOVER, text_color="#ffffff",
                     text_color_disabled="#ffffff", font=ctk.CTkFont(size=18, weight="bold"))
        self.b_ant = ctk.CTkButton(self.caixa, text="‹", command=lambda: self.faixa.anterior(), **botao)
        self.pontos = ctk.CTkLabel(self.caixa, text="", text_color=VERDE_ESC, font=ctk.CTkFont(size=13))
        self.b_prox = ctk.CTkButton(self.caixa, text="›", command=lambda: self.faixa.proximo(), **botao)
        self.b_ant.pack(side="left")
        self.pontos.pack(side="left", padx=8)
        self.b_prox.pack(side="left")

    def ligar(self, faixa):
        self.faixa = faixa

    def configurar(self, faixa):
        """Chamado depois de cada desenho da faixa: mostra ou esconde os controles e atualiza o estado."""
        precisa = faixa.n_posicoes > 1
        if precisa and not self.visivel:
            self.caixa.pack(side="right")
        elif not precisa and self.visivel:
            self.caixa.pack_forget()
        self.visivel = precisa
        self.mostrar_posicao(faixa.ativo)

    def mostrar_posicao(self, posicao):
        n = self.faixa.n_posicoes if self.faixa else 1
        self.pontos.configure(text=gl.pontos(n, posicao))
        self.b_ant.configure(state="disabled" if posicao <= 0 else "normal", fg_color=VERDE if posicao > 0 else CINZA_BTN)
        self.b_prox.configure(state="disabled" if posicao >= n - 1 else "normal",
                              fg_color=VERDE if posicao < n - 1 else CINZA_BTN)
