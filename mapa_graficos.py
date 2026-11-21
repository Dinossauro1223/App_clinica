# -*- coding: utf-8 -*-
"""Agregação mensal e gráficos do Mapa Nutricional.

Os gráficos são gerados com matplotlib (backend Agg, sem janela) e devolvidos como
bytes PNG; a interface só mostra a imagem. Cada registro do mapa (um leito num dia)
conta como um atendimento.
"""
import calendar
import io
import os
from collections import Counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

import mapa_db as mdb  # noqa: E402

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
     "graficos": ("atendimentos_dia", "perfil_dia", "resumo")},
    {"id": "dieta", "titulo": "Dieta", "cor": LARANJA,
     "descricao": "Consistência da dieta e características como laxativa e constipante",
     "graficos": ("consistencia", "caracteristicas")},
    {"id": "suplementos", "titulo": "Suplementos", "cor": VERDE_ESC,
     "descricao": "Quais suplementos e módulos foram mais usados",
     "graficos": ("suplementos", "modulos")},
    {"id": "cronicas", "titulo": "Doenças crônicas", "cor": AZUL,
     "descricao": "Diabetes, hipertensão e doença renal entre os pacientes atendidos",
     "graficos": ("cronicas",)},
)
GRUPO_OUTROS = {"id": "outros", "titulo": "Outros gráficos", "cor": CINZA, "descricao": "", "graficos": ()}


def agregar_mes(registros, ano, mes):
    """Resume os registros de um mês (lista de dicts de mapa_db.registros_do_mes)."""
    n = calendar.monthrange(ano, mes)[1]
    dias = {d: {"total": 0, "pastosa": 0, "acomp": 0, "supl": 0} for d in range(1, n + 1)}
    consist, via, acomp, supl_sn = Counter(), Counter(), Counter(), Counter()
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
        if sups:
            dias[d]["supl"] += 1
        pacientes.add(r.get("id_paciente") or "n:" + (r.get("nome_paciente") or "").strip().lower())
        consist[r.get("consistencia") or "Não informada"] += 1
        via[r.get("via") or "Não informada"] += 1
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
        "com_suplemento": supl_sn["Sim"],
        "enteral": via["Enteral"],
    }
    for k in ("pastosa", "acompanhante", "com_suplemento", "enteral"):
        kpis[k + "_pct"] = pct(kpis[k])
    return {"ano": ano, "mes": mes, "dias": dias, "consist": consist, "via": via, "acomp": acomp,
            "supl_sn": supl_sn, "sup_nome": sup_nome, "sup_mod": sup_mod, "carac": carac,
            "cronicas": cronicas, "dieta_carac": dieta_carac, "kpis": kpis}


# ------------------------------------------------------------------------ gráficos


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _titulo(agg, texto):
    return f"{texto} - {MESES[agg['mes'] - 1]} de {agg['ano']}"


def _vazio(agg, texto):
    fig, ax = plt.subplots(figsize=(9, 2.2))
    ax.axis("off")
    ax.text(0.5, 0.62, _titulo(agg, texto), ha="center", fontsize=12, fontweight="bold", color=VERDE_ESC)
    ax.text(0.5, 0.25, "Sem registros para exibir neste período.", ha="center", fontsize=10, color=CINZA)
    return _png(fig)


def grafico_atendimentos_dia(agg):
    titulo = "Pacientes atendidos por dia"
    if not agg["kpis"]["atendimentos"]:
        return _vazio(agg, titulo)
    dias = sorted(agg["dias"])
    vals = [agg["dias"][d]["total"] for d in dias]
    fig, ax = plt.subplots(figsize=(9, 3.4))
    barras = ax.bar(dias, vals, color=VERDE, width=0.72)
    for b, v in zip(barras, vals):
        if v:
            ax.text(b.get_x() + b.get_width() / 2, v + 0.05 * max(vals), str(v), ha="center", va="bottom", fontsize=8)
    ax.set_title(_titulo(agg, titulo), fontsize=12, fontweight="bold", color=VERDE_ESC)
    ax.set_xlabel("Dia do mês")
    ax.set_ylabel("Pacientes")
    ax.set_xticks(dias)
    ax.tick_params(axis="x", labelsize=7)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylim(0, max(vals) * 1.18)
    ax.spines[["top", "right"]].set_visible(False)
    return _png(fig)


def grafico_perfil_dia(agg):
    titulo = "Perfil dos atendidos por dia"
    if not agg["kpis"]["atendimentos"]:
        return _vazio(agg, titulo)
    dias = sorted(agg["dias"])
    fig, ax = plt.subplots(figsize=(9, 3.4))
    series = [("total", "Total atendidos", CINZA, "--"), ("pastosa", "Dieta pastosa", LARANJA, "-"),
              ("acomp", "Com acompanhante", AZUL, "-"), ("supl", "Com suplemento", VERDE_ESC, "-")]
    for chave, rot, cor, estilo in series:
        ax.plot(dias, [agg["dias"][d][chave] for d in dias], estilo, color=cor, marker="o", ms=3.5, lw=1.8, label=rot)
    ax.set_title(_titulo(agg, titulo), fontsize=12, fontweight="bold", color=VERDE_ESC)
    ax.set_xlabel("Dia do mês")
    ax.set_ylabel("Pacientes")
    ax.set_xticks(dias)
    ax.tick_params(axis="x", labelsize=7)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylim(bottom=0)
    ax.legend(fontsize=8, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.22), frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    return _png(fig)


def _barras_h(agg, titulo, contagem, ordem=None, cor=VERDE, maximo=12, rotulo_x="Atendimentos (paciente-dia)"):
    if not contagem:
        return _vazio(agg, titulo)
    itens = [(k, contagem[k]) for k in ordem if k in contagem] if ordem else contagem.most_common(maximo)
    itens = itens[:maximo]
    total = agg["kpis"]["atendimentos"] or 1
    nomes = [i[0] for i in itens][::-1]
    vals = [i[1] for i in itens][::-1]
    fig, ax = plt.subplots(figsize=(9, max(2.2, 0.42 * len(itens) + 1.3)))
    barras = ax.barh(nomes, vals, color=cor, height=0.62)
    for b, v in zip(barras, vals):
        ax.text(v + 0.01 * max(vals), b.get_y() + b.get_height() / 2, f"{v}  ({100.0 * v / total:.0f}%)",
                va="center", fontsize=8)
    ax.set_title(_titulo(agg, titulo), fontsize=12, fontweight="bold", color=VERDE_ESC)
    ax.set_xlabel(rotulo_x)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlim(0, max(vals) * 1.22)
    ax.spines[["top", "right"]].set_visible(False)
    return _png(fig)


def grafico_consistencia(agg):
    ordem = mdb.CONSISTENCIAS + ["Não informada"]
    return _barras_h(agg, "Consistência da dieta", agg["consist"], ordem=ordem, cor=LARANJA)


def grafico_suplementos(agg):
    return _barras_h(agg, "Suplementos mais utilizados", agg["sup_nome"], cor=VERDE_ESC)


def grafico_modulos(agg):
    return _barras_h(agg, "Uso por módulo de suplemento", agg["sup_mod"], cor=VERDE)


def _ordem_das_caracteristicas(cronicas):
    """Nomes de mdb.CARACTERISTICAS que são (ou não são) doenças crônicas, na ordem do mapa."""
    return [nome for campo, _, nome in mdb.CARACTERISTICAS if (campo in CAMPOS_CRONICOS) == cronicas]


def grafico_caracteristicas(agg):
    """Características da dieta que não são doenças (laxativa, constipante)."""
    return _barras_h(agg, "Características da dieta", agg["dieta_carac"], ordem=_ordem_das_caracteristicas(False),
                     cor=LARANJA)


def grafico_cronicas(agg):
    """Doenças crônicas marcadas no mapa (diabetes, hipertensão, doença renal)."""
    return _barras_h(agg, "Doenças crônicas", agg["cronicas"], ordem=_ordem_das_caracteristicas(True), cor=AZUL)


def grafico_resumo(agg):
    titulo = "Via da dieta, acompanhante e suplemento"
    if not agg["kpis"]["atendimentos"]:
        return _vazio(agg, titulo)
    fig, eixos = plt.subplots(1, 3, figsize=(9, 3.0))
    blocos = [("Via da dieta", agg["via"], {"Oral": VERDE, "Enteral": AZUL, "Não informada": CINZA}),
              ("Acompanhante", agg["acomp"], {"Sim": VERDE, "Não": CINZA}),
              ("Uso de suplemento", agg["supl_sn"], {"Sim": VERDE_ESC, "Não": CINZA})]
    for ax, (nome, cont, cores) in zip(eixos, blocos):
        chaves = [k for k in cont if cont[k]]
        ax.pie([cont[k] for k in chaves], labels=[f"{k}\n{cont[k]}" for k in chaves],
               colors=[cores.get(k, CINZA) for k in chaves], startangle=90, counterclock=False,
               wedgeprops={"width": 0.45, "edgecolor": "white"}, textprops={"fontsize": 8})
        ax.set_title(nome, fontsize=10, color=VERDE_ESC)
    fig.suptitle(_titulo(agg, titulo), fontsize=12, fontweight="bold", color=VERDE_ESC)
    return _png(fig)


# chave -> (título curto, função que desenha). A ordem de exibição vem de GRUPOS.
GRAFICOS = {
    "atendimentos_dia": ("Pacientes atendidos por dia", grafico_atendimentos_dia),
    "perfil_dia": ("Perfil por dia", grafico_perfil_dia),
    "resumo": ("Via, acompanhante e suplemento", grafico_resumo),
    "consistencia": ("Consistência da dieta", grafico_consistencia),
    "caracteristicas": ("Características da dieta", grafico_caracteristicas),
    "suplementos": ("Suplementos mais utilizados", grafico_suplementos),
    "modulos": ("Uso por módulo", grafico_modulos),
    "cronicas": ("Doenças crônicas", grafico_cronicas),
}


def ordem_de_exibicao():
    """Chaves dos gráficos na ordem da tela: grupo por grupo, e por último o que não tem grupo."""
    ordem = [c for g in GRUPOS for c in g["graficos"] if c in GRAFICOS]
    return ordem + [c for c in GRAFICOS if c not in ordem]


def gerar_todos(agg):
    """Lista [(chave, título, bytes PNG)] na ordem de exibição."""
    return [(c, GRAFICOS[c][0], GRAFICOS[c][1](agg)) for c in ordem_de_exibicao()]


def organizar_por_grupo(graficos):
    """Agrupa [(chave, título, png)] segundo GRUPOS. Devolve [{id, titulo, descricao, cor, graficos}].

    Gráfico que não está em nenhum grupo vai para "Outros gráficos"; grupo sem nenhum gráfico não aparece.
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


def gerar_por_grupo(agg):
    """Os gráficos do mês já agrupados por assunto, prontos para a tela."""
    return organizar_por_grupo(gerar_todos(agg))


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
