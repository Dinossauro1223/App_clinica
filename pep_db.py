# -*- coding: utf-8 -*-
"""Persistência do PEP nutricional. Requer migração v5 de db_migracoes.

As evoluções são append-only: correções devem ser registradas como adendos.
Pacientes são vinculados pelo ID do banco clínico, não por nome normalizado.
Senhas são armazenadas como PBKDF2-HMAC-SHA256; o SQLite não é criptografado.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime

import db_service as svc

_ITERACOES = 180_000
_TAMANHO_SALT = 16
_MAX_ASSINATURA = 2 * 1024 * 1024
_CHAVE_HOSPITAL = "senha_hospital_hash"


class PEPError(Exception):
    """Erro de operação do PEP."""


def _conectar(db_path):
    return svc.conectar(db_path, foreign_keys=True)


def _agora():
    return datetime.now().isoformat(timespec="seconds")


def _hash_senha(senha, salt_hex):
    salt = bytes.fromhex(salt_hex)
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, _ITERACOES).hex()


def _exigir_schema(conn):
    tabelas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    obrigatorias = {"Pep_Config", "Pep_Usuarios", "Pep_Evolucoes"}
    if not obrigatorias.issubset(tabelas):
        raise PEPError("Banco sem migração PEP v5. Feche e abra o programa para aplicar as migrações.")


def _config(conn, chave):
    row = conn.execute("SELECT valor FROM Pep_Config WHERE chave=?", (chave,)).fetchone()
    return row[0] if row else None


def _salvar_config(conn, chave, valor):
    conn.execute("INSERT INTO Pep_Config (chave, valor) VALUES (?, ?) "
                 "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (chave, valor))


def hospital_configurado(db_path):
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        return _config(conn, _CHAVE_HOSPITAL) is not None


def definir_senha_hospital(db_path, senha):
    if not isinstance(senha, str) or len(senha) < 8:
        raise ValueError("A senha institucional deve ter pelo menos 8 caracteres.")
    salt = secrets.token_hex(_TAMANHO_SALT)
    registro = json.dumps({"salt": salt, "hash": _hash_senha(senha, salt)})
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        _salvar_config(conn, _CHAVE_HOSPITAL, registro)
        conn.commit()


def entrar_hospital(db_path, senha):
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        registro = _config(conn, _CHAVE_HOSPITAL)
    if not registro:
        return False
    try:
        dados = json.loads(registro)
        tentativa = _hash_senha(str(senha), dados["salt"])
        return hmac.compare_digest(tentativa, dados["hash"])
    except (ValueError, KeyError, TypeError):
        return False


def criar_usuario(db_path, login, nome_completo, crn, senha, assinatura=None):
    login, nome_completo, crn = (str(v or "").strip() for v in (login, nome_completo, crn))
    if not login or not nome_completo or not crn:
        raise ValueError("Login, nome completo e CRN são obrigatórios.")
    if len(senha or "") < 8:
        raise ValueError("A senha individual deve ter pelo menos 8 caracteres.")
    if assinatura is not None and (not isinstance(assinatura, (bytes, bytearray)) or len(assinatura) > _MAX_ASSINATURA):
        raise ValueError("Assinatura deve ser um arquivo de imagem de até 2 MB.")
    salt = secrets.token_hex(_TAMANHO_SALT)
    digest = _hash_senha(senha, salt)
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        cur = conn.execute("INSERT INTO Pep_Usuarios (login, nome_completo, crn, salt, senha_hash, assinatura, criado_em) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (login, nome_completo, crn, salt, digest, bytes(assinatura) if assinatura is not None else None, _agora()))
        conn.commit()
        return cur.lastrowid


def autenticar(db_path, id_usuario, senha):
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        row = conn.execute("SELECT id_usuario, login, nome_completo, crn, salt, senha_hash, ativo "
                         "FROM Pep_Usuarios WHERE id_usuario=?", (int(id_usuario),)).fetchone()
    if not row or not row[6]:
        return None
    if not hmac.compare_digest(_hash_senha(str(senha), row[4]), row[5]):
        return None
    return {"id_usuario": row[0], "login": row[1], "nome_completo": row[2], "crn": row[3]}


def listar_usuarios(db_path, ativos=True):
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        sql = "SELECT id_usuario, login, nome_completo, crn, ativo FROM Pep_Usuarios"
        if ativos:
            sql += " WHERE ativo=1"
        sql += " ORDER BY nome_completo COLLATE NOCASE"
        return [{"id_usuario": r[0], "login": r[1], "nome_completo": r[2], "crn": r[3], "ativo": bool(r[4])}
                for r in conn.execute(sql)]


def desativar_usuario(db_path, id_usuario):
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        conn.execute("UPDATE Pep_Usuarios SET ativo=0 WHERE id_usuario=?", (int(id_usuario),))
        conn.commit()


def salvar_evolucao(db_path, id_paciente, paciente_nome, data_evolucao, cabecalho, texto, id_usuario, adendo_de=None):
    if isinstance(id_paciente, bool) or not isinstance(id_paciente, int) or id_paciente < 1:
        raise ValueError("Vínculo de paciente inválido: use o ID do cadastro clínico.")
    paciente_nome = str(paciente_nome or "").strip()
    texto = str(texto or "").strip()
    if not paciente_nome or not texto:
        raise ValueError("Nome do paciente e texto da evolução são obrigatórios.")
    try:
        data_iso = datetime.strptime(data_evolucao, "%d/%m/%Y").date().isoformat()
    except (TypeError, ValueError):
        raise ValueError("Data da evolução deve estar no formato DD/MM/AAAA.")
    if not isinstance(cabecalho, dict):
        raise ValueError("Cabeçalho da evolução deve ser um dicionário.")
    json_cabecalho = json.dumps(cabecalho, ensure_ascii=False, sort_keys=True)
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        paciente = conn.execute("SELECT id_paciente FROM Pacientes WHERE id_paciente=?", (id_paciente,)).fetchone()
        if not paciente:
            raise ValueError("Paciente não encontrado no cadastro clínico.")
        usuario = conn.execute("SELECT nome_completo, crn, ativo FROM Pep_Usuarios WHERE id_usuario=?", (int(id_usuario),)).fetchone()
        if not usuario or not usuario[2]:
            raise PEPError("Usuário profissional inexistente ou inativo.")
        if adendo_de is not None:
            anterior = conn.execute("SELECT id_paciente FROM Pep_Evolucoes WHERE id_evolucao=?", (int(adendo_de),)).fetchone()
            if not anterior or anterior[0] != id_paciente:
                raise ValueError("Adendo deve apontar para evolução do mesmo paciente.")
        cur = conn.execute("INSERT INTO Pep_Evolucoes (id_paciente, paciente_nome, data_evolucao, cabecalho_json, texto, "
                         "id_usuario, assinante_nome, assinante_crn, criada_em, adendo_de) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (id_paciente, paciente_nome, data_iso, json_cabecalho, texto, int(id_usuario),
                          usuario[0], usuario[1], _agora(), int(adendo_de) if adendo_de is not None else None))
        conn.commit()
        return cur.lastrowid


def _evolucao(row):
    data_exibicao = datetime.strptime(row[3], "%Y-%m-%d").strftime("%d/%m/%Y") if len(row[3]) == 10 and row[3][4] == "-" else row[3]
    return {"id_evolucao": row[0], "id_paciente": row[1], "paciente_nome": row[2], "data_evolucao": data_exibicao,
            "cabecalho": json.loads(row[4]), "texto": row[5], "id_usuario": row[6],
            "assinante": row[7], "crn": row[8], "criada_em": row[9], "adendo_de": row[10]}


def listar_evolucoes(db_path, id_paciente):
    with closing(_conectar(db_path)) as conn:
        _exigir_schema(conn)
        rows = conn.execute("SELECT id_evolucao, id_paciente, paciente_nome, data_evolucao, cabecalho_json, texto, id_usuario, "
                           "assinante_nome, assinante_crn, criada_em, adendo_de FROM Pep_Evolucoes "
                           "WHERE id_paciente=? ORDER BY data_evolucao DESC, id_evolucao DESC", (int(id_paciente),)).fetchall()
    return [_evolucao(r) for r in rows]


def ultima_evolucao(db_path, id_paciente):
    rows = listar_evolucoes(db_path, id_paciente)
    return next((r for r in rows if r["adendo_de"] is None), None)
