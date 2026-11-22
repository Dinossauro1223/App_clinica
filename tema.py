# -*- coding: utf-8 -*-
"""Tema compartilhado inicial do NutriLab.

Utilitários visuais pequenos e independentes, para integração gradual com as telas
existentes sem alterar o comportamento clínico ou os dados do aplicativo.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

BRANCO = "#FFFFFF"
FUNDO = "#F3F8F5"
BORDA = "#D6E6DC"
VERDE_ESC = "#0F3D2E"
VERDE = "#1E7A4F"
VERDE_HOVER = "#17633F"
VERDE_CLARO = "#E3F3EA"
LARANJA = "#F08A24"
LARANJA_CLARO = "#FFF1E0"
LARANJA_TEXTO = "#9A4F00"
TEXTO = "#1B2B24"
SUAVE = "#5F7368"

def fonte(tamanho: int = 13, peso: str = "normal") -> ctk.CTkFont:
    """Retorna fonte padrão da interface."""
    return ctk.CTkFont(family="Segoe UI", size=tamanho, weight=peso)

def data_valida(texto: str) -> bool:
    """Valida data no formato DD/MM/AAAA."""
    try:
        datetime.strptime(texto, "%d/%m/%Y")
        return True
    except (TypeError, ValueError):
        return False

def aplicar_tema_ttk(root: tk.Misc) -> None:
    """Aplica estilos ttk neutros e coerentes com o tema verde/branco."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("NutriLab.TFrame", background=FUNDO)
    style.configure("NutriLab.TLabel", background=FUNDO, foreground=TEXTO)
    style.configure("NutriLab.TButton", padding=(10, 6))
    style.configure("NutriLab.Treeview", rowheight=28, background=BRANCO,
                   fieldbackground=BRANCO, foreground=TEXTO)
    style.map("NutriLab.Treeview", background=[("selected", VERDE_CLARO)],
              foreground=[("selected", VERDE_ESC)])

def configurar_ctk() -> None:
    """Configura tema verde e recupera preferência de aparência do usuário."""
    modo = "Light"
    caminho = os.path.join(os.path.expanduser("~"), ".nutrilab", "preferencias.json")
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            preferencias = json.load(arquivo)
        if isinstance(preferencias, dict) and preferencias.get("aparencia") in ("Light", "Dark", "System"):
            modo = preferencias["aparencia"]
    except (OSError, ValueError, TypeError):
        pass
    ctk.set_appearance_mode(modo)
    ctk.set_default_color_theme("green")

class CampoData(ctk.CTkEntry):
    """Entrada de data que aplica máscara DD/MM/AAAA e sinaliza data inválida."""
    def __init__(self, master, placeholder_text="dd/mm/aaaa", command=None, **kwargs):
        kwargs.setdefault("border_color", BORDA)
        super().__init__(master, placeholder_text=placeholder_text, **kwargs)
        self._command = command
        self.bind("<KeyRelease>", self._formatar)

    @staticmethod
    def formatar(texto: str) -> str:
        digitos = "".join(c for c in texto if c.isdigit())[:8]
        if len(digitos) <= 2:
            return digitos
        if len(digitos) <= 4:
            return digitos[:2] + "/" + digitos[2:]
        return digitos[:2] + "/" + digitos[2:4] + "/" + digitos[4:]

    def _formatar(self, _event=None):
        bruto = self.get()
        novo = self.formatar(bruto)
        if novo != bruto:
            self.delete(0, "end")
            self.insert(0, novo)
        invalida = len(novo) == 10 and not data_valida(novo)
        self.configure(border_color=LARANJA if invalida else BORDA)
        if self._command:
            self._command()
