# -*- coding: utf-8 -*-
"""Avaliação nutricional (lógica pura, sem interface): peso ajustado por edema/ascite/amputações,
AJ a partir da altura (planilha 'Cálculos – Amputado'), DRI (EER, IOM 2005) e texto da evolução PEP.

Peso e altura estimados vêm de nutri_calculos (planilha 'Peso-Alt'). Nada aqui gera conduta:
a conduta é sempre o texto digitado pelo nutricionista."""
import nutri_calculos as nc

GLOSSARIO = {
    "DVA": "drogas vasoativas", "AHGT": "hemoglicoteste (glicemia capilar)", "F.I.": "função intestinal",
    "V.O.": "via oral", "TNE": "terapia nutricional enteral", "TNO": "terapia nutricional oral",
    "PTN": "proteína", "AJ": "altura do joelho", "PB": "perímetro do braço",
    "DRI": "ingestão dietética de referência", "IMC": "índice de massa corporal"}


def rotulo_crn(crn):
    """'12345' -> 'CRN 12345'; 'CRN-6 12345' fica como está."""
    return crn if crn.upper().startswith("CRN") else f"CRN {crn}"


def sig(sigla):
    """'DVA' -> 'DVA — drogas vasoativas' (sigla sempre acompanhada do significado)."""
    return f"{sigla} — {GLOSSARIO[sigla]}"


# nível: (membro, % do peso corporal). Cada membro conta uma vez: marque só o nível mais alto.
AMPUTACOES = {"Mão": ("sup", 0.7), "Antebraço + mão": ("sup", 2.3), "Braço inteiro": ("sup", 5.0),
              "Pé": ("inf", 1.5), "Perna abaixo do joelho": ("inf", 5.9), "Perna inteira": ("inf", 16.0)}
EDEMA = {"Ausente": 0, "+ tornozelo (1 kg)": 1, "++ joelho (3,5 kg)": 3.5,
         "+++ raiz da coxa (5,5 kg)": 5.5, "++++ anasarca (11 kg)": 11}
ASCITE = {"Ausente": 0, "Leve (2,2 kg)": 2.2, "Moderada (6 kg)": 6, "Grave (14 kg)": 14}

# Atividade: índice 0..3 (sedentário, pouco ativo, ativo, muito ativo) — IOM 2005.
_PA = {"ad": {"H": (1, 1.11, 1.25, 1.48), "M": (1, 1.12, 1.27, 1.45)},
       "so": {"H": (1, 1.12, 1.29, 1.59), "M": (1, 1.16, 1.27, 1.44)},
       "cr": {"H": (1, 1.13, 1.26, 1.42), "M": (1, 1.16, 1.31, 1.56)}}


def pct_amputacao(qtd):
    """qtd = {nível: 0|1|2}. Soma o % do peso perdido; no máximo 2 membros superiores e 2 inferiores."""
    membros, pct = {"sup": 0, "inf": 0}, 0.0
    for nivel, n in qtd.items():
        if n:
            membro, p = AMPUTACOES[nivel]
            membros[membro] += n
            pct += p * n
    if membros["sup"] > 2 or membros["inf"] > 2:
        raise ValueError("Há mais de dois membros superiores ou inferiores marcados: "
                         "marque só o nível mais alto de cada membro.")
    return pct


def peso_ajustado(peso, fluidos_kg=0.0, amput_pct=0.0):
    """Peso 'seco' e íntegro: (peso − edema − ascite) / (1 − % amputado)."""
    base = peso - fluidos_kg
    if base <= 0:
        raise ValueError("Edema + ascite iguais ou maiores que o peso: confira os dados.")
    if amput_pct >= 100:
        raise ValueError("Soma das amputações ≥ 100%: revise os níveis marcados.")
    return base / (1 - amput_pct / 100)


def aj_da_altura(altura_cm, idade, sexo):
    """AJ (cm) obtida da altura estimada — inverso de Chumlea 1985, como em 'Cálculos – Amputado'."""
    a, b, k = nc._ALTURA_1985[nc.norm_sexo(sexo)]
    aviso = [] if 60 <= idade <= 90 else ["AJ calculada com equação validada para 60–90 anos."]
    return (altura_cm - a - k * idade) / b, aviso


def eer_dri(sexo, idade, peso, altura_m, atividade=0, imc=None):
    """Necessidade de energia (kcal/dia), DRI/IOM 2005. None se os dados forem insuficientes (< 3 anos)."""
    s = nc.norm_sexo(sexo)
    if s is None or None in (idade, peso, altura_m) or idade < 3:
        return None
    if idade >= 19:
        if imc is not None and imc >= 25:  # TEE para manutenção de peso em sobrepeso/obesidade
            p = _PA["so"][s][atividade]
            return (1086 - 10.1 * idade + p * (13.7 * peso + 416 * altura_m)) if s == "H" else \
                   (448 - 7.95 * idade + p * (11.4 * peso + 619 * altura_m))
        p = _PA["ad"][s][atividade]
        return (662 - 9.53 * idade + p * (15.91 * peso + 539.6 * altura_m)) if s == "H" else \
               (354 - 6.91 * idade + p * (9.36 * peso + 726 * altura_m))
    p, dep = _PA["cr"][s][atividade], (20 if idade < 9 else 25)  # 3–18 anos: EER + depósito de energia
    return (88.5 - 61.9 * idade + p * (26.7 * peso + 903 * altura_m) + dep) if s == "H" else \
           (135.3 - 30.8 * idade + p * (10 * peso + 934 * altura_m) + dep)


def aporte_suplemento(ficha, quantidade):
    """ficha = linha de Mapa_Suplementos; quantidade/dia na unidade da ficha (ml ou g, sem conversão).
    Devolve (kcal, g de PTN ou None) ou None se a ficha não tiver kcal/100 ('ficha pendente': nunca se estima)."""
    if not quantidade or quantidade <= 0 or ficha.get("kcal_100") is None:
        return None
    ptn = ficha.get("ptn_100")
    return quantidade * ficha["kcal_100"] / 100, (quantidade * ptn / 100 if ptn is not None else None)


def resumo_suplementos(itens, kcal_meta=None, dri=None, ptn_meta=None):
    """itens = [(ficha, quantidade/dia)]. Devolve texto (campo Suplementação da evolução), detalhe (tela) e totais."""
    F, linhas, kcal, ptn = nc.fmt_num, [], 0.0, 0.0
    for ficha, q in itens:
        un, a = ficha.get("emb_un") or "ml", aporte_suplemento(ficha, q)
        if a is None:
            linhas.append(f"{ficha['nome']} {F(q, 0)} {un}/dia (ficha pendente)")
            continue
        kcal, ptn = kcal + a[0], ptn + (a[1] or 0.0)
        linhas.append(f"{ficha['nome']} {F(q, 0)} {un}/dia ({F(a[0], 0)} kcal"
                      + (f"; {F(a[1], 1)} g PTN)" if a[1] is not None else ")"))
    total = ""
    if kcal:
        ref = [f"{F(kcal / v * 100, 0)}% {n}" for v, n in ((kcal_meta, "da meta"), (dri, "da DRI")) if v]
        total = f"Aporte: {F(kcal, 0)} kcal/dia" + (f" ({'; '.join(ref)})" if ref else "")
        if ptn:
            total += f", {F(ptn, 1)} g PTN/dia" + (f" ({F(ptn / ptn_meta * 100, 0)}% da meta de PTN)" if ptn_meta else "")
        total += "."
    return {"texto": "; ".join(linhas) + (". " + total if total else ".") if linhas else "",
            "detalhe": "\n".join(linhas + ([total] if total else [])), "kcal": kcal, "ptn": ptn}


def calcular(d, lms=None, criterio_idoso="lipschitz"):
    """d: sexo, cor, idade, peso, aj, pb, altura (cm), edema, ascite, amputacoes {nível: qtd},
    kcalkg, ptnkg, atividade (0–3). Devolve peso/altura (aferido ou estimado), peso ajustado, IMC,
    metas, DRI e avisos."""
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
        aj, w = aj_da_altura(alt_cm, idade, sexo)
        avisos += ["AJ calculada a partir da altura informada (planilha 'Cálculos – Amputado'): "
                   f"{aj:.1f} cm."] + w
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
            e = nc.estimar_altura(aj, sexo, cor, idade, "planilha")
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
    dri = eer_dri(sexo, idade, ajustado, altura_m, int(d.get("atividade") or 0), imc) if imc else None
    if imc and idade is not None:
        if idade < 3:
            avisos.append("DRI indisponível abaixo de 3 anos neste programa.")
        elif idade < 19:
            avisos.append("Criança/adolescente: a DRI não classifica o peso; use o escore z (IMC/idade).")
    classe = nc.texto_classificacao(nc.classificar_imc(imc, idade, sexo, 0, criterio_idoso, lms)) if imc and idade is not None else ""
    return {"peso": peso, "tipo_peso": tipo_peso, "altura_m": altura_m, "tipo_alt": tipo_alt, "ajustado": ajustado,
            "ajustou": bool(fluidos or pct), "fluidos": fluidos, "amput_pct": pct, "imc": imc, "classe": classe,
            "kk": kk, "gk": gk, "kcal": kcal, "ptn": ajustado * gk if ajustado and gk else None, "dri": dri,
            "dif_dri_pct": (kcal - dri) / dri * 100 if kcal and dri else None, "avisos": avisos}


def montar_evolucao(f, r, ant, assinatura):
    """Texto da evolução PEP. f = campos do formulário; r = calcular(); ant = cabeçalho da evolução anterior
    (dict) ou None. Com anterior, o cabeçalho repete os dados dela e os dados novos vão para a CONDUTA."""
    F = lambda v, c=1: nc.fmt_num(v, c, "n/a")
    X = lambda k: (f.get(k) or "").strip() or "n/a"
    novo = ant is None
    c = {"peso": r["ajustado"], "tp": r["tipo_peso"], "alt": r["altura_m"], "ta": r["tipo_alt"],
         "kk": r["kk"], "gk": r["gk"], "ajustou": r["ajustou"]} if novo else ant
    imc = c["peso"] / c["alt"] ** 2 if c.get("peso") and c.get("alt") else None
    texto_cx = (f.get("cx") or "").strip() or "________"
    if novo:
        cond = f"Nova conduta (avaliação inicial): {texto_cx}"
    else:
        cond = "Mantida." if f.get("ct") == "Mantida" else f"Nova conduta: {texto_cx}"
    if r["ajustado"]:
        cond += (f"\n{'Avaliação inicial' if novo else 'Dados atuais para comparação'}: peso {F(r['peso'])} kg "
                 f"({(r['tipo_peso'] or '').lower()})"
                 + (f", ajustado {F(r['ajustado'])} kg (edema/ascite/amputação)" if r["ajustou"] else "")
                 + f"; alt. {F(r['altura_m'], 2)} m ({(r['tipo_alt'] or '').lower()}); IMC {F(r['imc'])} kg/m²; "
                 f"meta {F(r['kk'], 0)} kcal/kg/dia = {F(r['kcal'], 0)} kcal/dia"
                 + (f" (DRI: {F(r['dri'], 0)} kcal/dia)" if r["dri"] else "")
                 + f"; {F(r['ptn'], 0)} g PTN/dia ({F(r['gk'], 1)} g/kg).")
    ptn = c["gk"] * c["peso"] if c.get("gk") and c.get("peso") else None
    topo = ("NOVO PACIENTE: sem evolução anterior no histórico; o cabeçalho traz os dados da avaliação inicial.\n"
            if novo else "")
    return (f"{topo}ADMISSÃO: {f.get('adm') or '__/__/____'}. EVOLUÇÃO: {f.get('evo') or '__/__/____'}.\n"
            f"Peso (Kg): {F(c.get('peso'))} ({c.get('tp') or 'n/a'}{', ajustado' if c.get('ajustou') else ''}). "
            f"Alt. (m): {F(c.get('alt'), 2)} ({c.get('ta') or 'n/a'}). IMC: {F(imc)} Kg/m².\n"
            f"Metas nutricionais: {F(c.get('kk'), 0)} Kcal/Kg/dia (referência utilizada para cálculo de necessidades), "
            f"{F(ptn, 0)} g/PTN/dia ({F(c.get('gk'), 1)} g PTN/Kg).\n\n"
            f"DVA: {X('dva')}. AHGT: {X('ahgt')}. Função intestinal (F.I. 24h): {X('fi')}. "
            f"Fezes diarreicas: {X('diar')}.\n\n"
            f"Dietoterapia - Via de alimentação: {X('via')}. Aceitação (V.O.): {X('vo')}. Tolerância: (TNE): {X('tol')}.\n"
            f"TNO: {X('tno')}. Suplementação: {X('sup')}.\n"
            f"TNE: {'n/a' if f.get('via') == 'Oral' else 'sim'}. Volume: ({X('tv')}) ml/h. "
            f"Atinge meta calórica: ({X('tm')}). Proteína: ({X('tp')}) g/Kg de peso.\n\n"
            f"OBSERVAÇÕES: {X('obs')}.\n\nCONDUTA: {cond}\n\nAssinatura eletrônica: {assinatura}")
