# -*- coding: utf-8 -*-
"""Tela 'Avaliação e evolução': peso ajustado (edema, ascite, várias amputações), comparação com a DRI e
evolução PEP automática, assinada por usuário individual. Só interface: a lógica está em avaliacao_nutri e pep_db."""
import io
import traceback
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

import avaliacao_nutri as av
import mapa_db as mdb
import nutri_calculos as nc
import pep_db as pep
import tema as t

ATIV = ["Sedentário", "Pouco ativo", "Ativo", "Muito ativo"]
HOJE = datetime.now().strftime("%d/%m/%Y")
CAMPOS = [
    ("Paciente", [("paciente", "Nome do paciente (ou prontuário)", "e", ""), ("sexo", "Sexo", "s", ["Mulher", "Homem"]),
                  ("cor", "Raça/cor (equações de Chumlea)", "s", ["Branca", "Preta"]),
                  ("idade", "Idade (anos completos)", "e", "")]),
    ("Peso e altura", [("peso", "Peso aferido (kg) — vazio = estimar", "e", ""),
                       ("altura", "Altura aferida (cm) — vazio = estimar", "e", ""),
                       ("aj", av.sig("AJ") + " (cm)", "e", ""), ("pb", av.sig("PB") + " (cm)", "e", "")]),
    ("Edema, ascite e amputações (ajuste do peso)", [("edema", "Edema (retenção hídrica)", "s", list(av.EDEMA)),
                                                     ("ascite", "Ascite", "s", list(av.ASCITE))]),
    ("Metas", [("kcalkg", "Meta — kcal/kg/dia", "e", "25"), ("ptnkg", av.sig("PTN") + " — meta (g/kg/dia)", "e", "1,0"),
               ("atividade", "Atividade física (para a DRI)", "s", ATIV)]),
    ("Dados clínicos", [("adm", "Admissão (dd/mm/aaaa)", "e", ""), ("evo", "Evolução (dd/mm/aaaa)", "e", HOJE),
                        ("dva", av.sig("DVA"), "s", ["NÃO", "SIM"]), ("ahgt", av.sig("AHGT"), "e", "100 - 130 mg/dL (24h)"),
                        ("fi", av.sig("F.I.") + " (24h)", "e", "Presente, 1 episódio / há X dias"),
                        ("diar", "Fezes diarreicas", "s", ["Não", "Sim"]),
                        ("via", "Via de alimentação", "s", ["Oral", "Enteral", "Oral + Enteral"]),
                        ("vo", av.sig("V.O.") + " — aceitação", "e", "N/A"), ("tol", av.sig("TNE") + " — tolerância", "e", "n/a"),
                        ("tno", av.sig("TNO") + " — dieta", "e", "n/a"), ("sup", "Suplementação", "e", "Não"),
                        ("tv", "TNE — volume (ml/h)", "e", "n/a"), ("tm", "TNE — atinge meta calórica?", "e", "n/a"),
                        ("tp", "TNE — proteína (g/kg de peso)", "e", "n/a"), ("obs", "Observações", "t", "n/a")]),
    ("Conduta (escrita pelo nutricionista)", [("ct", "Conduta", "s", ["Mantida", "Nova conduta"]),
                                              ("cx", "Texto da nova conduta", "t", "")]),
]


class AvaliacaoUI:
    def __init__(self, app, db, raiz):
        self.app, self.db, self.raiz, self.pronto = app, db, raiz, False
        self.usuario, self.w, self.ant, self._chave = None, {}, None, None

    # ------------------------------------------------------------------ construção
    def construir(self):
        """Monta a tela uma única vez (o programa chama ao abrir); depois só se troca de página, sem recriar widgets."""
        if self.pronto:
            return
        raiz = self.raiz
        for w in raiz.winfo_children():  # recomeça limpo se uma tentativa anterior falhou no meio
            w.destroy()
        self.w = {}
        raiz.grid_columnconfigure(0, weight=1)
        raiz.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(raiz, text="Avaliação e evolução nutricional", font=t.fonte(22, "bold"),
                     text_color=t.VERDE).grid(row=0, column=0, sticky="w", padx=20, pady=(14, 4))
        self.divisor = tk.PanedWindow(raiz, orient="horizontal", sashwidth=10, sashrelief="flat", bd=0, bg=t.FUNDO,
                                      opaqueresize=False)
        self.divisor.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        painel_esq = ctk.CTkFrame(self.divisor, fg_color="transparent")  # o divisor só aceita filhos diretos
        esq = ctk.CTkScrollableFrame(painel_esq, fg_color="transparent")
        esq.pack(fill="both", expand=True)
        for titulo, campos in CAMPOS:
            g = self._card(esq, titulo)
            self._campos(g, campos)
            if titulo.startswith("Edema"):
                self._amputacoes(g)
            if titulo == "Metas":
                self._suplementos(esq)
        self._painel(self.divisor)
        self.divisor.add(painel_esq, minsize=340, stretch="always")
        self.divisor.add(self.direita, minsize=360, stretch="always")
        self.divisor.bind("<ButtonRelease-1>", self._salvar_divisor)
        self.atualizar()
        self.pronto = True

    def mostrar(self):
        try:
            self.construir()
        except Exception as erro:  # mostra o erro em vez de deixar a tela em branco
            traceback.print_exc()
            messagebox.showerror("Avaliação e evolução", f"Não foi possível montar a tela:\n{erro}\n\n"
                                 "Copie esta mensagem e envie ao suporte.")
            return
        self.app.mostrar_pagina(self.raiz)
        self.raiz.after(60, self._restaurar_divisor)

    def _restaurar_divisor(self):  # o programa lembra onde você deixou o divisor entre preenchimento e resultados
        largura = self.divisor.winfo_width()
        if largura > 1:
            frac = min(max(self.app.prefs.get("avaliacao_divisor", 0.6), 0.3), 0.8)
            self.divisor.sash_place(0, int(largura * frac), 0)

    def _salvar_divisor(self, _=None):
        largura = self.divisor.winfo_width()
        if largura > 1:
            self.app.prefs.set("avaliacao_divisor", round(self.divisor.sash_coord(0)[0] / largura, 3))

    def _card(self, pai, titulo):
        c = ctk.CTkFrame(pai, fg_color=t.BRANCO, border_width=1, border_color=t.BORDA, corner_radius=10)
        c.pack(fill="x", padx=(0, 12), pady=(0, 12))
        ctk.CTkLabel(c, text=titulo, font=t.fonte(14, "bold"), text_color=t.VERDE).pack(anchor="w", padx=14, pady=(10, 4))
        g = ctk.CTkFrame(c, fg_color="transparent")
        g.pack(fill="x", padx=10, pady=(0, 10))
        g.grid_columnconfigure((0, 1), weight=1, uniform="c")
        return g

    def _campos(self, g, campos, linha=0):
        col = 0
        for chave, rotulo, tipo, extra in campos:
            if tipo == "t" and col == 1:
                linha, col = linha + 1, 0
            cx = ctk.CTkFrame(g, fg_color="transparent")
            cx.grid(row=linha, column=col, columnspan=2 if tipo == "t" else 1, sticky="ew", padx=4, pady=3)
            ctk.CTkLabel(cx, text=rotulo, font=t.fonte(12), text_color=t.SUAVE, anchor="w").pack(fill="x")
            if tipo == "s":
                w = t.Selecao(cx, values=extra, command=lambda _: self.atualizar(), fg_color=t.BRANCO,
                                      text_color=t.TEXTO, button_color=t.VERDE, button_hover_color=t.VERDE_HOVER,
                                      dropdown_fg_color=t.BRANCO, dropdown_text_color=t.TEXTO)
                w.set(extra[0])
            else:
                w = (ctk.CTkTextbox(cx, height=62) if tipo == "t" else ctk.CTkEntry(cx))
                w.configure(border_color=t.BORDA, fg_color=t.BRANCO, text_color=t.TEXTO)
                w.insert("1.0" if tipo == "t" else 0, extra)
                w.bind("<KeyRelease>", lambda e: self.atualizar())
                if tipo == "t":  # Tab/Shift+Tab saem da caixa de texto em vez de inserir tabulação
                    w.bind("<Tab>", lambda e: (e.widget.tk_focusNext().focus(), "break")[1])
                    w.bind("<Shift-Tab>", lambda e: (e.widget.tk_focusPrev().focus(), "break")[1])
            w.pack(fill="x")
            self.w[chave] = w
            col += 2 if tipo == "t" else 1
            if col >= 2:
                linha, col = linha + 1, 0

    def _amputacoes(self, g):
        quadro = ctk.CTkFrame(g, fg_color=t.VERDE_CLARO, corner_radius=8)
        quadro.grid(row=5, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 2))
        ctk.CTkLabel(quadro, text="Amputações — quantidade por nível (marque só o nível mais alto de cada membro)",
                     font=t.fonte(12), text_color=t.SUAVE, anchor="w").grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(8, 2))
        for i, (nivel, (_, pct)) in enumerate(av.AMPUTACOES.items()):
            cx = ctk.CTkFrame(quadro, fg_color="transparent")
            cx.grid(row=1 + i // 3, column=i % 3, sticky="ew", padx=8, pady=3)
            ctk.CTkLabel(cx, text=f"{nivel} ({str(pct).replace('.', ',')}%)", font=t.fonte(12), text_color=t.TEXTO, anchor="w").pack(fill="x")
            w = t.Selecao(cx, values=["0", "1", "2"], width=80, command=lambda _: self.atualizar(),
                                  fg_color=t.BRANCO, text_color=t.TEXTO, button_color=t.VERDE, button_hover_color=t.VERDE_HOVER)
            w.set("0")
            w.pack(anchor="w")
            self.w["amp_" + nivel] = w
        quadro.grid_columnconfigure((0, 1, 2), weight=1)

    def _painel(self, raiz):
        dir_ = ctk.CTkFrame(raiz, fg_color=t.BRANCO, border_width=1, border_color=t.BORDA, corner_radius=10)
        self.direita = dir_
        self.chip = ctk.CTkLabel(dir_, text="", font=t.fonte(12, "bold"), corner_radius=99)
        self.chip.pack(anchor="w", padx=14, pady=(12, 6))
        grade = ctk.CTkFrame(dir_, fg_color="transparent")
        grade.pack(fill="x", padx=10)
        grade.grid_columnconfigure((0, 1), weight=1, uniform="k")
        self.kpi = {}
        for i, (chave, rotulo, laranja) in enumerate((("peso", "Peso ajustado (seco)", 0), ("imc", "IMC", 0),
                                                      ("meta", "Meta (kcal/dia)", 1), ("dri", "DRI (kcal/dia)", 1))):
            tile = ctk.CTkFrame(grade, fg_color=t.LARANJA_CLARO if laranja else t.VERDE_CLARO, corner_radius=8)
            tile.grid(row=i // 2, column=i % 2, sticky="ew", padx=4, pady=4)
            ctk.CTkLabel(tile, text=rotulo, font=t.fonte(12), text_color=t.SUAVE, anchor="w").pack(fill="x", padx=10, pady=(6, 0))
            self.kpi[chave] = ctk.CTkLabel(tile, text="—", font=t.fonte(20, "bold"), anchor="w",
                                           text_color=t.LARANJA_TXT if laranja else t.VERDE)
            self.kpi[chave].pack(fill="x", padx=10, pady=(0, 6))
        self.detalhe = ctk.CTkLabel(dir_, text="", font=t.fonte(13), text_color=t.TEXTO, justify="left", anchor="w")
        self.detalhe.pack(fill="x", padx=14, pady=(6, 0))
        self.avisos = ctk.CTkLabel(dir_, text="", font=t.fonte(12), text_color=t.LARANJA_TXT, fg_color=t.LARANJA_CLARO,
                                   corner_radius=8, justify="left", anchor="w", wraplength=400)
        self.rot_evo = ctk.CTkLabel(dir_, text="Evolução nutricional (PEP)", font=t.fonte(14, "bold"), text_color=t.VERDE)
        self.rot_evo.pack(anchor="w", padx=14, pady=(10, 2))
        self.saida = ctk.CTkTextbox(dir_, height=300, font=("Consolas", 12), border_width=1, border_color=t.BORDA,
                                    fg_color=t.FUNDO, text_color=t.TEXTO)
        self.saida.pack(fill="both", expand=True, padx=12)
        self.carimbo = ctk.CTkLabel(dir_, text="", font=t.fonte(12), text_color=t.SUAVE, anchor="w", compound="left")
        self.carimbo.pack(side="bottom", fill="x", padx=14, pady=(6, 0), before=self.rot_evo)
        botoes = ctk.CTkFrame(dir_, fg_color="transparent")
        botoes.pack(side="bottom", fill="x", padx=10, pady=10, before=self.carimbo)
        for texto, cmd, cor in (("Copiar evolução", self.copiar, t.LARANJA), ("Assinar e salvar", self.assinar, t.VERDE),
                                ("Entrar / trocar usuário", self._entrar, t.VERDE_ESC)):
            ctk.CTkButton(botoes, text=texto, command=cmd, fg_color=cor, hover_color=t.VERDE_HOVER if cor != t.LARANJA else "#D97A1B",
                          text_color="#2B1700" if cor == t.LARANJA else t.BRANCO, font=t.fonte(13, "bold")).pack(side="left", padx=4)

    def _suplementos(self, pai):
        """Suplemento do paciente: o aporte vem da ficha técnica do catálogo e é comparado com a meta e a DRI."""
        g = self._card(pai, "Suplementação do paciente (aporte pela ficha técnica)")
        try:
            self.catalogo = {s["nome"] + ("" if s["kcal_100"] is not None else " (ficha pendente)"): s
                             for s in mdb.listar_suplementos(self.db)}
        except Exception:  # catálogo do mapa ainda não criado neste banco
            self.catalogo = {}
        self.sups = []
        nomes = list(self.catalogo) or ["(catálogo vazio)"]
        self.sel_sup = t.Selecao(g, values=nomes, fg_color=t.BRANCO, text_color=t.TEXTO,
                                         button_color=t.VERDE, button_hover_color=t.VERDE_HOVER)
        self.sel_sup.set(nomes[0])
        self.sel_sup.grid(row=0, column=0, sticky="ew", padx=4, pady=3)
        self.qtd_sup = ctk.CTkEntry(g, placeholder_text="Quantidade por dia (ml ou g, como na ficha)", border_color=t.BORDA)
        self.qtd_sup.grid(row=0, column=1, sticky="ew", padx=4, pady=3)
        ctk.CTkButton(g, text="Adicionar", command=self._add_sup, fg_color=t.VERDE,
                      hover_color=t.VERDE_HOVER).grid(row=1, column=0, sticky="w", padx=4, pady=3)
        ctk.CTkButton(g, text="Limpar lista", command=self._limpar_sups, fg_color="transparent", text_color=t.VERDE,
                      hover_color=t.VERDE_CLARO).grid(row=1, column=1, sticky="w", padx=4)
        self.res_sup = ctk.CTkLabel(g, text="", font=t.fonte(12), text_color=t.SUAVE, justify="left", anchor="w", wraplength=520)
        self.res_sup.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 0))

    def _add_sup(self):
        ficha, qtd = self.catalogo.get(self.sel_sup.get()), nc.parse_num(self.qtd_sup.get())
        if not ficha or not qtd or qtd <= 0:
            messagebox.showwarning("Suplemento", "Escolha o suplemento e informe a quantidade por dia.")
            return
        self.sups.append((ficha, qtd))
        self.qtd_sup.delete(0, "end")
        self.atualizar()

    def _limpar_sups(self):
        self.sups = []
        self.atualizar()

    # ------------------------------------------------------------------ dados e cálculo
    def v(self, chave):
        w = self.w[chave]
        return w.get("1.0", "end").strip() if isinstance(w, ctk.CTkTextbox) else w.get().strip()

    def _definir(self, chave, valor):
        self.w[chave].delete(0, "end")
        self.w[chave].insert(0, valor)

    def _coletar(self):
        f = {k: self.v(k) for k in self.w}
        f["amputacoes"] = {n: int(f.pop("amp_" + n)) for n in av.AMPUTACOES}
        f["atividade"] = ATIV.index(f["atividade"])
        lms = getattr(getattr(self.app, "mapa", None), "lms", None)
        r = av.calcular(f, lms, getattr(getattr(self.app, "mapa", None), "criterio_idoso", "lipschitz"))
        self.res = av.resumo_suplementos(self.sups, r["kcal"], r["dri"], r["ptn"])
        if self.sups:  # com suplementos adicionados, o campo Suplementação da evolução vem do cálculo
            f["sup"] = self.res["texto"]
        return f, r

    def _assinatura(self):
        u = self.usuario
        return f"{u['nome_completo']} – {av.rotulo_crn(u['crn'])} – {datetime.now():%d/%m/%Y %H:%M}" if u else "(entre para assinar)"

    def atualizar(self):
        f, r = self._coletar()
        chave = pep.chave_paciente(f["paciente"])
        if chave != self._chave:  # trocou de paciente: busca a evolução anterior no histórico do programa
            self._chave = chave
            self.ant = pep.ultima_evolucao(self.db, f["paciente"]) if chave else None
            if chave and not self.v("adm"):
                self._definir("adm", self.ant["cabecalho"].get("adm", HOJE) if self.ant else HOJE)
                f["adm"] = self.v("adm")
        F = nc.fmt_num
        self.res_sup.configure(text=self.res["detalhe"] or "Nenhum suplemento adicionado.")
        self.chip.configure(text="  " + ("Informe o paciente" if not chave else
                                  f"Evolução anterior em {self.ant['data']}" if self.ant else "Novo paciente") + "  ",
                            fg_color=t.VERDE_CLARO if self.ant else t.LARANJA, text_color=t.VERDE if self.ant else "#2B1700")
        self.kpi["peso"].configure(text=F(r["ajustado"], 1, "—") + " kg")
        self.kpi["imc"].configure(text=F(r["imc"], 1, "—"))
        self.kpi["meta"].configure(text=F(r["kcal"], 0, "—"))
        self.kpi["dri"].configure(text=F(r["dri"], 0, "—"))
        dif = r["dif_dri_pct"]
        self.detalhe.configure(text="\n".join([
            f"Peso ({(r['tipo_peso'] or 'sem dados').lower()}): {F(r['peso'], 1, '—')} kg",
            f"Edema + ascite: {'− ' + F(r['fluidos'], 1) + ' kg' if r['fluidos'] else '—'}",
            f"Amputações: {F(r['amput_pct'], 1) + '% do peso' if r['amput_pct'] else '—'}",
            f"Altura ({(r['tipo_alt'] or 'sem dados').lower()}): {F(r['altura_m'], 2, '—')} m"
            + (f"   IMC: {r['classe']}" if r["classe"] else ""),
            f"Meta × DRI: {'+' if dif and dif > 0 else ''}{F(dif, 0, 'dados insuficientes')}{'%' if dif is not None else ''}",
            f"PTN: {F(r['ptn'], 0, '—')} g/dia ({F(r['gk'], 1, '—')} g/kg)"]))
        if r["avisos"]:
            self.avisos.configure(text="\n".join(r["avisos"]))
            self.avisos.pack(fill="x", padx=14, pady=(6, 0), before=self.rot_evo)
        else:
            self.avisos.pack_forget()
        self.saida.configure(state="normal")
        self.saida.delete("1.0", "end")
        self.saida.insert("1.0", av.montar_evolucao(f, r, self.ant["cabecalho"] if self.ant else None, self._assinatura()))
        self.saida.configure(state="disabled")
        self.carimbo.configure(text=f"Assinando como: {self.usuario['nome_completo']} — {av.rotulo_crn(self.usuario['crn'])}"
                               if self.usuario else "Ninguém identificado: clique em «Entrar / trocar usuário».")

    # ------------------------------------------------------------------ ações
    def copiar(self):
        self.app.clipboard_clear()
        self.app.clipboard_append(self.saida.get("1.0", "end").strip())

    def _entrar(self):
        dlg = _Login(self.app, self.db)
        self.app.wait_window(dlg)
        if dlg.usuario:
            self.usuario = dlg.usuario
            try:
                img = Image.open(io.BytesIO(dlg.usuario["assinatura"])) if dlg.usuario.get("assinatura") else None
            except OSError:
                img = None
            if img:
                img.thumbnail((140, 50))
                self.carimbo.configure(image=ctk.CTkImage(img, size=img.size))
            self.atualizar()

    def assinar(self):
        f, r = self._coletar()
        if not f["paciente"] or not r["ajustado"]:
            messagebox.showwarning("Dados incompletos", "Informe o paciente e o peso (aferido ou estimado).")
            return
        if not self.usuario:
            self._entrar()
        if not self.usuario or not messagebox.askyesno(
                "Assinar evolução", "Depois de assinada, a evolução não pode ser alterada (correções entram como adendo).\n\n"
                f"Assinar como {self.usuario['nome_completo']}?"):
            return
        cab = {"adm": f["adm"], "peso": r["ajustado"], "tp": r["tipo_peso"], "alt": r["altura_m"], "ta": r["tipo_alt"],
               "kk": r["kk"], "gk": r["gk"], "ajustou": r["ajustou"]}
        texto = av.montar_evolucao(f, r, self.ant["cabecalho"] if self.ant else None, self._assinatura())
        pep.salvar_evolucao(self.db, f["paciente"], f["evo"], cab, texto, self.usuario["id"])
        self._chave = None
        self.atualizar()
        messagebox.showinfo("Evolução assinada", "Salva no histórico do paciente.")


class _Login(ctk.CTkToplevel):
    """Etapa 1: senha do hospital. Etapa 2: escolher o usuário (ou criar: nome completo, CRN, assinatura)."""

    def __init__(self, pai, db):
        super().__init__(pai)
        self.db, self.usuario, self.imagem = db, None, None
        self.title("Identificação")
        self.geometry("420x470")
        self.configure(fg_color=t.BRANCO)
        self.transient(pai)
        self.after(150, self.grab_set)
        self.corpo = ctk.CTkFrame(self, fg_color="transparent")
        self.corpo.pack(fill="both", expand=True, padx=24, pady=18)
        self._hospital()

    def _tela(self, titulo):
        for w in self.corpo.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.corpo, text=titulo, font=t.fonte(16, "bold"), text_color=t.VERDE, wraplength=370, justify="left").pack(anchor="w", pady=(0, 8))

    def _ent(self, rotulo, oculto=False):
        ctk.CTkLabel(self.corpo, text=rotulo, font=t.fonte(12), text_color=t.SUAVE, anchor="w").pack(fill="x")
        e = ctk.CTkEntry(self.corpo, show="•" if oculto else "", border_color=t.BORDA)
        e.pack(fill="x", pady=(0, 6))
        return e

    def _fim(self, texto, cmd):
        self.erro = ctk.CTkLabel(self.corpo, text="", text_color=t.LARANJA_TXT, wraplength=370, justify="left")
        self.erro.pack(anchor="w")
        ctk.CTkButton(self.corpo, text=texto, command=cmd, fg_color=t.LARANJA, hover_color="#D97A1B", text_color="#2B1700",
                      font=t.fonte(13, "bold")).pack(fill="x", pady=(6, 0))

    def _hospital(self):
        primeira = not pep.hospital_configurado(self.db)
        self._tela("Primeiro acesso: defina a senha do hospital" if primeira else "Acesso do hospital")
        s1, s2 = self._ent("Senha do hospital", True), (self._ent("Repita a senha", True) if primeira else None)

        def ok():
            try:
                if primeira:
                    if s1.get() != s2.get():
                        raise ValueError("As senhas não conferem.")
                    pep.definir_senha_hospital(self.db, s1.get())
                elif not pep.entrar_hospital(self.db, s1.get()):
                    raise ValueError("Senha do hospital incorreta.")
            except ValueError as erro:
                self.erro.configure(text=str(erro))
                return
            self._usuarios()
        self._fim("Continuar", ok)

    def _usuarios(self):
        lista = pep.listar_usuarios(self.db)
        if not lista:
            return self._novo()
        self._tela("Quem está atendendo?")
        nomes = {f"{u['nome_completo']} — CRN {u['crn']}": u["id"] for u in lista}
        escolha = t.Selecao(self.corpo, values=list(nomes), fg_color=t.BRANCO, text_color=t.TEXTO,
                                    button_color=t.VERDE, button_hover_color=t.VERDE_HOVER)
        escolha.pack(fill="x", pady=(0, 8))
        senha = self._ent("Sua senha pessoal", True)

        def ok():
            u = pep.autenticar(self.db, nomes[escolha.get()], senha.get())
            if u:
                self.usuario = u
                self.destroy()
            else:
                self.erro.configure(text="Senha incorreta.")
        self._fim("Entrar", ok)
        ctk.CTkButton(self.corpo, text="Criar novo usuário", command=self._novo, fg_color="transparent", text_color=t.VERDE,
                      hover_color=t.VERDE_CLARO).pack(fill="x", pady=4)

    def _novo(self):
        self._tela("Novo usuário")
        nome, crn, login, senha = (self._ent("Nome completo"), self._ent("CRN (ex.: CRN-6 12345)"),
                                   self._ent("Login"), self._ent("Senha pessoal (mín. 6 caracteres)", True))
        rot = ctk.CTkLabel(self.corpo, text="Assinatura: nenhuma imagem escolhida", font=t.fonte(12), text_color=t.SUAVE, anchor="w")

        def escolher():
            caminho = filedialog.askopenfilename(parent=self, filetypes=[("Imagem", "*.png *.jpg *.jpeg")])
            if caminho:
                dados = open(caminho, "rb").read()
                try:
                    Image.open(io.BytesIO(dados)).verify()
                    if len(dados) > 1_000_000:
                        raise ValueError
                except (OSError, ValueError):
                    self.erro.configure(text="Use uma imagem PNG/JPG de até 1 MB.")
                    return
                self.imagem = dados
                rot.configure(text="Assinatura: " + caminho.replace("\\", "/").split("/")[-1])
        ctk.CTkButton(self.corpo, text="Escolher imagem da assinatura", command=escolher, fg_color=t.VERDE,
                      hover_color=t.VERDE_HOVER).pack(fill="x")
        rot.pack(fill="x", pady=(2, 4))

        def ok():
            try:
                uid = pep.criar_usuario(self.db, login.get(), nome.get(), crn.get(), senha.get(), self.imagem)
            except ValueError as erro:
                self.erro.configure(text=str(erro))
                return
            self.usuario = pep.autenticar(self.db, uid, senha.get())
            self.destroy()
        self._fim("Criar e entrar", ok)
