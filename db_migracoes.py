"""Migrações versionadas e reversíveis do banco local do NutriLab (Fase 0).

Princípios
  * As migrações ficam EM CÓDIGO (lista `MIGRACOES`) — assim o PyInstaller as inclui sem alterar o .spec.
  * A versão 1 é a BASELINE: representa o esquema legado (Pacientes, Consultas, Mapa_*...) e não altera nada.
    Em banco legado já existente ela é apenas ADOTADA (registrada); em banco vazio roda `inicializador_legado`.
  * Cada migração roda numa transação própria (`BEGIN IMMEDIATE`): ou entra inteira ou é desfeita.
  * Antes de aplicar/reverter qualquer coisa num banco com conteúdo, é criado um backup VERIFICADO
    (`db_service.criar_backup`). Se o backup falhar, nada é alterado.
  * Cada migração aplicada guarda um checksum; se o código mudar uma migração já aplicada, o sistema recusa seguir
    (`MigracaoAlteradaError`). Um banco migrado por código MAIS NOVO também é recusado (`VersaoMaisNovaError`).
  * Cada instrução de `up`/`down` deve ser UMA instrução SQL (não use `executescript`: ele confirma a transação).

Rollback: (a) `reverter_migracoes` executa os `down` na ordem inversa (se todos existirem); ou (b) restaurar o backup
`pre-migracao-vN` com `db_service.restaurar_backup`. Ambos são cobertos por testes (tests/test_db_migracoes.py).
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import db_service as svc

TABELA_CONTROLE = "schema_migrations"
TABELAS_LEGADO = ("pacientes", "consultas")     # marcadores (comparação sem diferenciar maiúsculas)

_DDL_CONTROLE = f"""CREATE TABLE IF NOT EXISTS {TABELA_CONTROLE} (
    versao INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    aplicada_em TEXT NOT NULL,
    checksum TEXT NOT NULL,
    origem TEXT NOT NULL
)"""


class ErroMigracao(svc.ErroBanco):
    pass


class MigracaoAlteradaError(ErroMigracao):
    pass


class MigracaoIrreversivelError(ErroMigracao):
    pass


class VersaoMaisNovaError(ErroMigracao):
    pass


class ListaMigracoesInvalida(ErroMigracao):
    pass


@dataclass(frozen=True)
class Migracao:
    versao: int
    nome: str
    up: tuple = ()
    down: tuple | None = None      # None = irreversível
    baseline: bool = False

    @property
    def checksum(self) -> str:
        """Identifica a definição `up` (versão, nome e instruções); `down` pode ser corrigido sem invalidar."""
        bruto = "\x1f".join([str(self.versao), self.nome, *self.up])
        return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


# --- v2: Almoxarifado, movimentos com valor histórico e programação por refeição ----------------
_ALMOX_UP = (
"""CREATE TABLE IF NOT EXISTS Almox_Itens (
 id_item INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, unidade TEXT NOT NULL,
 categoria TEXT NOT NULL DEFAULT 'Gêneros alimentícios', valor_unitario REAL, estoque_minimo REAL,
 ativo INTEGER NOT NULL DEFAULT 1, observacao TEXT, criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL,
 UNIQUE(nome COLLATE NOCASE, unidade COLLATE NOCASE))""",
"""CREATE TABLE IF NOT EXISTS Almox_Historico_Preco (
 id_preco INTEGER PRIMARY KEY AUTOINCREMENT, id_item INTEGER NOT NULL, valor_unitario REAL NOT NULL,
 origem TEXT NOT NULL, fonte TEXT, registrado_em TEXT NOT NULL)""",
"CREATE INDEX IF NOT EXISTS ix_almox_preco_item ON Almox_Historico_Preco(id_item, registrado_em)",
"""CREATE TABLE IF NOT EXISTS Almox_Movimentos (
 id_movimento INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, hora TEXT NOT NULL, id_item INTEGER NOT NULL,
 operacao TEXT NOT NULL CHECK(operacao IN ('entrada','saida')),
 motivo TEXT NOT NULL CHECK(motivo IN ('compra','consumo','perda','ajuste','estorno')),
 quantidade REAL NOT NULL CHECK(quantidade > 0), valor_unitario REAL NOT NULL CHECK(valor_unitario >= 0),
 valor_total REAL NOT NULL CHECK(valor_total >= 0), refeicao TEXT, observacao TEXT, usuario TEXT,
 origem TEXT NOT NULL DEFAULT 'manual', id_programacao INTEGER, id_linha_programacao INTEGER,
 id_estorno_de INTEGER UNIQUE, criado_em TEXT NOT NULL, UNIQUE(id_linha_programacao))""",
"CREATE INDEX IF NOT EXISTS ix_almox_mov_data ON Almox_Movimentos(data, motivo, refeicao)",
"CREATE INDEX IF NOT EXISTS ix_almox_mov_item ON Almox_Movimentos(id_item, data)",
"""CREATE TABLE IF NOT EXISTS Almox_Programacoes (
 id_programacao INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, refeicao TEXT NOT NULL,
 porcoes REAL NOT NULL CHECK(porcoes > 0), status TEXT NOT NULL DEFAULT 'rascunho',
 observacao TEXT, criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL)""",
"CREATE INDEX IF NOT EXISTS ix_almox_prog_data ON Almox_Programacoes(data, refeicao, status)",
"""CREATE TABLE IF NOT EXISTS Almox_Programacao_Itens (
 id_linha INTEGER PRIMARY KEY AUTOINCREMENT, id_programacao INTEGER NOT NULL, id_item INTEGER NOT NULL,
 quantidade_por_porcao REAL NOT NULL CHECK(quantidade_por_porcao > 0),
 quantidade_total REAL NOT NULL CHECK(quantidade_total > 0),
 valor_unitario REAL NOT NULL CHECK(valor_unitario >= 0), valor_total REAL NOT NULL CHECK(valor_total >= 0),
 origem TEXT NOT NULL DEFAULT 'manual', referencia_ficha TEXT, versao_ficha TEXT, observacao TEXT)""",
"CREATE INDEX IF NOT EXISTS ix_almox_prog_item ON Almox_Programacao_Itens(id_programacao, id_item)",
"""CREATE TRIGGER IF NOT EXISTS tr_almox_mov_nao_alterar BEFORE UPDATE ON Almox_Movimentos
 BEGIN SELECT RAISE(ABORT, 'Movimento é histórico: registre ajuste ou estorno.'); END""",
"""CREATE TRIGGER IF NOT EXISTS tr_almox_mov_nao_apagar BEFORE DELETE ON Almox_Movimentos
 BEGIN SELECT RAISE(ABORT, 'Movimento não pode ser apagado; registre estorno.'); END""",
"""CREATE TRIGGER IF NOT EXISTS tr_almox_preco_nao_alterar BEFORE UPDATE ON Almox_Historico_Preco
 BEGIN SELECT RAISE(ABORT, 'Histórico de preço não pode ser alterado.'); END""",
"""CREATE TRIGGER IF NOT EXISTS tr_almox_preco_nao_apagar BEFORE DELETE ON Almox_Historico_Preco
 BEGIN SELECT RAISE(ABORT, 'Histórico de preço não pode ser apagado.'); END""",
)
_ALMOX_DOWN = (
 "DROP TRIGGER IF EXISTS tr_almox_preco_nao_apagar",
 "DROP TRIGGER IF EXISTS tr_almox_preco_nao_alterar",
 "DROP TRIGGER IF EXISTS tr_almox_mov_nao_apagar",
 "DROP TRIGGER IF EXISTS tr_almox_mov_nao_alterar",
 "DROP TABLE IF EXISTS Almox_Programacao_Itens",
 "DROP TABLE IF EXISTS Almox_Programacoes",
 "DROP TABLE IF EXISTS Almox_Movimentos",
 "DROP TABLE IF EXISTS Almox_Historico_Preco",
 "DROP TABLE IF EXISTS Almox_Itens",
)

# Lista oficial. NOVAS migrações entram SEMPRE ao final, com versão contígua; nunca editar uma já publicada.
MIGRACOES = (
    Migracao(versao=1, nome="baseline_esquema_legado", up=(), down=None, baseline=True),
    Migracao(versao=2, nome="almoxarifado_custos_programacao", up=_ALMOX_UP, down=_ALMOX_DOWN),
)


@dataclass
class ResultadoMigracao:
    versao_inicial: int
    versao_final: int
    aplicadas: list = field(default_factory=list)
    revertidas: list = field(default_factory=list)
    backup: Path | None = None
    baseline_adotado: bool = False


def validar_lista(migracoes) -> None:
    if not migracoes:
        raise ListaMigracoesInvalida("a lista de migrações está vazia")
    for esperado, m in enumerate(migracoes, start=1):
        if m.versao != esperado:
            raise ListaMigracoesInvalida(
                f"as versões devem ser contíguas a partir de 1; esperado {esperado}, encontrado {m.versao}")
        if m.baseline and (esperado != 1 or m.up):
            raise ListaMigracoesInvalida("somente a versão 1 pode ser baseline, e ela não pode ter instruções `up`")
    if not migracoes[0].baseline:
        raise ListaMigracoesInvalida("a versão 1 deve ser a baseline do esquema legado")


# ----------------------------------------------------------------------------- estado

def _tabelas(conn) -> set:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def _aplicadas(conn) -> dict:
    if TABELA_CONTROLE not in _tabelas(conn):
        return {}
    return {v: (nome, checksum) for v, nome, checksum in conn.execute(
        f"SELECT versao, nome, checksum FROM {TABELA_CONTROLE} ORDER BY versao")}


def versao_atual(conn) -> int:
    """Maior versão registrada (0 se o banco ainda não tem controle de migrações)."""
    return max(_aplicadas(conn), default=0)


def _conferir_aplicadas(conn, migracoes) -> int:
    aplicadas, conhecidas = _aplicadas(conn), {m.versao: m for m in migracoes}
    for versao, (nome, checksum) in aplicadas.items():
        if versao not in conhecidas:
            raise VersaoMaisNovaError(
                f"o banco está na versão {max(aplicadas)} e este programa só conhece até a {max(conhecidas)}; "
                "atualize o programa — não rode versão antiga sobre banco migrado por versão nova")
        if conhecidas[versao].checksum != checksum:
            raise MigracaoAlteradaError(
                f"a migração {versao} ({nome}) foi alterada depois de aplicada; "
                "crie uma NOVA migração em vez de editar a antiga")
    return max(aplicadas, default=0)


def _executar_transacao(conn, instrucoes, descricao: str) -> None:
    """Executa as instruções numa transação; em erro, desfaz tudo e lança ErroMigracao."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        for instrucao in instrucoes:
            conn.execute(instrucao) if isinstance(instrucao, str) else instrucao(conn)
        conn.execute("COMMIT")
    except Exception as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise ErroMigracao(f"{descricao} falhou e foi desfeita: {type(exc).__name__}: {exc}") from exc


def _abrir(caminho) -> sqlite3.Connection:
    conn = svc.conectar(caminho)
    conn.isolation_level = None     # transações controladas explicitamente
    return conn


def _precisa_de_backup(caminho, tabelas_antes) -> bool:
    return str(caminho) != ":memory:" and Path(caminho).exists() and bool(tabelas_antes - {TABELA_CONTROLE})


# ----------------------------------------------------------------------------- aplicar / reverter

def aplicar_migracoes(caminho, migracoes=MIGRACOES, *, alvo: int | None = None, inicializador_legado=None,
                      backup: bool = True, agora=None) -> ResultadoMigracao:
    """Leva o banco até a versão `alvo` (padrão: a última).

    `inicializador_legado(conn)`: função chamada UMA vez, dentro da transação da baseline, quando o banco não tem o
    esquema legado (banco novo). Deve usar só `conn.execute` (nunca `executescript`) e ser idempotente
    (CREATE TABLE IF NOT EXISTS). Em banco legado existente ela NÃO é chamada.
    """
    validar_lista(migracoes)
    alvo = migracoes[-1].versao if alvo is None else alvo
    if not 1 <= alvo <= migracoes[-1].versao:
        raise ListaMigracoesInvalida(f"alvo {alvo} fora do intervalo 1..{migracoes[-1].versao}")
    conn = _abrir(caminho)
    try:
        tabelas_antes = _tabelas(conn)
        inicial = _conferir_aplicadas(conn, migracoes)
        pendentes = [m for m in migracoes if inicial < m.versao <= alvo]
        resultado = ResultadoMigracao(inicial, inicial)
        if not pendentes:
            return resultado
        if backup and _precisa_de_backup(caminho, tabelas_antes):
            resultado.backup = svc.criar_backup(caminho, motivo=f"pre-migracao-v{pendentes[-1].versao}", agora=agora)
        _executar_transacao(conn, [_DDL_CONTROLE], "criação da tabela de controle de migrações")
        tem_legado = any(t.lower() in TABELAS_LEGADO for t in tabelas_antes)
        for m in pendentes:
            origem = "migracao"
            instrucoes = list(m.up)
            if m.baseline:
                origem = "adotada-legado" if tem_legado else "banco-novo"
                resultado.baseline_adotado = tem_legado
                if not tem_legado and inicializador_legado is not None:
                    instrucoes = [inicializador_legado]
            instrucoes.append(_registro(m, origem, agora))
            _executar_transacao(conn, instrucoes, f"migração {m.versao} ({m.nome})")
            resultado.aplicadas.append(m.versao)
        resultado.versao_final = versao_atual(conn)
        return resultado
    finally:
        conn.close()


def _registro(m: Migracao, origem: str, agora):
    carimbo = svc._agora(agora).isoformat(timespec="seconds")

    def inserir(conn):
        conn.execute(f"INSERT INTO {TABELA_CONTROLE} (versao, nome, aplicada_em, checksum, origem) "
                     "VALUES (?, ?, ?, ?, ?)", (m.versao, m.nome, carimbo, m.checksum, origem))
    return inserir


def reverter_migracoes(caminho, para_versao: int, migracoes=MIGRACOES, *, backup: bool = True,
                       agora=None) -> ResultadoMigracao:
    """Reverte, em ordem inversa, as migrações acima de `para_versao` usando os scripts `down`.

    A baseline (versão 1) é irreversível; todas as migrações a reverter precisam ter `down`, caso contrário nada é
    alterado. Um backup `pre-reversao-para-vN` é criado antes.
    """
    validar_lista(migracoes)
    if para_versao < 1:
        raise MigracaoIrreversivelError("a baseline (versão 1) não pode ser revertida; para voltar a um estado "
                                        "anterior à baseline, restaure um backup")
    conn = _abrir(caminho)
    try:
        tabelas_antes = _tabelas(conn)
        atual = _conferir_aplicadas(conn, migracoes)
        resultado = ResultadoMigracao(atual, atual)
        a_reverter = [m for m in reversed(migracoes) if para_versao < m.versao <= atual]
        if not a_reverter:
            return resultado
        sem_down = [m.versao for m in a_reverter if m.down is None]
        if sem_down:
            raise MigracaoIrreversivelError(f"as migrações {sem_down} não têm script de reversão; nada foi alterado")
        if backup and _precisa_de_backup(caminho, tabelas_antes):
            resultado.backup = svc.criar_backup(caminho, motivo=f"pre-reversao-para-v{para_versao}", agora=agora)
        for m in a_reverter:
            remover = f"DELETE FROM {TABELA_CONTROLE} WHERE versao = {int(m.versao)}"
            _executar_transacao(conn, [*m.down, remover], f"reversão da migração {m.versao} ({m.nome})")
            resultado.revertidas.append(m.versao)
        resultado.versao_final = versao_atual(conn)
        return resultado
    finally:
        conn.close()
