# -*- coding: utf-8 -*-
"""Tela inicial do NutriLab composta por camadas SVG rasterizadas com alpha.

O Canvas mantém as ilustrações no fundo, anima folhas independentes e deixa
wordmark, assinatura institucional, opções e créditos em camadas próprias.
"""
import json
import math
import os
import random
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageTk
import tema


FUNDO = tema.FUNDO
LARGURA_BASE = 1533
ALTURA_BASE = 1026


class TelaBoasVindas:
    def __init__(self, master, ao_entrar):
        self.master = master
        self.ao_entrar = ao_entrar
        self.frame = ctk.CTkFrame(master, fg_color=FUNDO, corner_radius=0)
        self.canvas = tk.Canvas(self.frame, bg=tema.cor_atual(FUNDO), highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        base = self._base_path()
        self.pasta = os.path.join(base, "identidade_camadas")
        if not os.path.isdir(self.pasta):
            self.pasta = os.path.join(base, "assets", "identidade", "renderizados")
        self.imagens = {}
        self.folhas = []
        self.itens_folhas = []
        self.particulas = []
        self._fotos = []
        self._opcoes_visiveis = False
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
            "frasco", "wordmark", "assinatura", "facisa_ufrn", "folha_marca",
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
                    # Cada folha permanece presa à haste pelo ponto de inserção do SVG.
                    pivos = ((180, 205), (205, 143), (222, 220), (155, 285), (230, 290))
                    px_svg, py_svg = pivos[len(self.folhas)]
                    bx, by = item["bbox"][0], item["bbox"][1]
                    margem = max(12, int(max(imagem.size) * .16))
                    base = Image.new("RGBA", (imagem.width + 2*margem, imagem.height + 2*margem), (0,0,0,0))
                    base.alpha_composite(imagem, (margem, margem))
                    pivo = (margem + (px_svg-bx)*2, margem + (py_svg-by)*2)
                    self.folhas.append({
                        "imagem": imagem, "base": base, "pivo": pivo,
                        "base_x": 815 + px_svg * .95, "base_y": 120 + py_svg * .95,
                        "fase": len(self.folhas) * 1.25 + random.random(),
                        "velocidade": random.uniform(.018, .032),
                        "amplitude": random.uniform(2.2, 4.2),
                        "item": None, "foto": None,
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
        self.particulas = []

        # Camadas de fundo: decoração, arco e haste; cada folha é uma imagem RGBA.
        self._imagem("decoracao_inferior", 0, 0, 1533, 1026)
        self._imagem("arco", 815, 120, 570, 570)
        self._imagem("haste_folhas", 815, 120, 399, 380)

        # Folhas maiores oscilam em torno do ponto de ligação; não atravessam a cena.
        for folha in self.folhas:
            foto, x, y = self._folha_frame(folha, 0)
            folha["foto"] = foto
            folha["item"] = self.canvas.create_image(x, y, image=foto, anchor="nw", tags=("folha-animada",))
            self.itens_folhas.append(folha["item"])

        # Primeiro plano: maçã, wordmark, assinatura e marcas institucionais.
        self._imagem("maca", 929, 386, 378, 324)
        self._imagem("dna", 1238, 130, 132, 253)
        self._imagem("frasco", 1320, 410, 175, 245)
        self._imagem("boas_vindas", 108, 250, 520, 100)
        self._imagem("wordmark", 100, 345, 759, 159)
        self._imagem("assinatura", 110, 458, 990, 135)
        self._imagem("facisa_ufrn", 108, 655, 403, 81)
        self._imagem("topo_temas", 1090, 20, 440, 80)

        if self._opcoes_visiveis:
            self.canvas.create_text(
                self._px(766), self._py(760), text="Escolha por onde deseja começar",
                fill=tema.cor_atual(tema.VERDE_ESC),
                font=("Segoe UI", max(14, int(23 * self._escala)), "bold"),
                anchor="center"
            )
            self._desenhar_opcoes()
        else:
            self._item_instrucao = self.canvas.create_text(
                self._px(766), self._py(974), text="Clique em qualquer lugar para continuar",
                fill=tema.cor_atual(tema.VERDE), font=("Segoe UI", max(10, int(15 * self._escala)), "bold"),
                anchor="center"
            )
        self.canvas.create_text(
            self._px(500), self._py(1005),
            text="© 2026 Neis Bila de Alencar. Todos os direitos reservados.",
            fill=tema.cor_atual(tema.SUAVE), font=("Segoe UI", max(8, int(10 * self._escala))),
            anchor="center"
        )

    def _clicar(self, event=None):
        if not self._opcoes_visiveis:
            self.mostrar_opcoes()

    def mostrar_opcoes(self):
        if not self._ativo or self._opcoes_visiveis:
            return
        self._opcoes_visiveis = True
        # Redesenha apenas a composição vetorial; as opções são texto nativo do Canvas,
        # sem cartões/janelas que escondam as camadas da cena.
        self._desenhar_cena()

    def _desenhar_opcoes(self):
        opcoes = (
            ("clinica", "Gestão Clínica", "Pacientes, consultas, exames\ne avaliações"),
            ("nutricao", "Nutrição", "Mapa nutricional, gráficos\ne suplementos"),
            ("alimentar", "Gestão Alimentar", "Almoxarifado, copa e fichas\nde consumo"),
        )
        centros = (410, 766, 1122)
        for (chave, titulo, descricao), centro in zip(opcoes, centros):
            tag = "opcao-" + chave
            self.canvas.create_text(
                self._px(centro), self._py(804), text=titulo,
                fill=tema.cor_atual(tema.VERDE),
                font=("Segoe UI", max(13, int(18 * self._escala)), "bold"),
                anchor="center", tags=(tag,)
            )
            self.canvas.create_text(
                self._px(centro), self._py(846), text=descricao,
                fill=tema.cor_atual(tema.SUAVE),
                font=("Segoe UI", max(10, int(12 * self._escala))),
                anchor="center", justify="center", tags=(tag,)
            )
            self.canvas.create_text(
                self._px(centro), self._py(892), text="ENTRAR  ›",
                fill=tema.cor_atual(tema.VERDE_HOVER),
                font=("Segoe UI", max(10, int(12 * self._escala)), "bold"),
                anchor="center", tags=(tag,)
            )
            self.canvas.tag_bind(
                tag, "<Button-1>",
                lambda event, destino=chave: self._comando(destino)()
            )
            self.canvas.tag_bind(tag, "<Enter>", lambda event: self.canvas.configure(cursor="hand2"))
            self.canvas.tag_bind(tag, "<Leave>", lambda event: self.canvas.configure(cursor=""))

    def _comando(self, destino):
        def executar():
            if self._ativo:
                self.parar()
                self.ao_entrar(destino)
        return executar

    def _folha_frame(self, folha, angulo):
        imagem = folha["base"].rotate(
            angulo, resample=Image.Resampling.BICUBIC, expand=False, center=folha["pivo"]
        )
        if self._escala != 1:
            imagem = imagem.resize(
                (max(1, int(imagem.width*.475*self._escala)), max(1, int(imagem.height*.475*self._escala))),
                Image.Resampling.LANCZOS
            )
        foto = ImageTk.PhotoImage(imagem)
        x = self._px(folha["base_x"] - folha["pivo"][0]*.475)
        y = self._py(folha["base_y"] - folha["pivo"][1]*.475)
        return foto, x, y

    def _criar_particula(self):
        origem = self.imagens.get("folha_marca")
        if origem is None:
            return
        tamanho = random.randint(7, 15)
        self.particulas.append({
            "origem": origem, "tamanho": tamanho, "fase": random.uniform(0, math.tau), "frequencia": random.uniform(.08, .22),
            "x": random.uniform(570, 590), "y": random.uniform(405, 445),
            "vx": random.uniform(1.0, 2.2), "vy": random.uniform(-1.15, 1.15),
            "vida": random.randint(35, 75), "idade": 0, "item": None, "foto": None,
        })

    def _atualizar_particulas(self):
        if random.random() < .22 and len(self.particulas) < 16:
            self._criar_particula()
        for p in self.particulas[:]:
            p["idade"] += 1
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            if random.random() < .04:
                p["vy"] = random.uniform(-1.15, 1.15)
            progresso = p["idade"] / p["vida"]
            opacidade = max(0.0, 1.0 - max(0.0, (progresso - .35) / .65))
            pulso = .55 + .45 * ((1 + math.sin(p["idade"] * p["frequencia"] + p["fase"])) / 2)
            tamanho = max(4, int(p["tamanho"] * pulso))
            frame = p["origem"].resize((tamanho, tamanho), Image.Resampling.LANCZOS)
            frame.putalpha(frame.getchannel("A").point(lambda valor: int(valor*opacidade)))
            p["foto"] = ImageTk.PhotoImage(frame)
            if p["item"] is None:
                p["item"] = self.canvas.create_image(self._px(p["x"]), self._py(p["y"]), image=p["foto"], anchor="center")
            else:
                self.canvas.itemconfig(p["item"], image=p["foto"])
                self.canvas.coords(p["item"], self._px(p["x"]), self._py(p["y"]))
            if p["idade"] >= p["vida"] or p["x"] >= 850:
                self.canvas.delete(p["item"])
                self.particulas.remove(p)

    def _animar(self):
        if not self._ativo:
            return
        for folha in self.folhas:
            folha["fase"] += folha["velocidade"]
            angulo = math.sin(folha["fase"]) * folha["amplitude"]
            foto, x, y = self._folha_frame(folha, angulo)
            folha["foto"] = foto
            if folha["item"] is not None:
                self.canvas.itemconfig(folha["item"], image=foto)
                self.canvas.coords(folha["item"], x, y)
        self._atualizar_particulas()
        self._timer = self.frame.after(70, self._animar)

    def parar(self):
        self._ativo = False
        if self._timer is not None:
            try:
                self.frame.after_cancel(self._timer)
            except Exception:
                pass
            self._timer = None
