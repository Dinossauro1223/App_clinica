# -*- coding: utf-8 -*-
"""Análise longitudinal antropométrica observacional, sem diagnóstico automático.

Os limiares de perda ponderal são apresentados como faixas de alerta/documentação
(ASPEN/GLIM). Variação abrupta em até 24 h é sinal de revisão do balanço hídrico,
não critério isolado de desnutrição.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta


JANELAS_ASPEN = (
    # dias, tolerância de busca, faixa moderada (%), faixa elevada (> %), rótulo
    (7, 2, 1.0, 2.0, "1 semana"),
    (30, 7, 5.0, 5.0, "1 mês"),
    (90, 14, 7.5, 7.5, "3 meses"),
    (180, 30, 10.0, 10.0, "6 meses"),
    (365, 45, 20.0, 20.0, "1 ano"),
)


def _data(valor):
    if isinstance(valor, datetime):
        return valor
    texto = str(valor or "").strip()
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                    "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            pass
    raise ValueError("Data antropométrica inválida.")


def listar_pesos_historicos(db_path, id_paciente):
    """Lê pesos diários do mapa sem alterar dados; uma avaliação por data."""
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT id_registro, data, peso_kg, peso_origem, peso_metodo, peso_medido_em,
                      altura_cm, altura_origem, pp_cm, pb_cm, aj_cm, imc, avaliacao_json, atualizado_em
               FROM Mapa_Registros
               WHERE id_paciente=? AND peso_kg IS NOT NULL AND peso_kg>0
               ORDER BY data, atualizado_em, id_registro""",
            (int(id_paciente),),
        ).fetchall()
    por_data = {}
    for row in rows:
        item = dict(row)
        try:
            avaliacao = json.loads(item.get("avaliacao_json") or "{}")
        except (TypeError, ValueError):
            avaliacao = {}
        resultado = avaliacao.get("resultado") or avaliacao
        ajustado = resultado.get("ajustado", avaliacao.get("peso_ajustado"))
        if ajustado not in (None, "") and resultado.get("ajustou", True):
            try:
                item["peso_original_kg"] = item["peso_kg"]
                item["peso_kg"] = float(str(ajustado).replace(",", "."))
                item["peso_corrigido"] = True
            except (TypeError, ValueError):
                item["peso_corrigido"] = False
        else:
            item["peso_corrigido"] = False
        # Se houver mais de um registro do mesmo paciente no mesmo dia,
        # prevalece o último registro atualizado, sem somar ou fazer média.
        por_data[item["data"]] = item
    return [por_data[k] for k in sorted(por_data)]


def analisar_progressao_peso(registros, idade_anos=None, *, agora=None):
    """Compara a avaliação mais recente com janelas temporais próximas e documentadas."""
    itens = []
    for bruto in registros or []:
        try:
            peso = float(str(bruto.get("peso_kg")).replace(",", "."))
            valor_data = bruto.get("peso_medido_em") or bruto.get("medido_em") or bruto.get("data")
            quando = _data(valor_data)
            texto_data = str(valor_data or "")
            tem_hora = isinstance(valor_data, datetime) or (len(texto_data) > 10 and ":" in texto_data)
            if peso > 0:
                itens.append({**bruto, "_data": quando, "_peso": peso, "_tem_hora": tem_hora})
        except (TypeError, ValueError):
            continue
    itens.sort(key=lambda x: x["_data"])
    if not itens:
        return {"status": "sem_dados", "comparacoes": [], "alertas": [],
                "texto": "Sem avaliações de peso suficientes para analisar a progressão."}

    atual = itens[-1]
    try:
        adulto = idade_anos is not None and float(idade_anos) >= 18
    except (TypeError, ValueError):
        adulto = False
    alertas, comparacoes = [], []
    for anterior in reversed(itens[:-1]):
        intervalo_h = (atual["_data"] - anterior["_data"]).total_seconds() / 3600
        if 0 < intervalo_h <= 24 and atual.get("_tem_hora") and anterior.get("_tem_hora"):
            diferenca = atual["_peso"] - anterior["_peso"]
            perda_pct = (anterior["_peso"] - atual["_peso"]) / anterior["_peso"] * 100
            comparacoes.append({
                "janela": "até 24 horas", "dias_reais": round(intervalo_h / 24, 2),
                "peso_anterior_kg": anterior["_peso"], "peso_atual_kg": atual["_peso"],
                "diferenca_kg": round(diferenca, 2), "perda_percentual": round(perda_pct, 2),
                "faixa": "variação aguda — revisar balanço hídrico, não é faixa diagnóstica de desnutrição",
                "data_anterior": anterior["_data"].strftime("%d/%m/%Y"),
                "data_atual": atual["_data"].strftime("%d/%m/%Y"),
            })
            if adulto and anterior.get("peso_origem") == "R" and atual.get("peso_origem") == "R" and abs(diferenca) >= 1.0:
                alertas.append({
                    "tipo": "variacao_aguda_24h", "diferenca_kg": round(diferenca, 2),
                    "intervalo_horas": round(intervalo_h, 1),
                    "texto": ("Aumento" if diferenca > 0 else "Redução") +
                             f" de {abs(diferenca):.1f} kg em {intervalo_h:.1f} h. Revisar balanço hídrico, edema, diurese, "
                             "condições de pesagem e possível erro de medida. Não classificar como desnutrição isoladamente."
                })
            break
        if (0 < intervalo_h <= 48 and atual["_data"].date() != anterior["_data"].date()
                and (not atual.get("_tem_hora") or not anterior.get("_tem_hora"))):
            # O mapa registra a data, mas o horário real pode estar ausente.
            # Mostra a diferença entre datas consecutivas sem presumir 24 h exatas.
            diferenca = atual["_peso"] - anterior["_peso"]
            perda_pct = (anterior["_peso"] - atual["_peso"]) / anterior["_peso"] * 100
            comparacoes.append({
                "janela": "datas consecutivas (horário não registrado)",
                "dias_reais": round(intervalo_h / 24, 2),
                "peso_anterior_kg": anterior["_peso"], "peso_atual_kg": atual["_peso"],
                "diferenca_kg": round(diferenca, 2), "perda_percentual": round(perda_pct, 2),
                "faixa": "variação aguda — confirmar intervalo e revisar balanço hídrico",
                "data_anterior": anterior["_data"].strftime("%d/%m/%Y"),
                "data_atual": atual["_data"].strftime("%d/%m/%Y"),
            })
            if adulto and abs(diferenca) >= 1.0:
                alertas.append({
                    "tipo": "variacao_em_dias_consecutivos", "diferenca_kg": round(diferenca, 2),
                    "intervalo_horas": None,
                    "texto": ("Aumento" if diferenca > 0 else "Redução") +
                             f" de {abs(diferenca):.1f} kg entre datas consecutivas do mapa. "
                             "O horário da aferição não está registrado; confirmar se o intervalo foi de até 24 h "
                             "e revisar balanço hídrico/condições de pesagem. Não diagnostica desnutrição."
                })
            break

    outras_medidas = []
    if len(itens) > 1:
        anterior_recente = itens[-2]
        for campo, rotulo, unidade in (
            ("altura_cm", "Estatura", "cm"), ("aj_cm", "Altura do joelho", "cm"),
            ("pp_cm", "Perímetro da panturrilha", "cm"), ("pb_cm", "Perímetro do braço", "cm"),
        ):
            try:
                valor_ant = float(str(anterior_recente.get(campo)).replace(",", "."))
                valor_atual = float(str(atual.get(campo)).replace(",", "."))
            except (TypeError, ValueError):
                continue
            if abs(valor_atual - valor_ant) >= 0.01:
                outras_medidas.append({
                    "medida": rotulo, "unidade": unidade,
                    "anterior": valor_ant, "atual": valor_atual,
                    "diferenca": round(valor_atual - valor_ant, 2),
                    "data_anterior": anterior_recente["_data"].strftime("%d/%m/%Y"),
                    "data_atual": atual["_data"].strftime("%d/%m/%Y"),
                })

    data_atual = atual["_data"]
    for dias, tolerancia, limiar_moderado, limiar_elevado, rotulo in (JANELAS_ASPEN if adulto else ()):
        alvo = data_atual - timedelta(days=dias)
        candidatos = [x for x in itens[:-1] if x["_data"] < data_atual]
        if not candidatos:
            continue
        anterior = min(candidatos, key=lambda x: abs((x["_data"] - alvo).total_seconds()))
        distancia = abs((anterior["_data"] - alvo).total_seconds()) / 86400
        if distancia > tolerancia:
            continue
        intervalo = (data_atual - anterior["_data"]).total_seconds() / 86400
        if intervalo <= 0:
            continue
        perda = (anterior["_peso"] - atual["_peso"]) / anterior["_peso"] * 100
        pesos_aferidos = anterior.get("peso_origem") == "R" and atual.get("peso_origem") == "R"
        faixa = "variação observada; peso estimado/origem não confirmada"
        if pesos_aferidos:
            faixa = "sem limiar ASPEN atingido"
            if perda >= limiar_moderado:
                faixa = "faixa moderada de perda ponderal (ASPEN)"
            if perda > limiar_elevado:
                faixa = "faixa elevada de perda ponderal (ASPEN)"
        comparacoes.append({
            "janela": rotulo, "dias_reais": round(intervalo, 1),
            "peso_anterior_kg": anterior["_peso"], "peso_atual_kg": atual["_peso"],
            "diferenca_kg": round(atual["_peso"] - anterior["_peso"], 2),
            "perda_percentual": round(perda, 2), "limiar_percentual": limiar_moderado,
            "faixa": faixa, "data_anterior": anterior["_data"].strftime("%d/%m/%Y"),
            "data_atual": data_atual.strftime("%d/%m/%Y"),
            "origem_anterior": anterior.get("peso_origem"),
            "origem_atual": atual.get("peso_origem"),
            "origens_diferentes": anterior.get("peso_origem") != atual.get("peso_origem"),
        })

    bmi = None
    try:
        altura = float(str(atual.get("altura_cm")).replace(",", ".")) / 100
        bmi = atual["_peso"] / (altura * altura) if altura > 0 else None
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    criterio_bmi = None
    imc_com_pesagem_aferida = atual.get("peso_origem") == "R" and atual.get("altura_origem") == "R"
    if bmi is not None and adulto and imc_com_pesagem_aferida:
        limite = 22 if float(idade_anos) >= 70 else 20
        if bmi < limite:
            criterio_bmi = {"imc": round(bmi, 2), "limite": limite,
                            "texto": f"IMC abaixo do ponto de corte GLIM para idade (IMC {bmi:.1f}; corte <{limite})."}

    glim_peso = adulto and any(
        c.get("origem_anterior") == "R" and c.get("origem_atual") == "R" and (
            (c["janela"] == "6 meses" and c["perda_percentual"] > 5) or
            (c["dias_reais"] > 180 and c["perda_percentual"] > 10)
        )
        for c in comparacoes
    )
    fenotipicos = []
    if glim_peso:
        fenotipicos.append("perda ponderal compatível com limiar fenotípico GLIM")
    if criterio_bmi:
        fenotipicos.append("IMC reduzido segundo GLIM")
    etiologicos = []
    if fenotipicos:
        alertas.append({
            "tipo": "criterio_fenotipico_glim",
            "texto": "Há pelo menos um achado fenotípico que merece avaliação nutricional. "
                     "O diagnóstico GLIM exige também pelo menos um critério etiológico "
                     "(redução da ingestão/assimilação ou doença/carga inflamatória)."
        })

    return {
        "status": "calculado", "data_atual": data_atual.strftime("%d/%m/%Y"),
        "peso_atual_kg": atual["_peso"], "comparacoes": comparacoes,
        "outras_medidas": outras_medidas,
        "alertas": alertas, "imc": round(bmi, 2) if bmi is not None else None,
        "criterio_bmi_glim": criterio_bmi, "criterios_fenotipicos": fenotipicos,
        "criterios_etiologicos": etiologicos,
        "diagnostico_automatico": False,
        "nota": (
            "As faixas ASPEN e os critérios GLIM apresentados são para adultos; não foram aplicados a menores de 18 anos. "
            if not adulto else ""
        ) + (
            "Os critérios de perda ponderal foram aplicados somente quando as duas pesagens são aferidas; "
            if adulto else ""
        ) + (
            "O IMC GLIM foi avaliado somente com peso e estatura aferidos. "
            if adulto and not imc_com_pesagem_aferida else ""
        ) + "As faixas ASPEN apoiam a documentação clínica e não fecham diagnóstico isoladamente. "
            "GLIM requer ≥1 critério fenotípico e ≥1 etiológico. Mudanças agudas de peso podem refletir líquidos.",
    }


def formatar_progressao(resultado):
    if not resultado or resultado.get("status") == "sem_dados":
        return "Progressão antropométrica: sem histórico de peso suficiente."
    linhas = ["Progressão antropométrica do peso:"]
    for item in resultado.get("comparacoes", []):
        linhas.append(
            f"• {item['janela']}: {item['peso_anterior_kg']:.1f} → {item['peso_atual_kg']:.1f} kg; "
            f"{item['diferenca_kg']:+.1f} kg ({item['perda_percentual']:+.1f}% de perda; {item['faixa']})."
        )
        if item.get("origens_diferentes"):
            linhas.append("  Atenção: origem do peso anterior e atual é diferente (aferido/estimado).")
    for medida in resultado.get("outras_medidas", []):
        linhas.append(
            f"• {medida['medida']}: {medida['anterior']:.1f} → {medida['atual']:.1f} {medida['unidade']} "
            f"({medida['diferenca']:+.1f} {medida['unidade']}; {medida['data_anterior']} a {medida['data_atual']})."
        )
    if resultado.get("outras_medidas"):
        linhas.append("As variações de perímetros/estatura são exibidas para acompanhamento; não recebem classificação diagnóstica automática.")
    if resultado.get("criterio_bmi_glim"):
        linhas.append(resultado["criterio_bmi_glim"]["texto"])
    linhas.extend(a["texto"] for a in resultado.get("alertas", []))
    linhas.append(resultado.get("nota", ""))
    return "\n".join(linhas)
