# -*- coding: utf-8 -*-
"""Tela dos gráficos agrupados (CustomTkinter).

Cada grupo (atendimentos, dieta, suplementos, doenças crônicas) vira uma seção com título. Dois jeitos de mostrar,
escolhidos em Configurações do Mapa (graficos_layout.DISPOSICAO_*):

* lado a lado: os gráficos do grupo ficam numa faixa que se arrasta com o mouse, com setas e um indicador de posição.
  Ao soltar, a faixa encaixa no gráfico mais próximo. Shift + roda do mouse e as setas do teclado também andam.
* de cima para baixo: os gráficos de cada grupo um embaixo do outro, como a tela era antes, mas ainda agrupados.

As contas (larguras, encaixe, suavização) estão em graficos_layout.py e são testadas sem janela. Aqui só há widgets.
"""
import io
import time
import tkinter as tk

import customtkinter as ctk

import graficos_layout as gl

VERDE, VERDE_HOVER, VERDE_ESC = "#4caf50", "#388e3c", "#1b5e20"
CINZA_BTN, CINZA_TEXTO, FUNDO_SECAO = "#b0bec5", "#546e7a", "#f7fbf8"
INTERVALO_QUADROS_MS = 16          # cerca de 60 quadros por segundo no encaixe
PAUSA_ENTRE_ROLAGENS = 0.25        # segundos: Shift + roda anda uma posição por vez, mesmo girando rápido
LIMIAR_ARRASTE = 3                 # pixels: menos que isso é um clique, não um arraste
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


class FaixaHorizontal:
    """Os gráficos de um grupo lado a lado num tk.Canvas que se arrasta com o mouse e encaixa ao soltar."""

    def __init__(self, pai, imagens, cor_fundo=FUNDO_SECAO, escala=1.0, ao_mudar=None, ao_montar=None):
        self.imagens = list(imagens)          # PIL.Image no tamanho original de cada gráfico
        self.escala = max(0.5, float(escala))
        self.ao_mudar, self.ao_montar = ao_mudar, ao_montar
        self.carrossel = None
        self.deslocamento, self.ativo = 0.0, 0   # `ativo` é o índice da posição de encaixe (não do gráfico)
        self.fotos = []                       # o Tk apaga a imagem que ninguém referencia: guardamos aqui
        self._largura_montada = 0
        self._job_ajuste = self._job_animacao = None
        self._anim = self._arraste = None
        self._ultima_rolagem = 0.0
        self._morto = False
        c = self.canvas = tk.Canvas(pai, height=10, bg=cor_fundo, highlightthickness=0, bd=0, takefocus=1)
        c.bind("<Configure>", self._ao_configurar)
        c.bind("<ButtonPress-1>", self._pressionar)
        c.bind("<B1-Motion>", self._arrastar)
        c.bind("<ButtonRelease-1>", self._soltar)
        c.bind("<Shift-MouseWheel>", self._rolar)
        c.bind("<Shift-Button-4>", lambda ev: self._rolar_para(-1))   # Linux
        c.bind("<Shift-Button-5>", lambda ev: self._rolar_para(1))
        c.bind("<Left>", lambda ev: self.anterior())
        c.bind("<Right>", lambda ev: self.proximo())
        c.bind("<Destroy>", self._ao_destruir)

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
        n = len(self.imagens)
        card = gl.largura_do_card(largura_px, n, gl.LARGURA_MAX_CARD * self.escala, gl.ESPIADA * self.escala)
        self.carrossel = gl.Carrossel(n, card, largura_px, round(gl.ESPACO_ENTRE_CARDS * self.escala))
        self._largura_montada = largura_px
        c = self.canvas
        c.delete("all")
        self.fotos = []
        altura = 1
        for i, img in enumerate(self.imagens):
            w, h = gl.tamanho_do_card(img.width * self.escala, img.height * self.escala, card)
            foto = foto_tk(_redimensionar(img, w, h))
            self.fotos.append(foto)
            c.create_image(round(self.carrossel.x_do_card(i)), 0, image=foto, anchor="nw")
            altura = max(altura, h)
        c.configure(height=altura, scrollregion=(0, 0, round(self.carrossel.largura_total), altura),
                    cursor=self._cursor_de_repouso())
        self.ativo = min(self.ativo, self.carrossel.n_posicoes - 1)
        self._definir_deslocamento(self.carrossel.x_da_posicao(self.ativo), notificar=False)
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

    # ------------------------------------------------------------------ mouse e teclado
    @_tolerante
    def _pressionar(self, ev):
        if self.carrossel is None:
            return
        self.canvas.focus_set()
        self._cancelar_animacao()
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
        if self._job_ajuste:
            self._cancelar(self._job_ajuste)
            self._job_ajuste = None


class PainelGraficos:
    """Monta as seções dos grupos dentro de `pai` e guarda as imagens para o Tk não as apagar."""

    def __init__(self, pai, grupos, disposicao=gl.DISPOSICAO_LADO_A_LADO):
        self.pai = pai
        self.disposicao = gl.disposicao_valida(disposicao)
        self.imagens = []        # uma por gráfico: PIL.Image (lado a lado) ou CTkImage (de cima para baixo)
        self.faixas = []         # FaixaHorizontal, na disposição lado a lado
        self.controles = []      # setas e pontos de cada faixa (mesma ordem de `faixas`)
        self.escala = escala_da_tela(pai)
        for grupo in grupos:
            self._criar_secao(grupo)

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

    def _faixa(self, quadro, cabecalho, itens):
        imagens = [abrir_png(png) for _, _, png in itens]
        self.imagens.extend(imagens)
        controles = _Controles(cabecalho)
        faixa = FaixaHorizontal(quadro, imagens, FUNDO_SECAO, self.escala, controles.mostrar_posicao,
                                lambda f: controles.configurar(f))
        controles.ligar(faixa)
        faixa.canvas.pack(fill="x", padx=12, pady=(2, 12))
        self.faixas.append(faixa)
        self.controles.append(controles)

    def _empilhar(self, quadro, itens):
        for _, _, png in itens:
            img = abrir_png(png)
            largura = min(img.width, gl.LARGURA_MAX_CARD)
            ci = ctk.CTkImage(light_image=img, dark_image=img, size=(largura, int(img.height * largura / img.width)))
            self.imagens.append(ci)
            ctk.CTkLabel(quadro, text="", image=ci).pack(pady=6)

    def ajustar_todas(self, largura_px):
        """Desenha todas as faixas para essa largura (usado nos testes; no programa o Tk avisa o tamanho)."""
        for faixa in self.faixas:
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
