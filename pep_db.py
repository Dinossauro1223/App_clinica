# -*- coding: utf-8 -*-
"""Acesso ao PEP: senha do hospital, usuários (nome completo, CRN, assinatura) e evoluções assinadas.

Evolução assinada é imutável (gatilhos bloqueiam UPDATE/DELETE); correção = novo registro com adendo_de.
Senhas: PBKDF2-SHA256 com sal. Assinatura (imagem) fica só no banco, nunca no Git."""
import hashlib
import hmac
import json
import os
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime

ESQUEMA = """
CREATE TABLE IF NOT EXISTS Config_PEP(chave TEXT PRIMARY KEY, sal BLOB NOT NULL, hash BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS Usuarios_PEP(id INTEGER PRIMARY KEY, login TEXT UNIQUE NOT NULL, nome_completo TEXT NOT NULL,
  crn TEXT NOT NULL, assinatura BLOB, sal BLOB NOT NULL, senha_hash BLOB NOT NULL, ativo INTEGER NOT NULL DEFAULT 1,
  criado_em TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS Evolucoes_PEP(id INTEGER PRIMARY KEY, paciente TEXT NOT NULL, paciente_nome TEXT NOT NULL,
  data_evolucao TEXT NOT NULL, cabecalho TEXT NOT NULL, texto TEXT NOT NULL,
  usuario_id INTEGER NOT NULL REFERENCES Usuarios_PEP(id), assinado_em TEXT NOT NULL,
  adendo_de INTEGER REFERENCES Evolucoes_PEP(id));
CREATE INDEX IF NOT EXISTS ix_evolucoes_paciente ON Evolucoes_PEP(paciente, id);
CREATE TRIGGER IF NOT EXISTS evolucao_imutavel_upd BEFORE UPDATE ON Evolucoes_PEP
  BEGIN SELECT RAISE(ABORT, 'Evolução assinada é imutável: registre um adendo.'); END;
CREATE TRIGGER IF NOT EXISTS evolucao_imutavel_del BEFORE DELETE ON Evolucoes_PEP
  BEGIN SELECT RAISE(ABORT, 'Evolução assinada não pode ser apagada.'); END;
"""


@contextmanager
def _con(db):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    c.executescript(ESQUEMA)
    try:
        yield c
        c.commit()
    finally:
        c.close()


def _hash(senha, sal):
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, 200_000)


def _confere(senha, sal, esperado):
    return hmac.compare_digest(_hash(senha, sal), esperado)


def chave_paciente(nome):
    """Nome sem acento/caixa/espaços repetidos: 'José  Silva' e 'jose silva' são o mesmo paciente."""
    s = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def hospital_configurado(db):
    with _con(db) as c:
        return c.execute("SELECT 1 FROM Config_PEP WHERE chave='hospital'").fetchone() is not None


def definir_senha_hospital(db, senha):
    if len(senha) < 6:
        raise ValueError("Use ao menos 6 caracteres na senha do hospital.")
    if hospital_configurado(db):
        raise ValueError("A senha do hospital já foi definida.")
    sal = os.urandom(16)
    with _con(db) as c:
        c.execute("INSERT INTO Config_PEP VALUES('hospital', ?, ?)", (sal, _hash(senha, sal)))


def entrar_hospital(db, senha):
    with _con(db) as c:
        r = c.execute("SELECT sal, hash FROM Config_PEP WHERE chave='hospital'").fetchone()
    return bool(r) and _confere(senha, r["sal"], r["hash"])


def criar_usuario(db, login, nome, crn, senha, assinatura=None):
    login, nome, crn = login.strip().lower(), nome.strip(), crn.strip()
    if not (login and nome and crn):
        raise ValueError("Informe nome completo, CRN e login.")
    if len(senha) < 6:
        raise ValueError("Use ao menos 6 caracteres na senha.")
    sal = os.urandom(16)
    try:
        with _con(db) as c:
            return c.execute("INSERT INTO Usuarios_PEP(login, nome_completo, crn, assinatura, sal, senha_hash, criado_em)"
                             " VALUES(?,?,?,?,?,?,?)", (login, nome, crn, assinatura, sal, _hash(senha, sal),
                                                        datetime.now().isoformat(timespec="seconds"))).lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("Já existe um usuário com esse login.")


def listar_usuarios(db):
    with _con(db) as c:
        return [dict(r) for r in c.execute(
            "SELECT id, login, nome_completo, crn FROM Usuarios_PEP WHERE ativo=1 ORDER BY nome_completo")]


def autenticar(db, usuario_id, senha):
    """Devolve o usuário (com a assinatura em bytes) ou None se a senha estiver errada."""
    with _con(db) as c:
        r = c.execute("SELECT * FROM Usuarios_PEP WHERE id=? AND ativo=1", (usuario_id,)).fetchone()
    if r and _confere(senha, r["sal"], r["senha_hash"]):
        return {k: r[k] for k in ("id", "login", "nome_completo", "crn", "assinatura")}
    return None


def ultima_evolucao(db, paciente):
    """Última evolução (não adendo) do paciente ou None — origem do cabeçalho da próxima evolução."""
    with _con(db) as c:
        r = c.execute("SELECT e.*, u.nome_completo FROM Evolucoes_PEP e JOIN Usuarios_PEP u ON u.id=e.usuario_id "
                      "WHERE e.paciente=? AND e.adendo_de IS NULL ORDER BY e.id DESC LIMIT 1",
                      (chave_paciente(paciente),)).fetchone()
    if not r:
        return None
    return {"id": r["id"], "data": r["data_evolucao"], "cabecalho": json.loads(r["cabecalho"]),
            "texto": r["texto"], "assinante": r["nome_completo"]}


def salvar_evolucao(db, paciente, data_evolucao, cabecalho, texto, usuario_id, adendo_de=None):
    with _con(db) as c:
        return c.execute("INSERT INTO Evolucoes_PEP(paciente, paciente_nome, data_evolucao, cabecalho, texto, usuario_id,"
                         " assinado_em, adendo_de) VALUES(?,?,?,?,?,?,?,?)",
                         (chave_paciente(paciente), paciente.strip(), data_evolucao, json.dumps(cabecalho), texto,
                          usuario_id, datetime.now().isoformat(timespec="seconds"), adendo_de)).lastrowid
