# -*- coding: utf-8 -*-
"""PDF e impressão das condutas de alta.

  * Folha do PACIENTE: só as condutas CONFIRMADAS, em linguagem leiga, compacta (A4, fonte 10).
  * Relatório do NUTRICIONISTA: visão integral (todas as condutas, com situação, texto técnico, lista de conferência,
    texto que vai ao paciente, motivo de "não se aplica" e referências ABNT). Uso interno.

Usa só as primitivas de desenho do FPDF que o mapa_export já usa (text, rect, line, get_string_width): a quebra de linha
e a paginação são feitas aqui, o que dá o mesmo resultado no fpdf real e no simulador dos testes. As fontes padrão do
PDF só aceitam latin-1; símbolos fora dele são trocados (ver _TROCAS). `fpdf` é importado só na hora de gerar.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import unicodedata

import condutas_alta as ca

MARG = 14.0
LARG, ALT = 210.0, 297.0
Y_TOPO, Y_MAX, Y_RODAPE = 14.0, 281.0, 288.5
RECUO_ITEM = 3.8
VERDE, CINZA, PRETO, LARANJA = (27, 94, 32), (95, 95, 95), (0, 0, 0), (170, 80, 0)

# estilo -> (estilo da fonte, tamanho em pt, altura da linha em mm)
_ESTILOS = {
    "paciente": {"titulo": ("B", 15, 7.0), "sub": ("", 9.5, 4.4), "h": ("B", 11, 5.6), "p": ("", 10, 4.5),
                 "li": ("", 10, 4.5), "nota": ("I", 8.5, 3.9)},
    "profissional": {"titulo": ("B", 14, 6.6), "sub": ("", 9, 4.0), "h": ("B", 10.5, 5.2), "p": ("", 9, 4.0),
                     "li": ("", 9, 4.0), "nota": ("I", 8, 3.6), "ref": ("", 7.5, 3.3), "rot": ("B", 9, 4.0)},
}
_TROCAS = {"\u2013": "-", "\u2014": "-", "\u2212": "-", "•": "-", "≥": ">=", "≤": "<=",
           "→": "->", "←": "<-", "…": "...", "‘": "'", "’": "'", "“": '"',
           "”": '"', " ": " ", "≈": "~", "✓": "ok", "☐": "( )", "☑": "(x)"}


def _l1(txt):
    """Texto compatível com as fontes padrão do PDF (latin-1)."""
    txt = "".join(_TROCAS.get(ch, ch) for ch in str(txt or ""))
    return txt.encode("latin-1", "replace").decode("latin-1")


class _U:
    """Uma linha já quebrada, pronta para desenhar."""
    __slots__ = ("tipo", "texto", "recuo", "marcador_x", "cor", "antes", "manter", "regua")

    def __init__(self, tipo, texto, recuo=0.0, marcador_x=None, cor=PRETO, antes=0.0, manter=0, regua=False):
        self.tipo, self.texto, self.recuo, self.marcador_x = tipo, texto, recuo, marcador_x
        self.cor, self.antes, self.manter, self.regua = cor, antes, manter, regua


def _quebrar(pdf, texto, largura):
    """Quebra por palavras (e por caracteres, se uma palavra sozinha não couber: links longos)."""
    linhas, atual = [], ""
    for palavra in str(texto).split():
        while pdf.get_string_width(palavra) > largura:           # palavra maior que a linha
            if atual:
                linhas.append(atual)
                atual = ""
            corte = len(palavra)
            while corte > 1 and pdf.get_string_width(palavra[:corte]) > largura:
                corte -= 1
            linhas.append(palavra[:corte])
            palavra = palavra[corte:]
        tentativa = palavra if not atual else atual + " " + palavra
        if pdf.get_string_width(tentativa) <= largura:
            atual = tentativa
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas or [""]


# ------------------------------------------------------------------------------------------- montagem
class _Montador:
    def __init__(self, pdf, perfil):
        self.pdf, self.est, self.unidades = pdf, _ESTILOS[perfil], []
        self.larg = LARG - 2 * MARG

    def _fonte(self, tipo):
        e = self.est[tipo]
        self.pdf.set_font("Arial", e[0], e[1])

    def paragrafo(self, texto, tipo="p", cor=PRETO, antes=0.0, item=False, recuo=0.0, manter=0):
        self._fonte(tipo)
        indent = recuo + (RECUO_ITEM if item else 0.0)
        for i, ln in enumerate(_quebrar(self.pdf, _l1(texto), self.larg - indent)):
            self.unidades.append(_U(tipo, ln, indent, recuo if (item and i == 0) else None, cor,
                                    antes if i == 0 else 0.0, manter if i == 0 else 0))

    def texto_livre(self, texto, tipo="p", cor=PRETO, antes=0.0):
        """Linhas do texto da nutricionista/catálogo: '- ' vira marcador; o resto é parágrafo."""
        primeiro = True
        for kind, ln in ca.linhas_do_texto(texto):
            self.paragrafo(ln, "li" if kind == "item" else tipo, cor, antes if primeiro else 0.6, item=kind == "item")
            primeiro = False

    def titulo(self, texto):
        self.paragrafo(texto, "titulo", VERDE)

    def cabecalho(self, texto, cor=VERDE, antes=3.0):
        self.paragrafo(texto, "h", cor, antes, manter=2)
        self.unidades[-1].regua = True

    def regua(self):
        self.unidades.append(_U("nota", "", antes=0.4, regua=True))


def _paginar(unidades, est):
    paginas, atual, y = [], [], Y_TOPO
    for i, u in enumerate(unidades):
        h = est[u.tipo][2]
        antes = u.antes if atual else 0.0
        precisa = antes + h + sum(est[v.tipo][2] for v in unidades[i + 1:i + 1 + u.manter])
        if atual and y + precisa > Y_MAX:
            paginas.append(atual)
            atual, y, antes = [], Y_TOPO + 8.0, 0.0                 # espaço do mini cabeçalho
        atual.append((u, y + antes))
        y += antes + h
    if atual:
        paginas.append(atual)
    return paginas


def _renderizar(pdf, paginas, est, titulo_curto, rodape_esq):
    total = len(paginas)
    for n, itens in enumerate(paginas, start=1):
        pdf.add_page()
        pdf.set_line_width(0.2)
        if n > 1:
            pdf.set_font("Arial", "", 8)
            pdf.set_text_color(*CINZA)
            pdf.text(MARG, Y_TOPO + 3.2, _l1(titulo_curto))
            pdf.set_draw_color(*CINZA)
            pdf.line(MARG, Y_TOPO + 5.0, LARG - MARG, Y_TOPO + 5.0)
        for u, y in itens:
            e = est[u.tipo]
            if u.texto:
                pdf.set_font("Arial", e[0], e[1])
                pdf.set_text_color(*u.cor)
                base = y + e[2] * 0.76
                pdf.text(MARG + u.recuo, base, u.texto)
                if u.marcador_x is not None:
                    pdf.set_fill_color(*u.cor)
                    pdf.rect(MARG + u.marcador_x + 0.4, base - 1.6, 1.0, 1.0, "F")
            if u.regua:
                pdf.set_draw_color(*VERDE)
                pdf.set_line_width(0.25)
                pdf.line(MARG, y + e[2] - 0.5, LARG - MARG, y + e[2] - 0.5)
        pdf.set_draw_color(*CINZA)
        pdf.set_line_width(0.2)
        pdf.line(MARG, Y_RODAPE - 3.6, LARG - MARG, Y_RODAPE - 3.6)
        pdf.set_font("Arial", "", 8)
        pdf.set_text_color(*CINZA)
        pdf.text(MARG, Y_RODAPE, _l1(rodape_esq))
        pag = f"Página {n} de {total}"
        pdf.text(LARG - MARG - pdf.get_string_width(pag), Y_RODAPE, _l1(pag))


def _nova_pdf(pdf_factory):
    if pdf_factory is None:
        from fpdf import FPDF as pdf_factory
    pdf = pdf_factory(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.set_margins(MARG, MARG, MARG)
    return pdf


# ------------------------------------------------------------------------------------- conteúdo
def _linha_assinatura(modelo):
    nome, crn = (modelo.get("nutricionista") or "").strip(), (modelo.get("crn") or "").strip()
    return "Nutricionista: " + " ".join(x for x in (nome, f"({crn})" if crn else "") if x) if nome else "Nutrição"


def _montar_paciente(pdf, modelo):
    itens = [i for i in modelo["itens"] if i["estado"] == "confirmada"]
    if not itens:
        raise ca.ErroCondutasAlta("Não há condutas confirmadas para imprimir na folha do paciente.")
    m = _Montador(pdf, "paciente")
    m.titulo("Orientações de alta: nutrição")
    m.paragrafo(f"Paciente: {modelo['paciente'] or '______________________'}  |  Data: {modelo['data']}", "sub", PRETO)
    m.paragrafo("Siga estas orientações em casa. Se tiver dúvida ou notar algo diferente, procure o serviço de saúde.",
                "nota", CINZA, 0.6)
    m.regua()
    for it in itens:
        m.cabecalho(it["titulo_paciente"] or it["titulo"])
        m.texto_livre(it["texto_paciente"], "p", PRETO, 0.8)
    recado = ca.normalizar_texto(modelo.get("recado"))
    if recado:
        m.cabecalho("Recado da nutricionista")
        m.texto_livre(recado, "p", PRETO, 0.8)
    return m


def _rotulo_estado(it):
    if it["estado"] == "confirmada":
        return "CONFIRMADA" + (" (texto editado)" if it["editado"] else ""), VERDE
    if it["estado"] == "nao_se_aplica":
        return "NÃO SE APLICA", CINZA
    return "PENDENTE", LARANJA


def _montar_profissional(pdf, modelo):
    itens = modelo["itens"]
    m = _Montador(pdf, "profissional")
    m.titulo("Condutas de alta: visão do nutricionista")
    m.paragrafo("Uso interno, não entregar ao paciente. Cada conduta é uma sugestão do catálogo, só vale depois de "
                "confirmada pela nutricionista.", "nota", LARANJA)
    m.paragrafo(f"Paciente: {modelo['paciente'] or '-'}  |  Data: {modelo['data']}  |  Situação: "
                + ("entregue" if modelo.get("status") == "entregue" else "rascunho"), "sub", PRETO, 0.8)
    m.paragrafo(ca.frase_doencas_do_mapa(modelo["condicoes"], modelo.get("sem_registro", False)), "sub", PRETO)
    cont = {k: sum(1 for i in itens if i["estado"] == k) for k in ("confirmada", "nao_se_aplica", "pendente")}
    m.paragrafo(f"Confirmadas: {cont['confirmada']}  |  Não se aplicam: {cont['nao_se_aplica']}  |  "
                f"Pendentes: {cont['pendente']}", "sub", PRETO)
    m.regua()
    for it in itens:
        rotulo, cor = _rotulo_estado(it)
        extra = " | catálogo atualizado depois da decisão" if it.get("catalogo_mudou") else ""
        m.cabecalho(f"[{it['codigo']}] {it['titulo']}", cor)
        m.paragrafo(f"Situação: {rotulo}{extra}", "rot", cor, 0.4)
        m.texto_livre(it["texto_profissional"], "p", PRETO, 0.8)
        if it["conferir"]:
            m.paragrafo("Conferir antes de confirmar:", "rot", PRETO, 1.0, manter=1)
            for c in it["conferir"]:
                m.paragrafo(c, "li", PRETO, 0.3, item=True)
        if it["estado"] == "confirmada":
            m.paragrafo("Texto que vai ao paciente:", "rot", PRETO, 1.0, manter=1)
            m.texto_livre(it["texto_paciente"], "li", CINZA, 0.3)
        elif it["estado"] == "nao_se_aplica":
            m.paragrafo("Motivo: " + (it["justificativa"] or "-"), "p", CINZA, 0.8)
    recado = ca.normalizar_texto(modelo.get("recado"))
    if recado:
        m.cabecalho("Recado ao paciente (vai na folha)")
        m.texto_livre(recado, "p", PRETO, 0.8)
    refs = sorted({r for it in itens for r in it["fontes"]}, key=lambda r: r.upper())
    if refs:
        m.cabecalho("Referências")
        for r in refs:
            m.paragrafo(r, "ref", PRETO, 0.9)
    if modelo.get("catalogo"):
        m.paragrafo("Catálogo de condutas: " + "; ".join(modelo["catalogo"]) + ".", "nota", CINZA, 2.0)
    return m


_PERFIS = {
    "paciente": (_montar_paciente, lambda md: "Orientações de alta - " + (md["paciente"] or "paciente"),
                 lambda md: _linha_assinatura(md)),
    "profissional": (_montar_profissional, lambda md: "Condutas de alta (uso interno) - " + (md["paciente"] or "paciente"),
                     lambda md: "Visão do nutricionista - uso interno"),
}


def _gerar(modelo, perfil, caminho=None, pdf_factory=None):
    pdf = _nova_pdf(pdf_factory)
    montar, titulo_curto, rodape = _PERFIS[perfil]
    montador = montar(pdf, modelo)
    paginas = _paginar(montador.unidades, montador.est)
    _renderizar(pdf, paginas, montador.est, titulo_curto(modelo), rodape(modelo))
    if caminho:
        pdf.output(caminho)
    return len(paginas)


def exportar_pdf_paciente(caminho, modelo, pdf_factory=None):
    """Grava a folha do paciente (só condutas confirmadas) e devolve o número de páginas."""
    return _gerar(modelo, "paciente", caminho, pdf_factory)


def exportar_pdf_profissional(caminho, modelo, pdf_factory=None):
    """Grava o relatório integral do nutricionista e devolve o número de páginas."""
    return _gerar(modelo, "profissional", caminho, pdf_factory)


def contar_paginas(modelo, perfil="paciente", pdf_factory=None):
    """Páginas que o PDF teria (sem gravar nada). Lança ErroCondutasAlta se a folha do paciente estiver vazia."""
    return _gerar(modelo, perfil, None, pdf_factory)


def nome_sugerido(modelo, perfil="paciente"):
    base = unicodedata.normalize("NFKD", modelo.get("paciente") or "paciente").encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_")[:40] or "paciente"
    iso = "-".join(reversed((modelo.get("data") or "").split("/"))) or "sem-data"
    prefixo = "Orientacoes_de_alta" if perfil == "paciente" else "Condutas_de_alta_nutricionista"
    return f"{prefixo}_{slug}_{iso}.pdf"


# ------------------------------------------------------------------------------------- impressão
def imprimir_pdf(caminho, *, plataforma=None, startfile=None, executar=None, localizar=None):
    """Manda o PDF para a impressora padrão. Devolve (estado, mensagem): 'impresso', 'aberto' ou 'erro'.

    Windows: verbo "print" do leitor de PDF padrão; se ele não aceitar, abre o PDF para imprimir com Ctrl+P.
    Linux/macOS: `lp` (CUPS) se existir; senão abre o arquivo. Não há como confirmar que a impressora imprimiu.
    """
    plataforma = plataforma or sys.platform
    executar = executar or subprocess.run
    localizar = localizar or shutil.which
    if not os.path.exists(caminho):
        return "erro", "O arquivo PDF não foi encontrado."
    try:
        if plataforma.startswith("win"):
            abrir = startfile or os.startfile
            try:
                abrir(caminho, "print")
                return "impresso", "Enviado para a impressora padrão do computador."
            except OSError:
                abrir(caminho)
                return "aberto", ("O leitor de PDF não aceitou imprimir direto. O PDF foi aberto: use Ctrl+P para imprimir.")
        lp = localizar("lp")
        if lp and executar([lp, caminho], capture_output=True, timeout=30).returncode == 0:
            return "impresso", "Enviado para a impressora padrão do computador."
        abridor = localizar("open" if plataforma == "darwin" else "xdg-open")
        if abridor:
            executar([abridor, caminho], capture_output=True, timeout=30)
            return "aberto", "O PDF foi aberto: use o comando de imprimir do leitor de PDF."
    except (OSError, subprocess.SubprocessError) as erro:
        return "erro", f"Não foi possível imprimir ({type(erro).__name__}). Salve o PDF e imprima por outro programa."
    return "erro", "Nenhum programa de impressão foi encontrado. Salve o PDF e imprima por outro programa."
