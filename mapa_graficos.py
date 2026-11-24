# -*- coding: utf-8 -*-
"""Agregação mensal e gráficos do Mapa Nutricional.

Fluxo: os registros do mês viram um resumo (`agregar_mes`); o resumo vira a ESPECIFICAÇÃO de cada gráfico
(`especificar_todos`: um dict simples com tipo, título, números e cores, sem nenhuma biblioteca de desenho); e a
especificação é desenhada por quem precisar:

* a tela desenha direto no Canvas, com animação (graficos_nativos.py e graficos_ui.py), sem matplotlib;
* "Salvar imagens" e a imagem de reserva usam matplotlib (backend Agg, sem janela) e devolvem bytes PNG
  (`renderizar_png`). O matplotlib só é carregado nessa hora, o que deixa a tela de gráficos bem mais rápida.

Como tela e imagem saem da MESMA especificação, os números nunca divergem. Cada registro do mapa (um leito num dia)
conta como um atendimento.
"""
import calendar
import io
import os
from collections import Counter

import mapa_db as mdb

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]
VERDE_ESC, VERDE, VERDE_CLARO = "#1b5e20", "#4caf50", "#a5d6a7"
LARANJA, AZUL, CINZA = "#ef6c00", "#1565c0", "#78909c"

# Campos do mapa que são doenças crônicas. Os outros campos de mdb.CARACTERISTICAS (laxativa, constipante) descrevem a dieta.
CAMPOS_CRONICOS = ("dm", "has", "drc")

# Grupos da tela de gráficos, na ordem em que aparecem. Cada gráfico novo precisa entrar em um grupo; o que ficar de
# fora aparece no grupo "Outros gráficos" (nunca some).
GRUPOS = (
    {"id": "atendimentos", "titulo": "Atendimentos", "cor": VERDE,
     "descricao": "Quantos pacientes foram atendidos por dia e como é o perfil deles",
     "graficos": ("atendimentos_dia", "perfil_dia", "classificacao_terapia", "resumo")},
    {"id": "dieta", "titulo": "Dieta", "cor": LARANJA,
     "descricao": "Consistência da dieta e características como laxativa e constipante",
     "graficos": ("consistencia", "caracteristicas")},
    {"id": "suplementos", "titulo": "Suplementos", "cor": VERDE_ESC,
     "descricao": "Produtos registrados em suplementação oral e em dieta enteral, sem misturar a classificação dos pacientes",
     "graficos": ("suplementos", "modulos")},
    {"id": "cronicas", "titulo": "Doenças crônicas", "cor": AZUL,
     "descricao": "Diabetes, hipertensão e doença renal entre os pacientes atendidos",
     "graficos": ("cronicas",)},
)
GRUPO_OUTROS = {"id": "outros", "titulo": "Outros gráficos", "cor": CINZA, "descricao": "", "graficos": ()}


def agregar_mes(registros, ano, mes):
    """Resume os registros de um mês (lista de dicts de mapa_db.registros_do_mes)."""
    n = calendar.monthrange(ano, mes)[1]
    dias = {d: {"total": 0, "pastosa": 0, "acomp": 0, "oral_sem_suplemento": 0,
                 "oral_com_suplemento": 0, "enteral": 0} for d in range(1, n + 1)}
    consist, via, acomp, supl_sn = Counter(), Counter(), Counter(), Counter()
    classificacao_terapia = Counter()
    sup_nome, sup_mod, carac = Counter(), Counter(), Counter()
    cronicas, dieta_carac = Counter(), Counter()
    pacientes = set()
    for r in registros:
        d = int(r["data"][8:10])
        dias[d]["total"] += 1
        if r.get("consistencia") == "Pastosa":
            dias[d]["pastosa"] += 1
        if r.get("acompanhante"):
            dias[d]["acomp"] += 1
        sups = r.get("suplementos") or []
        via_registro = r.get("via") or "Não informada"
        if via_registro == "Enteral":
            classificacao_terapia["Dieta enteral"] += 1
            dias[d]["enteral"] += 1
        elif via_registro == "Oral" and sups:
            classificacao_terapia["Via oral com suplementação"] += 1
            dias[d]["oral_com_suplemento"] += 1
        elif via_registro == "Oral":
            classificacao_terapia["Via oral sem suplementação"] += 1
            dias[d]["oral_sem_suplemento"] += 1
        elif via_registro == "Zero":
            classificacao_terapia["Via zero"] += 1
        else:
            classificacao_terapia["Via não informada"] += 1
        pacientes.add(r.get("id_paciente") or "n:" + (r.get("nome_paciente") or "").strip().lower())
        consist[r.get("consistencia") or "Não informada"] += 1
        via[via_registro] += 1
        acomp["Sim" if r.get("acompanhante") else "Não"] += 1
        supl_sn["Sim" if sups else "Não"] += 1
        vistos_n, vistos_m = set(), set()
        for s in sups:
            if s["nome"] not in vistos_n:
                sup_nome[s["nome"]] += 1
                vistos_n.add(s["nome"])
            m = s.get("modulo") or "Sem módulo"
            if m not in vistos_m:
                sup_mod[m] += 1
                vistos_m.add(m)
        for campo, _, nome in mdb.CARACTERISTICAS:
            if r.get(campo):
                carac[nome] += 1
                (cronicas if campo in CAMPOS_CRONICOS else dieta_carac)[nome] += 1
    total = sum(v["total"] for v in dias.values())
    dias_com = sum(1 for v in dias.values() if v["total"])

    def pct(x):
        return 100.0 * x / total if total else 0.0

    kpis = {
        "atendimentos": total,
        "pacientes_unicos": len(pacientes),
        "dias_com_registro": dias_com,
        "media_por_dia": (total / dias_com) if dias_com else 0.0,
        "pastosa": sum(v["pastosa"] for v in dias.values()),
        "acompanhante": acomp["Sim"],
        "com_suplemento": classificacao_terapia["Via oral com suplementação"],
        "oral_sem_suplemento": classificacao_terapia["Via oral sem suplementação"],
        "oral_com_suplemento": classificacao_terapia["Via oral com suplementação"],
        "enteral": classificacao_terapia["Dieta enteral"],
    }
    for k in ("pastosa", "acompanhante", "com_suplemento", "oral_sem_suplemento", "oral_com_suplemento", "enteral"):
        kpis[k + "_pct"] = pct(kpis[k])
    return {"ano": ano, "mes": mes, "dias": dias, "consist": consist, "via": via, "acomp": acomp,
            "supl_sn": supl_sn, "classificacao_terapia": classificacao_terapia,
            "sup_nome": sup_nome, "sup_mod": sup_mod, "carac": carac,
            "cronicas": cronicas, "dieta_carac": dieta_carac, "kpis": kpis}


# ------------------------------------------------------------------------ especificações (sem biblioteca de desenho)
# Cada função devolve um dict. Campos comuns: tipo, titulo, periodo ("outubro de 2026"). Tipos:
#   "vazio"     mensagem                      (nada para mostrar no período)
#   "barras_v"  x, y, dicas, cor, rotulo_x, rotulo_y
#   "linhas"    x, series[{nome, cor, tracejado, valores}], rotulo_x, rotulo_y
#   "roscas"    blocos[{nome, itens[{rotulo, valor, cor}]}]
#   "barras_h"  itens[{nome, valor}] (de cima para baixo), total, cor, rotulo_x


def _periodo(agg):
    return f"{MESES[agg['mes'] - 1]} de {agg['ano']}"


def _vazio(agg, titulo):
    return {"tipo": "vazio", "titulo": titulo, "periodo": _periodo(agg),
            "mensagem": "Sem registros para exibir neste período."}


def spec_atendimentos_dia(agg):
    titulo = "Pacientes atendidos por dia"
    if not agg["kpis"]["atendimentos"]:
        return _vazio(agg, titulo)
    dias = sorted(agg["dias"])
    vals = [agg["dias"][d]["total"] for d in dias]
    return {"tipo": "barras_v", "titulo": titulo, "periodo": _periodo(agg), "x": dias, "y": vals,
            "dicas": [f"Dia {d}: {v} {'paciente' if v == 1 else 'pacientes'}" for d, v in zip(dias, vals)],
            "cor": VERDE, "rotulo_x": "Dia do mês", "rotulo_y": "Pacientes"}


def spec_perfil_dia(agg):
    titulo = "Perfil dos atendidos por dia"
    if not agg["kpis"]["atendimentos"]:
        return _vazio(agg, titulo)
    dias = sorted(agg["dias"])
    definicao = [("total", "Total atendidos", CINZA, True), ("pastosa", "Dieta pastosa", LARANJA, False),
                 ("acomp", "Com acompanhante", AZUL, False),
                 ("oral_sem_suplemento", "Via oral sem suplemento", VERDE_CLARO, False),
                 ("oral_com_suplemento", "Via oral com suplemento", VERDE_ESC, False),
                 ("enteral", "Dieta enteral", AZUL, False)]
    series = [{"nome": nome, "cor": cor, "tracejado": trac, "valores": [agg["dias"][d][chave] for d in dias]}
              for chave, nome, cor, trac in definicao]
    return {"tipo": "linhas", "titulo": titulo, "periodo": _periodo(agg), "x": dias, "series": series,
            "rotulo_x": "Dia do mês", "rotulo_y": "Pacientes"}


def spec_classificacao_terapia(agg):
    """Separa pacientes-dia em via oral sem suplemento, via oral com suplemento e dieta enteral."""
    titulo = "Classificação dos pacientes por terapia nutricional"
    ordem = ["Via oral sem suplementação", "Via oral com suplementação", "Dieta enteral",
             "Via zero", "Via não informada"]
    cores = {"Via oral sem suplementação": VERDE_CLARO, "Via oral com suplementação": VERDE_ESC,
             "Dieta enteral": AZUL, "Via zero": CINZA, "Via não informada": LARANJA}
    itens = [{"nome": nome, "valor": agg["classificacao_terapia"].get(nome, 0),
              "cor": cores[nome]} for nome in ordem if agg["classificacao_terapia"].get(nome, 0)]
    if not itens:
        return _vazio(agg, titulo)
    return {"tipo": "barras_h", "titulo": titulo, "periodo": _periodo(agg), "itens": itens,
            "total": agg["kpis"]["atendimentos"] or 1, "cor": VERDE, 
            "rotulo_x": "Pacientes-dia por classificação"}


def _spec_barras_h(agg, titulo, contagem, ordem=None, cor=VERDE, maximo=12, rotulo_x="Atendimentos (paciente-dia)"):
    if not contagem:
        return _vazio(agg, titulo)
    itens = [(k, contagem[k]) for k in ordem if k in contagem] if ordem else contagem.most_common(maximo)
    itens = itens[:maximo]
    return {"tipo": "barras_h", "titulo": titulo, "periodo": _periodo(agg),
            "itens": [{"nome": nome, "valor": valor} for nome, valor in itens],
            "total": agg["kpis"]["atendimentos"] or 1, "cor": cor, "rotulo_x": rotulo_x}


def spec_consistencia(agg):
    return _spec_barras_h(agg, "Consistência da dieta", agg["consist"], ordem=mdb.CONSISTENCIAS + ["Não informada"],
                          cor=LARANJA)


def spec_suplementos(agg):
    return _spec_barras_h(agg, "Suplementos mais utilizados", agg["sup_nome"], cor=VERDE_ESC)


def spec_modulos(agg):
    return _spec_barras_h(agg, "Uso por módulo (oral e enteral)", agg["sup_mod"], cor=VERDE)


def _ordem_das_caracteristicas(cronicas):
    """Nomes de mdb.CARACTERISTICAS que são (ou não são) doenças crônicas, na ordem do mapa."""
    return [nome for campo, _, nome in mdb.CARACTERISTICAS if (campo in CAMPOS_CRONICOS) == cronicas]


def spec_caracteristicas(agg):
    """Características da dieta que não são doenças (laxativa, constipante)."""
    return _spec_barras_h(agg, "Características da dieta", agg["dieta_carac"],
                          ordem=_ordem_das_caracteristicas(False), cor=LARANJA)


def spec_cronicas(agg):
    """Doenças crônicas marcadas no mapa (diabetes, hipertensão, doença renal)."""
    return _spec_barras_h(agg, "Doenças crônicas", agg["cronicas"], ordem=_ordem_das_caracteristicas(True), cor=AZUL)


def spec_resumo(agg):
    titulo = "Via da dieta e acompanhante"
    if not agg["kpis"]["atendimentos"]:
        return _vazio(agg, titulo)
    blocos = [("Via da dieta", agg["via"], {"Oral": VERDE, "Enteral": AZUL, "Zero": CINZA, "Não informada": LARANJA}),
              ("Acompanhante", agg["acomp"], {"Sim": VERDE, "Não": CINZA})]
    return {"tipo": "roscas", "titulo": titulo, "periodo": _periodo(agg),
            "blocos": [{"nome": nome, "itens": [{"rotulo": k, "valor": cont[k], "cor": cores.get(k, CINZA)}
                                                for k in list(cores) + [k for k in cont if k not in cores]
                                                if cont.get(k)]}
                       for nome, cont, cores in blocos]}


# chave -> (título curto, função que monta a especificação). A ordem de exibição vem de GRUPOS.
GRAFICOS = {
    "atendimentos_dia": ("Pacientes atendidos por dia", spec_atendimentos_dia),
    "perfil_dia": ("Perfil por dia", spec_perfil_dia),
    "resumo": ("Via e acompanhante", spec_resumo),
    "classificacao_terapia": ("Classificação da terapia nutricional", spec_classificacao_terapia),
    "consistencia": ("Consistência da dieta", spec_consistencia),
    "caracteristicas": ("Características da dieta", spec_caracteristicas),
    "suplementos": ("Suplementos mais utilizados", spec_suplementos),
    "modulos": ("Uso por módulo", spec_modulos),
    "cronicas": ("Doenças crônicas", spec_cronicas),
}


def ordem_de_exibicao():
    """Chaves dos gráficos na ordem da tela: grupo por grupo, e por último o que não tem grupo."""
    ordem = [c for g in GRUPOS for c in g["graficos"] if c in GRAFICOS]
    return ordem + [c for c in GRAFICOS if c not in ordem]


def especificar_todos(agg):
    """Lista [(chave, título, especificação)] na ordem de exibição. Rápido: não carrega matplotlib."""
    return [(c, GRAFICOS[c][0], GRAFICOS[c][1](agg)) for c in ordem_de_exibicao()]


def organizar_por_grupo(graficos):
    """Agrupa [(chave, título, conteúdo)] segundo GRUPOS. Devolve [{id, titulo, descricao, cor, graficos}].

    O conteúdo pode ser a especificação ou o PNG. Gráfico que não está em nenhum grupo vai para "Outros gráficos";
    grupo sem nenhum gráfico não aparece.
    """
    por_chave = {g[0]: g for g in graficos}
    usados, grupos = set(), []
    for grupo in GRUPOS:
        itens = [por_chave[c] for c in grupo["graficos"] if c in por_chave]
        usados.update(i[0] for i in itens)
        if itens:
            grupos.append({**grupo, "graficos": itens})
    resto = [g for g in graficos if g[0] not in usados]
    if resto:
        grupos.append({**GRUPO_OUTROS, "graficos": resto})
    return grupos


def especificar_por_grupo(agg):
    """As especificações dos gráficos do mês já agrupadas por assunto."""
    return organizar_por_grupo(especificar_todos(agg))


# ------------------------------------------------------------------------ imagens (matplotlib, só quando precisa)
def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor="white")
    _plt().close(fig)
    return buf.getvalue()


def _titulo(spec):
    return f"{spec['titulo']} - {spec['periodo']}"


def _png_vazio(spec):
    fig, ax = _plt().subplots(figsize=(9, 2.2))
    ax.axis("off")
    ax.text(0.5, 0.62, _titulo(spec), ha="center", fontsize=12, fontweight="bold", color=VERDE_ESC)
    ax.text(0.5, 0.25, spec["mensagem"], ha="center", fontsize=10, color=CINZA)
    return _png(fig)


def _png_barras_v(spec):
    from matplotlib.ticker import MaxNLocator
    dias, vals = spec["x"], spec["y"]
    fig, ax = _plt().subplots(figsize=(9, 3.4))
    barras = ax.bar(dias, vals, color=spec["cor"], width=0.72)
    for b, v in zip(barras, vals):
        if v:
            ax.text(b.get_x() + b.get_width() / 2, v + 0.05 * max(vals), str(v), ha="center", va="bottom", fontsize=8)
    ax.set_title(_titulo(spec), fontsize=12, fontweight="bold", color=VERDE_ESC)
    ax.set_xlabel(spec["rotulo_x"])
    ax.set_ylabel(spec["rotulo_y"])
    ax.set_xticks(dias)
    ax.tick_params(axis="x", labelsize=7)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylim(0, max(vals) * 1.18)
    ax.spines[["top", "right"]].set_visible(False)
    return _png(fig)


def _png_linhas(spec):
    from matplotlib.ticker import MaxNLocator
    dias = spec["x"]
    fig, ax = _plt().subplots(figsize=(9, 3.4))
    for serie in spec["series"]:
        ax.plot(dias, serie["valores"], "--" if serie["tracejado"] else "-", color=serie["cor"], marker="o", ms=3.5,
                lw=1.8, label=serie["nome"])
    ax.set_title(_titulo(spec), fontsize=12, fontweight="bold", color=VERDE_ESC)
    ax.set_xlabel(spec["rotulo_x"])
    ax.set_ylabel(spec["rotulo_y"])
    ax.set_xticks(dias)
    ax.tick_params(axis="x", labelsize=7)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylim(bottom=0)
    ax.legend(fontsize=8, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.22), frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    return _png(fig)


def _png_barras_h(spec):
    from matplotlib.ticker import MaxNLocator
    itens = spec["itens"]
    total = spec["total"]
    nomes = [i["nome"] for i in itens][::-1]
    vals = [i["valor"] for i in itens][::-1]
    fig, ax = _plt().subplots(figsize=(9, max(2.2, 0.42 * len(itens) + 1.3)))
    cores = [i.get("cor", spec["cor"]) for i in itens][::-1]
    barras = ax.barh(nomes, vals, color=cores, height=0.62)
    for b, v in zip(barras, vals):
        ax.text(v + 0.01 * max(vals), b.get_y() + b.get_height() / 2, f"{v}  ({100.0 * v / total:.0f}%)",
                va="center", fontsize=8)
    ax.set_title(_titulo(spec), fontsize=12, fontweight="bold", color=VERDE_ESC)
    ax.set_xlabel(spec["rotulo_x"])
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlim(0, max(vals) * 1.22)
    ax.spines[["top", "right"]].set_visible(False)
    return _png(fig)


def _png_roscas(spec):
    fig, eixos = _plt().subplots(1, 3, figsize=(9, 3.0))
    for ax, bloco in zip(eixos, spec["blocos"]):
        itens = bloco["itens"]
        ax.pie([i["valor"] for i in itens], labels=[f"{i['rotulo']}\n{i['valor']}" for i in itens],
               colors=[i["cor"] for i in itens], startangle=90, counterclock=False,
               wedgeprops={"width": 0.45, "edgecolor": "white"}, textprops={"fontsize": 8})
        ax.set_title(bloco["nome"], fontsize=10, color=VERDE_ESC)
    fig.suptitle(_titulo(spec), fontsize=12, fontweight="bold", color=VERDE_ESC)
    return _png(fig)


_DESENHISTAS_PNG = {"vazio": _png_vazio, "barras_v": _png_barras_v, "linhas": _png_linhas,
                    "barras_h": _png_barras_h, "roscas": _png_roscas}


def renderizar_png(spec):
    """Desenha uma especificação com matplotlib e devolve os bytes do PNG."""
    return _DESENHISTAS_PNG[spec["tipo"]](spec)


# Funções de um gráfico só, mantidas por compatibilidade: agregação -> PNG.
def grafico_atendimentos_dia(agg):
    return renderizar_png(spec_atendimentos_dia(agg))


def grafico_perfil_dia(agg):
    return renderizar_png(spec_perfil_dia(agg))


def grafico_consistencia(agg):
    return renderizar_png(spec_consistencia(agg))


def grafico_suplementos(agg):
    return renderizar_png(spec_suplementos(agg))


def grafico_modulos(agg):
    return renderizar_png(spec_modulos(agg))


def grafico_caracteristicas(agg):
    return renderizar_png(spec_caracteristicas(agg))


def grafico_cronicas(agg):
    return renderizar_png(spec_cronicas(agg))


def grafico_resumo(agg):
    return renderizar_png(spec_resumo(agg))


def gerar_todos(agg):
    """Lista [(chave, título, bytes PNG)] na ordem de exibição."""
    return [(c, t, renderizar_png(spec)) for c, t, spec in especificar_todos(agg)]


def gerar_por_grupo(agg):
    """Os gráficos do mês em PNG, já agrupados por assunto (imagem de reserva)."""
    return organizar_por_grupo(gerar_todos(agg))


def renderizar_grupos(grupos):
    """Troca a especificação de cada gráfico pelo PNG correspondente, sem refazer as contas dos dados."""
    return [{**g, "graficos": [(chave, titulo, renderizar_png(spec)) for chave, titulo, spec in g["graficos"]]}
            for g in grupos]


def salvar_graficos(agg, pasta):
    """Grava cada gráfico como PNG na pasta. Devolve a lista de caminhos."""
    os.makedirs(pasta, exist_ok=True)
    caminhos = []
    prefixo = f"mapa_{agg['ano']}-{agg['mes']:02d}_"
    for chave, _, png in gerar_todos(agg):
        p = os.path.join(pasta, prefixo + chave + ".png")
        with open(p, "wb") as f:
            f.write(png)
        caminhos.append(p)
    return caminhos
