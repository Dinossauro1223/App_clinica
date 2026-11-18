# -*- coding: utf-8 -*-
"""Telas do Mapa Nutricional (CustomTkinter): mapa do dia, registro por leito, histórico,
leitos, suplementos (ficha técnica) e gráficos mensais.

A lógica (cálculos, banco, exportação, gráficos) fica nos módulos nutri_calculos, mapa_db,
mapa_export e mapa_graficos; aqui só há interface. mapa_export e mapa_graficos são
importados na hora de usar (openpyxl, fpdf e matplotlib não atrasam a abertura do programa).
"""
import io
import os
import sqlite3
from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import customtkinter as ctk

import nutri_calculos as nc
import mapa_db as mdb
import condutas_alta as ca

VERDE_ESC, VERDE, VERDE_HOVER, FUNDO = "#1b5e20", "#4caf50", "#388e3c", "#F0F7F4"
CINZA_BTN, CINZA_HOVER = "#78909c", "#546e7a"
VERMELHO, VERMELHO_HOVER, LARANJA = "#c62828", "#8e0000", "#ef6c00"
ESTILO_TREE = "Mapa.Treeview"


def _estilo_tree():
    st = ttk.Style()
    st.theme_use("default")
    st.configure(ESTILO_TREE, font=("Segoe UI", 10), rowheight=28)
    st.configure(ESTILO_TREE + ".Heading", font=("Segoe UI", 10, "bold"), background=VERDE, foreground="white")
    st.map(ESTILO_TREE, background=[("selected", "#2e7d32")], foreground=[("selected", "white")])


def _btn(master, texto, comando, largura=140, cor=VERDE, hover=VERDE_HOVER, altura=32):
    return ctk.CTkButton(master, text=texto, command=comando, width=largura, height=altura, fg_color=cor,
                         hover_color=hover, text_color="#ffffff", font=ctk.CTkFont(size=12, weight="bold"))


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
        self.lms = None  # tabelas LMS da OMS (opcional): dados/oms_imc_idade_lms.csv
        for pasta in (os.path.dirname(os.path.abspath(db_path)), base_dir):
            self.lms = self.lms or nc.TabelaLMS.carregar_padrao(pasta)
        self._imagens = []

    # ------------------------------------------------------------------ configurações
    @property
    def criterio_idoso(self):
        return mdb.obter_config(self.db, "criterio_idoso", "lipschitz")

    @property
    def metodo_altura_idoso(self):
        return mdb.obter_config(self.db, "metodo_altura_idoso", "chumlea1985")

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
        if not self.id_setor or self.id_setor not in [s["id_setor"] for s in self.setores]:
            self.id_setor = self.setores[0]["id_setor"] if self.setores else None

        topo = ctk.CTkFrame(area, fg_color="transparent")
        topo.pack(fill="x", padx=20, pady=(15, 5))
        _titulo(topo, "Mapa Nutricional").pack(side="left")
        _btn(topo, "Configurações", self._abrir_config, 120, CINZA_BTN, CINZA_HOVER).pack(side="right", padx=(6, 0))
        _btn(topo, "Leitos", self._abrir_leitos, 90, CINZA_BTN, CINZA_HOVER).pack(side="right")

        barra = ctk.CTkFrame(area, fg_color="transparent")
        barra.pack(fill="x", padx=20, pady=4)
        _btn(barra, "◀", lambda: self._mudar_dia(-1), 40).pack(side="left")
        self.e_data = ctk.CTkEntry(barra, width=110, justify="center")
        self.e_data.pack(side="left", padx=4)
        self.e_data.bind("<Return>", lambda e: self._aplicar_data())
        _btn(barra, "▶", lambda: self._mudar_dia(1), 40).pack(side="left")
        _btn(barra, "Hoje", self._ir_hoje, 70, CINZA_BTN, CINZA_HOVER).pack(side="left", padx=(8, 16))
        ctk.CTkLabel(barra, text="Setor:").pack(side="left")
        self.cb_setor = ctk.CTkComboBox(barra, values=[s["nome"] for s in self.setores], width=190, state="readonly",
                                        command=self._trocar_setor)
        self.cb_setor.pack(side="left", padx=6)
        if self.id_setor:
            self.cb_setor.set([s["nome"] for s in self.setores if s["id_setor"] == self.id_setor][0])

        acoes = ctk.CTkFrame(area, fg_color="transparent")
        acoes.pack(fill="x", padx=20, pady=4)
        _btn(acoes, "Registrar / Editar", self._editar, 150).pack(side="left", padx=(0, 6))
        _btn(acoes, "Histórico", self._historico, 100, CINZA_BTN, CINZA_HOVER).pack(side="left", padx=(0, 6))
        _btn(acoes, "Condutas de alta", self._condutas_alta, 140, LARANJA, "#e65100").pack(side="left", padx=(0, 6))
        _btn(acoes, "Copiar último mapa", self._copiar_ultimo, 150, CINZA_BTN, CINZA_HOVER).pack(side="left", padx=(0, 6))
        _btn(acoes, "Remover do mapa", self._remover, 130, VERMELHO, VERMELHO_HOVER).pack(side="left", padx=(0, 6))
        _btn(acoes, "Excel", self._exportar_excel, 80, "#1565c0", "#0d47a1").pack(side="right")
        _btn(acoes, "PDF", self._exportar_pdf, 70, "#1565c0", "#0d47a1").pack(side="right", padx=6)

        self.lbl_aviso = ctk.CTkLabel(area, text="", text_color=LARANJA, font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_aviso.pack(fill="x", padx=22, pady=(2, 0), anchor="w")
        self.lbl_condutas = ctk.CTkLabel(area, text="", text_color=LARANJA, font=ctk.CTkFont(size=12, weight="bold"),
                                         anchor="w", justify="left")
        self.lbl_condutas.pack(fill="x", padx=22, pady=(0, 0), anchor="w")

        quadro = ctk.CTkFrame(area, fg_color="white")
        quadro.pack(fill="both", expand=True, padx=20, pady=6)
        colunas = [("leito", "Leito", 60, "center"), ("acomp", "Acomp.", 60, "center"), ("paciente", "Paciente", 220, "w"),
                   ("idade", "Idade", 50, "center"), ("imc", "IMC (classificação)", 170, "w"),
                   ("via", "Via", 70, "center"), ("consist", "Consistência", 85, "center"),
                   ("supl", "Suplementos", 190, "w"), ("fi", "Função intestinal", 110, "center"),
                   ("condutas", "Condutas de alta", 120, "center")]
        self.tree = ttk.Treeview(quadro, columns=[c[0] for c in colunas], show="headings", style=ESTILO_TREE,
                                 selectmode="browse")
        for chave, titulo, larg, anc in colunas:
            self.tree.heading(chave, text=titulo)
            self.tree.column(chave, width=larg, anchor=anc, stretch=chave in ("paciente", "supl"))
        self.tree.tag_configure("vago", foreground="#9e9e9e")
        self.tree.tag_configure("condpend", foreground="#e65100")
        rolagem = ttk.Scrollbar(quadro, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=rolagem.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        rolagem.pack(side="right", fill="y", pady=6)
        self.tree.bind("<Double-1>", lambda e: self._editar())

        self.lbl_resumo = ctk.CTkLabel(area, text="", font=ctk.CTkFont(size=12), text_color="#37474f")
        self.lbl_resumo.pack(fill="x", padx=22, pady=(0, 10), anchor="w")
        self._recarregar()

    def _trocar_setor(self, nome):
        for s in self.setores:
            if s["nome"] == nome:
                self.id_setor = s["id_setor"]
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
        ocupados = past = acomp = sup = com_pendencia = 0
        for it in self.linhas:
            l, r = it["leito"], it["registro"]
            if r is None:
                vals = (l["codigo"], "", "— vago —", "", "", "", "", "", "", "")
                tag = ("vago",)
            else:
                ocupados += 1
                past += r.get("consistencia") == "Pastosa"
                acomp += bool(r.get("acompanhante"))
                sup += bool(r.get("suplementos"))
                imc = f"{_fmt(r.get('imc'))} ({r['imc_class']})" if r.get("imc") and r.get("imc_class") else _fmt(r.get("imc"))
                cond = resumo.get(r.get("id_paciente"), {})
                vals = (l["codigo"], "Sim" if r.get("acompanhante") else "Não", r["nome_paciente"],
                        "" if r.get("idade_anos") is None else r["idade_anos"], imc, r.get("via") or "",
                        r.get("consistencia") or "", ", ".join(s["nome"] for s in r["suplementos"]),
                        self._fi_txt(r), cond.get("texto", ""))
                tag = ("condpend",) if cond.get("estado") == "pendente" else ()
                com_pendencia += cond.get("estado") == "pendente"
            self.tree.insert("", "end", iid=str(l["id_leito"]), values=vals, tags=tag)
        self._mostrar_aviso_condutas(com_pendencia)
        total = len(self.linhas)
        if not total:
            self.lbl_resumo.configure(text="Nenhum leito cadastrado neste setor. Use o botão \"Leitos\" para cadastrar.")
        else:
            self.lbl_resumo.configure(
                text=f"{ocupados} de {total} leitos com registro  ·  {past} em dieta pastosa  ·  "
                     f"{acomp} com acompanhante  ·  {sup} com suplemento")

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
        return next((s["nome"] for s in self.setores if s["id_setor"] == self.id_setor), "Setor")

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
        self.cb_setor_g = ctk.CTkComboBox(barra, values=["Todos os setores"] + [s["nome"] for s in self.setores],
                                          width=180, state="readonly")
        self.cb_setor_g.pack(side="left", padx=6)
        self.cb_setor_g.set("Todos os setores")
        _btn(barra, "Gerar", self._gerar_graficos, 90).pack(side="left", padx=(10, 6))
        _btn(barra, "Salvar imagens", self._salvar_graficos, 130, CINZA_BTN, CINZA_HOVER).pack(side="left")

        self.quadro_kpi = ctk.CTkFrame(area, fg_color="transparent")
        self.quadro_kpi.pack(fill="x", padx=20, pady=(8, 2))
        self.quadro_graf = ctk.CTkScrollableFrame(area, fg_color="white")
        self.quadro_graf.pack(fill="both", expand=True, padx=20, pady=(4, 12))
        self._agg = None
        self._gerar_graficos()

    def _parametros_graficos(self):
        mes = [m.capitalize() for m in self._mgr.MESES].index(self.cb_mes.get()) + 1
        ano = int(self.cb_ano.get())
        nome = self.cb_setor_g.get()
        id_setor = next((s["id_setor"] for s in self.setores if s["nome"] == nome), None)
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
                   ("Com suplemento", f"{k['com_suplemento']} ({k['com_suplemento_pct']:.0f}%)")]
        for rot, val in cartoes:
            cx = ctk.CTkFrame(self.quadro_kpi, fg_color="white", corner_radius=8)
            cx.pack(side="left", padx=4, ipadx=8, ipady=4)
            ctk.CTkLabel(cx, text=val, font=ctk.CTkFont(size=18, weight="bold"), text_color=VERDE_ESC).pack(padx=8)
            ctk.CTkLabel(cx, text=rot, font=ctk.CTkFont(size=11), text_color="#546e7a").pack(padx=8)
        for w in self.quadro_graf.winfo_children():
            w.destroy()
        from PIL import Image
        for _, _, png in self._mgr.gerar_todos(self._agg):
            img = Image.open(io.BytesIO(png)).convert("RGB")
            largura = min(img.width, 840)
            alt = int(img.height * largura / img.width)
            ci = ctk.CTkImage(light_image=img, dark_image=img, size=(largura, alt))
            self._imagens.append(ci)
            ctk.CTkLabel(self.quadro_graf, text="", image=ci).pack(pady=6)

    def _salvar_graficos(self):
        if not self._agg:
            return
        pasta = filedialog.askdirectory(title="Escolha a pasta para salvar as imagens")
        if not pasta:
            return
        try:
            caminhos = self._mgr.salvar_graficos(self._agg, pasta)
        except OSError as e:
            messagebox.showerror("Salvar imagens", f"Não foi possível gravar:\n{e}")
            return
        messagebox.showinfo("Salvar imagens", f"{len(caminhos)} imagens salvas em:\n{pasta}")

    # ===================================================================== SUPLEMENTOS
    def mostrar_suplementos(self):
        area = self._preparar_area()
        _titulo(area, "Suplementos (ficha técnica)").pack(anchor="w", padx=20, pady=(15, 2))
        ctk.CTkLabel(area, text="Valores por 100 mL ou 100 g, conforme a ficha técnica. O módulo define o agrupamento "
                                "da lista suspensa do mapa e dos gráficos.", text_color="#546e7a").pack(anchor="w", padx=22)
        barra = ctk.CTkFrame(area, fg_color="transparent")
        barra.pack(fill="x", padx=20, pady=8)
        _btn(barra, "Novo", self._novo_suplemento, 80).pack(side="left", padx=(0, 6))
        _btn(barra, "Editar", self._editar_suplemento, 80, CINZA_BTN, CINZA_HOVER).pack(side="left", padx=(0, 6))
        _btn(barra, "Ativar/Desativar", self._alternar_suplemento, 140, CINZA_BTN, CINZA_HOVER).pack(side="left", padx=(0, 6))
        _btn(barra, "Excluir", self._excluir_suplemento, 80, VERMELHO, VERMELHO_HOVER).pack(side="left", padx=(0, 12))
        self.var_inativos = tk.IntVar(value=0)
        ctk.CTkCheckBox(barra, text="Mostrar inativos", variable=self.var_inativos,
                        command=self._recarregar_suplementos).pack(side="left")
        quadro = ctk.CTkFrame(area, fg_color="white")
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
        self.tree_sup.tag_configure("inativo", foreground="#9e9e9e")
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
class _Janela(ctk.CTkToplevel):
    def __init__(self, ui, titulo, geometria):
        super().__init__(ui.app)
        self.ui = ui
        self.title(titulo)
        self.geometry(geometria)
        self.attributes("-topmost", True)
        self.after(200, lambda: _tornar_modal(self))


class DialogConfig(_Janela):
    def __init__(self, ui):
        super().__init__(ui, "Configurações do Mapa", "560x300")
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
                     text_color="#546e7a").pack(anchor="w", padx=20, pady=(12, 0))
        _btn(self, "Salvar", self._salvar, 120).pack(pady=16)

    def _salvar(self):
        for chave, rot in nc.CRITERIOS_IMC_IDOSO.items():
            if rot == self.cb_imc.get():
                mdb.salvar_config(self.ui.db, "criterio_idoso", chave)
        for chave, rot in nc.METODOS_ALTURA_IDOSO.items():
            if rot == self.cb_alt.get():
                mdb.salvar_config(self.ui.db, "metodo_altura_idoso", chave)
        self.destroy()


class DialogLeitos(_Janela):
    def __init__(self, ui):
        super().__init__(ui, "Leitos e setores", "560x600")
        self.setores = mdb.listar_setores(ui.db)
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(topo, text="Setor:").pack(side="left")
        self.cb_setor = ctk.CTkComboBox(topo, values=[s["nome"] for s in self.setores], width=200, state="readonly",
                                        command=lambda v: self._recarregar())
        self.cb_setor.pack(side="left", padx=6)
        atual = next((s["nome"] for s in self.setores if s["id_setor"] == ui.id_setor), self.setores[0]["nome"])
        self.cb_setor.set(atual)
        self.e_novo_setor = ctk.CTkEntry(topo, width=130, placeholder_text="Novo setor")
        self.e_novo_setor.pack(side="left", padx=(12, 4))
        _btn(topo, "Criar", self._criar_setor, 60, CINZA_BTN, CINZA_HOVER).pack(side="left")

        quadro = ctk.CTkFrame(self, fg_color="white")
        quadro.pack(fill="both", expand=True, padx=16, pady=6)
        self.tree = ttk.Treeview(quadro, columns=("codigo", "situacao"), show="headings", style=ESTILO_TREE,
                                 selectmode="browse", height=10)
        self.tree.heading("codigo", text="Leito")
        self.tree.heading("situacao", text="Situação")
        self.tree.column("codigo", width=300, anchor="w")
        self.tree.column("situacao", width=120, anchor="center")
        self.tree.tag_configure("inativo", foreground="#9e9e9e")
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
        return next(s["id_setor"] for s in self.setores if s["nome"] == self.cb_setor.get())

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
        self.cb_setor.configure(values=[s["nome"] for s in self.setores])
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
        quadro = ctk.CTkFrame(self, fg_color="white")
        quadro.pack(fill="both", expand=True, padx=16, pady=6)
        self.tree = ttk.Treeview(quadro, columns=("id", "nome", "nasc", "sexo"), show="headings", style=ESTILO_TREE,
                                 selectmode="browse")
        for c, t, w in (("id", "ID", 50), ("nome", "Nome", 280), ("nasc", "Nascimento", 90), ("sexo", "Sexo", 80)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w" if c == "nome" else "center")
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree.bind("<Double-1>", lambda e: self._escolher())
        _btn(self, "Usar este paciente", self._escolher, 170).pack(pady=(4, 14))
        self._buscar()

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
        super().__init__(ui, "Histórico do paciente", "900x480")
        self.reg = reg
        ctk.CTkLabel(self, text=reg["nome_paciente"], font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=VERDE_ESC).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkLabel(self, text="Duplo clique (ou o botão abaixo) abre o registro do dia, somente para consulta.",
                     text_color="#546e7a").pack(anchor="w", padx=16)
        quadro = ctk.CTkFrame(self, fg_color="white")
        quadro.pack(fill="both", expand=True, padx=16, pady=8)
        cols = [("data", "Data", 90), ("leito", "Leito", 60), ("peso", "Peso (kg)", 80), ("imc", "IMC", 150),
                ("via", "Via", 70), ("consist", "Consist.", 80), ("supl", "Suplementos", 220), ("reav", "Reav.", 90)]
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
            self.tree.insert("", "end", iid=str(r["id_registro"]), values=(
                mdb.iso_para_br(r["data"]), r["leito_codigo"], _fmt(r.get("peso_kg")), imc, r.get("via") or "",
                r.get("consistencia") or "", ", ".join(s["nome"] for s in r["suplementos"]),
                mdb.iso_para_br(r.get("data_reavaliacao"))))
        _btn(self, "Abrir registro", self._abrir, 140).pack(pady=(0, 14))

    def _abrir(self):
        sel = self.tree.selection()
        if not sel:
            return
        r = next(x for x in self.itens if str(x["id_registro"]) == sel[0])
        leito = {"id_leito": r["id_leito"], "codigo": r["leito_codigo"], "setor": r["setor"]}
        FormRegistro(self.ui, {"leito": leito, "registro": r}, somente_leitura=True, data_iso=r["data"])


# ================================================================== FORMULÁRIO DO REGISTRO
class FormRegistro(ctk.CTkToplevel):
    """Registro de um leito num dia (a anamnese do mapa num só lugar)."""

    def __init__(self, ui, item, somente_leitura=False, data_iso=None):
        super().__init__(ui.app)
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
        self._nome_original = self.reg.get("nome_paciente") or ""
        self._vinculo_manual = False
        self._altura_metodo = self.reg.get("altura_metodo")
        self._peso_metodo = self.reg.get("peso_metodo")
        self._suplementos = [dict(s) for s in self.reg.get("suplementos", [])]
        self._catalogo = mdb.listar_suplementos(ui.db)
        self._montar()
        self._preencher()
        self._recalcular()
        if somente_leitura:
            self._travar()
        self.after(200, lambda: _tornar_modal(self))

    # ----------------------------------------------------------------- construção
    def _reg(self, w):
        self._widgets.append(w)
        return w

    def _secao(self, titulo):
        ctk.CTkLabel(self.corpo, text=titulo, font=ctk.CTkFont(size=14, weight="bold"), text_color=VERDE_ESC
                     ).pack(anchor="w", padx=14, pady=(12, 2))
        quadro = ctk.CTkFrame(self.corpo, fg_color="white", corner_radius=8)
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
        self.lbl_class = ctk.CTkLabel(l, text="", text_color="#d50000", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_class.pack(side="left")
        self.lbl_info = ctk.CTkLabel(q, text="", text_color="#546e7a", wraplength=760, justify="left",
                                     font=ctk.CTkFont(size=11))
        self.lbl_info.pack(anchor="w", padx=12, pady=(0, 6))

        q = self._secao("Dieta")
        l = self._linha(q)
        self.e_reav = self._entrada(l, "Reavaliação prevista (DD/MM/AAAA)", 100)
        self.seg_via = self._seg(l, "Via", mdb.VIAS)
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
        ctk.CTkLabel(l, text="(com as marcações acima, escolhem as condutas de alta)", text_color="#546e7a",
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=8)
        l = self._linha(q)
        self.seg_cons = self._seg(l, "Consistência", mdb.CONSISTENCIAS)

        q = self._secao("Suplementos administrados")
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
            anchor="w", padx=10, pady=(0, 8))

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

    def _fi_mudou(self, valor):
        if valor == "Presente" and not self.e_fi_freq.get().strip():
            _set_entry(self.e_fi_freq, "1")

    def _coletar(self):
        g = lambda e: e.get().strip()
        n = lambda e: nc.parse_num(g(e))
        idade, meses = n(self.e_idade), n(self.e_meses)
        reav = None
        if g(self.e_reav):
            try:
                reav = mdb.data_br_para_iso(g(self.e_reav))
            except ValueError:
                raise ValueError("Data de reavaliação inválida. Use DD/MM/AAAA.")
        for campo, rot in ((self.e_aj, "AJ"), (self.e_pp, "PP"), (self.e_pb, "PB"), (self.e_altura, "Altura"),
                           (self.e_peso, "Peso"), (self.e_idade, "Idade"), (self.e_fi_freq, "Frequência"),
                           (self.e_fi_dias, "Dias")):
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
            **{campo: var.get() for campo, var in self.var_carac.items()},
            "condicoes": ",".join(c for c, var in self.var_cond.items() if var.get()) or None,
            "consistencia": self.seg_cons.get() or None,
            "obs_sim": self.t_sim.get("1.0", "end-1c").strip(), "obs_nao": self.t_nao.get("1.0", "end-1c").strip(),
            "fi_estado": fi, "fi_freq": n(self.e_fi_freq) if fi == "P" else None,
            "fi_dias_ausente": int(dias) if (fi == "A" and dias is not None) else None,
            "suplementos": list(self._suplementos),
        }

    # ---------------------------------------------------------------- cálculos
    def _recalcular(self):
        peso, alt = nc.parse_num(self.e_peso.get()), nc.parse_num(self.e_altura.get())
        idade = nc.parse_num(self.e_idade.get())
        imc = nc.calcular_imc(peso, alt)
        if imc is None:
            self.lbl_imc.configure(text="-")
            self.lbl_class.configure(text="")
            return
        self.lbl_imc.configure(text=nc.fmt_num(imc, 1))
        if idade is None:
            self.lbl_class.configure(text="(informe a idade para classificar)")
            return
        cl = nc.classificar_imc(imc, int(idade), {"Homem": "H", "Mulher": "M"}.get(self.seg_sexo.get()),
                                int(nc.parse_num(self.e_meses.get()) or 0), self.ui.criterio_idoso, self.ui.lms)
        txt = nc.texto_classificacao(cl)
        self.lbl_class.configure(text=f"({txt})" if txt else "")

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
    def _filtrar_sup(self):
        modulo = self.cb_mod.get()
        nomes = [s["nome"] for s in self._catalogo if modulo == "Todos os módulos" or s["modulo"] == modulo]
        self.cb_sup.configure(values=nomes)
        self.cb_sup.set(nomes[0] if len(nomes) == 1 else "")

    def _add_sup(self):
        nome = self.cb_sup.get()
        s = next((x for x in self._catalogo if x["nome"] == nome), None)
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
        self._suplementos.append({"id_suplemento": s["id_suplemento"], "nome": s["nome"], "modulo": s["modulo"],
                                  "qtd_dia": qtd, "unidade": s["emb_un"]})
        _set_entry(self.e_qtd, "")
        self._atualizar_sup()

    def _rem_sup(self):
        sel = self.tree_sup.selection()
        if sel:
            del self._suplementos[int(sel[0])]
            self._atualizar_sup()

    def _atualizar_sup(self):
        self.tree_sup.delete(*self.tree_sup.get_children())
        for i, s in enumerate(self._suplementos):
            qtd = f"{_fmt(s.get('qtd_dia')).replace(',0', '')} {s.get('unidade') or ''}".strip() if s.get("qtd_dia") else ""
            self.tree_sup.insert("", "end", iid=str(i), values=(s.get("modulo") or "", s["nome"], qtd))

    # ----------------------------------------------------------------- paciente
    def _buscar_paciente(self):
        DialogBuscarPaciente(self.ui, self._paciente_escolhido)

    def _paciente_escolhido(self, p):
        self._id_paciente = p["id_paciente"]
        self._vinculo_manual = True
        _set_entry(self.e_nome, p["nome"])
        sexo = nc.norm_sexo(p.get("sexo"))
        if sexo:
            self.seg_sexo.set({"H": "Homem", "M": "Mulher"}[sexo])
        idade = nc.idade_em_anos(p.get("data_nascimento") or "", datetime.fromisoformat(self.data_iso).date())
        if idade is not None:
            _set_entry(self.e_idade, idade)
        self._recalcular()
        self.focus_force()

    # -------------------------------------------------------------------- salvar
    def _salvar(self):
        try:
            reg = self._coletar()
        except ValueError as e:
            messagebox.showwarning("Registro", str(e), parent=self)
            return
        nome = reg["nome_paciente"]
        if nome.strip().lower() != self._nome_original.strip().lower() and not self._vinculo_manual:
            reg["id_paciente"] = None  # nome mudou: é outro paciente nesse leito
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
