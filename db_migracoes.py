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


# --- v2: condutas de alta (módulo condutas_alta.py) -------------------------------------------------------------------
# Documento de orientações de alta por paciente + uma linha por conduta decidida pela nutricionista (confirmada ou
# "não se aplica"), com texto, lista de conferência e referências COPIADOS no momento da decisão (o catálogo pode mudar
# depois). Depois de `entregue`, o documento e os itens ficam imutáveis (gatilhos abaixo); corrigir = nova versão
# (`substitui_id_doc`). Sem FOREIGN KEY para Pacientes: essa tabela pertence ao esquema legado.
_CONDUTAS_ALTA_UP = (
    """CREATE TABLE IF NOT EXISTS Condutas_Alta_Docs (
        id_doc INTEGER PRIMARY KEY AUTOINCREMENT,
        id_paciente INTEGER NOT NULL,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'rascunho' CHECK (status IN ('rascunho', 'entregue')),
        entregue_em TEXT,
        nutricionista TEXT,
        crn TEXT,
        recado TEXT,
        substitui_id_doc INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS Condutas_Alta_Itens (
        id_item INTEGER PRIMARY KEY AUTOINCREMENT,
        id_doc INTEGER NOT NULL REFERENCES Condutas_Alta_Docs (id_doc),
        codigo TEXT NOT NULL,
        versao_catalogo TEXT,
        decisao TEXT NOT NULL CHECK (decisao IN ('confirmada', 'nao_se_aplica')),
        origem TEXT NOT NULL DEFAULT 'regra' CHECK (origem IN ('regra', 'manual')),
        titulo TEXT NOT NULL,
        titulo_paciente TEXT,
        texto_paciente TEXT,
        texto_profissional TEXT,
        conferir TEXT,
        referencias TEXT,
        editado INTEGER NOT NULL DEFAULT 0,
        justificativa TEXT,
        decidido_em TEXT NOT NULL,
        UNIQUE (id_doc, codigo)
    )""",
    "CREATE INDEX IF NOT EXISTS ix_condutas_alta_docs_pac ON Condutas_Alta_Docs (id_paciente, status)",
    "CREATE INDEX IF NOT EXISTS ix_condutas_alta_itens_doc ON Condutas_Alta_Itens (id_doc)",
    """CREATE TRIGGER IF NOT EXISTS tr_condutas_alta_itens_ins_imutavel BEFORE INSERT ON Condutas_Alta_Itens
       WHEN (SELECT status FROM Condutas_Alta_Docs WHERE id_doc = NEW.id_doc) = 'entregue'
       BEGIN SELECT RAISE(ABORT, 'Documento de alta já entregue: crie uma nova versão em vez de alterar.'); END""",
    """CREATE TRIGGER IF NOT EXISTS tr_condutas_alta_itens_upd_imutavel BEFORE UPDATE ON Condutas_Alta_Itens
       WHEN (SELECT status FROM Condutas_Alta_Docs WHERE id_doc = OLD.id_doc) = 'entregue'
       BEGIN SELECT RAISE(ABORT, 'Documento de alta já entregue: crie uma nova versão em vez de alterar.'); END""",
    """CREATE TRIGGER IF NOT EXISTS tr_condutas_alta_itens_del_imutavel BEFORE DELETE ON Condutas_Alta_Itens
       WHEN (SELECT status FROM Condutas_Alta_Docs WHERE id_doc = OLD.id_doc) = 'entregue'
       BEGIN SELECT RAISE(ABORT, 'Documento de alta já entregue: não é possível apagar itens.'); END""",
    """CREATE TRIGGER IF NOT EXISTS tr_condutas_alta_docs_upd_imutavel BEFORE UPDATE ON Condutas_Alta_Docs
       WHEN OLD.status = 'entregue'
       BEGIN SELECT RAISE(ABORT, 'Documento de alta já entregue: crie uma nova versão em vez de alterar.'); END""",
    """CREATE TRIGGER IF NOT EXISTS tr_condutas_alta_docs_del_imutavel BEFORE DELETE ON Condutas_Alta_Docs
       WHEN OLD.status = 'entregue'
       BEGIN SELECT RAISE(ABORT, 'Documento de alta já entregue: não é possível apagar.'); END""",
)
# Reversão (sempre com backup `pre-reversao-para-v1` feito antes): remove as tabelas; documentos entregues só existirão no backup.
_CONDUTAS_ALTA_DOWN = (
    "DROP TRIGGER IF EXISTS tr_condutas_alta_docs_del_imutavel",
    "DROP TRIGGER IF EXISTS tr_condutas_alta_docs_upd_imutavel",
    "DROP TRIGGER IF EXISTS tr_condutas_alta_itens_del_imutavel",
    "DROP TRIGGER IF EXISTS tr_condutas_alta_itens_upd_imutavel",
    "DROP TRIGGER IF EXISTS tr_condutas_alta_itens_ins_imutavel",
    "DROP TABLE IF EXISTS Condutas_Alta_Itens",
    "DROP TABLE IF EXISTS Condutas_Alta_Docs",
)

# --- v3: travas contra substituição, que faltavam na v2 (revisão de QA de 19/11/2026) -----------------------------------
# No SQLite, `REPLACE INTO`, `INSERT OR REPLACE` e `UPDATE OR REPLACE` apagam a linha em conflito SEM disparar o gatilho de
# DELETE (isso só acontece com `recursive_triggers` ligado, e o padrão é desligado). Assim, um documento entregue podia ser
# trocado por um rascunho, ou um item entregue por outro, sem erro. Também era possível mover um item de rascunho para
# dentro de um documento entregue. Cada trava barra a operação ANTES de ela acontecer, em qualquer conexão (não depende de
# o programa ligar `recursive_triggers`). Continua valendo o limite da v2: quem tem acesso direto ao arquivo pode apagar os gatilhos.
_STATUS_DO_ITEM = ("(SELECT d.status FROM Condutas_Alta_Itens i JOIN Condutas_Alta_Docs d ON d.id_doc = i.id_doc "
                   "WHERE i.id_item = NEW.id_item)")
_CONDUTAS_ALTA_TRAVAS_UP = (
    """CREATE TRIGGER IF NOT EXISTS tr_condutas_alta_docs_ins_imutavel BEFORE INSERT ON Condutas_Alta_Docs
       WHEN (SELECT status FROM Condutas_Alta_Docs WHERE id_doc = NEW.id_doc) = 'entregue'
       BEGIN SELECT RAISE(ABORT, 'Documento de alta já entregue: não é possível substituir.'); END""",
    """CREATE TRIGGER IF NOT EXISTS tr_condutas_alta_docs_id_imutavel BEFORE UPDATE OF id_doc ON Condutas_Alta_Docs
       WHEN NEW.id_doc <> OLD.id_doc
        AND (SELECT status FROM Condutas_Alta_Docs WHERE id_doc = NEW.id_doc) = 'entregue'
       BEGIN SELECT RAISE(ABORT, 'Documento de alta já entregue: não é possível substituir.'); END""",
    """CREATE TRIGGER IF NOT EXISTS tr_condutas_alta_itens_mover_imutavel BEFORE UPDATE OF id_doc ON Condutas_Alta_Itens
       WHEN (SELECT status FROM Condutas_Alta_Docs WHERE id_doc = NEW.id_doc) = 'entregue'
       BEGIN SELECT RAISE(ABORT, 'Documento de alta já entregue: crie uma nova versão em vez de alterar.'); END""",
    f"""CREATE TRIGGER IF NOT EXISTS tr_condutas_alta_itens_ins_pk_imutavel BEFORE INSERT ON Condutas_Alta_Itens
       WHEN {_STATUS_DO_ITEM} = 'entregue'
       BEGIN SELECT RAISE(ABORT, 'Documento de alta já entregue: não é possível substituir itens.'); END""",
    f"""CREATE TRIGGER IF NOT EXISTS tr_condutas_alta_itens_id_imutavel BEFORE UPDATE OF id_item ON Condutas_Alta_Itens
       WHEN NEW.id_item <> OLD.id_item AND {_STATUS_DO_ITEM} = 'entregue'
       BEGIN SELECT RAISE(ABORT, 'Documento de alta já entregue: não é possível substituir itens.'); END""",
)
_CONDUTAS_ALTA_TRAVAS_DOWN = (
    "DROP TRIGGER IF EXISTS tr_condutas_alta_itens_id_imutavel",
    "DROP TRIGGER IF EXISTS tr_condutas_alta_itens_ins_pk_imutavel",
    "DROP TRIGGER IF EXISTS tr_condutas_alta_itens_mover_imutavel",
    "DROP TRIGGER IF EXISTS tr_condutas_alta_docs_id_imutavel",
    "DROP TRIGGER IF EXISTS tr_condutas_alta_docs_ins_imutavel",
)

# Lista oficial. NOVAS migrações entram SEMPRE ao final, com versão contígua; nunca editar uma já publicada.
# --- v4: prontuário nutricional (PEP), usuários e evoluções imutáveis ---
_PEP_UP = (
    """CREATE TABLE IF NOT EXISTS Pep_Config (
        chave TEXT PRIMARY KEY,
        valor TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS Pep_Usuarios (
        id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
        login TEXT NOT NULL UNIQUE COLLATE NOCASE,
        nome_completo TEXT NOT NULL,
        crn TEXT NOT NULL,
        salt TEXT NOT NULL,
        senha_hash TEXT NOT NULL,
        assinatura BLOB,
        ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
        criado_em TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS Pep_Evolucoes (
        id_evolucao INTEGER PRIMARY KEY AUTOINCREMENT,
        id_paciente INTEGER NOT NULL,
        paciente_nome TEXT NOT NULL,
        data_evolucao TEXT NOT NULL,
        cabecalho_json TEXT NOT NULL,
        texto TEXT NOT NULL,
        id_usuario INTEGER NOT NULL,
        assinante_nome TEXT NOT NULL,
        assinante_crn TEXT NOT NULL,
        criada_em TEXT NOT NULL,
        adendo_de INTEGER
    )""",
    "CREATE INDEX IF NOT EXISTS ix_pep_evolucoes_paciente_data ON Pep_Evolucoes (id_paciente, data_evolucao, id_evolucao)",
    """CREATE TRIGGER IF NOT EXISTS tr_pep_evolucoes_update_imutavel BEFORE UPDATE ON Pep_Evolucoes
       BEGIN SELECT RAISE(ABORT, 'Evolução PEP imutável: registre um adendo.'); END""",
    """CREATE TRIGGER IF NOT EXISTS tr_pep_evolucoes_delete_imutavel BEFORE DELETE ON Pep_Evolucoes
       BEGIN SELECT RAISE(ABORT, 'Evolução PEP imutável: não é permitido apagar.'); END""",
)
_PEP_DOWN = (
    "DROP TRIGGER IF EXISTS tr_pep_evolucoes_delete_imutavel",
    "DROP TRIGGER IF EXISTS tr_pep_evolucoes_update_imutavel",
    "DROP INDEX IF EXISTS ix_pep_evolucoes_paciente_data",
    "DROP TABLE IF EXISTS Pep_Evolucoes",
    "DROP TABLE IF EXISTS Pep_Usuarios",
    "DROP TABLE IF EXISTS Pep_Config",
)

MIGRACOES = (
    Migracao(versao=1, nome="baseline_esquema_legado", up=(), down=None, baseline=True),
    Migracao(versao=2, nome="condutas_alta", up=_CONDUTAS_ALTA_UP, down=_CONDUTAS_ALTA_DOWN),
    Migracao(versao=3, nome="condutas_alta_travas_contra_substituicao", up=_CONDUTAS_ALTA_TRAVAS_UP,
             down=_CONDUTAS_ALTA_TRAVAS_DOWN),
    Migracao(versao=4, nome="pep_evolucoes_immutability", up=_PEP_UP, down=_PEP_DOWN),
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
