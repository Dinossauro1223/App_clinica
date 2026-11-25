# -*- coding: utf-8 -*-
"""Regras puras para montar a evolução nutricional individual do NutriLab.

Este módulo não prescreve condutas. Só calcula a partir de parâmetros informados e
autorizados pelo nutricionista; não contém coeficientes clínicos presumidos.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
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
                                maximo_diario_ml=None, dias_alvo=4, *, habilitada=True,
                                autorizada=True, tolerancia=True, restricao=False):
    """Plano matemático diário; só fica ativo com autorização e tolerância clínica."""
    atual = _numero(volume_atual_ml, "Volume atual")
    meta = _numero(volume_meta_ml, "Volume-meta")
    incremento = _numero(incremento_diario_ml, "Incremento diário", minimo=0.000001)
    if not 30 <= incremento <= 40:
        raise ValueError("O incremento diário padrão deve ficar entre 30 e 40 mL.")
    if isinstance(dias_alvo, bool) or int(dias_alvo) != float(dias_alvo) or int(dias_alvo) not in (3, 4):
        raise ValueError("O prazo de referência deve ser de 3 ou 4 dias.")
    limite = meta if maximo_diario_ml in (None, "") else min(meta, _numero(maximo_diario_ml, "Volume máximo"))
    if atual > limite:
        raise ValueError("Oferta atual excede o limite/meta configurado.")
    motivo = None
    if not habilitada:
        motivo = "progressão não solicitada"
    elif not autorizada:
        motivo = "aguarda autorização do nutricionista"
    elif not tolerancia:
        motivo = "intolerância à dieta"
    elif restricao:
        motivo = "restrição clínica"
    elif atual >= limite:
        motivo = "meta ou volume máximo atingido"
    if motivo:
        return {"ativa": False, "motivo": motivo, "volume_atual_ml": atual,
                "volume_meta_ml": meta, "volume_limite_ml": limite, "passos": [],
                "dias_estimados": 0, "atinge_meta_no_prazo": False}
    passos, volume = [], atual
    while volume < limite and len(passos) < 365:
        proximo = min(limite, volume + incremento)
        passos.append({"dia": len(passos) + 1, "volume_total_ml": proximo,
                       "incremento_ml": proximo - volume})
        volume = proximo
    dias_estimados = len(passos)
    return {"ativa": True, "motivo": None, "volume_atual_ml": atual,
            "volume_meta_ml": meta, "volume_limite_ml": limite, "passos": passos,
            "dias_estimados": dias_estimados,
            "atinge_meta_no_prazo": limite >= meta and dias_estimados <= int(dias_alvo)}


def formatar_numero_pt(valor, casas=0):
    """Formata números no padrão brasileiro, com separador de milhar e decimal."""
    n = float(valor)
    texto = f"{n:,.{int(casas)}f}"
    texto = texto.replace(",", "\0").replace(".", ",").replace("\0", ".")
    if casas:
        texto = texto.rstrip("0").rstrip(",")
    return texto


def estimar_tempo_bomba(volume_adicional_ml, taxa_estimativa_ml_h=10):
    volume = _numero(volume_adicional_ml, "Volume adicional")
    taxa = _numero(taxa_estimativa_ml_h, "Taxa estimativa", minimo=0.000001)
    return volume / taxa



def calcular_oferta_enteral(volume_por_etapa_ml, numero_etapas, kcal_100ml, proteina_100ml):
    """Calcula oferta diária a partir da composição cadastrada por 100 mL da fórmula."""
    volume_etapa = _numero(volume_por_etapa_ml, "Volume por etapa", minimo=0.000001)
    etapas = _numero(numero_etapas, "Número de etapas", minimo=1)
    if int(etapas) != etapas:
        raise ValueError("Número de etapas deve ser inteiro.")
    kcal = _numero(kcal_100ml, "Energia por 100 mL", minimo=0.000001)
    ptn = _numero(proteina_100ml, "Proteína por 100 mL", minimo=0.000001)
    volume_total = volume_etapa * int(etapas)
    return {"volume_por_etapa_ml": volume_etapa, "etapas": int(etapas), "volume_total_ml": volume_total,
            "kcal_dia": volume_total * kcal / 100, "proteina_g_dia": volume_total * ptn / 100,
            "kcal_100ml": kcal, "proteina_100ml": ptn}


def calcular_proxima_antropometria(data_avaliacao, grau_nrs, intervalos=None):
    """Reaproveita a agenda NRS-2002 já configurável no NutriLab."""
    from nrs2002 import proxima_reavaliacao
    data = datetime.strptime(_data_br_ou_iso(data_avaliacao), "%Y-%m-%d").date()
    return proxima_reavaliacao(data, grau_nrs, intervalos).strftime("%d/%m/%Y")


def _data_br_ou_iso(valor):
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(valor), formato).date().isoformat()
        except (TypeError, ValueError):
            pass
    raise ValueError("Data antropométrica inválida.")


def aviso_bomba(volume_atual_ml, volume_meta_ml, usa_bomba, taxa_estimativa_ml_h=10):
    """Retorna aviso apenas para dieta enteral com bomba; 10 mL/h é estimativa, não prescrição."""
    if not usa_bomba:
        return None
    atual = _numero(volume_atual_ml, "Volume atual")
    meta = _numero(volume_meta_ml, "Volume-meta")
    adicional = max(0.0, meta - atual)
    horas = estimar_tempo_bomba(adicional, taxa_estimativa_ml_h)
    return {"volume_adicional_ml": adicional, "horas_estimadas": horas,
            "texto": (f"Atenção: faltam aproximadamente {adicional:.0f} mL para atingir o volume correspondente "
                      f"à meta nutricional. Considerando {taxa_estimativa_ml_h:g} mL/h em bomba de infusão, "
                      f"esse volume corresponde a aproximadamente {horas:.1f} horas estimadas adicionais de infusão.")}


def formatar_antropometria(dados):
    """Formata antropometria compacta, preservando origem e rastreabilidade."""
    data = dados.get("data") or date.today().strftime("%d/%m/%Y")
    idade = dados.get("idade_anos")
    if idade is None:
        idade = idade_em_anos(dados.get("data_nascimento"), dados.get("data_referencia") or data)
    partes = [f"Idade: {idade if idade is not None else 'não informada'} anos"]
    origem_peso = str(dados.get("peso_origem") or "").upper()
    origem_altura = str(dados.get("altura_origem") or "").upper()
    origem_peso = {"R": "A", "REAL": "A", "AFERIDO": "A", "ESTIMADO": "E"}.get(origem_peso, origem_peso)
    origem_altura = {"R": "A", "REAL": "A", "AFERIDA": "A", "ESTIMADA": "E"}.get(origem_altura, origem_altura)
    if origem_peso not in {"A", "E"} or origem_altura not in {"A", "E"}:
        raise ValueError("Origem do peso e da altura deve ser A (aferido) ou E (estimado).")
    if origem_peso == "E" or origem_altura == "E":
        for chave, rotulo in (("aj_cm", "AJ"), ("pp_cm", "PP"), ("pb_cm", "PB")):
            if dados.get(chave) not in (None, ""):
                partes.append(f"{rotulo}: {formatar_numero_pt(_numero(dados[chave], rotulo), 1)} cm")
    if dados.get("altura_m") is not None:
        altura = _numero(dados["altura_m"], "Altura", minimo=0.000001)
    elif dados.get("altura_cm") is not None:
        altura = _numero(dados["altura_cm"], "Altura", minimo=0.000001) / 100
    else:
        raise ValueError("Altura ausente.")
    partes.append(f"ALT: {formatar_numero_pt(altura, 2)} m ({origem_altura})")
    peso = _numero(dados.get("peso_kg"), "Peso", minimo=0.000001)
    peso_txt = f"PESO: {formatar_numero_pt(peso, 1)} kg ({origem_peso}"
    if dados.get("peso_corrigido"):
        peso_txt += "; corrigido"
    partes.append(peso_txt + ")")
    imc = calcular_imc(peso, altura)
    classificacao = str(dados.get("imc_class") or "classificação pendente")
    return f"**Antropometria {data}:** " + "; ".join(partes) + f"; IMC: {formatar_numero_pt(imc, 1)} kg/m² ({classificacao})."


def gerar_evolucao(dados):
    """Gera a evolução clínica a partir dos dados estruturados."""
    linhas = [formatar_antropometria(dados["antropometria"])]
    metas = dados.get("metas")
    if metas:
        linhas.append("**Metas nutricionais:** " +
            f"Kcal/dia: {formatar_numero_pt(metas['kcal_dia'])} kcal ({formatar_numero_pt(metas['kcal_kg'], 1)} kcal/kg); " +
            f"PTN/dia: {formatar_numero_pt(metas['proteina_g_dia'], 1)} g ({formatar_numero_pt(metas['proteina_g_kg'], 1)} g/kg).")
    via = str(dados.get("via") or "").strip().casefold()
    enteral = via == "enteral"
    oferta = dados.get("oferta")
    if enteral and metas and oferta and oferta.get("kcal_dia") is not None and oferta.get("proteina_g_dia") is not None:
        adeq = calcular_adequacao(oferta["kcal_dia"], oferta["proteina_g_dia"],
                                  metas["kcal_dia"], metas["proteina_g_dia"])
        linhas.append("**Adequação da meta:** " +
            f"Kcal/dia: {formatar_numero_pt(adeq['kcal_dia'])} kcal ({formatar_numero_pt(adeq['adequacao_kcal_pct'], 1)}% de adequação); " +
            f"PTN/dia: {formatar_numero_pt(adeq['proteina_g_dia'], 1)} g ({formatar_numero_pt(adeq['adequacao_proteina_pct'], 1)}% de adequação).")
    linhas.append(f"**DVA:** {'Sim' if dados.get('dva') else 'Não'}.")
    linhas.append(f"**Via de alimentação:** {'Enteral' if enteral else 'Oral' if via == 'oral' else dados.get('via') or 'não informada'}.")
    if enteral:
        tne, selecionados = classificar_tne(dados.get("tne_motivos") or [])
        linhas.append(f"**TNE:** {tne}" + (f" ({' e '.join(selecionados)})." if selecionados else "."))
        dieta = dados.get("dieta_enteral") or {}
        if dieta.get("nome") and dieta.get("volume_por_etapa_ml") is not None and dieta.get("etapas") is not None:
            volume_etapa = _numero(dieta["volume_por_etapa_ml"], "Volume por etapa")
            etapas = int(_numero(dieta["etapas"], "Etapas", minimo=1))
            volume_total = volume_etapa * etapas
            linhas.append("**Dieta enteral ofertada:** " +
                f"{dieta['nome']} — {formatar_numero_pt(volume_etapa, 1)} mL/etapa × {etapas} etapas, " +
                f"totalizando {formatar_numero_pt(volume_total)} mL/dia.")
        progressao = dados.get("progressao_enteral") or {}
        bomba = dados.get("bomba") or {}
        if progressao.get("autorizada") and progressao.get("plano", {}).get("ativa"):
            atual = _numero(progressao["volume_atual_ml"], "Volume atual")
            meta = _numero(progressao["volume_meta_ml"], "Volume-meta")
            incremento = _numero(progressao.get("incremento_diario_ml", 35), "Incremento diário", minimo=0.000001)
            prazo = progressao["plano"].get("dias_estimados")
            detalhe = f" Previsão matemática: {prazo} dia(s)." if prazo is not None else ""
            linhas.append("**Evolução da dieta:** " +
                f"Oferta atual de {formatar_numero_pt(atual)} mL/dia, com progressão programada de " +
                f"{formatar_numero_pt(incremento)} mL/dia até atingir {formatar_numero_pt(meta)} mL/dia.{detalhe}")
        elif not bomba.get("usa_bomba"):
            linhas.append("**Evolução da dieta:** Progressão de aproximadamente 30–40 mL/dia, conforme tolerância e conduta nutricional.")
        if bomba.get("usa_bomba") and oferta and oferta.get("volume_total_ml") is not None and oferta.get("volume_meta_ml") is not None:
            aviso = aviso_bomba(oferta["volume_total_ml"], oferta["volume_meta_ml"], True,
                                bomba.get("taxa_estimativa_ml_h", 10))
            if aviso:
                linhas.append("**Estimativa de bomba:** " + aviso["texto"])
    elif via == "oral":
        tno = dados.get("tno")
        if tno:
            if tno not in TNO_PERCENTUAIS:
                raise ValueError("Classificação TNO inválida.")
            linhas.append(f"**TNO:** {tno} ({TNO_PERCENTUAIS[tno]}% de consumo estimado).")
        porcao = dados.get("porcao_oral_ml")
        if dados.get("porcao_oral_autorizada") and porcao not in (None, ""):
            linhas.append(f"**Porção oral autorizada pelo nutricionista:** {formatar_numero_pt(_numero(porcao, 'Porção oral'))} mL.")
    if dados.get("dieta_oral"):
        dieta = dados["dieta_oral"]
        consistencia = dieta.get("consistencia")
        if consistencia == "Líq/Past":
            consistencia = "Líquida pastosa"
        itens = [consistencia] if consistencia else []
        caracteristicas = [str(x) for x in dieta.get("caracteristicas", []) if x]
        if itens or caracteristicas:
            if len(caracteristicas) > 1:
                caracteristicas_txt = ", ".join(caracteristicas[:-1]) + " e " + caracteristicas[-1]
            else:
                caracteristicas_txt = ", ".join(caracteristicas)
            complemento = "p. " + caracteristicas_txt if caracteristicas_txt else ""
            linhas.append("**Dieta oral ofertada:** " + ", ".join(itens + ([complemento] if complemento else [])) + ".")
    if dados.get("suplementacao"):
        itens = []
        for s in dados["suplementacao"]:
            qtd = _numero(s.get("quantidade"), "Quantidade", minimo=0.000001)
            etapas = int(_numero(s.get("etapas"), "Etapas", minimo=1))
            itens.append(f"{s['nome']} — {formatar_numero_pt(qtd, 1)} {s['unidade']}/etapa × {etapas} etapas")
        linhas.append("**Suplementação:** " + " + ".join(itens) + ".")
    if dados.get("observacoes"):
        linhas.append("**Observações:** " + str(dados["observacoes"]).strip())
    if dados.get("conduta"):
        linhas.append("**Conduta:** " + str(dados["conduta"]).strip())
    if dados.get("estagiarios"):
        nomes = dados["estagiarios"] if isinstance(dados["estagiarios"], (list, tuple)) else [dados["estagiarios"]]
        linhas.append("**Estagiário:** " + ", ".join(str(x) for x in nomes) + ".")
    if dados.get("nutricionistas"):
        nomes = dados["nutricionistas"] if isinstance(dados["nutricionistas"], (list, tuple)) else [dados["nutricionistas"]]
        linhas.append("**Nutricionista responsável:** " + "; ".join(str(x) for x in nomes) + ".")
    return "\n\n".join(linhas)


def _data_iso(valor):
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(valor), formato).date()
        except (TypeError, ValueError):
            pass
    return None


def gerar_alertas_mapa(linhas, data_referencia=None):
    """Agrupa evolução enteral, ausência de progressão e oferta abaixo da meta."""
    data_ref = _data_iso(data_referencia) or date.today()
    grupos = {"evoluiram": [], "nao_evoluiram": [], "abaixo_meta": []}
    for linha in linhas or []:
        registro = linha.get("registro") or {}
        if str(registro.get("via") or "").casefold() != "enteral":
            continue
        evo = registro.get("evolucao") or {}
        if evo.get("status_evolucao") != "fechada" and not evo.get("fechada"):
            grupos["nao_evoluiram"].append({
                "id_leito": registro.get("id_leito"), "leito": (linha.get("leito") or {}).get("codigo", ""),
                "nome": registro.get("nome_paciente", ""), "motivo": "evolução ainda não fechada",
                "volume_atual_ml": None, "volume_meta_ml": None,
            })
            continue
        dieta = evo.get("dieta_enteral") or {}
        progressao = evo.get("progressao_enteral") or {}
        etapas = int(dieta.get("etapas") or 1)
        volume_inicial_etapa = dieta.get("volume_por_etapa_ml")
        if volume_inicial_etapa in (None, ""):
            volume_inicial = None
        else:
            volume_inicial = float(volume_inicial_etapa) * etapas
        plan = progressao.get("plano") or {}
        passos = plan.get("passos") or []
        inicio = _data_iso(evo.get("data_evolucao") or registro.get("data")) or data_ref
        dias = max(0, (data_ref - inicio).days)
        anterior = volume_inicial
        atual = volume_inicial
        if progressao.get("autorizada") and passos:
            if dias:
                atual = float(passos[min(dias - 1, len(passos) - 1)]["volume_total_ml"])
                if dias > 1:
                    anterior = float(passos[min(dias - 2, len(passos) - 1)]["volume_total_ml"])
            incremento = max(0.0, atual - (anterior if anterior is not None else atual))
            if incremento > 0:
                grupos["evoluiram"].append({
                    "id_leito": registro.get("id_leito"), "leito": (linha.get("leito") or {}).get("codigo", ""),
                    "nome": registro.get("nome_paciente", ""), "volume_anterior_ml": anterior,
                    "volume_atual_ml": atual, "volume_meta_ml": progressao.get("volume_meta_ml"),
                    "incremento_ml": incremento,
                })
            else:
                if atual is not None and progressao.get("volume_meta_ml") and atual >= float(progressao["volume_meta_ml"]):
                    motivo = "meta atingida"
                elif plan.get("volume_limite_ml") is not None and progressao.get("volume_meta_ml") and float(plan["volume_limite_ml"]) < float(progressao["volume_meta_ml"]):
                    motivo = "volume máximo configurado atingido"
                else:
                    motivo = "sem aumento previsto para a data"
                grupos["nao_evoluiram"].append({
                    "id_leito": registro.get("id_leito"), "leito": (linha.get("leito") or {}).get("codigo", ""),
                    "nome": registro.get("nome_paciente", ""), "motivo": motivo,
                    "volume_atual_ml": atual, "volume_meta_ml": progressao.get("volume_meta_ml"),
                })
        else:
            motivo = progressao.get("motivo") or (
                "aguarda autorização do nutricionista" if progressao.get("solicitada") else "progressão não programada")
            grupos["nao_evoluiram"].append({
                "id_leito": registro.get("id_leito"), "leito": (linha.get("leito") or {}).get("codigo", ""),
                "nome": registro.get("nome_paciente", ""), "motivo": motivo,
                "volume_atual_ml": volume_inicial, "volume_meta_ml": progressao.get("volume_meta_ml"),
            })
        oferta = evo.get("oferta") or {}
        meta = evo.get("metas") or {}
        kcal_100 = dieta.get("kcal_100") or oferta.get("kcal_100ml")
        ptn_100 = dieta.get("ptn_100") or oferta.get("proteina_100ml")
        if atual is None:
            atual = oferta.get("volume_total_ml")
        if atual is not None and kcal_100 not in (None, 0) and meta.get("kcal_dia"):
            kcal_atual = float(atual) * float(kcal_100) / 100
            meta_kcal = float(meta["kcal_dia"])
            adequacao = kcal_atual / meta_kcal * 100
            ptn_atual = float(atual) * float(ptn_100) / 100 if ptn_100 else None
            adequacao_ptn = (ptn_atual / float(meta["proteina_g_dia"]) * 100
                             if ptn_atual is not None and meta.get("proteina_g_dia") else None)
            for grupo in ("evoluiram", "nao_evoluiram"):
                for alerta in grupos[grupo]:
                    if alerta.get("id_leito") == registro.get("id_leito") and alerta.get("nome") == registro.get("nome_paciente"):
                        alerta["adequacao_kcal_pct"] = adequacao
                        alerta["adequacao_proteina_pct"] = adequacao_ptn
            if kcal_atual < meta_kcal:
                deficit = meta_kcal - kcal_atual
                volume_adicional = deficit / (float(kcal_100) / 100)
                grupos["abaixo_meta"].append({
                    "id_leito": registro.get("id_leito"), "leito": (linha.get("leito") or {}).get("codigo", ""),
                    "nome": registro.get("nome_paciente", ""), "kcal_atual": kcal_atual,
                    "meta_kcal": meta_kcal, "adequacao_kcal_pct": adequacao,
                    "deficit_kcal": deficit, "volume_adicional_ml": volume_adicional,
                    "proteina_atual_g": ptn_atual, "meta_proteina_g": meta.get("proteina_g_dia"),
                })
    return grupos
