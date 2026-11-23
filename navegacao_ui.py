"""Navegação v4: barra lateral compacta/expansível e pilha de páginas laterais."""
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk
import tema


class BarraLateral(ctk.CTkFrame):
    """Barra de 58 px que expande sobre o conteúdo até 250 px, com rolagem própria."""

    RECOLHIDA = 58
    EXPANDIDA = 250

    def __init__(self, app, secoes, config, rodape="", persistir=True):
        super().__init__(app, width=self.RECOLHIDA, corner_radius=0, fg_color=tema.VERDE_ESC)
        self.app = app
        self.rodape = rodape
        try:
            if persistir:
                from configuracoes_ui import _ler as _ler_preferencias, _salvar as _salvar_preferencias
                self._ler_preferencias = _ler_preferencias
                self._salvar_preferencias = _salvar_preferencias
                self.fixa = bool(_ler_preferencias().get("barra_fixa", False))
            else:
                self._ler_preferencias = lambda: {}
                self._salvar_preferencias = lambda _dados: False
                self.fixa = False
        except Exception:
            self._ler_preferencias = lambda: {}
            self._salvar_preferencias = lambda _dados: False
            self.fixa = False
        self.aberta = False
        self.ativo = None
        self.itens = {}
        self.titulos = []
        self._fora = 0
        self.pack_propagate(False)
        self.place(x=0, y=0, relheight=1.0)

        topo = ctk.CTkFrame(self, fg_color="transparent", height=52)
        topo.pack(fill="x")
        topo.pack_propagate(False)
        self.btn_toggle = ctk.CTkButton(
            topo, text="☰", width=40, height=36, fg_color="transparent",
            hover_color=tema.VERDE_HOVER, text_color="#FFFFFF",
            font=ctk.CTkFont(size=18, weight="bold"), command=self.alternar
        )
        self.btn_toggle.pack(side="left", padx=9, pady=8)
        self.lbl_titulo = ctk.CTkLabel(
            topo, text="", font=ctk.CTkFont(size=18, weight="bold"), text_color="#FFFFFF"
        )
        self.lbl_titulo.pack(side="left", padx=4)

        rod = ctk.CTkFrame(self, fg_color="transparent")
        rod.pack(side="bottom", fill="x")
        self.lbl_rodape = ctk.CTkLabel(
            rod, text="", font=ctk.CTkFont(size=10), text_color="#A9CBB8",
            justify="left", anchor="w", wraplength=self.EXPANDIDA - 28
        )
        self.lbl_rodape.pack(side="bottom", fill="x", padx=14, pady=(2, 10))
        self._adicionar_item(rod, *config, rodape=True)

        self.rolagem = ctk.CTkScrollableFrame(
            self, fg_color="transparent", scrollbar_button_color=tema.VERDE_HOVER,
            scrollbar_button_hover_color=tema.VERDE
        )
        self.rolagem.pack(fill="both", expand=True)
        for nome, itens in secoes:
            lbl = ctk.CTkLabel(
                self.rolagem, text=nome, font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#A9CBB8", anchor="w"
            )
            lbl.pack(fill="x", padx=14, pady=(14, 2))
            self.titulos.append((lbl, nome))
            for item in itens:
                self._adicionar_item(self.rolagem, *item)
        app.grid_columnconfigure(0, minsize=self.EXPANDIDA if self.fixa else self.RECOLHIDA)
        self.configure(width=self.EXPANDIDA if self.fixa else self.RECOLHIDA)
        app.bind("<Control-b>", self.alternar, add="+")
        app.bind("<apostrophe>", self._atalho_apostrofo, add="+")
        self._rotular(self.fixa)
        self.after(150, self._vigiar)

    def _adicionar_item(self, pai, icone, texto, comando, rodape=False):
        linha = ctk.CTkFrame(pai, fg_color="transparent", height=40)
        linha.pack(fill="x")
        linha.pack_propagate(False)
        marca = ctk.CTkFrame(linha, width=4, height=40, corner_radius=0, fg_color="transparent")
        marca.pack(side="left")
        botao = ctk.CTkButton(
            linha, text=icone, anchor="center", height=40, corner_radius=0,
            fg_color="transparent", hover_color=tema.VERDE_HOVER,
            text_color="#E7F3EB", font=ctk.CTkFont(size=17),
            command=lambda: (self.marcar(texto), comando())
        )
        botao.pack(side="left", fill="x", expand=True)
        self.itens[texto] = (marca, botao, icone)
        if rodape:
            self._item_config = texto

    def _rotular(self, aberta):
        self.aberta = aberta
        for texto, (_marca, botao, icone) in self.itens.items():
            botao.configure(
                text=f"  {icone}    {texto}" if aberta else icone,
                anchor="w" if aberta else "center",
                font=ctk.CTkFont(size=14 if aberta else 17, weight="bold" if aberta else "normal")
            )
        for lbl, nome in self.titulos:
            lbl.configure(text=nome if aberta else "•", anchor="w" if aberta else "center")
        self.lbl_titulo.configure(text="NutriLab" if aberta else "")
        self.lbl_rodape.configure(text=self.rodape if aberta else "©")

    def _abrir(self, aberta):
        self.configure(width=self.EXPANDIDA if aberta else self.RECOLHIDA)
        self._rotular(aberta)
        self.lift()

    def _vigiar(self):
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
                    if self._fora >= 2:
                        self._abrir(False)
            self.after(120, self._vigiar)
        except tk.TclError:
            pass

    def definir_fixa(self, fixa):
        self.fixa = bool(fixa)
        try:
            preferencias = self._ler_preferencias()
            preferencias["barra_fixa"] = self.fixa
            self._salvar_preferencias(preferencias)
        except Exception:
            pass
        self.app.grid_columnconfigure(
            0, minsize=self.EXPANDIDA if self.fixa else self.RECOLHIDA
        )
        self._abrir(self.fixa)

    def alternar(self, _evento=None):
        self.definir_fixa(not self.fixa)
        return "break"

    def _atalho_apostrofo(self, _evento=None):
        try:
            foco = self.app.focus_get()
            if foco is not None and foco.winfo_class() in {"Entry", "Text", "TEntry", "TCombobox"}:
                return None
        except tk.TclError:
            return None
        return self.alternar()

    def marcar(self, texto):
        self.ativo = texto
        for nome, (marca, botao, _icone) in self.itens.items():
            ativo = nome == texto
            marca.configure(fg_color=tema.LARANJA if ativo else "transparent")
            botao.configure(
                fg_color=tema.VERDE_HOVER if ativo else "transparent",
                text_color="#FFFFFF" if ativo else "#E7F3EB"
            )


class PilhaAbasLaterais(ctk.CTkFrame):
    """Mantém páginas abertas em sequência; ESC remove a última e restaura a anterior."""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self._nav = ctk.CTkScrollableFrame(self, width=132, fg_color=tema.FUNDO)
        self._conteudo = ctk.CTkFrame(self, fg_color=tema.FUNDO, corner_radius=8)
        self._conteudo.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self._conteudo.grid_rowconfigure(0, weight=1)
        self._conteudo.grid_columnconfigure(0, weight=1)
        self._base = ctk.CTkFrame(self._conteudo, fg_color="transparent")
        self._base.pack(fill="both", expand=True)
        self._abas = []
        self._ativa = self._base

    @property
    def pagina_atual(self):
        return self._ativa

    @property
    def quantidade(self):
        return len(self._abas)

    def abrir(self, titulo):
        self._ativa.pack_forget()
        if not self._abas:
            self._nav.grid(row=0, column=0, sticky="ns", padx=(0, 8))
            self._conteudo.grid_configure(column=1, columnspan=1)
        frame = ctk.CTkFrame(self._conteudo, fg_color="transparent")
        frame.pack(fill="both", expand=True)
        aba = {"titulo": str(titulo), "frame": frame, "botao": None}
        botao = ctk.CTkButton(
            self._nav, text=str(titulo), height=38, width=118,
            corner_radius=8, fg_color=tema.VERDE_CLARO,
            hover_color=tema.BORDA, text_color=tema.TEXTO,
            anchor="w", font=ctk.CTkFont(size=12),
            command=lambda alvo=aba: self.selecionar(alvo)
        )
        botao.pack(fill="x", padx=4, pady=3)
        aba["botao"] = botao
        self._abas.append(aba)
        self._ativa = frame
        self._atualizar_abas()
        return frame

    def selecionar(self, aba):
        if self._ativa is not None:
            self._ativa.pack_forget()
        aba["frame"].pack(fill="both", expand=True)
        self._ativa = aba["frame"]
        self._atualizar_abas()

    def fechar(self, frame):
        indice = next((i for i, aba in enumerate(self._abas) if aba["frame"] is frame), None)
        if indice is None:
            return self._ativa
        aba = self._abas.pop(indice)
        era_ativa = self._ativa is frame
        try:
            frame._fechando_painel = True
        except Exception:
            pass
        aba["botao"].destroy()
        frame.destroy()
        if era_ativa:
            self._ativa = self._abas[-1]["frame"] if self._abas else self._base
            self._ativa.pack(fill="both", expand=True)
        if not self._abas:
            self._nav.grid_remove()
            self._conteudo.grid_configure(column=0, columnspan=2)
        self._atualizar_abas()
        return self._ativa

    def fechar_ultima(self):
        if not self._abas:
            return self._base
        return self.fechar(self._abas[-1]["frame"])

    def limpar(self):
        for aba in self._abas:
            try:
                aba["frame"]._fechando_painel = True
            except Exception:
                pass
            aba["botao"].destroy()
            aba["frame"].destroy()
        self._abas.clear()
        self._ativa = self._base
        self._base.pack(fill="both", expand=True)
        self._nav.grid_remove()
        self._conteudo.grid_configure(column=0, columnspan=2)
        return self._base

    def _atualizar_abas(self):
        for aba in self._abas:
            ativo = aba["frame"] is self._ativa
            aba["botao"].configure(
                fg_color=tema.VERDE if ativo else tema.VERDE_CLARO,
                text_color="#FFFFFF" if ativo else tema.TEXTO
            )
