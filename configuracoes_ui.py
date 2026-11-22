# -*- coding: utf-8 -*-
"""Tela enxuta de configurações visuais para o NutriLab."""
from __future__ import annotations

import json
import os
import customtkinter as ctk
import tema

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
        ctk.CTkLabel(card, text="Escolha como o NutriLab será exibido neste computador.",
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
        ctk.CTkButton(raiz, text="Voltar ao início", fg_color=tema.VERDE,
                     hover_color=tema.VERDE_HOVER, command=self.app.tela_inicial).pack(anchor="w", padx=24, pady=10)

    def _aplicar(self, nome):
        modo = self.OPCOES.get(nome, "Light")
        ctk.set_appearance_mode(modo)
        dados = _ler()
        dados["aparencia"] = modo
        if _salvar(dados):
            return
