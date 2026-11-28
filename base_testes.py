"""Exportação e abertura de cópias isoladas do banco para testes clínicos.

As operações preservam o banco de produção: a importação cria uma nova cópia em
bases_teste e abre outra instância do NutriLab apontando exclusivamente para ela.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import db_service


class ErroBaseTeste(ValueError):
    """Base inválida ou tentativa de usar o banco de produção como ambiente de teste."""


def _validar_base(caminho: Path) -> None:
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo de banco não encontrado: {caminho}")
    ok, linhas = db_service.verificar_integridade(caminho)
    if not ok:
        raise ErroBaseTeste("O arquivo não passou na verificação de integridade do SQLite: "
                            + "; ".join(linhas[:3]))
    conn = sqlite3.connect(caminho.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        tabelas = {r[0].casefold() for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if "pacientes" not in tabelas:
            raise ErroBaseTeste("O arquivo não contém a tabela de pacientes do NutriLab.")
    finally:
        conn.close()


def _copiar_consistente(origem: Path, destino: Path) -> Path:
    origem = origem.expanduser().resolve()
    destino = destino.expanduser().resolve()
    if origem == destino:
        raise ErroBaseTeste("A origem e o destino não podem ser o mesmo arquivo.")
    if not origem.is_file():
        raise FileNotFoundError(f"Banco de origem não encontrado: {origem}")
    if destino.exists():
        raise FileExistsError(f"O destino já existe e não será sobrescrito: {destino}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(destino.name + ".tmp")
    if temporario.exists():
        raise FileExistsError(f"Arquivo temporário já existe e será preservado: {temporario}")
    fonte = None
    copia = None
    try:
        fonte = sqlite3.connect(origem.as_uri() + "?mode=ro", uri=True, timeout=10)
        copia = sqlite3.connect(str(temporario), timeout=10)
        fonte.backup(copia)
        copia.commit()
        copia.close()
        copia = None
        fonte.close()
        fonte = None
        ok, linhas = db_service.verificar_integridade(temporario)
        if not ok:
            raise ErroBaseTeste("A cópia criada não passou na verificação: " + "; ".join(linhas[:3]))
        _validar_base(temporario)
        os.replace(temporario, destino)
        return destino
    except Exception:
        if copia is not None:
            copia.close()
        if fonte is not None:
            fonte.close()
        try:
            temporario.unlink()
        except OSError:
            pass
        raise


def exportar_base_teste(origem, destino) -> Path:
    """Exporta uma cópia consistente e validada da base completa, sem alterar a origem."""
    origem = Path(origem)
    destino = Path(destino)
    _validar_base(origem)
    return _copiar_consistente(origem, destino)


def importar_base_teste(arquivo, diretorio_dados=None) -> Path:
    """Importa uma base como cópia isolada, nunca como restauração da produção."""
    origem = Path(arquivo).expanduser().resolve()
    _validar_base(origem)
    raiz = Path(diretorio_dados) if diretorio_dados is not None else Path(db_service.caminho_banco()).parent
    pasta = raiz / "bases_teste"
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    destino = pasta / f"{origem.stem}_teste_{carimbo}.db"
    sufixo = 2
    while destino.exists():
        destino = pasta / f"{origem.stem}_teste_{carimbo}_{sufixo}.db"
        sufixo += 1
    return _copiar_consistente(origem, destino)


def abrir_base_teste(caminho, *, banco_producao=None) -> subprocess.Popen:
    """Abre outra instância do NutriLab com NUTRILAB_DB_PATH apontando para a cópia."""
    banco = Path(caminho).expanduser().resolve()
    _validar_base(banco)
    producao_atual = os.environ.get("NUTRILAB_DB_PRODUCAO")
    producao = Path(producao_atual or banco_producao or db_service.caminho_banco()).expanduser().resolve()
    banco_em_uso = Path(db_service.caminho_banco()).expanduser().resolve()
    if banco == producao or banco == banco_em_uso:
        raise ErroBaseTeste("Por segurança, a base de produção ou a base já aberta não pode ser reutilizada como outra instância de testes.")
    raiz = Path(__file__).resolve().parent
    ambiente = os.environ.copy()
    ambiente["NUTRILAB_DB_PRODUCAO"] = str(producao)
    ambiente["NUTRILAB_DB_PATH"] = str(banco)
    ambiente["NUTRILAB_MODO_TESTE"] = "1"
    if getattr(sys, "frozen", False):
        comando = [sys.executable]
    else:
        comando = [sys.executable, str(raiz / "main.py")]
    return subprocess.Popen(comando, cwd=str(raiz), env=ambiente, close_fds=(os.name != "nt"))
