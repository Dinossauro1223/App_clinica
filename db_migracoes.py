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
        instrucoes = [x if isinstance(x, str) else "callable:%s.%s" % (getattr(x, "__module__", ""), getattr(x, "__qualname__", type(x).__name__)) for x in self.up]
        bruto = "\x1f".join([str(self.versao), self.nome, *instrucoes])
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


# --- v4: evolução ambulatorial estruturada, biblioteca DOCX, relações de exames e triagens ----------------------------
_AMBULATORIAL_UP = (
    """CREATE TABLE IF NOT EXISTS Consulta_Dados_Estruturados (
        id_consulta INTEGER PRIMARY KEY,
        anamnese_guiada_json TEXT NOT NULL DEFAULT '{}',
        recordatorio_24h TEXT,
        antropometria_json TEXT NOT NULL DEFAULT '{}',
        necessidades_json TEXT NOT NULL DEFAULT '{}',
        criado_em TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS Consulta_Medicamentos (
        id_medicamento INTEGER PRIMARY KEY AUTOINCREMENT,
        id_consulta INTEGER NOT NULL,
        nome TEXT NOT NULL,
        dose TEXT,
        via TEXT,
        frequencia TEXT,
        indicacao TEXT,
        observacao TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS Consulta_Metas (
        id_meta INTEGER PRIMARY KEY AUTOINCREMENT,
        id_consulta INTEGER NOT NULL,
        descricao TEXT NOT NULL,
        indicador TEXT,
        prazo TEXT,
        status TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS Recomendacoes_Docs (
        id_recomendacao INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        caso_clinico TEXT NOT NULL,
        tags TEXT,
        nome_original TEXT NOT NULL,
        arquivo_relativo TEXT NOT NULL UNIQUE,
        tamanho_bytes INTEGER NOT NULL,
        sha256 TEXT NOT NULL,
        ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS Consulta_Recomendacoes (
        id_associacao INTEGER PRIMARY KEY AUTOINCREMENT,
        id_consulta INTEGER NOT NULL,
        id_paciente INTEGER NOT NULL,
        id_recomendacao INTEGER NOT NULL REFERENCES Recomendacoes_Docs(id_recomendacao),
        conduta_relacionada TEXT,
        observacao TEXT,
        associado_em TEXT NOT NULL,
        UNIQUE (id_consulta, id_recomendacao)
    )""",
    """CREATE TABLE IF NOT EXISTS Exames_Associacoes (
        id_associacao INTEGER PRIMARY KEY AUTOINCREMENT,
        id_exame TEXT NOT NULL,
        tipo_associacao TEXT NOT NULL CHECK (tipo_associacao IN ('exame_recomendado','diagnostico_clinico','diagnostico_nutricional')),
        valor_relacionado TEXT NOT NULL,
        justificativa TEXT,
        fonte TEXT,
        ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
        criado_em TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS Consulta_Triagens (
        id_triagem INTEGER PRIMARY KEY AUTOINCREMENT,
        id_consulta INTEGER NOT NULL,
        instrumento TEXT NOT NULL,
        versao TEXT,
        pontuacao_total REAL,
        classificacao TEXT,
        resultado_json TEXT NOT NULL,
        origem TEXT,
        criado_em TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS ix_consulta_medicamentos_consulta ON Consulta_Medicamentos(id_consulta)",
    "CREATE INDEX IF NOT EXISTS ix_consulta_metas_consulta ON Consulta_Metas(id_consulta)",
    "CREATE INDEX IF NOT EXISTS ix_recomendacoes_docs_ativas ON Recomendacoes_Docs(ativo,titulo)",
    "CREATE INDEX IF NOT EXISTS ix_consulta_recomendacoes_consulta ON Consulta_Recomendacoes(id_consulta,id_paciente)",
    "CREATE INDEX IF NOT EXISTS ix_exames_associacoes_exame ON Exames_Associacoes(id_exame,ativo)",
    "CREATE INDEX IF NOT EXISTS ix_consulta_triagens_consulta ON Consulta_Triagens(id_consulta,instrumento)",
)
_AMBULATORIAL_DOWN = (
    "DROP INDEX IF EXISTS ix_consulta_triagens_consulta",
    "DROP INDEX IF EXISTS ix_exames_associacoes_exame",
    "DROP INDEX IF EXISTS ix_consulta_recomendacoes_consulta",
    "DROP INDEX IF EXISTS ix_recomendacoes_docs_ativas",
    "DROP INDEX IF EXISTS ix_consulta_metas_consulta",
    "DROP INDEX IF EXISTS ix_consulta_medicamentos_consulta",
    "DROP TABLE IF EXISTS Consulta_Triagens",
    "DROP TABLE IF EXISTS Exames_Associacoes",
    "DROP TABLE IF EXISTS Consulta_Recomendacoes",
    "DROP TABLE IF EXISTS Recomendacoes_Docs",
    "DROP TABLE IF EXISTS Consulta_Metas",
    "DROP TABLE IF EXISTS Consulta_Medicamentos",
    "DROP TABLE IF EXISTS Consulta_Dados_Estruturados",
)

# --- v5: Almoxarifado, movimentos com valor histórico e programação por refeição ----------------
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

# --- v6: prontuário eletrônico nutricional, usuários e evoluções imutáveis ----------------
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
        id_usuario INTEGER NOT NULL REFERENCES Pep_Usuarios(id_usuario),
        assinante_nome TEXT NOT NULL,
        assinante_crn TEXT NOT NULL,
        criada_em TEXT NOT NULL,
        adendo_de INTEGER REFERENCES Pep_Evolucoes(id_evolucao)
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

# --- v7: rascunhos, equipe clínica e trilha de revisão da evolução nutricional ----------------
_PEP_EVOLUCAO_UP = (
    """CREATE TABLE IF NOT EXISTS Pep_Equipe (
        id_membro INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        funcao TEXT NOT NULL CHECK (funcao IN ('estagiario', 'nutricionista')),
        crn TEXT,
        crn_conferido INTEGER NOT NULL DEFAULT 0 CHECK (crn_conferido IN (0, 1)),
        id_usuario INTEGER REFERENCES Pep_Usuarios(id_usuario),
        ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
        criado_em TEXT NOT NULL,
        CHECK ((funcao = 'estagiario' AND crn IS NULL AND crn_conferido = 0)
            OR (funcao = 'nutricionista' AND crn IS NOT NULL))
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_pep_equipe_usuario ON Pep_Equipe(id_usuario) WHERE id_usuario IS NOT NULL",
    """CREATE TABLE IF NOT EXISTS Pep_Rascunhos (
        id_rascunho INTEGER PRIMARY KEY AUTOINCREMENT,
        id_paciente INTEGER NOT NULL,
        paciente_nome TEXT NOT NULL,
        data_evolucao TEXT NOT NULL,
        dados_json TEXT NOT NULL,
        id_elaborador INTEGER NOT NULL REFERENCES Pep_Equipe(id_membro),
        status TEXT NOT NULL DEFAULT 'rascunho' CHECK (status IN ('rascunho', 'em_revisao', 'fechada')),
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL,
        id_evolucao INTEGER REFERENCES Pep_Evolucoes(id_evolucao),
        fechado_em TEXT,
        fechado_por INTEGER REFERENCES Pep_Usuarios(id_usuario)
    )""",
    "CREATE INDEX IF NOT EXISTS ix_pep_rascunhos_paciente ON Pep_Rascunhos(id_paciente, atualizado_em)",
    "CREATE INDEX IF NOT EXISTS ix_pep_rascunhos_status ON Pep_Rascunhos(status, atualizado_em)",
    """CREATE TABLE IF NOT EXISTS Pep_Rascunho_Historico (
        id_historico INTEGER PRIMARY KEY AUTOINCREMENT,
        id_rascunho INTEGER NOT NULL REFERENCES Pep_Rascunhos(id_rascunho),
        id_autor INTEGER NOT NULL REFERENCES Pep_Equipe(id_membro),
        acao TEXT NOT NULL,
        snapshot_json TEXT NOT NULL,
        criado_em TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS ix_pep_rascunho_hist ON Pep_Rascunho_Historico(id_rascunho, id_historico)",
    """CREATE TABLE IF NOT EXISTS Pep_Evolucao_Metadados (
        id_evolucao INTEGER PRIMARY KEY REFERENCES Pep_Evolucoes(id_evolucao),
        id_elaborador INTEGER NOT NULL REFERENCES Pep_Equipe(id_membro),
        elaborador_nome TEXT NOT NULL,
        fechada_em TEXT NOT NULL,
        dados_json TEXT NOT NULL,
        confirmacao_json TEXT NOT NULL
    )""",
    """CREATE TRIGGER IF NOT EXISTS tr_pep_evolucao_meta_update_imutavel BEFORE UPDATE ON Pep_Evolucao_Metadados
       BEGIN SELECT RAISE(ABORT, 'Metadados da evolução fechada são imutáveis.'); END""",
    """CREATE TRIGGER IF NOT EXISTS tr_pep_evolucao_meta_delete_imutavel BEFORE DELETE ON Pep_Evolucao_Metadados
       BEGIN SELECT RAISE(ABORT, 'Metadados da evolução fechada não podem ser apagados.'); END""",
    """CREATE TRIGGER IF NOT EXISTS tr_pep_rascunho_hist_update_imutavel BEFORE UPDATE ON Pep_Rascunho_Historico
       BEGIN SELECT RAISE(ABORT, 'Histórico de rascunho é imutável.'); END""",
    """CREATE TRIGGER IF NOT EXISTS tr_pep_rascunho_hist_delete_imutavel BEFORE DELETE ON Pep_Rascunho_Historico
       BEGIN SELECT RAISE(ABORT, 'Histórico de rascunho é imutável.'); END""",
    """CREATE TRIGGER IF NOT EXISTS tr_pep_rascunho_fechado_update_imutavel BEFORE UPDATE ON Pep_Rascunhos
       WHEN OLD.status = 'fechada'
       BEGIN SELECT RAISE(ABORT, 'Rascunho fechado: correções devem ser registradas como adendo.'); END""",
    """CREATE TRIGGER IF NOT EXISTS tr_pep_rascunho_fechado_delete_imutavel BEFORE DELETE ON Pep_Rascunhos
       WHEN OLD.status = 'fechada'
       BEGIN SELECT RAISE(ABORT, 'Rascunho fechado não pode ser apagado.'); END""",
)
_PEP_EVOLUCAO_DOWN = (
    "DROP TRIGGER IF EXISTS tr_pep_evolucao_meta_delete_imutavel",
    "DROP TRIGGER IF EXISTS tr_pep_evolucao_meta_update_imutavel",
    "DROP TRIGGER IF EXISTS tr_pep_rascunho_fechado_delete_imutavel",
    "DROP TRIGGER IF EXISTS tr_pep_rascunho_fechado_update_imutavel",
    "DROP TRIGGER IF EXISTS tr_pep_rascunho_hist_delete_imutavel",
    "DROP TRIGGER IF EXISTS tr_pep_rascunho_hist_update_imutavel",
    "DROP INDEX IF EXISTS ix_pep_rascunho_hist",
    "DROP INDEX IF EXISTS ix_pep_rascunhos_status",
    "DROP INDEX IF EXISTS ix_pep_rascunhos_paciente",
    "DROP INDEX IF EXISTS ux_pep_equipe_usuario",
    "DROP TABLE IF EXISTS Pep_Evolucao_Metadados",
    "DROP TABLE IF EXISTS Pep_Rascunho_Historico",
    "DROP TABLE IF EXISTS Pep_Rascunhos",
    "DROP TABLE IF EXISTS Pep_Equipe",
)

# --- v8: colaboração multiprofissional e dados de evolução vinculados ao mapa ----------------
_PEP_MAPA_UP = (
    """CREATE TABLE IF NOT EXISTS Mapa_Evolucao_Dados (
        id_registro INTEGER PRIMARY KEY REFERENCES Mapa_Registros(id_registro) ON DELETE CASCADE,
        dados_json TEXT NOT NULL,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS Pep_Rascunho_Equipe (
        id_rascunho INTEGER NOT NULL REFERENCES Pep_Rascunhos(id_rascunho),
        id_membro INTEGER NOT NULL REFERENCES Pep_Equipe(id_membro),
        papel TEXT NOT NULL CHECK (papel IN ('estagiario', 'nutricionista')),
        PRIMARY KEY (id_rascunho, id_membro)
    )""",
    """CREATE TABLE IF NOT EXISTS Pep_Evolucao_Equipe (
        id_evolucao INTEGER NOT NULL REFERENCES Pep_Evolucoes(id_evolucao),
        id_membro INTEGER NOT NULL REFERENCES Pep_Equipe(id_membro),
        papel TEXT NOT NULL CHECK (papel IN ('estagiario', 'nutricionista')),
        nome_snapshot TEXT NOT NULL,
        crn_snapshot TEXT,
        PRIMARY KEY (id_evolucao, id_membro)
    )""",
    """CREATE TRIGGER IF NOT EXISTS tr_pep_rascunho_equipe_ins_fechado BEFORE INSERT ON Pep_Rascunho_Equipe
       WHEN (SELECT status FROM Pep_Rascunhos WHERE id_rascunho=NEW.id_rascunho) = 'fechada'
       BEGIN SELECT RAISE(ABORT, 'Equipe de evolução fechada não pode ser alterada.'); END""",
    """CREATE TRIGGER IF NOT EXISTS tr_pep_rascunho_equipe_upd_fechado BEFORE UPDATE ON Pep_Rascunho_Equipe
       WHEN (SELECT status FROM Pep_Rascunhos WHERE id_rascunho=OLD.id_rascunho) = 'fechada'
       BEGIN SELECT RAISE(ABORT, 'Equipe de evolução fechada não pode ser alterada.'); END""",
    """CREATE TRIGGER IF NOT EXISTS tr_pep_rascunho_equipe_del_fechado BEFORE DELETE ON Pep_Rascunho_Equipe
       WHEN (SELECT status FROM Pep_Rascunhos WHERE id_rascunho=OLD.id_rascunho) = 'fechada'
       BEGIN SELECT RAISE(ABORT, 'Equipe de evolução fechada não pode ser alterada.'); END""",
    """CREATE TRIGGER IF NOT EXISTS tr_pep_evolucao_equipe_update_imutavel BEFORE UPDATE ON Pep_Evolucao_Equipe
       BEGIN SELECT RAISE(ABORT, 'Equipe da evolução final é imutável.'); END""",
    """CREATE TRIGGER IF NOT EXISTS tr_pep_evolucao_equipe_delete_imutavel BEFORE DELETE ON Pep_Evolucao_Equipe
       BEGIN SELECT RAISE(ABORT, 'Equipe da evolução final não pode ser apagada.'); END""",
)
_PEP_MAPA_DOWN = (
    "DROP TRIGGER IF EXISTS tr_pep_evolucao_equipe_delete_imutavel",
    "DROP TRIGGER IF EXISTS tr_pep_evolucao_equipe_update_imutavel",
    "DROP TRIGGER IF EXISTS tr_pep_rascunho_equipe_del_fechado",
    "DROP TRIGGER IF EXISTS tr_pep_rascunho_equipe_upd_fechado",
    "DROP TRIGGER IF EXISTS tr_pep_rascunho_equipe_ins_fechado",
    "DROP TABLE IF EXISTS Pep_Evolucao_Equipe",
    "DROP TABLE IF EXISTS Pep_Rascunho_Equipe",
    "DROP TABLE IF EXISTS Mapa_Evolucao_Dados",
)

def _almox_validade_up(conn):
    """Adiciona validade ao cadastro de itens sem reescrever a migração v5 já publicada."""
    colunas = {r[1] for r in conn.execute("PRAGMA table_info(Almox_Itens)")}
    if "validade" not in colunas:
        conn.execute("ALTER TABLE Almox_Itens ADD COLUMN validade TEXT")


_ALMOX_VALIDADE_UP = (_almox_validade_up,)


# Lista oficial. NOVAS migrações entram SEMPRE ao final, com versão contígua; nunca editar uma já publicada.
MIGRACOES = (
    Migracao(versao=1, nome="baseline_esquema_legado", up=(), down=None, baseline=True),
    Migracao(versao=2, nome="condutas_alta", up=_CONDUTAS_ALTA_UP, down=_CONDUTAS_ALTA_DOWN),
    Migracao(versao=3, nome="condutas_alta_travas_contra_substituicao", up=_CONDUTAS_ALTA_TRAVAS_UP,
             down=_CONDUTAS_ALTA_TRAVAS_DOWN),
    Migracao(versao=4, nome="ambulatorial_anamnese_recomendacoes_exames_triagens",
             up=_AMBULATORIAL_UP, down=_AMBULATORIAL_DOWN),
    Migracao(versao=5, nome="almoxarifado_custos_programacao", up=_ALMOX_UP, down=_ALMOX_DOWN),
    Migracao(versao=6, nome="pep_evolucoes_immutability", up=_PEP_UP, down=_PEP_DOWN),
    Migracao(versao=7, nome="pep_rascunhos_equipe_e_revisao", up=_PEP_EVOLUCAO_UP, down=_PEP_EVOLUCAO_DOWN),
    Migracao(versao=8, nome="pep_colaboradores_e_integracao_mapa", up=_PEP_MAPA_UP, down=_PEP_MAPA_DOWN),
    Migracao(versao=9, nome="almox_validade_produtos", up=_ALMOX_VALIDADE_UP, down=None),
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
