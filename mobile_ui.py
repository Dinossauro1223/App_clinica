# -*- coding: utf-8 -*-
"""Tela 'Mobile (copa)' do NutriLab desktop (criada em 12/11/2026).

Receber o que a copa registrou no celular (o nutricionista confere antes de entrar no mapa) e enviar o mapa do dia para a copa.
Regras e tabelas: docs/mobile/INTEGRACAO_DESKTOP.md. A tela também abre sozinha:  python mobile_ui.py
"""
import os
import socket
import webbrowser
from datetime import date, datetime, timedelta, timezone
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

import integracao_mobile as im
import mapa_db as mdb
import ui_workers
import tema
from mobile import servidor as servidor_mobile

VERDE_ESC, VERDE, VERDE_HOVER = tema.VERDE_ESC, tema.VERDE, tema.VERDE_HOVER
CINZA, CINZA_HOVER, AZUL, AZUL_HOVER, LARANJA, LARANJA_HOVER = (
    tema.SUAVE, tema.SUAVE, tema.AZUL, tema.AZUL_HOVER, tema.LARANJA, tema.LARANJA
)
TIPOS = {"novo": "Novo paciente", "alterado": "Alterado", "troca": "Troca de paciente", "liberar": "Leito liberado"}
ROTULOS = {"nome_paciente": "nome", "idade_anos": "idade", "idade_meses": "meses", "acompanhante": "acompanhante",
           "obs_sim": "gosta", "obs_nao": "não aceita", "consistencia": "consistência", "via": "via"}
TODOS = "Todos os setores"


def _lado_mais_novo(pc, mobile):
    """Retorna pc/mobile/igual sem misturar datetimes com e sem fuso."""
    if not pc and not mobile:
        return "igual"
    if not pc:
        return "mobile"
    if not mobile:
        return "pc"
    try:
        a = datetime.fromisoformat(str(pc).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(mobile).replace("Z", "+00:00"))
        fuso = timezone(timedelta(hours=-3))
        if a.tzinfo is None:
            a = a.replace(tzinfo=fuso) if fuso else a
        if b.tzinfo is None:
            b = b.replace(tzinfo=fuso) if fuso else b
        return "pc" if a > b else "mobile" if b > a else "igual"
    except (TypeError, ValueError):
        a, b = str(pc).replace("T", " "), str(mobile).replace("T", " ")
        return "pc" if a > b else "mobile" if b > a else "igual"


def _btn(master, texto, comando, largura=160, cor=VERDE, hover=VERDE_HOVER):
    return ctk.CTkButton(master, text=texto, command=comando, width=largura, height=34, fg_color=cor, hover_color=hover,
                         font=ctk.CTkFont(size=13, weight="bold"))


def _resumo(d, extra=None):
    if not d or not d.get("nome_paciente"):
        return "(sem paciente)"
    idade = ("%sa" % d["idade_anos"]) if d.get("idade_anos") is not None else ""
    if d.get("idade_meses"):
        idade += " %sm" % d["idade_meses"]
    partes = [d["nome_paciente"] + (", " + idade.strip() if idade else "")]
    dieta = "Enteral" if d.get("via") == "Enteral" else d.get("consistencia")
    if dieta:
        partes.append(dieta)
    if extra and extra.get("dieta") and not dieta:
        partes.append("dieta: " + extra["dieta"])
    if d.get("acompanhante"):
        partes.append("acompanhante")
    if d.get("obs_sim"):
        partes.append("gosta: " + d["obs_sim"])
    if d.get("obs_nao"):
        partes.append("não aceita: " + d["obs_nao"])
    if extra and extra.get("diagnostico"):
        partes.append("diag.: " + extra["diagnostico"])
    return " · ".join(partes)


class MobileUI:
    """Tela 'Mobile (copa)'. `app` precisa de limpar_area_principal() e area_principal (como o AppClinica)."""

    def __init__(self, app, db_path, base_dir):
        self.app, self.db, self.base_dir = app, db_path, base_dir
        self.data = date.today()
        self.propostas = {}
        self.setores = []
        self.mobile_db = im.caminho_mobile_db(db_path, base_dir)
        self._atualizando_banco = False
        self._verificando = False

    # --------------------------------------------------------------- montagem
    def mostrar(self):
        self.app.limpar_area_principal()
        area = self.app.area_principal
        self.mobile_db = im.caminho_mobile_db(self.db, self.base_dir)
        self.setores = mdb.listar_setores(self.db)

        topo = ctk.CTkFrame(area, fg_color="transparent")
        topo.pack(fill="x", padx=20, pady=(15, 2))
        ctk.CTkLabel(topo, text="Mobile (copa)", font=ctk.CTkFont(size=24, weight="bold"), text_color=VERDE_ESC).pack(side="left")
        _btn(topo, "Abrir painel web", self._abrir_painel, 140, CINZA, CINZA_HOVER).pack(side="right")
        _btn(topo, "Trocar banco", self._trocar_banco, 120, CINZA, CINZA_HOVER).pack(side="right", padx=6)
        self.lbl_banco = ctk.CTkLabel(area, text="", font=ctk.CTkFont(size=12), text_color=tema.SUAVE, anchor="w", justify="left")
        self.lbl_banco.pack(fill="x", padx=22)

        barra = ctk.CTkFrame(area, fg_color="transparent")
        barra.pack(fill="x", padx=20, pady=(8, 2))
        ctk.CTkLabel(barra, text="Dia:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        _btn(barra, "◀", lambda: self._mudar_dia(-1), 36).pack(side="left", padx=(6, 2))
        self.ent_data = ctk.CTkEntry(barra, width=110, justify="center")
        self.ent_data.pack(side="left", padx=2)
        self.ent_data.bind("<Return>", lambda _e: self._aplicar_data())
        _btn(barra, "▶", lambda: self._mudar_dia(1), 36).pack(side="left", padx=2)
        _btn(barra, "Hoje", self._hoje, 70, CINZA, CINZA_HOVER).pack(side="left", padx=6)
        ctk.CTkLabel(barra, text="Setor (para enviar):", font=ctk.CTkFont(size=13)).pack(side="left", padx=(20, 4))
        self.cb_setor = ctk.CTkComboBox(barra, values=[TODOS] + [s["nome"] for s in self.setores], width=190, state="readonly")
        self.cb_setor.set(TODOS)
        self.cb_setor.pack(side="left")

        acoes = ctk.CTkFrame(area, fg_color="transparent")
        acoes.pack(fill="x", padx=20, pady=(8, 2))
        _btn(acoes, "Verificar o que chegou do mobile", self._verificar, 250).pack(side="left")
        _btn(acoes, "Comparar PC × Mobile", self._comparar, 190, CINZA, CINZA_HOVER).pack(side="left", padx=8)
        _btn(acoes, "Enviar mapa completo", self._enviar, 190, AZUL, AZUL_HOVER).pack(side="left", padx=8)
        self.lbl_status = ctk.CTkLabel(area, text='Use "Verificar" para ver o que a copa registrou no celular.', anchor="w",
                                       font=ctk.CTkFont(size=13), text_color=VERDE_ESC)
        self.lbl_status.pack(fill="x", padx=22, pady=(4, 2))

        quadro = ctk.CTkFrame(area)
        quadro.pack(fill="both", expand=True, padx=20, pady=4)
        cols = (("setor", "Setor", 110), ("leito", "Leito", 60), ("tipo", "Situação", 150), ("campos", "O que muda", 170),
                ("desktop", "No desktop", 250), ("mobile", "No mobile", 320))
        self.tree = ttk.Treeview(quadro, columns=[c[0] for c in cols], show="headings", height=9, selectmode="extended")
        for chave, titulo, largura in cols:
            self.tree.heading(chave, text=titulo)
            self.tree.column(chave, width=largura, anchor="w")
        sb = ttk.Scrollbar(quadro, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        dec = ctk.CTkFrame(area, fg_color="transparent")
        dec.pack(fill="x", padx=20, pady=2)
        _btn(dec, "Aplicar marcados", self._aplicar, 170).pack(side="left")
        _btn(dec, "Ignorar marcados", self._ignorar, 170, LARANJA, LARANJA_HOVER).pack(side="left", padx=8)
        ctk.CTkLabel(dec, text="Marque com Ctrl/Shift. Trocar de paciente zera os dados clínicos do leito; ignorar uma "
                               "correção da copa a recusa no mobile.", font=ctk.CTkFont(size=12), text_color=tema.SUAVE,
                     wraplength=520, justify="left").pack(side="left", padx=10)
        self.txt = ctk.CTkTextbox(area, height=130, font=ctk.CTkFont(size=12))
        self.txt.pack(fill="x", padx=20, pady=(4, 12))
        self._mostrar_data()
        self._atualizar_banco()

    def _atualizar_banco(self):
        """Atualiza o catálogo auxiliar sem bloquear a tela Mobile."""
        if self._atualizando_banco:
            return
        self._atualizando_banco = True
        self.lbl_banco.configure(text="Verificando banco do Mobile…")
        mobile_db = self.mobile_db
        def trabalho():
            try:
                with socket.create_connection(("127.0.0.1", 8765), timeout=1.0):
                    servidor = "ATIVO — celulares: http://%s:8765" % servidor_mobile.ip_lan()
            except OSError:
                servidor = "INATIVO — o servidor não responde na porta 8765"
            if not os.path.exists(mobile_db):
                return "%s; banco não encontrado: %s" % (servidor, mobile_db)
            qtd = im.sincronizar_catalogo_suplementos(self.db, mobile_db)
            return "%s; banco encontrado; catálogo de %d suplemento(s) atualizado" % (servidor, qtd)
        def sucesso(achou):
            if self._widgets_disponiveis():
                self.lbl_banco.configure(text="Banco do mobile: %s (%s)" % (mobile_db, achou))
        def erro(exc):
            if self._widgets_disponiveis():
                self.lbl_banco.configure(text="Banco do mobile: %s (falha ao atualizar catálogo: %s)" % (mobile_db, exc))
        def finalizar():
            self._atualizando_banco = False
        return ui_workers.executar_em_segundo_plano(
            self.app, trabalho, ao_sucesso=sucesso, ao_erro=erro, ao_finalizar=finalizar,
            nome="nutrilab-mobile-atualizar-catalogo")

    def _widgets_disponiveis(self):
        try:
            return bool(self.lbl_banco and self.lbl_banco.winfo_exists())
        except Exception:
            return False

    # ----------------------------------------------------------------- datas
    def _mostrar_data(self):
        self.ent_data.delete(0, "end")
        self.ent_data.insert(0, mdb.iso_para_br(self.data.isoformat()))

    def _aplicar_data(self):
        try:
            self.data = date.fromisoformat(mdb.data_br_para_iso(self.ent_data.get()))
        except ValueError:
            messagebox.showwarning("Mobile", "Data inválida. Use DD/MM/AAAA.")
            self._mostrar_data()

    def _mudar_dia(self, delta):
        self.data += timedelta(days=delta)
        self._mostrar_data()

    def _hoje(self):
        self.data = date.today()
        self._mostrar_data()

    # --------------------------------------------------------------- receber
    def _comparar(self):
        """Mostra lado a lado o estado local e a fotografia recebida do Mobile."""
        iso = self.data.isoformat()
        nome = self.cb_setor.get()
        sid = next((s["id_setor"] for s in self.setores if s["nome"] == nome), None)
        if sid is None:
            messagebox.showinfo("Comparar mapas", "Escolha um setor específico para comparar os mapas.", parent=self.app)
            return
        try:
            pc = {x["leito"]["codigo"]: x["registro"] for x in mdb.mapa_do_dia(self.db, iso, sid)}
            with servidor_mobile.LOCK:
                c = servidor_mobile.conectar(self.mobile_db)
                try:
                    servidor_mobile.migrar(c)
                    mobile = {x["codigo"]: x for x in servidor_mobile.linhas_mapa(c, sid, iso)}
                finally:
                    c.close()
        except Exception as e:
            messagebox.showwarning("Comparar mapas", "Não foi possível ler a cópia do Mobile:\n%s" % e, parent=self.app)
            return
        janela = ctk.CTkToplevel(self.app)
        janela.title("Mapa — PC × Mobile — %s" % mdb.iso_para_br(iso))
        janela.geometry("1180x620")
        janela.transient(self.app)
        ctk.CTkLabel(janela, text="Comparação de estado", font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=VERDE_ESC).pack(anchor="w", padx=18, pady=(16, 2))
        ctk.CTkLabel(janela, text="O timestamp mais recente é destacado. Nenhum lado é sobrescrito automaticamente.",
                     text_color=tema.SUAVE).pack(anchor="w", padx=18, pady=(0, 10))
        corpo = ctk.CTkFrame(janela, fg_color="transparent"); corpo.pack(fill="both", expand=True, padx=14, pady=4)
        pa = ctk.CTkFrame(corpo); pb = ctk.CTkFrame(corpo); pa.pack(side="left", fill="both", expand=True, padx=(0,6)); pb.pack(side="left", fill="both", expand=True, padx=(6,0))
        ctk.CTkLabel(pa, text="ESTADO ATUAL NO PC", font=ctk.CTkFont(size=14, weight="bold"), text_color=VERDE_ESC).pack(anchor="w", padx=10, pady=8)
        ctk.CTkLabel(pb, text="ESTADO RECEBIDO DO MOBILE / COPA", font=ctk.CTkFont(size=14, weight="bold"), text_color=AZUL).pack(anchor="w", padx=10, pady=8)
        cols=("leito","paciente","atualizado","origem")
        trees=[]
        for pai in (pa,pb):
            t=ttk.Treeview(pai,columns=cols,show="headings")
            for k,tit,w in (("leito","Leito",70),("paciente","Paciente",240),("atualizado","Última alteração",150),("origem","Origem",120)):
                t.heading(k,text=tit);t.column(k,width=w,anchor="w")
            t.tag_configure("mais_novo",foreground=tema.cor_atual(tema.VERDE_ESC))
            t.tag_configure("mais_antigo",foreground=tema.cor_atual(tema.SUAVE))
            t.pack(fill="both",expand=True,padx=8,pady=(0,8));trees.append(t)
        todos=sorted(set(pc)|set(mobile), key=lambda x:(len(x),x))
        for cod in todos:
            pr=pc.get(cod) or {}
            mr=mobile.get(cod) or {}
            pt=pr.get("atualizado_em") or ""
            mt=mr.get("atualizado_em") or ""
            vencedor = _lado_mais_novo(pt, mt)
            trees[0].insert("", "end", values=(cod,pr.get("nome_paciente") or "— vago —",pt[11:19] if len(pt)>18 else pt,"PC"), tags=("mais_novo" if vencedor=="pc" else "mais_antigo",))
            trees[1].insert("", "end", values=(cod,mr.get("nome") or "— vago —",mt[11:19] if len(mt)>18 else mt,"Mobile/Copa"), tags=("mais_novo" if vencedor=="mobile" else "mais_antigo",))
        rod=ctk.CTkFrame(janela,fg_color="transparent");rod.pack(fill="x",padx=18,pady=(4,14))
        _btn(rod,"Fechar",janela.destroy,110,CINZA,CINZA_HOVER).pack(side="right")
        _tornar = getattr(janela,"lift",None)
        if _tornar: janela.lift()

    def _verificar(self):
        """Lê o Mobile e concilia os dados em segundo plano; widgets só mudam no thread do Tk."""
        if self._verificando:
            return
        iso = self.data.isoformat()
        mobile_db = self.mobile_db
        self._verificando = True
        self.lbl_status.configure(text="Consultando alterações recebidas do Mobile…")
        def trabalho():
            ex = im.ler_mobile(mobile_db, iso)
            props = im.propostas_mapa(self.db, ex)
            im.importar_refeicoes(self.db, ex)
            im.importar_estoque(self.db, ex)
            pendentes = len([k for k in ex.get("correcoes_pendentes", []) if k["tipo"] != "mapa"])
            return props, pendentes
        def sucesso(resultado):
            if not self._widgets_disponiveis():
                return
            props, pendentes = resultado
            self._preencher(props, iso)
            self._resumo_texto(iso, pendentes)
            self.lbl_status.configure(text=("%d item(ns) do mapa para conferir." % len(props)) if props else "Nada novo no mapa.")
        def erro(exc):
            if self._widgets_disponiveis():
                messagebox.showwarning("Mobile", str(exc))
                self.lbl_status.configure(text="Não foi possível consultar o Mobile.")
        def finalizar():
            self._verificando = False
        return ui_workers.executar_em_segundo_plano(
            self.app, trabalho, ao_sucesso=sucesso, ao_erro=erro, ao_finalizar=finalizar,
            nome="nutrilab-mobile-verificar")

    def _preencher(self, props, iso):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.propostas, marcar = {}, []
        for p in props:
            iid = "%s|%s" % (p["data"], p["chave"])
            self.propostas[iid] = p
            setor = p["setor"] + ("" if p["data"] == iso else " (%s)" % mdb.iso_para_br(p["data"]))
            situacao = TIPOS[p["tipo"]] + (" · correção da copa" if p.get("id_correcao") else "")
            self.tree.insert("", "end", iid=iid, values=(setor, p["leito"], situacao, ", ".join(ROTULOS.get(k, k) for k in p["campos"]),
                                                         _resumo(p["desktop"]), _resumo(p["mobile"], p["extra"])))
            if p["padrao"]:
                marcar.append(iid)
        if marcar:
            self.tree.selection_set(marcar)

    def _resumo_texto(self, iso, outras_correcoes):
        r = im.resumo(self.db, iso)
        linhas = ["Refeições contadas em %s:" % mdb.iso_para_br(iso)]
        linhas += ["  %s: %s %g" % (x["setor"], x["refeicao"], x["qtd"]) for x in r["refeicoes"]] or ["  (nenhuma)"]
        linhas.append("Estoques:")
        linhas += ["  %s: %d item(ns) contados, última atualização %s" % (x["estoque"], x["itens"], (x["ultima"] or "")[11:16])
                   for x in r["estoques"]] or ["  (nenhum)"]
        linhas.append("Reposições do dia: %d (%d com saldo insuficiente na origem)" % (r["movimentos"], r["divergentes"]))
        if outras_correcoes:
            linhas.append("Correções de refeição/estoque aguardando no painel web do mobile: %d" % outras_correcoes)
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", "\n".join(linhas))
        self.txt.configure(state="disabled")

    def _selecionadas(self):
        return [self.propostas[i] for i in self.tree.selection() if i in self.propostas]

    def _aplicar(self):
        sel = self._selecionadas()
        if not sel:
            messagebox.showinfo("Mobile", "Selecione os itens que deseja aplicar.")
            return
        riscos = [p for p in sel if p["tipo"] in ("troca", "liberar")]
        if riscos and not messagebox.askyesno(
                "Confirmar", "%d item(ns) trocam o paciente do leito (zera os dados clínicos dele) ou liberam o leito "
                             "(apaga o registro do dia). Continuar?" % len(riscos)):
            return
        lms = getattr(getattr(self.app, "mapa", None), "lms", None)
        try:
            res = im.aplicar_mapa(self.db, sel, self.mobile_db, mdb.obter_config(self.db, "criterio_idoso", "lipschitz"), lms)
        except im.ErroMobile as e:
            messagebox.showwarning("Mobile", str(e))
            return
        if res["erros"]:
            messagebox.showwarning("Mobile", "Alguns itens não foram aplicados:\n" + "\n".join(res["erros"]))
        self._verificar()
        self.lbl_status.configure(text="%d item(ns) aplicado(s) ao mapa." % res["aplicados"])

    def _ignorar(self):
        sel = self._selecionadas()
        if not sel:
            messagebox.showinfo("Mobile", "Selecione os itens que deseja ignorar.")
            return
        try:
            im.ignorar_mapa(self.db, sel, self.mobile_db)
        except im.ErroMobile as e:
            messagebox.showwarning("Mobile", str(e))
            return
        self._verificar()
        self.lbl_status.configure(text="%d item(ns) ignorado(s)." % len(sel))

    # ---------------------------------------------------------------- enviar
    def _enviar(self):
        iso, nome = self.data.isoformat(), self.cb_setor.get()
        id_setor = next((s["id_setor"] for s in self.setores if s["nome"] == nome), None)
        try:
            pendentes = im.propostas_mapa(self.db, im.ler_mobile(self.mobile_db, iso))
        except im.ErroMobile as e:
            messagebox.showwarning("Mobile", str(e))
            return
        aviso = ("\n\nATENÇÃO: há %d alteração(ões) da copa que você ainda não conferiu; enviar agora pode sobrescrevê-las."
                 % len(pendentes)) if pendentes else ""
        if not messagebox.askyesno("Enviar para a copa", "Enviar o mapa de %s (%s) para a copa?\nAs copeiras receberão um aviso "
                                   "com os leitos alterados.%s" % (mdb.iso_para_br(iso), nome, aviso)):
            return
        try:
            res = im.enviar_mapa(self.db, self.mobile_db, iso, id_setor)
        except im.ErroMobile as e:
            messagebox.showwarning("Mobile", str(e))
            return
        total = sum(r["leitos"] for r in res)
        detalhe = ", ".join("%s %d" % (r["setor"], r["leitos"]) for r in res if r["leitos"])
        self.lbl_status.configure(text=("Enviado para a copa: %d leito(s) alterado(s) (%s)." % (total, detalhe)) if total
                                  else "O mobile já estava igual ao mapa do desktop: nada a avisar.")

    # ------------------------------------------------------------------ outros
    def _abrir_painel(self):
        webbrowser.open("http://localhost:8765")

    def _trocar_banco(self):
        caminho = filedialog.askopenfilename(title="Banco do servidor mobile (mobile.db)",
                                             filetypes=[("Banco do mobile", "*.db"), ("Todos os arquivos", "*.*")])
        if caminho:
            mdb.salvar_config(self.db, "mobile_db", caminho)
            self.mostrar()


if __name__ == "__main__":  # abre a tela sozinha, sem o programa principal
    base = os.path.dirname(os.path.abspath(__file__))
    banco = os.path.join(base, "clinica.db")
    mdb.inicializar(banco)

    class _Janela(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.title("NutriLab - Mobile (copa)")
            self.geometry("1100x760")
            self.area_principal = ctk.CTkFrame(self, fg_color="transparent")
            self.area_principal.pack(fill="both", expand=True)

        def limpar_area_principal(self):
            for w in self.area_principal.winfo_children():
                w.destroy()

    janela = _Janela()
    MobileUI(janela, banco, base).mostrar()
    janela.mainloop()
