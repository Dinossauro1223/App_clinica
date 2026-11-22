# -*- coding: utf-8 -*-
"""Tela inicial do NutriLab composta por camadas SVG rasterizadas com alpha.

O Canvas mantém as ilustrações no fundo, anima folhas independentes e deixa
wordmark, assinatura institucional, opções e créditos em camadas próprias.
"""
import json
import math
import os
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageTk


FUNDO = "#F8FCF5"
LARGURA_BASE = 1533
ALTURA_BASE = 1026


class TelaBoasVindas:
    def __init__(self, master, ao_entrar):
        self.master = master
        self.ao_entrar = ao_entrar
        self.frame = ctk.CTkFrame(master, fg_color=FUNDO, corner_radius=0)
        self.canvas = tk.Canvas(self.frame, bg=FUNDO, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.pasta = os.path.join(self._base_path(), "identidade_camadas")
        self.imagens = {}
        self.folhas = []
        self.itens_folhas = []
        self._fotos = []
        self._opcoes_visiveis = False
        self._opcoes_widgets = []
        self._opcoes_janelas = []
        self._ativo = True
        self._timer = None
        self._escala = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self._carregar_imagens()
        self.canvas.bind("<Configure>", self._redimensionar)
        self.canvas.bind("<Button-1>", self._clicar)
        self._timer = self.frame.after(90, self._animar)

    @staticmethod
    def _base_path():
        import sys
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return sys._MEIPASS
        return os.path.dirname(os.path.abspath(__file__))

    def _carregar_imagens(self):
        nomes = (
            "decoracao_inferior", "arco", "haste_folhas", "maca", "dna",
            "frasco", "wordmark", "assinatura", "facisa_ufrn",
            "topo_temas", "boas_vindas",
        )
        for nome in nomes:
            caminho = os.path.join(self.pasta, nome + ".png")
            if os.path.isfile(caminho):
                self.imagens[nome] = Image.open(caminho).convert("RGBA")
        manifesto = os.path.join(self.pasta, "folhas.json")
        if os.path.isfile(manifesto):
            with open(manifesto, "r", encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
            for item in dados:
                caminho = os.path.join(self.pasta, item["arquivo"])
                if os.path.isfile(caminho):
                    imagem = Image.open(caminho).convert("RGBA")
                    self.folhas.append({
                        "imagem": imagem,
                        "x": 815 + item["bbox"][0] * .95,
                        "y": 120 + item["bbox"][1] * .95,
                        "largura": imagem.width * .475,
                        "altura": imagem.height * .475,
                        "fase": len(self.folhas) * 1.7,
                        "velocidade": .55 + len(self.folhas) * .13,
                        "item": None,
                    })

    def _foto(self, imagem, largura, altura):
        largura, altura = max(1, int(largura)), max(1, int(altura))
        redimensionada = imagem.resize((largura, altura), Image.Resampling.LANCZOS)
        foto = ImageTk.PhotoImage(redimensionada)
        self._fotos.append(foto)
        return foto

    def _imagem(self, nome, x, y, largura, altura, tags=()):
        imagem = self.imagens.get(nome)
        if imagem is None:
            return None
        foto = self._foto(imagem, largura * self._escala, altura * self._escala)
        return self.canvas.create_image(
            self._px(x), self._py(y), image=foto, anchor="nw", tags=tags
        )

    def _px(self, x):
        return self._offset_x + x * self._escala

    def _py(self, y):
        return self._offset_y + y * self._escala

    def _redimensionar(self, event):
        if event.width < 2 or event.height < 2:
            return
        self._escala = min(event.width / LARGURA_BASE, event.height / ALTURA_BASE)
        self._offset_x = (event.width - LARGURA_BASE * self._escala) / 2
        self._offset_y = (event.height - ALTURA_BASE * self._escala) / 2
        self._desenhar_cena()

    def _desenhar_cena(self):
        self.canvas.delete("all")
        self._fotos = []
        self.itens_folhas = []
        self._opcoes_janelas = []

        # Camadas de fundo: decoração, arco e haste; cada folha é uma imagem RGBA.
        self._imagem("decoracao_inferior", 0, 0, 1533, 1026)
        self._imagem("arco", 815, 120, 570, 570)
        self._imagem("haste_folhas", 815, 120, 399, 380)

        # Folhas em imagens RGBA independentes, inseridas antes dos elementos de marca.
        for folha in self.folhas:
            foto = self._foto(
                folha["imagem"],
                folha["largura"] * self._escala,
                folha["altura"] * self._escala,
            )
            folha["item"] = self.canvas.create_image(
                self._px(folha["x"]), self._py(folha["y"]),
                image=foto, anchor="nw", tags=("folha-animada",)
            )
            self.itens_folhas.append(folha["item"])

        # Primeiro plano: maçã, wordmark, assinatura e marcas institucionais.
        self._imagem("maca", 929, 386, 378, 324)
        self._imagem("dna", 1238, 130, 132, 253)
        self._imagem("frasco", 1290, 424, 204, 265)
        self._imagem("boas_vindas", 108, 250, 520, 100)
        self._imagem("wordmark", 100, 345, 759, 159)
        self._imagem("assinatura", 110, 458, 990, 135)
        self._imagem("facisa_ufrn", 108, 655, 403, 81)
        self._imagem("topo_temas", 1090, 20, 440, 80)

        self._item_instrucao = self.canvas.create_text(
            self._px(766), self._py(974), text="Clique em qualquer lugar para continuar",
            fill="#287B58", font=("Segoe UI", max(10, int(15 * self._escala)), "bold"),
            anchor="center"
        )
        self.canvas.create_text(
            self._px(1500), self._py(1005),
            text="© 2026 Neis Bila de Alencar. Todos os direitos reservados.",
            fill="#52746A", font=("Segoe UI", max(8, int(10 * self._escala))),
            anchor="se"
        )
        if self._opcoes_visiveis:
            self._posicionar_opcoes()

    def _clicar(self, event=None):
        if not self._opcoes_visiveis:
            self.mostrar_opcoes()

    def mostrar_opcoes(self):
        if not self._ativo or self._opcoes_visiveis:
            return
        self._opcoes_visiveis = True
        self.canvas.delete(self._item_instrucao)
        self.canvas.create_text(
            self._px(766), self._py(760), text="Escolha por onde deseja começar",
            fill="#064D3C",
            font=("Segoe UI", max(14, int(23 * self._escala)), "bold"),
            anchor="center"
        )
        opcoes = (
            ("Gestão Clínica", "Pacientes, consultas, exames e avaliações", self._comando("clinica")),
            ("Nutrição", "Mapa nutricional, gráficos e suplementos", self._comando("nutricao")),
            ("Gestão Alimentar", "Almoxarifado, copa e fichas de consumo", self._comando("alimentar")),
        )
        for titulo, descricao, comando in opcoes:
            cartao = ctk.CTkFrame(self.frame, fg_color="transparent", corner_radius=0)
            ctk.CTkLabel(
                cartao, text=titulo, fg_color="transparent", text_color="#08764B",
                font=ctk.CTkFont(size=max(14, int(17 * self._escala)), weight="bold")
            ).pack(pady=(4, 2))
            ctk.CTkLabel(
                cartao, text=descricao, fg_color="transparent", text_color="#536968",
                font=ctk.CTkFont(size=max(10, int(12 * self._escala))),
                wraplength=max(130, int(220 * self._escala))
            ).pack(padx=5, pady=(0, 4))
            ctk.CTkButton(
                cartao, text="Entrar", fg_color="transparent", hover_color="#E8F4EA",
                text_color="#176D42", border_width=1, border_color="#A8CFB7",
                height=max(28, int(34 * self._escala)),
                font=ctk.CTkFont(size=max(11, int(13 * self._escala)), weight="bold"),
                command=comando
            ).pack(fill="x", padx=10, pady=(0, 4))
            self._opcoes_widgets.append(cartao)
        self._posicionar_opcoes()

    def _comando(self, destino):
        def executar():
            if self._ativo:
                self.parar()
                self.ao_entrar(destino)
        return executar

    def _posicionar_opcoes(self):
        if not self._opcoes_widgets:
            return
        # Janela transparente e sem cartões sólidos; os patrocinadores ficam acima da faixa de opções.
        largura = 210 * self._escala
        espacamento = 18 * self._escala
        centro = self._px(766)
        topo = self._py(790)
        if not self._opcoes_janelas:
            for cartao in self._opcoes_widgets:
                janela = self.canvas.create_window(0, 0, window=cartao, anchor="n")
                self._opcoes_janelas.append(janela)
        total = len(self._opcoes_janelas) * largura + (len(self._opcoes_janelas) - 1) * espacamento
        inicio = centro - total / 2 + largura / 2
        for indice, janela in enumerate(self._opcoes_janelas):
            x = inicio + indice * (largura + espacamento)
            self.canvas.coords(janela, x, topo)
            self.canvas.itemconfigure(janela, width=max(150, int(largura)))

    def _animar(self):
        if not self._ativo:
            return
        for folha in self.folhas:
            folha["fase"] += .055
            folha["x"] += folha["velocidade"]
            if folha["x"] > 1533:
                folha["x"] = -folha["largura"]
            y = folha["y"] + math.sin(folha["fase"]) * 7
            if folha["item"] is not None:
                self.canvas.coords(
                    folha["item"], self._px(folha["x"]), self._py(y)
                )
        self._timer = self.frame.after(70, self._animar)

    def parar(self):
        self._ativo = False
        if self._timer is not None:
            try:
                self.frame.after_cancel(self._timer)
            except Exception:
                pass
            self._timer = None
