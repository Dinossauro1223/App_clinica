# -*- coding: utf-8 -*-
"""Editor de evolução nutricional individual integrado ao registro do Mapa.

O rascunho pode ser preparado pela equipe. O fechamento exige autenticação de
nutricionista com CRN conferido e confirmação explícita.
"""
from __future__ import annotations

import json
import sqlite3
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

import avaliacao_nutri as avaliacao
import evolucao_nutricional as regras
import mapa_db as mdb
import pep_db
import pep_evolucao_db as evdb
import tema


class FormEvolucaoUI(ctk.CTkFrame):
    def __init__(self, ui, registro, form_registro):
        self.ui, self.reg, self.form_registro = ui, registro, form_registro
        self.app = ui.app
        self.painel = self.app.abrir_painel_lateral(
            "Evolução nutricional", lambda: None, _preservar_pai=True)
        super().__init__(self.painel, fg_color="transparent")
        self.pack(fill="both", expand=True)
        self.db = ui.db
        self.paciente = mdb.obter_paciente(self.db, registro.get("id_paciente")) or {}
        self.equipe = evdb.listar_equipe(self.db)
        self.estagiarios = [m for m in self.equipe if m["funcao"] == "estagiario"]
        self.nutricionistas = [m for m in self.equipe if m["funcao"] == "nutricionista" and m["id_usuario"]]
        self.dados_existentes = registro.get("evolucao") or {}
        self.id_rascunho = self.dados_existentes.get("id_rascunho")
        self._rascunho_fechado = False
        if self.id_rascunho:
            atual = evdb.obter_rascunho(self.db, self.id_rascunho)
            self._rascunho_fechado = bool(atual and atual["status"] == "fechada")
            if atual:
                self.dados_existentes = atual["dados"]
        self._montar()
        self._preencher()
        self._atualizar_correcao()

    def _secao(self, pai, titulo):
        card = ctk.CTkFrame(pai, fg_color=tema.BRANCO, border_width=1,
                            border_color=tema.BORDA, corner_radius=10)
        card.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(card, text=titulo, font=tema.fonte(14, "bold"),
                     text_color=tema.VERDE).pack(anchor="w", padx=12, pady=(10, 6))
        return card

    def _entry(self, pai, texto, valor="", largura=140):
        e = ctk.CTkEntry(pai, width=largura, placeholder_text=texto, border_color=tema.BORDA)
        if valor not in (None, ""):
            e.insert(0, str(valor))
        e.pack(side="left", padx=(0, 8), pady=(0, 8))
        return e

    def _montar(self):
        raiz = ctk.CTkScrollableFrame(self, fg_color="transparent")
        raiz.pack(fill="both", expand=True)
        ctk.CTkLabel(raiz, text="EVOLUÇÃO NUTRICIONAL",
                     font=tema.fonte(20, "bold"), text_color=tema.VERDE).pack(
                         anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(raiz,
                     text=f"{self.reg.get('nome_paciente', 'Paciente')} · {mdb.iso_para_br(self.reg.get('data', ''))}",
                     font=tema.fonte(12), text_color=tema.SUAVE).pack(anchor="w", padx=14, pady=(0, 10))

        q = self._secao(raiz, "Dados clínicos e metas")
        self.lbl_antropometria = ctk.CTkLabel(q, text="", justify="left", anchor="w",
                                               font=tema.fonte(12), text_color=tema.TEXTO)
        self.lbl_antropometria.pack(fill="x", padx=12, pady=(0, 4))
        self.lbl_correcao = ctk.CTkLabel(q, text="", justify="left", anchor="w",
                                         font=tema.fonte(11), text_color=tema.LARANJA_TEXTO,
                                         wraplength=760)
        self.lbl_correcao.pack(fill="x", padx=12, pady=(0, 8))
        linha = ctk.CTkFrame(q, fg_color="transparent")
        linha.pack(fill="x", padx=12)
        self.e_kcal_kg = self._entry(linha, "kcal/kg/dia", largura=120)
        self.e_ptn_kg = self._entry(linha, "g proteína/kg/dia", largura=140)
        self.lbl_metas = ctk.CTkLabel(q, text="", font=tema.fonte(12, "bold"),
                                      text_color=tema.VERDE_ESC)
        self.lbl_metas.pack(anchor="w", padx=12, pady=(0, 10))
        self.e_kcal_kg.bind("<KeyRelease>", lambda _e: self._atualizar_metas())
        self.e_ptn_kg.bind("<KeyRelease>", lambda _e: self._atualizar_metas())

        q_renal = self._secao(raiz, "Avaliação renal — KDIGO 2024 / KDOQI 2020")
        linha = ctk.CTkFrame(q_renal, fg_color="transparent")
        linha.pack(fill="x", padx=12, pady=(0, 5))
        ctk.CTkLabel(linha, text="Referência:", width=85, anchor="w").pack(side="left")
        self.cb_renal_ref = ctk.CTkComboBox(linha, values=["KDIGO 2024", "KDOQI 2020"],
                                            width=150, state="readonly")
        self.cb_renal_ref.set("KDIGO 2024")
        self.cb_renal_ref.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(linha, text="DRC confirmada:", width=115, anchor="w").pack(side="left")
        self.cb_drc_confirmada = ctk.CTkComboBox(linha, values=["—", "Sim", "Não"], width=90, state="readonly")
        self.cb_drc_confirmada.set("Sim" if self.reg.get("drc") else "—")
        self.cb_drc_confirmada.pack(side="left", padx=(0, 12))
        self.cb_condicao_renal = ctk.CTkComboBox(
            linha, values=["Não definida", "DRC", "LRA", "DRC + LRA"], width=130, state="readonly")
        self.cb_condicao_renal.set("DRC" if self.reg.get("drc") else "Não definida")
        self.cb_condicao_renal.pack(side="left", padx=(0, 8))
        linha = ctk.CTkFrame(q_renal, fg_color="transparent")
        linha.pack(fill="x", padx=12, pady=(0, 5))
        ctk.CTkLabel(linha, text="Estágio:", width=60, anchor="w").pack(side="left")
        self.cb_estagio_renal = ctk.CTkComboBox(linha, values=["—", "G1", "G2", "G3a", "G3b", "G4", "G5"],
                                                width=90, state="readonly")
        self.cb_estagio_renal.set("—")
        self.cb_estagio_renal.pack(side="left", padx=(0, 8))
        self.e_tfge = self._entry(linha, "TFGe (mL/min/1,73 m²)", "", 170)
        self.e_albuminuria = self._entry(linha, "Albuminúria (mg/g)", "", 145)
        self.cb_dialise = ctk.CTkComboBox(linha, values=["Não", "Hemodiálise", "Diálise peritoneal"],
                                          width=175, state="readonly")
        self.cb_dialise.set("Não")
        self.cb_dialise.pack(side="left", padx=(0, 8), pady=(0, 8))
        linha = ctk.CTkFrame(q_renal, fg_color="transparent")
        linha.pack(fill="x", padx=12, pady=(0, 5))
        self.e_frequencia_dialise = self._entry(linha, "sessões/semana", "", 120)
        self.e_duracao_dialise = self._entry(linha, "horas/sessão", "", 115)
        self.e_inicio_dialise = self._entry(linha, "início da diálise", "", 145)
        self.cb_estabilidade_renal = ctk.CTkComboBox(
            linha, values=["Não informada", "Estável", "Instável"], width=145, state="readonly")
        self.cb_estabilidade_renal.set("Não informada")
        self.cb_estabilidade_renal.pack(side="left", padx=(0, 8), pady=(0, 8))
        linha = ctk.CTkFrame(q_renal, fg_color="transparent")
        linha.pack(fill="x", padx=12, pady=(0, 5))
        ctk.CTkLabel(linha, text="Catabolismo:").pack(side="left", padx=(0, 4))
        self.cb_catabolismo = ctk.CTkComboBox(linha, values=["Não informado", "Sim", "Não"],
                                              width=125, state="readonly")
        self.cb_catabolismo.set("Não informado")
        self.cb_catabolismo.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(linha, text="Risco de desnutrição:").pack(side="left", padx=(0, 4))
        self.cb_risco_desnutricao = ctk.CTkComboBox(linha, values=["Não informado", "Sim", "Não"],
                                                    width=125, state="readonly")
        self.cb_risco_desnutricao.set("Não informado")
        self.cb_risco_desnutricao.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(linha, text="Fragilidade/sarcopenia:").pack(side="left", padx=(0, 4))
        self.cb_sarcopenia = ctk.CTkComboBox(linha, values=["Não informado", "Sim", "Não"],
                                             width=125, state="readonly")
        self.cb_sarcopenia.set("Não informado")
        self.cb_sarcopenia.pack(side="left", padx=(0, 8))
        linha = ctk.CTkFrame(q_renal, fg_color="transparent")
        linha.pack(fill="x", padx=12, pady=(0, 5))
        self.e_creatinina = self._entry(linha, "Creatinina (mg/dL)", "", 135)
        self.e_ureia = self._entry(linha, "Ureia (mg/dL)", "", 115)
        self.e_albumina_serica = self._entry(linha, "Albumina sérica (g/dL)", "", 150)
        ctk.CTkButton(linha, text="Avaliar referência proteica", command=self._avaliar_renal,
                      width=190, fg_color=tema.VERDE).pack(side="left", padx=(0, 8), pady=(0, 8))
        self.lbl_renal = ctk.CTkLabel(q_renal, text="A avaliação renal não altera automaticamente a meta proteica.",
                                      text_color=tema.SUAVE, wraplength=760, justify="left")
        self.lbl_renal.pack(anchor="w", padx=12, pady=(0, 8))
        ctk.CTkLabel(q_renal, text="TFGe deve vir do laudo. Creatinina, ureia e albumina sérica são apenas dados de apoio; não determinam isoladamente estágio ou meta proteica.",
                     text_color=tema.SUAVE, wraplength=760, justify="left",
                     font=tema.fonte(10)).pack(anchor="w", padx=12, pady=(0, 8))

        q = self._secao(raiz, "DVA e via de alimentação")
        linha = ctk.CTkFrame(q, fg_color="transparent")
        linha.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(linha, text="DVA:", width=55, anchor="w").pack(side="left")
        self.seg_dva = ctk.CTkSegmentedButton(linha, values=["Sim", "Não", "—"], width=160)
        self.seg_dva.set("—")
        self.seg_dva.pack(side="left")
        ctk.CTkLabel(linha, text=f"Via: {self.reg.get('via') or 'não informada'}",
                     font=tema.fonte(12, "bold"), text_color=tema.TEXTO).pack(side="left", padx=18)
        reav = mdb.iso_para_br(self.reg.get("data_reavaliacao"))
        nrs_class = self.reg.get("nrs2002_classificacao") or "não classificado"
        self.lbl_via = ctk.CTkLabel(q, text=f"NRS-2002: {nrs_class} · Próxima reavaliação: {reav or 'não definida'}",
                                    font=tema.fonte(11), text_color=tema.SUAVE)
        self.lbl_via.pack(anchor="w", padx=12, pady=(0, 8))

        cfg_porcoes = mdb.obter_config(self.db, "porcoes_orais_ml", "70,100,130,160,200")
        try:
            self.porcoes_orais = sorted({int(x.strip()) for x in str(cfg_porcoes).split(",") if int(x.strip()) > 0})
        except (TypeError, ValueError):
            self.porcoes_orais = [70, 100, 130, 160, 200]
        if not self.porcoes_orais:
            self.porcoes_orais = [70, 100, 130, 160, 200]
        self.q_oral = self._secao(raiz, "Via oral — TNO e porção autorizada")
        linha = ctk.CTkFrame(self.q_oral, fg_color="transparent")
        linha.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(linha, text="TNO:", width=55, anchor="w").pack(side="left")
        self.cb_tno = ctk.CTkComboBox(linha, values=["—"] + list(regras.TNO_PERCENTUAIS), width=150, state="readonly")
        self.cb_tno.set("—")
        self.cb_tno.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(linha, text="Porção (mL):", anchor="w").pack(side="left")
        self.cb_porcao = ctk.CTkComboBox(linha, values=[str(x) for x in self.porcoes_orais], width=100, state="readonly")
        self.cb_porcao.set(str(self.porcoes_orais[0]))
        self.cb_porcao.pack(side="left", padx=8)
        self.var_solicitar_porcao = tk.IntVar(value=0)
        ctk.CTkCheckBox(self.q_oral, text="Solicitar atualização da porção no mapa das copeiras",
                        variable=self.var_solicitar_porcao).pack(anchor="w", padx=12, pady=(0, 10))

        self.q_enteral = self._secao(raiz, "Via enteral — TNE, fórmula e progressão")
        self.tne_vars = {}
        linha = ctk.CTkFrame(self.q_enteral, fg_color="transparent")
        linha.pack(fill="x", padx=12, pady=(0, 6))
        for motivo in ("retrolimentação", "vômitos", "diarreia"):
            var = tk.IntVar(value=0)
            ctk.CTkCheckBox(linha, text=motivo.capitalize(), variable=var).pack(side="left", padx=(0, 12))
            self.tne_vars[motivo] = var
        self.formulas = [s for s in self.reg.get("suplementos", [])
                         if s.get("kcal_100") is not None and s.get("ptn_100") is not None]
        self.formula_por_nome = {s["nome"]: s for s in self.formulas}
        nomes = list(self.formula_por_nome) or ["Sem ficha completa"]
        linha = ctk.CTkFrame(self.q_enteral, fg_color="transparent")
        linha.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(linha, text="Fórmula:", width=65, anchor="w").pack(side="left")
        self.cb_formula = ctk.CTkComboBox(linha, values=nomes, width=260, state="readonly")
        self.cb_formula.set(nomes[0])
        self.cb_formula.pack(side="left", padx=(0, 10))
        formula_inicial = self.formulas[0] if self.formulas else {}
        etapas_iniciais = len(formula_inicial.get("refeicoes") or []) or 1
        qtd_dia_inicial = float(formula_inicial.get("qtd_dia") or 0)
        volume_inicial_etapa = qtd_dia_inicial / etapas_iniciais if qtd_dia_inicial else ""
        self.e_volume_etapa = self._entry(linha, "mL/etapa", volume_inicial_etapa, largura=95)
        self.e_etapas = self._entry(linha, "etapas/dia", str(etapas_iniciais), largura=90)
        self.cb_formula.bind("<<ComboboxSelected>>", self._atualizar_formula)
        linha = ctk.CTkFrame(self.q_enteral, fg_color="transparent")
        linha.pack(fill="x", padx=12, pady=(0, 6))
        self.var_bomba = tk.IntVar(value=0)
        ctk.CTkCheckBox(linha, text="Utiliza bomba de infusão", variable=self.var_bomba).pack(side="left", padx=(0, 16))
        self.e_horas_adm = self._entry(linha, "tempo de administração (h)", "", largura=175)
        self.e_fator_gotas = self._entry(linha, "fator do equipo (gotas/mL)", "", largura=190)
        self.var_progressao = tk.IntVar(value=0)
        ctk.CTkCheckBox(linha, text="Solicitar progressão enteral automática", variable=self.var_progressao).pack(side="left")
        linha = ctk.CTkFrame(self.q_enteral, fg_color="transparent")
        linha.pack(fill="x", padx=12, pady=(0, 8))
        self.e_incremento = self._entry(linha, "incremento diário (mL)", "35", largura=150)
        self.e_dias = self._entry(linha, "prazo (dias)", "4", largura=100)
        self.e_volume_maximo = self._entry(linha, "volume máximo/dia (mL)", "", largura=170)
        self.var_tolerancia = tk.IntVar(value=1)
        ctk.CTkCheckBox(linha, text="Boa tolerância", variable=self.var_tolerancia).pack(side="left", padx=(0, 12))
        self.var_restricao = tk.IntVar(value=0)
        ctk.CTkCheckBox(linha, text="Restrição clínica", variable=self.var_restricao).pack(side="left")
        ctk.CTkLabel(self.q_enteral,
                     text="Referência: incremento total de 30–40 mL/dia, com meta em 3–4 dias quando matematicamente possível. A execução depende de tolerância, volume máximo e autorização do nutricionista.",
                     font=tema.fonte(10), text_color=tema.SUAVE, wraplength=760,
                     justify="left").pack(anchor="w", padx=12, pady=(0, 8))

        q = self._secao(raiz, "Suplementação por etapa")
        self.sup_fields = []
        for s in self.reg.get("suplementos", []):
            linha = ctk.CTkFrame(q, fg_color="transparent")
            linha.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(linha, text=s.get("nome", "Suplemento"), width=220,
                         anchor="w", text_color=tema.TEXTO).pack(side="left")
            etapas_padrao = len(s.get("refeicoes") or []) or 1
            total_padrao = float(s.get("qtd_dia") or 0)
            qtd_padrao = total_padrao / etapas_padrao if total_padrao else ""
            qtd = self._entry(linha, "quantidade/etapa", qtd_padrao, 105)
            ctk.CTkLabel(linha, text=s.get("unidade") or "", width=35).pack(side="left")
            etapas = self._entry(linha, "etapas/dia", str(etapas_padrao), 85)
            self.sup_fields.append((s, qtd, etapas))

        q = self._secao(raiz, "Observações e conduta")
        self.t_observacoes = ctk.CTkTextbox(q, height=75, border_width=1, border_color=tema.BORDA)
        self.t_observacoes.pack(fill="x", padx=12, pady=(0, 8))
        self.t_conduta = ctk.CTkTextbox(q, height=75, border_width=1, border_color=tema.BORDA)
        self.t_conduta.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(q, text="Observações clínicas", font=tema.fonte(11, "bold"),
                     text_color=tema.SUAVE).place(x=16, y=30)
        ctk.CTkLabel(q, text="Conduta nutricional", font=tema.fonte(11, "bold"),
                     text_color=tema.SUAVE).place(x=16, y=115)

        q = self._secao(raiz, "Equipe responsável")
        ctk.CTkLabel(q, text="Elaborador principal (estagiário ou nutricionista):",
                     font=tema.fonte(11), text_color=tema.TEXTO).pack(anchor="w", padx=12)
        op_elab = [f"{m['id_membro']} — {m['nome']}" for m in self.equipe]
        self.membro_por_op = {f"{m['id_membro']} — {m['nome']}": m for m in self.equipe}
        self.cb_elaborador = ctk.CTkComboBox(q, values=op_elab or ["Cadastre a equipe nas Configurações"],
                                             width=360, state="readonly")
        self.cb_elaborador.set(op_elab[0] if op_elab else "Cadastre a equipe nas Configurações")
        self.cb_elaborador.pack(anchor="w", padx=12, pady=(4, 8))
        self.colab_vars = {}
        for m in self.equipe:
            var = tk.IntVar(value=1 if m["id_membro"] == (self.equipe[0]["id_membro"] if self.equipe else None) else 0)
            ctk.CTkCheckBox(q, text=f"{m['nome']} ({m['funcao']})", variable=var).pack(anchor="w", padx=12, pady=1)
            self.colab_vars[m["id_membro"]] = var
        ctk.CTkLabel(q, text="Nutricionista que revisará e fechará:", font=tema.fonte(11),
                     text_color=tema.TEXTO).pack(anchor="w", padx=12, pady=(8, 2))
        self.revisor_por_op = {f"{m['id_usuario']} — {m['nome']} ({m['crn']})": m for m in self.nutricionistas}
        self.cb_revisor = ctk.CTkComboBox(q, values=list(self.revisor_por_op) or ["Cadastre um nutricionista"],
                                          width=360, state="readonly")
        self.cb_revisor.set(next(iter(self.revisor_por_op), "Cadastre um nutricionista"))
        self.cb_revisor.pack(anchor="w", padx=12, pady=(0, 6))
        self.e_senha = ctk.CTkEntry(q, width=250, placeholder_text="Senha do nutricionista", show="*")
        self.e_senha.pack(anchor="w", padx=12, pady=(0, 8))
        self.var_autorizar_progressao = tk.IntVar(value=0)
        ctk.CTkCheckBox(q, text="Na revisão, autorizar progressão enteral solicitada",
                        variable=self.var_autorizar_progressao).pack(anchor="w", padx=12, pady=2)
        self.var_autorizar_porcao = tk.IntVar(value=0)
        ctk.CTkCheckBox(q, text="Na revisão, autorizar porção oral solicitada",
                        variable=self.var_autorizar_porcao).pack(anchor="w", padx=12, pady=(2, 10))

        self.lbl_status = ctk.CTkLabel(raiz, text="", font=tema.fonte(11), text_color=tema.SUAVE,
                                       wraplength=760, justify="left")
        self.lbl_status.pack(anchor="w", padx=16, pady=(0, 8))
        rodape = ctk.CTkFrame(raiz, fg_color="transparent")
        rodape.pack(fill="x", padx=12, pady=(0, 14))
        self.b_salvar = ctk.CTkButton(rodape, text="Salvar rascunho", command=self._salvar_rascunho,
                                      fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER)
        self.b_salvar.pack(side="left", padx=(0, 8))
        self.b_fechar = ctk.CTkButton(rodape, text="Revisar e fechar", command=self._fechar,
                                      fg_color=tema.LARANJA, hover_color=tema.LARANJA_TEXTO)
        self.b_fechar.pack(side="left", padx=8)
        ctk.CTkButton(rodape, text="Voltar ao registro", command=self._fechar_painel,
                      fg_color=tema.SUAVE, hover_color=tema.VERDE_ESC).pack(side="right")
        if self._rascunho_fechado:
            self._somente_leitura()

    def _atualizar_formula(self, _evento=None):
        ficha = self.formula_por_nome.get(self.cb_formula.get())
        if not ficha:
            return
        etapas = len(ficha.get("refeicoes") or []) or 1
        total = float(ficha.get("qtd_dia") or 0)
        volume = total / etapas if total else ""
        self.e_volume_etapa.delete(0, "end")
        if volume != "":
            self.e_volume_etapa.insert(0, str(round(volume, 2)))
        self.e_etapas.delete(0, "end")
        self.e_etapas.insert(0, str(etapas))

    def _preencher(self):
        dados = self.dados_existentes if isinstance(self.dados_existentes, dict) else {}
        self.seg_dva.set("Sim" if dados.get("dva") is True else "Não" if dados.get("dva") is False else "—")
        if dados.get("tno") in regras.TNO_PERCENTUAIS:
            self.cb_tno.set(dados["tno"])
        if dados.get("porcao_oral_ml") is not None:
            self.cb_porcao.set(str(dados["porcao_oral_ml"]))
        self.var_solicitar_porcao.set(int(bool(dados.get("porcao_oral_solicitada"))))
        for motivo, var in self.tne_vars.items():
            var.set(int(motivo in (dados.get("tne_motivos") or [])))
        dieta = dados.get("dieta_enteral") or {}
        if dieta.get("nome") in self.formula_por_nome:
            self.cb_formula.set(dieta["nome"])
        _set = lambda e, v: (e.delete(0, "end"), e.insert(0, str(v)) if v not in (None, "") else None)
        renal = dados.get("avaliacao_renal") or {}
        self.cb_renal_ref.set(renal.get("referencia") or "KDIGO 2024")
        self.cb_drc_confirmada.set("Sim" if renal.get("drc_confirmada") is True else
                                   "Não" if renal.get("drc_confirmada") is False else
                                   ("Sim" if self.reg.get("drc") else "—"))
        self.cb_condicao_renal.set({"DRC": "DRC", "LRA": "LRA", "DRC + LRA": "DRC + LRA"}.get(
            renal.get("condicao_renal"), "DRC" if self.reg.get("drc") else "Não definida"))
        self.cb_estagio_renal.set(renal.get("estagio") or "—")
        _set(self.e_tfge, renal.get("tfge_ml_min_173"))
        _set(self.e_albuminuria, renal.get("albuminuria_mg_g"))
        self.cb_dialise.set({"nao": "Não", "hemodialise": "Hemodiálise",
                             "peritoneal": "Diálise peritoneal"}.get(renal.get("dialise"), "Não"))
        _set(self.e_frequencia_dialise, renal.get("frequencia_dialise_semana"))
        _set(self.e_duracao_dialise, renal.get("duracao_dialise_horas"))
        _set(self.e_inicio_dialise, renal.get("inicio_dialise"))
        self.cb_estabilidade_renal.set({"estavel": "Estável", "instavel": "Instável",
                                        "nao_informada": "Não informada"}.get(
                                            renal.get("estabilidade_metabolica"), "Não informada"))
        for cb, chave in ((self.cb_catabolismo, "catabolismo"),
                          (self.cb_risco_desnutricao, "risco_desnutricao"),
                          (self.cb_sarcopenia, "fragilidade_sarcopenia")):
            valor = renal.get(chave)
            cb.set("Sim" if valor is True else "Não" if valor is False else "Não informado")
        _set(self.e_creatinina, (renal.get("exames_apoio") or {}).get("creatinina"))
        _set(self.e_ureia, (renal.get("exames_apoio") or {}).get("ureia"))
        _set(self.e_albumina_serica, (renal.get("exames_apoio") or {}).get("albumina_serica"))
        if renal:
            self._avaliar_renal()
        _set(self.e_volume_etapa, dieta.get("volume_por_etapa_ml"))
        _set(self.e_etapas, dieta.get("etapas", 1))
        progressao = dados.get("progressao_enteral") or {}
        self.var_progressao.set(int(bool(progressao.get("solicitada"))))
        _set(self.e_incremento, progressao.get("incremento_por_etapa_ml", 10))
        _set(self.e_dias, progressao.get("dias_alvo", 4))
        bomba_salva = dados.get("bomba") or {}
        self.var_bomba.set(int(bool(bomba_salva.get("usa_bomba"))))
        _set(self.e_horas_adm, bomba_salva.get("duracao_horas"))
        _set(self.e_fator_gotas, bomba_salva.get("fator_gotas_ml"))
        self.var_tolerancia.set(int(bool(progressao.get("tolerancia", True))))
        self.var_restricao.set(int(bool(progressao.get("restricao", False))))
        metas = dados.get("metas") or {}
        _set(self.e_kcal_kg, metas.get("kcal_kg"))
        _set(self.e_ptn_kg, metas.get("proteina_g_kg"))
        self.t_observacoes.insert("1.0", dados.get("observacoes") or "")
        self.t_conduta.insert("1.0", dados.get("conduta") or "")
        for s, qtd, etapas in self.sup_fields:
            salvo = next((x for x in dados.get("suplementacao", []) if x.get("nome") == s.get("nome")), None)
            if salvo:
                _set(qtd, salvo.get("quantidade"))
                _set(etapas, salvo.get("etapas", 1))
        if not metas and self._peso_nutricional():
            peso = self._peso_nutricional()
            if self.reg.get("meta_kcal"):
                _set(self.e_kcal_kg, round(float(self.reg["meta_kcal"]) / peso, 2))
            if self.reg.get("meta_proteina_g"):
                _set(self.e_ptn_kg, round(float(self.reg["meta_proteina_g"]) / peso, 2))
        self._atualizar_metas()

    def _atualizar_correcao(self):
        try:
            av = json.loads(self.reg.get("avaliacao_json") or "{}")
        except (TypeError, ValueError):
            av = {}
        resultado = av.get("resultado") or av
        if not resultado.get("ajustou"):
            self.lbl_correcao.configure(text="")
            return
        original = resultado.get("peso")
        final = resultado.get("ajustado", av.get("peso_ajustado"))
        if original in (None, "") or final in (None, ""):
            avisos = resultado.get("avisos") or av.get("avisos") or []
            self.lbl_correcao.configure(
                text="Correção antropométrica não calculável. " + " ".join(str(x) for x in avisos),
                text_color=tema.ERRO)
            return
        dados_av = resultado.get("dados") or av.get("dados") or {}
        edema = avaliacao.EDEMA.get(dados_av.get("edema"), 0)
        ascite = avaliacao.ASCITE.get(dados_av.get("ascite"), 0)
        amputacao = resultado.get("amput_pct", 0)
        self.lbl_correcao.configure(
            text=("Correção antropométrica — " +
                  f"peso original: {regras.formatar_numero_pt(original, 1)} kg; " +
                  f"edema: {regras.formatar_numero_pt(edema, 1)} kg; " +
                  f"ascite: {regras.formatar_numero_pt(ascite, 1)} kg; " +
                  f"amputação: {regras.formatar_numero_pt(amputacao, 1)}%; " +
                  f"peso nutricional final: {regras.formatar_numero_pt(final, 1)} kg."))


    @staticmethod
    def _tri_bool(texto):
        return True if texto == "Sim" else False if texto == "Não" else None

    def _dados_renal(self):
        texto_dialise = self.cb_dialise.get()
        estabilidade = {"Estável": "estavel", "Instável": "instavel",
                        "Não informada": "nao_informada"}.get(self.cb_estabilidade_renal.get(), "nao_informada")
        dados = {
            "referencia": self.cb_renal_ref.get(),
            "condicao_renal": {"Não definida": "NAO_DEFINIDA"}.get(
                self.cb_condicao_renal.get(), self.cb_condicao_renal.get()),
            "drc_confirmada": self._tri_bool(self.cb_drc_confirmada.get()),
            "estagio": None if self.cb_estagio_renal.get() == "—" else self.cb_estagio_renal.get(),
            "tfge": self.e_tfge.get().strip() or None,
            "albuminuria_mg_g": self.e_albuminuria.get().strip() or None,
            "dialise": {"Não": "nao", "Hemodiálise": "hemodialise",
                        "Diálise peritoneal": "peritoneal"}.get(texto_dialise, "nao"),
            "frequencia_dialise_semana": self.e_frequencia_dialise.get().strip() or None,
            "duracao_dialise_horas": self.e_duracao_dialise.get().strip() or None,
            "inicio_dialise": self.e_inicio_dialise.get().strip() or None,
            "estabilidade_metabolica": estabilidade,
            "catabolismo": self._tri_bool(self.cb_catabolismo.get()),
            "risco_desnutricao": self._tri_bool(self.cb_risco_desnutricao.get()),
            "fragilidade_sarcopenia": self._tri_bool(self.cb_sarcopenia.get()),
            "creatinina": self.e_creatinina.get().strip() or None,
            "ureia": self.e_ureia.get().strip() or None,
            "albumina_serica": self.e_albumina_serica.get().strip() or None,
        }
        preenchido = (dados["condicao_renal"] != "NAO_DEFINIDA" or
                      dados["drc_confirmada"] is not None or dados["estagio"] or dados["tfge"] or
                      dados["albuminuria_mg_g"] or dados["dialise"] != "nao" or
                      dados["estabilidade_metabolica"] != "nao_informada" or
                      any(dados[k] for k in ("creatinina", "ureia", "albumina_serica")))
        if not preenchido:
            return None
        return regras.avaliar_contexto_renal(
            dados, peso_kg=self._peso_nutricional(), idade_anos=self.reg.get("idade_anos"),
            diabetes=bool(self.reg.get("dm")))

    def _avaliar_renal(self):
        try:
            renal = self._dados_renal()
            if not renal:
                self.lbl_renal.configure(text="Informe dados renais para avaliar a referência.")
                return
            rec = renal["recomendacao_proteica"]
            gkg = rec.get("g_kg_dia")
            gdia = rec.get("g_dia")
            texto = rec["texto"]
            if gkg is not None:
                texto += f" Referência: {gkg} g/kg/dia"
                if gdia is not None:
                    gdia_txt = regras.formatar_numero_pt(gdia, 1) if isinstance(gdia, (int, float)) else str(gdia)
                    texto += f" ({gdia_txt} g/dia)"
                texto += "."
            if renal["faixa_tfge"]:
                texto += f" Faixa TFGe: {renal['faixa_tfge']}."
            if renal["categoria_albuminuria"]:
                texto += f" Albuminúria: {renal['categoria_albuminuria']}."
            if renal["avisos"]:
                texto += " " + " ".join(renal["avisos"])
            self.lbl_renal.configure(text=texto)
        except (ValueError, TypeError) as exc:
            self.lbl_renal.configure(text=str(exc), text_color=tema.ERRO)

    def _atualizar_metas(self):
        try:
            peso = self._peso_nutricional()
            kcalkg = float(self.e_kcal_kg.get().replace(",", "."))
            ptnkg = float(self.e_ptn_kg.get().replace(",", "."))
            self.lbl_metas.configure(
                text=f"Meta: {peso * kcalkg:.0f} kcal/dia · {peso * ptnkg:.1f} g PTN/dia")
        except (TypeError, ValueError):
            self.lbl_metas.configure(text="Informe kcal/kg e g proteína/kg para calcular as metas.")

    def _peso_nutricional(self):
        try:
            av = json.loads(self.reg.get("avaliacao_json") or "{}")
        except (TypeError, ValueError):
            av = {}
        resultado = av.get("resultado") or av
        peso = resultado.get("ajustado", av.get("peso_ajustado"))
        if peso in (None, "") and resultado.get("ajustou"):
            return None
        if peso in (None, ""):
            peso = self.reg.get("peso_kg")
        return float(peso) if peso not in (None, "") else None

    def _antropometria(self):
        try:
            av = json.loads(self.reg.get("avaliacao_json") or "{}")
        except (TypeError, ValueError):
            av = {}
        try:
            oms = json.loads(self.reg.get("pediatria_oms_json") or "{}")
        except (TypeError, ValueError):
            oms = {}
        resultados = oms.get("resultados") or {}
        imc_oms = resultados.get("imc_idade") or {}
        idade_reg = self.reg.get("idade_anos")
        nascimento = self.paciente.get("data_nascimento") or self.reg.get("data_nascimento")
        data_ref = mdb.iso_para_br(self.reg.get("data"))
        if idade_reg is None and nascimento:
            idade_reg = regras.idade_em_anos(nascimento, data_ref)
        if idade_reg is not None and int(idade_reg) < 20:
            classificacao = (imc_oms.get("classificacao") if imc_oms.get("status") == "calculado"
                             else "OMS pendente")
        else:
            classificacao = av.get("classe") or (av.get("resultado") or {}).get("classe") or self.reg.get("imc_class")
        resultado = av.get("resultado") or av
        peso = resultado.get("ajustado", av.get("peso_ajustado"))
        if peso in (None, "") and not resultado.get("ajustou"):
            peso = self.reg.get("peso_kg")
        idade = self.reg.get("idade_anos")
        if idade is None and nascimento:
            idade = regras.idade_em_anos(nascimento, data_ref)
        return {
            "data": data_ref,
            "idade_anos": idade,
            "data_nascimento": nascimento,
            "altura_cm": self.reg.get("altura_cm"),
            "altura_origem": self.reg.get("altura_origem") or "R",
            "peso_kg": peso,
            "peso_origem": self.reg.get("peso_origem") or "R",
            "peso_corrigido": bool(resultado.get("ajustou") or av.get("ajustou") or (
                peso not in (None, "") and self.reg.get("peso_kg") not in (None, "") and
                abs(float(peso) - float(self.reg["peso_kg"])) > 0.0001)),
            "imc_class": classificacao,
            "aj_cm": self.reg.get("aj_cm"), "pp_cm": self.reg.get("pp_cm"),
            "pb_cm": self.reg.get("pb_cm"),
        }

    def _dados(self, para_fechamento=False):
        antropometria = self._antropometria()
        peso = self._peso_nutricional()
        txt_kcal, txt_ptn = self.e_kcal_kg.get().strip(), self.e_ptn_kg.get().strip()
        if bool(txt_kcal) != bool(txt_ptn):
            raise ValueError("Informe os dois parâmetros: kcal/kg e g proteína/kg.")
        metas = None
        if txt_kcal and txt_ptn:
            if peso is None:
                raise ValueError("Peso nutricional ausente para calcular as metas.")
            metas = regras.calcular_metas(peso, txt_kcal, txt_ptn)
        elif para_fechamento:
            raise ValueError("Informe os parâmetros energéticos e proteicos antes do fechamento.")
        via = str(self.reg.get("via") or "").casefold()
        dados = {
            "data_evolucao": self.reg.get("data"),
            "antropometria": antropometria,
            "metas": metas,
            "via": self.reg.get("via"),
            "dva": True if self.seg_dva.get() == "Sim" else False if self.seg_dva.get() == "Não" else None,
            "tno": self.cb_tno.get() if via == "oral" and self.cb_tno.get() != "—" else None,
            "tne_motivos": [m for m, v in self.tne_vars.items() if v.get()] if via == "enteral" else [],
            "dieta_oral": {
                "consistencia": self.reg.get("consistencia"),
                "caracteristicas": [sigla for campo, sigla in (
                    ("dm", "DM"), ("has", "HAS"), ("laxativa", "LAX"),
                    ("constipante", "CON"), ("drc", "DRC")) if self.reg.get(campo)]
            } if via == "oral" else None,
            "porcao_oral_ml": int(self.cb_porcao.get()) if via == "oral" and self.cb_porcao.get() else None,
            "porcao_oral_solicitada": bool(self.var_solicitar_porcao.get()) if via == "oral" else False,
            "observacoes": self.t_observacoes.get("1.0", "end-1c").strip(),
            "conduta": self.t_conduta.get("1.0", "end-1c").strip(),
        }
        dados["avaliacao_renal"] = self._dados_renal()
        suplementacao = []
        for s, qtd, etapas in self.sup_fields:
            quantidade_txt = qtd.get().strip()
            etapas_txt = etapas.get().strip() or "1"
            quantidade = float(quantidade_txt.replace(",", ".")) if quantidade_txt else 0
            n_etapas_num = float(etapas_txt.replace(",", "."))
            if not n_etapas_num.is_integer():
                raise ValueError(f"Número de etapas de {s.get('nome', 'suplemento')} deve ser inteiro.")
            n_etapas = int(n_etapas_num)
            if quantidade > 0:
                suplementacao.append({"nome": s["nome"], "quantidade": quantidade,
                                      "unidade": s.get("unidade") or "mL", "etapas": n_etapas})
        dados["suplementacao"] = suplementacao
        if via == "enteral":
            nome = self.cb_formula.get()
            ficha = self.formula_por_nome.get(nome)
            volume_txt = self.e_volume_etapa.get().strip()
            etapas_txt = self.e_etapas.get().strip() or "1"
            volume_etapa = float(volume_txt.replace(",", ".")) if volume_txt else 0
            etapas_num = float(etapas_txt.replace(",", "."))
            if not etapas_num.is_integer():
                raise ValueError("Número de etapas da dieta enteral deve ser inteiro.")
            etapas = int(etapas_num)
            if ficha and volume_etapa > 0 and etapas > 0 and metas:
                dias_num = float((self.e_dias.get().strip() or "4").replace(",", "."))
                if not dias_num.is_integer():
                    raise ValueError("Prazo da progressão deve ser inteiro (3 ou 4 dias).")
                oferta = regras.calcular_oferta_enteral(
                    volume_etapa, etapas, ficha["kcal_100"], ficha["ptn_100"])
                volume_meta = metas["kcal_dia"] / (ficha["kcal_100"] / 100)
                oferta["volume_meta_ml"] = volume_meta
                dados["oferta"] = oferta
                dados["dieta_enteral"] = {
                    "nome": nome, "volume_por_etapa_ml": volume_etapa, "etapas": etapas,
                    "kcal_100": ficha["kcal_100"], "ptn_100": ficha["ptn_100"],
                }
                dados["bomba"] = {"usa_bomba": bool(self.var_bomba.get()), "taxa_estimativa_ml_h": 10}
                tipo_formula = str(ficha.get("tipo_formula") or "").strip().casefold()
                dados["dieta_enteral"]["tipo_formula"] = tipo_formula or "nao_informado"
                if tipo_formula == "fechada":
                    horas_txt = self.e_horas_adm.get().strip()
                    if not horas_txt:
                        raise ValueError("Informe em quantas horas a dieta fechada será administrada.")
                    fator_txt = self.e_fator_gotas.get().strip()
                    if not self.var_bomba.get() and not fator_txt:
                        raise ValueError("Informe o fator de gotas/mL indicado no equipo utilizado.")
                    if self.var_bomba.get() and not fator_txt:
                        fator_txt = "20"  # ignorado no cálculo da bomba
                    # Dimensiona a administração pelo volume necessário para atingir a meta
                    # energética, não apenas pelo volume parcial atualmente selecionado.
                    administracao = regras.planejar_administracao_enteral(
                        volume_meta, ficha["kcal_100"], horas_txt,
                        usa_bomba=bool(self.var_bomba.get()), fator_gotas_ml=fator_txt)
                    administracao["volume_etapas_atual_ml"] = oferta["volume_total_ml"]
                    administracao["meta_kcal_dia"] = metas["kcal_dia"]
                    dados["bomba"].update({"duracao_horas": float(horas_txt.replace(",", "."))})
                    if not self.var_bomba.get():
                        dados["bomba"]["fator_gotas_ml"] = float(fator_txt.replace(",", "."))
                    dados["administracao_enteral"] = administracao
                dados["progressao_enteral"] = {
                    "solicitada": bool(self.var_progressao.get()), "autorizada": False,
                    "volume_atual_ml": oferta["volume_total_ml"], "volume_meta_ml": volume_meta,
                    "volume_etapa_atual_ml": volume_etapa, "etapas": etapas,
                    "incremento_diario_ml": float((self.e_incremento.get().strip() or "35").replace(",", ".")),
                    "dias_alvo": int(dias_num),
                    "volume_maximo_ml": (float(self.e_volume_maximo.get().strip().replace(",", "."))
                                         if self.e_volume_maximo.get().strip() else None),
                    "tolerancia": bool(self.var_tolerancia.get()), "restricao": bool(self.var_restricao.get()),
                }
            else:
                dados["dieta_enteral"] = {"nome": nome}
                dados["progressao_enteral"] = {"solicitada": False, "autorizada": False}
        return dados

    def _colaboradores(self):
        ids = [mid for mid, var in self.colab_vars.items() if var.get()]
        op = self.cb_elaborador.get()
        membro = self.membro_por_op.get(op)
        if not membro:
            raise ValueError("Selecione um elaborador principal cadastrado.")
        if membro["id_membro"] not in ids:
            ids.append(membro["id_membro"])
        return membro["id_membro"], ids

    def _salvar_rascunho(self):
        try:
            if not self.reg.get("id_paciente"):
                raise ValueError("Vincule o paciente ao cadastro clínico antes de salvar a evolução.")
            dados = self._dados()
            if dados.get("metas"):
                self.form_registro.e_meta_kcal.delete(0, "end")
                self.form_registro.e_meta_kcal.insert(0, str(round(dados["metas"]["kcal_dia"], 1)))
                self.form_registro.e_meta_ptn.delete(0, "end")
                self.form_registro.e_meta_ptn.insert(0, str(round(dados["metas"]["proteina_g_dia"], 1)))
                if not self.form_registro._salvar(manter_aberto=True):
                    raise ValueError("Não foi possível sincronizar as metas com o registro do Mapa.")
                self.reg = mdb.obter_registro(self.db, self.reg["data"], self.reg["id_leito"]) or self.reg
                self.form_registro.reg = self.reg
            id_elaborador, colaboradores = self._colaboradores()
            self.id_rascunho = evdb.salvar_rascunho(
                self.db, self.reg["id_paciente"], self.reg["data"], dados, id_elaborador,
                self.id_rascunho, colaboradores_ids=colaboradores)
            dados["id_rascunho"] = self.id_rascunho
            dados["status_evolucao"] = "rascunho"
            mdb.salvar_dados_evolucao(self.db, self.reg["id_registro"], dados)
            self.reg = mdb.obter_registro(self.db, self.reg["data"], self.reg["id_leito"]) or self.reg
            self.form_registro.reg = self.reg
            self.ui._recarregar()
            self.lbl_status.configure(text=f"Rascunho #{self.id_rascunho} salvo. Ainda não é uma evolução fechada.",
                                       text_color=tema.VERDE)
            return True
        except (ValueError, TypeError, evdb.EvolucaoPEPError) as exc:
            self.lbl_status.configure(text=str(exc), text_color=tema.ERRO)
            return False

    def _fechar(self):
        if not self._salvar_rascunho():
            return
        op = self.cb_revisor.get()
        revisor = self.revisor_por_op.get(op)
        if not revisor:
            self.lbl_status.configure(text="Selecione um nutricionista com conta PEP e CRN conferido.",
                                       text_color=tema.ERRO)
            return
        senha = self.e_senha.get()
        if not senha:
            self.lbl_status.configure(text="Informe a senha do nutricionista para autenticar o fechamento.",
                                       text_color=tema.ERRO)
            return
        try:
            dados = self._dados(para_fechamento=True)
            progressao = dados.get("progressao_enteral") or {}
            progressao["autorizada"] = False
            progressao.pop("plano", None)
            dados["progressao_enteral"] = progressao
            dados["porcao_oral_autorizada"] = False
            id_elaborador, colaboradores = self._colaboradores()
            self.id_rascunho = evdb.salvar_rascunho(
                self.db, self.reg["id_paciente"], self.reg["data"], dados, id_elaborador,
                self.id_rascunho, colaboradores_ids=colaboradores)
            dados["id_rascunho"] = self.id_rascunho
            dados["status_evolucao"] = "rascunho"
            mdb.salvar_dados_evolucao(self.db, self.reg["id_registro"], dados)
            if not messagebox.askyesno(
                "Confirmar fechamento",
                "O nutricionista revisou os dados, conferiu metas e conduta e confirma o fechamento definitivo desta evolução?",
                parent=self.app):
                return
            id_evolucao = evdb.fechar_rascunho(
                self.db, self.id_rascunho, revisor["id_usuario"], senha, confirmado=True,
                autorizar_progressao=bool(self.var_autorizar_progressao.get()),
                autorizar_porcao_oral=bool(self.var_autorizar_porcao.get()))
            finalizado = evdb.obter_rascunho(self.db, self.id_rascunho)
            dados = finalizado["dados"]
            dados["id_rascunho"] = self.id_rascunho
            dados["id_evolucao"] = id_evolucao
            dados["status_evolucao"] = "fechada"
            dados["fechada"] = True
            mdb.salvar_dados_evolucao(self.db, self.reg["id_registro"], dados)
            self.reg = mdb.obter_registro(self.db, self.reg["data"], self.reg["id_leito"]) or self.reg
            self.form_registro.reg = self.reg
            self.ui._recarregar()
            self.lbl_status.configure(
                text=f"Evolução #{id_evolucao} fechada e assinada por {revisor['nome']} — {revisor['crn']}.",
                text_color=tema.VERDE)
            self._somente_leitura()
        except (ValueError, TypeError, evdb.EvolucaoPEPError, sqlite3.Error) as exc:
            self.lbl_status.configure(text=str(exc), text_color=tema.ERRO)

    def _somente_leitura(self):
        for widget in self.winfo_children():
            try:
                widget.configure(state="disabled")
            except (AttributeError, tk.TclError):
                pass
        def desabilitar(pai):
            for filho in pai.winfo_children():
                try:
                    filho.configure(state="disabled")
                except (AttributeError, tk.TclError):
                    pass
                desabilitar(filho)
        desabilitar(self)
        self.b_salvar.configure(state="disabled")
        self.b_fechar.configure(state="disabled")

    def _fechar_painel(self):
        self.app.fechar_painel_lateral(self.painel)
