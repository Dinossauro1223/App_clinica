"""Conferência automática da aba `Peso-Alt` da planilha de cálculos do setor contra o catálogo de referência do projeto.

Uso:
    python tools/conferir_equacoes_planilha.py "CÁLCULOS ESTIMATIVA DE PESO E ESTATURA.xlsx" [--aba Peso-Alt] [--markdown]

O que faz: lê SOMENTE os rótulos e as FÓRMULAS (texto) da aba, extrai os coeficientes das equações de Chumlea de peso
(AJ + PB) e de estatura (AJ [+ idade]) e compara com o catálogo `PESO_REFERENCIA` / `ESTATURA_REFERENCIA`, que reproduz as
tabelas do relatório do projeto (docs/referencias/RELATORIO_FORMULAS_E_ESTIMATIVAS.txt, seções 4 e 5).
Não lê nem imprime valores de entrada ou de outras abas. Não altera a planilha.

Código de saída: 0 = tudo igual à referência; 1 = divergência, fórmula não reconhecida ou layout inesperado; 2 = erro de uso.
Requer `openpyxl` (dependência do projeto).
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass

ABA_PADRAO = "Peso-Alt"

# Peso (kg) = AJ * a + PB * b - c        -> (a, b, c)           — relatório, seções 5.1 e 5.2
PESO_REFERENCIA = {
    ("6-18", "M", "branca"): (0.68, 2.64, 50.08),
    ("6-18", "M", "negra"): (0.59, 2.73, 48.32),
    ("6-18", "F", "branca"): (0.77, 2.47, 50.16),
    ("6-18", "F", "negra"): (0.71, 2.59, 50.43),
    ("19-59", "M", "branca"): (1.19, 3.21, 86.82),
    ("19-59", "M", "negra"): (1.09, 3.14, 83.72),
    ("19-59", "F", "branca"): (1.01, 2.81, 66.04),
    ("19-59", "F", "negra"): (1.24, 2.97, 82.48),
    ("60-80", "M", "branca"): (1.10, 3.07, 75.81),
    ("60-80", "M", "negra"): (0.44, 2.86, 39.21),
    ("60-80", "F", "branca"): (1.09, 2.68, 65.51),
    ("60-80", "F", "negra"): (1.50, 2.58, 84.22),
}

# Estatura (cm) = c + a * AJ - d * idade  -> (c, a, d)           — relatório, seções 4.2, 4.3 e 4.4
ESTATURA_REFERENCIA = {
    ("6-18", "M", "branca"): (40.54, 2.22, 0.0),
    ("6-18", "M", "negra"): (39.60, 2.18, 0.0),
    ("6-18", "F", "branca"): (43.21, 2.15, 0.0),
    ("6-18", "F", "negra"): (46.59, 2.02, 0.0),
    ("19-59", "M", "branca"): (71.85, 1.88, 0.0),
    ("19-59", "M", "negra"): (73.42, 1.79, 0.0),
    ("19-59", "F", "branca"): (70.25, 1.87, 0.06),
    ("19-59", "F", "negra"): (68.10, 1.86, 0.06),
    ("60-80", "M", "branca"): (59.01, 2.08, 0.0),
    ("60-80", "M", "negra"): (95.79, 1.37, 0.0),
    ("60-80", "F", "branca"): (75.00, 1.91, 0.17),
    ("60-80", "F", "negra"): (58.72, 1.96, 0.0),
}

# Amputado: a planilha inverte Chumlea, Roche e Steinbaugh (1985): AJ = (Estatura - c + d * idade) / a
AMPUTADO_REFERENCIA = {"M": (64.19, 0.04, 2.02), "F": (84.88, 0.24, 1.83)}

FONTE_GRUPO = {
    ("estatura", "6-18"): "Chumlea, Guo e Steinbaugh (1994)",
    ("estatura", "19-59"): "Chumlea, Guo e Steinbaugh (1994)",
    ("estatura", "60-80"): "Chumlea e Guo (1992)",
    ("peso", "6-18"): "Chumlea (citação varia: 1988/1994/1998)",
    ("peso", "19-59"): "Chumlea (citação varia: 1987 Ross/1988/1994)",
    ("peso", "60-80"): "Chumlea (citação varia: 1987 Ross/1988/1994)",
}

# Layout esperado da aba: linha -> (faixa, sexo, cor). Colunas: B = peso, F = estatura.
LINHAS = {
    10: ("6-18", "F", "branca"), 11: ("6-18", "F", "negra"), 13: ("6-18", "M", "branca"), 14: ("6-18", "M", "negra"),
    20: ("19-59", "F", "branca"), 21: ("19-59", "F", "negra"), 23: ("19-59", "M", "branca"), 24: ("19-59", "M", "negra"),
    30: ("60-80", "F", "branca"), 31: ("60-80", "F", "negra"), 33: ("60-80", "M", "branca"), 34: ("60-80", "M", "negra"),
}
CABECALHOS = {8: "6-18", 9: "MENINAS", 12: "MENINOS", 18: "19-59", 19: "MULHERES", 22: "HOMENS",
              28: "60-80", 29: "MULHERES", 32: "HOMENS"}
ENTRADAS = {"A3": "IDADE", "A4": "AJ", "A5": "PB"}      # B3 = idade, B4 = AJ, B5 = PB
CELULAS_AMPUTADO = {"M": "B45", "F": "C45"}
ROTULOS_AMPUTADO = {"A41": "IDADE", "A42": "ALT"}        # B41 = idade, B42 = altura estimada

_N = r"(\d+(?:\.\d+)?)"
RE_PESO = re.compile(rf"^=B4\*{_N}\+B5\*{_N}-{_N}$")
RE_ESTATURA = re.compile(rf"^=\({_N}\+{_N}\*B4(?:-{_N}\*B3)?\)/100$")
RE_AMPUTADO = re.compile(rf"^=\({_N}-{_N}\*B41-B42\)/-{_N}$")

OK, DIVERGENTE, NAO_RECONHECIDA, AUSENTE, LAYOUT = "OK", "DIVERGENTE", "FORMULA_NAO_RECONHECIDA", "AUSENTE", "LAYOUT"


class ErroConferencia(Exception):
    pass


@dataclass(frozen=True)
class Item:
    tipo: str            # peso | estatura | amputado | layout
    chave: str           # ex.: "6-18 F branca"
    estado: str
    planilha: str = ""
    referencia: str = ""
    celula: str = ""


def _limpa(valor) -> str:
    return re.sub(r"\s+", "", str(valor)) if valor is not None else ""


def extrair_peso(formula):
    m = RE_PESO.match(_limpa(formula))
    return tuple(float(x) for x in m.groups()) if m else None


def extrair_estatura(formula):
    m = RE_ESTATURA.match(_limpa(formula))
    if not m:
        return None
    c, a, d = m.groups()
    return float(c), float(a), float(d) if d is not None else 0.0


def extrair_amputado(formula):
    m = RE_AMPUTADO.match(_limpa(formula))
    return tuple(float(x) for x in m.groups()) if m else None


def _iguais(a, b) -> bool:
    return len(a) == len(b) and all(math.isclose(x, y, abs_tol=1e-9) for x, y in zip(a, b))


def _texto_peso(t) -> str:
    return f"{t[0]:g}·AJ + {t[1]:g}·PB − {t[2]:g}"


def _texto_estatura(t) -> str:
    return f"{t[0]:g} + {t[1]:g}·AJ" + (f" − {t[2]:g}·idade" if t[2] else "")


def _texto_amputado(t) -> str:
    return f"AJ = (Alt − {t[0]:g} + {t[1]:g}·idade) / {t[2]:g}"


def _rotulo(ws, celula) -> str:
    v = ws[celula].value
    return re.sub(r"\s+", " ", str(v)).strip().upper() if v is not None else ""


def conferir_layout(ws) -> list:
    itens = []
    for celula, esperado in ENTRADAS.items():
        if not _rotulo(ws, celula).startswith(esperado):
            itens.append(Item("layout", celula, LAYOUT, _rotulo(ws, celula) or "(vazio)", esperado, celula))
    for linha, esperado in CABECALHOS.items():
        achado = _rotulo(ws, f"A{linha}") or _rotulo(ws, f"E{linha}")
        if esperado not in achado:
            itens.append(Item("layout", f"A{linha}", LAYOUT, achado or "(vazio)", esperado, f"A{linha}"))
    for linha, (_, _, cor) in LINHAS.items():
        achado = _rotulo(ws, f"A{linha}")
        esperado = "BRANC" if cor == "branca" else "PRET"
        if not achado.startswith(esperado):
            itens.append(Item("layout", f"A{linha}", LAYOUT, achado or "(vazio)", esperado + "…", f"A{linha}"))
    for celula, esperado in ROTULOS_AMPUTADO.items():
        if not _rotulo(ws, celula).startswith(esperado):
            itens.append(Item("layout", celula, LAYOUT, _rotulo(ws, celula) or "(vazio)", esperado, celula))
    return itens


def conferir(ws) -> list:
    """Compara a aba com o catálogo. Retorna a lista de itens (um por equação conferida, mais os problemas de layout)."""
    itens = conferir_layout(ws)
    for linha, (faixa, sexo, cor) in LINHAS.items():
        chave = f"{faixa} {sexo} {cor}"
        for tipo, coluna, extrator, referencia, texto in (
                ("peso", "B", extrair_peso, PESO_REFERENCIA, _texto_peso),
                ("estatura", "F", extrair_estatura, ESTATURA_REFERENCIA, _texto_estatura)):
            celula = f"{coluna}{linha}"
            formula = ws[celula].value
            esperado = referencia[(faixa, sexo, cor)]
            if formula is None:
                itens.append(Item(tipo, chave, AUSENTE, "(vazio)", texto(esperado), celula))
                continue
            achado = extrator(formula)
            if achado is None:
                itens.append(Item(tipo, chave, NAO_RECONHECIDA, "(fórmula em formato não previsto)", texto(esperado), celula))
            elif _iguais(achado, esperado):
                itens.append(Item(tipo, chave, OK, texto(achado), texto(esperado), celula))
            else:
                itens.append(Item(tipo, chave, DIVERGENTE, texto(achado), texto(esperado), celula))
    for sexo, celula in CELULAS_AMPUTADO.items():
        esperado, formula = AMPUTADO_REFERENCIA[sexo], ws[celula].value
        achado = extrair_amputado(formula) if formula is not None else None
        if formula is None:
            itens.append(Item("amputado", sexo, AUSENTE, "(vazio)", _texto_amputado(esperado), celula))
        elif achado is None:
            itens.append(Item("amputado", sexo, NAO_RECONHECIDA, "(fórmula em formato não previsto)", _texto_amputado(esperado), celula))
        else:
            estado = OK if _iguais(achado, esperado) else DIVERGENTE
            itens.append(Item("amputado", sexo, estado, _texto_amputado(achado), _texto_amputado(esperado), celula))
    return itens


def carregar_aba(caminho, aba=ABA_PADRAO):
    try:
        import openpyxl
    except ImportError as exc:
        raise ErroConferencia("o pacote 'openpyxl' não está instalado (python -m pip install -r requirements.txt)") from exc
    try:
        wb = openpyxl.load_workbook(caminho, data_only=False)
    except Exception as exc:     # BadZipFile, InvalidFileException, PermissionError, FileNotFoundError...
        raise ErroConferencia(f"não foi possível abrir a planilha: {type(exc).__name__}") from exc
    if aba not in wb.sheetnames:
        raise ErroConferencia(f"a aba '{aba}' não existe (abas encontradas: {', '.join(wb.sheetnames)})")
    return wb[aba]


def formatar(itens) -> str:
    linhas = ["NutriLab — conferência da aba Peso-Alt contra o catálogo de referência", ""]
    for i in itens:
        if i.estado == OK:
            linhas.append(f"[ OK ] {i.tipo:<9} {i.chave:<16} {i.celula:<4} {i.planilha}")
        else:
            linhas.append(f"[{i.estado}] {i.tipo} {i.chave} ({i.celula}) planilha: {i.planilha} | referência: {i.referencia}")
    problemas = [i for i in itens if i.estado != OK]
    linhas += ["", f"Resumo: {len(itens) - len(problemas)} de {len(itens)} itens iguais à referência; {len(problemas)} com problema."]
    return "\n".join(linhas)


def formatar_markdown(itens) -> str:
    linhas = ["| Tipo | Grupo | Célula | Na planilha | Na referência | Estado |", "|---|---|---|---|---|---|"]
    for i in itens:
        linhas.append(f"| {i.tipo} | {i.chave} | {i.celula} | {i.planilha} | {i.referencia} | {i.estado} |")
    return "\n".join(linhas)


def _saida_tolerante() -> None:
    reconfigurar = getattr(sys.stdout, "reconfigure", None)
    if reconfigurar:
        reconfigurar(errors="replace")


def main(argv=None) -> int:
    _saida_tolerante()
    ap = argparse.ArgumentParser(description="Confere a aba Peso-Alt da planilha de cálculos contra o catálogo de referência.")
    ap.add_argument("planilha", help="caminho do arquivo .xlsx")
    ap.add_argument("--aba", default=ABA_PADRAO)
    ap.add_argument("--markdown", action="store_true", help="imprime a tabela em Markdown")
    args = ap.parse_args(argv)
    try:
        itens = conferir(carregar_aba(args.planilha, args.aba))
    except ErroConferencia as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    print(formatar_markdown(itens) if args.markdown else formatar(itens))
    return 0 if all(i.estado == OK for i in itens) else 1


if __name__ == "__main__":
    sys.exit(main())
