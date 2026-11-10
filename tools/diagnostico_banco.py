"""Diagnóstico SOMENTE-LEITURA dos bancos SQLite do NutriLab (Fase 0).

Uso:
    python tools/diagnostico_banco.py [PASTA_OU_ARQUIVO ...] [--nome clinica.db] [--todos] [--json saida.json]

Procura arquivos de banco sob as pastas indicadas (padrão: pasta atual), abre cada um em modo SOMENTE LEITURA e informa
tamanho, data de modificação, versão do esquema (tabela schema_migrations), verificação rápida de integridade e, para
cada tabela, apenas o NÚMERO de linhas. Nenhum conteúdo de linha é lido, impresso ou gravado.

Serve, principalmente, para achar a "DIVISÃO DE BANCO" do executável PyInstaller: o código legado usa
`get_writable_path()` (pasta do .exe) numa parte e `get_base_path()` (pode ser `_internal`) em outra, então
`clinica.db` pode existir em DUAS pastas, cada uma com parte dos dados. Esta ferramenta NÃO funde, move nem apaga nada.

Código de saída: 0 = sem alertas; 1 = divisão de banco, erro de leitura ou integridade reprovada.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:      # permite `python tools/diagnostico_banco.py`
    sys.path.insert(0, str(_RAIZ))

import db_service as svc  # noqa: E402

PASTAS_IGNORADAS = {".git", ".venv", "venv", "env", "node_modules", "__pycache__", ".pytest_cache"}
EXTENSOES_BANCO = (".db", ".sqlite", ".sqlite3")


def procurar_bancos(raizes, nome: str = svc.NOME_BANCO_PADRAO, todos: bool = False) -> list:
    achados, alvo = set(), nome.lower()
    for raiz in raizes:
        raiz = Path(raiz)
        if raiz.is_file():
            achados.add(raiz)
            continue
        for pasta, subpastas, arquivos in os.walk(raiz):
            subpastas[:] = [d for d in subpastas if d not in PASTAS_IGNORADAS]
            for arquivo in arquivos:
                baixo = arquivo.lower()
                if baixo == alvo or (todos and baixo.endswith(EXTENSOES_BANCO)):
                    achados.add(Path(pasta) / arquivo)
    return sorted(achados)


def _aspas(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def inspecionar(caminho) -> dict:
    """Metadados e contagem de linhas por tabela. Não lê conteúdo de linhas."""
    caminho = Path(caminho)
    info = {"caminho": str(caminho), "tamanho_bytes": None, "modificado_em": None, "versao_esquema": None,
            "integridade_rapida": None, "tabelas": {}, "erro": None}
    try:
        st = caminho.stat()
        info["tamanho_bytes"] = st.st_size
        info["modificado_em"] = datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
        conn = svc.conectar(caminho, somente_leitura=True)
    except (OSError, sqlite3.Error) as exc:
        info["erro"] = type(exc).__name__
        return info
    try:
        ok, _ = svc.verificar_integridade(conn, rapida=True)
        info["integridade_rapida"] = "ok" if ok else "FALHOU"
        nomes = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        for nome in nomes:
            info["tabelas"][nome] = conn.execute(f"SELECT COUNT(*) FROM {_aspas(nome)}").fetchone()[0]
        if "schema_migrations" in nomes:
            info["versao_esquema"] = conn.execute("SELECT MAX(versao) FROM schema_migrations").fetchone()[0]
    except sqlite3.Error as exc:
        info["erro"] = type(exc).__name__
        info["integridade_rapida"] = info["integridade_rapida"] or "FALHOU"
    finally:
        conn.close()
    return info


def _resumo(info: dict) -> str:
    return (f"{len(info['tabelas'])} tabelas, {sum(info['tabelas'].values())} linhas, "
            f"modificado em {info['modificado_em']}")


def detectar_divisao(inspecoes) -> list:
    """Alertas para o mesmo nome de banco existindo em pastas diferentes."""
    grupos = {}
    for info in inspecoes:
        grupos.setdefault(Path(info["caminho"]).name.lower(), []).append(info)
    avisos = []
    for nome, lista in sorted(grupos.items()):
        pastas = {str(Path(i["caminho"]).resolve().parent) for i in lista}
        if len(pastas) < 2:
            continue
        msg = (f"DIVISÃO DE BANCO: {len(lista)} arquivos '{nome}' em pastas diferentes — "
               + "; ".join(f"{i['caminho']} ({_resumo(i)})" for i in lista) + ". ")
        if any("_internal" in Path(i["caminho"]).parts for i in lista):
            msg += ("Um deles está em '_internal' (pasta interna do PyInstaller): o código legado pode ter gravado "
                    "parte dos dados ali. ")
        msg += ("NÃO apague nem copie um sobre o outro: gere backup de TODOS, compare o conteúdo com o responsável "
                "e só então decida qual é o oficial.")
        avisos.append(msg)
    return avisos


def formatar(inspecoes, avisos) -> str:
    linhas = ["NutriLab — diagnóstico de bancos (somente leitura; contagens, sem conteúdo)", ""]
    if not inspecoes:
        linhas.append("Nenhum banco encontrado nas pastas informadas.")
    for i in inspecoes:
        linhas.append(f"* {i['caminho']}")
        if i["erro"]:
            linhas.append(f"    ERRO ao ler: {i['erro']}")
            continue
        linhas.append(f"    tamanho {i['tamanho_bytes']} bytes | modificado em {i['modificado_em']} | "
                      f"integridade rápida: {i['integridade_rapida']} | "
                      f"versão do esquema: {i['versao_esquema'] if i['versao_esquema'] is not None else 'sem controle'}")
        for tabela, n in i["tabelas"].items():
            linhas.append(f"    - {tabela}: {n} linhas")
    if avisos:
        linhas += ["", *[f"[ALERTA] {a}" for a in avisos]]
    return "\n".join(linhas)



def _saida_tolerante() -> None:
    """Evita UnicodeEncodeError ao redirecionar a saída no Windows (páginas de código cp850/cp1252)."""
    reconfigurar = getattr(sys.stdout, "reconfigure", None)
    if reconfigurar:
        reconfigurar(errors="replace")

def main(argv=None) -> int:
    _saida_tolerante()
    ap = argparse.ArgumentParser(description="Diagnóstico somente-leitura dos bancos SQLite do NutriLab.")
    ap.add_argument("caminhos", nargs="*", default=["."], help="pastas (ou arquivos) a examinar; padrão: pasta atual")
    ap.add_argument("--nome", default=svc.NOME_BANCO_PADRAO, help="nome do arquivo de banco (padrão: clinica.db)")
    ap.add_argument("--todos", action="store_true", help="considerar qualquer .db/.sqlite/.sqlite3")
    ap.add_argument("--json", dest="json_saida", default=None, help="grava o relatório em JSON")
    args = ap.parse_args(argv)
    inspecoes = [inspecionar(p) for p in procurar_bancos(args.caminhos, args.nome, args.todos)]
    avisos = detectar_divisao(inspecoes)
    print(formatar(inspecoes, avisos))
    if args.json_saida:
        Path(args.json_saida).write_text(
            json.dumps({"bancos": inspecoes, "alertas": avisos}, ensure_ascii=False, indent=2), encoding="utf-8")
    problema = bool(avisos) or any(i["erro"] or i["integridade_rapida"] == "FALHOU" for i in inspecoes)
    return 1 if problema else 0


if __name__ == "__main__":
    sys.exit(main())
