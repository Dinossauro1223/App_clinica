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

# Pares (claro, escuro): o CustomTkinter seleciona a cor conforme o modo ativo.
BRANCO = ("#FFFFFF", "#202A24")
FUNDO = ("#F3F8F5", "#141C18")
BORDA = ("#D6E6DC", "#3A5145")
VERDE_ESC = ("#0F3D2E", "#0A251C")
VERDE = ("#1E7A4F", "#37A66F")
VERDE_HOVER = ("#17633F", "#2D8A5B")
VERDE_CLARO = ("#E3F3EA", "#294235")
LARANJA = ("#F08A24", "#F6A04D")
LARANJA_CLARO = ("#FFF1E0", "#3B2D1E")
LARANJA_TEXTO = ("#9A4F00", "#F6BD79")
TEXTO = ("#1B2B24", "#E5EEE8")
SUAVE = ("#5F7368", "#A9B9AF")
ERRO = ("#B3261E", "#F28B82")
ERRO_HOVER = ("#8E0000", "#CF6679")
AZUL = ("#1565C0", "#82B1FF")
AZUL_HOVER = ("#0D47A1", "#5C8FE6")


def cor_atual(paleta, modo=None):
    """Resolve uma cor (claro, escuro) para APIs Tk/ttk que não aceitam tuplas."""
    modo = (modo or ctk.get_appearance_mode()).lower()
    if isinstance(paleta, (tuple, list)) and len(paleta) == 2:
        return paleta[1] if modo == "dark" else paleta[0]
    return paleta

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
    """Aplica a paleta do modo atual também às tabelas e widgets ttk."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    fundo, branco = cor_atual(FUNDO), cor_atual(BRANCO)
    borda, texto, suave = cor_atual(BORDA), cor_atual(TEXTO), cor_atual(SUAVE)
    selecionado, texto_sel = cor_atual(VERDE_CLARO), cor_atual(VERDE_ESC)
    style.configure("NutriLab.TFrame", background=fundo)
    style.configure("NutriLab.TLabel", background=fundo, foreground=texto)
    style.configure("NutriLab.TButton", padding=(10, 6))
    for nome in ("Treeview", "NutriLab.Treeview"):
        style.configure(nome, rowheight=30, background=branco, fieldbackground=branco,
                        foreground=texto, bordercolor=borda, lightcolor=borda, darkcolor=borda,
                        borderwidth=1, relief="solid")
        style.map(nome, background=[("selected", selecionado)],
                  foreground=[("selected", texto_sel)])
    style.configure("Treeview.Heading", background=fundo, foreground=texto,
                    relief="solid", bordercolor=borda)
    style.map("Treeview.Heading", background=[("active", selecionado)],
              foreground=[("active", texto)])
    style.configure("TEntry", fieldbackground=branco, foreground=texto)
    style.configure("TCombobox", fieldbackground=branco, foreground=texto,
                    background=fundo, arrowcolor=texto)
    style.map("TCombobox", fieldbackground=[("readonly", branco)],
              foreground=[("readonly", texto)])

    def atualizar_tags(widget):
        try:
            if widget.winfo_class() == "Treeview":
                for tag in ("linha_par", "tbca_par"):
                    widget.tag_configure(tag, background=fundo, foreground=texto)
                for tag in ("linha_impar", "tbca_impar"):
                    widget.tag_configure(tag, background=branco, foreground=texto)
        except (tk.TclError, AttributeError):
            pass
        try:
            filhos = widget.winfo_children()
        except (tk.TclError, AttributeError):
            return
        for filho in filhos:
            atualizar_tags(filho)

    atualizar_tags(root)

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
    setter_aparencia = getattr(ctk, "set_appearance_mode", None)
    setter_tema = getattr(ctk, "set_default_color_theme", None)
    if callable(setter_aparencia):
        setter_aparencia(modo)
    if callable(setter_tema):
        setter_tema("green")

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
