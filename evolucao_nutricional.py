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



def validar_progressao_oral(valores):
    """Valida a sequência operacional oral configurável, sem decidir a porção clínica do paciente."""
    if not isinstance(valores, (list, tuple)) or len(valores) != 5:
        raise ValueError("Informe exatamente cinco porções para a progressão oral.")
    limpos = []
    for valor in valores:
        numero = _numero(valor, "Porção oral", minimo=1)
        if int(numero) != numero:
            raise ValueError("As porções orais devem ser números inteiros em mL.")
        limpos.append(int(numero))
    if any(a >= b for a, b in zip(limpos, limpos[1:])):
        raise ValueError("As porções devem estar em ordem crescente, sem valores repetidos.")
    return limpos


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



def tolerancia_enteral_permite_progressao(motivos, tolerancia_informada=True):
    """Vômitos ou diarreia impedem progressão automática, mesmo se o checkbox estiver marcado."""
    _, selecionados = classificar_tne(motivos)
    return bool(tolerancia_informada) and not bool({"vômitos", "diarreia"}.intersection(selecionados))


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


def calcular_peso_corrigido(peso_kg, liquidos_a_retirar_kg=0, percentual_amputacao=0):
    """Aplica somente correções explicitamente informadas e calculadas pelo protocolo do serviço."""
    peso = _numero(peso_kg, "Peso original", minimo=0.000001)
    liquidos = _numero(liquidos_a_retirar_kg, "Correção de líquidos")
    amputacao = _numero(percentual_amputacao, "Percentual de amputação")
    if amputacao >= 100:
        raise ValueError("Percentual de amputação deve ser inferior a 100%.")
    seco = peso - liquidos
    if seco <= 0:
        raise ValueError("Correção de líquidos iguala ou supera o peso original.")
    corrigido = seco / (1 - amputacao / 100)
    return {"peso_original_kg": peso, "correcao_liquidos_kg": liquidos,
            "percentual_amputacao": amputacao, "peso_nutricional_kg": corrigido,
            "corrigido": bool(liquidos or amputacao)}


def classificar_imc_referencia(imc, idade_anos, sexo=None, criterio_idoso="lipschitz", lms=None,
                               classificacao_oms=None):
    """Usa a referência já adotada pelo NutriLab; pediatria exige resultado OMS carregado."""
    from nutri_calculos import classificar_imc, texto_classificacao
    valor = _numero(imc, "IMC", minimo=0.000001)
    idade = _numero(idade_anos, "Idade")
    if idade < 20:
        if not classificacao_oms:
            raise ValueError("Classificação pediátrica exige resultado OMS oficial.")
        return str(classificacao_oms)
    resultado = classificar_imc(valor, int(idade), sexo, criterio_idoso=criterio_idoso, lms=lms)
    return texto_classificacao(resultado)


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


def planejar_progressao_por_etapa(volume_etapa_atual_ml, etapas, volume_etapa_meta_ml,
                                  incremento_por_etapa_ml=10, dias_alvo=4, *,
                                  habilitada=True, autorizada=False, tolerancia=True,
                                  restricao=False, volume_etapa_maximo_ml=None):
    """Planeja aumento por etapa; não executa nem prescreve sem autorização clínica explícita."""
    atual = _numero(volume_etapa_atual_ml, "Volume atual por etapa")
    n_etapas = _numero(etapas, "Número de etapas", minimo=1)
    meta = _numero(volume_etapa_meta_ml, "Volume-meta por etapa")
    incremento = _numero(incremento_por_etapa_ml, "Incremento por etapa", minimo=0.000001)
    if int(n_etapas) != n_etapas:
        raise ValueError("Número de etapas deve ser inteiro.")
    if isinstance(dias_alvo, bool) or int(dias_alvo) < 1:
        raise ValueError("Dias-alvo deve ser inteiro positivo.")
    limite = meta if volume_etapa_maximo_ml is None else min(meta, _numero(volume_etapa_maximo_ml, "Limite por etapa"))
    if atual > limite:
        raise ValueError("Oferta atual excede o limite/meta configurado.")
    pode = bool(habilitada and autorizada and tolerancia and not restricao)
    if not pode or atual >= limite:
        motivo = ("desativada" if not habilitada else "aguarda autorização" if not autorizada else
                  "intolerância" if not tolerancia else "restrição clínica" if restricao else "meta atingida")
        return {"ativa": False, "motivo": motivo, "volume_etapa_atual_ml": atual,
                "volume_total_atual_ml": atual * int(n_etapas), "volume_etapa_meta_ml": meta,
                "volume_total_meta_ml": meta * int(n_etapas), "passos": [], "dias_estimados": 0}
    passos, volume = [], atual
    while volume < limite and len(passos) < 365:
        proximo = min(limite, volume + incremento)
        passos.append({"dia": len(passos) + 1, "volume_etapa_ml": proximo,
                       "volume_total_ml": proximo * int(n_etapas),
                       "incremento_total_ml": (proximo - volume) * int(n_etapas)})
        volume = proximo
    return {"ativa": True, "motivo": None, "volume_etapa_atual_ml": atual,
            "volume_total_atual_ml": atual * int(n_etapas), "volume_etapa_meta_ml": meta,
            "volume_total_meta_ml": meta * int(n_etapas), "passos": passos,
            "dias_estimados": len(passos), "atinge_meta_no_prazo": len(passos) <= int(dias_alvo)}


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



def resumo_painel_evolucao(registro, data_destino):
    """Resume a evolução enteral para avisos operacionais do mapa, sem alterar prescrição."""
    if not registro:
        return None
    dados = registro.get("evolucao") or {}
    if str(registro.get("via") or dados.get("via") or "").casefold() != "enteral":
        return None
    metas = dados.get("metas") or {}
    dieta = dados.get("dieta_enteral") or {}
    progressao = dados.get("progressao_enteral") or {}
    oferta = dados.get("oferta") or {}
    try:
        meta_kcal = _numero(metas.get("kcal_dia"), "Meta energética", minimo=0.000001)
        kcal_100 = _numero(dieta.get("kcal_100"), "Energia da fórmula", minimo=0.000001)
        etapas = int(_numero(dieta.get("etapas"), "Etapas", minimo=1))
        inicial_etapa = _numero(dieta.get("volume_por_etapa_ml"), "Volume por etapa", minimo=0.000001)
    except (TypeError, ValueError):
        return None
    try:
        inicio = _data_br_ou_iso(dados.get("data_evolucao") or registro.get("data"))
        destino = _data_br_ou_iso(data_destino or registro.get("data"))
        dias = max(0, (date.fromisoformat(destino) - date.fromisoformat(inicio)).days)
        atual_etapa = inicial_etapa
        autorizada = bool(progressao.get("autorizada"))
        passos = (progressao.get("plano") or {}).get("passos") or []
        if autorizada and passos and dias:
            atual_etapa = _numero(passos[min(dias - 1, len(passos) - 1)]["volume_etapa_ml"],
                                  "Volume da progressão", minimo=0.000001)
    except (TypeError, ValueError, KeyError, IndexError):
        return None
    volume_atual = atual_etapa * etapas
    energia_atual = volume_atual * kcal_100 / 100
    ptn_100 = dieta.get("ptn_100")
    try:
        proteina_atual = volume_atual * _numero(ptn_100, "Proteína por 100 mL", minimo=0.000001) / 100
    except ValueError:
        proteina_atual = None
    meta_ptn = metas.get("proteina_g_dia")
    adequacao_kcal = energia_atual / meta_kcal * 100
    try:
        adequacao_ptn = (proteina_atual / _numero(meta_ptn, "Meta proteica", minimo=0.000001) * 100
                         if proteina_atual is not None else None)
    except ValueError:
        adequacao_ptn = None
    evoluiu = atual_etapa > inicial_etapa
    motivo = None
    if not progressao.get("solicitada"):
        motivo = "Progressão automática desativada"
    elif not autorizada:
        motivo = "Aguardando autorização do nutricionista"
    elif progressao.get("restricao"):
        motivo = "Restrição clínica"
    elif not progressao.get("tolerancia", True):
        motivo = "Intolerância enteral"
    elif volume_atual >= (float(oferta.get("volume_meta_ml") or progressao.get("volume_meta_ml"))
                           if (oferta.get("volume_meta_ml") or progressao.get("volume_meta_ml")) else float("inf")):
        motivo = "Meta energética atingida"
    elif not evoluiu:
        motivo = "Progressão ainda não iniciada"
    deficit = max(0.0, meta_kcal - energia_atual)
    volume_adicional = deficit / (kcal_100 / 100)
    try:
        volume_meta_total = _numero(oferta.get("volume_meta_ml") or progressao.get("volume_meta_ml") or 0,
                                    "Volume-meta")
    except ValueError:
        volume_meta_total = 0.0
    return {
        "via": "Enteral", "volume_inicial_ml": inicial_etapa * etapas,
        "volume_atual_ml": volume_atual, "volume_meta_ml": volume_meta_total,
        "incremento_ml": volume_atual - inicial_etapa * etapas, "energia_kcal": energia_atual,
        "meta_kcal": meta_kcal, "adequacao_kcal_pct": adequacao_kcal,
        "proteina_g": proteina_atual, "adequacao_ptn_pct": adequacao_ptn,
        "deficit_kcal": deficit, "volume_adicional_ml": volume_adicional,
        "evoluiu": evoluiu, "motivo_nao_evolucao": motivo,
        "data_inicio": inicio, "data_destino": destino,
    }


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
                partes.append(f"{rotulo}: {_numero(dados[chave], rotulo):g} cm")
    if dados.get("altura_m") is not None:
        altura = _numero(dados["altura_m"], "Altura", minimo=0.000001)
    elif dados.get("altura_cm") is not None:
        altura = _numero(dados["altura_cm"], "Altura", minimo=0.000001) / 100
    else:
        raise ValueError("Altura ausente.")
    partes.append(f"ALT: {altura:.2f} m ({origem_altura})".replace(".", ","))
    peso = _numero(dados.get("peso_kg"), "Peso", minimo=0.000001)
    peso_txt = f"PESO: {peso:g} kg ({origem_peso}"
    if dados.get("peso_corrigido"):
        peso_txt += "; corrigido"
    partes.append(peso_txt + ")")
    imc = calcular_imc(peso, altura)
    classificacao = str(dados.get("imc_class") or "classificação pendente")
    imc_txt = f"{imc:.1f}".replace(".", ",")
    return f"**Antropometria {data}:** " + "; ".join(partes) + f". IMC: {imc_txt} kg/m² ({classificacao})."


def gerar_evolucao(dados):
    """Gera a evolução clínica a partir dos dados estruturados."""
    linhas = [formatar_antropometria(dados["antropometria"])]
    metas = dados.get("metas")
    if metas:
        linhas.append("**Metas nutricionais:** " +
            f"Kcal/dia: {metas['kcal_dia']:.0f} kcal ({str(metas['kcal_kg']).replace('.', ',')} kcal/kg); " +
            f"PTN/dia: {str(round(metas['proteina_g_dia'], 1)).replace('.', ',')} g ({str(metas['proteina_g_kg']).replace('.', ',')} g/kg).")
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
        tne, selecionados = classificar_tne(dados.get("tne_motivos") or [])
        linhas.append(f"**TNE:** {tne}" + (f" ({' e '.join(selecionados)})." if selecionados else "."))
        dieta = dados.get("dieta_enteral") or {}
        if dieta.get("nome") and dieta.get("volume_por_etapa_ml") is not None and dieta.get("etapas") is not None:
            volume_etapa = _numero(dieta["volume_por_etapa_ml"], "Volume por etapa")
            etapas = int(_numero(dieta["etapas"], "Etapas", minimo=1))
            volume_total = volume_etapa * etapas
            linhas.append("**Dieta enteral ofertada:** " +
                f"{dieta['nome']} — {volume_etapa:g} mL/etapa × {etapas} etapas, " +
                f"totalizando {volume_total:.0f} mL/dia.")
        progressao = dados.get("progressao_enteral")
        if progressao and progressao.get("autorizada") and progressao.get("volume_atual_ml") is not None and progressao.get("volume_meta_ml") is not None:
            atual = _numero(progressao["volume_atual_ml"], "Volume atual")
            meta = _numero(progressao["volume_meta_ml"], "Volume-meta")
            if progressao.get("incremento_por_etapa_ml") is not None and progressao.get("etapas"):
                incremento_etapa = _numero(progressao["incremento_por_etapa_ml"], "Incremento por etapa", minimo=0.000001)
                etapas = int(_numero(progressao["etapas"], "Etapas", minimo=1))
                incremento_total = incremento_etapa * etapas
                plano = progressao.get("plano") or {}
                prazo = plano.get("dias_estimados")
                detalhe_prazo = f" Previsão matemática: {prazo} dia(s)." if prazo is not None else ""
                linhas.append("**Evolução da dieta:** " +
                    f"Oferta atual de {atual:.0f} mL/dia, com aumento de {incremento_etapa:.0f} mL por etapa " +
                    f"({incremento_total:.0f} mL/dia no total), condicionado à tolerância e reavaliação.{detalhe_prazo}")
            else:
                incremento = _numero(progressao.get("incremento_diario_ml", 35), "Incremento diário", minimo=0.000001)
                linhas.append("**Evolução da dieta:** " +
                    f"Oferta atual de {atual:.0f} mL/dia, com progressão programada de {incremento:.0f} mL/dia " +
                    f"até atingir o volume correspondente à meta energética.")
        bomba = dados.get("bomba")
        if bomba and bomba.get("usa_bomba") and oferta and oferta.get("volume_total_ml") is not None and oferta.get("volume_meta_ml") is not None:
            aviso = aviso_bomba(oferta["volume_total_ml"], oferta["volume_meta_ml"], True,
                                bomba.get("taxa_estimativa_ml_h", 10))
            if aviso:
                linhas.append("**Estimativa de bomba:** " + aviso["texto"])
        elif dados.get("orientacao_progressao"):
            linhas.append("**Orientação operacional:** Progressão de aproximadamente 30–40 mL/dia, conforme tolerância e conduta nutricional.")
    elif via == "oral" and dados.get("tno"):
        tno = dados["tno"]
        if tno not in TNO_PERCENTUAIS:
            raise ValueError("Classificação TNO inválida.")
        linhas.append(f"**TNO:** {tno} ({TNO_PERCENTUAIS[tno]}% de consumo estimado).")
        porcao = dados.get("porcao_oral_ml")
        if dados.get("porcao_oral_autorizada") and porcao not in (None, ""):
            linhas.append(f"**Porção oral autorizada pelo nutricionista:** {_numero(porcao, 'Porção oral')} mL.")
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
        nomes = dados["estagiarios"] if isinstance(dados["estagiarios"], (list, tuple)) else [dados["estagiarios"]]
        linhas.append("**Estagiário:** " + ", ".join(str(x) for x in nomes) + ".")
    if dados.get("nutricionistas"):
        nomes = dados["nutricionistas"] if isinstance(dados["nutricionistas"], (list, tuple)) else [dados["nutricionistas"]]
        linhas.append("**Nutricionista responsável:** " + "; ".join(str(x) for x in nomes) + ".")
    return "\n\n".join(linhas)

