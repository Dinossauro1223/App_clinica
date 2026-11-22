# -*- coding: utf-8 -*-
"""Tela de cálculo da avaliação nutricional. Os resultados não são gravados no PEP."""
from __future__ import annotations

from datetime import date, datetime
import customtkinter as ctk
import db_service
import nutri_calculos as nc
import avaliacao_nutri as av
import tema


class AvaliacaoUI:
    def __init__(self, app, db_path):
        self.app, self.db_path = app, db_path
        self.campos, self.amputacoes, self.pacientes = {}, {}, {}

    @staticmethod
    def idade(nascimento):
        try:
            d = datetime.strptime(nascimento, "%d/%m/%Y").date()
            hoje = date.today()
            return hoje.year - d.year - ((hoje.month, hoje.day) < (d.month, d.day))
        except (TypeError, ValueError):
            return None

    def _pacientes(self):
        try:
            with db_service.conectar(self.db_path) as conn:
                return conn.execute("SELECT id_paciente, nome, data_nascimento, sexo FROM Pacientes ORDER BY nome COLLATE NOCASE").fetchall()
        except Exception:
            return []

    def mostrar(self):
        self.app.limpar_area_principal()
        raiz = self.app.area_principal
        raiz.grid_columnconfigure(0, weight=1)
        raiz.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(raiz, text="Avaliação nutricional", font=tema.fonte(22, "bold"),
                     text_color=tema.VERDE).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 6))
        scroll = ctk.CTkScrollableFrame(raiz, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 12))
        self._paciente(scroll)
        self._medidas(scroll)
        self._ajustes(scroll)
        self._metas(scroll)
        botoes = ctk.CTkFrame(scroll, fg_color="transparent")
        botoes.pack(fill="x", pady=8)
        ctk.CTkButton(botoes, text="Calcular", fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER,
                      command=self.calcular).pack(side="left", padx=(0, 8))
        ctk.CTkButton(botoes, text="Limpar", fg_color=tema.SUAVE, hover_color=tema.VERDE_ESC,
                      command=self.limpar).pack(side="left", padx=8)
        ctk.CTkButton(botoes, text="Copiar", fg_color=tema.LARANJA, hover_color=tema.LARANJA_TEXTO,
                      command=self.copiar).pack(side="left", padx=8)
        self.saida = ctk.CTkTextbox(scroll, height=210, border_width=1, border_color=tema.BORDA,
                                   fg_color=tema.BRANCO, text_color=tema.TEXTO)
        self.saida.pack(fill="x", pady=(8, 4))
        self.saida.insert("1.0", "Preencha os dados e clique em Calcular. Valores estimados serão identificados.")
        ctk.CTkLabel(scroll, text="Esta tela é uma calculadora: os dados e resultados não são salvos no prontuário.",
                    font=tema.fonte(11), text_color=tema.SUAVE).pack(anchor="w", padx=4, pady=(0, 12))

    def _card(self, pai, titulo):
        card = ctk.CTkFrame(pai, fg_color=tema.BRANCO, border_width=1, border_color=tema.BORDA)
        card.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(card, text=titulo, font=tema.fonte(14, "bold"), text_color=tema.VERDE).pack(anchor="w", padx=12, pady=(10, 6))
        return card

    def _entry(self, card, chave, placeholder):
        e = ctk.CTkEntry(card, width=280, placeholder_text=placeholder, border_color=tema.BORDA)
        e.pack(anchor="w", padx=12, pady=(0, 8))
        self.campos[chave] = e
        return e

    def _paciente(self, scroll):
        card = self._card(scroll, "Paciente (opcional)")
        rows = self._pacientes()
        valores = ["— Sem paciente —"] + [f"{r[0]} — {r[1]}" for r in rows]
        self.pacientes = {valores[i+1]: r for i, r in enumerate(rows)}
        self.combo_paciente = ctk.CTkComboBox(card, values=valores, width=360, command=self._selecionar)
        self.combo_paciente.pack(anchor="w", padx=12, pady=(0, 8))
        self.combo_paciente.set(valores[0])
        self._entry(card, "idade", "Idade (anos completos)")
        self.combo_sexo = ctk.CTkComboBox(card, values=["Homem", "Mulher"], width=180)
        self.combo_sexo.set("Selecione sexo")
        self.combo_sexo.pack(anchor="w", padx=12, pady=(0, 8))
        self.combo_cor = ctk.CTkComboBox(card, values=["Branca", "Preta"], width=180)
        self.combo_cor.set("Selecione cor")
        self.combo_cor.pack(anchor="w", padx=12, pady=(0, 12))

    def _medidas(self, scroll):
        card = self._card(scroll, "Peso e altura")
        self._entry(card, "peso", "Peso aferido (kg) — vazio = estimar")
        self._entry(card, "altura", "Altura aferida (cm) — vazio = estimar")
        self._entry(card, "aj", "Altura do joelho (AJ), cm")
        self._entry(card, "pb", "Perímetro do braço (PB), cm")

    def _ajustes(self, scroll):
        card = self._card(scroll, "Edema, ascite e amputações")
        self.combo_edema = ctk.CTkComboBox(card, values=list(av.EDEMA), width=290)
        self.combo_edema.set("Ausente")
        self.combo_edema.pack(anchor="w", padx=12, pady=(0, 8))
        self.combo_ascite = ctk.CTkComboBox(card, values=list(av.ASCITE), width=290)
        self.combo_ascite.set("Ausente")
        self.combo_ascite.pack(anchor="w", padx=12, pady=(0, 8))
        for nivel in av.AMPUTACOES:
            linha = ctk.CTkFrame(card, fg_color="transparent")
            linha.pack(fill="x", padx=12, pady=3)
            ctk.CTkLabel(linha, text=nivel, width=220, anchor="w", text_color=tema.TEXTO).pack(side="left")
            campo = ctk.CTkComboBox(linha, values=["0", "1", "2"], width=70)
            campo.set("0")
            campo.pack(side="left")
            self.amputacoes[nivel] = campo

    def _metas(self, scroll):
        card = self._card(scroll, "Metas e DRI")
        self._entry(card, "kcalkg", "Meta energética (kcal/kg/dia)")
        self._entry(card, "ptnkg", "Meta proteica (g/kg/dia)")
        self.combo_atividade = ctk.CTkComboBox(card, values=["Sedentário", "Pouco ativo", "Ativo", "Muito ativo"], width=240)
        self.combo_atividade.set("Sedentário")
        self.combo_atividade.pack(anchor="w", padx=12, pady=(0, 12))

    def _selecionar(self, texto):
        row = self.pacientes.get(texto)
        if not row:
            return
        idade = self.idade(row[2])
        self.campos["idade"].delete(0, "end")
        if idade is not None:
            self.campos["idade"].insert(0, str(idade))
        self.combo_sexo.set(row[3] or "Selecione sexo")

    def calcular(self):
        d = {k: e.get() for k, e in self.campos.items()}
        d.update({"sexo": self.combo_sexo.get(), "cor": self.combo_cor.get(),
                  "edema": self.combo_edema.get(), "ascite": self.combo_ascite.get(),
                  "amputacoes": {k: int(e.get()) for k, e in self.amputacoes.items()},
                  "atividade": ["Sedentário", "Pouco ativo", "Ativo", "Muito ativo"].index(self.combo_atividade.get())})
        try:
            r = av.calcular(d, criterio_idoso=getattr(self.app.mapa, "criterio_idoso", "lipschitz"))
        except Exception as erro:
            self._resultado(f"Não foi possível calcular: {erro}")
            return
        fmt = lambda v, casas=1: nc.fmt_num(v, casas, "n/a")
        linhas = ["RESULTADOS"]
        if r["peso"] is not None: linhas.append(f"Peso: {fmt(r['peso'])} kg ({r['tipo_peso']})")
        if r["ajustou"]: linhas.append(f"Peso ajustado: {fmt(r['ajustado'])} kg | Líquidos descontados: {fmt(r['fluidos'])} kg | Amputações: {fmt(r['amput_pct'])}%")
        if r["altura_m"] is not None: linhas.append(f"Altura: {fmt(r['altura_m'],2)} m ({r['tipo_alt']})")
        if r["imc"] is not None: linhas.append(f"IMC: {fmt(r['imc'])} kg/m² — {r['classe']}")
        if r["kcal"] is not None: linhas.append(f"Meta energética: {fmt(r['kcal'],0)} kcal/dia")
        if r["ptn"] is not None: linhas.append(f"Meta proteica: {fmt(r['ptn'],0)} g/dia")
        if r["dri"] is not None: linhas.append(f"DRI/EER: {fmt(r['dri'],0)} kcal/dia")
        if r["dif_dri_pct"] is not None: linhas.append(f"Diferença entre meta e DRI: {fmt(r['dif_dri_pct'],0)}%")
        if r["avisos"]: linhas.extend(["", "AVISOS:"] + [f"• {a}" for a in r["avisos"]])
        self._resultado("\n".join(linhas))

    def _resultado(self, texto):
        self.saida.delete("1.0", "end")
        self.saida.insert("1.0", texto)

    def limpar(self):
        for e in self.campos.values():
            e.delete(0, "end")
        self.combo_paciente.set("— Sem paciente —")
        self.combo_sexo.set("Selecione sexo")
        self.combo_cor.set("Selecione cor")
        self.combo_edema.set("Ausente")
        self.combo_ascite.set("Ausente")
        self.combo_atividade.set("Sedentário")
        for e in self.amputacoes.values():
            e.set("0")
        self._resultado("Preencha os dados e clique em Calcular.")

    def copiar(self):
        self.app.clipboard_clear()
        self.app.clipboard_append(self.saida.get("1.0", "end").strip())
