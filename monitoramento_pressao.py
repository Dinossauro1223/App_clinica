"""Registro de pressão arterial e comparação observacional antes/depois de troca de suplemento."""
from __future__ import annotations

import sqlite3
import json
from datetime import datetime, timedelta


def criar_tabelas(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS PA_Registros (
        id_pa INTEGER PRIMARY KEY AUTOINCREMENT,
        id_paciente INTEGER NOT NULL,
        sistolica_mmhg INTEGER NOT NULL CHECK(sistolica_mmhg BETWEEN 30 AND 300),
        diastolica_mmhg INTEGER NOT NULL CHECK(diastolica_mmhg BETWEEN 20 AND 200),
        medido_em TEXT NOT NULL,
        posicao TEXT,
        braco TEXT,
        contexto TEXT,
        observacoes TEXT,
        autor TEXT,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT,
        ativo INTEGER NOT NULL DEFAULT 1 CHECK(ativo IN (0,1)),
        CHECK(sistolica_mmhg > diastolica_mmhg)
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pa_paciente_data ON PA_Registros(id_paciente, medido_em, ativo)")
    conn.execute("""CREATE TABLE IF NOT EXISTS Suplemento_Substituicoes (
        id_substituicao INTEGER PRIMARY KEY AUTOINCREMENT,
        id_paciente INTEGER NOT NULL,
        substituido_em TEXT NOT NULL,
        suplemento_anterior TEXT,
        suplemento_novo TEXT NOT NULL,
        motivo TEXT,
        autor TEXT,
        id_suplemento_anterior INTEGER,
        id_suplemento_novo INTEGER,
        snapshot_anterior_json TEXT,
        snapshot_novo_json TEXT,
        criado_em TEXT NOT NULL,
        ativo INTEGER NOT NULL DEFAULT 1 CHECK(ativo IN (0,1))
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_substituicao_paciente_data ON Suplemento_Substituicoes(id_paciente, substituido_em, ativo)")
    colunas = {r[1] for r in conn.execute("PRAGMA table_info(HGT_Registros)")}
    if "autor" not in colunas:
        conn.execute("ALTER TABLE HGT_Registros ADD COLUMN autor TEXT")


def salvar_pressao(caminho, id_paciente, sistolica, diastolica, medido_em,
                   posicao=None, braco=None, contexto=None, observacoes="", autor=None,
                   id_pa=None, agora=None):
    sistolica, diastolica = int(sistolica), int(diastolica)
    if not 30 <= sistolica <= 300 or not 20 <= diastolica <= 200 or sistolica <= diastolica:
        raise ValueError("Informe valores válidos: sistólica maior que diastólica.")
    dt = datetime.strptime(medido_em, "%Y-%m-%d %H:%M")
    carimbo = (agora or datetime.now()).isoformat(timespec="seconds")
    with sqlite3.connect(caminho) as conn:
        criar_tabelas(conn)
        if id_pa is None:
            cur = conn.execute("""INSERT INTO PA_Registros
                (id_paciente,sistolica_mmhg,diastolica_mmhg,medido_em,posicao,braco,contexto,observacoes,autor,criado_em)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (int(id_paciente),sistolica,diastolica,dt.strftime("%Y-%m-%d %H:%M:00"),
                 posicao,braco,contexto,(observacoes or "").strip(),autor,carimbo))
            return cur.lastrowid
        cur = conn.execute("""UPDATE PA_Registros SET sistolica_mmhg=?,diastolica_mmhg=?,medido_em=?,
            posicao=?,braco=?,contexto=?,observacoes=?,autor=?,atualizado_em=?
            WHERE id_pa=? AND id_paciente=? AND ativo=1""",
            (sistolica,diastolica,dt.strftime("%Y-%m-%d %H:%M:00"),posicao,braco,contexto,
             (observacoes or "").strip(),autor,carimbo,int(id_pa),int(id_paciente)))
        if cur.rowcount != 1:
            raise LookupError("Aferição não encontrada ou inativada.")
        return int(id_pa)


def listar_pressao(caminho, id_paciente, inicio=None, fim=None):
    sql = """SELECT id_pa,sistolica_mmhg,diastolica_mmhg,medido_em,posicao,braco,contexto,observacoes,autor
             FROM PA_Registros WHERE id_paciente=? AND ativo=1"""
    args = [int(id_paciente)]
    if inicio:
        sql += " AND medido_em>=?"; args.append(inicio)
    if fim:
        sql += " AND medido_em<=?"; args.append(fim)
    sql += " ORDER BY medido_em,id_pa"
    with sqlite3.connect(caminho) as conn:
        criar_tabelas(conn)
        return conn.execute(sql,args).fetchall()


def inativar_pressao(caminho, id_paciente, id_pa, agora=None):
    with sqlite3.connect(caminho) as conn:
        criar_tabelas(conn)
        cur=conn.execute("UPDATE PA_Registros SET ativo=0,atualizado_em=? WHERE id_pa=? AND id_paciente=? AND ativo=1",
                         ((agora or datetime.now()).isoformat(timespec="seconds"),int(id_pa),int(id_paciente)))
        return cur.rowcount == 1


def registrar_substituicao(caminho,id_paciente,substituido_em,suplemento_anterior,suplemento_novo,
                           motivo="",autor=None,agora=None,id_suplemento_anterior=None,
                           id_suplemento_novo=None,snapshot_anterior=None,snapshot_novo=None):
    dt=datetime.strptime(substituido_em,"%Y-%m-%d %H:%M")
    novo=(suplemento_novo or "").strip()
    if not novo:
        raise ValueError("Informe o suplemento novo.")
    carimbo=(agora or datetime.now()).isoformat(timespec="seconds")
    with sqlite3.connect(caminho) as conn:
        criar_tabelas(conn)
        cur=conn.execute("""INSERT INTO Suplemento_Substituicoes
            (id_paciente,substituido_em,suplemento_anterior,suplemento_novo,motivo,autor,
             id_suplemento_anterior,id_suplemento_novo,snapshot_anterior_json,snapshot_novo_json,criado_em)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (int(id_paciente),dt.strftime("%Y-%m-%d %H:%M:00"),(suplemento_anterior or "").strip() or None,
             novo,(motivo or "").strip() or None,autor,id_suplemento_anterior,id_suplemento_novo,
             json.dumps(snapshot_anterior,ensure_ascii=False,default=str) if snapshot_anterior is not None else None,
             json.dumps(snapshot_novo,ensure_ascii=False,default=str) if snapshot_novo is not None else None,carimbo))
        return cur.lastrowid


def listar_substituicoes(caminho,id_paciente):
    with sqlite3.connect(caminho) as conn:
        criar_tabelas(conn)
        return conn.execute("""SELECT id_substituicao,substituido_em,suplemento_anterior,suplemento_novo,
            id_suplemento_anterior,id_suplemento_novo,snapshot_anterior_json,snapshot_novo_json
            FROM Suplemento_Substituicoes WHERE id_paciente=? AND ativo=1
            ORDER BY substituido_em DESC,id_substituicao DESC""",(int(id_paciente),)).fetchall()


def _resumo(valores, chave):
    dias=sorted({v[0][:10] for v in valores})
    nums=[float(v[1]) for v in valores if v[1] is not None]
    return {"media": sum(nums)/len(nums) if nums else None,
            "afericoes":len(nums),"dias_com_dados":len(dias),"dias_cobertos":dias,
            "amostra_insuficiente":len(dias) < 3}


def comparar_tres_dias(caminho,id_paciente,substituido_em):
    """Compara janelas [troca-3d,troca) e [troca,troca+3d), sem incluir a hora da troca no período anterior."""
    troca=datetime.strptime(substituido_em,"%Y-%m-%d %H:%M")
    ini_antes=(troca-timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    fim_antes=troca.strftime("%Y-%m-%d %H:%M:%S")
    fim_depois=(troca+timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(caminho) as conn:
        criar_tabelas(conn)
        hgt_antes=conn.execute("""SELECT medido_em,valor_mg_dl FROM HGT_Registros
            WHERE id_paciente=? AND ativo=1 AND medido_em>=? AND medido_em<? ORDER BY medido_em""",
            (int(id_paciente),ini_antes,fim_antes)).fetchall()
        hgt_depois=conn.execute("""SELECT medido_em,valor_mg_dl FROM HGT_Registros
            WHERE id_paciente=? AND ativo=1 AND medido_em>=? AND medido_em<? ORDER BY medido_em""",
            (int(id_paciente),fim_antes,fim_depois)).fetchall()
        pa_antes=conn.execute("""SELECT medido_em,sistolica_mmhg,diastolica_mmhg FROM PA_Registros
            WHERE id_paciente=? AND ativo=1 AND medido_em>=? AND medido_em<? ORDER BY medido_em""",
            (int(id_paciente),ini_antes,fim_antes)).fetchall()
        pa_depois=conn.execute("""SELECT medido_em,sistolica_mmhg,diastolica_mmhg FROM PA_Registros
            WHERE id_paciente=? AND ativo=1 AND medido_em>=? AND medido_em<? ORDER BY medido_em""",
            (int(id_paciente),fim_antes,fim_depois)).fetchall()
    def resumo_pa(rows,idx):
        return _resumo([(r[0],r[idx]) for r in rows],"valor")
    return {
        "periodo_antes":{"inicio":ini_antes,"fim_exclusivo":fim_antes,
            "hgt":_resumo(hgt_antes,"valor"),"sistolica":resumo_pa(pa_antes,1),"diastolica":resumo_pa(pa_antes,2)},
        "periodo_depois":{"inicio":fim_antes,"fim_exclusivo":fim_depois,
            "hgt":_resumo(hgt_depois,"valor"),"sistolica":resumo_pa(pa_depois,1),"diastolica":resumo_pa(pa_depois,2)}
    }


class PainelMonitoramentoPressao(ctk.CTkFrame):
    """Interface de aferições pressóricas e comparação observacional de três dias."""
    def __init__(self, master, caminho_banco, id_paciente, **kwargs):
        super().__init__(master, **kwargs)
        self.caminho_banco=caminho_banco
        self.id_paciente=int(id_paciente)
        self.registros=[]
        topo=ctk.CTkFrame(self,fg_color="transparent"); topo.pack(fill="x",padx=12,pady=10)
        ctk.CTkLabel(topo,text="Pressão arterial — acompanhamento HAS",
                     font=ctk.CTkFont(size=19,weight="bold")).pack(side="left")
        ctk.CTkButton(topo,text="Registrar pressão",command=self._novo,
                      fg_color=tema.VERDE,hover_color=tema.VERDE_HOVER).pack(side="right")
        self.tabela=ttk.Treeview(self,columns=("data","pa","posicao","braco","contexto"),show="headings",height=9)
        for col,tit,w in (("data","Data e hora",145),("pa","PA (mmHg)",120),
                          ("posicao","Posição",100),("braco","Braço",100),("contexto","Contexto",150)):
            self.tabela.heading(col,text=tit); self.tabela.column(col,width=w,anchor="w")
        self.tabela.pack(fill="both",expand=True,padx=14,pady=8)
        self.canvas=tk.Canvas(self,height=220,background="#FFFFFF",highlightthickness=1,
                              highlightbackground="#D9E2DC")
        self.canvas.pack(fill="x",padx=14,pady=(0,8))
        botoes=ctk.CTkFrame(self,fg_color="transparent");botoes.pack(fill="x",padx=14,pady=(0,8))
        ctk.CTkButton(botoes,text="Editar",command=self._editar,fg_color=tema.VERDE).pack(side="left",padx=(0,8))
        ctk.CTkButton(botoes,text="Inativar",command=self._inativar,fg_color=tema.ERRO,
                      hover_color=tema.ERRO_HOVER).pack(side="left",padx=(0,8))
        ctk.CTkButton(botoes,text="Registrar troca e comparar 3 dias",command=self._troca,
                      fg_color=tema.VERDE).pack(side="right")
        self.atualizar()

    def atualizar(self):
        self.registros=listar_pressao(self.caminho_banco,self.id_paciente)
        for item in self.tabela.get_children(): self.tabela.delete(item)
        for r in self.registros:
            dt=datetime.fromisoformat(r[3]).strftime("%d/%m/%Y %H:%M")
            self.tabela.insert("","end",iid=str(r[0]),values=(dt,f"{r[1]}/{r[2]}",r[4] or "—",r[5] or "—",r[6] or "—"))
        self._desenhar_grafico()

    def _desenhar_grafico(self):
        c=self.canvas;c.delete("all")
        w=max(c.winfo_width(),520);h=220
        esq,dir_,topo,base=48,w-18,18,h-34
        if not self.registros:
            c.create_text(w/2,h/2,text="Nenhuma aferição de pressão registrada.",fill="#52645A")
            return
        valores=[float(r[1]) for r in self.registros]+[float(r[2]) for r in self.registros]
        minimo=max(0,min(20,min(valores)-10));maximo=max(180,max(valores)+10)
        for tick in range(int((minimo+9)//10*10),int(maximo)+1,20):
            y=base-(tick-minimo)/(maximo-minimo)*(base-topo)
            c.create_line(esq,y,dir_,y,fill="#E5EAE7")
            c.create_text(esq-7,y,text=str(tick),anchor="e",fill="#52645A")
        datas=[datetime.fromisoformat(r[3]) for r in self.registros]
        t0,t1=min(datas),max(datas);dur=max((t1-t0).total_seconds(),3600)
        for indice,cor,nome in ((1,"#B45309","Sistólica"),(2,"#2563EB","Diastólica")):
            pontos=[]
            for r,dt in zip(self.registros,datas):
                x=esq+(dt-t0).total_seconds()/dur*(dir_-esq)
                y=base-(float(r[indice])-minimo)/(maximo-minimo)*(base-topo)
                pontos.extend((x,y))
            if len(pontos)>=4:c.create_line(*pontos,fill=cor,width=2)
            for x,y in zip(pontos[::2],pontos[1::2]):
                c.create_oval(x-3,y-3,x+3,y+3,fill=cor,outline="#FFFFFF")
            c.create_text(dir_-105+(indice-1)*95,10,text=nome,fill=cor,anchor="nw")
        c.create_text(esq,base+15,text=t0.strftime("%d/%m %H:%M"),anchor="w",fill="#52645A")
        c.create_text(dir_,base+15,text=t1.strftime("%d/%m %H:%M"),anchor="e",fill="#52645A")

    def _dialogo(self,registro=None):
        win=ctk.CTkToplevel(self);win.title("Editar pressão" if registro else "Registrar pressão")
        win.geometry("430x600");win.transient(self.winfo_toplevel());win.grab_set()
        vars={
            "sistolica":ctk.StringVar(value=str(registro[1]) if registro else ""),
            "diastolica":ctk.StringVar(value=str(registro[2]) if registro else ""),
            "data":ctk.StringVar(value=datetime.fromisoformat(registro[3]).strftime("%Y-%m-%d") if registro else datetime.now().strftime("%Y-%m-%d")),
            "hora":ctk.StringVar(value=datetime.fromisoformat(registro[3]).strftime("%H:%M") if registro else datetime.now().strftime("%H:%M")),
            "posicao":ctk.StringVar(value=registro[4] or "" if registro else ""),
            "braco":ctk.StringVar(value=registro[5] or "" if registro else ""),
            "contexto":ctk.StringVar(value=registro[6] or "" if registro else ""),
            "obs":ctk.StringVar(value=registro[7] or "" if registro else ""),
            "autor":ctk.StringVar(value=registro[8] or "" if registro else "")
        }
        def entrada(rotulo,chave):
            ctk.CTkLabel(win,text=rotulo).pack(anchor="w",padx=22,pady=(8,2))
            ctk.CTkEntry(win,textvariable=vars[chave],width=380).pack(padx=22)
        entrada("Sistólica (mmHg)","sistolica");entrada("Diastólica (mmHg)","diastolica")
        entrada("Data (AAAA-MM-DD)","data");entrada("Horário (HH:MM)","hora")
        entrada("Posição (opcional)","posicao");entrada("Braço (opcional)","braco")
        entrada("Contexto (opcional)","contexto");entrada("Observações","obs");entrada("Responsável","autor")
        def salvar():
            try:
                salvar_pressao(self.caminho_banco,self.id_paciente,vars["sistolica"].get(),
                    vars["diastolica"].get(),vars["data"].get()+" "+vars["hora"].get(),
                    vars["posicao"].get() or None,vars["braco"].get() or None,
                    vars["contexto"].get() or None,vars["obs"].get(),vars["autor"].get() or None,
                    registro[0] if registro else None)
            except Exception as exc:
                messagebox.showerror("Aferição inválida",str(exc),parent=win);return
            win.destroy();self.atualizar()
        ctk.CTkButton(win,text="Salvar aferição",command=salvar,fg_color=tema.VERDE).pack(pady=18)

    def _novo(self): self._dialogo()
    def _selecionado(self):
        sel=self.tabela.selection()
        if not sel:
            messagebox.showinfo("Pressão arterial","Selecione uma aferição.");return None
        return next((r for r in self.registros if r[0]==int(sel[0])),None)
    def _editar(self):
        r=self._selecionado()
        if r:self._dialogo(r)
    def _inativar(self):
        r=self._selecionado()
        if r and messagebox.askyesno("Inativar aferição","O registro será preservado no banco e ocultado da lista. Continuar?"):
            inativar_pressao(self.caminho_banco,self.id_paciente,r[0]);self.atualizar()

    def _troca(self):
        win=ctk.CTkToplevel(self);win.title("Troca de suplemento — comparação de 3 dias")
        win.geometry("470x430");win.transient(self.winfo_toplevel());win.grab_set()
        data=ctk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        hora=ctk.StringVar(value=datetime.now().strftime("%H:%M"))
        anterior=ctk.StringVar();novo=ctk.StringVar();autor=ctk.StringVar()
        for rot,var in (("Data da substituição (AAAA-MM-DD)",data),("Horário (HH:MM)",hora),
                        ("Suplemento anterior",anterior),("Suplemento novo",novo),("Responsável",autor)):
            ctk.CTkLabel(win,text=rot).pack(anchor="w",padx=22,pady=(9,2))
            ctk.CTkEntry(win,textvariable=var,width=420).pack(padx=22)
        ctk.CTkLabel(win,text="A comparação usa três dias antes e três dias depois da data/hora informada.").pack(padx=20,pady=10)
        def executar():
            try:
                quando=data.get().strip()+" "+hora.get().strip()
                registrar_substituicao(self.caminho_banco,self.id_paciente,quando,anterior.get(),novo.get(),autor=autor.get())
                res=comparar_tres_dias(self.caminho_banco,self.id_paciente,quando)
                def fmt(d,k):
                    x=d[k]
                    if x["media"] is None:
                        return "sem dados"
                    aviso = "; amostra incompleta" if x["amostra_insuficiente"] else ""
                    return f'{x["media"]:.1f} (n={x["afericoes"]}; dias={x["dias_com_dados"]}/3{aviso})'
                msg=("ANTES — HGT: "+fmt(res["periodo_antes"],"hgt")+
                     "\\nANTES — PA sistólica: "+fmt(res["periodo_antes"],"sistolica")+
                     "\\nANTES — PA diastólica: "+fmt(res["periodo_antes"],"diastolica")+
                     "\\n\\nDEPOIS — HGT: "+fmt(res["periodo_depois"],"hgt")+
                     "\\nDEPOIS — PA sistólica: "+fmt(res["periodo_depois"],"sistolica")+
                     "\\nDEPOIS — PA diastólica: "+fmt(res["periodo_depois"],"diastolica")+
                     "\\n\\nComparação observacional; não demonstra causalidade.")
                messagebox.showinfo("Resumo dos períodos",msg,parent=win);win.destroy()
            except Exception as exc: messagebox.showerror("Comparação inválida",str(exc),parent=win)
        ctk.CTkButton(win,text="Registrar substituição e calcular",command=executar,
                      fg_color=tema.VERDE).pack(pady=15)
