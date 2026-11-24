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
]


def _colunas(setor_nome):
    """Acrescenta a identificação do setor na exportação da visão geral."""
    if setor_nome != "Todos_os_setores":
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


def textos_linha(leito, reg, abreviar=True):
    """Textos de todas as colunas de uma linha. `reg` None = leito vago."""
    nome_setor = leito.get("setor", "")
    sigla = leito.get("sigla_setor")
    grupo = leito.get("grupo_setor")
    setor_rotulo = f"{nome_setor} ({sigla})" if sigla else nome_setor
    if grupo and grupo != "Outros":
        setor_rotulo = f"{grupo} · {setor_rotulo}"
    t = {"leito": str(leito["codigo"]), "setor": setor_rotulo}
    if reg is None:
        t.update(paciente=None, acomp="", idade="", reav="", via="", carac="", consist="", supl=[], obs=[], fi="")
        return t
    t["paciente"] = linhas_paciente(reg, abreviar)
    t["acomp"] = "Sim" if reg.get("acompanhante") else "Não"
    t["idade"] = _idade_txt(reg)
    t["reav"] = mdb.iso_para_br(reg.get("data_reavaliacao"))
    t["via"] = reg.get("via") or ""
    nomes = [(sig if abreviar else nome) for campo, sig, nome in mdb.CARACTERISTICAS if reg.get(campo)]
    t["carac"] = ", ".join(nomes)
    t["consist"] = reg.get("consistencia") or ""
    supl = []
    nomes_refeicoes = {"desjejum": "desjejum", "colacao": "lanche da manhã", "almoco": "almoço",
                       "lanche": "lanche da tarde", "jantar": "jantar", "ceia": "ceia"}
    for s in reg.get("suplementos") or []:
        txt = s["nome"]
        if s.get("ml_oferta") is not None:
            refs = s.get("refeicoes") or []
            txt += f" {_n(s['ml_oferta'])} mL/oferta × {len(refs)} = {_n(s.get('qtd_dia'))} mL/d"
            if refs:
                txt += " (" + ", ".join(nomes_refeicoes.get(r, r) for r in refs) + ")"
            if s.get("agua_ml"):
                txt += f"; água: {_n(s['agua_ml'])} mL/oferta"
        elif s.get("qtd_dia"):
            txt += f" {_n(s['qtd_dia'])} {s.get('unidade') or ''}/d".rstrip()
        if s.get("batido_fruta"):
            txt += " (batido com fruta)"
        supl.append(txt)
    t["supl"] = supl
    obs = []
    if (reg.get("obs_sim") or "").strip():
        obs.append("Sim: " + reg["obs_sim"].strip())
    if (reg.get("obs_nao") or "").strip():
        obs.append("Não: " + reg["obs_nao"].strip())
    t["obs"] = obs
    t["fi"] = _fi_txt(reg, abreviar)
    return t


def _filtrar(linhas_mapa, incluir_vagos):
    return [l for l in linhas_mapa if incluir_vagos or l["registro"] is not None]


# ------------------------------------------------------------------------- Excel


def exportar_excel(caminho, linhas_mapa, data_iso, setor_nome, abreviar=False, incluir_vagos=True):
    """Gera o .xlsx do mapa (uma linha de Excel por leito)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.page import PageMargins
    from openpyxl.worksheet.properties import PageSetupProperties
    try:
        from openpyxl.cell.rich_text import CellRichText, TextBlock
        from openpyxl.cell.text import InlineFont
        rico = True
    except ImportError:  # openpyxl < 3.1
        rico = False

    colunas = _colunas(setor_nome)
    titulo_setor = "Todos os setores" if setor_nome == "Todos_os_setores" else setor_nome
    wb = Workbook()
    ws = wb.active
    ws.title = "Mapa"
    n_col = len(colunas)
    ultima = chr(ord("A") + n_col - 1)
    borda = Side(style="thin", color="808080")
    caixa = Border(left=borda, right=borda, top=borda, bottom=borda)

    ws.merge_cells(f"A1:{ultima}1")
    ws["A1"] = f"MAPA NUTRICIONAL  -  {titulo_setor}  -  {mdb.iso_para_br(data_iso)}"
    ws["A1"].font = Font(name="Arial", size=12, bold=True)
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 22
    ws.merge_cells(f"A2:{ultima}2")
    ws["A2"] = "Gerado em " + datetime.now().strftime("%d/%m/%Y %H:%M") + " pelo NutriLab"
    ws["A2"].font = Font(name="Arial", size=8, italic=True, color="666666")

    for i, (_, titulo, _, larg) in enumerate(colunas, start=1):
        c = ws.cell(row=3, column=i, value=titulo)
        c.font = Font(name="Arial", size=8, bold=True)
        c.fill = PatternFill("solid", fgColor="C8E6C9")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = caixa
        ws.column_dimensions[chr(ord("A") + i - 1)].width = larg
    ws.row_dimensions[3].height = 20

    f8 = Font(name="Arial", size=8)
    linha = 4
    for item in _filtrar(linhas_mapa, incluir_vagos):
        t = textos_linha(item["leito"], item["registro"], abreviar)
        altura_pt = 48.0
        for i, (chave, _, _, larg) in enumerate(colunas, start=1):
            c = ws.cell(row=linha, column=i)
            c.border = caixa
            c.font = f8
            centro = chave in ("leito", "acomp", "idade", "reav", "via", "consist", "fi")
            c.alignment = Alignment(horizontal="center" if centro else "left", vertical="center" if centro else "top",
                                    wrap_text=True)
            if chave == "leito":
                c.value = t["leito"]
                c.font = Font(name="Arial", size=9, bold=True)
            elif chave == "paciente":
                if t["paciente"] is None:
                    c.value = "Vago"
                    c.font = Font(name="Arial", size=8, italic=True, color="808080")
                elif rico:
                    blocos = []
                    for k, seg_linha in enumerate(t["paciente"]):
                        for texto, estilo in seg_linha:
                            fonte = InlineFont(rFont="Arial", sz=10 if estilo == "nome" else 8,
                                               b=(estilo == "nome"),
                                               color="FFFF0000" if estilo == "alerta" else "FF000000")
                            blocos.append(TextBlock(fonte, texto))
                        if k < len(t["paciente"]) - 1:
                            blocos.append(TextBlock(InlineFont(rFont="Arial", sz=8), "\n"))
                    c.value = CellRichText(*blocos)
                else:
                    c.value = "\n".join("".join(s for s, _ in seg) for seg in t["paciente"])
            elif chave in ("supl", "obs"):
                linhas_txt = t[chave]
                c.value = "\n".join(linhas_txt) if linhas_txt else None
                est = sum(max(1, math.ceil(len(x) / (larg * 1.05))) for x in linhas_txt)
                altura_pt = max(altura_pt, est * 11.0 + 4)
            elif chave == "carac":
                c.value = t["carac"] or None
                altura_pt = max(altura_pt, math.ceil(len(t["carac"]) / (larg * 1.05)) * 11.0 + 4)
            else:
                c.value = t[chave] or None
        ws.row_dimensions[linha].height = min(altura_pt, 400)
        linha += 1

    ws.merge_cells(f"A{linha + 1}:{ultima}{linha + 3}")
    ws[f"A{linha + 1}"] = "Legenda: " + LEGENDA
    ws[f"A{linha + 1}"].font = Font(name="Arial", size=7, color="444444")
    ws[f"A{linha + 1}"].alignment = Alignment(wrap_text=True, vertical="top")

    ws.freeze_panes = "A4"
    ws.print_title_rows = "3:3"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.page_margins = PageMargins(left=0.3, right=0.3, top=0.4, bottom=0.5)
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
    """Gera o PDF do mapa (A4 paisagem, títulos abreviados, 4 divisões na célula do paciente)."""
    if pdf_factory is None:
        from fpdf import FPDF as pdf_factory
    pdf = pdf_factory(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.set_margins(_MARG, _MARG, _MARG)
    colunas = _colunas(setor_nome)
    titulo_setor = "Todos os setores" if setor_nome == "Todos_os_setores" else setor_nome

    larguras = [c[2] for c in colunas]
    xs = [_MARG]
    for w in larguras[:-1]:
        xs.append(xs[-1] + w)
    idx = {c[0]: i for i, c in enumerate(colunas)}

    # 1) mede as linhas (precisa da fonte definida para get_string_width)
    itens = []
    for item in _filtrar(linhas_mapa, incluir_vagos):
        t = textos_linha(item["leito"], item["registro"], abreviar=True)
        pdf.set_font("Arial", "", 8)
        blocos = {}
        for chave in ("supl", "obs"):
            ls = []
            for x in t[chave]:
                ls.extend(_quebrar(pdf, x, larguras[idx[chave]] - 2.0))
            if len(ls) > _CAP_LINHAS:
                ls = ls[:_CAP_LINHAS - 1] + [ls[_CAP_LINHAS - 1].rstrip() + ".."]
            blocos[chave] = ls
        blocos["carac"] = _quebrar(pdf, t["carac"], larguras[idx["carac"]] - 2.0) if t["carac"] else []
        blocos["fi"] = _quebrar(pdf, t["fi"], larguras[idx["fi"]] - 2.0) if t["fi"] else []
        altura = max(_H_MIN, *(len(v) * _LIN + 1.4 for v in blocos.values()))
        itens.append((t, blocos, min(altura, 45.0)))

    # 2) pagina
    paginas, atual, y = [], [], _Y_CAB + _H_CAB
    for it in itens:
        if atual and y + it[2] > _Y_MAX:
            paginas.append(atual)
            atual, y = [], _Y_CAB + _H_CAB
        atual.append(it)
        y += it[2]
    paginas.append(atual)

    def baseline(y_topo, h, pt):
        return y_topo + h / 2.0 + pt * 0.3528 * 0.30

    def cabecalho(n_pag):
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "B", 12)
        pdf.text(_MARG, 13, _l1(f"MAPA NUTRICIONAL - {titulo_setor}"))
        pdf.set_font("Arial", "B", 10)
        dt = _l1("Data: " + mdb.iso_para_br(data_iso))
        pdf.text(297 - _MARG - pdf.get_string_width(dt), 13, dt)
        pdf.set_font("Arial", "", 7)
        pdf.text(_MARG, 16.6, _l1("Gerado em " + datetime.now().strftime("%d/%m/%Y %H:%M") + " - NutriLab"))
        pg = _l1(f"Pág. {n_pag}/{len(paginas)}")
        pdf.text(297 - _MARG - pdf.get_string_width(pg), 16.6, pg)
        pdf.set_fill_color(200, 230, 201)
        pdf.set_draw_color(90, 90, 90)
        pdf.set_line_width(0.2)
        pdf.set_font("Arial", "B", 7)
        for (chave, titulo, w, _), x in zip(colunas, xs):
            pdf.rect(x, _Y_CAB, w, _H_CAB, "FD")
            tt = _l1(titulo)
            pdf.text(x + (w - pdf.get_string_width(tt)) / 2.0, baseline(_Y_CAB, _H_CAB, 7), tt)

    def rodape():
        pdf.set_text_color(70, 70, 70)
        pdf.set_font("Arial", "", 6)
        pdf.set_font("Arial", "", 6)
        ls = _quebrar(pdf, "Legenda: " + LEGENDA, 297 - 2 * _MARG)
        y0 = 210 - _MARG - len(ls[:4]) * 2.6 + 2.0
        for k, l in enumerate(ls[:4]):
            pdf.text(_MARG, y0 + k * 2.6, l)
        pdf.set_text_color(0, 0, 0)

    for n_pag, grupo in enumerate(paginas, start=1):
        pdf.add_page()
        cabecalho(n_pag)
        y = _Y_CAB + _H_CAB
        for t, blocos, h in grupo:
            pdf.set_draw_color(90, 90, 90)
            pdf.set_line_width(0.2)
            for (chave, _, w, _), x in zip(colunas, xs):
                pdf.rect(x, y, w, h, "D")
            # leito, acompanhante, idade, reav., via, consistência: texto centralizado
            pdf.set_text_color(0, 0, 0)
            for chave, bold in (("leito", True), ("setor", False), ("acomp", False), ("idade", False), ("reav", False),
                                ("via", False), ("consist", False)):
                if chave not in idx or not t[chave]:
                    continue
                pdf.set_font("Arial", "B" if bold else "", 9 if bold else 8)
                tx = _l1(t[chave])
                i = idx[chave]
                pdf.text(xs[i] + (larguras[i] - pdf.get_string_width(tx)) / 2.0, baseline(y, h, 8), tx)
            # paciente: 4 divisões
            xp = xs[idx["paciente"]]
            wp = larguras[idx["paciente"]]
            if t["paciente"] is None:
                pdf.set_font("Arial", "I", 8)
                pdf.set_text_color(120, 120, 120)
                pdf.text(xp + 1.2, baseline(y, h, 8), "Vago")
                pdf.set_text_color(0, 0, 0)
            else:
                yy = y
                pdf.set_draw_color(150, 150, 150)
                pdf.set_line_width(0.15)
                for k, seg_linha in enumerate(t["paciente"]):
                    hl = _H_LIN_PAC[k]
                    if k > 0:
                        pdf.line(xp, yy, xp + wp, yy)
                    cx = xp + 1.2
                    for texto, estilo in seg_linha:
                        if estilo == "nome":
                            pdf.set_font("Arial", "B", 10)
                            pdf.set_text_color(0, 0, 0)
                        else:
                            pdf.set_font("Arial", "", 8)
                            pdf.set_text_color(*(VERMELHO_PDF if estilo == "alerta" else (0, 0, 0)))
                        tx = _l1(texto)
                        # nunca ultrapassa a célula: corta com '..' se preciso
                        while len(tx) > 3 and cx + pdf.get_string_width(tx) > xp + wp - 0.8:
                            tx = tx[:-3] + ".."
                        pdf.text(cx, baseline(yy, hl + 0.2, 10 if estilo == "nome" else 8), tx)
                        cx += pdf.get_string_width(tx)
                    yy += hl
                pdf.set_text_color(0, 0, 0)
            # suplementos, observações, características, função intestinal
            pdf.set_font("Arial", "", 8)
            pdf.set_text_color(0, 0, 0)
            for chave in ("carac", "supl", "obs", "fi"):
                i = idx[chave]
                ls = blocos[chave]
                topo = y + (h - len(ls) * _LIN) / 2.0  # bloco centralizado verticalmente
                for k, l in enumerate(ls):
                    pdf.text(xs[i] + 1.0, topo + (k + 1) * _LIN - 0.75, l)
            y += h
        rodape()
    pdf.output(caminho)
    return caminho
