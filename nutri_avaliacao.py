"""Peso corrigido (edema/ascite/amputação), DRI (EER/TEE, IOM 2005) e aporte de suplementos.

Funções puras, sem interface e sem banco. Fontes e pendências: ver REF-2026-11-15-001 no diário.
"""
from collections import namedtuple

from nutri_calculos import norm_sexo

# Descontos de líquido (kg) e perda por amputação (% do peso corporal) — valores da planilha/protótipo do setor.
EDEMA_KG = {"Ausente": 0.0, "+ tornozelo (1 kg)": 1.0, "++ joelho (3,5 kg)": 3.5,
            "+++ raiz da coxa (5,5 kg)": 5.5, "++++ anasarca (11 kg)": 11.0}
ASCITE_KG = {"Ausente": 0.0, "Leve (2,2 kg)": 2.2, "Moderada (6 kg)": 6.0, "Grave (14 kg)": 14.0}
AMPUTACAO_PCT = {"mão": 0.7, "antebraço + mão": 2.3, "braço inteiro": 5.0,
                 "pé": 1.5, "perna abaixo do joelho": 5.9, "perna inteira": 16.0}
ATIVIDADE = {"Sedentário": 0, "Pouco ativo": 1, "Ativo": 2, "Muito ativo": 3}


class DRIIndisponivel(ValueError):
    """Dados insuficientes ou faixa etária sem equação implementada."""


def peso_corrigido(peso_kg, edema_kg=0.0, ascite_kg=0.0, amputacao_pct=0.0):
    """Peso 'seco' ajustado: (peso - edema - ascite) / (1 - amputação%)."""
    if peso_kg is None or peso_kg <= 0:
        raise ValueError("Peso inválido.")
    if min(edema_kg, ascite_kg, amputacao_pct) < 0 or amputacao_pct >= 100:
        raise ValueError("Valores de edema, ascite ou amputação inválidos.")
    seco = peso_kg - edema_kg - ascite_kg
    if seco <= 0:
        raise ValueError("Descontos de líquido maiores que o peso informado.")
    return seco / (1 - amputacao_pct / 100.0)


Dri = namedtuple("Dri", "kcal equacao aviso")
_PA_ADULTO = {"H": (1, 1.11, 1.25, 1.48), "M": (1, 1.12, 1.27, 1.45)}
_PA_SOBREPESO = {"H": (1, 1.12, 1.29, 1.59), "M": (1, 1.16, 1.27, 1.44)}
_PA_CRIANCA = {"H": (1, 1.13, 1.26, 1.42), "M": (1, 1.16, 1.31, 1.56)}


def dri_energia(sexo, idade_anos, peso_kg, altura_m, nivel=0):
    """Necessidade energética estimada (IOM 2005). nivel: 0 sedentário ... 3 muito ativo."""
    s = norm_sexo(sexo)
    faltam = [n for n, v in (("sexo", s), ("idade", idade_anos), ("peso", peso_kg), ("altura", altura_m)) if not v and v != 0]
    if faltam or not peso_kg or not altura_m:
        raise DRIIndisponivel("faltam dados: " + ", ".join(faltam or ["peso/altura"]))
    if nivel not in (0, 1, 2, 3):
        raise DRIIndisponivel("nível de atividade inválido")
    w, h, a = peso_kg, altura_m, idade_anos
    if a < 3:
        raise DRIIndisponivel("menores de 3 anos: equação não implementada")
    if a < 19:
        pa = _PA_CRIANCA[s][nivel]
        e = 20.0 if a < 9 else 25.0
        k = (88.5 - 61.9 * a + pa * (26.7 * w + 903 * h) + e) if s == "H" else (135.3 - 30.8 * a + pa * (10 * w + 934 * h) + e)
        return Dri(k, "EER IOM 2005, 3–18 anos (peso saudável)",
                   "Equação para peso saudável; se há sobrepeso/obesidade, requer equação específica (não implementada).")
    if w / (h * h) >= 25:
        pa = _PA_SOBREPESO[s][nivel]
        k = (1086 - 10.1 * a + pa * (13.7 * w + 416 * h)) if s == "H" else (448 - 7.95 * a + pa * (11.4 * w + 619 * h))
        return Dri(k, "TEE IOM 2005, adulto com sobrepeso/obesidade (IMC ≥ 25)", "")
    pa = _PA_ADULTO[s][nivel]
    k = (662 - 9.53 * a + pa * (15.91 * w + 539.6 * h)) if s == "H" else (354 - 6.91 * a + pa * (9.36 * w + 726 * h))
    return Dri(k, "EER IOM 2005, adulto (IMC < 25)", "")


# Composição por mL (líquidos/preparados) ou por g (pós) — banco da planilha de suplementos.
# None = composição não cadastrada: NUNCA tratar como zero.
SUPLEMENTOS = {
    "Diamax IG": ("mL", 1.0, 0.044), "Nutrison 1,5": ("mL", 1.51, 0.06),
    "Trophic Soya 1,5 (líquido)": ("mL", 1.5, 0.057), "Trophic Fiber": ("mL", 1.2, 0.045),
    "Nutro 1,5": ("mL", 1.5, 0.061), "Trophic Basic pó (preparado 1,0 kcal/mL)": ("mL", 1.0, 0.037),
    "Trophic Soya pó (preparado 1,0 kcal/mL)": ("mL", 1.0, 0.037), "Suprasoya (preparado)": ("mL", 0.63, 0.035),
    "Aptamil Premium 1 (preparado)": ("mL", 0.66, 0.013), "Fresubin Protein Powder": ("g", 3.6, 0.87),
    "Glutamina em pó (provisório)": ("g", 4.0, 0.0), "Simbioflora (sachê)": ("sachê", None, None),
}


def aporte_suplementos(itens):
    """itens: [(nome, quantidade_por_vez, vezes_ao_dia)] -> (kcal, proteína_g, [nomes sem composição])."""
    kcal = ptn = 0.0
    sem = []
    for nome, qtd, vezes in itens:
        _, k, p = SUPLEMENTOS[nome]
        if k is None:
            sem.append(nome)
            continue
        total = qtd * vezes
        kcal += total * k
        ptn += total * p
    return kcal, ptn, sem
