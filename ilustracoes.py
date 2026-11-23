# -*- coding: utf-8 -*-
"""Ilustrações clínicas simplificadas geradas em Pillow para dicas do NutriLab."""
from __future__ import annotations

import os
from PIL import Image, ImageDraw

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imagens_clinicas")
PELE = (236, 243, 239)
CONTORNO = (31, 90, 64)
AGUA = (130, 196, 236)
AGUA_ESC = (30, 110, 180)
LARANJA = (240, 138, 36)
LARANJA_CLARO = (255, 218, 175)
S = 2

def carregar(nome, largura_max=700):
    """Carrega imagem de apoio local, retornando None quando ausente."""
    for ext in (".png", ".jpg", ".jpeg"):
        caminho = os.path.join(PASTA, nome + ext)
        if os.path.isfile(caminho):
            im = Image.open(caminho).convert("RGB")
            if im.width > largura_max:
                im = im.resize((largura_max, round(im.height * largura_max / im.width)), Image.Resampling.LANCZOS)
            return im
    return None

def _corpo(agua=False, ausentes=()):
    """Desenha corpo frontal simplificado; segmentos ausentes ficam laranja."""
    im = Image.new("RGB", (240*S, 360*S), "white")
    d = ImageDraw.Draw(im)
    def xy(*vals): return tuple(int(v*S) for v in vals)
    d.ellipse(xy(92, 18, 148, 74), fill=CONTORNO)
    d.ellipse(xy(96, 22, 144, 70), fill=PELE)
    d.rounded_rectangle(xy(80, 82, 160, 192), radius=18*S, fill=CONTORNO)
    d.rounded_rectangle(xy(84, 86, 156, 188), radius=16*S, fill=PELE)
    for a,b,w in [((86,98),(62,190),18),((154,98),(178,190),18),((100,186),(94,292),24),((140,186),(146,292),24),((94,292),(78,322),20),((146,292),(164,322),20)]:
        color= LARANJA if (a,b) in ausentes else CONTORNO
        d.line([xy(*a),xy(*b)], fill=color, width=w*S)
        for x,y in (a,b): d.ellipse(xy(x-w/2,y-w/2,x+w/2,y+w/2), fill=color)
    if agua:
        d.ellipse(xy(92, 116, 148, 170), fill=AGUA, outline=AGUA_ESC, width=3*S)
    return im.resize((240,360), Image.Resampling.LANCZOS)

def ascite():
    """Comparação ilustrativa entre ascite e edema periférico."""
    cached=carregar("ascite")
    if cached: return cached
    im=Image.new("RGB",(500,380),"white")
    im.paste(_corpo(agua=True),(0,10))
    im.paste(_corpo(),(250,10))
    d=ImageDraw.Draw(im)
    d.text((80,350),"Ascite",fill=CONTORNO)
    d.text((330,350),"Edema periférico",fill=CONTORNO)
    return im

def edema(nivel=1):
    """Imagem esquemática; nível 1–4 destaca progressivamente a extensão."""
    nivel=max(0,min(4,int(nivel)))
    cached=carregar(f"edema_{nivel}")
    if cached: return cached
    im=_corpo()
    d=ImageDraw.Draw(im)
    if nivel:
        # realce progressivo da região inferior, aproximado apenas para ensino visual
        y0=360-int(nivel*48)
        d.rectangle((64,y0,176,340),outline=LARANJA,width=5)
    return im

def amputacao(nivel="Mão", legenda=None):
    """Desenho genérico com marcação do membro; sem substituir avaliação individual."""
    cached=carregar("amputacao_"+str(nivel).lower().replace(" ","_"))
    if cached: return cached
    im=_corpo()
    d=ImageDraw.Draw(im)
    mapa={"Mão":(58,176,82,208),"Antebraço + mão":(54,142,82,208),"Braço inteiro":(48,88,82,208),"Pé":(78,286,110,326),"Perna abaixo do joelho":(82,236,110,326),"Perna inteira":(82,184,110,326)}
    d.rectangle(mapa.get(nivel,(58,176,82,208)),outline=LARANJA,width=5)
    if legenda:
        d.text((4,4),legenda,fill=CONTORNO)
    return im
