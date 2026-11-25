# -*- coding: utf-8 -*-
"""Telas do Mapa Nutricional (CustomTkinter): mapa do dia, registro por leito, histórico,
leitos, suplementos (ficha técnica) e gráficos mensais.

A lógica (cálculos, banco, exportação, gráficos) fica nos módulos nutri_calculos, mapa_db,
mapa_export e mapa_graficos; aqui só há interface. mapa_export e mapa_graficos são
importados na hora de usar (openpyxl, fpdf e matplotlib não atrasam a abertura do programa).
"""
import os
import json
import sqlite3
from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import customtkinter as ctk

import nutri_calculos as nc
import nrs2002 as nrs
import suplementos_calculos as sc
import avaliacao_nutri as avaliacao
import mapa_db as mdb
import condutas_alta as ca
import graficos_layout as gl
import tema
import pediatria_oms as oms

VERDE_ESC, VERDE, VERDE_HOVER, FUNDO = tema.VERDE_ESC, tema.VERDE, tema.VERDE_HOVER, tema.FUNDO
CINZA_BTN, CINZA_HOVER = tema.SUAVE, tema.SUAVE
VERMELHO, VERMELHO_HOVER, LARANJA = tema.ERRO, tema.ERRO_HOVER, tema.LARANJA
ESTILO_TREE = "Mapa.Treeview"


def _estilo_tree():
    st = ttk.Style()
    st.configure(ESTILO_TREE, font=("Segoe UI", 10), rowheight=28)


def _btn(master, texto, comando, largura=140, cor=VERDE, hover=VERDE_HOVER, altura=32):
    return ctk.CTkButton(master, text=texto, command=comando, width=largura, height=altura, fg_color=cor,
                         hover_color=hover, text_color=tema.BRANCO, font=ctk.CTkFont(size=12, weight="bold"))


def _titulo(master, texto):
    return ctk.CTkLabel(master, text=texto, font=ctk.CTkFont(size=24, weight="bold"), text_color=VERDE_ESC)


def _set_entry(entry, texto):
    entry.delete(0, "end")
    if texto not in (None, ""):
        entry.insert(0, str(texto))


def _fmt(v, casas=1):
    return nc.fmt_num(v, casas, vazio="")


def _tornar_modal(janela):
    try:
        janela.lift()
        janela.focus_force()
        janela.grab_set()
    except tk.TclError:
        pass


class MapaUI:
    """Ponto de entrada usado pelo main.py: mostrar_mapa, mostrar_graficos e mostrar_suplementos."""

    def __init__(self, app, db_path, base_dir):
        self.app, self.db, self.base_dir = app, db_path, base_dir
        self.data = date.today()
        self.id_setor = None
        self.lms = None  # tabelas LMS para avaliação nutricional geral.
        for pasta in (os.path.dirname(os.path.abspath(db_path)), base_dir):
            self.lms = self.lms or nc.TabelaLMS.carregar_padrao(pasta)
        self.tabela_oms = None
        self.erro_tabela_oms = None
        for pasta in (base_dir, os.path.dirname(os.path.abspath(db_path))):
            try:
                self.tabela_oms = self.tabela_oms or oms.TabelaReferenciaOMS.carregar_padrao(pasta)
            except (OSError, ValueError) as exc:
                self.erro_tabela_oms = str(exc)
        self._imagens = []
        self._grupos = None
        self._grupos_png = None
        self._painel = None

    # ------------------------------------------------------------------ configurações
    @property
    def criterio_idoso(self):
        return mdb.obter_config(self.db, "criterio_idoso", "lipschitz")

    @property
    def metodo_altura_idoso(self):
        return mdb.obter_config(self.db, "metodo_altura_idoso", "chumlea1985")

    @property
    def estilo_graficos(self):
        return gl.estilo_valido(mdb.obter_config(self.db, gl.CHAVE_ESTILO, gl.ESTILO_ANIMADO))

    @property
    def disposicao_graficos(self):
        """Como a tela de gráficos mostra cada grupo: lado a lado (arrastar) ou de cima para baixo."""
        return gl.disposicao_valida(mdb.obter_config(self.db, gl.CHAVE_CONFIG, gl.DISPOSICAO_LADO_A_LADO))

    def _preparar_area(self):
        self.app.limpar_area_principal()
        try:
            if self.app.winfo_width() < 1180:
                alt = min(780, max(600, self.app.winfo_screenheight() - 90))
                self.app.geometry(f"1240x{alt}")
        except tk.TclError:
            pass
        _estilo_tree()
        return self.app.area_principal

    # =========================================================================== MAPA
    def mostrar_mapa(self):
        area = self._preparar_area()
        self.setores = mdb.listar_setores(self.db)
        if self.id_setor not in [s["id_setor"] for s in self.setores]:
            self.id_setor = None

        cabecalho = ctk.CTkFrame(area, fg_color="transparent")
        cabecalho.pack(fill="x", padx=24, pady=(18, 8))
        titulo_area = ctk.CTkFrame(cabecalho, fg_color="transparent")
        titulo_area.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(titulo_area, text="NUTRILAB  /  ASSISTÊNCIA NUTRICIONAL",
                     font=ctk.CTkFont(size=10, weight="bold"), text_color=tema.VERDE).pack(anchor="w")
        _titulo(titulo_area, "Mapa Nutricional").pack(anchor="w", pady=(1, 0))
        ctk.CTkLabel(titulo_area, text="Acompanhamento diário dos pacientes e leitos",
                     font=ctk.CTkFont(size=12), text_color=tema.SUAVE).pack(anchor="w", pady=(1, 0))
        _btn(cabecalho, "Configurações", self._abrir_config, 130, CINZA_BTN, CINZA_HOVER).pack(side="right", padx=(8, 0))
        _btn(cabecalho, "Ordem do mapa geral", self._abrir_ordem_setores, 150, CINZA_BTN, CINZA_HOVER).pack(side="right", padx=6)
        _btn(cabecalho, "Gerenciar setores", self._abrir_leitos, 135, tema.VERDE_ESC, tema.VERDE_HOVER).pack(side="right", padx=6)
        _btn(cabecalho, "+ Adicionar leitos", self._abrir_adicionar_leitos, 145, tema.VERDE_ESC, tema.VERDE_HOVER).pack(side="right")

        filtros = ctk.CTkFrame(area, fg_color=tema.BRANCO, corner_radius=12,
                              border_width=1, border_color=tema.BORDA)
        filtros.pack(fill="x", padx=24, pady=(4, 8))
        ctk.CTkLabel(filtros, text="PERÍODO", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=tema.SUAVE).pack(side="left", padx=(14, 8), pady=12)
        _btn(filtros, "‹", lambda: self._mudar_dia(-1), 34, CINZA_BTN, CINZA_HOVER, 30).pack(side="left", pady=9)
        self.e_data = ctk.CTkEntry(filtros, width=112, justify="center", height=32)
        self.e_data.pack(side="left", padx=5, pady=9)
        self.e_data.bind("<Return>", lambda e: self._aplicar_data())
        _btn(filtros, "›", lambda: self._mudar_dia(1), 34, CINZA_BTN, CINZA_HOVER, 30).pack(side="left", pady=9)
        _btn(filtros, "Hoje", self._ir_hoje, 62, tema.VERDE_CLARO, tema.VERDE_CLARO, 30).pack(side="left", padx=(7, 18), pady=9)
        ctk.CTkFrame(filtros, width=1, height=28, fg_color=tema.BORDA).pack(side="left", padx=(0, 14), pady=9)
        ctk.CTkLabel(filtros, text="SETOR", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=tema.SUAVE).pack(side="left", padx=(0, 8), pady=12)
        self.cb_setor = ctk.CTkComboBox(
            filtros, values=["Visão geral (Internos e Externos)"] + [mdb.rotulo_setor(s) for s in self.setores],
            width=245, height=32, state="readonly", command=self._trocar_setor)
        self.cb_setor.pack(side="left", padx=(0, 12), pady=9)
        self.cb_setor.set(next((mdb.rotulo_setor(s) for s in self.setores if s["id_setor"] == self.id_setor),
                               "Visão geral (Internos e Externos)"))

        acoes = ctk.CTkFrame(area, fg_color="transparent")
        acoes.pack(fill="x", padx=24, pady=(2, 7))
        _btn(acoes, "+  Preencher leito", self._editar, 160).pack(side="left", padx=(0, 6))
        _btn(acoes, "Histórico", self._historico, 94, CINZA_BTN, CINZA_HOVER).pack(side="left", padx=3)
        _btn(acoes, "Condutas de alta", self._condutas_alta, 132, LARANJA, tema.LARANJA).pack(side="left", padx=3)
        _btn(acoes, "Copiar último mapa", self._copiar_ultimo, 142, CINZA_BTN, CINZA_HOVER).pack(side="left", padx=3)
        _btn(acoes, "Remover", self._remover, 88, VERMELHO, VERMELHO_HOVER).pack(side="left", padx=3)
        _btn(acoes, "Excel", self._exportar_excel, 72, tema.AZUL, tema.AZUL_HOVER).pack(side="right")
        _btn(acoes, "PDF", self._exportar_pdf, 64, tema.AZUL, tema.AZUL_HOVER).pack(side="right", padx=6)

        avisos = ctk.CTkFrame(area, fg_color="transparent")
        avisos.pack(fill="x", padx=26, pady=(0, 2))
        self.lbl_aviso = ctk.CTkLabel(avisos, text="", text_color=LARANJA,
                                      font=ctk.CTkFont(size=11, weight="bold"), anchor="w")
        self.lbl_aviso.pack(fill="x", anchor="w")
        self.lbl_condutas = ctk.CTkLabel(avisos, text="", text_color=LARANJA,
                                         font=ctk.CTkFont(size=11, weight="bold"), anchor="w", justify="left")
        self.lbl_condutas.pack(fill="x", anchor="w")
        self.lbl_inicio = ctk.CTkLabel(
            area, text="Selecione um leito vazio e clique em 'Preencher leito' para iniciar.",
            text_color=tema.SUAVE, anchor="w", justify="left")
        self.lbl_inicio.pack(fill="x", padx=28, pady=(2, 0), anchor="w")

        quadro = ctk.CTkFrame(area, fg_color=tema.BRANCO, corner_radius=12,
                              border_width=1, border_color=tema.BORDA)
        quadro.pack(fill="both", expand=True, padx=24, pady=(5, 7))
        cab_tabela = ctk.CTkFrame(quadro, fg_color="transparent")
        cab_tabela.pack(fill="x", padx=14, pady=(10, 3))
        ctk.CTkLabel(cab_tabela, text="PACIENTES E LEITOS",
                     font=ctk.CTkFont(size=11, weight="bold"), text_color=tema.VERDE_ESC).pack(side="left")
        ctk.CTkLabel(cab_tabela, text="Selecione um leito • duplo clique abre a ficha",
                     font=ctk.CTkFont(size=10), text_color=tema.SUAVE).pack(side="right")
        area_tabela = ctk.CTkFrame(quadro, fg_color="transparent")
        area_tabela.pack(fill="both", expand=True, padx=10, pady=(2, 0))
        colunas = [("leito", "Leito", 60, "center"), ("grupo", "Grupo", 85, "center"),
                   ("setor", "Setor", 180, "w"), ("acomp", "Acomp.", 60, "center"),
                   ("paciente", "Paciente", 220, "w"), ("idade", "Idade", 50, "center"),
                   ("imc", "IMC (classificação)", 170, "w"), ("via", "Via", 70, "center"),
                   ("consist", "Consistência", 85, "center"),
                   ("supl", "Terapia nutricional", 210, "w"), ("fi", "Função intestinal", 110, "center"),
                   ("condutas", "Condutas de alta", 120, "center")]
        self.tree = ttk.Treeview(area_tabela, columns=[c[0] for c in colunas], show="headings",
                                 style=ESTILO_TREE, selectmode="browse")
        for chave, titulo, larg, anc in colunas:
            self.tree.heading(chave, text=titulo)
            self.tree.column(chave, width=larg, anchor=anc, stretch=chave in ("paciente", "supl", "setor"))
        self.tree.tag_configure("vago", foreground=tema.cor_atual(tema.SUAVE))
        self.tree.tag_configure("condpend", foreground=tema.cor_atual(tema.LARANJA))
        rolagem = ttk.Scrollbar(area_tabela, orient="vertical", command=self.tree.yview)
        rolagem_x = ttk.Scrollbar(area_tabela, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=rolagem.set, xscrollcommand=rolagem_x.set)
        self.tree.pack(side="top", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")
        rolagem_x.pack(side="bottom", fill="x")
        self.tree.bind("<Double-1>", lambda e: self._editar())
        self.tree.bind("<Return>", self._atalho_editar)
        self.tree.bind("<F2>", self._atalho_editar)
        self.tree.bind("<Control-h>", self._atalho_historico)
        self.tree.bind("<Control-H>", self._atalho_historico)

        self.lbl_resumo = ctk.CTkLabel(area, text="", font=ctk.CTkFont(size=11, weight="bold"),
                                       text_color=tema.TEXTO)
        self.lbl_resumo.pack(fill="x", padx=28, pady=(0, 12), anchor="w")
        self._recarregar()

    def _trocar_setor(self, nome):
        self.id_setor = next((s["id_setor"] for s in self.setores if mdb.rotulo_setor(s) == nome), None)
        self._recarregar()

    def _mudar_dia(self, delta):
        self.data += timedelta(days=delta)
        self._recarregar()

    def _ir_hoje(self):
        self.data = date.today()
        self._recarregar()

    def _aplicar_data(self):
        try:
            self.data = datetime.strptime(self.e_data.get().strip(), "%d/%m/%Y").date()
        except ValueError:
            messagebox.showwarning("Data inválida", "Use o formato DD/MM/AAAA.")
        self._recarregar()

    def _recarregar(self):
        _set_entry(self.e_data, self.data.strftime("%d/%m/%Y"))
        hoje = date.today()
        if self.data == hoje:
            self.lbl_aviso.configure(text="")
        else:
            rel = "dia anterior" if self.data < hoje else "dia futuro"
            self.lbl_aviso.configure(text=f"Você está no mapa de {self.data.strftime('%d/%m/%Y')} ({rel}). "
                                          "As alterações ficam gravadas nessa data.")
        self.linhas = mdb.mapa_do_dia(self.db, self.data.isoformat(), self.id_setor)
        resumo = self._resumo_condutas()
        self.tree.delete(*self.tree.get_children())
        ocupados = past = acomp = sup_oral = oral_sem = enteral = com_pendencia = 0
        for it in self.linhas:
            l, r = it["leito"], it["registro"]
            if r is None:
                vals = (l["codigo"], l.get("grupo_setor") or "Outros",
                        f"{l.get('setor', '')} - {l.get('sigla_setor')}" if l.get("sigla_setor") else l.get("setor", ""),
                        "", "— vago —", "", "", "", "", "", "", "")
                tag = ("vago",)
            else:
                ocupados += 1
                past += r.get("consistencia") == "Pastosa"
                acomp += bool(r.get("acompanhante"))
                if r.get("via") == "Enteral":
                    enteral += 1
                elif r.get("via") == "Oral":
                    if r.get("suplementos"):
                        sup_oral += 1
                    else:
                        oral_sem += 1
                imc = f"{_fmt(r.get('imc'))} ({r['imc_class']})" if r.get("imc") and r.get("imc_class") else _fmt(r.get("imc"))
                cond = resumo.get(r.get("id_paciente"), {})
                itens_terapia = ", ".join(s["nome"] + (" (batido com fruta)" if s.get("batido_fruta") else "")
                                           for s in r["suplementos"])
                if r.get("via") == "Enteral":
                    itens_terapia = "Dieta enteral" + (": " + itens_terapia if itens_terapia else " (fórmula não informada)")
                elif r.get("via") == "Zero":
                    itens_terapia = "Via zero"
                elif itens_terapia:
                    itens_terapia = "Suplementação oral: " + itens_terapia
                vals = (l["codigo"], r.get("grupo_setor") or "Outros",
                        f"{r.get('setor', '')} - {r.get('sigla_setor')}" if r.get("sigla_setor") else r.get("setor", ""),
                        "Sim" if r.get("acompanhante") else "Não", r["nome_paciente"],
                        "" if r.get("idade_anos") is None else r["idade_anos"], imc, r.get("via") or "",
                        r.get("consistencia") or "", itens_terapia, self._fi_txt(r), cond.get("texto", ""))
                tag = ("condpend",) if cond.get("estado") == "pendente" else ()
                com_pendencia += cond.get("estado") == "pendente"
            self.tree.insert("", "end", iid=str(l["id_leito"]), values=vals, tags=tag)
        self._mostrar_aviso_condutas(com_pendencia)
        total = len(self.linhas)
        if ocupados == 0 and total:
            self.lbl_inicio.configure(text="Primeiro preenchimento: selecione um leito vazio e clique em 'Preencher leito'. "
                                           "Você também pode dar duplo clique na linha.")
        elif total:
            self.lbl_inicio.configure(text="Para atualizar um paciente, selecione o leito e clique em 'Preencher leito' "
                                           "ou dê duplo clique na linha.")
        else:
            self.lbl_inicio.configure(text="Adicione os leitos do setor para começar.")
        if not total:
            self.lbl_resumo.configure(text="Nenhum leito cadastrado neste setor. Use '+ Adicionar leitos' para começar.")
        else:
            self.lbl_resumo.configure(
                text=f"{ocupados} de {total} leitos com registro  ·  {past} em dieta pastosa  ·  "
                     f"{acomp} com acompanhante  ·  {ocupados - sup_oral - enteral} em via oral sem suplemento  ·  "
                     f"{sup_oral} com suplementação oral  ·  {enteral} em dieta enteral")

    # ------------------------------------------------------------------ condutas de alta
    def _catalogo_condutas(self):
        if getattr(self, "_cat_condutas", None) is None:
            self._cat_condutas = ca.carregar_catalogo()     # ErroCatalogo se algum arquivo estiver inválido
        return self._cat_condutas

    def _resumo_condutas(self):
        """{id_paciente: resumo} das condutas de alta dos registros do dia. Se o módulo falhar (catálogo inválido,
        banco sem a migração), o Mapa continua funcionando e a falha aparece em vermelho acima da lista."""
        self._erro_condutas = ""
        try:
            return ca.resumo_por_registro(self.db, [it["registro"] for it in self.linhas if it["registro"]],
                                          self._catalogo_condutas())
        except ca.ErroCondutasAlta as erro:
            self._erro_condutas = " ".join(str(erro).split("\n")[:2])
        except sqlite3.Error as erro:
            self._erro_condutas = f"erro no banco de dados ({erro})"
        return {}

    def _mostrar_aviso_condutas(self, com_pendencia):
        if self._erro_condutas:
            self.lbl_condutas.configure(text="Condutas de alta indisponíveis: " + self._erro_condutas,
                                        text_color=VERMELHO)
        elif com_pendencia:
            self.lbl_condutas.configure(
                text=f"{com_pendencia} {'paciente' if com_pendencia == 1 else 'pacientes'} com condutas de alta "
                     "pendentes: confirme antes da alta (botão \"Condutas de alta\").", text_color=LARANJA)
        else:
            self.lbl_condutas.configure(text="")

    def _pendencias_condutas(self, r):
        """Quantas condutas de alta sugeridas ainda esperam decisão para este registro (0 se o módulo falhar)."""
        try:
            res = ca.resumo_por_registro(self.db, [r], self._catalogo_condutas())
        except (ca.ErroCondutasAlta, sqlite3.Error):
            return 0
        return res.get(r.get("id_paciente"), {}).get("pendentes", 0)

    def _condutas_alta(self):
        it = self._selecionado()
        if not it:
            return
        if not it["registro"]:
            messagebox.showinfo("Condutas de alta", "Este leito não tem paciente registrado neste dia.")
            return
        self._abrir_condutas(it)

    def _abrir_condutas(self, it):
        from condutas_alta_ui import abrir_condutas_alta        # na hora de usar: evita importação circular
        r = it["registro"]
        if not r.get("id_paciente"):             # registro antigo/solto: sem paciente não há onde guardar a folha
            messagebox.showinfo("Condutas de alta", ca.MSG_SEM_PACIENTE)
            return
        pasta = getattr(self.app, "pasta_condutas_alta", None)
        abrir_condutas_alta(self.app, self.db, r["id_paciente"], r["nome_paciente"],
                            pasta(r["id_paciente"]) if pasta else None, ao_fechar=self._recarregar)

    @staticmethod
    def _fi_txt(r):
        if r.get("fi_estado") == "P":
            return f"Presente ({_fmt(r.get('fi_freq')).replace(',0', '') or '?'}x/d)"
        if r.get("fi_estado") == "A":
            return f"Ausente ({r.get('fi_dias_ausente') if r.get('fi_dias_ausente') is not None else '?'} d)"
        return ""

    def _selecionado(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Mapa", "Selecione um leito na lista.")
            return None
        return next((it for it in self.linhas if str(it["leito"]["id_leito"]) == sel[0]), None)

    def _editar(self):
        it = self._selecionado()
        if it:
            FormRegistro(self, it)

    def _atalho_editar(self, _evento=None):
        """Abre o formulário do leito selecionado (Enter/F2)."""
        self._editar()
        return "break"

    def _atalho_historico(self, _evento=None):
        """Abre o histórico do paciente selecionado (Ctrl+H)."""
        self._historico()
        return "break"

    def _historico(self):
        it = self._selecionado()
        if not it:
            return
        if not it["registro"]:
            messagebox.showinfo("Histórico", "Este leito não tem paciente registrado neste dia.")
            return
        DialogHistorico(self, it["registro"])

    def _remover(self):
        it = self._selecionado()
        if not it:
            return
        if not it["registro"]:
            messagebox.showinfo("Mapa", "Este leito já está vago neste dia.")
            return
        r = it["registro"]
        pend = self._pendencias_condutas(r)
        if pend:
            resp = messagebox.askyesnocancel(
                "Condutas de alta pendentes",
                f"{r['nome_paciente']} tem {pend} "
                f"{'conduta de alta' if pend == 1 else 'condutas de alta'} aguardando confirmação da nutricionista.\n\n"
                "Sim: abrir as condutas de alta agora (o paciente continua no mapa)\n"
                "Não: remover do mapa mesmo assim\nCancelar: voltar")
            if resp is None:
                return
            if resp:
                self._abrir_condutas(it)
                return
        if messagebox.askyesno("Remover do mapa",
                               f"Remover {r['nome_paciente']} do leito {it['leito']['codigo']} em "
                               f"{self.data.strftime('%d/%m/%Y')}?\n\nUse para alta ou transferência. "
                               "Os registros de outros dias são mantidos."):
            mdb.remover_registro(self.db, r["id_registro"])
            self._recarregar()

    def _copiar_ultimo(self):
        anterior = mdb.ultima_data_com_registros(self.db, self.data.isoformat(), self.id_setor)
        if not anterior:
            messagebox.showinfo("Copiar mapa", "Não há mapa anterior a esta data neste setor.")
            return
        if not messagebox.askyesno(
                "Copiar mapa",
                f"Copiar os pacientes do mapa de {mdb.iso_para_br(anterior)} para {self.data.strftime('%d/%m/%Y')}?\n\n"
                "Leitos que já têm registro neste dia não são alterados. Depois, ajuste o que mudou "
                "e remova quem teve alta."):
            return
        n = mdb.copiar_mapa(self.db, anterior, self.data.isoformat(), self.id_setor)
        self._recarregar()
        messagebox.showinfo("Copiar mapa", f"{n} registro(s) copiado(s).")

    # ------------------------------------------------------------------- exportações
    def _nome_setor(self):
        return next((mdb.rotulo_setor(s) for s in self.setores if s["id_setor"] == self.id_setor), "Todos_os_setores")

    def _exportar(self, extensao, rotulo, funcao):
        if not self.linhas:
            messagebox.showinfo("Exportar", "Não há leitos para exportar.")
            return
        nome = f"Mapa_{self._nome_setor().replace(' ', '_')}_{self.data.strftime('%Y-%m-%d')}{extensao}"
        caminho = filedialog.asksaveasfilename(defaultextension=extensao, initialfile=nome,
                                               filetypes=[(rotulo, "*" + extensao)])
        if not caminho:
            return
        try:
            funcao(caminho)
        except ImportError as e:
            messagebox.showerror("Biblioteca ausente", f"{e}\n\nInstale com:  pip install openpyxl fpdf")
            return
        except OSError as e:
            messagebox.showerror("Exportar", f"Não foi possível gravar o arquivo:\n{e}")
            return
        except Exception as e:  # erro inesperado de biblioteca: mostra em vez de falhar em silêncio
            messagebox.showerror("Exportar", f"Erro ao gerar o arquivo:\n{type(e).__name__}: {e}")
            return
        if messagebox.askyesno("Exportar", "Arquivo gerado. Deseja abri-lo agora?"):
            if hasattr(os, "startfile"):
                os.startfile(caminho)  # Windows

    def _exportar_pdf(self):
        import mapa_export as mex
        self._exportar(".pdf", "PDF",
                       lambda c: mex.exportar_pdf(c, self.linhas, self.data.isoformat(), self._nome_setor()))

    def _exportar_excel(self):
        import mapa_export as mex
        self._exportar(".xlsx", "Excel",
                       lambda c: mex.exportar_excel(c, self.linhas, self.data.isoformat(), self._nome_setor()))

    # ----------------------------------------------------------------------- diálogos
    def _abrir_leitos(self):
        DialogLeitos(self)

    def _abrir_adicionar_leitos(self):
        DialogAdicionarLeitos(self)

    def _abrir_ordem_setores(self):
        DialogOrdemSetores(self)

    def _abrir_config(self):
        DialogConfig(self)

    # ======================================================================= GRÁFICOS
    def mostrar_graficos(self):
        try:
            import mapa_graficos as mgr
        except ImportError as e:
            messagebox.showerror("Biblioteca ausente", f"{e}\n\nInstale com:  pip install matplotlib")
            return
        area = self._preparar_area()
        self.setores = mdb.listar_setores(self.db)
        meses = mdb.meses_com_dados(self.db)
        hoje = date.today()
        ano, mes = meses[0] if meses else (hoje.year, hoje.month)

        _titulo(area, "Gráficos do Mês").pack(anchor="w", padx=20, pady=(15, 5))
        barra = ctk.CTkFrame(area, fg_color="transparent")
        barra.pack(fill="x", padx=20, pady=4)
        self._mgr = mgr
        ctk.CTkLabel(barra, text="Mês:").pack(side="left")
        self.cb_mes = ctk.CTkComboBox(barra, values=[m.capitalize() for m in mgr.MESES], width=130, state="readonly")
        self.cb_mes.pack(side="left", padx=6)
        self.cb_mes.set(mgr.MESES[mes - 1].capitalize())
        ctk.CTkLabel(barra, text="Ano:").pack(side="left", padx=(8, 0))
        anos = sorted({a for a, _ in meses} | {hoje.year}, reverse=True)
        self.cb_ano = ctk.CTkComboBox(barra, values=[str(a) for a in anos], width=80, state="readonly")
        self.cb_ano.pack(side="left", padx=6)
        self.cb_ano.set(str(ano))
        ctk.CTkLabel(barra, text="Setor:").pack(side="left", padx=(8, 0))
        self.cb_setor_g = ctk.CTkComboBox(barra, values=["Visão geral (Internos e Externos)"] + [mdb.rotulo_setor(s) for s in self.setores],
                                          width=180, state="readonly")
        self.cb_setor_g.pack(side="left", padx=6)
        self.cb_setor_g.set("Visão geral (Internos e Externos)")
        _btn(barra, "Gerar", self._gerar_graficos, 90).pack(side="left", padx=(10, 6))
        _btn(barra, "Salvar imagens", self._salvar_graficos, 130, CINZA_BTN, CINZA_HOVER).pack(side="left")
        _btn(barra, "Configurações", self._abrir_config, 120, CINZA_BTN, CINZA_HOVER).pack(side="right")

        self.quadro_kpi = ctk.CTkFrame(area, fg_color="transparent")
        self.quadro_kpi.pack(fill="x", padx=20, pady=(8, 2))
        self.quadro_graf = ctk.CTkScrollableFrame(area, fg_color=tema.BRANCO)
        self.quadro_graf.pack(fill="both", expand=True, padx=20, pady=(4, 12))
        self._agg = self._grupos = self._grupos_png = self._painel = None
        self._gerar_graficos()

    def _parametros_graficos(self):
        mes = [m.capitalize() for m in self._mgr.MESES].index(self.cb_mes.get()) + 1
        ano = int(self.cb_ano.get())
        nome = self.cb_setor_g.get()
        id_setor = next((s["id_setor"] for s in self.setores if mdb.rotulo_setor(s) == nome), None)
        return ano, mes, id_setor

    def _gerar_graficos(self):
        for w in list(self.quadro_graf.winfo_children()) + list(self.quadro_kpi.winfo_children()):
            w.destroy()
        self._imagens = []
        ctk.CTkLabel(self.quadro_graf, text="Gerando gráficos...").pack(pady=20)
        self.app.update_idletasks()
        ano, mes, id_setor = self._parametros_graficos()
        regs = mdb.registros_do_mes(self.db, ano, mes, id_setor)
        self._agg = self._mgr.agregar_mes(regs, ano, mes)
        k = self._agg["kpis"]
        cartoes = [("Atendimentos", f"{k['atendimentos']}"), ("Pacientes diferentes", f"{k['pacientes_unicos']}"),
                   ("Média por dia", f"{k['media_por_dia']:.1f}".replace(".", ",")),
                   ("Dieta pastosa", f"{k['pastosa']} ({k['pastosa_pct']:.0f}%)"),
                   ("Com acompanhante", f"{k['acompanhante']} ({k['acompanhante_pct']:.0f}%)"),
                   ("Oral sem suplemento", f"{k['oral_sem_suplemento']} ({k['oral_sem_suplemento_pct']:.0f}%)"),
                   ("Oral com suplemento", f"{k['oral_com_suplemento']} ({k['oral_com_suplemento_pct']:.0f}%)"),
                   ("Dieta enteral", f"{k['enteral']} ({k['enteral_pct']:.0f}%)")]
        for rot, val in cartoes:
            cx = ctk.CTkFrame(self.quadro_kpi, fg_color=tema.BRANCO, corner_radius=8)
            cx.pack(side="left", padx=4, ipadx=8, ipady=4)
            ctk.CTkLabel(cx, text=val, font=ctk.CTkFont(size=18, weight="bold"), text_color=VERDE_ESC).pack(padx=8)
            ctk.CTkLabel(cx, text=rot, font=ctk.CTkFont(size=11), text_color=tema.SUAVE).pack(padx=8)
        self._grupos = self._mgr.especificar_por_grupo(self._agg)
        self._grupos_png = None
        self._montar_painel()

    def _grupos_para_o_estilo(self):
        if self.estilo_graficos == gl.ESTILO_ANIMADO:
            return self._grupos or []
        if self._grupos_png is None:
            try:
                self._grupos_png = self._mgr.renderizar_grupos(self._grupos or [])
            except ImportError as e:
                messagebox.showwarning("Imagens simples", f"{e}\n\nEste estilo precisa de:  pip install matplotlib\n"
                                                          "Mostrando os gráficos animados.")
                return self._grupos or []
        return self._grupos_png

    def _montar_painel(self):
        import graficos_ui
        for w in self.quadro_graf.winfo_children():
            w.destroy()
        self._painel = graficos_ui.PainelGraficos(
            self.quadro_graf, self._grupos_para_o_estilo(), self.disposicao_graficos
        )
        self._imagens = self._painel.imagens

    def aplicar_config_graficos(self):
        """Depois de salvar as Configurações: se a tela de gráficos está aberta, redesenha no novo jeito.

        Não gera os gráficos de novo (é a parte demorada): só reorganiza os que já existem.
        """
        quadro = getattr(self, "quadro_graf", None)
        try:
            aberta = quadro is not None and bool(quadro.winfo_exists()) and self._grupos is not None
        except tk.TclError:
            aberta = False
        if aberta:
            self._montar_painel()

    def _salvar_graficos(self):
        if not self._agg:
            return
        pasta = filedialog.askdirectory(title="Escolha a pasta para salvar as imagens")
        if not pasta:
            return
        try:
            caminhos = self._mgr.salvar_graficos(self._agg, pasta)
        except ImportError as e:
            messagebox.showerror("Biblioteca ausente", f"{e}\n\nInstale com:  pip install matplotlib")
            return
        except OSError as e:
            messagebox.showerror("Salvar imagens", f"Não foi possível gravar:\n{e}")
            return
        messagebox.showinfo("Salvar imagens", f"{len(caminhos)} imagens salvas em:\n{pasta}")

    # ===================================================================== SUPLEMENTOS
    def mostrar_suplementos(self):
        area = self._preparar_area()
        _titulo(area, "Suplementos (ficha técnica)").pack(anchor="w", padx=20, pady=(15, 2))
        ctk.CTkLabel(area, text="Valores por 100 mL ou 100 g, conforme a ficha técnica. O módulo define o agrupamento "
                                "da lista suspensa do mapa e dos gráficos.", text_color=tema.SUAVE).pack(anchor="w", padx=22)
        barra = ctk.CTkFrame(area, fg_color="transparent")
        barra.pack(fill="x", padx=20, pady=8)
        _btn(barra, "Novo", self._novo_suplemento, 80).pack(side="left", padx=(0, 6))
        _btn(barra, "Editar", self._editar_suplemento, 80, CINZA_BTN, CINZA_HOVER).pack(side="left", padx=(0, 6))
        _btn(barra, "Ativar/Desativar", self._alternar_suplemento, 140, CINZA_BTN, CINZA_HOVER).pack(side="left", padx=(0, 6))
        _btn(barra, "Excluir", self._excluir_suplemento, 80, VERMELHO, VERMELHO_HOVER).pack(side="left", padx=(0, 12))
        self.var_inativos = tk.IntVar(value=0)
        ctk.CTkCheckBox(barra, text="Mostrar inativos", variable=self.var_inativos,
                        command=self._recarregar_suplementos).pack(side="left")
        quadro = ctk.CTkFrame(area, fg_color=tema.BRANCO)
        quadro.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        cols = [("nome", "Nome", 200, "w"), ("modulo", "Módulo", 190, "w"), ("emb", "Embalagem", 90, "center"),
                ("kcal", "kcal/100", 65, "center"), ("ptn", "ptn/100", 65, "center"), ("lip", "lip/100", 65, "center"),
                ("carb", "carb/100", 70, "center"), ("sod", "sód/100", 70, "center"), ("preco", "Preço (R$)", 80, "center"),
                ("sit", "Situação", 70, "center")]
        self.tree_sup = ttk.Treeview(quadro, columns=[c[0] for c in cols], show="headings", style=ESTILO_TREE,
                                     selectmode="browse")
        for chave, titulo, larg, anc in cols:
            self.tree_sup.heading(chave, text=titulo)
            self.tree_sup.column(chave, width=larg, anchor=anc, stretch=chave in ("nome", "modulo"))
        self.tree_sup.tag_configure("inativo", foreground=tema.cor_atual(tema.SUAVE))
        rol = ttk.Scrollbar(quadro, orient="vertical", command=self.tree_sup.yview)
        self.tree_sup.configure(yscrollcommand=rol.set)
        self.tree_sup.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        rol.pack(side="right", fill="y", pady=6)
        self.tree_sup.bind("<Double-1>", lambda e: self._editar_suplemento())
        self._recarregar_suplementos()

    def _recarregar_suplementos(self):
        self.tree_sup.delete(*self.tree_sup.get_children())
        self._sups = mdb.listar_suplementos(self.db, apenas_ativos=not self.var_inativos.get())
        for s in self._sups:
            emb = f"{_fmt(s['emb_qtd']).replace(',0', '')} {s['emb_un']}" if s["emb_qtd"] else ""
            self.tree_sup.insert("", "end", iid=str(s["id_suplemento"]), tags=() if s["ativo"] else ("inativo",),
                                 values=(s["nome"], s["modulo"] or "", emb, _fmt(s["kcal_100"]), _fmt(s["ptn_100"]),
                                         _fmt(s["lip_100"]), _fmt(s["carb_100"]), _fmt(s["sod_100"]),
                                         _fmt(s["preco"], 2), "Ativo" if s["ativo"] else "Inativo"))

    def _sup_selecionado(self):
        sel = self.tree_sup.selection()
        if not sel:
            messagebox.showinfo("Suplementos", "Selecione um suplemento na lista.")
            return None
        return next((s for s in self._sups if str(s["id_suplemento"]) == sel[0]), None)

    def _novo_suplemento(self):
        DialogSuplemento(self, None)

    def _editar_suplemento(self):
        s = self._sup_selecionado()
        if s:
            DialogSuplemento(self, s)

    def _alternar_suplemento(self):
        s = self._sup_selecionado()
        if s:
            mdb.alterar_suplemento_ativo(self.db, s["id_suplemento"], not s["ativo"])
            self._recarregar_suplementos()

    def _excluir_suplemento(self):
        s = self._sup_selecionado()
        if not s:
            return
        if messagebox.askyesno("Excluir", f"Excluir '{s['nome']}'?\n\nSe já foi usado em algum mapa, ele será apenas "
                                          "desativado, para preservar o histórico."):
            apagou = mdb.remover_suplemento(self.db, s["id_suplemento"])
            if not apagou:
                messagebox.showinfo("Suplementos", "O suplemento já foi usado em registros e foi apenas desativado.")
            self._recarregar_suplementos()


# =============================================================================== DIÁLOGOS
class _Janela(ctk.CTkFrame):
    """Conteúdo de uma guia lateral; não cria janela Toplevel nem captura o foco."""

    def __init__(self, ui, titulo, geometria):
        self.ui = ui
        self.app = getattr(ui, "app", None)
        if self.app is None and hasattr(ui, "ui"):
            self.app = getattr(ui.ui, "app", None)
        self._painel_externo = bool(self.app and hasattr(self.app, "abrir_painel_lateral"))
        if self._painel_externo:
            self._painel_frame = self.app.abrir_painel_lateral(titulo, lambda: None)
            pai = self._painel_frame
        else:
            self._painel_frame = None
            pai = self.app or ui
        super().__init__(pai, fg_color="transparent")
        self.pack(fill="both", expand=True)

    def title(self, *_args):
        return None

    def geometry(self, *_args):
        return None

    def attributes(self, *_args, **_kwargs):
        return None

    def transient(self, *_args):
        return None

    def grab_set(self):
        return None

    def protocol(self, *_args):
        return None

    def resizable(self, *_args):
        return None

    def destroy(self):
        if getattr(self, "_destroy_em_progresso", False):
            return super().destroy()
        if self._painel_externo and self._painel_frame is not None:
            try:
                if getattr(self._painel_frame, "_fechando_painel", False):
                    return super().destroy()
                self._destroy_em_progresso = True
                self.app.fechar_painel_lateral(self._painel_frame)
                return
            except (tk.TclError, AttributeError):
                pass
        return super().destroy()


class DialogConfig(_Janela):
    def __init__(self, ui):
        super().__init__(ui, "Configurações do Mapa", "560x470")
        ctk.CTkLabel(self, text="Critério de IMC para idosos (60 anos ou mais):").pack(anchor="w", padx=20, pady=(20, 2))
        self.cb_imc = ctk.CTkComboBox(self, values=list(nc.CRITERIOS_IMC_IDOSO.values()), width=500, state="readonly")
        self.cb_imc.pack(padx=20)
        self.cb_imc.set(nc.CRITERIOS_IMC_IDOSO.get(ui.criterio_idoso, nc.CRITERIOS_IMC_IDOSO["lipschitz"]))
        ctk.CTkLabel(self, text="Equação de altura a partir da altura do joelho, 60 anos ou mais:").pack(
            anchor="w", padx=20, pady=(16, 2))
        self.cb_alt = ctk.CTkComboBox(self, values=list(nc.METODOS_ALTURA_IDOSO.values()), width=500, state="readonly")
        self.cb_alt.pack(padx=20)
        self.cb_alt.set(nc.METODOS_ALTURA_IDOSO.get(ui.metodo_altura_idoso, nc.METODOS_ALTURA_IDOSO["chumlea1985"]))
        ctk.CTkLabel(self, text="Vale para os próximos registros e cálculos. Registros antigos não mudam.",
                     text_color=tema.SUAVE).pack(anchor="w", padx=20, pady=(12, 0))
        ctk.CTkLabel(self, text="Gráficos do mês (os gráficos ficam agrupados por assunto):").pack(
            anchor="w", padx=20, pady=(16, 2))
        self.cb_graf = ctk.CTkComboBox(self, values=list(gl.ROTULOS_DISPOSICAO.values()), width=500, state="readonly")
        self.cb_graf.pack(padx=20)
        self.cb_graf.set(gl.ROTULOS_DISPOSICAO[ui.disposicao_graficos])
        ctk.CTkLabel(self, text="Estilo dos gráficos:").pack(anchor="w", padx=20, pady=(16, 2))
        self.cb_estilo = ctk.CTkComboBox(self, values=list(gl.ROTULOS_ESTILO.values()), width=500, state="readonly")
        self.cb_estilo.pack(padx=20)
        self.cb_estilo.set(gl.ROTULOS_ESTILO[ui.estilo_graficos])
        _btn(self, "Salvar", self._salvar, 120).pack(pady=16)

    def _salvar(self):
        for chave, rot in nc.CRITERIOS_IMC_IDOSO.items():
            if rot == self.cb_imc.get():
                mdb.salvar_config(self.ui.db, "criterio_idoso", chave)
        for chave, rot in nc.METODOS_ALTURA_IDOSO.items():
            if rot == self.cb_alt.get():
                mdb.salvar_config(self.ui.db, "metodo_altura_idoso", chave)
        mdb.salvar_config(self.ui.db, gl.CHAVE_CONFIG, gl.rotulo_para_disposicao(self.cb_graf.get()))
        mdb.salvar_config(self.ui.db, gl.CHAVE_ESTILO, gl.rotulo_para_estilo(self.cb_estilo.get()))
        self.destroy()
        self.ui.aplicar_config_graficos()


class DialogLeitos(_Janela):
    def __init__(self, ui):
        super().__init__(ui, "Leitos e setores", "560x600")
        self.setores = mdb.listar_setores(ui.db)
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(topo, text="Setor:").pack(side="left")
        self.cb_setor = ctk.CTkComboBox(topo, values=[mdb.rotulo_setor(s) for s in self.setores], width=200, state="readonly",
                                        command=lambda v: self._recarregar())
        self.cb_setor.pack(side="left", padx=6)
        atual = next((mdb.rotulo_setor(s) for s in self.setores if s["id_setor"] == ui.id_setor),
                      mdb.rotulo_setor(self.setores[0]))
        self.cb_setor.set(atual)
        self.e_novo_setor = ctk.CTkEntry(topo, width=130, placeholder_text="Novo setor")
        self.e_novo_setor.pack(side="left", padx=(12, 4))
        _btn(topo, "Criar", self._criar_setor, 60, CINZA_BTN, CINZA_HOVER).pack(side="left")

        quadro = ctk.CTkFrame(self, fg_color=tema.BRANCO)
        quadro.pack(fill="both", expand=True, padx=16, pady=6)
        self.tree = ttk.Treeview(quadro, columns=("codigo", "situacao"), show="headings", style=ESTILO_TREE,
                                 selectmode="browse", height=10)
        self.tree.heading("codigo", text="Leito")
        self.tree.heading("situacao", text="Situação")
        self.tree.column("codigo", width=300, anchor="w")
        self.tree.column("situacao", width=120, anchor="center")
        self.tree.tag_configure("inativo", foreground=tema.SUAVE)
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)

        um = ctk.CTkFrame(self, fg_color="transparent")
        um.pack(fill="x", padx=16, pady=2)
        self.e_codigo = ctk.CTkEntry(um, width=150, placeholder_text="Código do leito")
        self.e_codigo.pack(side="left")
        _btn(um, "Adicionar", self._adicionar, 100).pack(side="left", padx=6)
        _btn(um, "Ativar/Desativar", self._alternar, 130, CINZA_BTN, CINZA_HOVER).pack(side="left")
        _btn(um, "Remover", self._remover, 90, VERMELHO, VERMELHO_HOVER).pack(side="left", padx=6)

        seq = ctk.CTkFrame(self, fg_color="transparent")
        seq.pack(fill="x", padx=16, pady=(8, 14))
        ctk.CTkLabel(seq, text="Gerar sequência:").pack(side="left")
        self.e_pref = ctk.CTkEntry(seq, width=60, placeholder_text="Prefixo")
        self.e_pref.pack(side="left", padx=4)
        self.e_de = ctk.CTkEntry(seq, width=50, placeholder_text="de")
        self.e_de.pack(side="left", padx=2)
        self.e_ate = ctk.CTkEntry(seq, width=50, placeholder_text="até")
        self.e_ate.pack(side="left", padx=2)
        _btn(seq, "Gerar", self._gerar, 70, CINZA_BTN, CINZA_HOVER).pack(side="left", padx=6)
        _btn(self, "Fechar", self._fechar, 100, CINZA_BTN, CINZA_HOVER).pack(pady=(0, 12))
        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self._recarregar()

    def _id_setor(self):
        return next(s["id_setor"] for s in self.setores if mdb.rotulo_setor(s) == self.cb_setor.get())

    def _recarregar(self):
        self.tree.delete(*self.tree.get_children())
        self.leitos = mdb.listar_leitos(self.ui.db, self._id_setor(), apenas_ativos=False)
        for l in self.leitos:
            self.tree.insert("", "end", iid=str(l["id_leito"]), values=(l["codigo"], "Ativo" if l["ativo"] else "Inativo"),
                             tags=() if l["ativo"] else ("inativo",))

    def _fechar(self):
        """Atualiza a tela do mapa (leitos/setores mudaram) e fecha."""
        self.ui.id_setor = self._id_setor()
        self.destroy()
        self.ui.mostrar_mapa()

    def _criar_setor(self):
        try:
            mdb.criar_setor(self.ui.db, self.e_novo_setor.get())
        except ValueError as e:
            messagebox.showwarning("Setor", str(e), parent=self)
            return
        self.setores = mdb.listar_setores(self.ui.db)
        self.cb_setor.configure(values=[mdb.rotulo_setor(s) for s in self.setores])
        self.cb_setor.set(self.e_novo_setor.get().strip())
        _set_entry(self.e_novo_setor, "")
        self._recarregar()

    def _adicionar(self):
        try:
            mdb.criar_leito(self.ui.db, self._id_setor(), self.e_codigo.get())
        except ValueError as e:
            messagebox.showwarning("Leito", str(e), parent=self)
            return
        _set_entry(self.e_codigo, "")
        self._recarregar()

    def _gerar(self):
        de, ate = nc.parse_num(self.e_de.get()), nc.parse_num(self.e_ate.get())
        if de is None or ate is None:
            messagebox.showwarning("Sequência", "Informe os números inicial e final.", parent=self)
            return
        try:
            n = mdb.criar_leitos_sequencia(self.ui.db, self._id_setor(), self.e_pref.get().strip(), int(de), int(ate))
        except ValueError as e:
            messagebox.showwarning("Sequência", str(e), parent=self)
            return
        messagebox.showinfo("Sequência", f"{n} leito(s) criado(s).", parent=self)
        self._recarregar()

    def _leito_sel(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Leitos", "Selecione um leito.", parent=self)
            return None
        return next(l for l in self.leitos if str(l["id_leito"]) == sel[0])

    def _alternar(self):
        l = self._leito_sel()
        if l:
            mdb.alterar_leito_ativo(self.ui.db, l["id_leito"], not l["ativo"])
            self._recarregar()

    def _remover(self):
        l = self._leito_sel()
        if l and messagebox.askyesno("Remover leito", f"Remover o leito {l['codigo']}?\n\nSe tiver histórico, "
                                     "será apenas desativado.", parent=self):
            if not mdb.remover_leito(self.ui.db, l["id_leito"]):
                messagebox.showinfo("Leitos", "O leito tem histórico e foi apenas desativado.", parent=self)
            self._recarregar()


class DialogAdicionarLeitos(_Janela):
    """Fluxo simples para cadastrar um leito ou uma faixa numérica sem prefixos técnicos."""
    def __init__(self, ui):
        super().__init__(ui, "Adicionar leitos", "500x390")
        self.setores = mdb.listar_setores(ui.db)
        ctk.CTkLabel(self, text="Escolha onde os leitos serão adicionados.",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=22, pady=(20, 4))
        ctk.CTkLabel(self, text="Setor").pack(anchor="w", padx=22, pady=(14, 2))
        self.cb_setor = ctk.CTkComboBox(self, values=[mdb.rotulo_setor(x) for x in self.setores],
                                        width=440, state="readonly")
        self.cb_setor.pack(padx=22, anchor="w")
        atual = next((mdb.rotulo_setor(x) for x in self.setores if x["id_setor"] == ui.id_setor), None)
        self.cb_setor.set(atual or (mdb.rotulo_setor(self.setores[0]) if self.setores else ""))
        linha = ctk.CTkFrame(self, fg_color="transparent")
        linha.pack(fill="x", padx=22, pady=(16, 4))
        ctk.CTkLabel(linha, text="Do leito").pack(side="left")
        self.e_de = ctk.CTkEntry(linha, width=90, placeholder_text="Ex.: 10")
        self.e_de.pack(side="left", padx=(8, 18))
        ctk.CTkLabel(linha, text="Até o leito").pack(side="left")
        self.e_ate = ctk.CTkEntry(linha, width=90, placeholder_text="Ex.: 15")
        self.e_ate.pack(side="left", padx=8)
        ctk.CTkLabel(self, text="Para adicionar apenas um leito, informe o mesmo número nos dois campos.",
                     text_color=tema.SUAVE, wraplength=440, justify="left").pack(anchor="w", padx=22, pady=(4, 12))
        self.lbl_ajuda = ctk.CTkLabel(self, text="Os leitos já existentes serão preservados.",
                                      text_color=tema.SUAVE)
        self.lbl_ajuda.pack(anchor="w", padx=22)
        _btn(self, "Adicionar leitos", self._adicionar, 180).pack(pady=(22, 8))
        _btn(self, "Cancelar", self._fechar, 100, CINZA_BTN, CINZA_HOVER).pack()
        self.protocol("WM_DELETE_WINDOW", self._fechar)

    def _fechar(self):
        self.destroy()

    def _adicionar(self):
        setor = next((x for x in self.setores if mdb.rotulo_setor(x) == self.cb_setor.get()), None)
        de, ate = nc.parse_num(self.e_de.get()), nc.parse_num(self.e_ate.get())
        if not setor:
            messagebox.showwarning("Adicionar leitos", "Selecione um setor.", parent=self)
            return
        if de is None or ate is None or int(de) != de or int(ate) != ate or de < 1 or ate < de:
            messagebox.showwarning("Adicionar leitos", "Informe números inteiros maiores que zero e um intervalo crescente.",
                                   parent=self)
            return
        try:
            n = mdb.criar_leitos_sequencia(self.ui.db, setor["id_setor"], "", int(de), int(ate), largura=1)
        except ValueError as e:
            messagebox.showwarning("Adicionar leitos", str(e), parent=self)
            return
        self.ui.id_setor = setor["id_setor"]
        messagebox.showinfo("Leitos adicionados", f"{n} novo(s) leito(s) adicionado(s).", parent=self)
        self.destroy()
        self.ui.mostrar_mapa()


class DialogOrdemSetores(_Janela):
    """Permite ordenar setores dentro dos grupos Internos e Externos para o mapa geral e impressão."""
    def __init__(self, ui):
        super().__init__(ui, "Ordem do mapa geral e impressão", "560x560")
        ctk.CTkLabel(self, text="Organize a ordem em que os setores aparecem no mapa geral e nos arquivos PDF/Excel.",
                     wraplength=510, justify="left").pack(anchor="w", padx=20, pady=(18, 8))
        ctk.CTkLabel(self, text="A ordem é ajustada dentro de cada grupo: Internos e Externos.",
                     text_color=tema.SUAVE).pack(anchor="w", padx=20, pady=(0, 8))
        quadro = ctk.CTkFrame(self, fg_color=tema.BRANCO)
        quadro.pack(fill="both", expand=True, padx=20, pady=6)
        self.tree = ttk.Treeview(quadro, columns=("grupo", "setor"), show="headings",
                                 style=ESTILO_TREE, selectmode="browse", height=12)
        self.tree.heading("grupo", text="Grupo")
        self.tree.heading("setor", text="Setor")
        self.tree.column("grupo", width=110, anchor="center")
        self.tree.column("setor", width=330, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)
        acoes = ctk.CTkFrame(self, fg_color="transparent")
        acoes.pack(fill="x", padx=20, pady=8)
        _btn(acoes, "↑ Subir", self._subir, 110, CINZA_BTN, CINZA_HOVER).pack(side="left", padx=4)
        _btn(acoes, "↓ Descer", self._descer, 110, CINZA_BTN, CINZA_HOVER).pack(side="left", padx=4)
        _btn(acoes, "Fechar", self._fechar, 100, CINZA_BTN, CINZA_HOVER).pack(side="right", padx=4)
        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self._recarregar()

    def _recarregar(self, selecionar=None):
        self.setores = mdb.listar_setores(self.ui.db)
        self.tree.delete(*self.tree.get_children())
        for setor in self.setores:
            grupo = setor.get("grupo") or "Outros"
            self.tree.insert("", "end", iid=str(setor["id_setor"]),
                             values=(grupo, mdb.rotulo_setor(setor)))
        if selecionar and any(str(x["id_setor"]) == str(selecionar) for x in self.setores):
            self.tree.selection_set(str(selecionar))

    def _mover(self, direcao):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Ordem dos setores", "Selecione um setor para mover.", parent=self)
            return
        id_setor = int(sel[0])
        mdb.alterar_ordem_setor(self.ui.db, id_setor, direcao)
        self._recarregar(id_setor)

    def _subir(self):
        self._mover(-1)

    def _descer(self):
        self._mover(1)

    def _fechar(self):
        self.destroy()
        self.ui.mostrar_mapa()


class DialogSuplemento(_Janela):
    def __init__(self, ui, sup):
        super().__init__(ui, "Suplemento", "520x560")
        self.sup = sup or {}
        self.e = {}
        quadro = ctk.CTkFrame(self, fg_color="transparent")
        quadro.pack(fill="both", expand=True, padx=20, pady=14)
        campos = [("nome", "Nome", 330), ("preco", "Preço da embalagem (R$)", 120), ("emb_qtd", "Conteúdo da embalagem", 120),
                  ("kcal_100", "kcal por 100", 120), ("ptn_100", "Proteína (g) por 100", 120),
                  ("lip_100", "Lipídio (g) por 100", 120), ("carb_100", "Carboidrato (g) por 100", 120),
                  ("sod_100", "Sódio (mg) por 100", 120)]
        linha = 0
        ctk.CTkLabel(quadro, text="Módulo").grid(row=linha, column=0, sticky="w", pady=4)
        self.cb_mod = ctk.CTkComboBox(quadro, values=mdb.listar_modulos(ui.db), width=330)
        self.cb_mod.grid(row=linha, column=1, sticky="w", pady=4)
        self.cb_mod.set(self.sup.get("modulo") or "")
        linha += 1
        for chave, rotulo, larg in campos:
            ctk.CTkLabel(quadro, text=rotulo).grid(row=linha, column=0, sticky="w", pady=4, padx=(0, 10))
            self.e[chave] = ctk.CTkEntry(quadro, width=larg)
            self.e[chave].grid(row=linha, column=1, sticky="w", pady=4)
            _set_entry(self.e[chave], self.sup.get(chave) if chave == "nome" else _fmt(self.sup.get(chave), 2).replace(",00", ""))
            if chave == "emb_qtd":
                self.cb_un = ctk.CTkComboBox(quadro, values=["ml", "g"], width=70, state="readonly")
                self.cb_un.grid(row=linha, column=2, padx=6)
                self.cb_un.set(self.sup.get("emb_un") or "ml")
            linha += 1
        ctk.CTkLabel(quadro, text="Observações").grid(row=linha, column=0, sticky="nw", pady=4)
        self.t_obs = ctk.CTkTextbox(quadro, width=330, height=70)
        self.t_obs.grid(row=linha, column=1, sticky="w", pady=4)
        self.t_obs.insert("1.0", self.sup.get("observacao") or "")
        _btn(self, "Salvar", self._salvar, 120).pack(pady=(0, 14))

    def _salvar(self):
        d = {k: e.get().strip() for k, e in self.e.items()}
        d.update(modulo=self.cb_mod.get().strip(), emb_un=self.cb_un.get(),
                 observacao=self.t_obs.get("1.0", "end-1c").strip(), id_suplemento=self.sup.get("id_suplemento"))
        try:
            mdb.salvar_suplemento(self.ui.db, d)
        except ValueError as e:
            messagebox.showwarning("Suplemento", str(e), parent=self)
            return
        self.ui._recarregar_suplementos()
        self.destroy()


class DialogBuscarPaciente(_Janela):
    """Escolhe um paciente já cadastrado para vincular ao registro (histórico unificado)."""

    def __init__(self, ui, ao_escolher):
        super().__init__(ui, "Buscar paciente cadastrado", "560x440")
        self.ao_escolher = ao_escolher
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=16, pady=(14, 4))
        self.e_busca = ctk.CTkEntry(topo, width=340, placeholder_text="Parte do nome")
        self.e_busca.pack(side="left")
        self.e_busca.bind("<KeyRelease>", lambda e: self._buscar())
        quadro = ctk.CTkFrame(self, fg_color=tema.BRANCO)
        quadro.pack(fill="both", expand=True, padx=16, pady=6)
        self.tree = ttk.Treeview(quadro, columns=("id", "nome", "nasc", "sexo"), show="headings", style=ESTILO_TREE,
                                 selectmode="browse")
        for c, t, w in (("id", "ID", 50), ("nome", "Nome", 280), ("nasc", "Nascimento", 90), ("sexo", "Sexo", 80)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w" if c == "nome" else "center")
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree.bind("<Double-1>", lambda e: self._escolher())
        self.tree.bind("<Return>", self._atalho_escolher)
        self.e_busca.bind("<Escape>", self._atalho_fechar)
        self.e_busca.bind("<Control-f>", self._atalho_focar_busca)
        self.e_busca.bind("<Control-F>", self._atalho_focar_busca)
        self.tree.bind("<Escape>", self._atalho_fechar)
        self.tree.bind("<Control-f>", self._atalho_focar_busca)
        self.tree.bind("<Control-F>", self._atalho_focar_busca)
        _btn(self, "Usar este paciente", self._escolher, 170).pack(pady=(4, 14))
        self._buscar()
        self.after(250, self.e_busca.focus_set)

    def _atalho_escolher(self, _evento=None):
        self._escolher()
        return "break"

    def _atalho_fechar(self, _evento=None):
        self.destroy()
        return "break"

    def _atalho_focar_busca(self, _evento=None):
        self.e_busca.focus_set()
        self.e_busca.icursor("end")
        return "break"

    def _buscar(self):
        self.tree.delete(*self.tree.get_children())
        self.pacs = mdb.listar_pacientes(self.ui.db, self.e_busca.get())
        for p in self.pacs:
            self.tree.insert("", "end", iid=str(p["id_paciente"]),
                             values=(p["id_paciente"], p["nome"], p["data_nascimento"] or "", p["sexo"] or ""))

    def _escolher(self):
        sel = self.tree.selection()
        if not sel:
            return
        p = next(x for x in self.pacs if str(x["id_paciente"]) == sel[0])
        self.ao_escolher(p)
        self.destroy()


class DialogHistorico(_Janela):
    def __init__(self, ui, reg):
        super().__init__(ui, "Histórico do paciente", "1100x480")
        self.reg = reg
        ctk.CTkLabel(self, text=reg["nome_paciente"], font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=VERDE_ESC).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkLabel(self, text="Duplo clique (ou o botão abaixo) abre o registro do dia, somente para consulta.",
                     text_color=tema.SUAVE).pack(anchor="w", padx=16)
        quadro = ctk.CTkFrame(self, fg_color=tema.BRANCO)
        quadro.pack(fill="both", expand=True, padx=16, pady=8)
        cols = [("data", "Data", 90), ("leito", "Leito", 60), ("peso", "Peso (kg)", 80), ("imc", "IMC", 150),
                ("via", "Via", 70), ("consist", "Consist.", 80), ("supl", "Suplementos", 220), ("reav", "Reav.", 90), ("oms", "OMS pediatria", 170)]
        self.tree = ttk.Treeview(quadro, columns=[c[0] for c in cols], show="headings", style=ESTILO_TREE,
                                 selectmode="browse")
        for c, t, w in cols:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w" if c in ("supl", "imc") else "center")
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree.bind("<Double-1>", lambda e: self._abrir())
        self.itens = mdb.historico_paciente(ui.db, reg.get("id_paciente"), reg["nome_paciente"])
        for r in self.itens:
            imc = f"{_fmt(r.get('imc'))} ({r['imc_class']})" if r.get("imc") and r.get("imc_class") else _fmt(r.get("imc"))
            try:
                oms_salvo = json.loads(r.get("pediatria_oms_json") or "{}")
            except (TypeError, ValueError):
                oms_salvo = {}
            imc_oms = (oms_salvo.get("resultados") or {}).get("imc_idade") or {}
            if imc_oms.get("status") == "calculado":
                oms_txt = f"{imc_oms.get('classificacao')} (z={imc_oms.get('escore_z'):+.2f})"
            elif imc_oms.get("status") == "pendente":
                oms_txt = "Pendente"
            elif imc_oms.get("status") == "fora_faixa":
                oms_txt = "Fora da faixa"
            else:
                oms_txt = ""
            self.tree.insert("", "end", iid=str(r["id_registro"]), values=(
                mdb.iso_para_br(r["data"]), r["leito_codigo"], _fmt(r.get("peso_kg")), imc, r.get("via") or "",
                r.get("consistencia") or "", ", ".join(s["nome"] + (" (batido com fruta)" if s.get("batido_fruta") else "") for s in r["suplementos"]),
                mdb.iso_para_br(r.get("data_reavaliacao")), oms_txt))
        _btn(self, "Abrir registro", self._abrir, 140).pack(pady=(0, 14))

    def _abrir(self):
        sel = self.tree.selection()
        if not sel:
            return
        r = next(x for x in self.itens if str(x["id_registro"]) == sel[0])
        leito = {"id_leito": r["id_leito"], "codigo": r["leito_codigo"], "setor": r["setor"]}
        FormRegistro(self.ui, {"leito": leito, "registro": r}, somente_leitura=True, data_iso=r["data"])


# ================================================================== FORMULÁRIO DO REGISTRO
class FormRegistro(_Janela):
    """Registro de um leito num dia (a anamnese do mapa num só lugar)."""

    def __init__(self, ui, item, somente_leitura=False, data_iso=None):
        titulo = f"Leito {item['leito']['codigo']} — {mdb.iso_para_br(data_iso or ui.data.isoformat())}"
        super().__init__(ui, titulo, "860x780")
        self.ui = ui
        self.leito = item["leito"]
        self.reg = item["registro"] or {}
        self.somente_leitura = somente_leitura
        self.data_iso = data_iso or ui.data.isoformat()
        self.title(f"Leito {self.leito['codigo']}  -  {mdb.iso_para_br(self.data_iso)}"
                   + ("  (somente consulta)" if somente_leitura else ""))
        self.geometry("860x780")
        self.attributes("-topmost", True)
        self._widgets = []
        self._id_paciente = self.reg.get("id_paciente")
        self._data_nascimento = None
        paciente_vinculado = mdb.obter_paciente(ui.db, self._id_paciente)
        if paciente_vinculado:
            self._data_nascimento = paciente_vinculado.get("data_nascimento")
        self._nome_original = self.reg.get("nome_paciente") or ""
        self._vinculo_manual = False
        self._altura_metodo = self.reg.get("altura_metodo")
        self._peso_metodo = self.reg.get("peso_metodo")
        self._suplementos = [dict(s) for s in self.reg.get("suplementos", [])]
        self._catalogo = mdb.listar_suplementos(ui.db)
        self._catalogo_visivel = list(self._catalogo)
        self._via_anterior = None
        self._resultado_nrs = {}
        self._resultado_avaliacao = {}
        self._resultado_pediatria = {}
        self._montar()
        self.bind("<Control-s>", self._atalho_salvar)
        self.bind("<Control-S>", self._atalho_salvar)
        self.bind("<Escape>", self._atalho_fechar)
        self._preencher()
        self._recalcular()
        if somente_leitura:
            self._travar()
        # A guia lateral não usa janela modal nem captura o foco.

    # ----------------------------------------------------------------- construção
    def _reg(self, w):
        self._widgets.append(w)
        return w

    def _secao(self, titulo):
        ctk.CTkLabel(self.corpo, text=titulo, font=ctk.CTkFont(size=14, weight="bold"), text_color=VERDE_ESC
                     ).pack(anchor="w", padx=14, pady=(12, 2))
        quadro = ctk.CTkFrame(self.corpo, fg_color=tema.BRANCO, corner_radius=8)
        quadro.pack(fill="x", padx=10, pady=2)
        return quadro

    def _linha(self, quadro):
        f = ctk.CTkFrame(quadro, fg_color="transparent")
        f.pack(fill="x", padx=10, pady=4)
        return f

    def _entrada(self, pai, rotulo, largura=80, **kw):
        ctk.CTkLabel(pai, text=rotulo).pack(side="left", padx=(0, 4))
        e = self._reg(ctk.CTkEntry(pai, width=largura, **kw))
        e.pack(side="left", padx=(0, 12))
        e.bind("<KeyRelease>", lambda ev: self._recalcular())
        return e

    def _seg(self, pai, rotulo, valores, cmd=None):
        if rotulo:
            ctk.CTkLabel(pai, text=rotulo).pack(side="left", padx=(0, 4))
        s = self._reg(ctk.CTkSegmentedButton(pai, values=valores, command=lambda v: (cmd(v) if cmd else None, self._recalcular())))
        s.pack(side="left", padx=(0, 12))
        return s

    def _montar(self):
        self.corpo = ctk.CTkScrollableFrame(self, fg_color=FUNDO)
        self.corpo.pack(fill="both", expand=True, padx=6, pady=(6, 0))

        q = self._secao(f"Identificação  -  Leito {self.leito['codigo']}")
        l = self._linha(q)
        ctk.CTkLabel(l, text="Paciente").pack(side="left", padx=(0, 4))
        self.e_nome = self._reg(ctk.CTkEntry(l, width=360, font=ctk.CTkFont(size=13, weight="bold")))
        self.e_nome.pack(side="left", padx=(0, 8))
        self.b_buscar = self._reg(_btn(l, "Buscar cadastrado", self._buscar_paciente, 140, CINZA_BTN, CINZA_HOVER, 28))
        self.b_buscar.pack(side="left")
        l = self._linha(q)
        self.seg_acomp = self._seg(l, "Acompanhante?", ["Sim", "Não"])
        self.e_idade = self._entrada(l, "Idade (anos)", 60)
        self.e_meses = self._entrada(l, "+ meses", 45)
        self.seg_sexo = self._seg(l, "Sexo", ["Homem", "Mulher"])
        self.seg_cor = self._seg(l, "Cor", ["Branco", "Negro"])

        q = self._secao("Antropometria")
        l = self._linha(q)
        self.e_aj = self._entrada(l, "AJ - altura do joelho (cm)", 70)
        self.e_pp = self._entrada(l, "PP - panturrilha (cm)", 70)
        self.e_pb = self._entrada(l, "PB - braço (cm)", 70)
        l = self._linha(q)
        self.e_altura = self._entrada(l, "Altura (cm)", 80)
        self.seg_alt = self._seg(l, "", ["Estimada", "Real"])
        self.b_alt = self._reg(_btn(l, "Estimar pela AJ", self._estimar_altura, 130, CINZA_BTN, CINZA_HOVER, 28))
        self.b_alt.pack(side="left")
        l = self._linha(q)
        self.e_peso = self._entrada(l, "Peso (kg)", 80)
        self.seg_peso = self._seg(l, "", ["Estimado", "Real"])
        self.b_peso = self._reg(_btn(l, "Estimar por AJ + PB", self._estimar_peso, 150, CINZA_BTN, CINZA_HOVER, 28))
        self.b_peso.pack(side="left")
        l = self._linha(q)
        ctk.CTkLabel(l, text="IMC (kg/m²):").pack(side="left")
        self.lbl_imc = ctk.CTkLabel(l, text="-", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_imc.pack(side="left", padx=6)
        self.lbl_class = ctk.CTkLabel(l, text="", text_color=tema.ERRO, font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_class.pack(side="left")
        self.lbl_info = ctk.CTkLabel(q, text="", text_color=tema.SUAVE, wraplength=760, justify="left",
                                     font=ctk.CTkFont(size=11))
        self.lbl_info.pack(anchor="w", padx=12, pady=(0, 6))
        self.lbl_oms_pediatria = ctk.CTkLabel(
            q, text="OMS pediatria: informe idade, sexo, peso e altura; o resultado exige tabela oficial.",
            text_color=tema.SUAVE, wraplength=760, justify="left", font=ctk.CTkFont(size=11))
        self.lbl_oms_pediatria.pack(anchor="w", padx=12, pady=(0, 2))
        ctk.CTkLabel(
            q, text="Medida OMS: comprimento deitado antes de 24 meses; estatura em pé a partir de 24 meses.",
            text_color=tema.SUAVE, wraplength=760, justify="left", font=ctk.CTkFont(size=10)
        ).pack(anchor="w", padx=12, pady=(0, 4))
        linha_curvas = self._linha(q)
        self.b_curvas_oms = self._reg(_btn(linha_curvas, "Ver curvas OMS", self._abrir_curvas_oms,
                                            130, CINZA_BTN, CINZA_HOVER, 28))
        self.b_curvas_oms.pack(side="left")

        q = self._secao("Dieta")
        l = self._linha(q)
        self.e_reav = self._entrada(l, "Reavaliação prevista (DD/MM/AAAA)", 100)
        self.seg_via = self._seg(l, "Via", mdb.VIAS, cmd=self._via_mudou)
        l = self._linha(q)
        ctk.CTkLabel(l, text="Características:").pack(side="left", padx=(0, 6))
        self.var_carac = {}
        for campo, sigla, nome in mdb.CARACTERISTICAS:
            self.var_carac[campo] = tk.IntVar(value=0)
            self._reg(ctk.CTkCheckBox(l, text=nome, variable=self.var_carac[campo], width=20)).pack(side="left", padx=6)
        l = self._linha(q)
        ctk.CTkLabel(l, text="Outras doenças relatadas:").pack(side="left", padx=(0, 6))
        self.var_cond = {}
        for codigo, nome in mdb.CONDICOES:
            self.var_cond[codigo] = tk.IntVar(value=0)
            self._reg(ctk.CTkCheckBox(l, text=nome, variable=self.var_cond[codigo], width=20)).pack(side="left", padx=6)
        ctk.CTkLabel(l, text="(com as marcações acima, escolhem as condutas de alta)", text_color=tema.SUAVE,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=8)
        l = self._linha(q)
        self.seg_cons = self._seg(l, "Consistência", mdb.CONSISTENCIAS)
        l = self._linha(q)
        self.e_meta_kcal = self._entrada(l, "Meta energética (kcal/dia)", 85)
        self.e_meta_ptn = self._entrada(l, "Meta proteica (g/dia)", 85)

        q = self._secao("Suplementação oral / dieta enteral")
        self.lbl_sup_tipo = ctk.CTkLabel(q, text="Suplementação oral: complemento da alimentação por via oral",
                                         text_color=tema.SUAVE, wraplength=760, justify="left")
        self.lbl_sup_tipo.pack(anchor="w", padx=12, pady=(0, 4))
        l = self._linha(q)
        self.cb_mod = self._reg(ctk.CTkComboBox(l, values=["Todos os módulos"] + mdb.listar_modulos(self.ui.db), width=210,
                                                state="readonly", command=lambda v: self._filtrar_sup()))
        self.cb_mod.pack(side="left", padx=(0, 6))
        self.cb_mod.set("Todos os módulos")
        self.cb_sup = self._reg(ctk.CTkComboBox(l, values=[s["nome"] for s in self._catalogo], width=230, state="readonly"))
        self.cb_sup.pack(side="left", padx=(0, 6))
        self.cb_sup.set("")
        self.e_qtd = self._reg(ctk.CTkEntry(l, width=70, placeholder_text="qtd/dia"))
        self.e_qtd.pack(side="left", padx=(0, 6))
        self._reg(_btn(l, "Adicionar", self._add_sup, 90, VERDE, VERDE_HOVER, 28)).pack(side="left")
        self.tree_sup = ttk.Treeview(q, columns=("mod", "nome", "qtd"), show="headings", style=ESTILO_TREE, height=3,
                                     selectmode="browse")
        for c, t, w in (("mod", "Módulo", 230), ("nome", "Suplemento", 280), ("qtd", "Qtd/dia", 90)):
            self.tree_sup.heading(c, text=t)
            self.tree_sup.column(c, width=w, anchor="w")
        self.tree_sup.pack(fill="x", padx=10, pady=(2, 2))
        self._reg(_btn(q, "Remover selecionado", self._rem_sup, 160, VERMELHO, VERMELHO_HOVER, 26)).pack(
            anchor="w", padx=10, pady=(0, 4))
        self.lbl_oferta = ctk.CTkLabel(q, text="Aporte calculado: informe dose e metas.",
                                       text_color=tema.TEXTO, wraplength=760, justify="left")
        self.lbl_oferta.pack(anchor="w", padx=12, pady=(0, 8))

        q = self._secao("Observações")
        for attr, rot in (("t_sim", "Sim: (alimentos que consome)"), ("t_nao", "Não: (alimentos que não consome)")):
            l = self._linha(q)
            ctk.CTkLabel(l, text=rot, width=190, anchor="w").pack(side="left")
            t = self._reg(ctk.CTkTextbox(l, width=540, height=44))
            t.pack(side="left")
            setattr(self, attr, t)

        q = self._secao("Função intestinal")
        l = self._linha(q)
        self.seg_fi = self._seg(l, "", ["Presente", "Ausente"], cmd=self._fi_mudou)
        self.e_fi_freq = self._reg(ctk.CTkEntry(l, width=60))
        self.e_fi_freq.pack(side="left", padx=(0, 4))
        ctk.CTkLabel(l, text="x por dia (se presente)").pack(side="left", padx=(0, 14))
        self.e_fi_dias = self._reg(ctk.CTkEntry(l, width=60))
        self.e_fi_dias.pack(side="left", padx=(0, 4))
        ctk.CTkLabel(l, text="dias sem evacuar (se ausente)").pack(side="left")

        # Triagem NRS-2002 integrada ao mapa; o algoritmo oficial permanece em nrs2002.py.
        q = self._secao("Triagem nutricional — NRS-2002")
        self.nrs_respostas = {}
        for codigo, pergunta in nrs.PERGUNTAS:
            l = self._linha(q)
            ctk.CTkLabel(l, text=pergunta, width=340, anchor="w").pack(side="left")
            cb = self._reg(ctk.CTkComboBox(l, values=["—", "Não", "Sim"], width=150, state="readonly",
                                           command=lambda _v: self._recalcular_nrs()))
            cb.set("—")
            cb.pack(side="left")
            self.nrs_respostas[codigo] = cb
        l = self._linha(q)
        ctk.CTkLabel(l, text="Estado nutricional").pack(side="left", padx=(0, 6))
        self.cb_nrs_estado = self._reg(ctk.CTkComboBox(
            l, values=["—"] + [nrs.ESTADO[i] for i in range(4)], width=180, state="readonly",
            command=lambda _v: self._recalcular_nrs()))
        self.cb_nrs_estado.set("—")
        self.cb_nrs_estado.pack(side="left", padx=(0, 14))
        ctk.CTkLabel(l, text="Gravidade da doença").pack(side="left", padx=(0, 6))
        self.cb_nrs_gravidade = self._reg(ctk.CTkComboBox(
            l, values=["—"] + [nrs.GRAVIDADE[i] for i in range(4)], width=180, state="readonly",
            command=lambda _v: self._recalcular_nrs()))
        self.cb_nrs_gravidade.set("—")
        self.cb_nrs_gravidade.pack(side="left")
        self.lbl_nrs_classificacao = ctk.CTkLabel(
            q, text="Classificação NRS-2002: não preenchida", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=VERDE_ESC, anchor="w")
        self.lbl_nrs_classificacao.pack(anchor="w", padx=12, pady=(2, 10))

        # Avaliação nutricional: reaproveita o núcleo validado e exibe apenas a classificação final.
        q = self._secao("Avaliação nutricional")
        l = self._linha(q)
        ctk.CTkLabel(l, text="Edema").pack(side="left", padx=(0, 4))
        self.cb_av_edema = self._reg(ctk.CTkComboBox(
            l, values=list(avaliacao.EDEMA), width=190, state="readonly",
            command=lambda _v: self._recalcular_avaliacao()))
        self.cb_av_edema.set("Ausente")
        self.cb_av_edema.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(l, text="Ascite").pack(side="left", padx=(0, 4))
        self.cb_av_ascite = self._reg(ctk.CTkComboBox(
            l, values=list(avaliacao.ASCITE), width=180, state="readonly",
            command=lambda _v: self._recalcular_avaliacao()))
        self.cb_av_ascite.set("Ausente")
        self.cb_av_ascite.pack(side="left")
        l = self._linha(q)
        self.av_amputacoes = {}
        for nivel in avaliacao.AMPUTACOES:
            ctk.CTkLabel(l, text=nivel, width=145, anchor="w").pack(side="left", padx=(0, 3))
            cb = self._reg(ctk.CTkComboBox(
                l, values=["0", "1", "2"], width=55, state="readonly",
                command=lambda _v: self._recalcular_avaliacao()))
            cb.set("0")
            cb.pack(side="left", padx=(0, 8))
            self.av_amputacoes[nivel] = cb
        self.lbl_avaliacao_classificacao = ctk.CTkLabel(
            q, text="Classificação da avaliação: informe os dados antropométricos.",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=VERDE_ESC, anchor="w")
        self.lbl_avaliacao_classificacao.pack(anchor="w", padx=12, pady=(2, 10))

        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.pack(fill="x", padx=10, pady=8)
        self.b_salvar = _btn(rodape, "Salvar", self._salvar, 130)
        self.b_salvar.pack(side="right")
        _btn(rodape, "Fechar" if self.somente_leitura else "Cancelar", self.destroy, 110, CINZA_BTN, CINZA_HOVER
             ).pack(side="right", padx=8)
        if self.somente_leitura:
            self.b_salvar.pack_forget()

    # ------------------------------------------------------------- preencher/coletar
    def _preencher(self):
        r = self.reg
        _set_entry(self.e_nome, r.get("nome_paciente"))
        if r.get("acompanhante") is not None and r:
            self.seg_acomp.set("Sim" if r["acompanhante"] else "Não")
        _set_entry(self.e_idade, r.get("idade_anos"))
        _set_entry(self.e_meses, r.get("idade_meses"))
        if r.get("sexo"):
            self.seg_sexo.set({"H": "Homem", "M": "Mulher"}[r["sexo"]])
        if r.get("cor"):
            self.seg_cor.set({"B": "Branco", "N": "Negro"}[r["cor"]])
        for chave, campo in (("aj_cm", self.e_aj), ("pp_cm", self.e_pp), ("pb_cm", self.e_pb),
                             ("altura_cm", self.e_altura), ("peso_kg", self.e_peso)):
            _set_entry(campo, _fmt(r.get(chave)).replace(",0", "") if r.get(chave) is not None else "")
        if r.get("altura_origem"):
            self.seg_alt.set({"E": "Estimada", "R": "Real"}[r["altura_origem"]])
        if r.get("peso_origem"):
            self.seg_peso.set({"E": "Estimado", "R": "Real"}[r["peso_origem"]])
        _set_entry(self.e_reav, mdb.iso_para_br(r.get("data_reavaliacao")))
        if r.get("via"):
            self.seg_via.set(r["via"])
        _set_entry(self.e_meta_kcal, _fmt(r.get("meta_kcal")).replace(",0", "") if r.get("meta_kcal") is not None else "")
        _set_entry(self.e_meta_ptn, _fmt(r.get("meta_proteina_g")).replace(",0", "") if r.get("meta_proteina_g") is not None else "")
        self._via_mudou(r.get("via") or "Oral", preservar=True)
        for campo, var in self.var_carac.items():
            var.set(1 if r.get(campo) else 0)
        ativas = mdb.codigos_condicoes(r.get("condicoes"))
        for codigo, var in self.var_cond.items():
            var.set(1 if codigo in ativas else 0)
        if r.get("consistencia"):
            self.seg_cons.set(r["consistencia"])
        self.t_sim.insert("1.0", r.get("obs_sim") or "")
        self.t_nao.insert("1.0", r.get("obs_nao") or "")
        if r.get("fi_estado"):
            self.seg_fi.set({"P": "Presente", "A": "Ausente"}[r["fi_estado"]])
        _set_entry(self.e_fi_freq, _fmt(r.get("fi_freq")).replace(",0", "") if r.get("fi_freq") else "")
        _set_entry(self.e_fi_dias, r.get("fi_dias_ausente"))
        self._atualizar_sup()
        try:
            salvo_nrs = json.loads(r.get("nrs2002_json") or "{}")
            for codigo, valor in (salvo_nrs.get("respostas") or {}).items():
                if codigo in self.nrs_respostas:
                    self.nrs_respostas[codigo].set("—" if valor is None else "Sim" if valor else "Não")
            if salvo_nrs.get("estado") is not None:
                self.cb_nrs_estado.set(nrs.ESTADO[int(salvo_nrs["estado"])])
            if salvo_nrs.get("gravidade") is not None:
                self.cb_nrs_gravidade.set(nrs.GRAVIDADE[int(salvo_nrs["gravidade"])])
            salvo_av = json.loads(r.get("avaliacao_json") or "{}")
            dados_av = salvo_av.get("dados") or {}
            if dados_av.get("edema") in avaliacao.EDEMA:
                self.cb_av_edema.set(dados_av["edema"])
            if dados_av.get("ascite") in avaliacao.ASCITE:
                self.cb_av_ascite.set(dados_av["ascite"])
            for nivel, cb in self.av_amputacoes.items():
                cb.set(str((dados_av.get("amputacoes") or {}).get(nivel, 0)))
        except (TypeError, ValueError, KeyError):
            pass

    def _fi_mudou(self, valor):
        if valor == "Presente" and not self.e_fi_freq.get().strip():
            _set_entry(self.e_fi_freq, "1")

    def _coletar(self):
        g = lambda e: e.get().strip()
        n = lambda e: nc.parse_num(g(e))
        idade, meses = n(self.e_idade), n(self.e_meses)
        if self._data_nascimento:
            idade_meses_oms, _, _, erro_idade = self._idade_para_oms()
            if idade_meses_oms is None:
                raise ValueError(erro_idade or "Não foi possível calcular a idade pela data de nascimento.")
            idade, meses = divmod(idade_meses_oms, 12)
        elif idade is None and meses is not None and meses > 0:
            idade, meses = divmod(int(meses), 12)
        reav = None
        if g(self.e_reav):
            try:
                reav = mdb.data_br_para_iso(g(self.e_reav))
            except ValueError:
                raise ValueError("Data de reavaliação inválida. Use DD/MM/AAAA.")
        for campo, rot in ((self.e_aj, "AJ"), (self.e_pp, "PP"), (self.e_pb, "PB"), (self.e_altura, "Altura"),
                           (self.e_peso, "Peso"), (self.e_idade, "Idade"), (self.e_fi_freq, "Frequência"),
                           (self.e_fi_dias, "Dias"), (self.e_meta_kcal, "Meta energética"),
                           (self.e_meta_ptn, "Meta proteica")):
            if g(campo) and nc.parse_num(g(campo)) is None:
                raise ValueError(f"Valor inválido em {rot}.")
        origem_a = {"Estimada": "E", "Real": "R"}.get(self.seg_alt.get())
        origem_p = {"Estimado": "E", "Real": "R"}.get(self.seg_peso.get())
        fi = {"Presente": "P", "Ausente": "A"}.get(self.seg_fi.get())
        dias = n(self.e_fi_dias)
        return {
            "data": self.data_iso, "id_leito": self.leito["id_leito"], "id_paciente": self._id_paciente,
            "nome_paciente": g(self.e_nome), "acompanhante": 1 if self.seg_acomp.get() == "Sim" else 0,
            "sexo": {"Homem": "H", "Mulher": "M"}.get(self.seg_sexo.get()),
            "cor": {"Branco": "B", "Negro": "N"}.get(self.seg_cor.get()),
            "idade_anos": int(idade) if idade is not None else None, "idade_meses": int(meses) if meses else None,
            "aj_cm": n(self.e_aj), "pp_cm": n(self.e_pp), "pb_cm": n(self.e_pb),
            "altura_cm": n(self.e_altura), "altura_origem": origem_a,
            "altura_metodo": self._altura_metodo if origem_a == "E" else None,
            "peso_kg": n(self.e_peso), "peso_origem": origem_p,
            "peso_metodo": self._peso_metodo if origem_p == "E" else None,
            "data_reavaliacao": reav, "via": self.seg_via.get() or None,
            "meta_kcal": n(self.e_meta_kcal), "meta_proteina_g": n(self.e_meta_ptn),
            **{campo: var.get() for campo, var in self.var_carac.items()},
            "condicoes": ",".join(c for c, var in self.var_cond.items() if var.get()) or None,
            "consistencia": self.seg_cons.get() or None,
            "obs_sim": self.t_sim.get("1.0", "end-1c").strip(), "obs_nao": self.t_nao.get("1.0", "end-1c").strip(),
            "fi_estado": fi, "fi_freq": n(self.e_fi_freq) if fi == "P" else None,
            "fi_dias_ausente": int(dias) if (fi == "A" and dias is not None) else None,
            "suplementos": list(self._suplementos),
            "nrs2002_json": json.dumps(self._resultado_nrs, ensure_ascii=False),
            "nrs2002_classificacao": self._resultado_nrs.get("rotulo", ""),
            "avaliacao_json": json.dumps(self._resultado_avaliacao, ensure_ascii=False),
            "avaliacao_classificacao": self._resultado_avaliacao.get("classe", ""),
            "pediatria_oms_json": json.dumps(self._resultado_pediatria, ensure_ascii=False),
        }

    # ---------------------------------------------------------------- cálculos
    def _idade_para_oms(self):
        # Quando o paciente está vinculado, a data de nascimento é a fonte principal.
        # Isso evita divergência entre a idade digitada e a idade cronológica real.
        if self._data_nascimento:
            bruto = str(self._data_nascimento).strip()
            try:
                nascimento = date.fromisoformat(bruto)
            except ValueError:
                try:
                    nascimento = datetime.strptime(bruto, "%d/%m/%Y").date()
                except ValueError:
                    return None, None, None, "Data de nascimento inválida."
            try:
                idade_dias = oms.calcular_idade_dias(nascimento.isoformat(), self.data_iso)
                idade_meses = oms.calcular_idade_meses(nascimento.isoformat(), self.data_iso)
            except ValueError as exc:
                return None, None, None, str(exc)
            return idade_meses, idade_dias, idade_dias / 30.4375, nascimento.isoformat()

        anos = nc.parse_num(self.e_idade.get())
        meses_extra = nc.parse_num(self.e_meses.get()) or 0
        if anos is None and meses_extra <= 0:
            return None, None, None, "Informe a idade ou vincule um paciente com data de nascimento."
        idade_meses = int((anos or 0) * 12 + meses_extra)
        if idade_meses < 0:
            return None, None, None, "Idade não pode ser negativa."
        return idade_meses, None, float(idade_meses), None

    def _recalcular_pediatria(self, imc):
        idade_meses, idade_dias, meses_decimais, nascimento = self._idade_para_oms()
        if idade_meses is None:
            self._resultado_pediatria = {"status": "pendente", "aviso": nascimento, "resultados": {}}
            self.lbl_oms_pediatria.configure(text="OMS pediatria: " + (nascimento or "informe a idade ou vincule um paciente com data de nascimento."))
            self.lbl_class.configure(text="(classificação pediátrica pendente)")
            return
        sexo = {"Homem": "H", "Mulher": "M"}.get(self.seg_sexo.get())
        tabela = self.ui.tabela_oms
        medidas = {
            "imc_idade": imc,
            "peso_idade": nc.parse_num(self.e_peso.get()),
            "estatura_idade": nc.parse_num(self.e_altura.get()),
        }
        resultados = {
            indicador: oms.avaliar_indicador(indicador, valor, sexo, meses_decimais, tabela,
                                             idade_dias=idade_dias,
                                             idade_meses_completos=idade_meses)
            for indicador, valor in medidas.items()
        }
        self._resultado_pediatria = {
            "status": "calculado" if any(x.get("status") == "calculado" for x in resultados.values()) else "pendente",
            "data_avaliacao": self.data_iso, "data_nascimento": nascimento,
            "idade_dias": idade_dias, "idade_meses_completos": idade_meses,
            "idade_meses_decimais": round(meses_decimais, 4), "sexo": sexo,
            "peso_kg": medidas["peso_idade"], "altura_cm": medidas["estatura_idade"],
            "imc": imc, "resultados": resultados,
            "fonte": "OMS 2006 / OMS 2007 — pacotes WHO anthro 1.1.0 e anthroplus 1.1.0",
        }
        nomes = {"imc_idade": "IMC/idade", "peso_idade": "Peso/idade", "estatura_idade": "Estatura/idade"}
        linhas = []
        for indicador, resultado in resultados.items():
            if resultado["status"] == "calculado":
                linhas.append(f"{nomes[indicador]}: z={resultado['escore_z']:+.2f} — {resultado['classificacao']}")
            elif resultado["status"] == "fora_faixa":
                linhas.append(f"{nomes[indicador]}: não aplicável nesta idade")
            else:
                linhas.append(f"{nomes[indicador]}: pendente ({resultado.get('aviso') or 'dados insuficientes'})")
        if tabela is None:
            aviso = self.ui.erro_tabela_oms or "arquivo oficial dados/oms_lms_pediatricos.csv não encontrado"
            linhas = ["Tabelas LMS oficiais OMS não carregadas: " + aviso]
        if idade_meses > 228:
            linhas.insert(0, "Faixa OMS pediátrica encerrada aos 228 meses (19 anos completos).")
        elif idade_meses <= 60 and idade_dias is None:
            linhas.insert(0, "Para OMS 2006, informe/vincule a data de nascimento para calcular a idade exata em dias.")
        self.lbl_oms_pediatria.configure(text="OMS pediatria — " + " | ".join(linhas))
        imc_oms = resultados["imc_idade"]
        if imc_oms["status"] == "calculado":
            self.lbl_class.configure(text=f"(OMS: {imc_oms['classificacao']} · z={imc_oms['escore_z']:+.2f})")
        elif imc_oms["status"] == "fora_faixa":
            self.lbl_class.configure(text="(fora da faixa de referência OMS)")
        else:
            self.lbl_class.configure(text="(classificação OMS pendente)")

    def _abrir_curvas_oms(self):
        if self.ui.tabela_oms is None:
            messagebox.showwarning(
                "Curvas OMS", "As tabelas LMS oficiais não foram carregadas. Confira dados/oms_lms_pediatricos.csv.",
                parent=self)
            return
        idade_meses, idade_dias, meses_decimais, _ = self._idade_para_oms()
        if idade_meses is None:
            messagebox.showinfo("Curvas OMS", "Informe a idade do paciente.", parent=self)
            return
        sexo = {"Homem": "H", "Mulher": "M"}.get(self.seg_sexo.get())
        if sexo is None:
            messagebox.showinfo("Curvas OMS", "Informe o sexo para selecionar a referência correta.", parent=self)
            return
        imc = nc.calcular_imc(nc.parse_num(self.e_peso.get()), nc.parse_num(self.e_altura.get()))
        DialogCurvasOMS(
            self.ui, self.ui.tabela_oms, sexo, meses_decimais,
            nc.parse_num(self.e_peso.get()), nc.parse_num(self.e_altura.get()), imc)

    def _recalcular(self):
        self._recalcular_oferta()
        peso, alt = nc.parse_num(self.e_peso.get()), nc.parse_num(self.e_altura.get())
        idade = nc.parse_num(self.e_idade.get())
        imc = nc.calcular_imc(peso, alt)
        self.lbl_imc.configure(text=nc.fmt_num(imc, 1) if imc is not None else "-")
        idade_meses, _, _, _ = self._idade_para_oms()
        if idade_meses is not None and idade_meses < 240:
            self._recalcular_pediatria(imc)
        elif idade_meses is None:
            self.lbl_class.configure(text="(informe a idade para classificar)")
            self.lbl_oms_pediatria.configure(text="OMS pediatria: informe a idade.")
            self._resultado_pediatria = {"status": "pendente", "resultados": {}}
        else:
            self.lbl_oms_pediatria.configure(text="Indicadores OMS pediátricos não se aplicam a partir de 20 anos.")
            self._resultado_pediatria = {}
            if imc is None:
                self.lbl_class.configure(text="")
            else:
                idade_adulta = int(idade_meses // 12)
                cl = nc.classificar_imc(imc, idade_adulta, {"Homem": "H", "Mulher": "M"}.get(self.seg_sexo.get()),
                                        int(idade_meses % 12), self.ui.criterio_idoso, self.ui.lms)
                txt = nc.texto_classificacao(cl)
                self.lbl_class.configure(text=f"({txt})" if txt else "")
        self._recalcular_nrs()
        self._recalcular_avaliacao()

    def _recalcular_nrs(self):
        respostas = {codigo: (None if cb.get() == "—" else cb.get() == "Sim")
                     for codigo, cb in self.nrs_respostas.items()}
        estado_txt, gravidade_txt = self.cb_nrs_estado.get(), self.cb_nrs_gravidade.get()
        estado = int(estado_txt[0]) if estado_txt != "—" else None
        gravidade = int(gravidade_txt[0]) if gravidade_txt != "—" else None
        idade = nc.parse_num(self.e_idade.get())
        try:
            resultado = nrs.classificar(respostas, estado, gravidade, idade)
        except ValueError as exc:
            resultado = {"completo": False, "rotulo": str(exc), "grau": None, "escore": None}
        self._resultado_nrs = {
            "respostas": respostas, "estado": estado, "gravidade": gravidade,
            "idade": idade, **resultado,
        }
        self.lbl_nrs_classificacao.configure(
            text=f"Classificação NRS-2002: {resultado.get('rotulo') or 'Não preenchida'}")

    def _recalcular_avaliacao(self):
        dados = {
            "sexo": self.seg_sexo.get(), "cor": self.seg_cor.get(),
            "idade": self.e_idade.get(), "peso": self.e_peso.get(),
            "altura": self.e_altura.get(), "aj": self.e_aj.get(), "pb": self.e_pb.get(),
            "edema": self.cb_av_edema.get(), "ascite": self.cb_av_ascite.get(),
            "amputacoes": {nivel: int(cb.get() or 0) for nivel, cb in self.av_amputacoes.items()},
        }
        try:
            resultado = avaliacao.calcular(dados, self.ui.lms, self.ui.criterio_idoso)
            classe = resultado.get("classe") or ""
            rotulo = classe if classe else "Dados insuficientes para classificar"
            self._resultado_avaliacao = {
                "dados": dados, "classe": classe, "imc": resultado.get("imc"),
                "peso_ajustado": resultado.get("ajustado"), "avisos": resultado.get("avisos", []),
            }
        except (ValueError, TypeError) as exc:
            rotulo = f"Não foi possível classificar: {exc}"
            self._resultado_avaliacao = {"dados": dados, "classe": "", "erro": str(exc)}
        self.lbl_avaliacao_classificacao.configure(text=f"Classificação da avaliação: {rotulo}")

    def _estimar_altura(self):
        try:
            est = nc.estimar_altura(self.e_aj.get(), self.seg_sexo.get(), self.seg_cor.get(), self.e_idade.get(),
                                    self.ui.metodo_altura_idoso)
        except nc.EstimativaIndisponivel as e:
            messagebox.showwarning("Estimar altura", str(e), parent=self)
            return
        _set_entry(self.e_altura, nc.fmt_num(est.valor, 1))
        self.seg_alt.set("Estimada")
        self._altura_metodo = est.equacao
        self.lbl_info.configure(text="Altura: " + est.equacao + (". " + " ".join(est.avisos) if est.avisos else ""))
        self._recalcular()

    def _estimar_peso(self):
        try:
            est = nc.estimar_peso(self.e_aj.get(), self.e_pb.get(), self.seg_sexo.get(), self.seg_cor.get(),
                                  self.e_idade.get())
        except nc.EstimativaIndisponivel as e:
            messagebox.showwarning("Estimar peso", str(e), parent=self)
            return
        _set_entry(self.e_peso, nc.fmt_num(est.valor, 1))
        self.seg_peso.set("Estimado")
        self._peso_metodo = est.equacao
        self.lbl_info.configure(text="Peso: " + est.equacao + ". " + " ".join(est.avisos))
        self._recalcular()

    # --------------------------------------------------------------- suplementos
    def _via_mudou(self, via, preservar=False):
        """Separa suplemento oral de fórmula enteral; não mantém os dois tratamentos misturados."""
        if not hasattr(self, "cb_sup"):
            return
        enteral = via == "Enteral"
        zero = via == "Zero"
        nova_via = "Enteral" if enteral else "Zero" if zero else "Oral"
        if self._via_anterior != nova_via and not preservar:
            self._suplementos = []
        self._via_anterior = nova_via
        # A via classifica o paciente e o tipo de terapia no mapa; não deve esconder produtos
        # do catálogo. A indicação de uso de cada produto continua registrada no seu módulo/ficha.
        self._catalogo_visivel = list(self._catalogo)
        modulos = ["Todos os módulos"] + mdb.listar_modulos(self.ui.db)
        self.cb_mod.configure(values=modulos)
        self.cb_mod.set("Todos os módulos")
        if enteral:
            self.lbl_sup_tipo.configure(
                text="DIETA ENTERAL: paciente classificado separadamente como enteral. "
                     "A seleção de via substitui a suplementação anterior; todos os produtos permanecem "
                     "visíveis no catálogo. Confira a indicação e a via de administração na ficha técnica.")
        elif zero:
            self.lbl_sup_tipo.configure(text="VIA ZERO: paciente classificado em via zero. "
                                             "Não registre oferta enquanto essa via estiver selecionada.")
        else:
            self.lbl_sup_tipo.configure(
                text="SUPLEMENTAÇÃO ORAL: complemento da alimentação pela boca. "
                     "O paciente permanece classificado como via oral com suplementação, separado dos pacientes enterais.")
        self._filtrar_sup()
        self._atualizar_sup()
        self._recalcular_oferta()

    def _filtrar_sup(self):
        modulo = self.cb_mod.get()
        catalogo = self._catalogo_visivel
        nomes = [s["nome"] for s in catalogo
                 if self.seg_via.get() == "Enteral" or modulo == "Todos os módulos" or s["modulo"] == modulo]
        self.cb_sup.configure(values=nomes)
        self.cb_sup.set(nomes[0] if len(nomes) == 1 else "")

    def _add_sup(self):
        nome = self.cb_sup.get()
        s = next((x for x in self._catalogo_visivel if x["nome"] == nome), None)
        if not s:
            messagebox.showinfo("Suplementos", "Escolha o suplemento na lista.", parent=self)
            return
        if any(x.get("id_suplemento") == s["id_suplemento"] for x in self._suplementos):
            messagebox.showinfo("Suplementos", "Este suplemento já foi adicionado.", parent=self)
            return
        txt = self.e_qtd.get().strip()
        qtd = nc.parse_num(txt)
        if txt and qtd is None:
            messagebox.showwarning("Suplementos", "Quantidade inválida.", parent=self)
            return
        self._suplementos.append({
            "id_suplemento": s["id_suplemento"], "nome": s["nome"], "modulo": s["modulo"],
            "qtd_dia": qtd, "unidade": s["emb_un"],
            **{campo: s.get(campo) for campo in ("kcal_100", "ptn_100", "lip_100", "carb_100", "sod_100")},
            "ficha_observacao": s.get("observacao"),
        })
        _set_entry(self.e_qtd, "")
        self._atualizar_sup()
        self._recalcular_oferta()

    def _rem_sup(self):
        sel = self.tree_sup.selection()
        if sel:
            del self._suplementos[int(sel[0])]
            self._atualizar_sup()
            self._recalcular_oferta()

    def _atualizar_sup(self):
        self.tree_sup.delete(*self.tree_sup.get_children())
        for i, s in enumerate(self._suplementos):
            qtd = f"{_fmt(s.get('qtd_dia')).replace(',0', '')} {s.get('unidade') or ''}".strip() if s.get("qtd_dia") else ""
            self.tree_sup.insert("", "end", iid=str(i), values=(s.get("modulo") or "", s["nome"], qtd))

    def _recalcular_oferta(self):
        if not hasattr(self, "lbl_oferta"):
            return
        por_id = {s["id_suplemento"]: s for s in self._catalogo}
        itens = [{**por_id.get(item.get("id_suplemento"), {}), **item} for item in self._suplementos]
        resultado = sc.calcular_oferta(
            itens, peso_kg=nc.parse_num(self.e_peso.get()),
            meta_kcal=nc.parse_num(self.e_meta_kcal.get()),
            meta_proteina_g=nc.parse_num(self.e_meta_ptn.get()))
        t = resultado["totais"]
        partes = []
        if t["kcal_100"] is not None:
            partes.append(f"{t['kcal_100']:.1f} kcal/dia")
            if resultado["percentual_meta_kcal"] is not None:
                partes.append(f"{resultado['percentual_meta_kcal']:.1f}% da meta energética")
        else:
            partes.append("energia: ficha/dose pendente")
        if t["ptn_100"] is not None:
            partes.append(f"{t['ptn_100']:.1f} g proteína/dia")
            if resultado["percentual_meta_proteina"] is not None:
                partes.append(f"{resultado['percentual_meta_proteina']:.1f}% da meta proteica")
            if resultado["proteina_g_kg"] is not None:
                partes.append(f"{resultado['proteina_g_kg']:.2f} g/kg")
        else:
            partes.append("proteína: ficha/dose pendente")
        pend = len(resultado["pendencias"])
        if pend:
            partes.append(f"{pend} item(ns) com dados incompletos")
        elif not itens:
            partes = ["Adicione itens com dose diária e informe as metas para calcular a participação."]
        self.lbl_oferta.configure(text="Aporte calculado: " + " · ".join(partes))

    # ----------------------------------------------------------------- paciente
    def _buscar_paciente(self):
        DialogBuscarPaciente(self.ui, self._paciente_escolhido)

    def _paciente_escolhido(self, p):
        self._id_paciente = p["id_paciente"]
        self._data_nascimento = p.get("data_nascimento")
        self._vinculo_manual = True
        _set_entry(self.e_nome, p["nome"])
        sexo = nc.norm_sexo(p.get("sexo"))
        if sexo:
            self.seg_sexo.set({"H": "Homem", "M": "Mulher"}[sexo])
        nascimento = p.get("data_nascimento") or ""
        referencia = datetime.fromisoformat(self.data_iso).date()
        try:
            nasc = datetime.strptime(nascimento.strip(), "%d/%m/%Y").date()
            total_meses = (referencia.year - nasc.year) * 12 + referencia.month - nasc.month
            if referencia.day < nasc.day:
                total_meses -= 1
            if total_meses >= 0:
                anos, meses = divmod(total_meses, 12)
                _set_entry(self.e_idade, anos)
                _set_entry(self.e_meses, meses)
        except (ValueError, AttributeError):
            # Sem nascimento válido, preserva a idade que o profissional já informou.
            pass
        self._recalcular()
        self.focus_force()

    # -------------------------------------------------------------------- salvar
    def _atalho_salvar(self, _evento=None):
        if not self.somente_leitura:
            self._salvar()
        return "break"

    def _atalho_fechar(self, _evento=None):
        self.destroy()
        return "break"

    def _salvar(self):
        try:
            reg = self._coletar()
        except ValueError as e:
            messagebox.showwarning("Registro", str(e), parent=self)
            return
        nome = reg["nome_paciente"]
        if nome.strip().lower() != self._nome_original.strip().lower() and not self._vinculo_manual:
            reg["id_paciente"] = None  # nome mudou: é outro paciente nesse leito
            self._data_nascimento = None
            self._recalcular()
            reg["pediatria_oms_json"] = json.dumps(self._resultado_pediatria, ensure_ascii=False)
        if not reg["id_paciente"] and nome:
            iguais = [p for p in mdb.listar_pacientes(self.ui.db, nome) if p["nome"].strip().lower() == nome.lower()]
            if iguais:
                p = iguais[0]
                extra = f" (há {len(iguais)} cadastros com esse nome)" if len(iguais) > 1 else ""
                resp = messagebox.askyesnocancel(
                    "Paciente já cadastrado",
                    f"Já existe '{p['nome']}' no cadastro (nascimento: {p['data_nascimento'] or 'não informado'}){extra}.\n\n"
                    "Sim: vincular este registro a ele (histórico unificado)\n"
                    "Não: criar um novo cadastro\nCancelar: voltar", parent=self)
                if resp is None:
                    return
                if resp:
                    reg["id_paciente"] = p["id_paciente"]
                    self._data_nascimento = p.get("data_nascimento")
                    self._recalcular()
                    reg["pediatria_oms_json"] = json.dumps(self._resultado_pediatria, ensure_ascii=False)
        if reg["idade_anos"] is None and reg["peso_kg"] and reg["altura_cm"]:
            if not messagebox.askyesno("Idade não informada",
                                       "Sem a idade, o IMC não será classificado. Salvar mesmo assim?", parent=self):
                return
        try:
            mdb.salvar_registro(self.ui.db, reg, self.ui.criterio_idoso, self.ui.lms)
        except ValueError as e:
            messagebox.showwarning("Registro", str(e), parent=self)
            return
        self.ui._recarregar()
        self.destroy()

    def _travar(self):
        for w in self._widgets:
            try:
                w.configure(state="disabled")
            except (tk.TclError, ValueError, AttributeError):
                pass

class DialogCurvasOMS(_Janela):
    """Exibe curvas LMS oficiais OMS 2006/2007 e posiciona as medidas do paciente."""

    def __init__(self, ui, tabela, sexo, idade_meses, peso, altura, imc):
        super().__init__(ui, "Curvas de crescimento — OMS", "1100x800")
        ctk.CTkLabel(
            self, text="CURVAS DE CRESCIMENTO OMS · 0–19 ANOS",
            font=ctk.CTkFont(size=18, weight="bold"), text_color=VERDE_ESC
        ).pack(anchor="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(
            self,
            text="Peso/idade está disponível somente até 10 anos. Medir comprimento deitado antes de 24 meses "
                 "e estatura em pé a partir de 24 meses.",
            text_color=tema.SUAVE, wraplength=980, justify="left"
        ).pack(anchor="w", padx=16, pady=(0, 6))
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError as exc:
            ctk.CTkLabel(self, text=f"Biblioteca de gráficos indisponível: {exc}",
                         text_color=tema.ERRO).pack(padx=16, pady=20)
            return
        figura = Figure(figsize=(10, 8), dpi=100)
        eixos = figura.subplots(3, 1)
        configuracoes = (
            ("imc_idade", "IMC/idade", "IMC (kg/m²)", imc),
            ("peso_idade", "Peso/idade", "Peso (kg)", peso),
            ("estatura_idade", "Estatura/idade", "Comprimento/estatura (cm)", altura),
        )
        curvas_z = (
            ("z_menos3", "−3 DP", "--"),
            ("z_menos2", "−2 DP", ":"),
            ("z_zero", "Mediana", "-"),
            ("z_mais2", "+2 DP", ":"),
            ("z_mais3", "+3 DP", "--"),
        )
        for ax, (indicador, titulo, eixo_y, medida_paciente) in zip(eixos, configuracoes):
            ax.set_title(titulo, loc="left", fontsize=10, fontweight="bold")
            ax.set_xlabel("Idade (anos)")
            ax.set_ylabel(eixo_y)
            ax.grid(True, alpha=0.22)
            for referencia in ("oms_2006", "oms_2007"):
                pontos = tabela.curva(indicador, sexo, referencia)
                if not pontos:
                    continue
                xs = []
                for ponto in pontos:
                    x_meses = (ponto["idade"] / 30.4375 if referencia == "oms_2006"
                               else ponto["idade"])
                    if referencia == "oms_2006" and x_meses > 60:
                        continue
                    if referencia == "oms_2007" and x_meses < 60:
                        continue
                    limite_meses = 120 if indicador == "peso_idade" else 228
                    if referencia == "oms_2007" and x_meses > limite_meses:
                        continue
                    xs.append(x_meses / 12.0)
                for chave, rotulo, estilo in curvas_z:
                    ys = []
                    for ponto in pontos:
                        x_meses = (ponto["idade"] / 30.4375 if referencia == "oms_2006"
                                   else ponto["idade"])
                        if referencia == "oms_2006" and x_meses > 60:
                            continue
                        if referencia == "oms_2007" and x_meses < 60:
                            continue
                        limite_meses = 120 if indicador == "peso_idade" else 228
                        if referencia == "oms_2007" and x_meses > limite_meses:
                            continue
                        ys.append(ponto[chave])
                    ax.plot(xs, ys, linestyle=estilo, linewidth=1.0 if chave != "z_zero" else 1.8,
                            label=rotulo if referencia == "oms_2006" else None)
            limite_medida = 120 if indicador == "peso_idade" else 228
            if medida_paciente is not None and idade_meses is not None and 0 <= idade_meses <= limite_medida:
                ax.scatter([idade_meses / 12.0], [medida_paciente], marker="o", s=42,
                           edgecolors="black", linewidths=0.6, zorder=5, label="Paciente")
            ax.set_xlim(0, 19)
            if indicador == "peso_idade":
                ax.axvline(10, linestyle="--", linewidth=0.8, alpha=0.5)
        eixos[0].legend(loc="best", ncol=6, fontsize=8)
        figura.tight_layout(pad=2.0)
        canvas = FigureCanvasTkAgg(figura, master=self)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=8)

