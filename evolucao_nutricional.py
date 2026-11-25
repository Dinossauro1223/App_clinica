# -*- coding: utf-8 -*-
"""Regras puras para montar a evolução nutricional individual do NutriLab.

Este módulo não prescreve condutas. Só calcula a partir de parâmetros informados e
autorizados pelo nutricionista; não contém coeficientes clínicos presumidos.
"""
from __future__ import annotations

from datetime import date, datetime
from math import ceil


TNO_PERCENTUAIS = {"Ruim": 25, "Baixa": 50, "Regular": 75, "Boa": 100, "Ótima": 100}
TNE_MOTIVOS = {"retrolimentação", "vômitos", "diarreia"}


def _numero(valor, nome, *, minimo=0):
    if isinstance(valor, bool):
        raise ValueError(f"{nome} inválido.")
    try:
        n = float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError(f"{nome} deve ser numérico.") from None
    if n < minimo:
        raise ValueError(f"{nome} deve ser maior ou igual a {minimo}.")
    return n


def idade_em_anos(data_nascimento, data_referencia=None):
    """Idade completa em anos; retorna None se a data de nascimento estiver ausente."""
    if not data_nascimento:
        return None
    def parse(v):
        if isinstance(v, date):
            return v
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(str(v), fmt).date()
            except ValueError:
                pass
        raise ValueError("Data de nascimento/referência inválida.")
    nasc = parse(data_nascimento)
    ref = parse(data_referencia or date.today())
    if nasc > ref:
        raise ValueError("Data de nascimento posterior à data de referência.")
    return ref.year - nasc.year - ((ref.month, ref.day) < (nasc.month, nasc.day))


def calcular_imc(peso_kg, altura_m):
    peso = _numero(peso_kg, "Peso", minimo=0.000001)
    altura = _numero(altura_m, "Altura", minimo=0.000001)
    return peso / (altura * altura)


def calcular_metas(peso_kg, kcal_kg, proteina_kg):
    peso = _numero(peso_kg, "Peso nutricional", minimo=0.000001)
    kcal = _numero(kcal_kg, "Parâmetro kcal/kg", minimo=0.000001)
    ptn = _numero(proteina_kg, "Parâmetro g/kg", minimo=0.000001)
    return {"kcal_dia": peso * kcal, "proteina_g_dia": peso * ptn,
            "kcal_kg": kcal, "proteina_g_kg": ptn, "peso_referencia_kg": peso}


def calcular_adequacao(energia_ofertada, proteina_ofertada, meta_kcal, meta_proteina_g):
    energia = _numero(energia_ofertada, "Energia ofertada")
    proteina = _numero(proteina_ofertada, "Proteína ofertada")
    kcal_meta = _numero(meta_kcal, "Meta energética", minimo=0.000001)
    ptn_meta = _numero(meta_proteina_g, "Meta proteica", minimo=0.000001)
    return {"kcal_dia": energia, "proteina_g_dia": proteina,
            "adequacao_kcal_pct": energia / kcal_meta * 100,
            "adequacao_proteina_pct": proteina / ptn_meta * 100,
            "deficit_kcal": max(0.0, kcal_meta - energia)}


def classificar_tne(motivos):
    selecionados = {str(x).strip().casefold() for x in (motivos or []) if str(x).strip()}
    desconhecidos = selecionados - TNE_MOTIVOS
    if desconhecidos:
        raise ValueError("Motivo(s) de TNE desconhecido(s): " + ", ".join(sorted(desconhecidos)))
    if selecionados.intersection({"vômitos", "diarreia"}):
        ordem = [x for x in ("vômitos", "diarreia", "retrolimentação") if x in selecionados]
        return "Ruim", ordem
    if "retrolimentação" in selecionados:
        return "Regular", ["retrolimentação"]
    return "Ótima", []


def volume_meta_enteral(meta_kcal, densidade_kcal_ml):
    meta = _numero(meta_kcal, "Meta energética", minimo=0.000001)
    densidade = _numero(densidade_kcal_ml, "Densidade energética", minimo=0.000001)
    return meta / densidade


def planejar_progressao_enteral(volume_atual_ml, volume_meta_ml, incremento_diario_ml=35,
                                maximo_diario_ml=None, dias_alvo=4):
    """Plano matemático; deve ser liberado/ajustado pelo nutricionista antes de executar."""
    atual = _numero(volume_atual_ml, "Volume atual")
    meta = _numero(volume_meta_ml, "Volume-meta")
    incremento = _numero(incremento_diario_ml, "Incremento", minimo=0.000001)
    if isinstance(dias_alvo, bool) or int(dias_alvo) < 1:
        raise ValueError("Dias-alvo deve ser inteiro positivo.")
    limite = meta if maximo_diario_ml is None else min(meta, _numero(maximo_diario_ml, "Volume máximo"))
    if atual > limite:
        raise ValueError("Oferta atual excede o limite/meta configurado.")
    passos = []
    volume = atual
    for dia in range(1, int(dias_alvo) + 1):
        if volume >= limite:
            break
        volume = min(limite, volume + incremento)
        passos.append({"dia": dia, "volume_total_ml": volume, "incremento_ml": volume - (passos[-1]["volume_total_ml"] if passos else atual)})
    dias_estimados = ceil((limite - atual) / incremento) if limite > atual else 0
    return {"volume_atual_ml": atual, "volume_meta_ml": meta, "volume_limite_ml": limite,
            "passos": passos, "dias_estimados": dias_estimados,
            "atinge_meta_no_prazo": dias_estimados <= int(dias_alvo)}


def estimar_tempo_bomba(volume_adicional_ml, taxa_estimativa_ml_h=10):
    volume = _numero(volume_adicional_ml, "Volume adicional")
    taxa = _numero(taxa_estimativa_ml_h, "Taxa estimativa", minimo=0.000001)
    return volume / taxa


def formatar_antropometria(dados):
    """Gera o bloco compacto; medidas auxiliares aparecem quando peso/altura são estimados."""
    data = dados.get("data") or date.today().strftime("%d/%m/%Y")
    idade = dados.get("idade_anos")
    if idade is None:
        idade = idade_em_anos(dados.get("data_nascimento"), dados.get("data_referencia") or data)
    partes = [f"Idade: {idade if idade is not None else 'não informada'} anos"]
    peso_origem = str(dados.get("peso_origem") or "").upper()
    altura_origem = str(dados.get("altura_origem") or "").upper()
    if peso_origem not in {"A", "E"} or altura_origem not in {"A", "E"}:
        raise ValueError("Origem do peso e da altura deve ser A (aferido) ou E (estimado).")
    if peso_origem == "E" or altura_origem == "E":
        for chave, rotulo in (("aj_cm", "AJ"), ("pp_cm", "PP"), ("pb_cm", "PB")):
            if dados.get(chave) not in (None, ""):
                partes.append(f"{rotulo}: {_numero(dados[chave], rotulo)} cm")
    if dados.get("altura_m") is not None:
        altura = _numero(dados["altura_m"], "Altura", minimo=0.000001)
        partes.append(f"ALT: {altura:.2f} m ({altura_origem})")
    elif dados.get("altura_cm") is not None:
        altura = _numero(dados["altura_cm"], "Altura", minimo=0.000001) / 100
        partes.append(f"ALT: {altura:.2f} m ({altura_origem})")
    else:
        raise ValueError("Altura ausente.")
    peso = _numero(dados.get("peso_kg"), "Peso", minimo=0.000001)
    peso_txt = f"PESO: {peso:g} kg ({peso_origem}"
    if dados.get("peso_corrigido"):
        peso_txt += "; corrigido"
    partes.append(peso_txt + ")")
    imc = calcular_imc(peso, altura)
    classificacao = str(dados.get("imc_class") or "classificação pendente")
    return f"**Antropometria {data}:** " + "; ".join(partes) + f". IMC: {imc:.1f} kg/m² ({classificacao})."


def gerar_evolucao(dados):
    """Gera texto somente com dados presentes; adequação apenas para enteral calculável."""
    linhas = [formatar_antropometria(dados["antropometria"])]
    metas = dados.get("metas")
    if metas:
        linhas.append("**Metas nutricionais:** " +
            f"Kcal/dia: {metas['kcal_dia']:.0f} kcal ({metas['kcal_kg']:g} kcal/kg); " +
            f"PTN/dia: {metas['proteina_g_dia']:.1f} g ({metas['proteina_g_kg']:g} g/kg).")
    via = str(dados.get("via") or "").strip().casefold()
    enteral = via == "enteral"
    oferta = dados.get("oferta")
    if enteral and metas and oferta and oferta.get("kcal_dia") is not None and oferta.get("proteina_g_dia") is not None:
        adeq = calcular_adequacao(oferta["kcal_dia"], oferta["proteina_g_dia"],
                                  metas["kcal_dia"], metas["proteina_g_dia"])
        linhas.append("**Adequação da meta:** " +
            f"Kcal/dia: {adeq['kcal_dia']:.0f} kcal ({adeq['adequacao_kcal_pct']:.1f}% de adequação); " +
            f"PTN/dia: {adeq['proteina_g_dia']:.1f} g ({adeq['adequacao_proteina_pct']:.1f}% de adequação).")
    linhas.append(f"**DVA:** {'Sim' if dados.get('dva') else 'Não'}.")
    linhas.append(f"**Via de alimentação:** {'Enteral' if enteral else 'Oral' if via == 'oral' else dados.get('via') or 'não informada'}.")
    if enteral:
        motivos = dados.get("tne_motivos") or []
        tne, selecionados = classificar_tne(motivos)
        linhas.append(f"**TNE:** {tne}" + (f" ({' e '.join(selecionados)})." if selecionados else "."))
    elif via == "oral" and dados.get("tno"):
        tno = dados["tno"]
        if tno not in TNO_PERCENTUAIS:
            raise ValueError("Classificação TNO inválida.")
        linhas.append(f"**TNO:** {tno} ({TNO_PERCENTUAIS[tno]}% de consumo estimado).")
    if dados.get("dieta_oral"):
        dieta = dados["dieta_oral"]
        itens = [dieta.get("consistencia")] if dieta.get("consistencia") else []
        caracteristicas = [x for x in dieta.get("caracteristicas", []) if x]
        if itens or caracteristicas:
            linhas.append("**Dieta oral ofertada:** " + ", ".join(itens + (["p. " + ", ".join(caracteristicas)] if caracteristicas else [])) + ".")
    if dados.get("suplementacao"):
        itens = []
        for s in dados["suplementacao"]:
            qtd = _numero(s.get("quantidade"), "Quantidade", minimo=0.000001)
            etapas = int(_numero(s.get("etapas"), "Etapas", minimo=1))
            itens.append(f"{s['nome']} — {qtd:g} {s['unidade']}/etapa × {etapas} etapas")
        linhas.append("**Suplementação:** " + " + ".join(itens) + ".")
    if dados.get("observacoes"):
        linhas.append("**Observações:** " + str(dados["observacoes"]).strip())
    if dados.get("conduta"):
        linhas.append("**Conduta:** " + str(dados["conduta"]).strip())
    if dados.get("estagiarios"):
        linhas.append("**Estagiário:** " + ", ".join(dados["estagiarios"]) + ".")
    if dados.get("nutricionistas"):
        linhas.append("**Nutricionista responsável:** " + "; ".join(dados["nutricionistas"]) + ".")
    return "\n\n".join(linhas)
