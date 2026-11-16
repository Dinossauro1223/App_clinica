# -*- coding: utf-8 -*-
"""Configurações: última opção da barra lateral. Abre já na seção da aba em que o usuário estava."""
import customtkinter as ctk

import tema as t

SECOES = ("Aparência", "Mapa e antropometria")
ABA_PARA_SECAO = {"Mapa nutricional": "Mapa e antropometria", "Avaliação e evolução": "Mapa e antropometria",
                  "Gráficos do mês": "Mapa e antropometria", "Suplementos": "Mapa e antropometria"}


class ConfiguracoesUI:
    def __init__(self, app):
        self.app = app

    def mostrar(self, secao=None):
        app = self.app
        secao = secao or ABA_PARA_SECAO.get(getattr(app.menu_lateral, "ativo", None), SECOES[0])
        app.limpar_area_principal()
        raiz = app.area_principal
        ctk.CTkLabel(raiz, text="Configurações", font=t.fonte(22, "bold"), text_color=t.VERDE).pack(anchor="w", padx=24, pady=(18, 6))
        seg = ctk.CTkSegmentedButton(raiz, values=list(SECOES), command=self.mostrar, selected_color=t.VERDE,
                                     selected_hover_color=t.VERDE_HOVER, unselected_color=t.VERDE_CLARO,
                                     unselected_hover_color=t.BORDA, text_color=t.TEXTO)
        seg.pack(anchor="w", padx=24, pady=(0, 12))
        seg.set(secao)
        card = ctk.CTkFrame(raiz, fg_color=t.BRANCO, border_width=1, border_color=t.BORDA, corner_radius=10)
        card.pack(fill="x", padx=24)
        if secao == SECOES[0]:
            sw = ctk.CTkSwitch(card, text="Barra lateral sempre aberta", progress_color=t.VERDE, font=t.fonte(14),
                               command=lambda: app.menu_lateral.definir_fixa(bool(sw.get())))
            sw.pack(anchor="w", padx=18, pady=(16, 4))
            if app.menu_lateral.fixa:
                sw.select()
            ctk.CTkLabel(card, text="Desligada, a barra fica fina e abre ao passar o mouse. Atalhos: botão ☰, Ctrl+B ou a "
                         "tecla ' (fora de campos de texto).", font=t.fonte(12), text_color=t.SUAVE, justify="left",
                         wraplength=640, anchor="w").pack(anchor="w", padx=18, pady=(0, 16))
        else:
            ctk.CTkLabel(card, text="Critério de IMC para idosos e equação de altura pela altura do joelho valem para o "
                         "Mapa e para a Avaliação e evolução.", font=t.fonte(12), text_color=t.SUAVE, justify="left",
                         wraplength=640, anchor="w").pack(anchor="w", padx=18, pady=(16, 8))
            ctk.CTkButton(card, text="Abrir configurações do mapa", command=app.mapa._abrir_config, fg_color=t.VERDE,
                          hover_color=t.VERDE_HOVER, font=t.fonte(13, "bold")).pack(anchor="w", padx=18, pady=(0, 16))
