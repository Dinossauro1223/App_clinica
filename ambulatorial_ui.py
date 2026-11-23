# -*- coding: utf-8 -*-
"""Interface para anamnese guiada, medicamentos, metas e recomendações DOCX."""
import os
import sqlite3
import subprocess
from contextlib import closing
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import ambulatorial as amb

VERDE = "#1b5e20"
BOTAO = "#4caf50"
HOVER = "#388e3c"
BORDA = "#a5d6a7"
BRANCO = "#ffffff"

CAMPOS = {
    "História e objetivos": [
        ("queixa_principal", "Queixa principal/motivo da consulta", 3),
        ("objetivos", "Objetivos e expectativas do paciente", 2),
        ("historia_atual", "História da condição atual, evolução e tratamentos", 3),
        ("diagnosticos", "Diagnósticos e antecedentes clínicos relatados", 2),
        ("historico_familiar", "Histórico familiar relevante", 2),
    ],
    "Alimentação e rotina": [
        ("rotina", "Rotina diária e horários", 2), ("apetite", "Apetite e alterações recentes", 2),
        ("preferencias", "Preferências alimentares", 2), ("aversoes", "Aversões e restrições alimentares", 2),
        ("alergias_intolerancias", "Alergias/intolerâncias relatadas", 2),
        ("ingestao_hidrica", "Ingestão hídrica", 2), ("recordatorio_habitual", "Padrão alimentar habitual", 2),
    ],
    "Sinais e contexto": [
        ("sintomas_gastrointestinais", "Sintomas gastrointestinais", 2),
        ("mastigacao_degluticao", "Mastigação e deglutição", 2),
        ("funcao_intestinal", "Função intestinal/evacuação", 2), ("sono_estresse", "Sono/estresse", 2),
        ("atividade_fisica", "Atividade física e mobilidade", 2),
        ("contexto_social", "Contexto social e segurança alimentar", 2),
        ("observacoes", "Observações adicionais", 2),
    ],
}


class PainelConsultaEstruturada(ctk.CTkFrame):
    def __init__(self, master, db_path, pasta_dados, **kwargs):
        super().__init__(master, fg_color="#e8f5e9", corner_radius=8, **kwargs)
        self.db_path, self.pasta_dados = db_path, pasta_dados
        self.campos, self.medicamentos, self.metas, self.vars_docs = {}, [], [], {}
        ctk.CTkLabel(self, text="Anamnese guiada e plano de cuidado", text_color=VERDE,
                     font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=12, pady=(10, 3))
        self.tabs = ctk.CTkTabview(self, fg_color="#f1f8ea")
        self.tabs.pack(fill="both", expand=True, padx=8, pady=8)
        abas = {nome: self.tabs.add(nome) for nome in
                ("Anamnese", "Medicamentos", "Metas", "Recordatório 24 h", "Recomendações DOCX")}
        self._anamnese(abas["Anamnese"])
        self._medicamentos(abas["Medicamentos"])
        self._metas(abas["Metas"])
        self._recordatorio(abas["Recordatório 24 h"])
        self._documentos(abas["Recomendações DOCX"])

    def _anamnese(self, master):
        tabs = ctk.CTkTabview(master, fg_color="#e8f5e9")
        tabs.pack(fill="both", expand=True, padx=4, pady=4)
        for secao, campos in CAMPOS.items():
            aba = tabs.add(secao)
            scroll = ctk.CTkScrollableFrame(aba, fg_color="transparent")
            scroll.pack(fill="both", expand=True)
            for chave, rotulo, altura in campos:
                bloco = ctk.CTkFrame(scroll, fg_color="transparent")
                bloco.pack(fill="x", padx=6, pady=4)
                ctk.CTkLabel(bloco, text=rotulo, text_color=VERDE,
                             font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")
                campo = ctk.CTkTextbox(bloco, height=altura * 28, fg_color=BRANCO,
                                       border_width=1, border_color=BORDA, text_color="#263238")
                campo.pack(fill="x")
                self.campos[chave] = campo

    def _medicamentos(self, master):
        ctk.CTkLabel(master, text="Cada medicamento tem campos próprios. Registre o relato e confira com a prescrição.",
                     text_color="#455a64", wraplength=720).pack(anchor="w", padx=8, pady=8)
        self.box_med = ctk.CTkScrollableFrame(master, fg_color="transparent", height=235)
        self.box_med.pack(fill="both", expand=True, padx=6)
        ctk.CTkButton(master, text="+ Adicionar medicamento", command=self.adicionar_medicamento,
                      fg_color=BOTAO, hover_color=HOVER).pack(anchor="w", padx=8, pady=8)
        self.adicionar_medicamento()

    def adicionar_medicamento(self):
        linha = ctk.CTkFrame(self.box_med, fg_color=BRANCO)
        linha.pack(fill="x", pady=4)
        campos = {}
        specs = (("nome", "Medicamento", 155), ("dose", "Dose", 90), ("via", "Via", 75),
                 ("frequencia", "Frequência/horário", 125), ("indicacao", "Indicação", 125))
        for col, (chave, hint, largura) in enumerate(specs):
            campo = ctk.CTkEntry(linha, width=largura, placeholder_text=hint,
                                 fg_color=BRANCO, border_color=BORDA, text_color="#263238")
            campo.grid(row=0, column=col, padx=3, pady=6)
            campos[chave] = campo
        ctk.CTkButton(linha, text="×", width=30, fg_color="#c62828",
                      command=lambda f=linha: self._remover(self.medicamentos, f)).grid(row=0, column=5, padx=3)
        self.medicamentos.append((linha, campos))

    def _metas(self, master):
        ctk.CTkLabel(master, text="Metas são registradas separadamente e definidas pelo profissional.",
                     text_color="#455a64").pack(anchor="w", padx=8, pady=8)
        self.box_metas = ctk.CTkScrollableFrame(master, fg_color="transparent", height=235)
        self.box_metas.pack(fill="both", expand=True, padx=6)
        ctk.CTkButton(master, text="+ Adicionar meta", command=self.adicionar_meta,
                      fg_color=BOTAO, hover_color=HOVER).pack(anchor="w", padx=8, pady=8)
        self.adicionar_meta()

    def adicionar_meta(self):
        linha = ctk.CTkFrame(self.box_metas, fg_color=BRANCO)
        linha.pack(fill="x", pady=4)
        campos = {}
        specs = (("descricao", "Meta", 220), ("indicador", "Indicador/valor-alvo", 175),
                 ("prazo", "Prazo", 105), ("status", "Situação", 105))
        for col, (chave, hint, largura) in enumerate(specs):
            campo = ctk.CTkEntry(linha, width=largura, placeholder_text=hint,
                                 fg_color=BRANCO, border_color=BORDA, text_color="#263238")
            campo.grid(row=0, column=col, padx=3, pady=6)
            campos[chave] = campo
        ctk.CTkButton(linha, text="×", width=30, fg_color="#c62828",
                      command=lambda f=linha: self._remover(self.metas, f)).grid(row=0, column=4, padx=3)
        self.metas.append((linha, campos))

    @staticmethod
    def _remover(lista, frame):
        frame.destroy()
        lista[:] = [(f, c) for f, c in lista if f is not frame]

    def _recordatorio(self, master):
        ctk.CTkLabel(master, text="Opcional: horário/refeição, alimentos e bebidas, quantidades, preparo e local de consumo.",
                     text_color="#455a64", wraplength=720).pack(anchor="w", padx=8, pady=8)
        self.recordatorio = ctk.CTkTextbox(master, height=250, fg_color=BRANCO,
                                           border_width=1, border_color=BORDA, text_color="#263238")
        self.recordatorio.pack(fill="both", expand=True, padx=8, pady=8)

    def _documentos(self, master):
        ctk.CTkLabel(master, text="Cadastre documentos Word reutilizáveis e selecione os que serão associados a este paciente/consulta.",
                     text_color="#455a64", wraplength=720).pack(anchor="w", padx=8, pady=(8, 4))
        barra = ctk.CTkFrame(master, fg_color="transparent")
        barra.pack(fill="x", padx=8, pady=4)
        ctk.CTkButton(barra, text="Cadastrar novo DOCX", command=self._novo_docx,
                      fg_color=BOTAO, hover_color=HOVER).pack(side="left", padx=(0, 6))
        ctk.CTkButton(barra, text="Atualizar lista", command=self._listar_docs,
                      fg_color="#607d8b").pack(side="left")
        self.conduta_doc = ctk.CTkEntry(master, placeholder_text="Conduta/plano relacionado aos documentos (opcional)",
                                        fg_color=BRANCO, border_color=BORDA, text_color="#263238")
        self.conduta_doc.pack(fill="x", padx=8, pady=4)
        self.lista_docs = ctk.CTkScrollableFrame(master, fg_color="transparent", height=190)
        self.lista_docs.pack(fill="both", expand=True, padx=6, pady=4)
        self._listar_docs()

    def _listar_docs(self):
        for widget in self.lista_docs.winfo_children():
            widget.destroy()
        self.vars_docs = {}
        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                docs = amb.listar_recomendacoes(conn)
        except sqlite3.Error as exc:
            ctk.CTkLabel(self.lista_docs, text=f"Erro ao carregar recomendações: {exc}").pack(anchor="w")
            return
        if not docs:
            ctk.CTkLabel(self.lista_docs, text="Biblioteca vazia. Cadastre um DOCX para começar.",
                         text_color="#455a64").pack(anchor="w", pady=8)
            return
        for doc in docs:
            var = tk.BooleanVar(value=False)
            self.vars_docs[doc["id_recomendacao"]] = var
            linha = ctk.CTkFrame(self.lista_docs, fg_color=BRANCO)
            linha.pack(fill="x", pady=3)
            ctk.CTkCheckBox(linha, text=f'{doc["titulo"]} — {doc["caso_clinico"]}',
                            variable=var, text_color="#263238").pack(side="left", padx=8, pady=6)
            ctk.CTkButton(linha, text="Abrir", width=55, fg_color="#607d8b",
                          command=lambda d=doc: self._abrir_docx(d)).pack(side="right", padx=6, pady=4)

    def _novo_docx(self):
        app = self.winfo_toplevel()
        painel_externo = hasattr(app, "abrir_painel_lateral")
        if painel_externo:
            container = app.abrir_painel_lateral("Cadastrar recomendação DOCX", lambda: None)
        else:
            container = self
        painel = ctk.CTkFrame(container, fg_color="transparent")
        painel.pack(fill="both", expand=True)
        cabecalho = ctk.CTkFrame(painel, fg_color="transparent")
        cabecalho.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(cabecalho, text="Cadastrar recomendação DOCX",
                     font=ctk.CTkFont(size=18, weight="bold"), text_color=VERDE).pack(side="left")

        def fechar():
            if painel_externo:
                app.fechar_painel_lateral(container)
            else:
                painel.destroy()

        ctk.CTkButton(cabecalho, text="Fechar guia", width=100, command=fechar).pack(side="right")
        entradas = {}
        for chave, rotulo, dica in (("titulo", "Título", "Ex.: Orientações nutricionais"),
                                     ("caso", "Caso clínico/situação de uso", "Ex.: Diabetes tipo 2"),
                                     ("tags", "Palavras-chave (opcional)", "Ex.: DM; educação alimentar")):
            ctk.CTkLabel(painel, text=rotulo, text_color=VERDE).pack(anchor="w", padx=14, pady=(10, 2))
            campo = ctk.CTkEntry(painel, width=510, placeholder_text=dica,
                                 fg_color=BRANCO, border_color=BORDA, text_color="#263238")
            campo.pack(padx=14)
            entradas[chave] = campo
        arquivo = {"path": ""}
        rotulo = ctk.CTkLabel(painel, text="Nenhum arquivo selecionado", wraplength=500)
        rotulo.pack(pady=8)

        def escolher():
            path = filedialog.askopenfilename(parent=painel, title="Selecione o DOCX",
                                              filetypes=[("Documento Word", "*.docx")])
            if path:
                arquivo["path"] = path
                rotulo.configure(text=os.path.basename(path))

        ctk.CTkButton(painel, text="Selecionar .docx", command=escolher).pack()

        def salvar():
            try:
                if not arquivo["path"]:
                    raise amb.ErroAmbulatorial("Selecione o documento DOCX.")
                with closing(sqlite3.connect(self.db_path)) as conn:
                    with conn:
                        amb.cadastrar_recomendacao_docx(conn, arquivo["path"], self.pasta_dados,
                            entradas["titulo"].get(), entradas["caso"].get(), entradas["tags"].get())
                fechar()
                self._listar_docs()
                messagebox.showinfo("Biblioteca", "Recomendação cadastrada.", parent=self)
            except (amb.ErroAmbulatorial, sqlite3.Error, OSError) as exc:
                messagebox.showerror("Não foi possível cadastrar", str(exc), parent=painel)

        ctk.CTkButton(painel, text="Salvar na biblioteca", command=salvar,
                      fg_color=BOTAO, hover_color=HOVER).pack(pady=12)

    def _abrir_docx(self, doc):
        try:
            path = amb.caminho_recomendacao(self.pasta_dados, doc["arquivo_relativo"])
            if os.name == "nt":
                os.startfile(str(path))
            elif os.sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except (amb.ErroAmbulatorial, OSError) as exc:
            messagebox.showerror("Abrir DOCX", str(exc), parent=self)

    def dados(self):
        return {
            "anamnese_guiada": {k: w.get("1.0", "end-1c").strip() for k, w in self.campos.items()},
            "recordatorio_24h": self.recordatorio.get("1.0", "end-1c").strip(),
            "medicamentos": [{k: w.get().strip() for k, w in campos.items()} for _, campos in self.medicamentos],
            "metas": [{k: w.get().strip() for k, w in campos.items()} for _, campos in self.metas],
            "recomendacoes_ids": [rid for rid, v in self.vars_docs.items() if v.get()],
            "conduta_recomendacao": self.conduta_doc.get().strip(),
        }


class DialogoAssociacoesExames(ctk.CTkFrame):
    """Gerencia exames complementares em uma guia lateral, sem abrir Toplevel."""
    def __init__(self, master, db_path):
        try:
            app = master.winfo_toplevel()
        except Exception:
            app = master
        self.app = app
        self._painel_externo = bool(app and hasattr(app, "abrir_painel_lateral"))
        if self._painel_externo:
            self._painel_frame = app.abrir_painel_lateral("Associações de exames", lambda: None)
            pai = self._painel_frame
        else:
            self._painel_frame = None
            pai = getattr(master, "area_principal", master)
        super().__init__(pai, fg_color="transparent")
        self.pack(fill="both", expand=True)
        self.db_path = db_path
        cabecalho = ctk.CTkFrame(self, fg_color="transparent")
        cabecalho.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(cabecalho, text="Associações de exames",
                     font=ctk.CTkFont(size=18, weight="bold"), text_color=VERDE).pack(side="left")
        ctk.CTkButton(cabecalho, text="Fechar guia", width=90,
                      command=self.destroy, fg_color=BOTAO, hover_color=HOVER).pack(side="right")
        with closing(sqlite3.connect(db_path)) as conn:
            rows = conn.execute("SELECT id_exame, nome_amigavel FROM Exames_Catalogo ORDER BY nome_amigavel").fetchall()
        self.exames = {f"{nome} ({codigo})": codigo for codigo, nome in rows}
        if not self.exames:
            ctk.CTkLabel(self, text="Cadastre exames primeiro.").pack(padx=20, pady=20)
            return
        ctk.CTkLabel(self, text="Exame de origem", text_color=VERDE).pack(anchor="w", padx=14, pady=(12, 2))
        self.combo_exame = ctk.CTkComboBox(self, values=list(self.exames), width=520,
                                           command=lambda _: self.atualizar())
        self.combo_exame.pack(anchor="w", padx=14)
        self.combo_exame.set(list(self.exames)[0])
        ctk.CTkLabel(self, text="Tipo de associação", text_color=VERDE).pack(anchor="w", padx=14, pady=(8, 2))
        self.combo_tipo = ctk.CTkComboBox(self, width=290,
            values=["Exame recomendado", "Diagnóstico clínico", "Diagnóstico nutricional"])
        self.combo_tipo.pack(anchor="w", padx=14)
        self.combo_tipo.set("Exame recomendado")
        self.valor = ctk.CTkEntry(self, width=520, placeholder_text="ID do exame sugerido ou nome do diagnóstico",
                                  fg_color=BRANCO, border_color=BORDA, text_color="#263238")
        self.valor.pack(anchor="w", padx=14, pady=6)
        self.justificativa = ctk.CTkEntry(self, width=680, placeholder_text="Justificativa da associação (opcional)",
                                          fg_color=BRANCO, border_color=BORDA, text_color="#263238")
        self.justificativa.pack(anchor="w", padx=14, pady=4)
        self.fonte = ctk.CTkEntry(self, width=680, placeholder_text="Fonte/referência (opcional)",
                                  fg_color=BRANCO, border_color=BORDA, text_color="#263238")
        self.fonte.pack(anchor="w", padx=14, pady=4)
        ctk.CTkButton(self, text="Adicionar associação", command=self.salvar,
                      fg_color=BOTAO, hover_color=HOVER).pack(anchor="w", padx=14, pady=8)
        self.lista = ctk.CTkTextbox(self, height=220, fg_color=BRANCO, text_color="#263238")
        self.lista.pack(fill="both", expand=True, padx=14, pady=10)
        self.atualizar()

    def atualizar(self):
        if not hasattr(self, "lista"):
            return
        codigo = self.exames.get(self.combo_exame.get())
        with closing(sqlite3.connect(self.db_path)) as conn:
            itens = amb.associacoes_do_exame(conn, codigo)
            nomes = {r[0]: r[1] for r in conn.execute("SELECT id_exame,nome_amigavel FROM Exames_Catalogo")}
        self.lista.delete("1.0", "end")
        for item in itens:
            tipo = {"exame_recomendado": "Exame recomendado", "diagnostico_clinico": "Diagnóstico clínico",
                    "diagnostico_nutricional": "Diagnóstico nutricional"}.get(item["tipo_associacao"])
            valor = item["valor_relacionado"]
            if item["tipo_associacao"] == "exame_recomendado":
                valor = f"{nomes.get(valor, valor)} ({valor})"
            self.lista.insert("end", f"• {tipo}: {valor}\n")
            if item["justificativa"]:
                self.lista.insert("end", f"  Justificativa: {item['justificativa']}\n")
            if item["fonte"]:
                self.lista.insert("end", f"  Fonte: {item['fonte']}\n")
            self.lista.insert("end", "\n")

    def salvar(self):
        tipo = {"Exame recomendado": "exame_recomendado", "Diagnóstico clínico": "diagnostico_clinico",
                "Diagnóstico nutricional": "diagnostico_nutricional"}.get(self.combo_tipo.get())
        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                with conn:
                    amb.salvar_associacao_exame(conn, self.exames.get(self.combo_exame.get()), tipo,
                        self.valor.get(), self.justificativa.get(), self.fonte.get())
            for campo in (self.valor, self.justificativa, self.fonte):
                campo.delete(0, "end")
            self.atualizar()
        except (amb.ErroAmbulatorial, sqlite3.Error) as exc:
            messagebox.showerror("Associação não salva", str(exc), parent=self)

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
            except Exception:
                pass
        return super().destroy()
