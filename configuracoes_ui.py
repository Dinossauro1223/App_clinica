# -*- coding: utf-8 -*-
"""Tela enxuta de configurações visuais para o NutriLab."""
from __future__ import annotations

import json
import os
import customtkinter as ctk
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
        ctk.CTkLabel(card, text="Escolha como o NutriLab será exibido. Algumas telas antigas ainda usam cores fixas e não acompanham completamente o modo escuro.",
                     font=tema.fonte(13), text_color=tema.SUAVE).pack(anchor="w", padx=18, pady=(0, 10))
        dados = _ler()
        atual = dados.get("aparencia", "Light")
        escolha = next((nome for nome, modo in self.OPCOES.items() if modo == atual), "Claro")
        seletor = ctk.CTkSegmentedButton(card, values=list(self.OPCOES), command=self._aplicar,
                                         selected_color=tema.VERDE, selected_hover_color=tema.VERDE_HOVER,
                                         unselected_color=tema.VERDE_CLARO,
                                         unselected_hover_color=tema.BORDA)
        seletor.set(escolha)
        seletor.pack(anchor="w", padx=18, pady=(0, 16))
        self.lbl_status = ctk.CTkLabel(card, text="", font=tema.fonte(12), text_color=tema.SUAVE)
        self.lbl_status.pack(anchor="w", padx=18, pady=(0, 12))
        self._nrs(raiz)
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

    def _aplicar(self, nome):
        modo = self.OPCOES.get(nome, "Light")
        ctk.set_appearance_mode(modo)
        dados = _ler()
        dados["aparencia"] = modo
        if _salvar(dados):
            if hasattr(self, "lbl_status"):
                self.lbl_status.configure(text="Aparência salva. A alteração já está aplicada.", text_color=tema.VERDE)
        elif hasattr(self, "lbl_status"):
            self.lbl_status.configure(text="Não foi possível salvar a preferência.", text_color=tema.LARANJA_TEXTO)
