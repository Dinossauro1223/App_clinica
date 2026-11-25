# -*- coding: utf-8 -*-
"""Persistência da evolução nutricional individual, rascunhos e fechamento autenticado.

A evolução final é gerada a partir de dados estruturados e gravada em Pep_Evolucoes,
que já possui travas append-only. Rascunhos mantêm snapshots de auditoria imutáveis.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import closing
from datetime import date, datetime

import db_service as svc
import pep_db
import evolucao_nutricional as regras


class EvolucaoPEPError(Exception):
    """Erro de regra de negócio do fluxo de evolução."""


def _conectar(db_path):
    return svc.conectar(db_path, foreign_keys=True)


def _agora():
    return datetime.now().isoformat(timespec="seconds")


def _exigir_schema(conn):
    tabelas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    obrigatorias = {"Pep_Equipe", "Pep_Rascunhos", "Pep_Rascunho_Historico", "Pep_Evolucoes", "Pep_Usuarios"}
    if not obrigatorias.issubset(tabelas):
        raise EvolucaoPEPError("Banco sem migração PEP v7. Reinicie o NutriLab para aplicar as migrações.")


def _data_iso(valor):
    if isinstance(valor, date):
        return valor.isoformat()
    texto = str(valor or "").strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            pass
    raise ValueError("Data da evolução inválida. Use DD/MM/AAAA.")


def _crn(valor):
    texto = re.sub(r"\s+", " ", str(valor or "").strip().upper())
    if not re.fullmatch(r"CRN[ -]?\d{1,2}[ /-]?\d{3,8}(?:-[A-Z]{1,2})?", texto):
        raise ValueError("CRN inválido. Informe no formato CRN-6 1234 e confira o registro profissional.")
    return texto


def _snapshot(conn, id_rascunho, id_autor, acao, dados, agora):
    conn.execute(
        "INSERT INTO Pep_Rascunho_Historico (id_rascunho, id_autor, acao, snapshot_json, criado_em) "
        "VALUES (?, ?, ?, ?, ?)",
        (id_rascunho, id_autor, acao, json.dumps(dados, ensure_ascii=False, sort_keys=True), agora),
    )


def cadastrar_membro(db_path, nome, funcao, *, crn=None, crn_conferido=False, id_usuario=None):
    """Cadastra estagiário ou vincula nutricionista a uma conta PEP autenticável."""
    nome = str(nome or "").strip()
    funcao = str(funcao or "").strip().casefold()
    if not nome:
        raise ValueError("Informe o nome do integrante.")
    if funcao not in {"estagiario", "nutricionista"}:
        raise ValueError("Função deve ser estagiario ou nutricionista.")
    if funcao == "estagiario":
        if crn or id_usuario is not None or crn_conferido:
            raise ValueError("Estagiário não pode receber CRN nem vínculo de conta de fechamento.")
        crn_limpo, conferido, usuario = None, 0, None
    else:
        crn_limpo = _crn(crn)
        if crn_conferido is not True:
            raise ValueError("Confirme que o CRN foi conferido antes de cadastrar o nutricionista.")
        if isinstance(id_usuario, bool) or not isinstance(id_usuario, int) or id_usuario < 1:
            raise ValueError("Vincule uma conta PEP individual ao nutricionista.")
        with closing(_conectar(db_path)) as conn:
            _exigir_schema(conn)
            conta = conn.execute(
                "SELECT nome_completo, crn, ativo FROM Pep_Usuarios WHERE id_usuario=?", (id_usuario,)
            ).fetchone()
            if not conta or not conta[2]:
                raise ValueError("Conta PEP inexistente ou inativa.")
            if str(conta[1]).strip().upper() != crn_limpo:
                raise ValueError("O CRN do cadastro da equipe deve corresponder ao CRN da conta PEP.")
        conferido, usuario = 1, id_usuario
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        cur = conn.execute(
            "INSERT INTO Pep_Equipe (nome, funcao, crn, crn_conferido, id_usuario, ativo, criado_em) "
            "VALUES (?, ?, ?, ?, ?, 1, ?)",
            (nome, funcao, crn_limpo, conferido, usuario, _agora()),
        )
        conn.commit()
        return cur.lastrowid


def listar_equipe(db_path, funcao=None, ativos=True):
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        sql = "SELECT id_membro, nome, funcao, crn, crn_conferido, id_usuario, ativo FROM Pep_Equipe WHERE 1=1"
        params = []
        if funcao:
            sql += " AND funcao=?"
            params.append(str(funcao).casefold())
        if ativos:
            sql += " AND ativo=1"
        sql += " ORDER BY nome COLLATE NOCASE"
        return [dict(r) for r in conn.execute(sql, params)]


def desativar_membro(db_path, id_membro):
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        conn.execute("UPDATE Pep_Equipe SET ativo=0 WHERE id_membro=?", (int(id_membro),))
        conn.commit()


def salvar_rascunho(db_path, id_paciente, data_evolucao, dados, id_elaborador, id_rascunho=None):
    """Cria ou atualiza rascunho clínico e acrescenta um snapshot auditável."""
    if isinstance(id_paciente, bool) or not isinstance(id_paciente, int) or id_paciente < 1:
        raise ValueError("Vínculo de paciente inválido.")
    if isinstance(id_elaborador, bool) or not isinstance(id_elaborador, int) or id_elaborador < 1:
        raise ValueError("Selecione o integrante que está elaborando a evolução.")
    if not isinstance(dados, dict):
        raise ValueError("Os dados estruturados da evolução devem ser um dicionário.")
    data_iso = _data_iso(data_evolucao)
    dados_json = json.dumps(dados, ensure_ascii=False, sort_keys=True, allow_nan=False)
    agora = _agora()
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        paciente = conn.execute("SELECT nome FROM Pacientes WHERE id_paciente=?", (id_paciente,)).fetchone()
        if not paciente:
            raise ValueError("Paciente não encontrado no cadastro clínico.")
        membro = conn.execute("SELECT nome, ativo FROM Pep_Equipe WHERE id_membro=?", (id_elaborador,)).fetchone()
        if not membro or not membro[1]:
            raise EvolucaoPEPError("Integrante inexistente ou inativo.")
        if id_rascunho is None:
            cur = conn.execute(
                "INSERT INTO Pep_Rascunhos (id_paciente, paciente_nome, data_evolucao, dados_json, "
                "id_elaborador, status, criado_em, atualizado_em) VALUES (?, ?, ?, ?, ?, 'rascunho', ?, ?)",
                (id_paciente, paciente[0], data_iso, dados_json, id_elaborador, agora, agora),
            )
            novo_id = cur.lastrowid
            acao = "criado"
        else:
            atual = conn.execute(
                "SELECT id_paciente, id_elaborador, status FROM Pep_Rascunhos WHERE id_rascunho=?",
                (int(id_rascunho),),
            ).fetchone()
            if not atual or atual[0] != id_paciente:
                raise ValueError("Rascunho não encontrado para este paciente.")
            if atual[2] == "fechada":
                raise EvolucaoPEPError("Evolução fechada. Registre um adendo em vez de alterar o histórico.")
            conn.execute(
                "UPDATE Pep_Rascunhos SET paciente_nome=?, data_evolucao=?, dados_json=?, "
                "id_elaborador=?, atualizado_em=? WHERE id_rascunho=?",
                (paciente[0], data_iso, dados_json, id_elaborador, agora, int(id_rascunho)),
            )
            novo_id, acao = int(id_rascunho), "atualizado"
        _snapshot(conn, novo_id, id_elaborador, acao, dados, agora)
        conn.commit()
        return novo_id


def obter_rascunho(db_path, id_rascunho):
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        row = conn.execute(
            "SELECT R.*, E.nome AS elaborador_nome FROM Pep_Rascunhos R "
            "JOIN Pep_Equipe E ON E.id_membro=R.id_elaborador WHERE R.id_rascunho=?",
            (int(id_rascunho),),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["dados"] = json.loads(item.pop("dados_json"))
    return item


def listar_rascunhos(db_path, id_paciente=None, status=None):
    sql = "SELECT id_rascunho FROM Pep_Rascunhos WHERE 1=1"
    params = []
    if id_paciente is not None:
        sql += " AND id_paciente=?"
        params.append(int(id_paciente))
    if status:
        sql += " AND status=?"
        params.append(str(status))
    sql += " ORDER BY atualizado_em DESC, id_rascunho DESC"
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        ids = [r[0] for r in conn.execute(sql, params)]
    return [obter_rascunho(db_path, i) for i in ids]


def historico_rascunho(db_path, id_rascunho):
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        return [dict(r) for r in conn.execute(
            "SELECT H.*, E.nome AS autor_nome FROM Pep_Rascunho_Historico H "
            "JOIN Pep_Equipe E ON E.id_membro=H.id_autor WHERE H.id_rascunho=? ORDER BY H.id_historico",
            (int(id_rascunho),),
        )]


def fechar_rascunho(db_path, id_rascunho, id_usuario, senha, *, confirmado=False):
    """Fecha apenas após autenticação de nutricionista com CRN conferido e confirmação explícita."""
    if confirmado is not True:
        raise EvolucaoPEPError("O nutricionista precisa confirmar explicitamente a revisão e o fechamento.")
    profissional = pep_db.autenticar(db_path, id_usuario, senha)
    if not profissional:
        raise EvolucaoPEPError("Autenticação do nutricionista inválida ou conta inativa.")
    agora = _agora()
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        conta = conn.execute(
            "SELECT U.nome_completo, U.crn, U.ativo, E.id_membro, E.nome, E.crn, E.crn_conferido "
            "FROM Pep_Usuarios U JOIN Pep_Equipe E ON E.id_usuario=U.id_usuario "
            "WHERE U.id_usuario=? AND E.funcao='nutricionista' AND E.ativo=1",
            (int(id_usuario),),
        ).fetchone()
        if not conta or not conta[2] or not conta[6] or _crn(conta[1]) != _crn(conta[5]):
            conn.rollback()
            raise EvolucaoPEPError("Fechamento exige nutricionista ativo, vinculado e com CRN previamente conferido.")
        r = conn.execute(
            "SELECT id_paciente, paciente_nome, data_evolucao, dados_json, id_elaborador, status "
            "FROM Pep_Rascunhos WHERE id_rascunho=?",
            (int(id_rascunho),),
        ).fetchone()
        if not r:
            conn.rollback()
            raise ValueError("Rascunho não encontrado.")
        if r[5] == "fechada":
            conn.rollback()
            raise EvolucaoPEPError("Esta evolução já foi fechada.")
        dados = json.loads(r[3])
        if not isinstance(dados, dict) or not isinstance(dados.get("antropometria"), dict):
            conn.rollback()
            raise ValueError("A antropometria estruturada é obrigatória para gerar a evolução.")
        dados["antropometria"].setdefault("data", datetime.strptime(r[2], "%Y-%m-%d").strftime("%d/%m/%Y"))
        membro = conn.execute("SELECT nome FROM Pep_Equipe WHERE id_membro=? AND ativo=1", (r[4],)).fetchone()
        if not membro:
            conn.rollback()
            raise EvolucaoPEPError("O elaborador do rascunho está inativo ou não existe.")
        dados["estagiarios"] = dados.get("estagiarios") or ([membro[0]] if membro else [])
        dados["nutricionistas"] = [f"{conta[0]} — {conta[1]}"]
        texto = regras.gerar_evolucao(dados)
        dados_json = json.dumps(dados, ensure_ascii=False, sort_keys=True, allow_nan=False)
        confirmacao = json.dumps({
            "confirmado": True, "confirmado_por": conta[0], "crn": conta[1],
            "confirmado_em": agora, "sha256_texto": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
        }, ensure_ascii=False, sort_keys=True)
        cur = conn.execute(
            "INSERT INTO Pep_Evolucoes (id_paciente, paciente_nome, data_evolucao, cabecalho_json, texto, "
            "id_usuario, assinante_nome, assinante_crn, criada_em, adendo_de, dados_json, id_elaborador, "
            "elaborador_nome, fechada_em, confirmacao_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)",
            (r[0], r[1], r[2], json.dumps({"dados": dados}, ensure_ascii=False, sort_keys=True), texto,
             int(id_usuario), conta[0], conta[1], agora, dados_json, r[4], membro[0], agora, confirmacao),
        )
        id_evolucao = cur.lastrowid
        conn.execute(
            "UPDATE Pep_Rascunhos SET status='fechada', id_evolucao=?, fechado_em=?, fechado_por=?, atualizado_em=? "
            "WHERE id_rascunho=?",
            (id_evolucao, agora, int(id_usuario), agora, int(id_rascunho)),
        )
        _snapshot(conn, int(id_rascunho), r[4], "fechado", dados, agora)
        conn.commit()
        return id_evolucao


def validar_crn_formato(valor):
    """Valida sintaxe local do CRN; não substitui consulta de regularidade no conselho."""
    try:
        return _crn(valor)
    except ValueError:
        return None
