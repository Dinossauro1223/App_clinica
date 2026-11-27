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



def _comparar_valor(atual, novo):
    if atual is None or novo is None:
        return {"atual": atual, "substituto": novo, "diferenca": None, "diferenca_percentual": None}
    diferenca = round(novo - atual, 4)
    percentual = round(diferenca / atual * 100, 2) if atual != 0 else None
    return {"atual": atual, "substituto": novo, "diferenca": diferenca,
            "diferenca_percentual": percentual}


def resumir_osmolaridade_preparacoes(item):
    preparacoes = item.get("preparacoes")
    if not isinstance(preparacoes, list) or not preparacoes:
        return {"status": "preparacoes_nao_informadas",
                "mensagem": "A distribuição por preparação não foi informada; osmolaridade diária não será presumida.",
                "preparacoes": []}
    resultados = []
    for indice, preparacao in enumerate(preparacoes, 1):
        dose = preparacao.get("dose")
        agua_misturada = preparacao.get("agua_adicionada_ml", 0)
        calculo = calcular_osmolaridade_diluicao(item, dose, agua_misturada)
        dose_ref = _positivo(item.get("dose_ref"))
        volume_ref = _positivo(item.get("volume_final_ref_ml"))
        unidade_dose = str(item.get("unidade_dose_ref") or "").strip().lower()
        unidade_item = str(item.get("unidade") or "").strip().lower()
        dose_num = _positivo(dose)
        volume_final = None
        if dose_ref and volume_ref and dose_num and unidade_dose == unidade_item:
            agua_num = float(agua_misturada or 0)
            if isfinite(agua_num) and agua_num >= 0:
                volume_final = round(volume_ref * (dose_num / dose_ref) + agua_num, 1)
        resultados.append({"numero": indice, "refeicao": preparacao.get("refeicao"),
                           "dose": dose, "agua_adicionada_ml": agua_misturada,
                           "agua_separada_ml": preparacao.get("agua_separada_ml"),
                           "volume_final_ml": volume_final, **calculo})
    completo = all(x.get("valor") is not None for x in resultados)
    volume_completo = all(x.get("volume_final_ml") is not None for x in resultados)
    return {"status": "calculada" if completo else "dados_incompletos",
            "preparacoes": resultados,
            "volume_final_total_ml": (round(sum(x["volume_final_ml"] for x in resultados), 1)
                                      if volume_completo else None),
            "agua_separada_total_ml": round(sum(
                float(p.get("agua_separada_ml") or 0) for p in preparacoes), 1)}


def comparar_substituicao(itens_atuais, id_substituido, substituto, *,
                           peso_kg=None, meta_kcal=None, meta_proteina_g=None):
    """Compara o aporte diário antes/depois de trocar um suplemento.

    preparacoes é uma lista de administrações independentes com dose,
    agua_adicionada_ml (misturada) e agua_separada_ml (oferta separada).
    Sem essa distribuição, a osmolaridade não é calculada por média diária.
    """
    itens = [dict(x) for x in (itens_atuais or [])]
    atual = next((x for x in itens if x.get("id_suplemento") == id_substituido), None)
    if atual is None:
        raise ValueError("O suplemento que será substituído não foi encontrado na lista atual.")
    novo_item = dict(substituto or {})
    if _positivo(novo_item.get("qtd_dia")) is None:
        raise ValueError("Informe a quantidade diária do suplemento substituto.")
    if str(novo_item.get("unidade") or "").strip().lower() not in ("ml", "g"):
        raise ValueError("A unidade do suplemento substituto deve ser mL ou g.")
    depois_itens = [x for x in itens if x.get("id_suplemento") != id_substituido]
    depois_itens.append(novo_item)
    antes = calcular_oferta(itens, peso_kg, meta_kcal, meta_proteina_g)
    depois = calcular_oferta(depois_itens, peso_kg, meta_kcal, meta_proteina_g)

    def metricas(resultado):
        totais = resultado["totais"]
        kcal, ptn = totais["kcal_100"], totais["ptn_100"]
        peso = resultado["peso_kg"]
        return {
            "energia_kcal_dia": kcal,
            "energia_kcal_kg_dia": round(kcal / peso, 3) if kcal is not None and peso else None,
            "proteina_g_dia": ptn,
            "proteina_g_kg_dia": round(ptn / peso, 3) if ptn is not None and peso else None,
            "sodio_mg_dia": totais["sod_100"],
            "percentual_meta_energetica": resultado["percentual_meta_kcal"],
            "percentual_meta_proteica": resultado["percentual_meta_proteina"],
        }

    m_antes, m_depois = metricas(antes), metricas(depois)
    def volume_produto(lista):
        if all(str(x.get("unidade") or "").strip().lower() == "ml" and _positivo(x.get("qtd_dia")) is not None
               for x in lista):
            return round(sum(float(x["qtd_dia"]) for x in lista), 1)
        if not lista:
            return 0.0
        return None
    m_antes["volume_produto_ml_dia"] = volume_produto(itens)
    m_depois["volume_produto_ml_dia"] = volume_produto(depois_itens)
    osm_atual = resumir_osmolaridade_preparacoes(atual)
    osm_novo = resumir_osmolaridade_preparacoes(novo_item)
    m_antes["volume_preparacao_final_ml_dia"] = osm_atual.get("volume_final_total_ml")
    m_depois["volume_preparacao_final_ml_dia"] = osm_novo.get("volume_final_total_ml")
    comparacoes = {k: _comparar_valor(m_antes[k], m_depois[k]) for k in m_antes}
    def agua_total(lista, campo):
        total = 0.0
        chave_prep = "agua_adicionada_ml" if campo == "agua_ml" else "agua_separada_ml"
        for item in lista:
            preparacoes = item.get("preparacoes")
            if isinstance(preparacoes, list) and preparacoes:
                total += sum(float(p.get(chave_prep) or 0) for p in preparacoes)
            else:
                total += float(item.get(campo) or 0)
        return round(total, 1)
    return {
        "suplemento_atual": {"id_suplemento": atual.get("id_suplemento"), "nome": atual.get("nome")},
        "suplemento_substituto": {"id_suplemento": novo_item.get("id_suplemento"), "nome": novo_item.get("nome")},
        "antes": m_antes, "depois": m_depois, "comparacoes": comparacoes,
        "aporte_completo": antes["completo"] and depois["completo"],
        "pendencias": {"antes": antes["pendencias"], "depois": depois["pendencias"]},
        "agua_misturada_ml_dia": _comparar_valor(agua_total(itens, "agua_ml"),
                                                  agua_total(depois_itens, "agua_ml")),
        "agua_separada_ml_dia": _comparar_valor(agua_total(itens, "agua_separada_ml"),
                                                 agua_total(depois_itens, "agua_separada_ml")),
        "osmolaridade_atual": osm_atual,
        "osmolaridade_substituto": osm_novo,
        "alertas": [f"{rotulo} diminui após a substituição." for chave, rotulo in
                    (("energia_kcal_dia", "A oferta energética"),
                     ("proteina_g_dia", "A oferta proteica"))
                    if comparacoes[chave]["diferenca"] is not None and comparacoes[chave]["diferenca"] < 0],
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
