# -*- coding: utf-8 -*-
"""Interface desktop do Almoxarifado: custos, itens, movimentos e programação."""
import calendar
from datetime import date, timedelta
import customtkinter as ctk
from tkinter import ttk, messagebox
import almox_db as adb
import tema

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
    def __init__(self,app,db_path):
        self.app,self.db=app,db_path
        adb.inicializar(self.db)
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
        for p in ("Resumo e custos","Itens","Movimentações","Programação"):
            ctk.CTkButton(nav,text=p,width=150,command=lambda x=p:self.ir(x),fg_color=VERDE if p==self.pagina else tema.SUAVE).pack(side="left",padx=3)
        self.ir(self.pagina)
    def ir(self,p):
        self.pagina=p
        for w in self.conteudo.winfo_children():w.destroy()
        {"Resumo e custos":self._resumo,"Itens":self._itens_ui,"Movimentações":self._movimentos,"Programação":self._programacao}[p]()
    def _tree(self,parent,cols,widths=None,height=9):
        box=ctk.CTkFrame(parent,fg_color="white");box.pack(fill="both",expand=True,pady=6)
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
        self.e_obs=ctk.CTkEntry(self.conteudo,placeholder_text="Observações / fonte do preço");self.e_obs.pack(fill="x",pady=4)
        bar=ctk.CTkFrame(self.conteudo,fg_color="transparent");bar.pack(fill="x")
        ctk.CTkButton(bar,text="Novo / limpar",command=self._limpar_item).pack(side="left",padx=3)
        ctk.CTkButton(bar,text="Salvar item",command=self._salvar_item).pack(side="left",padx=3)
        ctk.CTkButton(bar,text="Ativar / desativar",command=self._alternar_item).pack(side="left",padx=3)
        ctk.CTkButton(bar,text="Histórico de preços",command=self._precos).pack(side="left",padx=3)
        self.t_itens=self._tree(self.conteudo,("Nome","Unidade","Categoria","Valor unitário","Saldo","Mínimo","Situação"),(190,80,150,130,100,100,90),12)
        self._carregar_itens()
        self.t_itens.bind("<<TreeviewSelect>>",self._selecionar_item)
    def _carregar_itens(self):
        self.itens=adb.listar_itens(self.db,False);self.t_itens.delete(*self.t_itens.get_children())
        for i in self.itens:self.t_itens.insert("","end",iid=str(i["id_item"]),values=(i["nome"],i["unidade"],i["categoria"],_br(i["valor_unitario"]),_num(i["saldo"]),_num(i["estoque_minimo"]),"Ativo" if i["ativo"] else "Inativo"))
    def _selecionar_item(self,_=None):
        sel=self.t_itens.selection()
        if not sel:return
        i=next(x for x in self.itens if x["id_item"]==int(sel[0]));self.item_atual=i["id_item"]
        _set(self.e_nome,i["nome"]);_set(self.e_un,i["unidade"]);self.cb_cat.set(i["categoria"]);_set(self.e_preco,i["valor_unitario"]);_set(self.e_min,i["estoque_minimo"]);_set(self.e_obs,i["observacao"])
    def _limpar_item(self):
        self.item_atual=None
        for e in (self.e_nome,self.e_un,self.e_preco,self.e_min,self.e_obs):_set(e,"")
        self.cb_cat.set(adb.CATEGORIAS[0]);self.t_itens.selection_remove(self.t_itens.selection())
    def _salvar_item(self):
        try:
            d={"id_item":self.item_atual,"nome":self.e_nome.get(),"unidade":self.e_un.get(),"categoria":self.cb_cat.get(),"valor_unitario":self.e_preco.get(),"estoque_minimo":self.e_min.get(),"observacao":self.e_obs.get()}
            adb.salvar_item(self.db,d);self._carregar_itens();self._atualizar_combos();messagebox.showinfo("Almoxarifado","Item salvo.")
        except Exception as e:messagebox.showwarning("Item",str(e))
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
        self.t_mov=self._tree(self.conteudo,("Data","Item","Tipo","Quantidade","Preço unitário","Total","Refeição"),(110,180,100,100,120,120,150),12)
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
        for x in self.movs:self.t_mov.insert("","end",iid=str(x["id_movimento"]),values=(x["data"],x["item"],x["motivo"],_num(x["quantidade"]),_br(x["valor_unitario"]),_br(x["valor_total"]),adb.REFEICOES_LABEL.get(x["refeicao"],"—")))
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
