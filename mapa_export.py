# -*- coding: utf-8 -*-
"""Exportação do Mapa Nutricional para Excel (.xlsx) e PDF.

Layout pedido: uma linha por leito; a célula do paciente tem 4 divisões:
  1) Nome (Arial 10, negrito)
  2) Sexo, Cor, AJ, PP, PB            (Arial 8, sem negrito)
  3) Altura (cm) e Peso (kg), com (E)stimado/(R)eal
  4) IMC (kg/m²) + (classificação) em vermelho
No PDF todos os títulos são abreviados (legenda no rodapé de cada página).
"""
import math
import json
import unicodedata
from datetime import datetime

import nutri_calculos as nc
import mapa_db as mdb

# chave, título abreviado, largura no PDF (mm), largura no Excel (caracteres)
COLUNAS = [
    ("leito", "Lt", 11, 7),
    ("acomp", "Ac.", 9, 6),
    ("paciente", "Paciente", 81, 60),
    ("idade", "Id.", 9, 6),
    ("reav", "Reav.", 17, 11),
    ("via", "Via", 13, 9),
    ("carac", "Caract. dieta", 25, 18),
    ("consist", "Consist.", 18, 10),
    ("supl", "Suplementos", 34, 24),
    ("obs", "Obs. (Sim/Não)", 46, 32),
    ("fi", "F. Int.", 18, 12),
    # Colunas institucionais adicionais; as onze primeiras preservam a API/layout legado.
    ("cons_LV", "LV", 6, 6),
    ("cons_BR", "BR", 6, 6),
    ("cons_PAS", "PAS", 6, 6),
    ("cons_LPAS", "LÍQ. PAS", 8, 9),
    ("cons_LIQ", "LÍQ", 6, 6),
    ("via_inst", "Via ALM.", 13, 12),
    ("supl_inst", "Suplementação / Dieta enteral", 36, 32),
    ("preferencias", "Preferências", 24, 24),
    ("observacoes", "Observações", 22, 22),
    ("diagnosticos", "Diagnósticos", 20, 20),
]


def _colunas(setor_nome):
    """Acrescenta a identificação do setor na exportação da visão geral."""
    if setor_nome != "Todos_os_setores" and not str(setor_nome).startswith("Grupo_"):
        return COLUNAS
    ajustes = {"paciente": -6, "via": -2, "supl": -6, "obs": -10}
    base = [(k, t, w + ajustes.get(k, 0), ex + ajustes.get(k, 0)) for k, t, w, ex in COLUNAS]
    base.insert(1, ("setor", "Setor / grupo", 30, 24))
    return base


LEGENDA = ("Lt = leito; Ac. = possui acompanhante; Sx = sexo (H = homem, M = mulher); Cor (B = branco, N = negro); "
           "AJ = altura do joelho (cm); PP = perímetro da panturrilha (cm); PB = perímetro do braço (cm); "
           "Alt = altura; E = estimada/o, R = real; Id. = idade (anos); Reav. = data prevista para reavaliação; "
           "DM = diabetes mellitus; HAS = hipertensão arterial; Lax. = laxativa; Const. = constipante; "
           "DRC = doença renal; Consist. = consistência; Líq/Past = líquido-pastosa; "
           "F. Int. = função intestinal (Pres. = presente, em vezes por dia; Aus. = ausente, em dias).")

VERMELHO_PDF = (200, 0, 0)

# ----------------------------------------------------------------- textos das células


def _n(v, casas=1):
    """Número com vírgula; inteiros sem casas ('48' em vez de '48,0'). None -> '-'."""
    if v is None:
        return "-"
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return nc.fmt_num(v, casas)


def _idade_txt(reg):
    a, m = reg.get("idade_anos"), reg.get("idade_meses")
    if a is None:
        return ""
    if a < 5 and m:
        return f"{a}a{m}m" if a else f"{m}m"
    return str(a)


def _fi_txt(reg, abreviar):
    est = reg.get("fi_estado")
    if est == "P":
        f = reg.get("fi_freq")
        freq = f"{_n(f)}x/d" if f else "?"
        return f"Pres. ({freq})" if abreviar else f"Presente ({freq})"
    if est == "A":
        d = reg.get("fi_dias_ausente")
        dias = f"{d} d" if d is not None else "?"
        return f"Aus. ({dias})" if abreviar else f"Ausente ({dias.replace(' d', ' dias')})"
    return ""


def linhas_paciente(reg, abreviar=True):
    """Quatro linhas de segmentos [(texto, estilo)], estilo: 'nome' | 'normal' | 'alerta'."""
    nome = (reg.get("nome_paciente") or "").strip()
    sx, cor = reg.get("sexo"), reg.get("cor")
    if abreviar:
        sx_t = {"H": "H", "M": "M"}.get(sx, "-")
        cor_t = {"B": "B", "N": "N"}.get(cor, "-")
        l2 = f"Sx: {sx_t}  Cor: {cor_t}  AJ: {_n(reg.get('aj_cm'))}  PP: {_n(reg.get('pp_cm'))}  PB: {_n(reg.get('pb_cm'))}"
        l3 = "Alt (cm): {}{}   Peso (kg): {}{}"
        ori_a = {"E": " (E)", "R": " (R)"}
        ori_p = ori_a
    else:
        sx_t = {"H": "Homem", "M": "Mulher"}.get(sx, "-")
        cor_t = {"B": "Branco", "N": "Negro"}.get(cor, "-")
        l2 = (f"Sexo: {sx_t}  Cor: {cor_t}  AJ: {_n(reg.get('aj_cm'))} cm  "
              f"PP: {_n(reg.get('pp_cm'))} cm  PB: {_n(reg.get('pb_cm'))} cm")
        l3 = "Altura (cm): {}{}   Peso (kg): {}{}"
        ori_a = {"E": " (Estimada)", "R": " (Real)"}
        ori_p = {"E": " (Estimado)", "R": " (Real)"}
    l3 = l3.format(_n(reg.get("altura_cm")), ori_a.get(reg.get("altura_origem"), ""),
                   _n(reg.get("peso_kg")), ori_p.get(reg.get("peso_origem"), ""))
    imc = reg.get("imc")
    l4 = [(f"IMC (kg/m²): {nc.fmt_num(imc, 1)}", "normal")]
    if imc is not None and reg.get("imc_class"):
        l4.append((f" ({reg['imc_class']})", "alerta"))
    return [[(nome, "nome")], [(l2, "normal")], [(l3, "normal")], l4]


def _fmt_data(valor):
    if not valor:
        return ""
    try:
        return datetime.strptime(str(valor)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(valor)


def _fmt_num_pt(valor, casas=1, milhar=False):
    if valor is None or valor == "":
        return ""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    texto = f"{numero:,.{casas}f}" if milhar else f"{numero:.{casas}f}"
    texto = texto.replace(",", "#").replace(".", ",").replace("#", ".")
    if casas and texto.endswith("," + "0" * casas):
        texto = texto[:-(casas + 1)]
    return texto


def _consistencias(reg):
    valor = (reg.get("consistencia") or "").strip().lower()
    mapa = {"livre":"LV", "branda":"BR", "pastosa":"PAS",
            "líq/past":"LÍQ. PAS", "liq/past":"LÍQ. PAS",
            "líquida":"LÍQ", "liquida":"LÍQ"}
    selecionada = mapa.get(valor, "")
    return {chave: ("X" if chave == selecionada else "")
            for chave in ("LV", "BR", "PAS", "LÍQ. PAS", "LÍQ")}


def _reavaliacao(reg):
    data_base = reg.get("data")
    classificacao = reg.get("nrs2002_classificacao")
    if not classificacao and reg.get("nrs2002_json"):
        try:
            classificacao = json.loads(reg["nrs2002_json"]).get("grau")
        except (TypeError, ValueError, AttributeError):
            classificacao = None
    if not data_base or not classificacao:
        return _fmt_data(reg.get("data_reavaliacao"))
    try:
        import nrs2002
        try:
            intervalos = nrs2002.ler_intervalos()
        except TypeError:
            intervalos = None
        dias = nrs2002.dias_para(classificacao, intervalos)
        base = datetime.strptime(str(data_base)[:10], "%Y-%m-%d").date()
        from datetime import timedelta
        return (base + timedelta(days=dias)).strftime("%d/%m/%Y")
    except (ImportError, ValueError, TypeError, KeyError):
        return _fmt_data(reg.get("data_reavaliacao"))


def textos_linha(leito, reg, abreviar=True):
    """Prepara os campos clínicos do mapa; registro None representa leito vago."""
    sigla = leito.get("sigla_setor")
    t = {"leito": (f"{sigla} {leito['codigo']}" if sigla else str(leito["codigo"]))}
    if setor := leito.get("setor"):
        grupo = leito.get("grupo_setor")
        sigla_setor = leito.get("sigla_setor")
        t["setor"] = (f"{grupo} · {setor} ({sigla_setor})"
                      if grupo and sigla_setor else setor)
    if reg is None:
        t.update(acomp="", paciente=None, idade="", reav="", via="",
                 consistencias={k: "" for k in ("LV", "BR", "PAS", "LÍQ. PAS", "LÍQ")},
                 carac="", fi="", supl="", preferencias="", obs="", diagnosticos="")
        return t

    nome = (reg.get("nome_paciente") or "").strip()
    primeira = f"{nome} — {_fmt_data(reg.get('data'))}" if nome and reg.get("data") else (nome or _fmt_data(reg.get("data")))
    partes = [primeira]
    if reg.get("sexo"):
        partes.append(f"Sexo: {reg['sexo']}")
    if reg.get("cor"):
        partes.append(f"Cor: {reg['cor']}")
    if not (reg.get("altura_origem") == "M" and reg.get("peso_origem") == "M"):
        for campo, rotulo in (("aj_cm", "AJ (cm)"), ("pp_cm", "PP (cm)"), ("pb_cm", "PB")):
            if reg.get(campo) is not None:
                partes.append(f"{rotulo}: {_fmt_num_pt(reg[campo], 1)}")
    origem_alt = "A" if reg.get("altura_origem") == "M" else (reg.get("altura_origem") or "")
    if reg.get("altura_cm") is not None:
        partes.append(f"ALT ({origem_alt}): {_fmt_num_pt(reg['altura_cm'], 2)}")
    if reg.get("peso_kg") is not None:
        partes.append(f"Peso ({'A' if reg.get('peso_origem') == 'M' else (reg.get('peso_origem') or '')}): {_fmt_num_pt(reg['peso_kg'], 1)} Kg")
    if reg.get("imc") is not None:
        partes.append(f"IMC (Kg/m²): {_fmt_num_pt(reg['imc'], 1)}" +
                      (f" ({reg['imc_class']})" if reg.get("imc_class") else ""))
    if reg.get("meta_kcal") is not None:
        partes.append(f"Kcal: {_fmt_num_pt(reg['meta_kcal'], 0, True)}")
    if reg.get("meta_proteina_g") is not None:
        partes.append(f"Proteínas: {_fmt_num_pt(reg['meta_proteina_g'], 2)} g")
    paciente = "\n".join(partes)

    carac = []
    for campo, sigla_c, _nome in mdb.CARACTERISTICAS:
        if reg.get(campo):
            carac.append({"Lax.": "LAX", "Const.": "CONST"}.get(sigla_c, sigla_c))
    nomes_refeicoes = {"desjejum":"Desj", "colacao":"Col", "almoco":"ALM",
                       "lanche":"Lanche", "jantar":"Jant", "ceia":"Ceia"}
    suplementos = []
    for s in reg.get("suplementos") or []:
        nome_sup = s.get("nome") or ""
        qtd = s.get("qtd_dia")
        ml_oferta = s.get("ml_oferta")
        refeicoes_orig = s.get("refeicoes") or []
        refeicoes = [nomes_refeicoes.get(x, x) for x in refeicoes_orig]
        if ml_oferta is not None:
            volume = _fmt_num_pt(ml_oferta, 0)
            texto = f"{nome_sup}: {volume} mL/oferta"
            if qtd is not None and refeicoes_orig:
                texto += f" × {len(refeicoes_orig)} = {_fmt_num_pt(qtd, 0)} mL/d"
            elif qtd is not None:
                texto += f" ({_fmt_num_pt(qtd, 0)} mL/dia)"
            agua = s.get("agua_ml")
            if agua is not None and float(agua or 0) > 0:
                texto += f"; água: {_fmt_num_pt(agua, 0)} mL/oferta"
            if s.get("batido_fruta"):
                texto += " (batido com fruta)"
        else:
            texto = (f"{nome_sup}: {_fmt_num_pt(qtd, 0)} {s.get('unidade') or 'mL'}/Etapa"
                     if qtd is not None else nome_sup)
        if refeicoes:
            texto += " (" + ", ".join(refeicoes) + ")"
        suplementos.append(texto)
    preferencias = []
    if (reg.get("obs_sim") or "").strip():
        preferencias.append("Sim: " + reg["obs_sim"].strip())
    if (reg.get("obs_nao") or "").strip():
        preferencias.append("Não: " + reg["obs_nao"].strip())
    diagnosticos = (reg.get("condicoes") or "").strip()
    if reg.get("diagnosticos"):
        diagnosticos = ", ".join(x for x in (diagnosticos, str(reg["diagnosticos"])) if x)
    fi = ""
    if reg.get("fi_estado") == "P":
        fi = f"P. {_fmt_num_pt(reg.get('fi_freq') or 1, 0)}x/dia"
    elif reg.get("fi_estado") == "A":
        fi = f"A. {reg.get('fi_dias_ausente') or '?'} dia(s)"
    t.update(acomp="X" if reg.get("acompanhante") else "", paciente=paciente,
             idade=_idade_txt(reg), reav=_reavaliacao(reg), via=reg.get("via") or "",
             consistencias=_consistencias(reg), carac=", ".join(carac), fi=fi,
             supl="\n".join(suplementos), supl_inst="\n".join(suplementos),
             via_inst=reg.get("via") or "", preferencias="\n".join(preferencias),
             observacoes="\n".join(preferencias), obs="\n".join(preferencias),
             diagnosticos=diagnosticos)
    return t


def _filtrar(linhas_mapa, incluir_vagos):
    return [l for l in linhas_mapa if incluir_vagos or l["registro"] is not None]



def filtrar_para_impressao(linhas_mapa, grupo="Ambos", incluir_vagos=True):
    """Aplica os filtros exclusivos da impressão, sem modificar a lista original.

    grupo: "Ambos" (Internos + Externos), "Internos" ou "Externos".
    Setores legados classificados como "Outros" não entram nos grupos solicitados.
    """
    if grupo not in ("Ambos", "Internos", "Externos"):
        raise ValueError("Grupo de impressão inválido.")
    permitidos = {"Internos", "Externos"} if grupo == "Ambos" else {grupo}
    return [item for item in linhas_mapa
            if (item["leito"].get("grupo_setor") or "Outros") in permitidos
            and (incluir_vagos or item.get("registro") is not None)]


# ------------------------------------------------------------------------- Excel


def exportar_excel(caminho, linhas_mapa, data_iso, setor_nome, abreviar=False, incluir_vagos=True):
    """Exporta o mapa institucional em XLSX, com cabeçalho hierárquico e colunas clínicas."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.page import PageMargins
    from openpyxl.worksheet.properties import PageSetupProperties

    colunas = _colunas(setor_nome)
    wb = Workbook()
    ws = wb.active
    ws.title = "Mapa"
    ultima = ws.cell(row=1, column=len(colunas)).column_letter
    borda = Side(style="thin", color="808080")
    caixa = Border(left=borda, right=borda, top=borda, bottom=borda)
    ws.merge_cells(f"A1:{ultima}1")
    ws["A1"] = "SETOR DE NUTRIÇÃO"
    ws["A1"].font = Font(name="Arial", size=14, bold=True)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 25
    ws.merge_cells(f"A2:{ultima}2")
    ws["A2"] = "MAPA DE DIETAS - SETOR GERAL"
    ws["A2"].font = Font(name="Arial", size=11, bold=True)
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 22
    ws.merge_cells(f"A3:{ultima}3")
    ws["A3"] = "IMPRESSO EM " + _fmt_data(data_iso)
    ws["A3"].font = Font(name="Arial", size=8, italic=True)
    ws["A3"].alignment = Alignment(horizontal="right", vertical="center")
    ws.row_dimensions[3].height = 18
    for i, (key, title, _wp, width_xl) in enumerate(colunas, 1):
        cell = ws.cell(row=4, column=i, value=title)
        cell.font = Font(name="Arial", size=8, bold=True)
        cell.fill = PatternFill("solid", fgColor="C8E6C9")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = caixa
        ws.column_dimensions[cell.column_letter].width = width_xl
    ws.row_dimensions[4].height = 28

    for row_idx, item in enumerate(_filtrar(linhas_mapa, incluir_vagos), start=5):
        t = textos_linha(item["leito"], item["registro"], abreviar)
        for col_idx, (key, _title, _wp, _wx) in enumerate(colunas, 1):
            if key.startswith("cons_"):
                codigo = {"cons_LV":"LV", "cons_BR":"BR", "cons_PAS":"PAS",
                          "cons_LPAS":"LÍQ. PAS", "cons_LIQ":"LÍQ"}[key]
                value = t["consistencias"].get(codigo, "")
            else:
                value = t.get(key, "")
            cell = ws.cell(row=row_idx, column=col_idx, value=value or None)
            cell.font = Font(name="Arial", size=8)
            central = key in ("leito", "acomp", "idade", "reav") or key.startswith("cons_")
            cell.alignment = Alignment(horizontal="center" if central else "left",
                                       vertical="top", wrap_text=True)
            cell.border = caixa
            if key in ("supl", "supl_inst") and value:
                cell.fill = PatternFill("solid", fgColor="FCE4D6")
        ws.row_dimensions[row_idx].height = 66 if item["registro"] else 28

    ws.freeze_panes = "A5"
    ws.print_title_rows = "1:4"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.page_margins = PageMargins(left=0.25, right=0.25, top=0.35, bottom=0.4)
    ws.print_options.horizontalCentered = True
    ws.oddFooter.center.text = "Página &P de &N"
    ws.oddFooter.left.text = "NutriLab"
    wb.save(caminho)
    return caminho


# --------------------------------------------------------------------------- PDF

_SUBST = {"–": "-", "—": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "≥": ">=", "≤": "<=",
          "→": "->", "•": "-", "\u00a0": " "}


def _l1(txt):
    """Texto compatível com as fontes padrão do FPDF (latin-1)."""
    txt = "" if txt is None else str(txt)
    for a, b in _SUBST.items():
        txt = txt.replace(a, b)
    return unicodedata.normalize("NFC", txt).encode("latin-1", "replace").decode("latin-1")


def _quebrar(pdf, texto, largura):
    """Quebra o texto em linhas que cabem em `largura` mm na fonte atual."""
    saida = []
    for par in _l1(texto).split("\n"):
        atual = ""
        for palavra in par.split(" "):
            cand = palavra if not atual else atual + " " + palavra
            if pdf.get_string_width(cand) <= largura:
                atual = cand
                continue
            if atual:
                saida.append(atual)
            while len(palavra) > 1 and pdf.get_string_width(palavra) > largura:
                k = len(palavra)
                while k > 1 and pdf.get_string_width(palavra[:k]) > largura:
                    k -= 1
                saida.append(palavra[:k])
                palavra = palavra[k:]
            atual = palavra
        saida.append(atual)
    return saida


# geometria (mm), A4 paisagem
_MARG = 8.0
_Y_CAB = 19.0
_H_CAB = 6.5
_Y_MAX = 189.0
_LIN = 3.3
_H_LIN_PAC = [4.4, 3.6, 3.6, 3.6]
_H_MIN = sum(_H_LIN_PAC) + 0.8
_CAP_LINHAS = 9


def exportar_pdf(caminho, linhas_mapa, data_iso, setor_nome, incluir_vagos=True, pdf_factory=None):
    """Gera o mapa institucional em PDF A4 paisagem."""
    if pdf_factory is None:
        from fpdf import FPDF as pdf_factory
    pdf = pdf_factory(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.set_margins(5, 5, 5)
    colunas = _colunas(setor_nome)
    total = sum(c[2] for c in colunas)
    escala = min(1.0, 287.0 / total)
    larguras = [c[2] * escala for c in colunas]
    xs = [5.0]
    for w in larguras[:-1]:
        xs.append(xs[-1] + w)
    itens = []
    for item in _filtrar(linhas_mapa, incluir_vagos):
        t = textos_linha(item["leito"], item["registro"], True)
        valores = []
        for key, _title, _w, _x in colunas:
            if key.startswith("cons_"):
                cod = {"cons_LV":"LV","cons_BR":"BR","cons_PAS":"PAS",
                       "cons_LPAS":"LÍQ. PAS","cons_LIQ":"LÍQ"}[key]
                value = t["consistencias"].get(cod, "")
            else:
                value = t.get(key, "")
            valores.append("" if value is None else str(value))
        itens.append((t, valores))

    def cabecalho():
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "B", 12)
        pdf.text(5, 10, "SETOR DE NUTRICAO")
        pdf.set_font("Arial", "B", 10)
        titulo = "MAPA DE DIETAS - SETOR GERAL"
        pdf.text(5, 15, titulo)
        pdf.set_font("Arial", "", 7)
        pdf.text(5, 19, _l1("IMPRESSO EM " + _fmt_data(data_iso)))
        pdf.set_fill_color(200, 230, 201)
        pdf.set_draw_color(90, 90, 90)
        pdf.set_font("Arial", "B", 5)
        for (_key, title, _w, _x), x, w in zip(colunas, xs, larguras):
            pdf.rect(x, 23, w, 8, "FD")
            titulo_pdf = {"Preferências": "Preferencias", "Observações": "Observacoes",
                          "Diagnósticos": "Diagnosticos"}.get(title, _l1(title))
            pdf.text(x + 0.5, 28, titulo_pdf[:max(2, int(w * 1.1))])

    pdf.add_page()
    cabecalho()
    y = 31
    for t, values in itens:
        altura = 17 if t["paciente"] else 9
        if y + altura > 198:
            pdf.add_page()
            cabecalho()
            y = 31
        pdf.set_draw_color(130, 130, 130)
        for x, w in zip(xs, larguras):
            pdf.rect(x, y, w, altura, "D")
        for i, value in enumerate(values):
            if not value:
                continue
            key = colunas[i][0]
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Arial", "B" if key == "leito" else "", 5 if key != "paciente" else 6)
            linhas = _l1(value).splitlines() or [""]
            max_linhas = max(1, int((altura - 1) / 2.4))
            for j, line in enumerate(linhas[:max_linhas]):
                limite = max(2, int(larguras[i] * 1.3))
                line = line[:limite]
                x_texto, y_texto = xs[i] + 0.5, y + 3 + j * 2.3
                # Mantém a classificação antropométrica destacada em vermelho no PDF.
                if key == "paciente" and "IMC (" in line and " (" in line:
                    base, classificacao = line.rsplit(" (", 1)
                    pdf.text(x_texto, y_texto, base)
                    x_classe = x_texto + pdf.get_string_width(base)
                    pdf.set_text_color(*VERMELHO_PDF)
                    pdf.text(x_classe, y_texto, " (" + classificacao)
                    pdf.set_text_color(0, 0, 0)
                else:
                    pdf.text(x_texto, y_texto, line)
        y += altura
    pdf.output(caminho)
    return caminho
