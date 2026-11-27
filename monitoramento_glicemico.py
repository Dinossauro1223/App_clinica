"""Registro e visualização observacional de HGT por paciente.

Não estima curvas fisiológicas nem altera condutas. Gráfico desenhado em Canvas para
evitar dependências adicionais e manter compatibilidade com o executável Windows.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
import json
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox

import customtkinter as ctk
import tema
import monitoramento_enteral as me


CONTEXTOS = ("Jejum", "Pré-prandial", "Pós-prandial", "Aleatória")


def criar_tabela(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS HGT_Registros (
            id_hgt INTEGER PRIMARY KEY AUTOINCREMENT,
            id_paciente INTEGER NOT NULL,
            valor_mg_dl REAL NOT NULL CHECK(valor_mg_dl > 0 AND valor_mg_dl < 2000),
            medido_em TEXT NOT NULL,
            contexto TEXT NOT NULL CHECK(contexto IN ('Jejum','Pré-prandial','Pós-prandial','Aleatória')),
            observacoes TEXT,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT,
            ativo INTEGER NOT NULL DEFAULT 1 CHECK(ativo IN (0,1))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_hgt_paciente_data
        ON HGT_Registros(id_paciente, medido_em, ativo)
    """)


def salvar_hgt(caminho, id_paciente, valor, medido_em, contexto, observacoes="",
               id_hgt=None, agora=None):
    """Insere ou corrige medição. Exclusões lógicas preservam histórico."""
    valor = float(valor)
    if not 0 < valor < 2000:
        raise ValueError("O HGT deve ser maior que zero e menor que 2000 mg/dL.")
    dt = datetime.strptime(medido_em, "%Y-%m-%d %H:%M")
    if contexto not in CONTEXTOS:
        raise ValueError("Contexto glicêmico inválido.")
    carimbo = (agora or datetime.now()).isoformat(timespec="seconds")
    with closing(sqlite3.connect(caminho)) as conn, conn:
        criar_tabela(conn)
        if id_hgt is None:
            cur = conn.execute("""
                INSERT INTO HGT_Registros
                (id_paciente, valor_mg_dl, medido_em, contexto, observacoes, criado_em)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (int(id_paciente), valor, dt.strftime("%Y-%m-%d %H:%M:00"),
                  contexto, observacoes.strip(), carimbo))
            return cur.lastrowid
        cur = conn.execute("""
            UPDATE HGT_Registros SET valor_mg_dl=?, medido_em=?, contexto=?,
                observacoes=?, atualizado_em=?
            WHERE id_hgt=? AND id_paciente=? AND ativo=1
        """, (valor, dt.strftime("%Y-%m-%d %H:%M:00"), contexto,
              observacoes.strip(), carimbo, int(id_hgt), int(id_paciente)))
        if cur.rowcount != 1:
            raise LookupError("Medição não encontrada ou já inativada.")
        return int(id_hgt)


def listar_hgt(caminho, id_paciente, inicio=None, fim=None):
    sql = """SELECT id_hgt, valor_mg_dl, medido_em, contexto, observacoes
             FROM HGT_Registros WHERE id_paciente=? AND ativo=1"""
    args = [int(id_paciente)]
    if inicio:
        sql += " AND medido_em >= ?"
        args.append(inicio)
    if fim:
        sql += " AND medido_em <= ?"
        args.append(fim)
    sql += " ORDER BY medido_em, id_hgt"
    with closing(sqlite3.connect(caminho)) as conn, conn:
        criar_tabela(conn)
        return conn.execute(sql, args).fetchall()


def inativar_hgt(caminho, id_paciente, id_hgt, agora=None):
    with closing(sqlite3.connect(caminho)) as conn, conn:
        criar_tabela(conn)
        cur = conn.execute("""
            UPDATE HGT_Registros SET ativo=0, atualizado_em=?
            WHERE id_hgt=? AND id_paciente=? AND ativo=1
        """, ((agora or datetime.now()).isoformat(timespec="seconds"),
              int(id_hgt), int(id_paciente)))
        return cur.rowcount == 1


def intervalo_relativo_hora(medido_em, oferta_em):
    """Retorna minutos entre HGT e oferta real; negativo significa antes da oferta."""
    a = datetime.fromisoformat(medido_em)
    b = datetime.fromisoformat(oferta_em)
    return int((a - b).total_seconds() // 60)


def listar_ofertas_nutricionais(caminho, id_paciente, inicio=None, fim=None):
    """Lê ofertas reais do mapa; só cria evento temporal quando HH:MM foi registrado."""
    sql = """SELECT m.data,s.nome,s.preparacoes_json,s.carb_100,s.fibra_g_100,
                    s.tipo_fibra,s.unidade
             FROM Mapa_Registros m
             JOIN Mapa_Registro_Suplementos s ON s.id_registro=m.id_registro
             WHERE m.id_paciente=?"""
    args = [int(id_paciente)]
    if inicio:
        sql += " AND m.data>=?"; args.append(inicio[:10])
    if fim:
        sql += " AND m.data<=?"; args.append(fim[:10])
    sql += " ORDER BY m.data,s.nome"
    eventos = []
    try:
        with closing(sqlite3.connect(caminho)) as conn, conn:
            rows = conn.execute(sql,args).fetchall()
    except sqlite3.Error:
        return eventos
    for data, nome, preparacoes_json, carb_100, fibra_100, tipo_fibra, unidade in rows:
        try:
            preparacoes = json.loads(preparacoes_json or "[]")
        except (TypeError, ValueError):
            continue
        for prep in preparacoes:
            horario = str(prep.get("horario") or "").strip()
            if not horario:
                continue
            try:
                instante = datetime.strptime(f"{data} {horario}","%Y-%m-%d %H:%M")
                dose = float(prep.get("dose"))
            except (TypeError, ValueError):
                continue
            agua = prep.get("agua_adicionada_ml")
            agua_separada = prep.get("agua_separada_ml")
            try:
                agua = float(agua) if agua not in (None,"") else None
            except (TypeError,ValueError):
                agua = None
            try:
                agua_separada = float(agua_separada) if agua_separada not in (None,"") else None
            except (TypeError,ValueError):
                agua_separada = None
            try:
                carboidratos = dose * float(carb_100) / 100 if carb_100 is not None else None
            except (TypeError,ValueError):
                carboidratos = None
            try:
                fibras = dose * float(fibra_100) / 100 if fibra_100 is not None else None
            except (TypeError,ValueError):
                fibras = None
            eventos.append({
                "instante": instante, "suplemento": nome, "refeicao": prep.get("refeicao") or "",
                "dose": dose, "unidade": unidade or "", "agua_misturada_ml": agua,
                "agua_separada_ml": agua_separada, "carboidratos_g": carboidratos,
                "fibras_g": fibras, "tipo_fibra": tipo_fibra or "não informado", "tipo_evento": "suplemento"
            })
    try:
        administracoes = me.listar_administracoes(caminho, id_paciente, inicio, fim)
    except (sqlite3.Error, ValueError):
        administracoes = []
    for adm in administracoes:
        try:
            instante = datetime.fromisoformat(adm["inicio_em"])
        except (TypeError, ValueError):
            continue
        eventos.append({
            "instante": instante, "suplemento": "Dieta enteral",
            "refeicao": "administração",
            "dose": adm.get("volume_administrado_ml"), "unidade": "mL",
            "agua_misturada_ml": None, "agua_separada_ml": None,
            "carboidratos_g": None, "fibras_g": None,
            "tipo_fibra": "não informado", "tipo_evento": "enteral",
            "fim_em": adm.get("fim_em"), "taxa_ml_h": adm.get("taxa_ml_h"),
            "pausado_min": adm.get("pausado_min"),
            "via_administracao": adm.get("via_administracao"),
        })
    return sorted(eventos,key=lambda x:x["instante"])


class PainelMonitoramentoGlicemico(ctk.CTkFrame):
    """Painel do perfil do paciente; eventos nutricionais reais podem ser acoplados por integração."""

    def __init__(self, master, caminho_banco, id_paciente, **kwargs):
        super().__init__(master, **kwargs)
        self.caminho_banco = caminho_banco
        self.id_paciente = int(id_paciente)
        self.selecionado = None
        self._construir()
        self.atualizar()

    def _construir(self):
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=12, pady=10)
        ctk.CTkLabel(topo, text="Monitoramento glicêmico",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(topo, text="Registrar HGT", command=self._novo,
                      fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER).pack(side="right")

        self.canvas = tk.Canvas(self, height=250, background="#FFFFFF",
                                highlightthickness=1, highlightbackground="#D9E2DC")
        self.canvas.pack(fill="x", padx=14, pady=(4, 10))
        ctk.CTkLabel(self, text=(
            "O gráfico apresenta medições reais de HGT e marcações das ofertas com horário efetivamente "
            "registrado no mapa. Oferta sem horário permanece fora do eixo temporal."
        ), text_color=tema.SUAVE, wraplength=900, justify="left").pack(anchor="w", padx=16)

        self.tabela = ttk.Treeview(self, columns=("data", "valor", "contexto", "obs"),
                                   show="headings", height=8)
        for col, titulo, largura in (
            ("data", "Data e hora", 150), ("valor", "HGT (mg/dL)", 110),
            ("contexto", "Contexto", 130), ("obs", "Observações", 360)):
            self.tabela.heading(col, text=titulo)
            self.tabela.column(col, width=largura, anchor="w")
        self.tabela.pack(fill="both", expand=True, padx=14, pady=8)
        ctk.CTkLabel(self,text="Ofertas nutricionais registradas no mapa",
                     font=ctk.CTkFont(size=14,weight="bold")).pack(anchor="w",padx=16,pady=(8,2))
        self.ofertas_tabela=ttk.Treeview(self,columns=("hora","produto","dose","agua","agua_sep","carb","fibra"),
                                          show="headings",height=5)
        for col,titulo,largura in (("hora","Horário",115),("produto","Suplemento / refeição",230),
            ("dose","Dose",90),("agua","Água misturada (mL)",115),("agua_sep","Água separada (mL)",115),("carb","Carboidratos (g)",120),("fibra","Fibras (g)",110)):
            self.ofertas_tabela.heading(col,text=titulo);self.ofertas_tabela.column(col,width=largura,anchor="w")
        self.ofertas_tabela.pack(fill="x",padx=14,pady=(0,8))
        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(fill="x", padx=14, pady=(0, 12))
        ctk.CTkButton(botoes, text="Editar selecionado", command=self._editar,
                      fg_color=tema.VERDE).pack(side="left", padx=(0, 8))
        ctk.CTkButton(botoes, text="Inativar registro", command=self._inativar,
                      fg_color=tema.ERRO, hover_color=tema.ERRO_HOVER).pack(side="left")

    def atualizar(self):
        self.registros = listar_hgt(self.caminho_banco, self.id_paciente)
        self.ofertas = listar_ofertas_nutricionais(self.caminho_banco,self.id_paciente)
        for item in self.tabela.get_children():
            self.tabela.delete(item)
        for r in self.registros:
            dt = datetime.fromisoformat(r[2]).strftime("%d/%m/%Y %H:%M")
            self.tabela.insert("", "end", iid=str(r[0]),
                               values=(dt, f"{r[1]:g}", r[3], r[4] or "—"))
        for item in self.ofertas_tabela.get_children():
            self.ofertas_tabela.delete(item)
        for i,evento in enumerate(self.ofertas):
            dose="—" if evento.get("dose") is None else f'{evento["dose"]:g} {evento["unidade"]}'
            agua="—" if evento["agua_misturada_ml"] is None else f'{evento["agua_misturada_ml"]:g}'
            agua_sep="—" if evento["agua_separada_ml"] is None else f'{evento["agua_separada_ml"]:g}'
            carb="—" if evento["carboidratos_g"] is None else f'{evento["carboidratos_g"]:.1f}'
            fibra="—" if evento["fibras_g"] is None else f'{evento["fibras_g"]:.1f} ({evento["tipo_fibra"]})'
            self.ofertas_tabela.insert("","end",iid=f"oferta-{i}",values=(
                evento["instante"].strftime("%d/%m %H:%M"),
                f'{evento["suplemento"]} / {evento["refeicao"]}',dose,agua,agua_sep,carb,fibra))
        self._desenhar_grafico()

    def _desenhar_grafico(self):
        c=self.canvas;c.delete("all")
        w=max(c.winfo_width(),500);h=250
        esquerda,direita,topo,base=55,w-20,22,h-35
        datas_hgt=[datetime.fromisoformat(r[2]) for r in self.registros]
        datas_oferta=[e["instante"] for e in self.ofertas]
        todas=datas_hgt+datas_oferta
        if not todas:
            c.create_text(w/2,h/2,text="Sem medições ou ofertas com horário registrado.",
                          fill="#52645A",font=("Arial",12))
            return
        t0,t1=min(todas),max(todas)
        duracao=max((t1-t0).total_seconds(),3600)
        valores=[float(r[1]) for r in self.registros]
        minimo=min(0,min(valores)-20) if valores else 0
        maximo=max(200,max(valores)+20) if valores else 200
        for tick in range(int((minimo+19)//20*20),int(maximo)+1,20):
            y=base-(tick-minimo)/(maximo-minimo)*(base-topo)
            c.create_line(esquerda,y,direita,y,fill="#E5EAE7")
            c.create_text(esquerda-8,y,text=str(tick),anchor="e",fill="#52645A")
        c.create_text(12,12,text="mg/dL",anchor="nw",fill="#52645A")
        c.create_text(direita-175,12,text="HGT ●   Oferta ┆",anchor="ne",fill="#52645A")
        pontos=[]
        for dt,valor in zip(datas_hgt,valores):
            x=esquerda+(dt-t0).total_seconds()/duracao*(direita-esquerda)
            y=base-(valor-minimo)/(maximo-minimo)*(base-topo)
            pontos.extend((x,y))
        if len(pontos)>=4:c.create_line(*pontos,fill="#267B55",width=2,smooth=False)
        for idx,(x,y) in enumerate(zip(pontos[::2],pontos[1::2])):
            c.create_oval(x-4,y-4,x+4,y+4,fill="#D97706",outline="#FFFFFF",width=1)
            c.create_text(x,y-13,text=f"{valores[idx]:g}",fill="#26352C",font=("Arial",9))
        for evento in self.ofertas:
            dt=evento["instante"]
            x=esquerda+(dt-t0).total_seconds()/duracao*(direita-esquerda)
            c.create_line(x,topo+8,x,base,fill="#B45309",dash=(3,3),width=2)
            c.create_polygon(x-4,topo+4,x+4,topo+4,x,topo+12,fill="#B45309",outline="")
        for dt in (t0,t1):
            x=esquerda+(dt-t0).total_seconds()/duracao*(direita-esquerda)
            c.create_text(x,base+15,text=dt.strftime("%d/%m %H:%M"),
                          fill="#52645A",font=("Arial",8))

    def _dialogo(self, registro=None):
        win = ctk.CTkToplevel(self)
        win.title("Editar HGT" if registro else "Registrar HGT")
        win.geometry("420x430")
        win.transient(self.winfo_toplevel())
        win.grab_set()
        valor = ctk.StringVar(value=str(registro[1]) if registro else "")
        data = ctk.StringVar(value=datetime.fromisoformat(registro[2]).strftime("%Y-%m-%d") if registro else datetime.now().strftime("%Y-%m-%d"))
        hora = ctk.StringVar(value=datetime.fromisoformat(registro[2]).strftime("%H:%M") if registro else datetime.now().strftime("%H:%M"))
        contexto = ctk.StringVar(value=registro[3] if registro else "Aleatória")
        obs = ctk.StringVar(value=registro[4] or "" if registro else "")
        def campo(rotulo, var):
            ctk.CTkLabel(win, text=rotulo).pack(anchor="w", padx=22, pady=(9, 2))
            ctk.CTkEntry(win, textvariable=var, width=370).pack(padx=22)
        ctk.CTkLabel(win, text="Valor de HGT (mg/dL)").pack(anchor="w", padx=22, pady=(18,2))
        ctk.CTkEntry(win, textvariable=valor, width=370).pack(padx=22)
        campo("Data (AAAA-MM-DD)", data)
        campo("Horário (HH:MM)", hora)
        ctk.CTkLabel(win, text="Contexto").pack(anchor="w", padx=22, pady=(9,2))
        ctk.CTkOptionMenu(win, variable=contexto, values=list(CONTEXTOS), width=370).pack(padx=22)
        campo("Observações", obs)
        def salvar():
            try:
                mid = f"{data.get().strip()} {hora.get().strip()}"
                salvar_hgt(self.caminho_banco, self.id_paciente, valor.get().replace(",", "."),
                           mid, contexto.get(), obs.get(), registro[0] if registro else None)
            except Exception as exc:
                messagebox.showerror("HGT inválido", str(exc), parent=win)
                return
            win.destroy()
            self.atualizar()
        ctk.CTkButton(win, text="Salvar medição", command=salvar,
                      fg_color=tema.VERDE).pack(pady=18)

    def _novo(self):
        self._dialogo()

    def _editar(self):
        sel = self.tabela.selection()
        if not sel:
            messagebox.showinfo("Editar HGT", "Selecione uma medição.")
            return
        rid = int(sel[0])
        self._dialogo(next(r for r in self.registros if r[0] == rid))

    def _inativar(self):
        sel = self.tabela.selection()
        if not sel:
            messagebox.showinfo("Inativar HGT", "Selecione uma medição.")
            return
        rid = int(sel[0])
        if messagebox.askyesno("Inativar HGT", "O registro será ocultado da lista, mas preservado no banco. Continuar?"):
            inativar_hgt(self.caminho_banco, self.id_paciente, rid)
            self.atualizar()
