# -*- coding: utf-8 -*-
"""Interface independente para triagem NRS-2002; não salva dados clínicos."""
from __future__ import annotations

from datetime import date, datetime
import tkinter as tk
import customtkinter as ctk

import nrs2002 as nrs
import db_service
import tema


class NRSUI:
    def __init__(self, app, db_path):
        self.app, self.db_path = app, db_path
        self.respostas = {chave: None for chave, _ in nrs.PERGUNTAS}
        self.pacientes = {}
        self.campos = {}

    @staticmethod
    def _idade(nascimento):
        try:
            d = datetime.strptime(nascimento, "%d/%m/%Y").date()
            hoje = date.today()
            return hoje.year - d.year - ((hoje.month, hoje.day) < (d.month, d.day))
        except (ValueError, TypeError):
            return None

    def _pacientes(self):
        try:
            with db_service.conectar(self.db_path) as conn:
                rows = conn.execute("SELECT id_paciente, nome, data_nascimento FROM Pacientes ORDER BY nome COLLATE NOCASE").fetchall()
            return rows
        except Exception:
            return []

    def mostrar(self):
        self.app.limpar_area_principal()
        raiz = self.app.area_principal
        raiz.grid_columnconfigure(0, weight=1)
        raiz.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(raiz, text="Triagem nutricional — NRS-2002", font=tema.fonte(22, "bold"),
                     text_color=tema.VERDE).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 6))
        corpo = ctk.CTkScrollableFrame(raiz, fg_color="transparent")
        corpo.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))
        paciente_card = ctk.CTkFrame(corpo, fg_color=tema.BRANCO, border_width=1, border_color=tema.BORDA)
        paciente_card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(paciente_card, text="Paciente (opcional)", font=tema.fonte(14, "bold"),
                     text_color=tema.TEXTO).pack(anchor="w", padx=14, pady=(12, 4))
        lista = ["— Sem paciente selecionado —"]
        rows = self._pacientes()
        self.pacientes = {f"{r[0]} — {r[1]}": r for r in rows}
        lista += list(self.pacientes)
        self.combo_paciente = ctk.CTkComboBox(paciente_card, values=lista, width=360, command=self._selecionar_paciente, state="readonly")
        self.combo_paciente.pack(anchor="w", padx=14, pady=(0, 8))
        self.combo_paciente.set(lista[0])
        self.entrada_idade = ctk.CTkEntry(paciente_card, width=140, placeholder_text="Idade (anos)")
        self.entrada_idade.pack(anchor="w", padx=14, pady=(0, 12))
        self.card_triagem = ctk.CTkFrame(corpo, fg_color=tema.BRANCO, border_width=1, border_color=tema.BORDA)
        self.card_triagem.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(self.card_triagem, text="Etapa 1 — Triagem inicial", font=tema.fonte(14, "bold"),
                     text_color=tema.VERDE).pack(anchor="w", padx=14, pady=(12, 4))
        self.campos = {}
        for chave, pergunta in nrs.PERGUNTAS:
            linha = ctk.CTkFrame(self.card_triagem, fg_color="transparent")
            linha.pack(fill="x", padx=14, pady=4)
            ctk.CTkLabel(linha, text=pergunta, font=tema.fonte(13), text_color=tema.TEXTO,
                        anchor="w", width=320).pack(side="left")
            combo = ctk.CTkComboBox(linha, values=["Selecione", "Não", "Sim"], width=130, state="readonly")
            combo.set("Selecione")
            combo.pack(side="left")
            self.campos[chave] = combo
        ctk.CTkLabel(self.card_triagem, text="Se houver pelo menos um 'sim', preencha os escores da etapa 2.",
                     font=tema.fonte(12), text_color=tema.SUAVE).pack(anchor="w", padx=14, pady=(6, 12))
        self.card_etapa2 = ctk.CTkFrame(corpo, fg_color=tema.BRANCO, border_width=1, border_color=tema.BORDA)
        self.card_etapa2.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(self.card_etapa2, text="Etapa 2 — Escores", font=tema.fonte(14, "bold"),
                     text_color=tema.VERDE).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(self.card_etapa2, text=nrs.ESTADO_DICA, font=tema.fonte(12), text_color=tema.TEXTO,
                     justify="left", anchor="w", wraplength=720).pack(fill="x", padx=14, pady=(0, 8))
        self.combo_estado = ctk.CTkComboBox(self.card_etapa2, values=list(nrs.ESTADO.values()), width=300, state="readonly")
        self.combo_estado.set("Selecione")
        self.combo_estado.pack(anchor="w", padx=14, pady=(0, 8))
        ctk.CTkLabel(self.card_etapa2, text=nrs.GRAVIDADE_DICA, font=tema.fonte(12), text_color=tema.TEXTO,
                     justify="left", anchor="w", wraplength=720).pack(fill="x", padx=14, pady=(0, 8))
        self.combo_gravidade = ctk.CTkComboBox(self.card_etapa2, values=list(nrs.GRAVIDADE.values()), width=300, state="readonly")
        self.combo_gravidade.set("Selecione")
        self.combo_gravidade.pack(anchor="w", padx=14, pady=(0, 12))
        botoes = ctk.CTkFrame(corpo, fg_color="transparent")
        botoes.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(botoes, text="Calcular triagem", command=self.calcular, fg_color=tema.VERDE,
                      hover_color=tema.VERDE_HOVER).pack(side="left", padx=(0, 8))
        ctk.CTkButton(botoes, text="Limpar", command=self.limpar, fg_color=tema.SUAVE,
                      hover_color=tema.VERDE_ESC).pack(side="left", padx=8)
        ctk.CTkButton(botoes, text="Copiar resultado", command=self.copiar, fg_color=tema.LARANJA,
                      hover_color=tema.LARANJA_TEXTO).pack(side="left", padx=8)
        self.resultado = ctk.CTkLabel(corpo, text="Preencha a triagem inicial e clique em Calcular.",
                                     font=tema.fonte(14, "bold"), text_color=tema.TEXTO,
                                     justify="left", anchor="w", wraplength=720)
        self.resultado.pack(fill="x", padx=8, pady=12)
        ctk.CTkLabel(corpo, text="Ferramenta de apoio. Confirme o escore e a conduta com o protocolo institucional.",
                     font=tema.fonte(11), text_color=tema.SUAVE).pack(anchor="w", padx=8, pady=(0, 12))

    def _selecionar_paciente(self, valor):
        row = self.pacientes.get(valor)
        idade = self._idade(row[2]) if row else None
        self.entrada_idade.delete(0, "end")
        if idade is not None:
            self.entrada_idade.insert(0, str(idade))

    def _escore_combo(self, combo, valores):
        texto = combo.get()
        return next((n for n, rotulo in valores.items() if rotulo == texto), None)

    def calcular(self):
        respostas = {k: (True if campo.get() == "Sim" else False if campo.get() == "Não" else None)
                     for k, campo in self.campos.items()}
        idade_txt = self.entrada_idade.get().strip()
        try:
            idade = int(idade_txt) if idade_txt else None
            if idade is not None and idade < 0:
                raise ValueError
        except ValueError:
            self.resultado.configure(text="Informe idade em anos completos (número inteiro).", text_color=tema.LARANJA_TEXTO)
            return
        estado = self._escore_combo(self.combo_estado, nrs.ESTADO)
        gravidade = self._escore_combo(self.combo_gravidade, nrs.GRAVIDADE)
        r = nrs.classificar(respostas, estado, gravidade, idade)
        if not r["completo"]:
            self.resultado.configure(text=r["rotulo"], text_color=tema.LARANJA_TEXTO)
            return
        try:
            intervalos = nrs.ler_intervalos(self.db_path)
        except Exception:
            intervalos = dict(nrs.DIAS_PADRAO)
        grau = r["grau"]
        dias = nrs.dias_para(grau, intervalos)
        alvo = nrs.proxima_reavaliacao(date.today(), grau, intervalos)
        texto = f"{r['rotulo']}\nReavaliar em {dias} dias (até {alvo.strftime('%d/%m/%Y')})."
        if dias > nrs.LIMITE_RDC63:
            texto += f"\nAtenção: o intervalo supera {nrs.LIMITE_RDC63} dias (limite indicado pela RDC 63/2000)."
        self.resultado.configure(text=texto, text_color=tema.VERDE if grau in ("triagem_negativa", "sem_risco") else tema.LARANJA_TEXTO)

    def limpar(self):
        for campo in self.campos.values():
            campo.set("Selecione")
        self.combo_estado.set("Selecione")
        self.combo_gravidade.set("Selecione")
        self.entrada_idade.delete(0, "end")
        self.combo_paciente.set("— Sem paciente selecionado —")
        self.resultado.configure(text="Preencha a triagem inicial e clique em Calcular.", text_color=tema.TEXTO)

    def copiar(self):
        texto = self.resultado.cget("text")
        self.app.clipboard_clear()
        self.app.clipboard_append(texto)
