# -*- coding: utf-8 -*-
"""Tela enxuta de configurações visuais para o NutriLab."""
from __future__ import annotations

import json
import os
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
import db_service
import tema
import nrs2002 as nrs

CAMINHO = os.path.join(os.path.expanduser("~"), ".nutrilab", "preferencias.json")

def _ler():
    try:
        with open(CAMINHO, encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}

def _salvar(dados):
    try:
        os.makedirs(os.path.dirname(CAMINHO), exist_ok=True)
        with open(CAMINHO, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except OSError:
        return False
    return True

class ConfiguracoesUI:
    """Renderiza opções de aparência e grava a preferência local do usuário."""
    OPCOES = {"Claro": "Light", "Escuro": "Dark", "Sistema": "System"}

    def __init__(self, app):
        self.app = app

    def mostrar(self):
        raiz = self.app.area_principal
        self.app.limpar_area_principal()
        ctk.CTkLabel(raiz, text="Configurações", font=tema.fonte(24, "bold"),
                      text_color=tema.VERDE).pack(anchor="w", padx=24, pady=(22, 8))
        card = ctk.CTkFrame(raiz, fg_color=tema.BRANCO, border_width=1,
                           border_color=tema.BORDA, corner_radius=12)
        card.pack(fill="x", padx=24, pady=12)
        ctk.CTkLabel(card, text="Aparência do aplicativo", font=tema.fonte(16, "bold"),
                     text_color=tema.TEXTO).pack(anchor="w", padx=18, pady=(18, 6))
        ctk.CTkLabel(card, text="Escolha como o NutriLab será exibido. As telas e tabelas acompanham a paleta selecionada; o modo Sistema segue a aparência do sistema operacional.",
                     font=tema.fonte(13), text_color=tema.SUAVE).pack(anchor="w", padx=18, pady=(0, 10))
        dados = _ler()
        atual = dados.get("aparencia", "Light")
        escolha = next((nome for nome, modo in self.OPCOES.items() if modo == atual), "Claro")
        seletor = ctk.CTkSegmentedButton(
            card, values=list(self.OPCOES), command=self._aplicar,
            selected_color=tema.VERDE, selected_hover_color=tema.VERDE_HOVER,
            unselected_color=tema.BRANCO, unselected_hover_color=tema.BORDA,
            text_color=tema.TEXTO, text_color_disabled=tema.SUAVE,
            corner_radius=8, border_width=1
        )
        seletor.set(escolha)
        seletor.pack(anchor="w", padx=18, pady=(0, 16))
        self.lbl_status = ctk.CTkLabel(card, text="", font=tema.fonte(12), text_color=tema.SUAVE)
        self.lbl_status.pack(anchor="w", padx=18, pady=(0, 12))
        self._nrs(raiz)
        self._equipe(raiz)
        self._backups(raiz)
        ctk.CTkButton(raiz, text="Voltar ao início", fg_color=tema.VERDE,
                     hover_color=tema.VERDE_HOVER, command=self.app.tela_inicial).pack(anchor="w", padx=24, pady=10)

    def _nrs(self, raiz):
        """Permite ajustar os intervalos de reavaliação, armazenados no banco oficial do Mapa."""
        card = ctk.CTkFrame(raiz, fg_color=tema.BRANCO, border_width=1,
                           border_color=tema.BORDA, corner_radius=12)
        card.pack(fill="x", padx=24, pady=(4, 12))
        ctk.CTkLabel(card, text="Reavaliação nutricional (NRS-2002)", font=tema.fonte(16, "bold"),
                    text_color=tema.TEXTO).pack(anchor="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(card, text="Configure o intervalo para cada classificação. Padrão: 7 dias; permitido: 1–90 dias.",
                    font=tema.fonte(12), text_color=tema.SUAVE).pack(anchor="w", padx=18, pady=(0, 10))
        caminho_db = getattr(getattr(self.app, "mapa", None), "db", None)
        if not caminho_db:
            ctk.CTkLabel(card, text="Banco de dados do Mapa não disponível nesta sessão.",
                         text_color=tema.LARANJA_TEXTO).pack(anchor="w", padx=18, pady=(0, 14))
            return
        atuais = nrs.ler_intervalos(caminho_db)
        campos = {}
        for codigo, rotulo in nrs.GRAUS:
            linha = ctk.CTkFrame(card, fg_color="transparent")
            linha.pack(fill="x", padx=18, pady=3)
            ctk.CTkLabel(linha, text=rotulo, font=tema.fonte(12), text_color=tema.TEXTO,
                        anchor="w", width=300).pack(side="left")
            entrada = ctk.CTkEntry(linha, width=65, border_color=tema.BORDA)
            entrada.insert(0, str(atuais[codigo]))
            entrada.pack(side="left")
            ctk.CTkLabel(linha, text="dias", font=tema.fonte(12), text_color=tema.SUAVE).pack(side="left", padx=6)
            campos[codigo] = entrada
        status = ctk.CTkLabel(card, text="", font=tema.fonte(12), text_color=tema.SUAVE)
        status.pack(anchor="w", padx=18, pady=(4, 8))
        def salvar():
            try:
                novos = nrs.salvar_intervalos(caminho_db, {codigo: int(entry.get()) for codigo, entry in campos.items()})
            except (ValueError, KeyError, TypeError):
                status.configure(text="Informe números inteiros de 1 a 90 em todos os campos.",
                              text_color=tema.LARANJA_TEXTO)
                return
            aviso = " Atenção: a RDC 63/2000 estabelece reavaliação no máximo a cada 10 dias." if max(novos.values()) > nrs.LIMITE_RDC63 else ""
            status.configure(text="Intervalos salvos no banco do Mapa." + aviso,
                          text_color=tema.LARANJA_TEXTO if aviso else tema.VERDE)
        ctk.CTkButton(card, text="Salvar intervalos", command=salvar, fg_color=tema.VERDE,
                      hover_color=tema.VERDE_HOVER, font=tema.fonte(12, "bold")).pack(anchor="w", padx=18, pady=(0, 14))


    def _equipe(self, raiz):
        """Cadastro de estagiários e nutricionistas vinculados ao fluxo de evolução."""
        card = ctk.CTkFrame(raiz, fg_color=tema.BRANCO, border_width=1,
                           border_color=tema.BORDA, corner_radius=12)
        card.pack(fill="x", padx=24, pady=(4, 12))
        ctk.CTkLabel(card, text="Equipe de evolução nutricional", font=tema.fonte(16, "bold"),
                     text_color=tema.TEXTO).pack(anchor="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(card,
                     text="Cadastre os estagiários que elaboram rascunhos e os nutricionistas que revisam e fecham evoluções. O CRN precisa ser conferido no conselho antes do cadastro.",
                     font=tema.fonte(12), text_color=tema.SUAVE, wraplength=760, justify="left"
        ).pack(anchor="w", padx=18, pady=(0, 10))
        caminho_db = getattr(getattr(self.app, "mapa", None), "db", None)
        if not caminho_db:
            ctk.CTkLabel(card, text="Banco de dados do Mapa não disponível nesta sessão.",
                         text_color=tema.LARANJA_TEXTO).pack(anchor="w", padx=18, pady=(0, 14))
            return
        try:
            import pep_db
            import pep_evolucao_db as evdb
            evdb.listar_equipe(caminho_db, ativos=False)
        except Exception as erro:
            ctk.CTkLabel(card, text=f"Cadastro de equipe indisponível. Reinicie o NutriLab para aplicar as migrações PEP. Detalhe: {erro}",
                         text_color=tema.LARANJA_TEXTO, wraplength=760, justify="left").pack(
                             anchor="w", padx=18, pady=(0, 14))
            return

        status = ctk.CTkLabel(card, text="", font=tema.fonte(11), text_color=tema.SUAVE,
                              wraplength=760, justify="left")
        status.pack(anchor="w", padx=18, pady=(4, 8))

        est = ctk.CTkFrame(card, fg_color="transparent")
        est.pack(fill="x", padx=18, pady=(0, 10))
        ctk.CTkLabel(est, text="Novo estagiário", font=tema.fonte(13, "bold"),
                     text_color=tema.TEXTO).pack(anchor="w", pady=(4, 4))
        e_est = ctk.CTkEntry(est, width=320, placeholder_text="Nome completo")
        e_est.pack(side="left", padx=(0, 8))
        def adicionar_estagiario():
            try:
                evdb.cadastrar_membro(caminho_db, e_est.get(), "estagiario")
                e_est.delete(0, "end")
                status.configure(text="Estagiário cadastrado.", text_color=tema.VERDE)
                atualizar_lista()
            except Exception as erro:
                status.configure(text=str(erro), text_color=tema.LARANJA_TEXTO)
        ctk.CTkButton(est, text="Adicionar estagiário", command=adicionar_estagiario,
                      fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER).pack(side="left")

        nut = ctk.CTkFrame(card, fg_color="transparent")
        nut.pack(fill="x", padx=18, pady=(0, 10))
        ctk.CTkLabel(nut, text="Novo nutricionista (conta individual para assinatura)", font=tema.fonte(13, "bold"),
                     text_color=tema.TEXTO).pack(anchor="w", pady=(4, 4))
        linha1 = ctk.CTkFrame(nut, fg_color="transparent")
        linha1.pack(fill="x", pady=2)
        e_nome = ctk.CTkEntry(linha1, width=260, placeholder_text="Nome completo")
        e_nome.pack(side="left", padx=(0, 6))
        e_crn = ctk.CTkEntry(linha1, width=150, placeholder_text="CRN-6 1234")
        e_crn.pack(side="left", padx=6)
        linha2 = ctk.CTkFrame(nut, fg_color="transparent")
        linha2.pack(fill="x", pady=2)
        e_login = ctk.CTkEntry(linha2, width=180, placeholder_text="Login individual")
        e_login.pack(side="left", padx=(0, 6))
        e_senha = ctk.CTkEntry(linha2, width=180, placeholder_text="Senha (mínimo 8 caracteres)", show="*")
        e_senha.pack(side="left", padx=6)
        var_crn = tk.IntVar(value=0)
        ctk.CTkCheckBox(nut, text="Confirmo que consultei o conselho e conferi a identificação e a situação do CRN.",
                        variable=var_crn).pack(anchor="w", pady=(4, 6))
        def adicionar_nutricionista():
            usuario_id = None
            try:
                crn = evdb.validar_crn_formato(e_crn.get())
                if not crn:
                    raise ValueError("CRN inválido. Use o formato CRN-6 1234 e confira a regularidade no conselho.")
                if not var_crn.get():
                    raise ValueError("Marque a confirmação de conferência do CRN.")
                usuario_id = pep_db.criar_usuario(
                    caminho_db, e_login.get(), e_nome.get(), crn, e_senha.get())
                evdb.cadastrar_membro(
                    caminho_db, e_nome.get(), "nutricionista", crn=crn,
                    crn_conferido=True, id_usuario=usuario_id)
                for campo in (e_nome, e_crn, e_login, e_senha):
                    campo.delete(0, "end")
                var_crn.set(0)
                status.configure(text="Nutricionista cadastrado com conta individual e CRN conferido.",
                                 text_color=tema.VERDE)
                atualizar_lista()
            except Exception as erro:
                if usuario_id:
                    try:
                        pep_db.desativar_usuario(caminho_db, usuario_id)
                    except Exception:
                        pass
                status.configure(text=str(erro), text_color=tema.LARANJA_TEXTO)
        ctk.CTkButton(nut, text="Adicionar nutricionista", command=adicionar_nutricionista,
                      fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER).pack(anchor="w", pady=(0, 4))

        lista = ctk.CTkFrame(card, fg_color="transparent")
        lista.pack(fill="x", padx=18, pady=(0, 14))
        ctk.CTkLabel(lista, text="Integrantes cadastrados", font=tema.fonte(13, "bold"),
                     text_color=tema.TEXTO).pack(anchor="w", pady=(4, 6))
        lista_itens = ctk.CTkFrame(lista, fg_color="transparent")
        lista_itens.pack(fill="x")
        def atualizar_lista():
            for filho in lista_itens.winfo_children():
                filho.destroy()
            try:
                membros = evdb.listar_equipe(caminho_db, ativos=False)
            except Exception as erro:
                status.configure(text=str(erro), text_color=tema.LARANJA_TEXTO)
                return
            for membro in membros:
                linha = ctk.CTkFrame(lista_itens, fg_color="transparent")
                linha.pack(fill="x", pady=2)
                situacao = "Ativo" if membro["ativo"] else "Inativo"
                detalhe = f"{membro['nome']} — {membro['funcao']} — {membro['crn'] or 'sem CRN'} — {situacao}"
                ctk.CTkLabel(linha, text=detalhe, anchor="w", text_color=tema.TEXTO).pack(side="left", fill="x", expand=True)
                if membro["ativo"]:
                    def desativar(mid=membro["id_membro"], nome=membro["nome"]):
                        if not messagebox.askyesno("Desativar integrante",
                                                   f"Desativar {nome}? Rascunhos pendentes impedem a desativação.",
                                                   parent=self.app):
                            return
                        try:
                            evdb.desativar_membro(caminho_db, mid)
                            status.configure(text=f"{nome} desativado.", text_color=tema.VERDE)
                            atualizar_lista()
                        except Exception as erro:
                            status.configure(text=str(erro), text_color=tema.LARANJA_TEXTO)
                    ctk.CTkButton(linha, text="Desativar", width=78, fg_color=tema.SUAVE,
                                  hover_color=tema.LARANJA, command=desativar).pack(side="right", padx=4)
        atualizar_lista()

    def _backups(self, raiz):
        """Lista snapshots locais por data e permite restauração protegida."""
        caminho_db = db_service.caminho_banco()
        card = ctk.CTkFrame(raiz, fg_color=tema.BRANCO, border_width=1,
                           border_color=tema.BORDA, corner_radius=12)
        card.pack(fill="x", padx=24, pady=(4, 12))
        ctk.CTkLabel(card, text="Backups e recuperação de dados",
                     font=tema.fonte(16, "bold"), text_color=tema.TEXTO).pack(
                         anchor="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(
            card,
            text="As cópias ficam na pasta backups, ao lado do banco. Restaurar substitui o banco atual "
                 "pela cópia escolhida e cria automaticamente uma cópia de segurança do estado atual.",
            font=tema.fonte(12), text_color=tema.SUAVE, wraplength=760, justify="left"
        ).pack(anchor="w", padx=18, pady=(0, 10))

        arquivos = list(reversed(db_service.listar_backups(caminho_db)))
        if not arquivos:
            ctk.CTkLabel(card, text="Nenhum backup encontrado nesta instalação.",
                         font=tema.fonte(12), text_color=tema.SUAVE).pack(
                             anchor="w", padx=18, pady=(0, 14))
            return

        opcoes = {}
        for arquivo in arquivos:
            nome = arquivo.name
            import re
            m = re.search(r"\.backup_(\d{8})-(\d{6})_(.+)\.db$", nome)
            if m:
                data = f"{m.group(1)[6:8]}/{m.group(1)[4:6]}/{m.group(1)[0:4]}"
                hora = f"{m.group(2)[0:2]}:{m.group(2)[2:4]}:{m.group(2)[4:6]}"
                motivo = m.group(3).replace("-", " ")
                rotulo = f"{data} {hora} — {motivo}"
            else:
                rotulo = nome
            opcoes[rotulo] = arquivo

        seletor = ctk.CTkOptionMenu(card, values=list(opcoes),
                                    width=360, fg_color=tema.VERDE,
                                    button_color=tema.VERDE_HOVER)
        seletor.set(next(iter(opcoes)))
        seletor.pack(anchor="w", padx=18, pady=(0, 10))
        status = ctk.CTkLabel(card, text=f"{len(arquivos)} backup(s) disponível(is).",
                              font=tema.fonte(12), text_color=tema.SUAVE)
        status.pack(anchor="w", padx=18, pady=(0, 8))

        def restaurar():
            arquivo = opcoes.get(seletor.get())
            if arquivo is None:
                status.configure(text="Selecione um backup válido.", text_color=tema.LARANJA_TEXTO)
                return
            if not messagebox.askyesno(
                "Confirmar restauração",
                "O banco atual será substituído pelo backup selecionado. "
                "Uma cópia do estado atual será criada automaticamente antes da troca. "
                "Deseja continuar?"
            ):
                return
            try:
                resultado = db_service.restaurar_backup(arquivo, caminho_db)
            except Exception as erro:
                messagebox.showerror("Falha na restauração",
                                     f"A restauração não foi concluída. Se houve falha na troca, use a cópia pre-restauração criada automaticamente.\n\nDetalhe: {erro}")
                return
            messagebox.showinfo(
                "Restauração concluída",
                f"Backup restaurado com sucesso.\n\nCópia do estado anterior: "
                f"{resultado.copia_de_seguranca or 'não necessária'}.\n\n"
                "Feche e abra novamente o NutriLab para recarregar os dados restaurados."
            )
            status.configure(text="Restauração concluída. Reinicie o aplicativo.",
                              text_color=tema.VERDE)

        ctk.CTkButton(card, text="Restaurar backup selecionado", command=restaurar,
                      fg_color=tema.LARANJA, hover_color=tema.LARANJA_TEXTO,
                      font=tema.fonte(12, "bold")).pack(anchor="w", padx=18, pady=(0, 14))

    def _aplicar(self, nome):
        modo = self.OPCOES.get(nome, "Light")
        ctk.set_appearance_mode(modo)
        # O CustomTkinter atualiza os componentes com cores em tupla; ttk exige reaplicar os estilos.
        try:
            tema.aplicar_tema_ttk(self.app)
        except Exception:
            pass
        dados = _ler()
        dados["aparencia"] = modo
        if _salvar(dados):
            if hasattr(self, "lbl_status"):
                self.lbl_status.configure(text="Aparência salva. A alteração já está aplicada.", text_color=tema.VERDE)
        elif hasattr(self, "lbl_status"):
            self.lbl_status.configure(text="Não foi possível salvar a preferência.", text_color=tema.LARANJA_TEXTO)
