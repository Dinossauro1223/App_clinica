# -*- coding: utf-8 -*-
"""Biblioteca de imagens personalizadas do NutriLab, persistente entre atualizações."""
from __future__ import annotations
import re
import shutil
from pathlib import Path
from PIL import Image

EXTENSOES = {".png", ".jpg", ".jpeg", ".webp"}
CHAVES_ESCALAS = {"bristol", "urina", "aceitacao"}

def pasta_dados():
    p = Path.home() / ".nutrilab" / "midias"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _chave(valor):
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(valor or "").strip()).strip("-_").lower()
    if not s or len(s) > 80:
        raise ValueError("Informe um identificador curto (por exemplo, ENT-001 ou bristol).")
    return s

def salvar_imagem(categoria, identificador, origem):
    categoria = "escalas" if categoria == "escalas" else "orientacoes"
    chave = _chave(identificador)
    origem = Path(origem)
    if origem.suffix.lower() not in EXTENSOES:
        raise ValueError("Formato não suportado. Use PNG, JPG, JPEG ou WEBP.")
    with Image.open(origem) as img:
        img.verify()
    destino_dir = pasta_dados() / categoria
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / (chave + origem.suffix.lower())
    temporario = destino.with_name(destino.name + ".tmp")
    shutil.copy2(origem, temporario)
    temporario.replace(destino)
    for antigo in destino_dir.glob(chave + ".*"):
        if antigo != destino and antigo.is_file():
            antigo.unlink()
    return destino

def resolver_imagem(categoria, identificador):
    categoria = "escalas" if categoria == "escalas" else "orientacoes"
    try:
        chave = _chave(identificador)
    except ValueError:
        return None
    pasta = pasta_dados() / categoria
    for ext in EXTENSOES:
        p = pasta / (chave + ext)
        if p.is_file():
            return p
    return None

def listar_imagens(categoria=None):
    base = pasta_dados()
    categorias = [categoria] if categoria else ["escalas", "orientacoes"]
    saida = []
    for cat in categorias:
        pasta = base / cat
        if pasta.is_dir():
            for p in sorted(pasta.iterdir()):
                if p.is_file() and p.suffix.lower() in EXTENSOES:
                    saida.append((cat, p.stem, p))
    return saida
