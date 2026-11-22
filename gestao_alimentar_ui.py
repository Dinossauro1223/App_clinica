# -*- coding: utf-8 -*-
"""Interface desktop da Gestão alimentar (Fichas técnicas)."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

import gestao_alimentar_db as ga
import integracao_mobile as im

VERDE_ESC = "#0F3D2E"
VERDE = "#1E7A4F"
VERDE_HOVER = "#17633F"
LARANJA = "#ef6c00"
CINZA = "#607d8b"
UNIDADES = ["g", "kg", "mg", "ml", "L", "un"]
CATEGORIAS = ["Salada", "Acompanhamento", "Prato principal", "Guarnição", "Sobremesa", "Suco", "Preparação", "Outra"]


def _fmt_num(valor, casas=2):
    if valor is None:
        return "—"
    try:
        return (f"{float(valor):,.{casas}f}").replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(valor)


def _fmt_brl(valor):
    return "—" if valor is None else "R$ " + _fmt_num(valor, 2)


def _btn(master, texto, comando, largura=145, cor=VERDE, hover=VERDE_HOVER):
    return ctk.CTkButton(master, text=texto, command=comando, width=largura, height=34,
                         fg_color=cor, hover_color=hover, font=ctk.CTkFont(size=12, weight="bold"))


def _tree(master, definicoes, altura=12):
    cols = [x[0] for x in definicoes]
    frame = ctk.CTkFrame(master, fg_color="transparent")
    tree = ttk.Treeview(frame, columns=cols, show="headings", height=altura, selectmode="browse")
    for key, titulo, largura, ancora in definicoes:
        tree.heading(key, text=titulo)
        tree.column(key, width=largura, minwidth=max(48, min(largura, 72)), anchor=ancora, stretch=True)
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return frame, tree


class GestaoAlimentarUI:
    """Tela principal da função de fichas técnicas."""

    def __init__(self, app, db_path, base_dir):
        self.app, self.db, self.base_dir = app, db_path, base_dir
        self.mobile_db = im.caminho_mobile_db(db_path, base_dir)
        self.fichas_tree = None
        self.produtos_tree = None
        self.tbca_tree = None
        self.lbl_status = None
        self.lbl_resumo = None
        self.lbl_tbca_count = None
        self.var_busca_tbca = tk.StringVar(value="")
        self._ficha_selecionada = None
        ga.inicializar(self.db)

    def mostrar(self):
        self.app.limpar_area_principal()
        area = self.app.area_principal
        topo = ctk.CTkFrame(area, fg_color="transparent")
        topo.pack(fill="x", padx=18, pady=(12, 2))
        ctk.CTkLabel(topo, text="Gestão alimentar — Fichas técnicas", font=ctk.CTkFont(size=23, weight="bold"),
                     text_color=VERDE_ESC).pack(side="left")
        _btn(topo, "Sincronizar Almoxarifado", self.sincronizar, 190, cor=CINZA, hover="#455a64").pack(side="right")
        self.lbl_status = ctk.CTkLabel(area, text="Produtos do Almoxarifado ainda não sincronizados nesta sessão.",
                                       text_color="#52645a", font=ctk.CTkFont(size=11), anchor="w")
        self.lbl_status.pack(fill="x", padx=20, pady=(0, 5))

        self.tabs = ctk.CTkTabview(area, segmented_button_selected_color=VERDE,
                                  segmented_button_selected_hover_color=VERDE_HOVER,
                                  segmented_button_unselected_color="#9eada4",
                                  segmented_button_unselected_hover_color="#71857a")
        self.tabs.pack(fill="both", expand=True, padx=14, pady=(2, 12))
        self.tab_fichas = self.tabs.add("Fichas técnicas")
        self.tab_almox = self.tabs.add("Almoxarifado")
        self.tab_tbca = self.tabs.add("Base TBCA")
        self._montar_tab_fichas()
        self._montar_tab_almox()
        self._montar_tab_tbca()
        self.carregar_fichas()
        self.carregar_produtos()
        self.carregar_tbca_count()
        # Tenta sincronizar automaticamente; falha de conexão não impede o uso da ficha.
        self.sincronizar(silencioso=True)

    def _montar_tab_fichas(self):
        barra = ctk.CTkFrame(self.tab_fichas, fg_color="transparent")
        barra.pack(fill="x", padx=8, pady=(6, 4))
        _btn(barra, "＋ Nova ficha", self.nova_ficha, 125).pack(side="left")
        _btn(barra, "Editar selecionada", self.editar_ficha, 150, cor=CINZA, hover="#455a64").pack(side="left", padx=6)
        _btn(barra, "Inativar", self.inativar_ficha, 95, cor=LARANJA, hover="#e65100").pack(side="left")
        ctk.CTkLabel(barra, text="Selecione uma ficha para ver cálculo, custo e estoque.",
                     font=ctk.CTkFont(size=11), text_color="#546e7a").pack(side="left", padx=12)

        corpo = ctk.CTkFrame(self.tab_fichas, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=7, pady=(3, 6))
        corpo.grid_columnconfigure(0, weight=1, minsize=280)
        corpo.grid_columnconfigure(1, weight=2, minsize=450)
        corpo.grid_rowconfigure(0, weight=1)
        esquerda = ctk.CTkFrame(corpo)
        esquerda.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        direita = ctk.CTkFrame(corpo)
        direita.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        ctk.CTkLabel(esquerda, text="Preparações cadastradas", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=VERDE_ESC).pack(anchor="w", padx=10, pady=(9, 4))
        frame, self.fichas_tree = _tree(esquerda, [("nome", "Preparação", 220, "w"),
                                                  ("porcoes", "Porções", 65, "center")], altura=18)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.fichas_tree.bind("<<TreeviewSelect>>", self._selecionar_ficha)
        ctk.CTkLabel(direita, text="Composição e resultado", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=VERDE_ESC).pack(anchor="w", padx=10, pady=(9, 2))
        self.lbl_resumo = ctk.CTkLabel(direita, text="Nenhuma ficha selecionada.", anchor="w", justify="left",
                                       wraplength=720, font=ctk.CTkFont(size=12), text_color="#31443a")
        self.lbl_resumo.pack(fill="x", padx=10, pady=(2, 8))
        frame, self.ingredientes_tree = _tree(direita, [
            ("nome", "Ingrediente", 185, "w"), ("qtd", "Per capita", 95, "e"),
            ("fc", "FC", 55, "center"), ("bruto", "Bruto total", 105, "e"),
            ("custo", "Custo total", 100, "e"), ("estoque", "Estoque", 100, "center")], altura=13)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.lbl_nutrientes = ctk.CTkLabel(direita, text="", anchor="w", justify="left", wraplength=720,
                                          font=ctk.CTkFont(size=11), text_color="#455a64")
        self.lbl_nutrientes.pack(fill="x", padx=10, pady=(0, 10))

    def _montar_tab_almox(self):
        topo = ctk.CTkFrame(self.tab_almox, fg_color="transparent")
        topo.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(topo, text="Itens recebidos do estoque Almoxarifado no mobile",
                     font=ctk.CTkFont(size=14, weight="bold"), text_color=VERDE_ESC).pack(side="left")
        _btn(topo, "Atualizar agora", self.sincronizar, 125, cor=CINZA, hover="#455a64").pack(side="right")
        ctk.CTkLabel(self.tab_almox,
                     text="O saldo é lido do mobile. Preço unitário refere-se à unidade de estoque cadastrada; conteúdo da embalagem informa quantos g/ml/un essa unidade contém.",
                     font=ctk.CTkFont(size=11), text_color="#546e7a", anchor="w", justify="left", wraplength=900).pack(fill="x", padx=10, pady=4)
        frame, self.produtos_tree = _tree(self.tab_almox, [
            ("nome", "Produto", 220, "w"), ("un", "Un. estoque", 95, "center"),
            ("preco", "Preço unitário", 110, "e"), ("emb", "Conteúdo/unidade", 125, "e"),
            ("saldo", "Qtd. em estoque", 115, "e"), ("data", "Data do saldo", 125, "center")], altura=18)
        frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))

    def _montar_tab_tbca(self):
        topo = ctk.CTkFrame(self.tab_tbca, fg_color="transparent")
        topo.pack(fill="x", padx=8, pady=(8, 5))
        _btn(topo, "Importar TBCA do Excel", self.importar_tbca, 175).pack(side="left")
        self.lbl_tbca_count = ctk.CTkLabel(topo, text="Alimentos na base: 0", font=ctk.CTkFont(size=12, weight="bold"),
                                           text_color=VERDE_ESC)
        self.lbl_tbca_count.pack(side="left", padx=12)
        busca = ctk.CTkEntry(topo, textvariable=self.var_busca_tbca, width=250, placeholder_text="Buscar alimento ou ID TBCA")
        busca.pack(side="right", padx=(4, 0))
        busca.bind("<Return>", lambda _e: self.buscar_tbca())
        _btn(topo, "Buscar", self.buscar_tbca, 85, cor=CINZA, hover="#455a64").pack(side="right")
        ctk.CTkLabel(self.tab_tbca,
                     text="Importa a aba ‘TBCA (2024)’ do arquivo de referência. As demais abas de fórmulas da planilha não são executadas pelo aplicativo; a ficha aplica seus próprios cálculos validados.",
                     font=ctk.CTkFont(size=11), text_color="#546e7a", anchor="w", justify="left", wraplength=930).pack(fill="x", padx=10, pady=3)
        frame, self.tbca_tree = _tree(self.tab_tbca, [
            ("id", "ID", 90, "center"), ("alimento", "Alimento", 330, "w"),
            ("kcal", "kcal/100g", 90, "e"), ("proteina", "Proteína/100g", 110, "e"),
            ("carbo", "Carboidrato/100g", 120, "e"), ("lipidio", "Lipídio/100g", 100, "e")], altura=18)
        frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.buscar_tbca()

    # --------------------------------------------------------------- fichas
    def carregar_fichas(self):
        for iid in self.fichas_tree.get_children():
            self.fichas_tree.delete(iid)
        for ficha in ga.listar_fichas(self.db):
            iid = str(ficha["id_ficha"])
            self.fichas_tree.insert("", "end", iid=iid, values=(ficha["nome"], _fmt_num(ficha["porcoes"], 0)))
        if self.fichas_tree.get_children() and not self.fichas_tree.selection():
            primeiro = self.fichas_tree.get_children()[0]
            self.fichas_tree.selection_set(primeiro)
            self.fichas_tree.focus(primeiro)
            self._selecionar_ficha()
        elif not self.fichas_tree.get_children():
            self._ficha_selecionada = None
            self.lbl_resumo.configure(text="Nenhuma ficha cadastrada. Use ‘Nova ficha’ para começar.")
            for iid in self.ingredientes_tree.get_children():
                self.ingredientes_tree.delete(iid)
            self.lbl_nutrientes.configure(text="")

    def _selecionar_ficha(self, _event=None):
        selecionados = self.fichas_tree.selection()
        if not selecionados:
            return
        self._ficha_selecionada = int(selecionados[0])
        self._mostrar_detalhes(self._ficha_selecionada)

    def _mostrar_detalhes(self, id_ficha):
        try:
            resultado = ga.calcular_ficha(self.db, id_ficha)
        except Exception as exc:
            messagebox.showerror("Gestão alimentar", f"Não foi possível calcular a ficha.\n\n{exc}")
            return
        ficha = resultado["ficha"]
        custo = _fmt_brl(resultado["custo_total"])
        if resultado["custo_total"] is None:
            custo = "incompleto — parcial: " + _fmt_brl(resultado["custo_parcial_total"])
        alertas = []
        if resultado["custos_faltantes"]:
            alertas.append(f"{resultado['custos_faltantes']} ingrediente(s) sem preço/conteúdo compatível")
        if resultado["estoque_insuficiente"]:
            alertas.append(f"{resultado['estoque_insuficiente']} ingrediente(s) com saldo insuficiente")
        if resultado["estoque_incompleto"]:
            alertas.append(f"{resultado['estoque_incompleto']} ingrediente(s) sem estoque/cadastro completo")
        texto = (f"{ficha['nome']}  ·  {ficha.get('categoria') or 'Sem categoria'}  ·  {int(ficha['porcoes']) if float(ficha['porcoes']).is_integer() else ficha['porcoes']} porção(ões)\n"
                 f"Custo total: {custo}  ·  Custo por porção: {_fmt_brl(resultado['custo_por_porcao'])}\n"
                 f"Descrição: {ficha.get('descricao') or '—'}")
        if alertas:
            texto += "\nAtenção: " + "; ".join(alertas)
        self.lbl_resumo.configure(text=texto)
        for iid in self.ingredientes_tree.get_children():
            self.ingredientes_tree.delete(iid)
        for item in resultado["linhas"]:
            status = "Sem vínculo"
            if item.get("id_produto_mobile") is not None:
                status = "Cadastro incompleto" if item.get("estoque_suficiente") is None else status
            if item.get("estoque_suficiente") is True:
                status = "Suficiente"
            elif item.get("estoque_suficiente") is False:
                status = "Insuficiente"
            self.ingredientes_tree.insert("", "end", values=(
                item["nome"], f"{_fmt_num(item['qtd_per_capita'])} {item['unidade']}",
                _fmt_num(item["fator_correcao"], 3), f"{_fmt_num(item['qtd_bruta_total'])} {item['unidade']}",
                _fmt_brl(item["custo_total"]), status))
        n = resultado["nutrientes_per_capita"]
        falt = resultado["nutrientes_faltantes"]
        resumo_n = ("Por porção — "
                    f"Energia: {_fmt_num(n['kcal'])} kcal; proteína: {_fmt_num(n['proteina'])} g; "
                    f"carboidratos: {_fmt_num(n['carboidrato'])} g; lipídios: {_fmt_num(n['lipidio'])} g. ")
        if any(falt[k] for k in ("kcal", "proteina", "carboidrato", "lipidio")):
            resumo_n += "Há ingrediente(s) sem composição ou conversão de unidade; valores exibidos são parciais e não substituem conferência."
        else:
            resumo_n += "Composição calculada a partir da TBCA importada."
        self.lbl_nutrientes.configure(text=resumo_n)

    def nova_ficha(self):
        FichaDialog(self, None, self.carregar_fichas)

    def editar_ficha(self):
        if not self._ficha_selecionada:
            messagebox.showinfo("Gestão alimentar", "Selecione uma ficha para editar.")
            return
        ficha = ga.obter_ficha(self.db, self._ficha_selecionada)
        if ficha:
            FichaDialog(self, ficha, self.carregar_fichas)

    def inativar_ficha(self):
        if not self._ficha_selecionada:
            messagebox.showinfo("Gestão alimentar", "Selecione uma ficha para inativar.")
            return
        ficha = ga.obter_ficha(self.db, self._ficha_selecionada)
        if not ficha:
            return
        if messagebox.askyesno("Inativar ficha", f"Inativar ‘{ficha['nome']}’? Ela deixará de aparecer na lista, mas seus dados serão mantidos."):
            ga.inativar_ficha(self.db, self._ficha_selecionada)
            self._ficha_selecionada = None
            self.carregar_fichas()

    # ------------------------------------------------------------ almoxarifado
    def sincronizar(self, silencioso=False):
        try:
            self.mobile_db = im.caminho_mobile_db(self.db, self.base_dir)
            linhas = im.ler_produtos_almox(self.mobile_db)
            qtd = ga.sincronizar_produtos_almox(self.db, linhas)
            self.lbl_status.configure(text=f"Almoxarifado sincronizado: {qtd} produto(s) · banco mobile: {self.mobile_db}")
            self.carregar_produtos()
            if self._ficha_selecionada:
                self._mostrar_detalhes(self._ficha_selecionada)
            return qtd
        except Exception as exc:
            mensagem = f"Não foi possível ler o Almoxarifado mobile. Confira se o servidor/banco está inicializado.\n\n{exc}"
            if self.lbl_status:
                self.lbl_status.configure(text="Almoxarifado não sincronizado. Consulte a aba Almoxarifado.")
            if not silencioso:
                messagebox.showwarning("Sincronização do Almoxarifado", mensagem)
            return 0

    def carregar_produtos(self):
        if not self.produtos_tree:
            return
        for iid in self.produtos_tree.get_children():
            self.produtos_tree.delete(iid)
        for item in ga.listar_produtos_almox(self.db):
            conteudo = "—"
            if item.get("embalagem_qtd") is not None and item.get("embalagem_un"):
                conteudo = f"{_fmt_num(item['embalagem_qtd'])} {item['embalagem_un']}"
            self.produtos_tree.insert("", "end", values=(item["nome"], item.get("unidade_estoque") or "—",
                _fmt_brl(item.get("preco_unitario")), conteudo,
                _fmt_num(item.get("estoque_qtd")), item.get("estoque_data") or "—"))

    # ------------------------------------------------------------------- TBCA
    def carregar_tbca_count(self):
        total = ga.contar_alimentos(self.db)
        self.lbl_tbca_count.configure(text=f"Alimentos na base: {total:,}".replace(",", "."))

    def importar_tbca(self):
        caminho = filedialog.askopenfilename(title="Selecione a planilha TBCA 2024",
            filetypes=[("Planilhas Excel", "*.xlsx"), ("Todos os arquivos", "*.*")])
        if not caminho:
            return
        try:
            total = ga.importar_tbca_excel(self.db, caminho)
            self.carregar_tbca_count()
            self.buscar_tbca()
            messagebox.showinfo("Importação TBCA", f"{total} alimento(s) importado(s)/atualizado(s) com sucesso.")
        except Exception as exc:
            messagebox.showerror("Importação TBCA", str(exc))

    def buscar_tbca(self):
        if not self.tbca_tree:
            return
        termo = self.var_busca_tbca.get().strip()
        rows = ga.listar_alimentos(self.db, termo=termo, limite=250)
        for iid in self.tbca_tree.get_children():
            self.tbca_tree.delete(iid)
        for item in rows:
            self.tbca_tree.insert("", "end", values=(item["id_tbca"], item["alimento"],
                _fmt_num(item.get("kcal")), _fmt_num(item.get("proteina")),
                _fmt_num(item.get("carboidrato")), _fmt_num(item.get("lipidio"))))


class FichaDialog:
    """Editor de preparação com linhas de ingrediente e vínculo opcional à TBCA/Almoxarifado."""

    def __init__(self, tela: GestaoAlimentarUI, ficha, ao_salvar):
        self.tela, self.ao_salvar, self.ficha = tela, ao_salvar, ficha
        self.janela = ctk.CTkToplevel(tela.app)
        self.janela.title("Editar ficha técnica" if ficha else "Nova ficha técnica")
        self.janela.geometry("1160x720")
        self.janela.minsize(980, 620)
        self.janela.transient(tela.app)
        self.janela.grab_set()
        self.rows = []
        self.produtos = ga.listar_produtos_almox(tela.db)
        self.tbca = ga.listar_alimentos(tela.db, limite=500)
        self._montar()
        self._preencher()

    def _montar(self):
        area = self.janela
        ctk.CTkLabel(area, text="Dados da preparação", font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=VERDE_ESC).pack(anchor="w", padx=16, pady=(12, 4))
        cab = ctk.CTkFrame(area, fg_color="transparent")
        cab.pack(fill="x", padx=14)
        cab.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(cab, text="Nome *").grid(row=0, column=0, sticky="w", padx=3, pady=4)
        self.nome = ctk.CTkEntry(cab, width=330, placeholder_text="Nome da preparação")
        self.nome.grid(row=0, column=1, sticky="ew", padx=3, pady=4)
        ctk.CTkLabel(cab, text="Categoria").grid(row=0, column=2, sticky="w", padx=3, pady=4)
        self.categoria = ctk.CTkComboBox(cab, values=CATEGORIAS, width=180)
        self.categoria.grid(row=0, column=3, sticky="w", padx=3, pady=4)
        ctk.CTkLabel(cab, text="Porções *").grid(row=0, column=4, sticky="w", padx=3, pady=4)
        self.porcoes = ctk.CTkEntry(cab, width=75)
        self.porcoes.grid(row=0, column=5, sticky="w", padx=3, pady=4)
        ctk.CTkLabel(area, text="Descrição / modo de preparo (opcional)", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=17, pady=(5, 0))
        self.descricao = ctk.CTkTextbox(area, height=52)
        self.descricao.pack(fill="x", padx=16, pady=(2, 5))
        barra = ctk.CTkFrame(area, fg_color="transparent")
        barra.pack(fill="x", padx=16, pady=(4, 2))
        ctk.CTkLabel(barra, text="Ingredientes", font=ctk.CTkFont(size=15, weight="bold"), text_color=VERDE_ESC).pack(side="left")
        _btn(barra, "＋ Adicionar ingrediente", self.adicionar_linha, 175).pack(side="right")
        ctk.CTkLabel(area, text="Nome · qtd. per capita · unidade · FC · medida caseira · ID TBCA · NPU · densidade (g/ml) · produto do Almoxarifado",
                     text_color="#546e7a", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=17, pady=(0, 2))
        self.scroll = ctk.CTkScrollableFrame(area, fg_color="#f4f7f5")
        self.scroll.pack(fill="both", expand=True, padx=15, pady=4)
        rodape = ctk.CTkFrame(area, fg_color="transparent")
        rodape.pack(fill="x", padx=15, pady=(4, 12))
        ctk.CTkLabel(rodape, text="* Campos obrigatórios. Volume só será convertido em gramas para os nutrientes com densidade informada.",
                     text_color="#546e7a", font=ctk.CTkFont(size=10), wraplength=700).pack(side="left")
        _btn(rodape, "Cancelar", self.janela.destroy, 100, cor=CINZA, hover="#455a64").pack(side="right", padx=(5, 0))
        _btn(rodape, "Salvar ficha", self.salvar, 120).pack(side="right")

    def _preencher(self):
        if self.ficha:
            self.nome.insert(0, self.ficha["nome"])
            self.categoria.set(self.ficha.get("categoria") or "")
            self.porcoes.insert(0, str(self.ficha["porcoes"]))
            self.descricao.insert("1.0", self.ficha.get("descricao") or "")
            for item in self.ficha["ingredientes"]:
                self.adicionar_linha(item)
        else:
            self.categoria.set(CATEGORIAS[0])
            self.porcoes.insert(0, "1")
            self.adicionar_linha()

    def adicionar_linha(self, item=None):
        linha = ctk.CTkFrame(self.scroll, fg_color="white", corner_radius=6)
        linha.pack(fill="x", padx=2, pady=3)
        campos = {}
        nome = ctk.CTkEntry(linha, width=185, placeholder_text="Ingrediente *")
        nome.pack(side="left", padx=(5, 2), pady=6)
        qtd = ctk.CTkEntry(linha, width=75, placeholder_text="Qtd *")
        qtd.pack(side="left", padx=2, pady=6)
        unidade = ctk.CTkComboBox(linha, width=65, values=UNIDADES)
        unidade.set("g")
        unidade.pack(side="left", padx=2, pady=6)
        fc = ctk.CTkEntry(linha, width=60, placeholder_text="FC")
        fc.insert(0, "1")
        fc.pack(side="left", padx=2, pady=6)
        medida = ctk.CTkEntry(linha, width=115, placeholder_text="Medida caseira")
        medida.pack(side="left", padx=2, pady=6)
        tbca = ctk.CTkEntry(linha, width=78, placeholder_text="ID TBCA")
        tbca.pack(side="left", padx=2, pady=6)
        npu = ctk.CTkEntry(linha, width=55, placeholder_text="NPU")
        npu.pack(side="left", padx=2, pady=6)
        dens = ctk.CTkEntry(linha, width=65, placeholder_text="g/ml")
        dens.pack(side="left", padx=2, pady=6)
        opcoes = ["— sem vínculo —"] + [f"{p['id_mobile']} | {p['nome']}" for p in self.produtos]
        produto = ctk.CTkComboBox(linha, width=225, values=opcoes)
        produto.set(opcoes[0])
        produto.pack(side="left", padx=2, pady=6)
        remover = ctk.CTkButton(linha, text="×", width=28, height=28, fg_color="#b71c1c", hover_color="#8e0000",
                                command=lambda: self._remover_linha(registro))
        remover.pack(side="left", padx=4)
        registro = {"frame": linha, "nome": nome, "qtd": qtd, "unidade": unidade, "fc": fc,
                    "medida": medida, "tbca": tbca, "npu": npu, "dens": dens, "produto": produto}
        self.rows.append(registro)
        if item:
            nome.insert(0, item.get("nome") or "")
            qtd.insert(0, str(item.get("qtd_per_capita") or ""))
            unidade.set(item.get("unidade") or "g")
            fc.delete(0, "end"); fc.insert(0, str(item.get("fator_correcao") or 1))
            medida.insert(0, item.get("medida_caseira") or "")
            tbca.insert(0, str(item.get("tbca_id") or ""))
            npu.insert(0, str(item.get("npu") if item.get("npu") is not None else ""))
            dens.insert(0, str(item.get("densidade_g_ml") or ""))
            if item.get("id_produto_mobile") is not None:
                for op in opcoes[1:]:
                    if op.startswith(str(item["id_produto_mobile"]) + " |"):
                        produto.set(op)
                        break

    def _remover_linha(self, registro):
        registro["frame"].destroy()
        if registro in self.rows:
            self.rows.remove(registro)

    def salvar(self):
        ingredientes = []
        for linha in self.rows:
            produto_txt = linha["produto"].get()
            id_produto = None
            if produto_txt != "— sem vínculo —" and " | " in produto_txt:
                try:
                    id_produto = int(produto_txt.split(" | ", 1)[0])
                except ValueError:
                    id_produto = None
            ingredientes.append({
                "nome": linha["nome"].get().strip(), "qtd_per_capita": linha["qtd"].get(),
                "unidade": linha["unidade"].get(), "fator_correcao": linha["fc"].get() or 1,
                "medida_caseira": linha["medida"].get().strip() or None,
                "tbca_id": linha["tbca"].get().strip() or None,
                "npu": linha["npu"].get().strip() or None,
                "densidade_g_ml": linha["dens"].get().strip() or None,
                "id_produto_mobile": id_produto,
            })
        try:
            ga.salvar_ficha(self.tela.db, self.nome.get(), self.categoria.get(), self.porcoes.get(), ingredientes,
                            descricao=self.descricao.get("1.0", "end").strip(),
                            id_ficha=self.ficha["id_ficha"] if self.ficha else None)
        except Exception as exc:
            messagebox.showerror("Ficha técnica", str(exc), parent=self.janela)
            return
        self.janela.destroy()
        self.ao_salvar()
