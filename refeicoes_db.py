# -*- coding: utf-8 -*-
"""Regras e histórico imutável de refeições servidas por público.

O registro de serviço preserva paciente/leito, horário e custo como snapshots.
Alterações posteriores no mapa ou no cadastro de preços não reescrevem o passado.
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
from datetime import datetime, time

PUBLICOS = ("paciente", "funcionario", "acompanhante")
REFEICOES = ("desjejum", "colacao", "almoco", "lanche", "jantar", "ceia")


class _ConexaoFechavel(sqlite3.Connection):
    """Fecha também o handle ao sair de um bloco 'with'."""

    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


def conectar(db_path):
    os.makedirs(os.path.dirname(os.path.abspath(str(db_path))), exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=15, factory=_ConexaoFechavel)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def inicializar(db_path):
    with conectar(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS Refeicoes_Janelas (
            publico TEXT NOT NULL CHECK(publico IN ('paciente','funcionario')),
            refeicao TEXT NOT NULL,
            inicio TEXT NOT NULL,
            fim TEXT NOT NULL,
            atualizado_em TEXT NOT NULL,
            PRIMARY KEY(publico, refeicao)
        );
        CREATE TABLE IF NOT EXISTS Refeicoes_Autorizacoes_Acompanhante (
            id_autorizacao INTEGER PRIMARY KEY AUTOINCREMENT,
            id_paciente TEXT NOT NULL,
            nome_paciente_snapshot TEXT NOT NULL,
            leito_snapshot TEXT NOT NULL,
            quantidade_acompanhantes INTEGER NOT NULL CHECK(quantidade_acompanhantes > 0),
            refeicoes_json TEXT NOT NULL,
            justificativa TEXT NOT NULL,
            autorizado_por TEXT NOT NULL,
            registrado_por TEXT,
            inicio_vigencia TEXT NOT NULL,
            fim_vigencia TEXT,
            situacao TEXT NOT NULL DEFAULT 'ativa'
                CHECK(situacao IN ('ativa','encerrada','cancelada')),
            criado_em TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ref_autorizacao_paciente
            ON Refeicoes_Autorizacoes_Acompanhante(id_paciente, situacao, inicio_vigencia);
        CREATE TABLE IF NOT EXISTS Refeicoes_Servidas (
            id_servico INTEGER PRIMARY KEY AUTOINCREMENT,
            servido_em TEXT NOT NULL,
            data_refeicao TEXT NOT NULL,
            refeicao TEXT NOT NULL,
            publico TEXT NOT NULL CHECK(publico IN ('paciente','funcionario','acompanhante')),
            destinatario_id TEXT,
            destinatario_nome_snapshot TEXT NOT NULL,
            id_paciente TEXT,
            nome_paciente_snapshot TEXT,
            leito_snapshot TEXT,
            quantidade REAL NOT NULL CHECK(quantidade > 0),
            unidade TEXT NOT NULL DEFAULT 'porcao',
            valor_unitario_snapshot REAL,
            custo_total_snapshot REAL,
            categoria_custo TEXT NOT NULL CHECK(categoria_custo IN ('pacientes','funcionarios','acompanhantes')),
            id_autorizacao_acompanhante INTEGER,
            usuario_registro TEXT,
            observacao TEXT,
            criado_em TEXT NOT NULL,
            FOREIGN KEY(id_autorizacao_acompanhante)
                REFERENCES Refeicoes_Autorizacoes_Acompanhante(id_autorizacao)
        );
        CREATE INDEX IF NOT EXISTS idx_ref_serv_instant
            ON Refeicoes_Servidas(servido_em, publico, refeicao);
        CREATE INDEX IF NOT EXISTS idx_ref_serv_paciente
            ON Refeicoes_Servidas(id_paciente, data_refeicao);
        CREATE TRIGGER IF NOT EXISTS trg_refeicoes_servidas_sem_update
        BEFORE UPDATE ON Refeicoes_Servidas
        BEGIN
            SELECT RAISE(ABORT, 'O histórico de refeições servidas é imutável.');
        END;
        CREATE TRIGGER IF NOT EXISTS trg_refeicoes_servidas_sem_delete
        BEFORE DELETE ON Refeicoes_Servidas
        BEGIN
            SELECT RAISE(ABORT, 'O histórico de refeições servidas é imutável.');
        END;
        """)
        colunas = {r[1] for r in conn.execute("PRAGMA table_info(Refeicoes_Autorizacoes_Acompanhante)")}
        if "registrado_por" not in colunas:
            conn.execute("ALTER TABLE Refeicoes_Autorizacoes_Acompanhante ADD COLUMN registrado_por TEXT")


def _agora():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _validar_publico(publico, permitir_acompanhante=True):
    if publico not in (PUBLICOS if permitir_acompanhante else PUBLICOS[:2]):
        raise ValueError("Público inválido.")


def _validar_refeicao(refeicao):
    if refeicao not in REFEICOES:
        raise ValueError("Refeição inválida.")


def _hora(valor, campo):
    try:
        return time.fromisoformat(str(valor))
    except (TypeError, ValueError):
        raise ValueError(f"Informe {campo} no formato HH:MM.") from None


def salvar_janela(db_path, publico, refeicao, inicio, fim):
    """Salva janela local configurada; não cria horários padrão."""
    _validar_publico(publico, permitir_acompanhante=False)
    _validar_refeicao(refeicao)
    ini, final = _hora(inicio, "início"), _hora(fim, "fim")
    if ini == final:
        raise ValueError("O início e o fim da janela não podem ser iguais.")
    agora = _agora()
    with conectar(db_path) as conn:
        conn.execute("""
            INSERT INTO Refeicoes_Janelas(publico,refeicao,inicio,fim,atualizado_em)
            VALUES(?,?,?,?,?)
            ON CONFLICT(publico,refeicao) DO UPDATE SET
                inicio=excluded.inicio,fim=excluded.fim,atualizado_em=excluded.atualizado_em
        """, (publico, refeicao, ini.strftime("%H:%M"), final.strftime("%H:%M"), agora))


def listar_janelas(db_path, publico=None):
    if publico is not None:
        _validar_publico(publico, permitir_acompanhante=False)
    with conectar(db_path) as conn:
        sql = "SELECT * FROM Refeicoes_Janelas"
        args = ()
        if publico:
            sql += " WHERE publico=?"
            args = (publico,)
        sql += " ORDER BY publico, CASE refeicao WHEN 'desjejum' THEN 1 WHEN 'colacao' THEN 2 WHEN 'almoco' THEN 3 WHEN 'lanche' THEN 4 WHEN 'jantar' THEN 5 ELSE 6 END"
        return [dict(r) for r in conn.execute(sql, args)]


def salvar_autorizacao_acompanhante(
    db_path, *, id_paciente, nome_paciente, leito, quantidade,
    refeicoes, justificativa, autorizado_por, registrado_por=None,
    inicio_vigencia=None, fim_vigencia=None
):
    if not str(id_paciente or "").strip():
        raise ValueError("Identifique o paciente relacionado.")
    if not str(nome_paciente or "").strip() or not str(leito or "").strip():
        raise ValueError("Nome do paciente e leito são obrigatórios.")
    try:
        quantidade = int(quantidade)
    except (TypeError, ValueError):
        raise ValueError("Informe a quantidade de acompanhantes.") from None
    if quantidade < 1:
        raise ValueError("A quantidade de acompanhantes deve ser maior que zero.")
    refeicoes = sorted(set(refeicoes or []))
    if not refeicoes:
        raise ValueError("Selecione ao menos uma refeição autorizada.")
    for refeicao in refeicoes:
        _validar_refeicao(refeicao)
    if not str(justificativa or "").strip() or not str(autorizado_por or "").strip():
        raise ValueError("Justificativa e responsável pela autorização são obrigatórios.")
    try:
        inicio = datetime.fromisoformat(inicio_vigencia)
        fim = datetime.fromisoformat(fim_vigencia) if fim_vigencia else None
    except (TypeError, ValueError):
        raise ValueError("Informe a vigência em data e hora válidas.") from None
    if fim and fim <= inicio:
        raise ValueError("O término deve ser posterior ao início.")
    with conectar(db_path) as conn:
        cur = conn.execute("""
            INSERT INTO Refeicoes_Autorizacoes_Acompanhante(
                id_paciente,nome_paciente_snapshot,leito_snapshot,quantidade_acompanhantes,
                refeicoes_json,justificativa,autorizado_por,registrado_por,inicio_vigencia,fim_vigencia,
                situacao,criado_em
            ) VALUES(?,?,?,?,?,?,?,?,?,?,'ativa',?)
        """, (str(id_paciente), str(nome_paciente).strip(), str(leito).strip(), quantidade,
              json.dumps(refeicoes, ensure_ascii=False), justificativa.strip(),
              autorizado_por.strip(), str(registrado_por or "").strip() or None,
              inicio.isoformat(), fim.isoformat() if fim else None, _agora()))
        return cur.lastrowid


def encerrar_autorizacao_acompanhante(db_path, id_autorizacao, situacao="encerrada"):
    if situacao not in ("encerrada", "cancelada"):
        raise ValueError("Situação de encerramento inválida.")
    with conectar(db_path) as conn:
        cur = conn.execute("""
            UPDATE Refeicoes_Autorizacoes_Acompanhante SET situacao=?
            WHERE id_autorizacao=? AND situacao='ativa'
        """, (situacao, int(id_autorizacao)))
        return cur.rowcount == 1


def _janela_permite(conn, publico, refeicao, instante):
    if publico == "acompanhante":
        return True
    row = conn.execute(
        "SELECT inicio,fim FROM Refeicoes_Janelas WHERE publico=? AND refeicao=?",
        (publico, refeicao)
    ).fetchone()
    if not row:
        raise ValueError(f"Configure a janela de {refeicao} para {publico} antes de registrar o serviço.")
    # O servidor já normaliza os horários para America/Recife antes de chamar este módulo.
    hora = instante.time().replace(tzinfo=None)
    ini, fim = _hora(row["inicio"], "início"), _hora(row["fim"], "fim")
    return ini <= hora <= fim if ini < fim else (hora >= ini or hora <= fim)


def registrar_refeicao_servida(
    db_path, *, servido_em, refeicao, publico, destinatario_nome,
    quantidade=1, unidade="porcao", valor_unitario=None,
    destinatario_id=None, id_paciente=None, nome_paciente=None, leito=None,
    id_autorizacao_acompanhante=None, usuario_registro=None, observacao=None
):
    """Grava fato de serviço com snapshots; nunca consulta o ocupante atual do leito."""
    _validar_refeicao(refeicao)
    _validar_publico(publico)
    try:
        instante = datetime.fromisoformat(servido_em)
    except (TypeError, ValueError):
        raise ValueError("Informe a data e hora efetiva em que a refeição foi servida.") from None
    try:
        quantidade = float(quantidade)
    except (TypeError, ValueError):
        raise ValueError("Quantidade inválida.") from None
    if not math.isfinite(quantidade) or quantidade <= 0:
        raise ValueError("A quantidade deve ser maior que zero.")
    if valor_unitario in (None, ""):
        preco = custo = None
    else:
        try:
            preco = float(valor_unitario)
        except (TypeError, ValueError):
            raise ValueError("Valor unitário inválido.") from None
        if not math.isfinite(preco) or preco < 0:
            raise ValueError("Valor unitário inválido.")
        custo = round(preco * quantidade, 6)
    if not str(destinatario_nome or "").strip():
        raise ValueError("Identifique quem recebeu a refeição.")
    if publico == "paciente" and not str(id_paciente or "").strip():
        raise ValueError("O serviço ao paciente exige o identificador do paciente/internação.")
    if publico == "paciente" and (not str(nome_paciente or "").strip() or not str(leito or "").strip()):
        raise ValueError("O serviço ao paciente exige snapshots do nome e do leito.")
    if publico == "acompanhante" and not id_autorizacao_acompanhante:
        raise ValueError("A refeição de acompanhante exige autorização da assistência social.")
    categoria = {"paciente": "pacientes", "funcionario": "funcionarios",
                 "acompanhante": "acompanhantes"}[publico]
    with conectar(db_path) as conn:
        if not _janela_permite(conn, publico, refeicao, instante):
            raise ValueError("O horário informado está fora da janela configurada.")
        if publico == "acompanhante":
            auth = conn.execute("""
                SELECT * FROM Refeicoes_Autorizacoes_Acompanhante
                WHERE id_autorizacao=? AND situacao='ativa'
            """, (int(id_autorizacao_acompanhante),)).fetchone()
            if not auth:
                raise ValueError("Autorização de acompanhante inexistente ou inativa.")
            inicio = datetime.fromisoformat(auth["inicio_vigencia"])
            fim = datetime.fromisoformat(auth["fim_vigencia"]) if auth["fim_vigencia"] else None
            instante_comparacao = instante
            zona = instante.tzinfo or inicio.tzinfo
            if instante_comparacao.tzinfo is None and zona is not None:
                instante_comparacao = instante_comparacao.replace(tzinfo=zona)
            if inicio.tzinfo is None and instante_comparacao.tzinfo is not None:
                inicio = inicio.replace(tzinfo=instante_comparacao.tzinfo)
            if fim is not None and fim.tzinfo is None and instante_comparacao.tzinfo is not None:
                fim = fim.replace(tzinfo=instante_comparacao.tzinfo)
            permitidas = json.loads(auth["refeicoes_json"])
            if str(id_paciente or "") != auth["id_paciente"]:
                raise ValueError("A autorização pertence a outro paciente, não ao leito atual.")
            if refeicao not in permitidas or instante_comparacao < inicio or (fim and instante_comparacao > fim):
                raise ValueError("A refeição ou o horário não está coberto pela autorização.")
            if quantidade > auth["quantidade_acompanhantes"]:
                raise ValueError("A quantidade excede a autorização da assistência social.")
            nome_paciente = auth["nome_paciente_snapshot"]
            leito = auth["leito_snapshot"]
        instante_registro = instante
        cur = conn.execute("""
            INSERT INTO Refeicoes_Servidas(
                servido_em,data_refeicao,refeicao,pubLico,destinatario_id,
                destinatario_nome_snapshot,id_paciente,nome_paciente_snapshot,leito_snapshot,
                quantidade,unidade,valor_unitario_snapshot,custo_total_snapshot,
                categoria_custo,id_autorizacao_acompanhante,usuario_registro,observacao,criado_em
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (instante_registro.isoformat(), instante_registro.date().isoformat(), refeicao, publico,
              str(destinatario_id) if destinatario_id is not None else None,
              str(destinatario_nome).strip(), str(id_paciente) if id_paciente is not None else None,
              nome_paciente, leito, quantidade, str(unidade or "porcao"), preco, custo,
              categoria, id_autorizacao_acompanhante, usuario_registro, observacao, _agora()))
        return cur.lastrowid


def listar_refeicoes_servidas(db_path, inicio, fim, publico=None):
    if publico is not None:
        _validar_publico(publico)
    with conectar(db_path) as conn:
        sql = "SELECT * FROM Refeicoes_Servidas WHERE data_refeicao BETWEEN ? AND ?"
        args = [str(inicio), str(fim)]
        if publico:
            sql += " AND publico=?"
            args.append(publico)
        sql += " ORDER BY servido_em,id_servico"
        return [dict(r) for r in conn.execute(sql, args)]


def resumo_custos(db_path, inicio, fim):
    with conectar(db_path) as conn:
        rows = conn.execute("""
            SELECT categoria_custo,COUNT(*) AS servicos,SUM(quantidade) AS quantidade,
                   SUM(custo_total_snapshot) AS custo
            FROM Refeicoes_Servidas WHERE data_refeicao BETWEEN ? AND ?
            GROUP BY categoria_custo ORDER BY categoria_custo
        """, (str(inicio), str(fim))).fetchall()
    return {r["categoria_custo"]: dict(r) for r in rows}


def listar_autorizacoes_acompanhante(db_path, id_paciente=None, situacao=None):
    """Consulta autorizações sem depender do ocupante atual do leito."""
    sql = "SELECT * FROM Refeicoes_Autorizacoes_Acompanhante WHERE 1=1"
    args = []
    if id_paciente:
        sql += " AND id_paciente=?"
        args.append(str(id_paciente))
    if situacao:
        if situacao not in ("ativa", "encerrada", "cancelada"):
            raise ValueError("Situação de autorização inválida.")
        sql += " AND situacao=?"
        args.append(situacao)
    sql += " ORDER BY criado_em DESC,id_autorizacao DESC"
    with conectar(db_path) as conn:
        saida = []
        for row in conn.execute(sql, args):
            item = dict(row)
            try:
                item["refeicoes"] = json.loads(item.pop("refeicoes_json") or "[]")
            except (TypeError, ValueError):
                item["refeicoes"] = []
            saida.append(item)
        return saida


def remover_janela(db_path, publico, refeicao):
    """Remove uma janela explicitamente; sem janela, o serviço fica bloqueado."""
    _validar_publico(publico, permitir_acompanhante=False)
    _validar_refeicao(refeicao)
    with conectar(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM Refeicoes_Janelas WHERE publico=? AND refeicao=?",
            (publico, refeicao)
        )
        return cur.rowcount == 1
