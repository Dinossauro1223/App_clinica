# -*- coding: utf-8 -*-
"""Interface desktop da Gestão alimentar (Fichas técnicas)."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

import gestao_alimentar_db as ga
import integracao_mobile as im
import ui_workers
import tema

VERDE_ESC = tema.VERDE_ESC
VERDE = tema.VERDE
VERDE_HOVER = tema.VERDE_HOVER
LARANJA = tema.LARANJA
CINZA = tema.SUAVE
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
    try:
        tema.aplicar_tema_ttk(frame.winfo_toplevel())
    except Exception:
        pass
    tree = ttk.Treeview(frame, columns=cols, show="headings", height=altura,
                        selectmode="browse", style="Treeview")
    tree.tag_configure("linha_par", background=tema.cor_atual(tema.FUNDO),
                       foreground=tema.cor_atual(tema.TEXTO))
    tree.tag_configure("linha_impar", background=tema.cor_atual(tema.BRANCO),
                       foreground=tema.cor_atual(tema.TEXTO))
    for key, titulo, largura, ancora in definicoes:
        tree.heading(key, text=titulo)
        tree.column(key, width=largura, minwidth=max(48, min(largura, 72)), anchor=ancora, stretch=True)
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return frame, tree


class _PainelJanela(ctk.CTkFrame):
    """Container compatível com diálogos antigos, agora hospedado em uma guia lateral."""

    def __init__(self, app, titulo):
        self.app = app
        self._painel_externo = bool(app and hasattr(app, "abrir_painel_lateral"))
        if self._painel_externo:
            abrir = getattr(app, "abrir_painel_modal", app.abrir_painel_lateral)
            self._painel_frame = abrir(titulo, lambda: None)
            pai = self._painel_frame
        else:
            self._painel_frame = None
            pai = getattr(app, "area_principal", app)
        super().__init__(pai, fg_color="transparent")
        self.pack(fill="both", expand=True)

    def title(self, *_args): return None
    def geometry(self, *_args): return None
    def minsize(self, *_args): return None
    def transient(self, *_args): return None
    def grab_set(self): return None
    def protocol(self, *_args): return None
    def resizable(self, *_args): return None
    def attributes(self, *_args, **_kwargs): return None

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
        self._movimentos_cache = {}
        self.tree_movimentos = None
        self.tree_medias_consumo = None
        self.tree_preparacoes_consumo = None
        self.lbl_consumo_status = None
        self._sincronizando = False
        self._importando_tbca = False
        self._importando_retiradas = False
        ga.inicializar(self.db)

    def mostrar(self):
        self.app.limpar_area_principal()
        area = self.app.area_principal
        topo = ctk.CTkFrame(area, fg_color="transparent")
        topo.pack(fill="x", padx=18, pady=(12, 2))
        ctk.CTkLabel(topo, text="Gestão alimentar — Fichas técnicas", font=ctk.CTkFont(size=23, weight="bold"),
                     text_color=VERDE_ESC).pack(side="left")
        _btn(topo, "Sincronizar Almoxarifado", self.sincronizar, 190, cor=CINZA, hover=tema.SUAVE).pack(side="right")
        self.lbl_status = ctk.CTkLabel(area, text="Produtos do Almoxarifado ainda não sincronizados nesta sessão.",
                                       text_color=tema.SUAVE, font=ctk.CTkFont(size=11), anchor="w")
        self.lbl_status.pack(fill="x", padx=20, pady=(0, 5))

        self.tabs = ctk.CTkTabview(area, segmented_button_selected_color=VERDE,
                                  segmented_button_selected_hover_color=VERDE_HOVER,
                                  segmented_button_unselected_color=tema.SUAVE,
                                  segmented_button_unselected_hover_color=tema.SUAVE)
        self.tabs.pack(fill="both", expand=True, padx=14, pady=(2, 12))
        self.tab_fichas = self.tabs.add("Fichas técnicas")
        self.tab_almox = self.tabs.add("Almoxarifado")
        self.tab_tbca = self.tabs.add("Base TBCA")
        self.tab_consumo = self.tabs.add("Consumo observado")
        self._montar_tab_fichas()
        self._montar_tab_almox()
        self._montar_tab_tbca()
        self._montar_tab_consumo()
        self.carregar_fichas()
        self.carregar_produtos()
        self.carregar_tbca_count()
        # Tenta sincronizar automaticamente; falha de conexão não impede o uso da ficha.
        self.sincronizar(silencioso=True)

    def _montar_tab_fichas(self):
        barra = ctk.CTkFrame(self.tab_fichas, fg_color="transparent")
        barra.pack(fill="x", padx=8, pady=(6, 4))
        _btn(barra, "＋ Nova ficha", self.nova_ficha, 125).pack(side="left")
        _btn(barra, "Editar selecionada", self.editar_ficha, 150, cor=CINZA, hover=tema.SUAVE).pack(side="left", padx=6)
        _btn(barra, "Inativar", self.inativar_ficha, 95, cor=LARANJA, hover=tema.LARANJA).pack(side="left")
        ctk.CTkLabel(barra, text="Selecione uma ficha para ver cálculo, custo e estoque.",
                     font=ctk.CTkFont(size=11), text_color=tema.SUAVE).pack(side="left", padx=12)

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
                                       wraplength=720, font=ctk.CTkFont(size=12), text_color=tema.TEXTO)
        self.lbl_resumo.pack(fill="x", padx=10, pady=(2, 8))
        frame, self.ingredientes_tree = _tree(direita, [
            ("nome", "Ingrediente", 185, "w"), ("qtd", "Per capita", 95, "e"),
            ("fc", "FC", 55, "center"), ("bruto", "Bruto total", 105, "e"),
            ("custo", "Custo total", 100, "e"), ("estoque", "Estoque", 100, "center")], altura=13)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.lbl_nutrientes = ctk.CTkLabel(direita, text="", anchor="w", justify="left", wraplength=720,
                                          font=ctk.CTkFont(size=11), text_color=tema.SUAVE)
        self.lbl_nutrientes.pack(fill="x", padx=10, pady=(0, 10))

    def _montar_tab_almox(self):
        topo = ctk.CTkFrame(self.tab_almox, fg_color="transparent")
        topo.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(topo, text="Itens recebidos do estoque Almoxarifado no mobile",
                     font=ctk.CTkFont(size=14, weight="bold"), text_color=VERDE_ESC).pack(side="left")
        _btn(topo, "Atualizar agora", self.sincronizar, 125, cor=CINZA, hover=tema.SUAVE).pack(side="right")
        _btn(topo, "Editar / vincular TBCA", lambda: self._editar_produto_almox(False), 175, cor=tema.AZUL).pack(side="right", padx=5)
        _btn(topo, "＋ Novo produto", lambda: self._editar_produto_almox(True), 135).pack(side="right", padx=5)
        _btn(topo, "Pedidos de reposição", self._abrir_pedidos_almox, 155, cor=CINZA, hover=tema.SUAVE).pack(side="right", padx=5)
        _btn(topo, "Prazo médio", self._abrir_prazos_almox, 115, cor=CINZA, hover=tema.SUAVE).pack(side="right", padx=5)
        ctk.CTkLabel(self.tab_almox,
                     text="O saldo é lido do mobile. Preço unitário refere-se à unidade de estoque cadastrada; conteúdo da embalagem informa quantos g/ml/un essa unidade contém.",
                     font=ctk.CTkFont(size=11), text_color=tema.SUAVE, anchor="w", justify="left", wraplength=900).pack(fill="x", padx=10, pady=4)
        frame, self.produtos_tree = _tree(self.tab_almox, [
            ("nome", "Produto", 190, "w"), ("un", "Un. estoque", 85, "center"),
            ("preco", "Preço unitário", 105, "e"), ("emb", "Conteúdo/unidade", 115, "e"),
            ("saldo", "Qtd. em estoque", 105, "e"), ("data", "Data do saldo", 110, "center"),
            ("tbca", "Alimento TBCA vinculado", 250, "w")], altura=18)
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
        busca.bind("<KeyRelease>", lambda _e: self.buscar_tbca())
        _btn(topo, "Buscar", self.buscar_tbca, 85, cor=CINZA, hover=tema.SUAVE).pack(side="right")
        ctk.CTkLabel(self.tab_tbca,
                     text="Importa a aba ‘TBCA (2024)’ do arquivo de referência. As demais abas de fórmulas da planilha não são executadas pelo aplicativo; a ficha aplica seus próprios cálculos validados.",
                     font=ctk.CTkFont(size=11), text_color=tema.SUAVE, anchor="w", justify="left", wraplength=930).pack(fill="x", padx=10, pady=3)
        frame, self.tbca_tree = _tree(self.tab_tbca, [
            ("id", "ID", 90, "center"), ("alimento", "Alimento", 330, "w"),
            ("kcal", "kcal/100g", 90, "e"), ("proteina", "Proteína/100g", 110, "e"),
            ("carbo", "Carboidrato/100g", 120, "e"), ("lipidio", "Lipídio/100g", 100, "e")], altura=18)
        self.tbca_tree.configure(selectmode="extended")
        self.tbca_tree.tag_configure("tbca_par", background=tema.cor_atual(tema.FUNDO),
                                     foreground=tema.cor_atual(tema.TEXTO))
        self.tbca_tree.tag_configure("tbca_impar", background=tema.cor_atual(tema.BRANCO),
                                     foreground=tema.cor_atual(tema.TEXTO))
        frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.buscar_tbca()

    # --------------------------------------------------------------- fichas
    def carregar_fichas(self):
        for iid in self.fichas_tree.get_children():
            self.fichas_tree.delete(iid)
        for indice, ficha in enumerate(ga.listar_fichas(self.db)):
            iid = str(ficha["id_ficha"])
            self.fichas_tree.insert(
                "", "end", iid=iid, values=(ficha["nome"], _fmt_num(ficha["porcoes"], 0)),
                tags=("linha_par" if indice % 2 == 0 else "linha_impar",)
            )
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
        for indice, item in enumerate(resultado["linhas"]):
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
                _fmt_brl(item["custo_total"]), status),
                tags=("linha_par" if indice % 2 == 0 else "linha_impar",))
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
        """Sincroniza o catálogo fora da thread gráfica para não congelar a interface."""
        if self._sincronizando:
            return None
        self._sincronizando = True
        if self.lbl_status:
            self.lbl_status.configure(text="Sincronizando Almoxarifado…")
        def trabalho():
            mobile_db = im.caminho_mobile_db(self.db, self.base_dir)
            linhas = im.ler_produtos_almox(mobile_db)
            qtd = ga.sincronizar_produtos_almox(self.db, linhas)
            return mobile_db, qtd
        def sucesso(resultado):
            if not self._widgets_disponiveis():
                return
            self.mobile_db, qtd = resultado
            self.lbl_status.configure(text=f"Almoxarifado sincronizado: {qtd} produto(s) · banco mobile: {self.mobile_db}")
            self.carregar_produtos()
            if self._ficha_selecionada:
                self._mostrar_detalhes(self._ficha_selecionada)
        def erro(exc):
            if not self._widgets_disponiveis():
                return
            self.lbl_status.configure(text="Almoxarifado não sincronizado. Consulte a aba Almoxarifado.")
            if not silencioso:
                mensagem = ("Não foi possível ler o Almoxarifado mobile. Confira se o servidor/banco está inicializado.\n\n"
                            + str(exc))
                messagebox.showwarning("Sincronização do Almoxarifado", mensagem)
        def finalizar():
            self._sincronizando = False
        return ui_workers.executar_em_segundo_plano(
            self.app, trabalho, ao_sucesso=sucesso, ao_erro=erro, ao_finalizar=finalizar,
            nome="nutrilab-sincronizar-almoxarifado")

    def _widgets_disponiveis(self):
        try:
            return bool(self.lbl_status and self.lbl_status.winfo_exists())
        except Exception:
            return False


    def _editar_produto_almox(self, novo=False):
        selecionado = self.produtos_tree.selection() if self.produtos_tree else ()
        if not novo and not selecionado:
            messagebox.showinfo("Almoxarifado", "Selecione um produto para editar ou vincular à TBCA.")
            return
        id_item = None if novo else int(selecionado[0])
        item = None if novo else next((p for p in ga.listar_produtos_almox(self.db) if int(p["id_mobile"]) == id_item), None)
        if not novo and not item:
            messagebox.showwarning("Almoxarifado", "Produto não encontrado. Sincronize o catálogo e tente novamente.")
            return
        janela = _PainelJanela(self.app, "Cadastrar produto do Almoxarifado" if novo else "Editar produto e vínculo TBCA")
        janela.title("Cadastrar produto do Almoxarifado" if novo else "Editar produto e vínculo TBCA")
        janela.geometry("760x600")
        janela.minsize(650, 520)
        janela.transient(self.app)
        janela.grab_set()
        ctk.CTkLabel(janela, text="Catálogo compartilhado com o mobile",
                     font=ctk.CTkFont(size=18, weight="bold"), text_color=VERDE_ESC).pack(
                         anchor="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(janela,
                     text="O conteúdo da embalagem (g/mL/un) é diferente da quantidade de embalagens em estoque. O vínculo TBCA será reutilizado ao montar fichas técnicas.",
                     font=ctk.CTkFont(size=11), text_color=tema.SUAVE, wraplength=700,
                     justify="left").pack(anchor="w", padx=20, pady=(0, 10))
        form = ctk.CTkFrame(janela, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=18)
        form.grid_columnconfigure(1, weight=1)
        def campo(rotulo, linha, valor="", placeholder=""):
            ctk.CTkLabel(form, text=rotulo).grid(row=linha, column=0, sticky="w", padx=4, pady=6)
            entrada = ctk.CTkEntry(form, placeholder_text=placeholder)
            entrada.grid(row=linha, column=1, sticky="ew", padx=4, pady=6)
            if valor not in (None, ""):
                entrada.insert(0, str(valor))
            return entrada
        nome = campo("Nome do produto *", 0, item.get("nome") if item else "", "Ex.: Leite integral")
        unidade = campo("Unidade de estoque *", 1, item.get("unidade_estoque") if item else "pacote", "Ex.: pacote, frasco, lata")
        preco = campo("Preço por unidade de estoque (R$)", 2, item.get("preco_unitario") if item else "", "Ex.: 8,50")
        conteudo = campo("Conteúdo de cada embalagem", 3, item.get("embalagem_qtd") if item else "", "Ex.: 500")
        ctk.CTkLabel(form, text="Unidade do conteúdo").grid(row=4, column=0, sticky="w", padx=4, pady=6)
        unidade_var = ctk.StringVar(value=(item.get("embalagem_un") if item else None) or "g")
        seg = ctk.CTkSegmentedButton(form, values=["g", "mL", "un"], variable=unidade_var)
        seg.grid(row=4, column=1, sticky="w", padx=4, pady=6)
        saldo = campo("Saldo do almoxarifado (embalagens)", 5, "", "Deixe vazio para não alterar o saldo")
        alimentos = ga.listar_alimentos(self.db, limite=10000)
        rotulos = ["— sem vínculo com a TBCA —"] + [f"{a['id_tbca']} | {a['alimento']}" for a in alimentos]
        por_id = {str(a["id_tbca"]): a for a in alimentos}
        ctk.CTkLabel(form, text="Alimento da TBCA").grid(row=6, column=0, sticky="w", padx=4, pady=6)
        tbca = ctk.CTkComboBox(form, values=rotulos, width=480)
        tbca.grid(row=6, column=1, sticky="ew", padx=4, pady=6)
        tbca.set("— sem vínculo com a TBCA —")
        if item and item.get("tbca_id"):
            alimento = por_id.get(str(item["tbca_id"]))
            if alimento:
                tbca.set(f"{alimento['id_tbca']} | {alimento['alimento']}")
        if not alimentos:
            tbca.configure(state="disabled")
            ctk.CTkLabel(form, text="Importe a base TBCA na aba Base TBCA para habilitar o vínculo.",
                         font=ctk.CTkFont(size=10), text_color=tema.SUAVE).grid(row=7, column=1, sticky="w", padx=4)
        if item:
            try:
                self.mobile_db = im.caminho_mobile_db(self.db, self.base_dir)
                prazo = im.prazo_medio_produto(self.mobile_db, id_item)
            except Exception:
                prazo = None
            if prazo:
                texto_prazo = "Prazo médio de recebimento: %.1f dia(s) corrido(s) · %d pedido(s) recebido(s) · %d pendente(s)" % (
                    prazo["prazo_medio_dias"] or 0, prazo["pedidos_recebidos"], prazo["pendentes"])
            else:
                texto_prazo = "Ainda não há histórico de pedidos e recebimentos para este insumo."
            ctk.CTkLabel(form, text=texto_prazo, font=ctk.CTkFont(size=11),
                         text_color=tema.SUAVE, wraplength=690, justify="left").grid(
                             row=7, column=0, columnspan=2, sticky="w", padx=4, pady=(8, 2))
        rodape = ctk.CTkFrame(janela, fg_color="transparent")
        rodape.pack(fill="x", padx=18, pady=14)
        def salvar():
            escolha = tbca.get().strip()
            tbca_id = None if not escolha or escolha.startswith("—") else escolha.split(" | ", 1)[0].strip()
            dados = {"nome": nome.get(), "unidade": unidade.get(), "preco_unitario": preco.get(),
                     "embalagem_qtd": conteudo.get(), "embalagem_un": unidade_var.get(), "tbca_id": tbca_id}
            try:
                self.mobile_db = im.caminho_mobile_db(self.db, self.base_dir)
                im.salvar_produto_almox(self.mobile_db, dados, id_item=id_item,
                                        estoque_inicial=saldo.get().strip() or None)
            except Exception as exc:
                messagebox.showwarning("Almoxarifado", str(exc))
                return
            janela.destroy()
            self.sincronizar(silencioso=True)
            self.lbl_status.configure(text="Produto salvo no catálogo compartilhado. Sincronizando o espelho da ficha técnica…")
        _btn(rodape, "Cancelar", janela.destroy, 100, cor=CINZA, hover=tema.SUAVE).pack(side="right", padx=4)
        if item:
            _btn(rodape, "＋ Pedido de reposição", lambda: self._novo_pedido_almox(id_item, janela),
                 165, cor=tema.AZUL, hover=tema.AZUL_HOVER).pack(side="left", padx=4)
        _btn(rodape, "Salvar produto", salvar, 140).pack(side="right", padx=4)


    def _mobile_db_path(self):
        self.mobile_db = im.caminho_mobile_db(self.db, self.base_dir)
        return self.mobile_db

    def _novo_pedido_almox(self, id_item, parent=None):
        produto = next((p for p in ga.listar_produtos_almox(self.db) if int(p["id_mobile"]) == int(id_item)), None)
        if not produto:
            messagebox.showwarning("Pedido de reposição", "Produto não encontrado.")
            return
        janela = _PainelJanela(self.app, "Registrar pedido de reposição")
        janela.title("Registrar pedido de reposição")
        janela.geometry("460x360")
        janela.transient(parent or self.app)
        janela.grab_set()
        ctk.CTkLabel(janela, text="Pedido de reposição",
                     font=ctk.CTkFont(size=17, weight="bold"), text_color=VERDE_ESC).pack(
                         anchor="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(janela, text=produto["nome"], font=ctk.CTkFont(size=13, weight="bold")).pack(
            anchor="w", padx=18, pady=(0, 12))
        ctk.CTkLabel(janela, text="Quantidade de embalagens/unidades solicitadas").pack(anchor="w", padx=18)
        qtd = ctk.CTkEntry(janela, placeholder_text="Ex.: 20")
        qtd.pack(fill="x", padx=18, pady=(4, 10))
        ctk.CTkLabel(janela, text="Fornecedor (opcional)").pack(anchor="w", padx=18)
        fornecedor = ctk.CTkEntry(janela, placeholder_text="Nome do fornecedor")
        fornecedor.pack(fill="x", padx=18, pady=(4, 10))
        ctk.CTkLabel(janela, text="Observação (opcional)").pack(anchor="w", padx=18)
        obs = ctk.CTkEntry(janela, placeholder_text="Prazo informado, número do pedido…")
        obs.pack(fill="x", padx=18, pady=(4, 12))
        def salvar_pedido():
            try:
                im.criar_pedido_almox(self._mobile_db_path(), id_item, qtd.get(),
                                      fornecedor.get(), obs.get(), getpass.getuser())
            except Exception as exc:
                messagebox.showwarning("Pedido de reposição", str(exc), parent=janela)
                return
            janela.destroy()
            messagebox.showinfo("Pedido registrado",
                                "O pedido foi registrado. Quando o material chegar, marque o recebimento para calcular o prazo e atualizar o estoque.",
                                parent=parent or self.app)
            self._abrir_pedidos_almox()
        rodape = ctk.CTkFrame(janela, fg_color="transparent")
        rodape.pack(fill="x", padx=18, pady=12)
        _btn(rodape, "Cancelar", janela.destroy, 100, cor=CINZA, hover=tema.SUAVE).pack(side="right", padx=4)
        _btn(rodape, "Registrar pedido", salvar_pedido, 140).pack(side="right", padx=4)

    def _abrir_pedidos_almox(self):
        try:
            pedidos = im.listar_pedidos_almox(self._mobile_db_path(), apenas_pendentes=True)
        except Exception as exc:
            messagebox.showwarning("Pedidos de reposição", str(exc))
            return
        janela = _PainelJanela(self.app, "Pedidos de reposição pendentes")
        janela.title("Pedidos de reposição pendentes")
        janela.geometry("820x500")
        ctk.CTkLabel(janela, text="Pedidos aguardando recebimento",
                     font=ctk.CTkFont(size=18, weight="bold"), text_color=VERDE_ESC).pack(
                         anchor="w", padx=18, pady=(16, 8))
        frame, arvore = _tree(janela, [
            ("item", "Insumo", 220, "w"), ("qtd", "Quantidade", 100, "e"),
            ("data", "Solicitado em", 150, "center"), ("por", "Solicitado por", 130, "w"),
            ("forn", "Fornecedor", 150, "w")], altura=12)
        frame.pack(fill="both", expand=True, padx=14, pady=8)
        for pedido in pedidos:
            arvore.insert("", "end", iid=str(pedido["id"]), values=(
                pedido["item"], _fmt_num(pedido["qtd"]), pedido["solicitado_em"],
                pedido["solicitado_nome"] or "—", pedido["fornecedor"] or "—"))
        def receber():
            sel = arvore.selection()
            if not sel:
                messagebox.showinfo("Recebimento", "Selecione um pedido pendente.", parent=janela)
                return
            pedido_id = int(sel[0])
            if not messagebox.askyesno("Confirmar recebimento",
                                       "Confirmar a chegada do pedido? A quantidade será adicionada ao estoque do almoxarifado.",
                                       parent=janela):
                return
            try:
                im.receber_pedido_almox(self._mobile_db_path(), pedido_id, getpass.getuser())
            except Exception as exc:
                messagebox.showwarning("Recebimento", str(exc), parent=janela)
                return
            janela.destroy()
            self.sincronizar(silencioso=True)
            messagebox.showinfo("Recebimento registrado",
                                "A entrada foi registrada no estoque e o prazo de recebimento foi calculado.",
                                parent=self.app)
        rodape = ctk.CTkFrame(janela, fg_color="transparent")
        rodape.pack(fill="x", padx=14, pady=(0, 14))
        _btn(rodape, "Atualizar lista", lambda: (janela.destroy(), self._abrir_pedidos_almox()),
             130, cor=CINZA, hover=tema.SUAVE).pack(side="left")
        _btn(rodape, "Registrar recebimento", receber, 170).pack(side="right")

    def _abrir_prazos_almox(self):
        try:
            prazos = im.listar_prazos_almox(self._mobile_db_path())
        except Exception as exc:
            messagebox.showwarning("Prazo médio de reposição", str(exc))
            return
        janela = _PainelJanela(self.app, "Prazo médio de recebimento por insumo")
        janela.title("Prazo médio de recebimento por insumo")
        janela.geometry("760x540")
        ctk.CTkLabel(janela, text="Prazo médio de reposição",
                     font=ctk.CTkFont(size=19, weight="bold"), text_color=VERDE_ESC).pack(
                         anchor="w", padx=20, pady=(18, 4))
        ctk.CTkLabel(janela, text="Dias corridos entre o registro do pedido e a confirmação do recebimento. A média é calculada apenas com pedidos recebidos.",
                     font=ctk.CTkFont(size=11), text_color=tema.SUAVE, wraplength=700,
                     justify="left").pack(anchor="w", padx=20, pady=(0, 12))
        lista = ctk.CTkScrollableFrame(janela, fg_color="transparent")
        lista.pack(fill="both", expand=True, padx=16, pady=8)
        if not prazos:
            ctk.CTkLabel(lista, text="Ainda não há pedidos e recebimentos registrados.").pack(anchor="w", padx=8, pady=8)
            return
        maximo = max([float(p["prazo_medio_dias"] or 0) for p in prazos] + [1.0])
        for p in prazos:
            linha = ctk.CTkFrame(lista, corner_radius=10)
            linha.pack(fill="x", padx=4, pady=5)
            cab = ctk.CTkFrame(linha, fg_color="transparent")
            cab.pack(fill="x", padx=12, pady=(8, 2))
            ctk.CTkLabel(cab, text=p["nome"], font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
            prazo = p["prazo_medio_dias"]
            ctk.CTkLabel(cab, text=("%.1f dia(s)" % prazo) if prazo is not None else "Sem recebimentos",
                         text_color=VERDE_ESC, font=ctk.CTkFont(size=12, weight="bold")).pack(side="right")
            barra = ctk.CTkProgressBar(linha, height=9, progress_color=VERDE)
            barra.pack(fill="x", padx=12, pady=3)
            barra.set(float(prazo or 0) / maximo)
            ctk.CTkLabel(linha, text="%d pedido(s) recebido(s) · %d pendente(s)" %
                         (p["pedidos_recebidos"], p["pendentes"] or 0),
                         font=ctk.CTkFont(size=10), text_color=tema.SUAVE).pack(anchor="w", padx=12, pady=(0, 8))

    def carregar_produtos(self):
        if not self.produtos_tree:
            return
        for iid in self.produtos_tree.get_children():
            self.produtos_tree.delete(iid)
        for indice, item in enumerate(ga.listar_produtos_almox(self.db)):
            conteudo = "—"
            if item.get("embalagem_qtd") is not None and item.get("embalagem_un"):
                conteudo = f"{_fmt_num(item['embalagem_qtd'])} {item['embalagem_un']}"
            self.produtos_tree.insert("", "end", iid=str(item["id_mobile"]), values=(item["nome"], item.get("unidade_estoque") or "—",
                _fmt_brl(item.get("preco_unitario")), conteudo,
                _fmt_num(item.get("estoque_qtd")), item.get("estoque_data") or "—",
                item.get("tbca_alimento") or ("ID " + str(item["tbca_id"]) if item.get("tbca_id") else "—")),
                tags=("linha_par" if indice % 2 == 0 else "linha_impar",))


    # ------------------------------------------------------ consumo observado
    def _montar_tab_consumo(self):
        topo = ctk.CTkFrame(self.tab_consumo, fg_color="transparent")
        topo.pack(fill="x", padx=8, pady=(7, 4))
        hoje = __import__("datetime").date.today()
        inicio = hoje.replace(day=1).isoformat()
        self.e_consumo_inicio = ctk.CTkEntry(topo, width=115, placeholder_text="AAAA-MM-DD")
        self.e_consumo_inicio.pack(side="left", padx=3)
        self.e_consumo_inicio.insert(0, inicio)
        self.e_consumo_fim = ctk.CTkEntry(topo, width=115, placeholder_text="AAAA-MM-DD")
        self.e_consumo_fim.pack(side="left", padx=3)
        self.e_consumo_fim.insert(0, hoje.isoformat())
        _btn(topo, "Importar retiradas mobile", self.importar_retiradas, 170, cor=VERDE).pack(side="left", padx=4)
        _btn(topo, "Atualizar relatório", self.carregar_consumo, 135, cor=CINZA, hover=tema.SUAVE).pack(side="left", padx=4)
        _btn(topo, "Preparações esperadas", self.abrir_preparacoes, 165, cor=CINZA, hover=tema.SUAVE).pack(side="left", padx=4)
        _btn(topo, "Gerar rascunhos por horário", self.gerar_rascunhos_por_horario, 205, cor=AZUL).pack(side="left", padx=4)
        self.lbl_consumo_status = ctk.CTkLabel(self.tab_consumo,
            text="Importe o histórico de retiradas Almoxarifado → Cozinha. Movimentos Cozinha → Copa não entram como novo consumo.",
            anchor="w", justify="left", text_color=tema.SUAVE, font=ctk.CTkFont(size=11))
        self.lbl_consumo_status.pack(fill="x", padx=12, pady=(0, 5))

        sub = ctk.CTkTabview(self.tab_consumo, segmented_button_selected_color=VERDE,
                            segmented_button_selected_hover_color=VERDE_HOVER,
                            segmented_button_unselected_color=tema.SUAVE,
                            segmented_button_unselected_hover_color=tema.SUAVE)
        sub.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        tab_mov = sub.add("Movimentações e destinações")
        tab_med = sub.add("Média por ingrediente")
        tab_prep = sub.add("Consumo por preparação")
        barra = ctk.CTkFrame(tab_mov, fg_color="transparent")
        barra.pack(fill="x", padx=6, pady=5)
        _btn(barra, "Distribuir retirada selecionada", self.alocar_retirada, 210).pack(side="left")
        defs = [("data","Data",90,"center"),("hora","Hora",65,"center"),("item","Ingrediente",180,"w"),
                ("qtd","Quantidade líquida",105,"e"),("devolvido","Devolvido",85,"e"),("alocado","Alocado",90,"e"),("pendente","Sem destino",95,"e"),
                ("preco","Preço/un.",90,"e"),("custo","Custo",95,"e"),("fonte","Preço",95,"center"),("observacao","Observação",220,"w")]
        frame,self.tree_movimentos = _tree(tab_mov,defs,altura=13)
        frame.pack(fill="both",expand=True,padx=6,pady=(0,6))
        self.tree_movimentos.bind("<Double-1>", lambda _e: self.alocar_retirada())

        frame,self.tree_medias_consumo = _tree(tab_med,[
            ("item","Ingrediente",190,"w"),("total","Retirada líquida",110,"e"),
            ("media","Média/dia calendário",125,"e"),("intervalo","Intervalo médio",110,"e"),
            ("alocado","Associado",90,"e"),("pendente","Pendente",90,"e"),
            ("custo","Custo líquido",105,"e")],altura=16)
        frame.pack(fill="both",expand=True,padx=6,pady=6)
        ctk.CTkLabel(tab_med,text="A média diária divide a retirada líquida (retiradas menos devoluções) pelos dias do período. O intervalo médio considera datas com movimentação; nenhum desses indicadores equivale sozinho ao consumo efetivo.",
                     text_color=tema.SUAVE,font=ctk.CTkFont(size=10),wraplength=850,justify="left").pack(anchor="w",padx=9,pady=(0,8))
        frame,self.tree_preparacoes_consumo = _tree(tab_prep,[
            ("refeicao","Refeição",90,"center"),("preparacao","Preparação",180,"w"),
            ("item","Ingrediente",175,"w"),("media","Média/execução",110,"e"),
            ("porcao","Quantidade/porção prevista",145,"e"),("execucoes","Execuções",75,"center"),
            ("custo","Custo observado",110,"e")],altura=16)
        frame.pack(fill="both",expand=True,padx=6,pady=6)
        ctk.CTkLabel(tab_prep,text="As quantidades associadas são observacionais. Porção média só aparece quando as porções previstas foram informadas em todas as execuções contabilizadas.",
                     text_color=tema.SUAVE,font=ctk.CTkFont(size=10),wraplength=850,justify="left").pack(anchor="w",padx=9,pady=(0,8))


    def gerar_rascunhos_por_horario(self):
        """Importa retiradas e sugere fichas quando horário + agenda identificam uma única preparação."""
        try:
            inicio, fim = self._periodo_consumo()
            self.mobile_db = im.caminho_mobile_db(self.db, self.base_dir)
            importacao = im.importar_movimentos_cozinha(self.db, self.mobile_db, inicio, fim)
            janelas = im.ler_janelas_refeicoes(self.mobile_db)
            primeiro = __import__("datetime").date.fromisoformat(inicio)
            ultimo = __import__("datetime").date.fromisoformat(fim)
            totais = {"alocadas": 0, "rascunhos": 0, "sem_horario": 0,
                      "horario_ambiguo": 0, "sem_preparacao": 0, "varias_preparacoes": 0,
                      "ja_alocadas": 0, "sem_porcoes": 0}
            erros = []
            dia = primeiro
            while dia <= ultimo:
                data = dia.isoformat()
                movimentos = ga.listar_movimentos_cozinha(self.db, data, data)
                resultado = ga.gerar_rascunhos_por_horario(self.db, data, movimentos, janelas)
                for chave in totais:
                    totais[chave] += int(resultado.get(chave, 0))
                erros.extend(resultado.get("erros", []))
                dia += __import__("datetime").timedelta(days=1)
            self.carregar_consumo()
            texto = (
                "Importação de movimentos: %s retirada(s) Almoxarifado → Cozinha.\n\n"
                "Alocações automáticas: %d\nRascunhos de fichas criados: %d\n"
                "Sem horário compatível: %d\nHorários sobrepostos: %d\n"
                "Sem preparação agendada: %d\nMais de uma preparação na refeição: %d\n"
                "Já alocadas/sem saldo pendente: %d\nPreparações sem porções: %d"
            ) % (importacao.get("retiradas_cozinha", 0), totais["alocadas"], totais["rascunhos"],
                 totais["sem_horario"], totais["horario_ambiguo"], totais["sem_preparacao"],
                 totais["varias_preparacoes"], totais["ja_alocadas"], totais["sem_porcoes"])
            if erros:
                texto += "\n\nOcorrências: " + " | ".join(erros[:4])
            texto += "\n\nAs fichas geradas estão marcadas como 'Rascunho automático'. Revise quantidades, unidades e vínculos TBCA antes de utilizá-las."
            messagebox.showinfo("Geração automática por horário", texto, parent=self.tab_consumo)
        except Exception as exc:
            messagebox.showerror("Geração automática por horário", str(exc), parent=self.tab_consumo)

    def _periodo_consumo(self):
        ini, fim = self.e_consumo_inicio.get().strip(), self.e_consumo_fim.get().strip()
        if not ini or not fim:
            raise ValueError("Informe as datas inicial e final.")
        return ini, fim

    def importar_retiradas(self):
        if self._importando_retiradas:
            return None
        try:
            inicio, fim = self._periodo_consumo()
            self.mobile_db = im.caminho_mobile_db(self.db, self.base_dir)
        except Exception as exc:
            messagebox.showerror("Importação de retiradas", str(exc), parent=self.tab_consumo)
            return None
        self._importando_retiradas = True
        if self.lbl_consumo_status:
            self.lbl_consumo_status.configure(text="Importando retiradas do Mobile…")
        def trabalho():
            return im.importar_movimentos_cozinha(self.db, self.mobile_db, inicio, fim)
        def sucesso(r):
            if not self._widgets_disponiveis():
                return
            self.carregar_consumo()
            if self.lbl_consumo_status:
                self.lbl_consumo_status.configure(
                    text=f"Importação concluída: {r['retiradas_cozinha']} retirada(s) Almoxarifado → Cozinha; {r['importados']} movimento(s) no total. Chave original preservada; repetir a importação não duplica registros."
                )
        def erro(exc):
            if not self._widgets_disponiveis():
                return
            messagebox.showerror("Importação de retiradas", str(exc), parent=self.tab_consumo)
            if self.lbl_consumo_status:
                self.lbl_consumo_status.configure(text="Não foi possível importar. Confira o servidor mobile e as datas informadas.")
        def finalizar():
            self._importando_retiradas = False
        return ui_workers.executar_em_segundo_plano(
            self.app, trabalho, ao_sucesso=sucesso, ao_erro=erro, ao_finalizar=finalizar,
            nome="nutrilab-importar-retiradas")

    def carregar_consumo(self):
        if not self.tree_movimentos:
            return None
        try:
            inicio, fim = self._periodo_consumo()
            movimentos = ga.listar_movimentos_cozinha(self.db, inicio, fim)
            resumo = ga.resumo_consumo_observado(self.db, inicio, fim)
            self._movimentos_cache = {(m["data"],int(m["id_mobile"])):m for m in movimentos}
            for tree in (self.tree_movimentos,self.tree_medias_consumo,self.tree_preparacoes_consumo):
                for iid in tree.get_children():
                    tree.delete(iid)
            for indice, m in enumerate(movimentos):
                fonte = {"historico":"Histórico","atual_estimado":"Atual*","pendente":"Sem preço"}.get(m.get("origem_preco"),"—")
                observacao = m.get("observacao") or "—"
                if float(m.get("qtd_devolvida_alocada") or 0) > 1e-8:
                    observacao += " · Devolução já alocada: revise a destinação"
                if float(m.get("devolucao_sobre_alocada") or 0) > 1e-8:
                    observacao += " · Devolução excede retiradas anteriores"
                self.tree_movimentos.insert("", "end", iid=f"{m['data']}|{m['id_mobile']}",
                    values=(m["data"],m["hora"],m["item"],
                            _fmt_num(m["qtd"]),_fmt_num(float(m.get("qtd_devolvida") or 0)+float(m.get("qtd_devolvida_alocada") or 0)),
                            _fmt_num(m["qtd_alocada"]),_fmt_num(m["qtd_disponivel_para_alocar"]),
                            _fmt_brl(m.get("preco_unitario_snapshot")),
                            _fmt_brl(m.get("custo_retirada")),fonte,observacao),
                    tags=("linha_par" if indice % 2 == 0 else "linha_impar",))
            for indice, item in enumerate(resumo["itens"]):
                intervalo = "—" if item["intervalo_medio_dias"] is None else _fmt_num(item["intervalo_medio_dias"],1)+" d"
                self.tree_medias_consumo.insert("", "end",
                    values=(item["item"],_fmt_num(item["total_retirado"]),_fmt_num(item["media_diaria_periodo"]),
                            intervalo,_fmt_num(item["total_alocado"]),_fmt_num(item["total_pendente"]),
                            _fmt_brl(item.get("custo_total"))),
                    tags=("linha_par" if indice % 2 == 0 else "linha_impar",))
            for indice, p in enumerate(resumo["por_preparacao"]):
                refeicao = p["refeicao"] or "—"
                self.tree_preparacoes_consumo.insert("", "end",
                    values=(refeicao,p["preparacao"],p["item"],_fmt_num(p["media_por_execucao"]),
                            _fmt_num(p["media_por_porcao_prevista"]),p["execucoes"],_fmt_brl(p.get("custo_total"))),
                    tags=("linha_par" if indice % 2 == 0 else "linha_impar",))
            pendentes = resumo["movimentos_pendentes"]
            self.lbl_consumo_status.configure(
                text=f"{resumo['movimentos']} movimentação(ões) no período · {pendentes} com quantidade ainda sem destinação. *Preço atual é apenas estimativa para movimentos antigos sem snapshot histórico."
            )
            return resumo
        except Exception as exc:
            messagebox.showerror("Consumo observado", str(exc), parent=self.tab_consumo)
            return None

    def abrir_preparacoes(self):
        try:
            _, data = self._periodo_consumo()
            PreparacoesDiaDialog(self.app,self.db,data,self.carregar_consumo)
        except Exception as exc:
            messagebox.showerror("Preparações esperadas",str(exc),parent=self.tab_consumo)

    def alocar_retirada(self):
        sel = self.tree_movimentos.selection() if self.tree_movimentos else ()
        if not sel:
            messagebox.showinfo("Destinação da retirada","Selecione uma retirada na tabela.",parent=self.tab_consumo)
            return
        chave = sel[0].split("|",1)
        mov = self._movimentos_cache.get((chave[0],int(chave[1])))
        if not mov:
            self.carregar_consumo()
            return
        if float(mov.get("qtd") or 0) <= 0:
            messagebox.showinfo("Devolução registrada","Este movimento é uma devolução ao almoxarifado e já foi descontado do total líquido. Não precisa ser destinado a uma preparação.",parent=self.tab_consumo)
            return
        AlocarRetiradaDialog(self.app,self.db,mov,self.carregar_consumo)

    # ------------------------------------------------------------------- TBCA
    def carregar_tbca_count(self):
        total = ga.contar_alimentos(self.db)
        self.lbl_tbca_count.configure(text=f"Alimentos na base: {total:,}".replace(",", "."))

    def importar_tbca(self):
        caminho = filedialog.askopenfilename(title="Selecione a planilha TBCA 2024",
            filetypes=[("Planilhas Excel", "*.xlsx"), ("Todos os arquivos", "*.*")])
        if not caminho or self._importando_tbca:
            return
        self._importando_tbca = True
        self.lbl_tbca_count.configure(text="Importando TBCA…")
        def trabalho():
            return ga.importar_tbca_excel(self.db, caminho)
        def sucesso(total):
            if not self._widgets_disponiveis():
                return
            self.carregar_tbca_count()
            self.buscar_tbca()
            messagebox.showinfo("Importação TBCA", f"{total} alimento(s) importado(s)/atualizado(s) com sucesso.")
        def erro(exc):
            if self._widgets_disponiveis():
                messagebox.showerror("Importação TBCA", str(exc))
        def finalizar():
            self._importando_tbca = False
        return ui_workers.executar_em_segundo_plano(
            self.app, trabalho, ao_sucesso=sucesso, ao_erro=erro, ao_finalizar=finalizar,
            nome="nutrilab-importar-tbca")

    def buscar_tbca(self):
        if not self.tbca_tree:
            return
        termo = self.var_busca_tbca.get().strip()
        rows = ga.listar_alimentos(self.db, termo=termo, limite=10000)
        self.tbca_tree.delete(*self.tbca_tree.get_children())
        encontrados = []
        for indice, item in enumerate(rows):
            iid = self.tbca_tree.insert("", "end",
                values=(item["id_tbca"], item["alimento"],
                    _fmt_num(item.get("kcal")), _fmt_num(item.get("proteina")),
                    _fmt_num(item.get("carboidrato")), _fmt_num(item.get("lipidio"))),
                tags=("tbca_par" if indice % 2 == 0 else "tbca_impar",))
            encontrados.append(iid)
        # Destaca simultaneamente todos os resultados do prefixo digitado para facilitar a conferência.
        if termo and encontrados:
            self.tbca_tree.selection_set(encontrados)
            self.tbca_tree.focus(encontrados[0])
            self.tbca_tree.see(encontrados[0])
        else:
            self.tbca_tree.selection_remove(self.tbca_tree.selection())


def _extrair_id_tbca(valor):
    """Aceita tanto o rótulo selecionado 'ID | nome' quanto um ID digitado manualmente."""
    texto = str(valor or "").strip()
    if not texto or texto.startswith("—"):
        return None
    return texto.split(" | ", 1)[0].strip() or None


class FichaDialog:
    """Editor de preparação com linhas de ingrediente e vínculo opcional à TBCA/Almoxarifado."""

    def __init__(self, tela: GestaoAlimentarUI, ficha, ao_salvar):
        self.tela, self.ao_salvar, self.ficha = tela, ao_salvar, ficha
        self.janela = _PainelJanela(tela.app, "Editar ficha técnica" if ficha else "Nova ficha técnica")
        self.janela.title("Editar ficha técnica" if ficha else "Nova ficha técnica")
        self.janela.geometry("1320x720")
        self.janela.minsize(1080, 620)
        self.janela.transient(tela.app)
        self.janela.grab_set()
        self.rows = []
        self.produtos = ga.listar_produtos_almox(tela.db)
        self.tbca = ga.listar_alimentos(tela.db, limite=10000)
        self._tbca_por_rotulo = {
            f"{item['id_tbca']} | {item['alimento']}": item for item in self.tbca
        }
        self._produtos_por_rotulo = {
            f"{item['id_mobile']} | {item['nome']}": item for item in self.produtos
        }
        self._opcoes_tbca = ["— selecionar alimento da TBCA —"] + list(self._tbca_por_rotulo)
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
        ctk.CTkLabel(area, text="Selecione o alimento da TBCA para preencher nome e referência nutricional. O vínculo com o Almoxarifado é separado e opcional: associa o ingrediente ao item do estoque e usa seu preço/estoque sincronizados.",
                     text_color=tema.SUAVE, font=ctk.CTkFont(size=10), wraplength=1250).pack(anchor="w", padx=17, pady=(0, 2))
        ctk.CTkLabel(area, text="Preço manual: R$ por unidade da medida escolhida (g, kg, ml, L ou un). Quando preenchido, prevalece sobre o preço do Almoxarifado.",
                     text_color=tema.SUAVE, font=ctk.CTkFont(size=10), wraplength=1250).pack(anchor="w", padx=17, pady=(0, 2))
        ctk.CTkLabel(area, text="Campos por ingrediente: nome · quantidade per capita · unidade · fator de correção · alimento TBCA · medida caseira · NPU · densidade · vínculo Almoxarifado.",
                     text_color=tema.SUAVE, font=ctk.CTkFont(size=10), wraplength=1100).pack(anchor="w", padx=17, pady=(0, 2))
        self.scroll = ctk.CTkScrollableFrame(area, fg_color=tema.FUNDO)
        self.scroll.pack(fill="both", expand=True, padx=15, pady=4)
        rodape = ctk.CTkFrame(area, fg_color="transparent")
        rodape.pack(fill="x", padx=15, pady=(4, 12))
        ctk.CTkLabel(rodape, text="* Campos obrigatórios. Volume só será convertido em gramas para os nutrientes com densidade informada.",
                     text_color=tema.SUAVE, font=ctk.CTkFont(size=10), wraplength=700).pack(side="left")
        _btn(rodape, "Cancelar", self.janela.destroy, 100, cor=CINZA, hover=tema.SUAVE).pack(side="right", padx=(5, 0))
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
        # Cada ingrediente ocupa um cartão com linhas próprias para identificação,
        # referência TBCA, parâmetros nutricionais e vínculo/custo do Almoxarifado.
        linha = ctk.CTkFrame(self.scroll, fg_color=tema.BRANCO, corner_radius=6)
        linha.pack(fill="x", padx=2, pady=4)

        linha_identificacao = ctk.CTkFrame(linha, fg_color="transparent")
        linha_identificacao.pack(fill="x", padx=6, pady=(6, 2))
        nome = ctk.CTkEntry(linha_identificacao, width=210, placeholder_text="Ingrediente *")
        nome.pack(side="left", padx=(0, 4), pady=3)
        qtd = ctk.CTkEntry(linha_identificacao, width=75, placeholder_text="Qtd *")
        qtd.pack(side="left", padx=3, pady=3)
        unidade = ctk.CTkComboBox(linha_identificacao, width=72, values=UNIDADES)
        unidade.set("g")
        unidade.pack(side="left", padx=3, pady=3)
        fc = ctk.CTkEntry(linha_identificacao, width=65, placeholder_text="FC")
        fc.insert(0, "1")
        fc.pack(side="left", padx=3, pady=3)

        linha_tbca = ctk.CTkFrame(linha, fg_color="transparent")
        linha_tbca.pack(fill="x", padx=6, pady=2)
        ctk.CTkLabel(linha_tbca, text="TBCA:", text_color=tema.SUAVE).pack(side="left", padx=(0, 4))
        tbca = ctk.CTkComboBox(
            linha_tbca, width=210, values=self._opcoes_tbca,
            command=lambda valor: self._selecionar_tbca(registro, valor)
        )
        tbca.set("— selecionar alimento da TBCA —")
        tbca.pack(side="left", padx=3, pady=3)
        ctk.CTkLabel(linha_tbca, text="Medida caseira:", text_color=tema.SUAVE).pack(side="left", padx=(8, 4))
        medida = ctk.CTkEntry(linha_tbca, width=120, placeholder_text="Ex.: 1 colher")
        medida.pack(side="left", padx=3, pady=3)

        linha_referencias = ctk.CTkFrame(linha, fg_color="transparent")
        linha_referencias.pack(fill="x", padx=6, pady=2)
        ctk.CTkLabel(linha_referencias, text="NPU:", text_color=tema.SUAVE).pack(side="left", padx=(0, 4))
        npu = ctk.CTkEntry(linha_referencias, width=75, placeholder_text="NPU")
        npu.pack(side="left", padx=3, pady=3)
        ctk.CTkLabel(linha_referencias, text="Densidade (g/mL):", text_color=tema.SUAVE).pack(side="left", padx=(8, 4))
        dens = ctk.CTkEntry(linha_referencias, width=95, placeholder_text="g/mL")
        dens.pack(side="left", padx=3, pady=3)

        linha_estoque = ctk.CTkFrame(linha, fg_color="transparent")
        linha_estoque.pack(fill="x", padx=6, pady=(2, 6))
        opcoes = ["— sem vínculo com Almoxarifado —"] + [f"{p['id_mobile']} | {p['nome']}" for p in self.produtos]
        ctk.CTkLabel(linha_estoque, text="Almoxarifado:", text_color=tema.SUAVE).pack(side="left", padx=(0, 4))
        produto = ctk.CTkComboBox(linha_estoque, width=170, values=opcoes,
                                  command=lambda valor: self._selecionar_produto(registro, valor))
        produto.set(opcoes[0])
        produto.pack(side="left", padx=3, pady=3)
        ctk.CTkLabel(linha_estoque, text="Preço manual (R$/unid.):", width=130,
                     font=ctk.CTkFont(size=11), text_color=tema.SUAVE).pack(side="left", padx=(8, 3))
        preco = ctk.CTkEntry(linha_estoque, width=90, placeholder_text="0,00")
        preco.pack(side="left", padx=3, pady=3)
        remover = ctk.CTkButton(
            linha_identificacao, text="×", width=28, height=28,
            fg_color=tema.ERRO_HOVER, hover_color=tema.ERRO_HOVER,
            command=lambda: self._remover_linha(registro)
        )
        remover.pack(side="left", padx=4)

        registro = {"frame": linha, "nome": nome, "qtd": qtd, "unidade": unidade, "fc": fc,
                    "medida": medida, "tbca": tbca, "npu": npu, "dens": dens,
                    "produto": produto, "preco": preco}
        self.rows.append(registro)
        if item:
            nome.insert(0, item.get("nome") or "")
            qtd.insert(0, str(item.get("qtd_per_capita") or ""))
            unidade.set(item.get("unidade") or "g")
            fc.delete(0, "end"); fc.insert(0, str(item.get("fator_correcao") or 1))
            medida.insert(0, item.get("medida_caseira") or "")
            if item.get("tbca_id"):
                rotulo_tbca = next(
                    (rotulo for rotulo, alimento in self._tbca_por_rotulo.items()
                     if str(alimento["id_tbca"]) == str(item["tbca_id"])),
                    None,
                )
                if rotulo_tbca:
                    tbca.set(rotulo_tbca)
            else:
                tbca.set("— selecionar alimento da TBCA —")
            npu.insert(0, str(item.get("npu") if item.get("npu") is not None else ""))
            dens.insert(0, str(item.get("densidade_g_ml") or ""))
            preco.insert(0, str(item.get("preco_unitario_manual") or ""))
            if item.get("id_produto_mobile") is not None:
                for op in opcoes[1:]:
                    if op.startswith(str(item["id_produto_mobile"]) + " |"):
                        produto.set(op)
                        break

    def _selecionar_tbca(self, registro, valor):
        """Vincula o nome escolhido ao ID TBCA e preenche referências da própria tabela."""
        alimento = self._tbca_por_rotulo.get(valor)
        if not alimento:
            return
        nome = registro["nome"]
        nome.delete(0, "end")
        nome.insert(0, alimento["alimento"])
        if alimento.get("fc_referencia") not in (None, 0):
            registro["fc"].delete(0, "end")
            registro["fc"].insert(0, str(alimento["fc_referencia"]))
        if alimento.get("medida_caseira"):
            registro["medida"].delete(0, "end")
            registro["medida"].insert(0, str(alimento["medida_caseira"]))
        if alimento.get("npu") is not None:
            registro["npu"].delete(0, "end")
            registro["npu"].insert(0, str(alimento["npu"]))


    def _selecionar_produto(self, registro, valor):
        """Ao escolher um insumo já vinculado, reaproveita automaticamente o alimento TBCA."""
        produto = self._produtos_por_rotulo.get(valor)
        if not produto or not produto.get("tbca_id"):
            return
        rotulo = next((r for r, a in self._tbca_por_rotulo.items()
                       if str(a["id_tbca"]) == str(produto["tbca_id"])), None)
        if rotulo and registro["tbca"].get() == "— selecionar alimento da TBCA —":
            registro["tbca"].set(rotulo)
            self._selecionar_tbca(registro, rotulo)

    def _remover_linha(self, registro):
        registro["frame"].destroy()
        if registro in self.rows:
            self.rows.remove(registro)

    def salvar(self):
        ingredientes = []
        for linha in self.rows:
            produto_txt = linha["produto"].get()
            id_produto = None
            if produto_txt != "— sem vínculo com Almoxarifado —" and " | " in produto_txt:
                try:
                    id_produto = int(produto_txt.split(" | ", 1)[0])
                except ValueError:
                    id_produto = None
            ingredientes.append({
                "nome": linha["nome"].get().strip(), "qtd_per_capita": linha["qtd"].get(),
                "unidade": linha["unidade"].get(), "fator_correcao": linha["fc"].get() or 1,
                "medida_caseira": linha["medida"].get().strip() or None,
                "tbca_id": _extrair_id_tbca(linha["tbca"].get()),
                "npu": linha["npu"].get().strip() or None,
                "densidade_g_ml": linha["dens"].get().strip() or None,
                "preco_unitario_manual": linha["preco"].get().strip() or None,
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


class PreparacoesDiaDialog:
    """Cadastro do cardápio esperado por dia/refeição, com vínculo opcional a uma ficha existente."""

    def __init__(self, app, db_path, data, ao_salvar):
        self.app,self.db,self.data,self.ao_salvar=app,db_path,data,ao_salvar
        self.janela=_PainelJanela(app, "Preparações esperadas — " + str(data))
        self.janela.title("Preparações esperadas — "+data)
        self.janela.geometry("820x570")
        self.janela.transient(app);self.janela.grab_set()
        self.rows=[]
        self.fichas=ga.listar_fichas(db_path)
        self._montar()
        self._carregar()

    def _montar(self):
        area=self.janela
        topo=ctk.CTkFrame(area,fg_color="transparent");topo.pack(fill="x",padx=14,pady=(12,5))
        ctk.CTkLabel(topo,text="Data").pack(side="left")
        self.e_data=ctk.CTkEntry(topo,width=115);self.e_data.pack(side="left",padx=5);self.e_data.insert(0,self.data)
        ctk.CTkLabel(topo,text="Refeição").pack(side="left",padx=(12,3))
        self.cb_ref=ctk.CTkComboBox(topo,width=150,values=["desjejum","colacao","almoco","lanche","jantar","ceia"])
        self.cb_ref.set("almoco");self.cb_ref.pack(side="left")
        _btn(topo,"Carregar",self._carregar,100,cor=CINZA,hover=tema.SUAVE).pack(side="left",padx=6)
        bloco=ctk.CTkFrame(area);bloco.pack(fill="x",padx=14,pady=5)
        self.e_nome=ctk.CTkEntry(bloco,width=230,placeholder_text="Nome da preparação esperada")
        self.e_nome.pack(side="left",padx=6,pady=8)
        self.e_porcoes=ctk.CTkEntry(bloco,width=95,placeholder_text="Porções")
        self.e_porcoes.pack(side="left",padx=4,pady=8)
        op=["— sem ficha —"]+[f"{x['id_ficha']} | {x['nome']}" for x in self.fichas]
        self.cb_ficha=ctk.CTkComboBox(bloco,width=235,values=op)
        self.cb_ficha.set(op[0]);self.cb_ficha.pack(side="left",padx=4,pady=8)
        _btn(bloco,"Adicionar",self._adicionar,100).pack(side="left",padx=4)
        frame,self.tree=_tree(area,[("nome","Preparação",260,"w"),("porcoes","Porções previstas",115,"e"),("ficha","Ficha vinculada",250,"w")],altura=12)
        frame.pack(fill="both",expand=True,padx=14,pady=5)
        rod=ctk.CTkFrame(area,fg_color="transparent");rod.pack(fill="x",padx=14,pady=(4,12))
        _btn(rod,"Remover selecionada",self._remover,155,cor=LARANJA,hover=tema.LARANJA).pack(side="left")
        _btn(rod,"Salvar cardápio esperado",self._salvar,190).pack(side="right")

    def _carregar(self):
        try:
            self.data=self.e_data.get().strip()
            self.rows=ga.listar_preparacoes_dia(self.db,self.data,self.cb_ref.get())
            for iid in self.tree.get_children():self.tree.delete(iid)
            for i,r in enumerate(self.rows):
                nome_ficha=r.get("nome_ficha") or "—"
                self.tree.insert("", "end", iid=str(i), values=(r["nome"],_fmt_num(r.get("porcoes_previstas")),nome_ficha),
                                 tags=("linha_par" if i % 2 == 0 else "linha_impar",))
        except Exception as exc:
            messagebox.showerror("Preparações esperadas",str(exc),parent=self.janela)

    def _adicionar(self):
        nome=self.e_nome.get().strip()
        if not nome:
            messagebox.showwarning("Preparações esperadas","Informe o nome da preparação.",parent=self.janela);return
        porcoes=ga._numero(self.e_porcoes.get())
        if porcoes is not None and porcoes<=0:
            messagebox.showwarning("Preparações esperadas","As porções devem ser maiores que zero.",parent=self.janela);return
        ficha=None
        txt=self.cb_ficha.get()
        if txt!="— sem ficha —" and " | " in txt:
            try:ficha=int(txt.split(" | ",1)[0])
            except ValueError:ficha=None
        novo={"nome":nome,"porcoes_previstas":porcoes,"id_ficha":ficha}
        self.rows=[x for x in self.rows if x["nome"].casefold()!=nome.casefold()]
        self.rows.append(novo)
        self._render()
        self.e_nome.delete(0,"end");self.e_porcoes.delete(0,"end");self.cb_ficha.set("— sem ficha —")

    def _render(self):
        for iid in self.tree.get_children():self.tree.delete(iid)
        for i,r in enumerate(self.rows):
            ficha_nome=next((x["nome"] for x in self.fichas if x["id_ficha"]==r.get("id_ficha")),"—")
            self.tree.insert(
                "", "end", iid=str(i),
                values=(r["nome"], _fmt_num(r.get("porcoes_previstas")), ficha_nome),
                tags=("linha_par" if i % 2 == 0 else "linha_impar",)
            )

    def _remover(self):
        sel=self.tree.selection()
        if not sel:return
        idx=int(sel[0])
        if 0<=idx<len(self.rows):
            self.rows.pop(idx);self._render()

    def _salvar(self):
        try:
            total=ga.salvar_preparacoes_dia(self.db,self.e_data.get().strip(),self.cb_ref.get(),self.rows)
            self.data=self.e_data.get().strip()
            self.janela.destroy()
            messagebox.showinfo("Preparações esperadas",f"{total} preparação(ões) salva(s).",parent=self.app)
            self.ao_salvar()
        except Exception as exc:
            messagebox.showerror("Preparações esperadas",str(exc),parent=self.janela)


class AlocarRetiradaDialog:
    """Distribui uma retirada entre as preparações, uso geral ou perdas."""

    TIPOS={"Preparação":"preparacao","Uso geral / não identificado":"uso_geral","Perda":"perda"}

    def __init__(self,app,db_path,movimento,ao_salvar):
        self.app,self.db,self.mov,self.ao_salvar=app,db_path,movimento,ao_salvar
        self.janela=_PainelJanela(app, "Destinar retirada — " + str(movimento["item"]))
        self.janela.title("Destinar retirada — "+str(movimento["item"]))
        self.janela.geometry("920x620")
        self.janela.transient(app);self.janela.grab_set()
        self.rows=[]
        self.preps=[]
        self._montar()
        self._carregar_existentes()

    def _montar(self):
        m=self.mov
        preco=(_fmt_brl(m.get("preco_unitario_snapshot"))+" · "+
               {"historico":"histórico","atual_estimado":"preço atual estimado","pendente":"sem preço"}.get(m.get("origem_preco"),"sem preço"))
        ctk.CTkLabel(self.janela,
            text=f"{m['data']} {m['hora']} · {m['item']} · retirada { _fmt_num(m['qtd'])} {m['unidade']} · {preco}",
            anchor="w",justify="left",wraplength=880).pack(fill="x",padx=14,pady=(12,6))
        filt=ctk.CTkFrame(self.janela,fg_color="transparent");filt.pack(fill="x",padx=12,pady=5)
        ctk.CTkLabel(filt,text="Preparações da data").pack(side="left")
        self.e_data_prep=ctk.CTkEntry(filt,width=112);self.e_data_prep.pack(side="left",padx=4);self.e_data_prep.insert(0,m["data"])
        self.cb_ref=ctk.CTkComboBox(filt,width=130,values=["todas","desjejum","colacao","almoco","lanche","jantar","ceia"])
        self.cb_ref.set("todas");self.cb_ref.pack(side="left",padx=4)
        _btn(filt,"Carregar preparações",self._carregar_preps,145,cor=CINZA,hover=tema.SUAVE).pack(side="left",padx=4)
        area=ctk.CTkFrame(self.janela);area.pack(fill="x",padx=14,pady=6)
        self.cb_tipo=ctk.CTkComboBox(area,width=200,values=list(self.TIPOS))
        self.cb_tipo.set("Preparação");self.cb_tipo.pack(side="left",padx=5,pady=8)
        self.cb_prep=ctk.CTkComboBox(area,width=360,values=["— selecione —"])
        self.cb_prep.set("— selecione —");self.cb_prep.pack(side="left",padx=5,pady=8)
        self.e_qtd=ctk.CTkEntry(area,width=100,placeholder_text="Quantidade")
        self.e_qtd.pack(side="left",padx=5,pady=8)
        _btn(area,"Adicionar destino",self._adicionar,135).pack(side="left",padx=5)
        defs=[("tipo","Destino",180,"w"),("qtd","Quantidade",110,"e"),("un","Unidade",80,"center"),
              ("custo","Custo",110,"e")]
        frame,self.tree=_tree(self.janela,defs,altura=12)
        frame.pack(fill="both",expand=True,padx=14,pady=6)
        self.lbl_pendente=ctk.CTkLabel(self.janela,text="",anchor="w")
        self.lbl_pendente.pack(fill="x",padx=16,pady=(0,5))
        rod=ctk.CTkFrame(self.janela,fg_color="transparent");rod.pack(fill="x",padx=14,pady=(4,12))
        _btn(rod,"Remover destino",self._remover,135,cor=LARANJA,hover=tema.LARANJA).pack(side="left")
        _btn(rod,"Salvar destinações",self._salvar,155).pack(side="right")

    def _carregar_preps(self):
        try:
            data=self.e_data_prep.get().strip()
            ref=self.cb_ref.get()
            self.preps=ga.listar_preparacoes_dia(self.db,data,None if ref=="todas" else ref)
            opts=["— selecione —"]+[f"{p['id_preparacao_dia']} | {p['data']} | {p['refeicao']} | {p['nome']}" for p in self.preps]
            self.cb_prep.configure(values=opts);self.cb_prep.set(opts[0])
        except Exception as exc:
            messagebox.showerror("Destinação da retirada",str(exc),parent=self.janela)

    def _carregar_existentes(self):
        try:
            existentes=ga.listar_alocacoes_retirada(self.db,self.mov["data"],self.mov["id_mobile"])
            for a in existentes:
                self.rows.append({"tipo_destino":a["tipo_destino"],"id_preparacao_dia":a.get("id_preparacao_dia"),
                    "quantidade":float(a["quantidade"]),"nome":a["preparacao_nome_snapshot"]})
            self._render()
        except Exception as exc:
            messagebox.showerror("Destinação da retirada",str(exc),parent=self.janela)

    def _adicionar(self):
        tipo=self.TIPOS[self.cb_tipo.get()]
        qtd=ga._numero(self.e_qtd.get())
        if qtd is None or qtd<=0:
            messagebox.showwarning("Destinação da retirada","Informe uma quantidade maior que zero.",parent=self.janela);return
        pid=None;nome="Uso geral / não identificado" if tipo=="uso_geral" else "Perda"
        if tipo=="preparacao":
            txt=self.cb_prep.get()
            if " | " not in txt:
                messagebox.showwarning("Destinação da retirada","Selecione uma preparação.",parent=self.janela);return
            pid=int(txt.split(" | ",1)[0])
            p=next((x for x in self.preps if x["id_preparacao_dia"]==pid),None)
            nome=p["nome"] if p else txt
        self.rows.append({"tipo_destino":tipo,"id_preparacao_dia":pid,"quantidade":qtd,"nome":nome})
        self._render();self.e_qtd.delete(0,"end")

    def _render(self):
        for iid in self.tree.get_children():self.tree.delete(iid)
        total=sum(float(x["quantidade"]) for x in self.rows)
        for i,r in enumerate(self.rows):
            tipo={"preparacao":"Preparação: "+r["nome"],"uso_geral":"Uso geral / não identificado","perda":"Perda"}[r["tipo_destino"]]
            unit=self.mov["unidade"]
            preco=self.mov.get("preco_unitario_snapshot")
            custo=float(r["quantidade"])*float(preco) if preco is not None else None
            self.tree.insert(
                "", "end", iid=str(i),
                values=(tipo, _fmt_num(r["quantidade"]), unit, _fmt_brl(custo)),
                tags=("linha_par" if i % 2 == 0 else "linha_impar",)
            )
        pend=max(0,float(self.mov["qtd"])-total)
        self.lbl_pendente.configure(text=f"Retirada: {_fmt_num(self.mov['qtd'])} {self.mov['unidade']} · Destinado: {_fmt_num(total)} · Sem destino: {_fmt_num(pend)} {self.mov['unidade']}")
        if total>float(self.mov["qtd"])+1e-8:
            self.lbl_pendente.configure(text=self.lbl_pendente.cget("text")+" — a soma ultrapassa a retirada; corrija antes de salvar.",text_color=tema.ERRO)
        else:
            self.lbl_pendente.configure(text_color=tema.TEXTO)

    def _remover(self):
        sel=self.tree.selection()
        if not sel:return
        self.rows.pop(int(sel[0]));self._render()

    def _salvar(self):
        try:
            r=ga.salvar_alocacoes_retirada(self.db,self.mov["data"],self.mov["id_mobile"],self.rows,
                                           usuario=os.environ.get("USERNAME") or os.environ.get("USER") or "desktop")
            self.janela.destroy()
            messagebox.showinfo("Destinação salva",
                f"Revisão {r['revisao']} salva. Destinado: {_fmt_num(r['alocada'])} {self.mov['unidade']} · Sem destino: {_fmt_num(r['pendente'])} {self.mov['unidade']}",
                parent=self.app)
            self.ao_salvar()
        except Exception as exc:
            messagebox.showerror("Destinação da retirada",str(exc),parent=self.janela)
