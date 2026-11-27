# -*- coding: utf-8 -*-
"""Cálculo auditável do aporte de suplementos/fórmulas em relação às metas informadas.

Não estima metas clínicas. O profissional informa meta energética/proteica; valores ausentes
na ficha ou na dose permanecem pendentes e nunca são substituídos por produtos semelhantes.
"""
from math import isfinite


def _positivo(valor):
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    return n if isfinite(n) and n > 0 else None


def calcular_oferta(itens, peso_kg=None, meta_kcal=None, meta_proteina_g=None):
    """Calcula aporte diário e participação nas metas.

    Cada item deve trazer qtd_dia, unidade ('ml' ou 'g') e composição por 100 unidades:
    kcal_100, ptn_100, lip_100, carb_100 e sod_100. Composição ausente não é inferida.
    Totais de cada nutriente só são considerados completos quando todos os itens têm
    dose, unidade e valor daquele nutriente.
    """
    peso = _positivo(peso_kg)
    meta_e = _positivo(meta_kcal)
    meta_p = _positivo(meta_proteina_g)
    campos = ("kcal_100", "ptn_100", "lip_100", "carb_100", "sod_100")
    resultados = []
    totais = {c: 0.0 for c in campos}
    completos = {c: True for c in campos}
    pendencias = []

    for indice, item in enumerate(itens or [], 1):
        nome = str(item.get("nome") or f"Item {indice}")
        qtd = _positivo(item.get("qtd_dia"))
        unidade = str(item.get("unidade") or "").strip().lower()
        valido_un = unidade in ("ml", "g")
        aporte = {}
        motivos = []
        if qtd is None:
            motivos.append("quantidade diária não informada")
        if not valido_un:
            motivos.append("unidade não informada ou incompatível")
        for campo in campos:
            composicao = item.get(campo)
            try:
                composicao = float(composicao) if composicao is not None else None
            except (TypeError, ValueError):
                composicao = None
            if composicao is None or not isfinite(composicao) or composicao < 0:
                aporte[campo] = None
                completos[campo] = False
            elif qtd is None or not valido_un:
                aporte[campo] = None
                completos[campo] = False
            else:
                aporte[campo] = composicao * qtd / 100.0
                totais[campo] += aporte[campo]
        if motivos or any(aporte[c] is None for c in campos):
            pendencias.append({"nome": nome, "motivos": motivos or ["ficha técnica incompleta"]})
        resultados.append({"nome": nome, "quantidade": qtd, "unidade": unidade or None, **aporte})

    totais_saida = {c: (round(totais[c], 4) if completos[c] else None) for c in campos}
    kcal = totais_saida["kcal_100"]
    proteina = totais_saida["ptn_100"]
    return {
        "itens": resultados,
        "totais": totais_saida,
        "meta_kcal": meta_e,
        "meta_proteina_g": meta_p,
        "peso_kg": peso,
        "percentual_meta_kcal": round(kcal / meta_e * 100, 2) if kcal is not None and meta_e else None,
        "percentual_meta_proteina": round(proteina / meta_p * 100, 2) if proteina is not None and meta_p else None,
        "proteina_g_kg": round(proteina / peso, 3) if proteina is not None and peso else None,
        "completo": not pendencias,
        "pendencias": pendencias,
    }


def calcular_osmolaridade_diluicao(item, dose, agua_adicionada_ml=0):
    """Estima mOsm/L com base em osmolaridade, dose e volume final de referência.\n\n    Dose e água representam os totais diários do item. A estimativa pressupõe que\n    todas as ofertas mantenham a mesma proporção de produto/água. Se as preparações\n    tiverem diluições diferentes, cada uma deve ser avaliada separadamente; este\n    resumo diário não substitui o cálculo individual.\n    """
    unidade = str(item.get("unidade_osmolaridade") or "mOsm/L").strip()
    if unidade != "mOsm/L":
        return {"valor": None, "status": "unidade_incompativel", "mensagem": "A ficha informa mOsm/kg; não é possível converter para mOsm/L sem dados de densidade."}
    osm, dose_ref, vol_ref, dose_atual = (_positivo(item.get("osmolaridade_ref")), _positivo(item.get("dose_ref")), _positivo(item.get("volume_final_ref_ml")), _positivo(dose))
    if agua_adicionada_ml in (None, ""):
        agua = 0.0
    else:
        try:
            agua = float(agua_adicionada_ml)
        except (TypeError, ValueError):
            agua = None
        if agua is None or not isfinite(agua) or agua < 0:
            return {"valor": None, "status": "agua_invalida", "mensagem": "Quantidade de água inválida."}
    if osm is None or dose_ref is None or vol_ref is None:
        return {"valor": None, "status": "referencia_incompleta", "mensagem": "Informe osmolaridade, dose de referência e volume final de preparo da ficha técnica."}
    if dose_atual is None:
        return {"valor": None, "status": "dose_ausente", "mensagem": "Informe a quantidade do produto nesta preparação."}
        if str(item.get("unidade_dose_ref") or "").strip().lower() != str(item.get("unidade") or "").strip().lower():
        return {"valor": None, "status": "unidade_dose_incompativel", "mensagem": "A unidade da dose atual difere da unidade de referência da ficha."}
    fator = dose_atual / dose_ref
    osmoles = osm * (vol_ref / 1000.0) * fator
    volume_final_ml = vol_ref * fator + agua
    if volume_final_ml <= 0:
        return {"valor": None, "status": "volume_invalido", "mensagem": "Volume final inválido."}
    return {"valor": round(osmoles / (volume_final_ml / 1000.0), 1), "status": "estimada", "mensagem": "Estimativa matemática baseada na ficha de referência; não equivale a análise laboratorial.", "volume_final_ml": round(volume_final_ml, 1)}
