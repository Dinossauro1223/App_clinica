# -*- coding: utf-8 -*-
"""Regras puras para montar a evolução nutricional individual do NutriLab.

Este módulo não prescreve condutas. Só calcula a partir de parâmetros informados e
autorizados pelo nutricionista; não contém coeficientes clínicos presumidos.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from math import ceil, isfinite


TNO_PERCENTUAIS = {"Ruim": 25, "Baixa": 50, "Regular": 75, "Boa": 100, "Ótima": 100}
TNE_MOTIVOS = {"retrolimentação", "vômitos", "diarreia"}


def _numero(valor, nome, *, minimo=0):
    if isinstance(valor, bool):
        raise ValueError(f"{nome} inválido.")
    try:
        n = float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError(f"{nome} deve ser numérico.") from None
    if not isfinite(n) or n < minimo:
        raise ValueError(f"{nome} deve ser um número finito maior ou igual a {minimo}.")
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



def classificar_categoria_tfge(tfge_ml_min_173):
    """Classifica a faixa de TFGe; G1/G2 isoladamente não confirmam DRC."""
    if tfge_ml_min_173 in (None, ""):
        return None
    valor = _numero(tfge_ml_min_173, "TFGe")
    if valor >= 90:
        return "G1"
    if valor >= 60:
        return "G2"
    if valor >= 45:
        return "G3a"
    if valor >= 30:
        return "G3b"
    if valor >= 15:
        return "G4"
    return "G5"


def classificar_albuminuria_mg_g(valor_mg_g):
    """Categorias KDIGO A1 (<30), A2 (30–300) e A3 (>300 mg/g)."""
    if valor_mg_g in (None, ""):
        return None
    valor = _numero(valor_mg_g, "Albuminúria")
    if valor < 30:
        return "A1"
    if valor <= 300:
        return "A2"
    return "A3"


def avaliar_contexto_renal(dados, peso_kg=None, idade_anos=None, diabetes=False):
    """Organiza dados renais e apresenta referência proteica sem alterar metas prescritas.

    A TFGe é recebida do laudo; creatinina, ureia e albumina sérica são apenas
    dados de apoio e não determinam estágio nem meta proteica isoladamente.
    """
    dados = dict(dados or {})
    referencia = str(dados.get("referencia") or "KDIGO 2024").strip()
    if referencia not in ("KDIGO 2024", "KDOQI 2020"):
        raise ValueError("Referência renal inválida.")
    tfge = _numero(dados["tfge"], "TFGe") if dados.get("tfge") not in (None, "") else None
    faixa_tfge = classificar_categoria_tfge(tfge) if tfge is not None else None
    estagio = str(dados.get("estagio") or "").strip().upper() or faixa_tfge
    if estagio and estagio not in ("G1", "G2", "G3A", "G3B", "G4", "G5"):
        raise ValueError("Estágio renal inválido.")
    if estagio in ("G3A", "G3B"):
        estagio = estagio[:2] + estagio[2:].lower()
    albuminuria = (_numero(dados["albuminuria_mg_g"], "Albuminúria")
                   if dados.get("albuminuria_mg_g") not in (None, "") else None)
    categoria_albuminuria = classificar_albuminuria_mg_g(albuminuria) if albuminuria is not None else None
    dialise = str(dados.get("dialise") or "nao").strip().lower()
    frequencia_dialise = (_numero(dados["frequencia_dialise_semana"], "Frequência de diálise", minimo=0.000001)
                          if dados.get("frequencia_dialise_semana") not in (None, "") else None)
    duracao_dialise = (_numero(dados["duracao_dialise_horas"], "Duração da diálise", minimo=0.000001)
                       if dados.get("duracao_dialise_horas") not in (None, "") else None)
    inicio_dialise = str(dados.get("inicio_dialise") or "").strip() or None
    if dialise not in ("nao", "hemodialise", "peritoneal"):
        raise ValueError("Modalidade de diálise inválida.")
    estabilidade = str(dados.get("estabilidade_metabolica") or "nao_informada").strip().lower()
    if estabilidade not in ("estavel", "instavel", "nao_informada"):
        raise ValueError("Estabilidade metabólica inválida.")
    risco_desnutricao = dados.get("risco_desnutricao")
    catabolismo = dados.get("catabolismo")
    sarcopenia = dados.get("fragilidade_sarcopenia")
    peso = _numero(peso_kg, "Peso nutricional", minimo=0.000001) if peso_kg not in (None, "") else None
    idade = _numero(idade_anos, "Idade") if idade_anos not in (None, "") else None
    recomendacao = {"status": "individualizar", "g_kg_dia": None, "g_dia": None,
                    "texto": "Meta proteica deve ser definida individualmente; não há recomendação numérica automática para os dados informados."}
    avisos = []
    confirmada = dados.get("drc_confirmada") is True
    condicao_renal = str(dados.get("condicao_renal") or
                         ("DRC" if confirmada else "NAO_DEFINIDA")).strip().upper()
    if condicao_renal not in ("DRC", "LRA", "DRC + LRA", "NAO_DEFINIDA"):
        raise ValueError("Condição renal inválida.")
    if faixa_tfge in ("G1", "G2") and not confirmada:
        avisos.append("TFGe em G1/G2 isoladamente não confirma DRC; é necessário marcador de lesão renal e cronicidade.")
    if tfge is not None and tfge < 60:
        avisos.append("Confirme persistência por pelo menos 3 meses ou outro critério clínico para caracterização de DRC.")
    if estagio and faixa_tfge and estagio != faixa_tfge:
        avisos.append("Estágio informado difere da faixa calculada pela TFGe; conferir o laudo e o histórico.")
    if categoria_albuminuria:
        avisos.append(f"Albuminúria: categoria {categoria_albuminuria} (mg/g). Interpretar junto à TFGe e à cronicidade.")
    if condicao_renal in ("LRA", "DRC + LRA"):
        recomendacao["texto"] = "Lesão renal aguda ou condição aguda associada: não aplicar automaticamente recomendações proteicas de DRC; individualizar conforme fase, catabolismo e terapia renal."
    elif idade is not None and idade < 18:
        recomendacao["texto"] = "Em crianças/adolescentes, não aplicar restrição proteica renal automática; considerar crescimento e avaliação especializada."
    elif estabilidade != "estavel" or catabolismo is True:
        recomendacao["texto"] = "Instabilidade metabólica ou catabolismo: não aplicar metas restritivas automáticas; individualizar com a equipe."
    elif risco_desnutricao is True or sarcopenia is True:
        recomendacao["texto"] = "Risco nutricional, fragilidade ou sarcopenia: evitar restrição automática e individualizar a meta proteica."
    elif dialise in ("hemodialise", "peritoneal"):
        if not confirmada:
            recomendacao["texto"] = "Informe/valide DRC confirmada antes de aplicar referências proteicas de diálise da KDOQI."
        elif referencia == "KDOQI 2020":
            recomendacao.update(status="referencia", g_kg_dia="1,0–1,2",
                                texto="KDOQI 2020: 1,0–1,2 g/kg/dia em adultos metabolicamente estáveis em hemodiálise ou diálise peritoneal.")
        else:
            recomendacao["texto"] = "KDIGO 2024 não define aqui uma meta numérica específica para diálise; individualizar. KDOQI 2020 pode ser consultada como referência alternativa."
    elif estagio in ("G3a", "G3b", "G4", "G5") and confirmada:
        if referencia == "KDIGO 2024":
            recomendacao.update(status="referencia", g_kg_dia=0.8,
                                texto="KDIGO 2024: aproximadamente 0,8 g/kg/dia em adultos com DRC G3–G5; evitar ingestão elevada (>1,3 g/kg/dia) em risco de progressão.")
        elif diabetes:
            recomendacao.update(status="referencia", g_kg_dia="0,6–0,8",
                                texto="KDOQI 2020: 0,6–0,8 g/kg/dia em DRC G3–G5 com diabetes, sob supervisão próxima.")
        else:
            recomendacao.update(status="referencia", g_kg_dia="0,55–0,60",
                                texto="KDOQI 2020: 0,55–0,60 g/kg/dia em DRC G3–G5 sem diabetes, metabolicamente estável e sob supervisão próxima.")
    if isinstance(recomendacao.get("g_kg_dia"), (int, float)) and peso:
        recomendacao["g_dia"] = round(recomendacao["g_kg_dia"] * peso, 1)
    elif isinstance(recomendacao.get("g_kg_dia"), str) and peso:
        partes = recomendacao["g_kg_dia"].replace(",", ".").split("–")
        if len(partes) == 2:
            minimo, maximo = (float(x) for x in partes)
            recomendacao["g_dia"] = (
                f"{formatar_numero_pt(minimo * peso, 1)}–{formatar_numero_pt(maximo * peso, 1)}"
            )
    if dados.get("creatinina") not in (None, ""):
        avisos.append("Creatinina registrada como dado de apoio; não define isoladamente estágio ou meta proteica.")
    if dados.get("ureia") not in (None, "") or dados.get("albumina_serica") not in (None, ""):
        avisos.append("Ureia e albumina sérica são dados de apoio e não alteram automaticamente a meta proteica.")
    return {
        "referencia": referencia, "condicao_renal": condicao_renal,
        "tfge_ml_min_173": tfge, "faixa_tfge": faixa_tfge,
        "drc_confirmada": confirmada, "estagio": estagio,
        "albuminuria_mg_g": albuminuria, "categoria_albuminuria": categoria_albuminuria,
        "dialise": dialise, "frequencia_dialise_semana": frequencia_dialise,
        "duracao_dialise_horas": duracao_dialise, "inicio_dialise": inicio_dialise,
        "estabilidade_metabolica": estabilidade,
        "catabolismo": catabolismo, "risco_desnutricao": risco_desnutricao,
        "fragilidade_sarcopenia": sarcopenia, "recomendacao_proteica": recomendacao,
        "avisos": avisos,
        "exames_apoio": {k: dados.get(k) for k in ("creatinina", "ureia", "albumina_serica")},
    }


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
    # Calcula o prazo total para atingir o limite, mas expõe somente os passos
    # dentro da janela solicitada (3 ou 4 dias). O restante continua estimado em dias.
    dias_estimados = 0
    volume_estimado = atual
    while volume_estimado < limite and dias_estimados < 365:
        volume_estimado = min(limite, volume_estimado + incremento)
        dias_estimados += 1
    passos, volume = [], atual
    for dia in range(1, min(dias_estimados, int(dias_alvo)) + 1):
        proximo = min(limite, volume + incremento)
        passos.append({"dia": dia, "volume_total_ml": proximo,
                       "incremento_ml": proximo - volume})
        volume = proximo
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



def planejar_administracao_enteral(volume_total_ml, kcal_100ml, duracao_horas, *, usa_bomba=False, fator_gotas_ml=20):
    """Calcula taxa de administração e energia ofertada no período informado.

    O fator de gotas deve corresponder ao equipo utilizado. Bomba retorna mL/h;
    gravidade retorna gotas/min. Resultado matemático, não prescrição de velocidade.
    """
    volume = _numero(volume_total_ml, "Volume total", minimo=0.000001)
    kcal = _numero(kcal_100ml, "Energia por 100 mL", minimo=0.000001)
    horas = _numero(duracao_horas, "Duração da administração", minimo=0.000001)
    taxa_ml_h = volume / horas
    energia_total = volume * kcal / 100
    resultado = {"volume_total_ml": volume, "duracao_horas": horas,
                 "energia_total_kcal": energia_total, "energia_kcal_h": energia_total / horas,
                 "taxa_ml_h": taxa_ml_h, "usa_bomba": bool(usa_bomba)}
    if usa_bomba:
        resultado["velocidade_bomba_ml_h"] = round(taxa_ml_h, 1)
    else:
        fator = _numero(fator_gotas_ml, "Fator de gotas do equipo", minimo=0.000001)
        resultado["fator_gotas_ml"] = fator
        resultado["gotejamento_gotas_min"] = round(taxa_ml_h * fator / 60, 1)
    return resultado


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
        administracao = dados.get("administracao_enteral") or {}
        if administracao:
            if administracao.get("usa_bomba"):
                taxa_txt = f"velocidade da bomba: {formatar_numero_pt(administracao['velocidade_bomba_ml_h'], 1)} mL/h"
            else:
                taxa_txt = (f"gotejamento estimado: {formatar_numero_pt(administracao['gotejamento_gotas_min'], 1)} gotas/min "
                            f"(equipo de {formatar_numero_pt(administracao['fator_gotas_ml'], 1)} gotas/mL)")
            volume_atual = administracao.get("volume_etapas_atual_ml")
            diferenca_volume = (administracao["volume_total_ml"] - volume_atual
                                if volume_atual is not None else None)
            contexto_volume = ""
            if diferenca_volume is not None and abs(diferenca_volume) > 0.1:
                contexto_volume = (
                    f" Oferta atualmente cadastrada: {formatar_numero_pt(volume_atual)} mL/dia; "
                    f"diferença até o volume-meta: {formatar_numero_pt(diferenca_volume)} mL/dia."
                )
            linhas.append("**Administração da dieta fechada — planejamento do volume-meta:** " +
                f"{formatar_numero_pt(administracao['volume_total_ml'])} mL em {formatar_numero_pt(administracao['duracao_horas'], 1)} h; " +
                f"{taxa_txt}; {formatar_numero_pt(administracao['energia_total_kcal'])} kcal no período " +
                f"({formatar_numero_pt(administracao['energia_kcal_h'], 1)} kcal/h)." +
                contexto_volume +
                " Estimativa matemática para o volume-meta; não altera a prescrição atual. Validar volume, velocidade e tolerância clinicamente.")
        if bomba.get("usa_bomba") and not administracao and oferta and oferta.get("volume_total_ml") is not None and oferta.get("volume_meta_ml") is not None:
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
