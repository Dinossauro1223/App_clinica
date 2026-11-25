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
    conn = svc.conectar(db_path, foreign_keys=True)
    conn.row_factory = sqlite3.Row
    return conn


def _agora():
    return datetime.now().isoformat(timespec="seconds")


def _exigir_schema(conn):
    tabelas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    obrigatorias = {"Pep_Equipe", "Pep_Rascunhos", "Pep_Rascunho_Historico", "Pep_Evolucoes", "Pep_Usuarios",
                    "Pep_Rascunho_Equipe", "Pep_Evolucao_Equipe", "Pep_Evolucao_Metadados"}
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


def salvar_rascunho(db_path, id_paciente, data_evolucao, dados, id_elaborador, id_rascunho=None, colaboradores_ids=None):
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
    selecionados = list(dict.fromkeys([id_elaborador] + list(colaboradores_ids or [])))
    if any(isinstance(i, bool) or not isinstance(i, int) or i < 1 for i in selecionados):
        raise ValueError("IDs dos colaboradores inválidos.")
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        paciente = conn.execute("SELECT nome FROM Pacientes WHERE id_paciente=?", (id_paciente,)).fetchone()
        if not paciente:
            raise ValueError("Paciente não encontrado no cadastro clínico.")
        membro = conn.execute("SELECT nome, ativo FROM Pep_Equipe WHERE id_membro=?", (id_elaborador,)).fetchone()
        if not membro or not membro[1]:
            raise EvolucaoPEPError("Integrante inexistente ou inativo.")
        membros = conn.execute(
            f"SELECT id_membro, funcao FROM Pep_Equipe WHERE ativo=1 AND id_membro IN ({','.join('?' for _ in selecionados)})",
            selecionados,
        ).fetchall()
        if len(membros) != len(selecionados):
            raise EvolucaoPEPError("Um ou mais colaboradores não existem ou estão inativos.")
        papeis = {m["id_membro"]: m["funcao"] for m in membros}
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
        conn.execute("DELETE FROM Pep_Rascunho_Equipe WHERE id_rascunho=?", (novo_id,))
        for id_membro in selecionados:
            conn.execute(
                "INSERT INTO Pep_Rascunho_Equipe (id_rascunho, id_membro, papel) VALUES (?, ?, ?)",
                (novo_id, id_membro, papeis[id_membro]),
            )
        snapshot = dict(dados)
        snapshot["_colaboradores_ids"] = selecionados
        _snapshot(conn, novo_id, id_elaborador, acao, snapshot, agora)
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
    with closing(_conectar(db_path)) as conn:
        item["colaboradores"] = [dict(r) for r in conn.execute(
            "SELECT E.id_membro, E.nome, E.funcao, E.crn FROM Pep_Rascunho_Equipe R "
            "JOIN Pep_Equipe E ON E.id_membro=R.id_membro WHERE R.id_rascunho=? ORDER BY E.funcao, E.nome",
            (int(id_rascunho),),
        )]
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


def fechar_rascunho(db_path, id_rascunho, id_usuario, senha, *, confirmado=False,
                    autorizar_progressao=False, autorizar_porcao_oral=False):
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
        if not dados.get("metas"):
            conn.rollback()
            raise ValueError("As metas energéticas e proteicas precisam estar calculadas antes do fechamento.")
        via = str(dados.get("via") or "").casefold()
        if via == "oral" and dados.get("tno") not in regras.TNO_PERCENTUAIS:
            conn.rollback()
            raise ValueError("Classifique o TNO antes do fechamento.")
        if via == "enteral" and not dados.get("oferta"):
            conn.rollback()
            raise ValueError("A oferta enteral e sua adequação precisam ser calculadas com a ficha técnica.")
        progressao = dados.get("progressao_enteral") or {}
        progressao["autorizada"] = bool(autorizar_progressao and progressao.get("solicitada"))
        if progressao["autorizada"]:
            progressao["plano"] = regras.planejar_progressao_por_etapa(
                progressao["volume_etapa_atual_ml"], progressao["etapas"],
                progressao["volume_meta_ml"] / progressao["etapas"],
                progressao["incremento_por_etapa_ml"], progressao["dias_alvo"],
                habilitada=True, autorizada=True,
                tolerancia=progressao.get("tolerancia", True),
                restricao=progressao.get("restricao", False))
        elif progressao:
            progressao.pop("plano", None)
        dados["progressao_enteral"] = progressao
        dados["porcao_oral_autorizada"] = bool(
            autorizar_porcao_oral and dados.get("porcao_oral_solicitada") and via == "oral")
        dados["antropometria"].setdefault("data", datetime.strptime(r[2], "%Y-%m-%d").strftime("%d/%m/%Y"))
        membros = [dict(x) for x in conn.execute(
            "SELECT E.id_membro, E.nome, E.funcao, E.crn FROM Pep_Rascunho_Equipe R "
            "JOIN Pep_Equipe E ON E.id_membro=R.id_membro WHERE R.id_rascunho=? AND E.ativo=1",
            (int(id_rascunho),),
        )]
        if not membros:
            membro_base = conn.execute("SELECT id_membro, nome, funcao, crn FROM Pep_Equipe WHERE id_membro=? AND ativo=1",
                                       (r[4],)).fetchone()
            if membro_base:
                membros = [dict(membro_base)]
        membro = conn.execute("SELECT nome FROM Pep_Equipe WHERE id_membro=? AND ativo=1", (r[4],)).fetchone()
        if not membro:
            conn.rollback()
            raise EvolucaoPEPError("O elaborador do rascunho está inativo ou não existe.")
        estagiarios = [m["nome"] for m in membros if m["funcao"] == "estagiario"]
        nutricionistas = [f"{m['nome']} — {m['crn']}" for m in membros if m["funcao"] == "nutricionista"]
        dados["estagiarios"] = estagiarios or dados.get("estagiarios") or ([membro[0]] if membro else [])
        assinatura = f"{conta[0]} — {conta[1]}"
        if assinatura not in nutricionistas:
            nutricionistas.append(assinatura)
        dados["nutricionistas"] = nutricionistas
        texto = regras.gerar_evolucao(dados)
        dados_json = json.dumps(dados, ensure_ascii=False, sort_keys=True, allow_nan=False)
        confirmacao = json.dumps({
            "confirmado": True, "confirmado_por": conta[0], "crn": conta[1],
            "confirmado_em": agora, "sha256_texto": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
        }, ensure_ascii=False, sort_keys=True)
        cur = conn.execute(
            "INSERT INTO Pep_Evolucoes (id_paciente, paciente_nome, data_evolucao, cabecalho_json, texto, "
            "id_usuario, assinante_nome, assinante_crn, criada_em, adendo_de) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (r[0], r[1], r[2], json.dumps({"dados": dados}, ensure_ascii=False, sort_keys=True), texto,
             int(id_usuario), conta[0], conta[1], agora),
        )
        id_evolucao = cur.lastrowid
        conn.execute(
            "INSERT INTO Pep_Evolucao_Metadados (id_evolucao, id_elaborador, elaborador_nome, fechada_em, "
            "dados_json, confirmacao_json) VALUES (?, ?, ?, ?, ?, ?)",
            (id_evolucao, r[4], membro[0], agora, dados_json, confirmacao),
        )
        ids_equipe = {m["id_membro"] for m in membros}
        assinante_equipe = conn.execute(
            "SELECT id_membro, nome, funcao, crn FROM Pep_Equipe WHERE id_usuario=? AND funcao='nutricionista' AND ativo=1",
            (int(id_usuario),),
        ).fetchone()
        if assinante_equipe:
            ids_equipe.add(assinante_equipe["id_membro"])
        for integrante in membros + ([dict(assinante_equipe)] if assinante_equipe and assinante_equipe["id_membro"] not in {m["id_membro"] for m in membros} else []):
            conn.execute(
                "INSERT INTO Pep_Evolucao_Equipe (id_evolucao, id_membro, papel, nome_snapshot, crn_snapshot) "
                "VALUES (?, ?, ?, ?, ?)",
                (id_evolucao, integrante["id_membro"], integrante["funcao"], integrante["nome"], integrante["crn"]),
            )
        conn.execute(
            "UPDATE Pep_Rascunhos SET dados_json=?, status='fechada', id_evolucao=?, fechado_em=?, fechado_por=?, atualizado_em=? "
            "WHERE id_rascunho=?",
            (dados_json, id_evolucao, agora, int(id_usuario), agora, int(id_rascunho)),
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
