"""Verificação do ambiente de desenvolvimento do NutriLab (Fase 0).

Uso (na raiz do repositório):
    python tools/verificar_ambiente.py [--requirements requirements.txt] [--estrito]

O que confere:
  * versão do Python (mínimo 3.10; referência 3.12);
  * versões fixadas em requirements.txt x versões instaladas;
  * conflito entre `fpdf2` e os pacotes legados `fpdf`/`pyfpdf` (todos fornecem o módulo `fpdf`);
  * fuso America/Recife (no Windows exige o pacote `tzdata`);
  * disponibilidade do tkinter (apenas aviso: não existe em muitos servidores de CI).

Código de saída: 0 = sem erros; 1 = há erros. Não lê nem imprime dados clínicos.
"""
from __future__ import annotations

import argparse
import importlib.metadata as metadados
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PYTHON_MINIMO = (3, 10)
PYTHON_REFERENCIA = (3, 12)
FUSO_HOSPITAL = "America/Recife"
DISTRIBUICOES_FPDF_LEGADO = ("fpdf", "pyfpdf")


def normalizar_nome(nome: str) -> str:
    """Normaliza nome de distribuição (PEP 503): minúsculas e '-' no lugar de '_', '.' e '-' repetidos."""
    return re.sub(r"[-_.]+", "-", nome).lower()


def ler_requirements(caminho) -> dict:
    """Lê linhas `nome==versão` (ignora comentários, linhas vazias e opções como `-r`)."""
    pins = {}
    for linha in Path(caminho).read_text(encoding="utf-8").splitlines():
        linha = re.sub(r"\s+#.*$", "", linha).strip()
        if not linha or linha.startswith(("#", "-")):
            continue
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*([A-Za-z0-9.+!_-]+)$", linha)
        if m:
            pins[normalizar_nome(m.group(1))] = m.group(2)
    return pins


def versao_instalada(nome: str):
    """Versão instalada da distribuição `nome` ou None."""
    try:
        return metadados.version(nome)
    except metadados.PackageNotFoundError:
        return None


def fuso_disponivel():
    """(ok, mensagem) — confere se o fuso do hospital carrega via zoneinfo."""
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(FUSO_HOSPITAL)
        return True, f"fuso {FUSO_HOSPITAL} disponível"
    except Exception as exc:  # ZoneInfoNotFoundError, ImportError...
        return False, f"fuso {FUSO_HOSPITAL} indisponível ({type(exc).__name__}); instale o pacote 'tzdata'"


def tkinter_disponivel() -> bool:
    try:
        import tkinter  # noqa: F401

        return True
    except Exception:
        return False


@dataclass
class Relatorio:
    erros: list = field(default_factory=list)
    avisos: list = field(default_factory=list)
    infos: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.erros


def verificar(requirements=None, *, estrito=False, versao_python=None, instalada=None,
              fuso=None, tkinter_ok=None) -> Relatorio:
    """Executa as verificações. Parâmetros opcionais existem para permitir testes isolados."""
    rel = Relatorio()
    instalada = instalada or versao_instalada
    fuso = fuso or fuso_disponivel
    tkinter_ok = tkinter_ok if tkinter_ok is not None else tkinter_disponivel

    vp = tuple(versao_python or sys.version_info[:3])
    texto_vp = ".".join(str(x) for x in vp)
    if vp[:2] < PYTHON_MINIMO:
        rel.erros.append(f"Python {texto_vp} é anterior ao mínimo {PYTHON_MINIMO[0]}.{PYTHON_MINIMO[1]}")
    elif vp[:2] != PYTHON_REFERENCIA:
        rel.avisos.append(
            f"Python {texto_vp} difere da referência {PYTHON_REFERENCIA[0]}.{PYTHON_REFERENCIA[1]}; "
            "funciona em tese, mas não foi validado")
    else:
        rel.infos.append(f"Python {texto_vp} (referência)")

    legados = [n for n in DISTRIBUICOES_FPDF_LEGADO if instalada(n)]
    if legados and instalada("fpdf2"):
        rel.erros.append(
            "Conflito de PDF: 'fpdf2' e " + ", ".join(f"'{n}'" for n in legados) +
            " estão instalados juntos e fornecem o mesmo módulo 'fpdf'. "
            "Desinstale os legados (python -m pip uninstall fpdf pyfpdf) e reinstale fpdf2.")
    elif legados:
        rel.erros.append("Apenas o pacote legado " + ", ".join(f"'{n}'" for n in legados) +
                         " está instalado; o projeto exige 'fpdf2'.")

    if requirements is None:
        requirements = Path(__file__).resolve().parent.parent / "requirements.txt"
    requirements = Path(requirements)
    if not requirements.is_file():
        rel.erros.append(f"requirements.txt não encontrado em {requirements}")
    else:
        pins = ler_requirements(requirements)
        if not pins:
            rel.erros.append("requirements.txt não contém nenhuma versão fixada (nome==versão)")
        for nome, fixada in sorted(pins.items()):
            atual = instalada(nome)
            if atual is None:
                rel.erros.append(f"{nome}=={fixada} não está instalado")
            elif atual != fixada:
                msg = f"{nome}: instalado {atual}, fixado {fixada}"
                (rel.erros if estrito else rel.avisos).append(msg)
            else:
                rel.infos.append(f"{nome}=={atual}")

    ok_fuso, msg_fuso = fuso()
    (rel.infos if ok_fuso else rel.erros).append(msg_fuso)

    if tkinter_ok():
        rel.infos.append("tkinter disponível")
    else:
        rel.avisos.append("tkinter indisponível: a interface gráfica não abre neste ambiente "
                          "(esperado em servidores de CI; no Windows reinstale o Python marcando 'tcl/tk').")
    return rel


def formatar(rel: Relatorio) -> str:
    linhas = ["NutriLab — verificação de ambiente", ""]
    linhas += [f"[ERRO ] {m}" for m in rel.erros]
    linhas += [f"[AVISO] {m}" for m in rel.avisos]
    linhas += [f"[ OK  ] {m}" for m in rel.infos]
    linhas += ["", "Resultado: " + ("OK" if rel.ok else "FALHA — corrija os erros acima")]
    return "\n".join(linhas)



def _saida_tolerante() -> None:
    """Evita UnicodeEncodeError ao redirecionar a saída no Windows (páginas de código cp850/cp1252)."""
    reconfigurar = getattr(sys.stdout, "reconfigure", None)
    if reconfigurar:
        reconfigurar(errors="replace")

def main(argv=None) -> int:
    _saida_tolerante()
    ap = argparse.ArgumentParser(description="Verifica o ambiente de desenvolvimento do NutriLab.")
    ap.add_argument("--requirements", default=None, help="caminho do requirements.txt (padrão: o da raiz do repositório)")
    ap.add_argument("--estrito", action="store_true", help="trata versão diferente da fixada como erro")
    args = ap.parse_args(argv)
    rel = verificar(args.requirements, estrito=args.estrito)
    print(formatar(rel))
    return 0 if rel.ok else 1


if __name__ == "__main__":
    sys.exit(main())
