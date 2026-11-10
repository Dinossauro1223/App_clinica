"""Serviço único de banco local do NutriLab (Fase 0).

Responsabilidades
  * UMA fábrica de caminho do banco (`caminho_banco`) para desenvolvimento E para o executável PyInstaller;
  * conexão SQLite (`conectar`), com avisos para locais inseguros (rede, pasta sincronizada na nuvem);
  * backup consistente (API de backup do SQLite) e restauração SEMPRE precedida de cópia de segurança;
  * verificação de integridade.

Compatibilidade: o caminho gravável preserva a convenção de `get_writable_path()` do código legado — a pasta do
.exe quando empacotado e a pasta do projeto em desenvolvimento. O caminho "base" do PyInstaller (`_MEIPASS`,
normalmente `_internal`) NUNCA é usado para dados. Nada aqui apaga, move ou sobrescreve dados existentes sem antes
gerar um backup verificado.

Este módulo NÃO é um mecanismo multiusuário: SQLite local não deve ser compartilhado por rede nem por pasta
sincronizada (ver docs/decisoes/ADR-0001 e ADR-0003). Funciona com Python 3.10+ e usa só a biblioteca padrão.
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
import unicodedata
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

NOME_BANCO_PADRAO = "clinica.db"
VAR_CAMINHO_BANCO = "NUTRILAB_DB_PATH"        # caminho completo do arquivo (desenvolvimento/testes)
VAR_DIRETORIO_DADOS = "NUTRILAB_DATA_DIR"     # pasta onde fica o banco (desenvolvimento/testes)
FUSO_HOSPITAL = "America/Recife"
PASTA_BACKUPS = "backups"
MARCADORES_NUVEM = ("onedrive", "dropbox", "google drive", "googledrive", "meu drive", "my drive",
                    "icloud", "box sync", "nextcloud", "owncloud")


class ErroBanco(Exception):
    """Erro genérico do serviço de banco."""


class IntegridadeError(ErroBanco):
    """Um banco/backup não passou na verificação de integridade."""


class ResultadoRestauracao(NamedTuple):
    destino: Path
    copia_de_seguranca: Path | None


# ----------------------------------------------------------------------------- caminho único

def esta_empacotado() -> bool:
    """True quando executando como executável PyInstaller (sys.frozen)."""
    return bool(getattr(sys, "frozen", False))


def raiz_aplicacao() -> Path:
    """Pasta do .exe (empacotado) ou pasta do projeto (desenvolvimento). Nunca `_internal`/`_MEIPASS`."""
    if esta_empacotado():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def diretorio_dados() -> Path:
    """Pasta gravável dos dados locais. `NUTRILAB_DATA_DIR` tem precedência (desenvolvimento/testes)."""
    env = os.environ.get(VAR_DIRETORIO_DADOS)
    return Path(env).expanduser() if env else raiz_aplicacao()


def caminho_banco(nome: str = NOME_BANCO_PADRAO) -> Path:
    """ÚNICA função que decide onde fica o banco. `NUTRILAB_DB_PATH` (arquivo completo) vence `NUTRILAB_DATA_DIR`."""
    env = os.environ.get(VAR_CAMINHO_BANCO)
    if env:
        return Path(env).expanduser()
    return diretorio_dados() / nome


def _unidade_de_rede_windows(texto: str) -> bool:
    """Best-effort: True se a letra de unidade for de rede (GetDriveTypeW == DRIVE_REMOTE)."""
    if os.name != "nt":
        return False
    try:
        import ctypes

        unidade = os.path.splitdrive(texto)[0]
        return len(unidade) == 2 and ctypes.windll.kernel32.GetDriveTypeW(unidade + "\\") == 4
    except Exception:
        return False


def avisos_local(caminho) -> list:
    """Avisos (heurísticos, por texto) sobre locais inadequados para um SQLite com gravação."""
    texto = str(caminho)
    baixo = texto.lower().replace("\\", "/")
    avisos = []
    if texto.startswith("\\\\") or baixo.startswith("//") or _unidade_de_rede_windows(texto):
        avisos.append("o banco está em local de REDE: SQLite não é seguro para uso compartilhado por rede "
                      "(risco de corrupção). Multiusuário exige API e banco central.")
    if any(m in baixo for m in MARCADORES_NUVEM):
        avisos.append("o banco está em pasta SINCRONIZADA na nuvem (OneDrive/Dropbox/Drive...): a sincronização "
                      "pode copiar o arquivo no meio de uma gravação e corrompê-lo.")
    if "/program files" in baixo:
        avisos.append("o banco está em 'Program Files': essa pasta costuma ser somente leitura para o usuário comum.")
    return avisos


# ----------------------------------------------------------------------------- conexão e integridade

def conectar(caminho=None, *, somente_leitura: bool = False, timeout: float = 5.0,
             foreign_keys: bool | None = None) -> sqlite3.Connection:
    """Abre uma conexão SQLite.

    `foreign_keys=None` NÃO altera o PRAGMA (preserva o comportamento do código legado); True/False o define.
    `somente_leitura=True` nunca cria nem altera o arquivo.
    """
    if str(caminho) == ":memory:":
        conn = sqlite3.connect(":memory:", timeout=timeout)
    else:
        destino = Path(caminho) if caminho is not None else caminho_banco()
        for aviso in avisos_local(destino):
            warnings.warn(aviso, RuntimeWarning, stacklevel=2)
        if somente_leitura:
            if not destino.is_file():
                raise FileNotFoundError(f"banco não encontrado: {destino}")
            conn = sqlite3.connect(f"{destino.resolve().as_uri()}?mode=ro", uri=True, timeout=timeout)
        else:
            destino.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(destino), timeout=timeout)
    if foreign_keys is not None:
        conn.execute(f"PRAGMA foreign_keys = {'ON' if foreign_keys else 'OFF'}")
    return conn


def verificar_integridade(fonte, *, rapida: bool = False):
    """(ok, linhas) — `fonte` é um caminho ou uma conexão já aberta. Nunca lança por arquivo corrompido."""
    aberta_aqui = not isinstance(fonte, sqlite3.Connection)
    try:
        conn = conectar(fonte, somente_leitura=True) if aberta_aqui else fonte
    except (FileNotFoundError, sqlite3.DatabaseError) as exc:
        return False, [f"erro: {type(exc).__name__}"]
    try:
        linhas = [str(r[0]) for r in conn.execute(f"PRAGMA {'quick_check' if rapida else 'integrity_check'}")]
        return linhas == ["ok"], linhas
    except sqlite3.DatabaseError as exc:
        return False, [f"erro: {exc}"]
    finally:
        if aberta_aqui:
            conn.close()


# ----------------------------------------------------------------------------- backup e restauração

def _agora(agora=None) -> datetime:
    if agora is not None:
        return agora
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(FUSO_HOSPITAL))
    except Exception:   # Windows sem o pacote tzdata: Recife está em UTC-3 (sem horário de verão desde 2019)
        return datetime.now(timezone(timedelta(hours=-3)))


def _slug(texto: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-") or "manual"


def _remover_se_existir(caminho: Path) -> None:
    try:
        caminho.unlink()
    except FileNotFoundError:
        pass


def pasta_backups(caminho_db) -> Path:
    return Path(caminho_db).parent / PASTA_BACKUPS


def _copiar_com_api_de_backup(origem: Path, destino: Path) -> None:
    src = conectar(origem, somente_leitura=True)
    try:
        dst = sqlite3.connect(str(destino))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def criar_backup(caminho=None, *, motivo: str = "manual", destino_dir=None, agora=None) -> Path:
    """Cria um backup consistente e VERIFICADO em `<pasta do banco>/backups/` (ignorada pelo .gitignore).

    Nome: `<banco>.backup_AAAAMMDD-HHMMSS_<motivo>.db` (horário de America/Recife). Nunca sobrescreve backup existente.
    """
    origem = Path(caminho) if caminho is not None else caminho_banco()
    if not origem.is_file():
        raise FileNotFoundError(f"banco não encontrado: {origem}")
    pasta = Path(destino_dir) if destino_dir else pasta_backups(origem)
    pasta.mkdir(parents=True, exist_ok=True)
    base = f"{origem.stem}.backup_{_agora(agora).strftime('%Y%m%d-%H%M%S')}_{_slug(motivo)}"
    destino, n = pasta / f"{base}.db", 2
    while destino.exists():
        destino, n = pasta / f"{base}-{n}.db", n + 1
    try:
        _copiar_com_api_de_backup(origem, destino)
    except Exception:
        _remover_se_existir(destino)    # só o arquivo parcial criado agora
        raise
    ok, linhas = verificar_integridade(destino)
    if not ok:
        _remover_se_existir(destino)
        raise IntegridadeError("o backup recém-criado não passou na verificação de integridade: "
                               + "; ".join(linhas[:3]))
    return destino


_RE_CARIMBO = re.compile(r"\.backup_(\d{8}-\d{6})_")


def _chave_backup(arquivo: Path):
    m = _RE_CARIMBO.search(arquivo.name)
    return (m.group(1) if m else "", arquivo.stat().st_mtime_ns, arquivo.name)


def listar_backups(caminho=None, destino_dir=None) -> list:
    """Backups do banco, do mais antigo ao mais recente: data/hora do nome e, em empate, ordem de criação."""
    origem = Path(caminho) if caminho is not None else caminho_banco()
    pasta = Path(destino_dir) if destino_dir else pasta_backups(origem)
    if not pasta.is_dir():
        return []
    return sorted(pasta.glob(f"{origem.stem}.backup_*.db"), key=_chave_backup)


def restaurar_backup(backup, destino=None, *, agora=None) -> ResultadoRestauracao:
    """Restaura `backup` em `destino` (padrão: caminho_banco()).

    Ordem de segurança: (1) valida o backup; (2) se já existe banco no destino, cria cópia de segurança
    `pre-restauracao`; (3) grava a restauração num arquivo temporário e a valida; (4) MOVE (não apaga) os arquivos
    auxiliares -wal/-shm/-journal do banco antigo; (5) troca atomicamente. Em falha, o banco atual fica intacto.
    No Windows, feche o programa antes: a troca falha se o arquivo estiver aberto.
    """
    backup = Path(backup)
    destino = Path(destino) if destino is not None else caminho_banco()
    if not backup.is_file():
        raise FileNotFoundError(f"backup não encontrado: {backup}")
    ok, linhas = verificar_integridade(backup)
    if not ok:
        raise IntegridadeError("o backup informado não passou na verificação de integridade; "
                               "nada foi alterado: " + "; ".join(linhas[:3]))
    destino.parent.mkdir(parents=True, exist_ok=True)
    copia = criar_backup(destino, motivo="pre-restauracao", agora=agora) if destino.exists() else None
    temporario = destino.with_name(destino.name + ".restaurando")
    _remover_se_existir(temporario)     # sobra de uma tentativa anterior (arquivo criado por este módulo)
    try:
        _copiar_com_api_de_backup(backup, temporario)
        ok, linhas = verificar_integridade(temporario)
        if not ok:
            raise IntegridadeError("a cópia restaurada não passou na verificação; o banco atual permanece intacto: "
                                   + "; ".join(linhas[:3]))
        for sufixo in ("-wal", "-shm", "-journal"):
            auxiliar = destino.with_name(destino.name + sufixo)
            if auxiliar.exists():
                os.replace(auxiliar, auxiliar.with_name(auxiliar.name + ".antes-da-restauracao"))
        os.replace(temporario, destino)
    except Exception:
        _remover_se_existir(temporario)
        raise
    return ResultadoRestauracao(destino, copia)
