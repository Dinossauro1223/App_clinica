# -*- coding: utf-8 -*-
"""Tema do NutriLab (branco, verdes e laranja) e componentes compartilhados: barra lateral fluida,
balões de descrição, caixa de seleção que funciona com o teclado e preferências de tela."""
import json
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

BRANCO, FUNDO, BORDA = "#FFFFFF", "#F3F8F5", "#D6E6DC"
VERDE_ESC, VERDE, VERDE_HOVER, VERDE_CLARO = "#0F3D2E", "#1E7A4F", "#17633F", "#E3F3EA"
LARANJA, LARANJA_CLARO, LARANJA_TXT = "#F08A24", "#FFF1E0", "#9A4F00"
TEXTO, SUAVE, LATERAL_TXT, LATERAL_ATIVO = "#1B2B24", "#5F7368", "#D3EBDF", "#14513C"
RAIL, ABERTA = 58, 250  # largura da barra fina (só ícones) e da barra aberta


def fonte(tamanho=13, peso="normal"):
    return ctk.CTkFont(family="Segoe UI", size=tamanho, weight=peso)


class Preferencias:
    """Preferências de tela deste computador (JSON ao lado do programa): barra fixa, posição do divisor..."""

    def __init__(self, caminho):
        self.caminho, self.dados = caminho, {}
        try:
            with open(caminho, encoding="utf-8") as f:
                self.dados = json.load(f)
        except (OSError, ValueError):
            pass
        if not isinstance(self.dados, dict):
            self.dados = {}

    def get(self, chave, padrao=None):
        return self.dados.get(chave, padrao)

    def set(self, chave, valor):
        self.dados[chave] = valor
        try:
            with open(self.caminho, "w", encoding="utf-8") as f:
                json.dump(self.dados, f)
        except OSError:
            pass


class Dica:
    """Balão com a descrição da função, exibido quando o mouse descansa sobre o widget."""

    def __init__(self, widget, texto, atraso=600):
        self.w, self.texto, self.atraso, self.job, self.top = widget, texto, atraso, None, None
        for evento, funcao in (("<Enter>", self._agendar), ("<Leave>", self._ocultar), ("<ButtonPress>", self._ocultar)):
            widget.bind(evento, funcao, add="+")

    def _agendar(self, _=None):
        self._ocultar()
        self.job = self.w.after(self.atraso, self._mostrar)

    def _mostrar(self):
        self.job = None
        self.top = tk.Toplevel(self.w)
        self.top.wm_overrideredirect(True)
        tk.Label(self.top, text=self.texto, bg=VERDE_ESC, fg=BRANCO, font=("Segoe UI", 10), justify="left",
                 padx=10, pady=6, wraplength=300).pack()
        self.top.wm_geometry(f"+{self.w.winfo_rootx() + self.w.winfo_width() + 6}+{self.w.winfo_rooty() + 2}")

    def _ocultar(self, _=None):
        try:
            if self.job:
                self.w.after_cancel(self.job)
            if self.top:
                self.top.destroy()
        except tk.TclError:
            pass
        self.job = self.top = None


class Selecao(ctk.CTkComboBox):
    """Caixa de seleção: o Tab chega nela, as setas ↑/↓ trocam a opção e Enter abre a lista."""

    def __init__(self, master, values, command=None, width=140, **_estilo):
        super().__init__(master, values=values, command=command, state="readonly", border_color=BORDA,
                         fg_color=BRANCO, text_color=TEXTO, button_color=VERDE, button_hover_color=VERDE_HOVER,
                         dropdown_fg_color=BRANCO, dropdown_text_color=TEXTO, width=width)
        self._opcoes, self._ao_escolher = list(values), command
        self.set(self._opcoes[0])
        try:  # só API pública; se uma versão do customtkinter mudar isso, a caixa segue funcionando com o mouse
            self.bind("<Down>", lambda e: self._mover(1))
            self.bind("<Up>", lambda e: self._mover(-1))
            self.bind("<Return>", lambda e: self._abrir())
        except (AttributeError, ValueError, tk.TclError):
            pass

    def _mover(self, passo):
        atual = self._opcoes.index(self.get()) if self.get() in self._opcoes else 0
        novo = self._opcoes[max(0, min(len(self._opcoes) - 1, atual + passo))]
        self.set(novo)
        if self._ao_escolher:
            self._ao_escolher(novo)
        return "break"

    def _abrir(self):
        abrir = getattr(self, "_open_dropdown_menu", None)
        if abrir:
            abrir()
        return "break"


class BarraLateral(ctk.CTkFrame):
    """Barra lateral fluida: fica fina (só ícones) e abre sobre a tela ao passar o mouse. O botão ☰, Ctrl+B ou a
    tecla ' (fora de campos de texto) a deixam fixa. Cada opção mostra uma descrição ao pousar o mouse."""

    def __init__(self, app, titulo, secoes, config, rodape, prefs):
        super().__init__(app, width=RAIL, corner_radius=0, fg_color=VERDE_ESC)
        self.app, self.prefs, self.titulo, self.rodape = app, prefs, titulo, rodape
        self.itens, self.titulos, self.ativo, self._fora = {}, [], None, 0
        self.fixa, self.aberta = bool(prefs.get("barra_fixa", False)), False
        self.pack_propagate(False)
        topo = ctk.CTkFrame(self, fg_color="transparent", height=52)
        topo.pack(fill="x")
        topo.pack_propagate(False)
        btn = ctk.CTkButton(topo, text="☰", width=40, height=36, fg_color="transparent", hover_color=LATERAL_ATIVO,
                            text_color=BRANCO, font=fonte(18), command=self.alternar)
        btn.pack(side="left", padx=9, pady=8)
        Dica(btn, "Fixar ou soltar a barra lateral\nAtalhos: Ctrl+B ou a tecla ' (fora de campos de texto)")
        self.lbl_titulo = ctk.CTkLabel(topo, text="", font=fonte(18, "bold"), text_color=BRANCO)
        self.lbl_titulo.pack(side="left", padx=4)
        rod = ctk.CTkFrame(self, fg_color="transparent")  # rodapé fixo: Configurações é sempre a última opção
        rod.pack(side="bottom", fill="x")
        self.lbl_rodape = ctk.CTkLabel(rod, text="", font=fonte(10), text_color="#A9CBB8", justify="left", anchor="w",
                                       wraplength=ABERTA - 28)
        self.lbl_rodape.pack(side="bottom", fill="x", padx=14, pady=(2, 10))
        self._item(rod, *config)
        rolagem = ctk.CTkScrollableFrame(self, fg_color="transparent", scrollbar_button_color=LATERAL_ATIVO,
                                         scrollbar_button_hover_color=VERDE)
        rolagem.pack(fill="both", expand=True)
        for nome, itens in secoes:
            lbl = ctk.CTkLabel(rolagem, text=nome, font=fonte(11, "bold"), text_color="#A9CBB8", anchor="w")
            lbl.pack(fill="x", padx=14, pady=(14, 2))
            self.titulos.append((lbl, nome))
            for item in itens:
                self._item(rolagem, *item)
        app.grid_columnconfigure(0, minsize=ABERTA if self.fixa else RAIL)
        if self.fixa:
            self.configure(width=ABERTA)  # width vale só no construtor ou em configure(), nunca no place()
        self.place(x=0, y=0, relheight=1.0)
        self._rotular(self.fixa)
        self.lift()
        app.bind("<Control-b>", self.alternar)
        app.bind("<apostrophe>", self._atalho_apostrofo)
        self.after(150, self._vigiar)

    def _item(self, pai, icone, texto, descricao, comando):
        linha = ctk.CTkFrame(pai, fg_color="transparent", height=40)
        linha.pack(fill="x")
        linha.pack_propagate(False)
        marca = ctk.CTkFrame(linha, width=4, height=40, corner_radius=0, fg_color="transparent")
        marca.pack(side="left")
        botao = ctk.CTkButton(linha, text=icone, anchor="center", height=40, corner_radius=0, fg_color="transparent",
                              hover_color=LATERAL_ATIVO, text_color=LATERAL_TXT, font=fonte(15),
                              command=lambda: (self.marcar(texto), comando()))
        botao.pack(side="left", fill="x", expand=True)
        Dica(botao, f"{texto}\n{descricao}")
        self.itens[texto] = (marca, botao, icone)

    def _rotular(self, aberta):
        self.aberta = aberta
        for texto, (_, botao, icone) in self.itens.items():
            botao.configure(text=f"  {icone}    {texto}" if aberta else icone, anchor="w" if aberta else "center")
        for lbl, nome in self.titulos:
            lbl.configure(text=nome if aberta else "•", anchor="w" if aberta else "center")
        self.lbl_titulo.configure(text=self.titulo if aberta else "")
        self.lbl_rodape.configure(text=self.rodape if aberta else "©")

    def _abrir(self, aberta):
        self.configure(width=ABERTA if aberta else RAIL)
        self._rotular(aberta)
        self.lift()

    def _vigiar(self):
        """Abre ao passar o mouse e fecha quando ele sai (a menos que a barra esteja fixa)."""
        try:
            if not self.fixa:
                px, py = self.winfo_pointerxy()
                x0, y0 = self.winfo_rootx(), self.winfo_rooty()
                dentro = x0 <= px <= x0 + self.winfo_width() and y0 <= py <= y0 + self.winfo_height()
                if dentro:
                    self._fora = 0
                    if not self.aberta:
                        self._abrir(True)
                elif self.aberta:
                    self._fora += 1
                    if self._fora >= 2:  # não pisca quando o mouse só roça a borda
                        self._abrir(False)
            self.after(120, self._vigiar)
        except tk.TclError:
            pass  # janela fechada

    def definir_fixa(self, fixa):
        self.fixa = fixa
        self.prefs.set("barra_fixa", fixa)
        self.app.grid_columnconfigure(0, minsize=ABERTA if fixa else RAIL)
        self._abrir(fixa)

    def alternar(self, _=None):
        self.definir_fixa(not self.fixa)
        return "break"

    def _atalho_apostrofo(self, _):
        if isinstance(self.app.focus_get(), (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox)):
            return None  # quem digita d'água ou D'Ávila não aciona a barra
        return self.alternar()

    def marcar(self, texto):
        self.ativo = texto
        for nome, (marca, botao, _) in self.itens.items():
            on = nome == texto
            marca.configure(fg_color=LARANJA if on else "transparent")
            botao.configure(fg_color=LATERAL_ATIVO if on else "transparent", text_color=BRANCO if on else LATERAL_TXT)
