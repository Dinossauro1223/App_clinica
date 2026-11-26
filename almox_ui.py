# -*- coding: utf-8 -*-
"""Interface desktop do Almoxarifado: custos, itens, movimentos e programação."""
import calendar
from datetime import date, timedelta
import customtkinter as ctk
from tkinter import ttk, messagebox
import almox_db as adb
import almox_reposicao as arep
import tema
import integracao_mobile as im

FUNDO=tema.FUNDO
VERDE=tema.VERDE
CINZA=tema.SUAVE

def _br(v):
    try:return f"R$ {float(v or 0):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except (TypeError,ValueError):return "R$ 0,00"
def _num(v):
    return str(v or "").strip().replace(".",",")
def _set(e,v):
    e.delete(0,"end");e.insert(0,"" if v is None else str(v))

class AlmoxUI:
    def __init__(self,app,db_path,base_dir=None):
        self.app,self.db,self.base_dir=app,db_path,base_dir
        adb.inicializar(self.db)
        arep.inicializar(self.db)
        self.pagina="Resumo e custos"
        self.item_atual=None
        self.prog_atual=None
        self.itens=[]
    def mostrar(self):
        self.app.limpar_area_principal()
        area=self.app.area_principal
        ctk.CTkLabel(area,text="Almoxarifado",font=ctk.CTkFont(size=24,weight="bold"),text_color=VERDE).pack(anchor="w",padx=20,pady=(15,4))
        ctk.CTkLabel(area,text="Controle de estoque, preços, gastos realizados e programação por refeição.",text_color=CINZA).pack(anchor="w",padx=22,pady=(0,8))
        nav=ctk.CTkFrame(area,fg_color="transparent");nav.pack(fill="x",padx=18,pady=4)
        self.conteudo=ctk.CTkFrame(area,fg_color="transparent");self.conteudo.pack(fill="both",expand=True,padx=16,pady=8)
        for p in ("Resumo e custos","Itens","Reposição","Movimentações","Programação"):
            ctk.CTkButton(nav,text=p,width=150,command=lambda x=p:self.ir(x),fg_color=VERDE if p==self.pagina else tema.SUAVE).pack(side="left",padx=3)
        self.ir(self.pagina)
    def ir(self,p):
        self.pagina=p
        for w in self.conteudo.winfo_children():w.destroy()
        {"Resumo e custos":self._resumo,"Itens":self._itens_ui,"Reposição":self._reposicao,"Movimentações":self._movimentos,"Programação":self._programacao}[p]()
    def _tree(self,parent,cols,widths=None,height=9):
        box=ctk.CTkFrame(parent,fg_color=tema.BRANCO);box.pack(fill="both",expand=True,pady=6)
        t=ttk.Treeview(box,columns=cols,show="headings",height=height)
        for i,col in enumerate(cols):
            t.heading(col,text=col)
            t.column(col,width=(widths[i] if widths else 130),anchor="w")
        sy=ttk.Scrollbar(box,orient="vertical",command=t.yview);t.configure(yscrollcommand=sy.set)
        t.pack(side="left",fill="both",expand=True,padx=4,pady=4);sy.pack(side="right",fill="y")
        return t
    def _resumo(self):
        top=ctk.CTkFrame(self.conteudo,fg_color="transparent");top.pack(fill="x")
        self.e_mes=ctk.CTkEntry(top,width=120,placeholder_text="AAAA-MM");self.e_mes.pack(side="left",padx=4)
        _set(self.e_mes,date.today().strftime("%Y-%m"))
        self.e_dia=ctk.CTkEntry(top,width=130,placeholder_text="AAAA-MM-DD");self.e_dia.pack(side="left",padx=4)
        _set(self.e_dia,adb.hoje())
        ctk.CTkButton(top,text="Atualizar custos",command=self._atualizar_resumo).pack(side="left",padx=6)
        self.lbl_res=ctk.CTkLabel(self.conteudo,text="",font=ctk.CTkFont(size=16,weight="bold"));self.lbl_res.pack(anchor="w",pady=6)
        ctk.CTkLabel(self.conteudo,text="Custos realizados no mês por refeição (consumos lançados no estoque)").pack(anchor="w")
        self.t_ref=self._tree(self.conteudo,("Refeição","Custo realizado"),(220,160),6)
        ctk.CTkLabel(self.conteudo,text="Detalhamento do dia selecionado").pack(anchor="w",pady=(8,0))
        self.t_dia=self._tree(self.conteudo,("Data","Refeição","Custo"),(140,220,140),5)
        self._atualizar_resumo()
    def _atualizar_resumo(self):
        mes=self.e_mes.get().strip()
        try:
            ano,mm=map(int,mes.split("-"));inicio=f"{ano:04d}-{mm:02d}-01";fim=f"{ano:04d}-{mm:02d}-{calendar.monthrange(ano,mm)[1]:02d}"
            dia=date.fromisoformat(self.e_dia.get().strip()).isoformat()
            r=adb.resumo_periodo(self.db,inicio,fim);diafim=dia
        except Exception as e:messagebox.showwarning("Custos",str(e));return
        self.lbl_res.configure(text=f"Realizado no mês: {_br(r['realizado_total'])}    Programado em rascunho/confirmado: {_br(r['programado_total'])}    Perdas líquidas: {_br(r['perdas_total'])}")
        self.t_ref.delete(*self.t_ref.get_children())
        for x in r["realizado_refeicao"]:self.t_ref.insert("","end",values=(adb.REFEICOES_LABEL.get(x["refeicao"],x["refeicao"]),_br(x["total"])))
        self.t_dia.delete(*self.t_dia.get_children())
        # Exibe uma linha por movimento de consumo/estorno no dia, preservando o detalhamento de cada refeição.
        for m in adb.listar_movimentos(self.db,dia,dia):
            if m["refeicao"] and m["motivo"] in ("consumo","estorno"):
                sinal="" if m["operacao"]=="saida" else "−"
                self.t_dia.insert("","end",values=(dia,adb.REFEICOES_LABEL[m["refeicao"]],sinal+_br(m["valor_total"])))
        if not self.t_dia.get_children():self.t_dia.insert("","end",values=(dia,"Sem consumo lançado","—"))
    def _itens_ui(self):
        form=ctk.CTkFrame(self.conteudo,fg_color="transparent");form.pack(fill="x")
        self.e_nome=ctk.CTkEntry(form,placeholder_text="Nome do item",width=220);self.e_nome.pack(side="left",padx=3)
        self.e_un=ctk.CTkEntry(form,placeholder_text="Unidade (kg, g, L, un)",width=140);self.e_un.pack(side="left",padx=3)
        self.cb_cat=ctk.CTkComboBox(form,values=list(adb.CATEGORIAS),width=175);self.cb_cat.pack(side="left",padx=3);self.cb_cat.set(adb.CATEGORIAS[0])
        self.e_preco=ctk.CTkEntry(form,placeholder_text="Preço por unidade (R$)",width=150);self.e_preco.pack(side="left",padx=3)
        self.e_min=ctk.CTkEntry(form,placeholder_text="Estoque mínimo",width=130);self.e_min.pack(side="left",padx=3)
        embalagem=ctk.CTkFrame(self.conteudo,fg_color="transparent");embalagem.pack(fill="x",pady=3)
        ctk.CTkLabel(embalagem,text="Conteúdo por embalagem (preencha se a unidade de estoque for un):").pack(side="left",padx=3)
        self.e_emb_qtd=ctk.CTkEntry(embalagem,width=110,placeholder_text="Ex.: 800");self.e_emb_qtd.pack(side="left",padx=3)
        self.cb_emb_un=ctk.CTkComboBox(embalagem,values=["g","kg","ml","L","mg"],width=85);self.cb_emb_un.pack(side="left",padx=3);self.cb_emb_un.set("g")
        self.e_obs=ctk.CTkEntry(self.conteudo,placeholder_text="Observações / fonte do preço");self.e_obs.pack(fill="x",pady=4)
        validade=ctk.CTkFrame(self.conteudo,fg_color="transparent");validade.pack(fill="x",pady=3)
        ctk.CTkLabel(validade,text="Validade (opcional):").pack(side="left",padx=3)
        self.e_validade=ctk.CTkEntry(validade,width=140,placeholder_text="AAAA-MM-DD");self.e_validade.pack(side="left",padx=3)
        filtro=ctk.CTkFrame(self.conteudo,fg_color="transparent");filtro.pack(fill="x",pady=(8,3))
        self.e_busca=ctk.CTkEntry(filtro,placeholder_text="Buscar produto pelo nome...",width=320);self.e_busca.pack(side="left",padx=3);self.e_busca.bind("<KeyRelease>",lambda _e:self._carregar_itens())
        self.cb_filtro_categoria=ctk.CTkComboBox(filtro,values=["Todas as categorias"]+list(adb.CATEGORIAS),width=210,command=lambda _v:self._carregar_itens());self.cb_filtro_categoria.pack(side="left",padx=3);self.cb_filtro_categoria.set("Todas as categorias")
        bar=ctk.CTkFrame(self.conteudo,fg_color="transparent");bar.pack(fill="x")
        ctk.CTkButton(bar,text="Novo / limpar",command=self._limpar_item).pack(side="left",padx=3)
        ctk.CTkButton(bar,text="Salvar item",command=self._salvar_item).pack(side="left",padx=3)
        ctk.CTkButton(bar,text="Ativar / desativar",command=self._alternar_item).pack(side="left",padx=3)
        ctk.CTkButton(bar,text="Histórico de preços",command=self._precos).pack(side="left",padx=3)
        ctk.CTkButton(bar,text="Sincronizar catálogo mobile",command=self._sincronizar_catalogo_mobile).pack(side="left",padx=3)
        ctk.CTkButton(bar,text="Importar categoria/validade do mobile",command=self._importar_classificacao_mobile).pack(side="left",padx=3)
        self.t_itens=self._tree(self.conteudo,("Nome","Unidade","Categoria","Validade","Valor unitário","Custo/g ou ml","Saldo","Mínimo","Situação"),(160,65,130,95,105,105,70,70,75),12)
        self._carregar_itens()
        self.t_itens.bind("<<TreeviewSelect>>",self._selecionar_item)
    @staticmethod
    def _custo_base_item(i):
        preco=i.get("valor_unitario")
        if preco is None:return "—"
        unidade=str(i.get("unidade") or "").strip().lower()
        if unidade in ("g","ml"):divisor=1
        elif unidade in ("kg","l"):divisor=1000
        elif unidade=="mg":divisor=0.001
        elif unidade=="un" and i.get("embalagem_qtd") and i.get("embalagem_un"):
            conteudo=float(i["embalagem_qtd"]);u=str(i["embalagem_un"]).lower()
            divisor=conteudo*(1000 if u in ("kg","l") else 0.001 if u=="mg" else 1)
        else:return "—"
        return _br(float(preco)/divisor).replace("R$ ","R$ ")+("/g" if unidade in ("g","kg","mg") or (unidade=="un" and str(i.get("embalagem_un") or "").lower() in ("g","kg","mg")) else "/ml")

    def _carregar_itens(self):
        todos=adb.listar_itens(self.db,False,termo=self.e_busca.get() or None)
        categoria=self.cb_filtro_categoria.get()
        self.itens=[i for i in todos if categoria=="Todas as categorias" or i["categoria"]==categoria]
        self.t_itens.delete(*self.t_itens.get_children())
        for i in self.itens:self.t_itens.insert("","end",iid=str(i["id_item"]),values=(i["nome"],i["unidade"],i["categoria"],i.get("validade") or "—",_br(i["valor_unitario"]),self._custo_base_item(i),_num(i["saldo"]),_num(i["estoque_minimo"]),"Ativo" if i["ativo"] else "Inativo"))
    def _selecionar_item(self,_=None):
        sel=self.t_itens.selection()
        if not sel:return
        i=next(x for x in self.itens if x["id_item"]==int(sel[0]));self.item_atual=i["id_item"]
        _set(self.e_nome,i["nome"]);_set(self.e_un,i["unidade"]);self.cb_cat.set(i["categoria"]);_set(self.e_preco,i["valor_unitario"]);_set(self.e_min,i["estoque_minimo"]);_set(self.e_emb_qtd,i.get("embalagem_qtd"));self.cb_emb_un.set(i.get("embalagem_un") or "g");_set(self.e_obs,i["observacao"]);_set(self.e_validade,i.get("validade"))
    def _limpar_item(self):
        self.item_atual=None
        for e in (self.e_nome,self.e_un,self.e_preco,self.e_min,self.e_emb_qtd,self.e_obs,self.e_validade):_set(e,"")
        self.cb_cat.set(adb.CATEGORIAS[0]);self.t_itens.selection_remove(self.t_itens.selection())
    def _salvar_item(self):
        try:
            d={"id_item":self.item_atual,"nome":self.e_nome.get(),"unidade":self.e_un.get(),"categoria":self.cb_cat.get(),"valor_unitario":self.e_preco.get(),"estoque_minimo":self.e_min.get(),"embalagem_qtd":self.e_emb_qtd.get(),"embalagem_un":self.cb_emb_un.get(),"observacao":self.e_obs.get(),"validade":self.e_validade.get()}
            adb.salvar_item(self.db,d);self._carregar_itens();self._atualizar_combos();messagebox.showinfo("Almoxarifado","Item salvo.")
        except Exception as e:messagebox.showwarning("Item",str(e))
    def _sincronizar_catalogo_mobile(self):
        try:
            base=self.base_dir
            if not base:
                import main
                base=main.get_base_path()
            mobile_db=im.caminho_mobile_db(self.db,base)
            resultado=im.sincronizar_catalogo_almox_desktop(self.db,mobile_db)
            self._carregar_itens()
            self._atualizar_combos()
            resumo=(f"Produtos sincronizados: {resultado['sincronizados']}\\n"
                    f"Novos no mobile: {resultado['criados']}\\n"
                    f"Atualizados: {resultado['atualizados']}\\n"
                    f"Espelho da Gestão Alimentar: {resultado['produtos_espelhados']}")
            if resultado["erros"]:
                resumo+="\\n\\nItens que precisam de revisão:\\n"+"\\n".join(
                    f"#{x['id_item']}: {x['erro']}" for x in resultado["erros"])
                messagebox.showwarning("Sincronização do catálogo",resumo)
            else:
                messagebox.showinfo("Sincronização do catálogo",resumo)
        except Exception as e:
            messagebox.showwarning("Sincronização do catálogo",str(e))

    def _importar_classificacao_mobile(self):
        try:
            base=self.base_dir
            if not base:
                import main
                base=main.get_base_path()
            mobile_db=im.caminho_mobile_db(self.db,base)
            resultado=im.importar_classificacao_almox_mobile(self.db,mobile_db)
            self._carregar_itens()
            self._atualizar_combos()
            messagebox.showinfo("Classificação do mobile",
                f"Itens atualizados: {resultado['atualizados']}\n"
                f"Vínculos sem produto mobile: {resultado['sem_vinculo']}\n\n"
                "Categorias padrão e validades vazias não apagam dados já cadastrados no desktop.")
        except Exception as e:
            messagebox.showwarning("Classificação do mobile",str(e))

    def _alternar_item(self):
        if not self.item_atual:messagebox.showinfo("Item","Selecione um item.");return
        i=adb.obter_item(self.db,self.item_atual);adb.alterar_item_ativo(self.db,self.item_atual,not i["ativo"]);self._carregar_itens()
    def _precos(self):
        if not self.item_atual:return
        linhas=adb.historico_precos(self.db,self.item_atual)
        messagebox.showinfo("Histórico de preços","\n".join(f"{x['registrado_em']} — {_br(x['valor_unitario'])} ({x['origem']})" for x in linhas) or "Sem histórico.")
    def _atualizar_combos(self):
        self.itens=adb.listar_itens(self.db,True)
        if hasattr(self,"cb_mov_item"):self.cb_mov_item.configure(values=[f"{x['id_item']} — {x['nome']} ({x['unidade']})" for x in self.itens])
        if hasattr(self,"cb_prog_item"):self.cb_prog_item.configure(values=[f"{x['id_item']} — {x['nome']} ({x['unidade']})" for x in self.itens])
    def _reposicao(self):
        self._atualizar_combos()
        form=ctk.CTkFrame(self.conteudo,fg_color="transparent");form.pack(fill="x")
        self.cb_rep_item=ctk.CTkComboBox(form,values=[f"{x['id_item']} — {x['nome']} ({x['unidade']})" for x in self.itens],width=250)
        self.cb_rep_item.pack(side="left",padx=3)
        self.e_rep_qtd=ctk.CTkEntry(form,width=110,placeholder_text="Quantidade");self.e_rep_qtd.pack(side="left",padx=3)
        self.e_rep_fornecedor=ctk.CTkEntry(form,width=190,placeholder_text="Fornecedor (opcional)");self.e_rep_fornecedor.pack(side="left",padx=3)
        self.e_rep_solicitante=ctk.CTkEntry(form,width=160,placeholder_text="Solicitado por");self.e_rep_solicitante.pack(side="left",padx=3)
        ctk.CTkButton(form,text="Solicitar reposição",command=self._solicitar_reposicao).pack(side="left",padx=3)
        self.e_rep_obs=ctk.CTkEntry(self.conteudo,placeholder_text="Observação do pedido (opcional)")
        self.e_rep_obs.pack(fill="x",pady=4)
        ctk.CTkLabel(self.conteudo,text="Pedidos: selecione um pedido pendente e registre o recebimento para atualizar o saldo").pack(anchor="w",pady=(8,2))
        self.t_rep= self._tree(self.conteudo,("Item","Qtd. pedida","Qtd. recebida","Custo total","Solicitado em","Solicitante","Fornecedor","Estado","Recebido em"),(150,85,90,100,100,110,130,80,100),8)
        bar=ctk.CTkFrame(self.conteudo,fg_color="transparent");bar.pack(fill="x")
        ctk.CTkButton(bar,text="Registrar recebimento",command=self._receber_reposicao).pack(side="left",padx=3)
        ctk.CTkButton(bar,text="Atualizar",command=self._carregar_reposicoes).pack(side="left",padx=3)
        ctk.CTkLabel(self.conteudo,text="Prazo médio por insumo — somente pedidos efetivamente recebidos").pack(anchor="w",pady=(10,2))
        self.t_prazos=self._tree(self.conteudo,("Item","Pedidos recebidos","Prazo médio (dias)","Menor","Maior","Pendentes"),(180,130,140,90,90,100),6)
        self._carregar_reposicoes()

    def _solicitar_reposicao(self):
        try:
            iid=int(self.cb_rep_item.get().split("—",1)[0].strip())
            arep.solicitar(self.db,iid,self.e_rep_qtd.get(),solicitado_por=self.e_rep_solicitante.get(),
                           fornecedor=self.e_rep_fornecedor.get(),observacao=self.e_rep_obs.get())
            _set(self.e_rep_qtd,"");_set(self.e_rep_obs,"")
            self._carregar_reposicoes()
            messagebox.showinfo("Reposição","Pedido registrado. O saldo só será atualizado no recebimento.")
        except Exception as e:messagebox.showwarning("Reposição",str(e))

    def _carregar_reposicoes(self):
        pedidos=arep.listar(self.db)
        self.t_rep.delete(*self.t_rep.get_children())
        for p in pedidos:
            self.t_rep.insert("","end",iid=str(p["id_pedido"]),values=(
                p["item"],_num(p["quantidade"]),_num(p.get("quantidade_recebida")) if p.get("quantidade_recebida") is not None else "—",
                _br(p.get("custo_total_recebido")) if p.get("custo_total_recebido") is not None else "—",
                p["solicitado_em"],p["solicitado_por"] or "—",
                p["fornecedor"] or "—",p["status"],p["recebido_em"] or "—"))
        self.t_prazos.delete(*self.t_prazos.get_children())
        for p in arep.prazos_medios(self.db):
            medio="—" if p["prazo_medio_dias"] is None else _num(p["prazo_medio_dias"])
            self.t_prazos.insert("","end",values=(p["nome"],p["pedidos_recebidos"],medio,
                "—" if p["menor_prazo_dias"] is None else _num(p["menor_prazo_dias"]),
                "—" if p["maior_prazo_dias"] is None else _num(p["maior_prazo_dias"]),p["pedidos_pendentes"]))

    def _receber_reposicao(self):
        sel=self.t_rep.selection()
        if not sel:
            messagebox.showinfo("Reposição","Selecione um pedido pendente.")
            return
        from tkinter import simpledialog
        nome=simpledialog.askstring("Recebimento","Nome de quem recebeu (opcional):")
        if nome is None:return
        try:
            pedido_id=int(sel[0])
            pedido=next((p for p in arep.listar(self.db) if p["id_pedido"]==pedido_id),None)
            if not pedido or pedido["status"]!="pendente":
                raise ValueError("Selecione um pedido pendente.")
            item=adb.obter_item(self.db,pedido["id_item"])
            lote=messagebox.askyesno(
                "Forma de informar o custo",
                "Deseja informar o CUSTO TOTAL de todas as unidades recebidas?\\n\\n"
                "Sim: informar custo total do lote e quantidade recebida.\\n"
                "Não: informar o preço por unidade."
            )
            if lote:
                qtd=simpledialog.askstring(
                    "Quantidade recebida",
                    f"Quantidade recebida de {item['nome']} ({item['unidade']}):",
                    initialvalue=str(pedido["quantidade"])
                )
                if qtd is None:return
                total=simpledialog.askstring(
                    "Custo total do lote",
                    "Informe o valor total pago por todo o lote (R$):"
                )
                if total is None:return
                arep.receber(self.db,pedido_id,recebido_por=nome,
                             quantidade_recebida=qtd,valor_total_compra=total)
            else:
                preco=simpledialog.askstring(
                    "Preço unitário",
                    f"Informe o preço por {item['unidade']} de {item['nome']} (R$):",
                    initialvalue="" if item.get("valor_unitario") is None else str(item["valor_unitario"])
                )
                if preco is None:return
                arep.receber(self.db,pedido_id,recebido_por=nome,valor_unitario=preco)
            self._carregar_reposicoes();self._atualizar_combos()
            messagebox.showinfo("Reposição","Recebimento registrado e entrada lançada no estoque.")
        except Exception as e:messagebox.showwarning("Reposição",str(e))

    def _movimentos(self):
        self._atualizar_combos()
        f=ctk.CTkFrame(self.conteudo,fg_color="transparent");f.pack(fill="x")
        self.cb_mov_item=ctk.CTkComboBox(f,values=[f"{x['id_item']} — {x['nome']} ({x['unidade']})" for x in self.itens],width=240);self.cb_mov_item.pack(side="left",padx=3)
        self.cb_tipo=ctk.CTkComboBox(f,values=["entrada","consumo","perda","ajuste_entrada","ajuste_saida"],width=150);self.cb_tipo.pack(side="left",padx=3);self.cb_tipo.set("entrada")
        self.e_mov_data=ctk.CTkEntry(f,width=120);self.e_mov_data.pack(side="left",padx=3);_set(self.e_mov_data,adb.hoje())
        self.e_mov_qtd=ctk.CTkEntry(f,width=100,placeholder_text="Quantidade");self.e_mov_qtd.pack(side="left",padx=3)
        self.e_mov_preco=ctk.CTkEntry(f,width=140,placeholder_text="Preço unitário (R$)");self.e_mov_preco.pack(side="left",padx=3)
        g=ctk.CTkFrame(self.conteudo,fg_color="transparent");g.pack(fill="x")
        self.cb_mov_ref=ctk.CTkComboBox(g,values=["— sem refeição —"]+[v for _,v in adb.REFEICOES],width=180);self.cb_mov_ref.pack(side="left",padx=3);self.cb_mov_ref.set("— sem refeição —")
        self.e_mov_obs=ctk.CTkEntry(g,placeholder_text="Observação / documento de compra",width=360);self.e_mov_obs.pack(side="left",padx=3)
        ctk.CTkButton(g,text="Registrar movimento",command=self._registrar).pack(side="left",padx=3)
        self.t_mov=self._tree(self.conteudo,("Data","Item","Tipo","Quantidade","Preço unitário","Total","Refeição","Observação"),(100,150,90,90,105,105,120,230),12)
        bar=ctk.CTkFrame(self.conteudo,fg_color="transparent");bar.pack(fill="x")
        ctk.CTkButton(bar,text="Estornar movimento selecionado",command=self._estornar,fg_color=tema.ERRO).pack(side="left",padx=4)
        self._carregar_movimentos()
    def _registrar(self):
        try:
            escolha=self.cb_mov_item.get();iid=int(escolha.split("—",1)[0].strip())
            tipo=self.cb_tipo.get();ref=next((k for k,v in adb.REFEICOES if v==self.cb_mov_ref.get()),None)
            adb.registrar_movimento(self.db,self.e_mov_data.get(),iid,tipo,self.e_mov_qtd.get(),self.e_mov_preco.get() or None,ref,self.e_mov_obs.get())
            self._carregar_movimentos();self._atualizar_combos();messagebox.showinfo("Estoque","Movimento registrado.")
        except Exception as e:messagebox.showwarning("Movimento",str(e))
    def _carregar_movimentos(self):
        self.movs=adb.listar_movimentos(self.db);self.t_mov.delete(*self.t_mov.get_children())
        for x in self.movs:self.t_mov.insert("","end",iid=str(x["id_movimento"]),values=(x["data"],x["item"],x["motivo"],_num(x["quantidade"]),_br(x["valor_unitario"]),_br(x["valor_total"]),adb.REFEICOES_LABEL.get(x["refeicao"],"—"),x.get("observacao") or "—"))
    def _estornar(self):
        sel=self.t_mov.selection()
        if not sel:messagebox.showinfo("Estorno","Selecione um movimento.");return
        from tkinter import simpledialog
        motivo=simpledialog.askstring("Estornar movimento","Justificativa do estorno:")
        if motivo is None:return
        try:adb.estornar_movimento(self.db,int(sel[0]),justificativa=motivo);self._carregar_movimentos();messagebox.showinfo("Estorno","Estorno registrado.")
        except Exception as e:messagebox.showwarning("Estorno",str(e))
    def _programacao(self):
        self._atualizar_combos()
        f=ctk.CTkFrame(self.conteudo,fg_color="transparent");f.pack(fill="x")
        self.e_prog_data=ctk.CTkEntry(f,width=120);self.e_prog_data.pack(side="left",padx=3);_set(self.e_prog_data,adb.hoje())
        self.cb_prog_ref=ctk.CTkComboBox(f,values=[v for _,v in adb.REFEICOES],width=170);self.cb_prog_ref.pack(side="left",padx=3);self.cb_prog_ref.set("Almoço")
        self.e_prog_porcoes=ctk.CTkEntry(f,width=100,placeholder_text="Porções");self.e_prog_porcoes.pack(side="left",padx=3)
        ctk.CTkButton(f,text="Criar programação",command=self._criar_programacao).pack(side="left",padx=3)
        g=ctk.CTkFrame(self.conteudo,fg_color="transparent");g.pack(fill="x")
        self.cb_prog_item=ctk.CTkComboBox(g,values=[f"{x['id_item']} — {x['nome']}" for x in self.itens],width=250);self.cb_prog_item.pack(side="left",padx=3)
        self.e_prog_qpp=ctk.CTkEntry(g,width=130,placeholder_text="Qtd. por porção");self.e_prog_qpp.pack(side="left",padx=3)
        ctk.CTkButton(g,text="Adicionar insumo",command=self._add_prog).pack(side="left",padx=3)
        self.t_prog=self._tree(self.conteudo,("Data","Refeição","Porções","Estado","Custo estimado"),(120,160,100,120,140),7)
        self.t_prog_itens=self._tree(self.conteudo,("Item","Unidade","Qtd./porção","Qtd. total","Preço unitário","Custo"),(180,80,110,110,120,120),6)
        bar=ctk.CTkFrame(self.conteudo,fg_color="transparent");bar.pack(fill="x")
        for label,cmd in (("Atualizar",self._carregar_programacoes),("Confirmar",self._confirmar_programacao),("Realizar e lançar consumo",self._realizar_programacao),("Cancelar",self._cancelar_programacao)):
            ctk.CTkButton(bar,text=label,command=cmd).pack(side="left",padx=3)
        self._carregar_programacoes()
        self.t_prog.bind("<<TreeviewSelect>>",self._selecionar_programacao)
    def _criar_programacao(self):
        try:
            ref=next(k for k,v in adb.REFEICOES if v==self.cb_prog_ref.get())
            self.prog_atual=adb.criar_programacao(self.db,self.e_prog_data.get(),ref,self.e_prog_porcoes.get())
            self._carregar_programacoes()
        except Exception as e:messagebox.showwarning("Programação",str(e))
    def _carregar_programacoes(self):
        self.progs=adb.listar_programacoes(self.db);self.t_prog.delete(*self.t_prog.get_children())
        for p in self.progs:self.t_prog.insert("","end",iid=str(p["id_programacao"]),values=(p["data"],adb.REFEICOES_LABEL[p["refeicao"]],_num(p["porcoes"]),p["status"],_br(p["custo_estimado"])))
    def _selecionar_programacao(self,_=None):
        sel=self.t_prog.selection()
        if not sel:return
        self.prog_atual=int(sel[0]);self.t_prog_itens.delete(*self.t_prog_itens.get_children())
        for x in adb.itens_programacao(self.db,self.prog_atual):self.t_prog_itens.insert("","end",values=(x["item"],x["unidade"],_num(x["quantidade_por_porcao"]),_num(x["quantidade_total"]),_br(x["valor_unitario"]),_br(x["valor_total"])))
    def _add_prog(self):
        if not self.prog_atual:messagebox.showinfo("Programação","Crie ou selecione uma programação.");return
        try:iid=int(self.cb_prog_item.get().split("—",1)[0].strip());adb.adicionar_item_programacao(self.db,self.prog_atual,iid,self.e_prog_qpp.get());_set(self.e_prog_qpp,"");self._carregar_programacoes();self.t_prog.selection_set(str(self.prog_atual));self._selecionar_programacao()
        except Exception as e:messagebox.showwarning("Programação",str(e))
    def _confirmar_programacao(self):
        if not self.prog_atual:return
        try:adb.alterar_status_programacao(self.db,self.prog_atual,"confirmada");self._carregar_programacoes()
        except Exception as e:messagebox.showwarning("Programação",str(e))
    def _realizar_programacao(self):
        if not self.prog_atual:return
        if not messagebox.askyesno("Realizar","Registrar a saída real dos insumos e atribuir o custo à refeição?"):return
        try:adb.realizar_programacao(self.db,self.prog_atual);self._carregar_programacoes();messagebox.showinfo("Programação","Consumo real registrado.")
        except Exception as e:messagebox.showwarning("Programação",str(e))
    def _cancelar_programacao(self):
        if not self.prog_atual:return
        try:adb.alterar_status_programacao(self.db,self.prog_atual,"cancelada");self._carregar_programacoes()
        except Exception as e:messagebox.showwarning("Programação",str(e))
