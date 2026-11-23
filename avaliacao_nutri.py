# -*- coding: utf-8 -*-
"""Cálculos centrais da avaliação nutricional (sem interface).

Usa equações já presentes em nutri_calculos.py. Valores estimados e ajustados
são apoio à decisão e devem ser identificados na tela de avaliação.
"""
import nutri_calculos as nc

EDEMA = {"Ausente": 0, "+ tornozelo (1 kg)": 1, "++ joelho (3,5 kg)": 3.5,
         "+++ raiz da coxa (5,5 kg)": 5.5, "++++ anasarca (11 kg)": 11}
ASCITE = {"Ausente": 0, "Leve (2,2 kg)": 2.2, "Moderada (6 kg)": 6, "Grave (14 kg)": 14}
AMPUTACOES = {"Mão": ("sup", 0.7), "Antebraço + mão": ("sup", 2.3), "Braço inteiro": ("sup", 5.0),
              "Pé": ("inf", 1.5), "Perna abaixo do joelho": ("inf", 5.9), "Perna inteira": ("inf", 16.0)}
_PA = {"ad": {"H": (1, 1.11, 1.25, 1.48), "M": (1, 1.12, 1.27, 1.45)},
       "so": {"H": (1, 1.12, 1.29, 1.59), "M": (1, 1.16, 1.27, 1.44)},
       "cr": {"H": (1, 1.13, 1.26, 1.42), "M": (1, 1.16, 1.31, 1.56)}}

def pct_amputacao(qtd):
    """Percentual de peso correspondente às amputações informadas."""
    membros, pct = {"sup": 0, "inf": 0}, 0.0
    for nivel, n in (qtd or {}).items():
        if nivel not in AMPUTACOES:
            raise ValueError(f"Nível de amputação desconhecido: {nivel}")
        if isinstance(n, bool) or not isinstance(n, int) or n not in (0, 1, 2):
            raise ValueError("Cada nível deve ser informado como 0, 1 ou 2.")
        if n:
            membro, p = AMPUTACOES[nivel]
            membros[membro] += n
            pct += p * n
    if membros["sup"] > 2 or membros["inf"] > 2:
        raise ValueError("Há mais de dois membros superiores ou inferiores marcados: marque só o nível mais alto de cada membro.")
    return pct

def peso_ajustado(peso, fluidos_kg=0.0, amput_pct=0.0):
    """Peso seco e íntegro: (peso aferido - edema/ascite) / (1 - % amputado)."""
    base = peso - fluidos_kg
    if base <= 0:
        raise ValueError("Edema + ascite iguais ou maiores que o peso: confira os dados.")
    if amput_pct >= 100:
        raise ValueError("Soma das amputações >= 100%: revise os níveis marcados.")
    return base / (1 - amput_pct / 100)

def aj_da_altura(altura_cm, idade, sexo):
    """AJ estimada por inversão da equação de Chumlea 1985 para idosos."""
    a, b, k = nc._ALTURA_1985[nc.norm_sexo(sexo)]
    aviso = [] if 60 <= idade <= 90 else ["AJ calculada com equação validada para 60–90 anos."]
    return (altura_cm - a - k * idade) / b, aviso

def eer_dri(sexo, idade, peso, altura_m, atividade=0, imc=None):
    """DRI/EER (IOM 2005); retorna None se insuficiente ou idade < 3 anos."""
    s = nc.norm_sexo(sexo)
    if s is None or None in (idade, peso, altura_m) or idade < 3:
        return None
    if isinstance(atividade, bool) or not isinstance(atividade, int) or atividade not in range(4):
        raise ValueError("Atividade deve ser um inteiro de 0 a 3.")
    if idade >= 19:
        if imc is not None and imc >= 25:
            p = _PA["so"][s][atividade]
            return (1086 - 10.1 * idade + p * (13.7 * peso + 416 * altura_m)) if s == "H" else \
                   (448 - 7.95 * idade + p * (11.4 * peso + 619 * altura_m))
        p = _PA["ad"][s][atividade]
        return (662 - 9.53 * idade + p * (15.91 * peso + 539.6 * altura_m)) if s == "H" else \
               (354 - 6.91 * idade + p * (9.36 * peso + 726 * altura_m))
    p, dep = _PA["cr"][s][atividade], (20 if idade < 9 else 25)
    return (88.5 - 61.9 * idade + p * (26.7 * peso + 903 * altura_m) + dep) if s == "H" else \
           (135.3 - 30.8 * idade + p * (10 * peso + 934 * altura_m) + dep)

def calcular(d, lms=None, criterio_idoso="lipschitz"):
    """Recebe dados da avaliação e retorna peso/altura, ajustes, IMC, metas, DRI e avisos."""
    P, avisos = nc.parse_num, []
    sexo, cor, idade = nc.norm_sexo(d.get("sexo")), nc.norm_cor(d.get("cor")), P(d.get("idade"))
    peso, alt_cm, aj, pb = P(d.get("peso")), P(d.get("altura")), P(d.get("aj")), P(d.get("pb"))
    fluidos = EDEMA.get(d.get("edema"), 0) + ASCITE.get(d.get("ascite"), 0)
    try:
        pct = pct_amputacao(d.get("amputacoes") or {})
    except ValueError as erro:
        pct = 0.0
        avisos.append(str(erro))
    if aj is None and pct and alt_cm and idade is not None and sexo:
        aj, alertas = aj_da_altura(alt_cm, idade, sexo)
        avisos += [f"AJ calculada a partir da altura informada: {aj:.1f} cm."] + alertas
    tipo_peso = tipo_alt = None
    if peso is not None:
        tipo_peso = "Aferido"
    else:
        try:
            e = nc.estimar_peso(aj, pb, sexo, cor, idade)
            peso, tipo_peso, avisos = e.valor, "Estimado", avisos + list(e.avisos)
        except nc.EstimativaIndisponivel as erro:
            avisos.append(f"Peso: {erro}")
    if alt_cm is not None:
        tipo_alt = "Aferida"
    else:
        try:
            e = nc.estimar_altura(aj, sexo, cor, idade, "chumlea1985")
            alt_cm, tipo_alt, avisos = e.valor, "Estimada", avisos + list(e.avisos) + [f"Altura: {e.equacao}."]
        except nc.EstimativaIndisponivel as erro:
            avisos.append(f"Altura: {erro}")
    ajustado = None
    if peso is not None:
        try:
            ajustado = peso_ajustado(peso, fluidos, pct)
        except ValueError as erro:
            avisos.append(str(erro))
    altura_m = alt_cm / 100 if alt_cm else None
    imc = ajustado / altura_m ** 2 if ajustado and altura_m else None
    kk, gk = P(d.get("kcalkg")), P(d.get("ptnkg"))
    kcal = ajustado * kk if ajustado and kk else None
    atividade = int(d.get("atividade") or 0)
    dri = eer_dri(sexo, idade, ajustado, altura_m, atividade, imc) if imc else None
    if imc and idade is not None:
        if idade < 3:
            avisos.append("DRI indisponível abaixo de 3 anos neste programa.")
        elif idade < 19:
            avisos.append("Criança/adolescente: a DRI não classifica o peso; use o escore z (IMC/idade).")
    classe = nc.texto_classificacao(nc.classificar_imc(imc, idade, sexo, 0, criterio_idoso, lms)) if imc and idade is not None else ""
    return {"peso": peso, "tipo_peso": tipo_peso, "altura_m": altura_m, "tipo_alt": tipo_alt,
            "ajustado": ajustado, "ajustou": bool(fluidos or pct), "fluidos": fluidos, "amput_pct": pct,
            "imc": imc, "classe": classe, "kk": kk, "gk": gk, "kcal": kcal,
            "ptn": ajustado * gk if ajustado and gk else None, "dri": dri,
            "dif_dri_pct": (kcal - dri) / dri * 100 if kcal and dri else None, "avisos": avisos}
