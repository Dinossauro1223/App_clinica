"""NutriLab Mobile - servidor da rede local (LAN). Somente biblioteca padrão do Python.

Criado em 12/11/2026. Descrição completa e contrato de dados: docs/mobile/INTEGRACAO_MOBILE.md
Uso:  python mobile/servidor.py [--porta 8765] [--db CAMINHO] [--redefinir-admin]
"""
import argparse
import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import sqlite3
import threading
import time
import traceback
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

AQUI = Path(__file__).resolve().parent
TZ = timezone(timedelta(hours=-3))  # America/Recife (sem horário de verão)
REFEICOES = ["desjejum", "colacao", "almoco", "lanche", "jantar", "ceia"]
ESTOQUES = ["almox", "cozinha", "copa"]
PERFIS = ["admin", "setor", "estoque_almox", "estoque_cozinha", "estoque_copa"]
# Hierarquia de abastecimento: de quem cada estoque pode receber.
ORIGENS = {"almox": ["externo"], "cozinha": ["almox"], "copa": ["cozinha", "almox"]}
LOCK = threading.Lock()
SESSOES, FALHAS = {}, {}

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios(id INTEGER PRIMARY KEY, login TEXT UNIQUE NOT NULL, nome TEXT NOT NULL,
  perfil TEXT NOT NULL, id_setor INTEGER, salt TEXT NOT NULL, senha TEXT NOT NULL, ativo INTEGER DEFAULT 1, criado_em TEXT);
CREATE TABLE IF NOT EXISTS setores(id INTEGER PRIMARY KEY, nome TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS leitos(id INTEGER PRIMARY KEY, id_setor INTEGER NOT NULL, codigo TEXT NOT NULL, UNIQUE(id_setor, codigo));
CREATE TABLE IF NOT EXISTS itens(id INTEGER PRIMARY KEY, nome TEXT UNIQUE NOT NULL, unidade TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS mapa_dia(data TEXT, id_leito INTEGER, ocupado INTEGER, acompanhante INTEGER, dieta TEXT,
  por_usuario INTEGER, por_perfil TEXT, atualizado_em TEXT, PRIMARY KEY(data, id_leito));
CREATE TABLE IF NOT EXISTS refeicoes_dia(data TEXT, id_setor INTEGER, refeicao TEXT, qtd REAL,
  por_usuario INTEGER, por_perfil TEXT, atualizado_em TEXT, PRIMARY KEY(data, id_setor, refeicao));
CREATE TABLE IF NOT EXISTS estoque_dia(data TEXT, estoque TEXT, id_item INTEGER, qtd REAL,
  por_usuario INTEGER, por_perfil TEXT, atualizado_em TEXT, PRIMARY KEY(data, estoque, id_item));
CREATE TABLE IF NOT EXISTS movimentos(id INTEGER PRIMARY KEY, data TEXT, hora TEXT, origem TEXT, destino TEXT,
  id_item INTEGER, qtd REAL, por_usuario INTEGER, divergente INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS correcoes(id INTEGER PRIMARY KEY, tipo TEXT, data TEXT, chave TEXT, rotulo TEXT,
  valor_atual TEXT, valor_proposto TEXT, por_usuario INTEGER, criado_em TEXT, status TEXT DEFAULT 'pendente', decidido_em TEXT);
"""


class Erro(Exception):
    def __init__(self, msg, cod=400):
        super().__init__(msg)
        self.msg, self.cod = msg, cod


# ------------------------------------------------------------------ utilidades
def hoje():
    return datetime.now(TZ).date().isoformat()


def agora():
    return datetime.now(TZ).isoformat(timespec="seconds")


def num(v, nome="valor"):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise Erro("Número inválido em %s." % nome)
    if not 0 <= x <= 1e9:
        raise Erro("Valor fora do limite em %s." % nome)
    return x


def dia_valido(txt):
    try:
        return date.fromisoformat(str(txt)).isoformat()
    except ValueError:
        raise Erro("Data inválida (use AAAA-MM-DD).")


def hash_senha(senha, salt):
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(salt), 200_000).hex()


def conectar(db):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c


def definir_senha(c, uid, senha):
    if len(str(senha)) < 6:
        raise Erro("A senha precisa ter pelo menos 6 caracteres.")
    salt = secrets.token_hex(16)
    c.execute("UPDATE usuarios SET salt=?, senha=? WHERE id=?", (salt, hash_senha(str(senha), salt), uid))


def criar_usuario(c, login, nome, perfil, id_setor, senha):
    login = str(login).strip().lower()
    if not login or not str(nome).strip():
        raise Erro("Informe login e nome.")
    if perfil not in PERFIS:
        raise Erro("Perfil inválido.")
    if perfil == "setor" and not c.execute("SELECT 1 FROM setores WHERE id=?", (id_setor,)).fetchone():
        raise Erro("Escolha o setor do usuário.")
    try:
        c.execute("INSERT INTO usuarios(login,nome,perfil,id_setor,salt,senha,criado_em) VALUES(?,?,?,?,'','',?)",
                  (login, str(nome).strip(), perfil, id_setor if perfil == "setor" else None, agora()))
    except sqlite3.IntegrityError:
        raise Erro("Esse login já existe.")
    definir_senha(c, c.execute("SELECT id FROM usuarios WHERE login=?", (login,)).fetchone()["id"], senha)


def preparar_banco(db, redefinir=False):
    """Cria o banco e o usuário 'admin'. Devolve a senha gerada (ou None se o admin já existia)."""
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    c = conectar(db)
    c.executescript(ESQUEMA)
    adm = c.execute("SELECT id FROM usuarios WHERE login='admin'").fetchone()
    senha = None
    if adm is None or redefinir:
        senha = secrets.token_urlsafe(8)
        if adm is None:
            criar_usuario(c, "admin", "Administrador", "admin", None, senha)
        else:
            definir_senha(c, adm["id"], senha)
    c.commit()
    c.close()
    return senha


def pub(u):
    est = u["perfil"][8:] if u["perfil"].startswith("estoque_") else None
    return {"id": u["id"], "nome": u["nome"], "perfil": u["perfil"], "id_setor": u["id_setor"], "estoque": est}


# --------------------------------------------------------------- autenticação
def login(c, ip, b):
    falhas = [t for t in FALHAS.get(ip, []) if t > time.time() - 300]
    if len(falhas) >= 8:
        raise Erro("Muitas tentativas. Aguarde alguns minutos.", 429)
    r = c.execute("SELECT * FROM usuarios WHERE login=? AND ativo=1", (str(b.get("login", "")).strip().lower(),)).fetchone()
    if not r or not hmac.compare_digest(r["senha"], hash_senha(str(b.get("senha", "")), r["salt"])):
        FALHAS[ip] = falhas + [time.time()]
        raise Erro("Login ou senha incorretos.", 401)
    tok = secrets.token_urlsafe(24)
    SESSOES[tok] = (r["id"], time.time() + 12 * 3600)
    return {"token": tok, "usuario": pub(dict(r)), "hoje": hoje()}


def usuario(c, auth):
    s = SESSOES.get(auth[7:] if auth.startswith("Bearer ") else "")
    if not s or s[1] < time.time():
        raise Erro("Sessão expirada. Entre novamente.", 401)
    r = c.execute("SELECT * FROM usuarios WHERE id=? AND ativo=1", (s[0],)).fetchone()
    if not r:
        raise Erro("Usuário desativado.", 401)
    return dict(r)


def setor_alvo(c, u, pedido):
    if u["perfil"] == "admin":
        if not pedido:
            raise Erro("Escolha o setor.")
        sid = int(pedido)
    elif u["perfil"] == "setor":
        sid = u["id_setor"]
    else:
        raise Erro("Sem permissão para este setor.", 403)
    s = c.execute("SELECT * FROM setores WHERE id=?", (sid,)).fetchone()
    if not s:
        raise Erro("Setor não encontrado.", 404)
    return dict(s)


def estoque_alvo(u, pedido):
    est = pedido if u["perfil"] == "admin" else (u["perfil"][8:] if u["perfil"].startswith("estoque_") else None)
    if est not in ESTOQUES:
        raise Erro("Sem permissão para este estoque.", 403)
    return est


def dia_alvo(u, pedido):
    """Usuários comuns só mexem no PRÓPRIO DIA (data do servidor); só o admin escolhe a data."""
    return dia_valido(pedido) if (u["perfil"] == "admin" and pedido) else hoje()


# ------------------------------------------- gravação com alerta de correção
def atual(c, tipo, data, chave):
    if tipo == "mapa":
        r = c.execute("SELECT ocupado,acompanhante,dieta,por_perfil FROM mapa_dia WHERE data=? AND id_leito=?", (data, int(chave)))
    elif tipo == "refeicao":
        sid, ref = chave.split("|")
        r = c.execute("SELECT qtd,por_perfil FROM refeicoes_dia WHERE data=? AND id_setor=? AND refeicao=?", (data, int(sid), ref))
    else:
        est, iid = chave.split("|")
        r = c.execute("SELECT qtd,por_perfil FROM estoque_dia WHERE data=? AND estoque=? AND id_item=?", (data, est, int(iid)))
    r = r.fetchone()
    return dict(r) if r else None


def gravar(c, tipo, data, chave, v, uid, perfil):
    t = agora()
    if tipo == "mapa":
        c.execute("INSERT INTO mapa_dia VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(data,id_leito) DO UPDATE SET ocupado=excluded.ocupado,"
                  "acompanhante=excluded.acompanhante,dieta=excluded.dieta,por_usuario=excluded.por_usuario,"
                  "por_perfil=excluded.por_perfil,atualizado_em=excluded.atualizado_em",
                  (data, int(chave), v["ocupado"], v["acompanhante"], v["dieta"], uid, perfil, t))
    else:
        tab, cols = ("refeicoes_dia", "id_setor,refeicao") if tipo == "refeicao" else ("estoque_dia", "estoque,id_item")
        a, b = chave.split("|")
        a = int(a) if tipo == "refeicao" else a
        b = b if tipo == "refeicao" else int(b)
        c.execute("INSERT INTO %s VALUES(?,?,?,?,?,?,?) ON CONFLICT(data,%s) DO UPDATE SET qtd=excluded.qtd,"
                  "por_usuario=excluded.por_usuario,por_perfil=excluded.por_perfil,atualizado_em=excluded.atualizado_em" % (tab, cols),
                  (data, a, b, v["qtd"], uid, perfil, t))


def salvar(c, u, tipo, data, chave, rotulo, novo):
    """Devolve 'ok', 'igual' ou 'pendente'. Se o ADMIN já atualizou este dado no dia e um usuário comum
    manda valor diferente, nada é sobrescrito: nasce uma correção pendente para o admin aprovar ou recusar."""
    a = atual(c, tipo, data, chave)
    if a:
        por = a.pop("por_perfil")
        if all(a.get(k) == v for k, v in novo.items()):
            c.execute("UPDATE correcoes SET status='substituida' WHERE tipo=? AND data=? AND chave=? AND status='pendente'", (tipo, data, chave))
            return "igual"
        if por == "admin" and u["perfil"] != "admin":
            c.execute("UPDATE correcoes SET status='substituida' WHERE tipo=? AND data=? AND chave=? AND status='pendente'", (tipo, data, chave))
            c.execute("INSERT INTO correcoes(tipo,data,chave,rotulo,valor_atual,valor_proposto,por_usuario,criado_em) VALUES(?,?,?,?,?,?,?,?)",
                      (tipo, data, chave, rotulo, json.dumps(a), json.dumps(novo), u["id"], agora()))
            return "pendente"
    gravar(c, tipo, data, chave, novo, u["id"], u["perfil"])
    return "ok"


def pendentes(c, tipo, data):
    return [r[0] for r in c.execute("SELECT chave FROM correcoes WHERE tipo=? AND data=? AND status='pendente'", (tipo, data))]


# ----------------------------------------- leituras (já com a base do dia anterior)
def linhas_mapa(c, sid, d):
    sql = ("SELECT l.id id_leito,l.codigo,COALESCE(h.ocupado,0) ocupado,COALESCE(h.acompanhante,0) acompanhante,"
           "COALESCE(h.dieta,'') dieta,h.data data_base,h.por_perfil,h.atualizado_em FROM leitos l "
           "LEFT JOIN mapa_dia h ON h.id_leito=l.id AND h.data=(SELECT MAX(data) FROM mapa_dia WHERE id_leito=l.id AND data<=?) "
           "WHERE l.id_setor=? ORDER BY l.codigo")
    return [{**dict(r), "herdado": r["data_base"] not in (None, d)} for r in c.execute(sql, (d, sid))]


def linhas_refeicoes(c, sid, d):
    out = []
    for ref in REFEICOES:
        r = c.execute("SELECT qtd,data data_base,por_perfil,atualizado_em FROM refeicoes_dia WHERE id_setor=? AND refeicao=? AND data<=? "
                      "ORDER BY data DESC LIMIT 1", (sid, ref, d)).fetchone()
        x = dict(r) if r else {"qtd": 0, "data_base": None, "por_perfil": None, "atualizado_em": None}
        out.append({**x, "refeicao": ref, "herdado": bool(r) and r["data_base"] != d})
    return out


def linhas_estoque(c, est, d):
    sql = ("SELECT i.id id_item,i.nome,i.unidade,COALESCE(h.qtd,0) qtd,h.data data_base,h.por_perfil,h.atualizado_em FROM itens i "
           "LEFT JOIN estoque_dia h ON h.id_item=i.id AND h.estoque=? AND "
           "h.data=(SELECT MAX(data) FROM estoque_dia WHERE id_item=i.id AND estoque=? AND data<=?) ORDER BY i.nome")
    return [{**dict(r), "herdado": r["data_base"] not in (None, d)} for r in c.execute(sql, (est, est, d))]


def saldo(c, est, iid, d):
    r = c.execute("SELECT qtd FROM estoque_dia WHERE estoque=? AND id_item=? AND data<=? ORDER BY data DESC LIMIT 1", (est, iid, d)).fetchone()
    return r["qtd"] if r else 0.0


# ------------------------------------------------------------ operações (POST)
def post_mapa(c, u, s, d, leitos):
    cods = {r["id"]: r["codigo"] for r in c.execute("SELECT id,codigo FROM leitos WHERE id_setor=?", (s["id"],))}
    res = {"ok": 0, "igual": 0, "pendente": 0}
    for l in leitos:
        lid = int(l["id_leito"])
        if lid not in cods:
            raise Erro("Leito de outro setor.", 403)
        n = {"ocupado": int(bool(l.get("ocupado"))), "acompanhante": int(bool(l.get("acompanhante"))), "dieta": str(l.get("dieta", ""))[:60]}
        if not n["ocupado"]:
            n["acompanhante"], n["dieta"] = 0, ""
        res[salvar(c, u, "mapa", d, str(lid), "Leito %s (%s)" % (cods[lid], s["nome"]), n)] += 1
    return res


def post_refeicoes(c, u, s, d, itens):
    res = {"ok": 0, "igual": 0, "pendente": 0}
    for i in itens:
        if i["refeicao"] not in REFEICOES:
            raise Erro("Refeição inválida.")
        res[salvar(c, u, "refeicao", d, "%d|%s" % (s["id"], i["refeicao"]), "%s - %s" % (s["nome"], i["refeicao"]),
                   {"qtd": num(i["qtd"], i["refeicao"])})] += 1
    return res


def post_estoque(c, u, est, d, itens):
    nomes = {r["id"]: r["nome"] for r in c.execute("SELECT id,nome FROM itens")}
    res = {"ok": 0, "igual": 0, "pendente": 0}
    for i in itens:
        iid = int(i["id_item"])
        if iid not in nomes:
            raise Erro("Item inexistente.")
        res[salvar(c, u, "estoque", d, "%s|%d" % (est, iid), "%s (%s)" % (nomes[iid], est), {"qtd": num(i["qtd"], nomes[iid])})] += 1
    return res


def mover(c, u, est, iid, qtd, d):
    """Ajuste de saldo por reposição: se o admin já tinha atualizado o dia, a marca de 'admin' é mantida."""
    a = atual(c, "estoque", d, "%s|%d" % (est, iid))
    gravar(c, "estoque", d, "%s|%d" % (est, iid), {"qtd": qtd}, u["id"], "admin" if a and a["por_perfil"] == "admin" else u["perfil"])


def post_reposicao(c, u, est, b):
    iid, qtd, org, d = int(b["id_item"]), num(b["qtd"], "quantidade"), b.get("origem"), hoje()
    if qtd <= 0 or not c.execute("SELECT 1 FROM itens WHERE id=?", (iid,)).fetchone():
        raise Erro("Informe um item e uma quantidade maior que zero.")
    if org not in ORIGENS[est]:
        raise Erro("O estoque da %s só pode receber de: %s." % (est, ", ".join(ORIGENS[est])))
    if est == "copa" and org == "almox":
        disp = saldo(c, "cozinha", iid, d)
        if disp > 0:
            raise Erro("A cozinha ainda tem %g: pegue primeiro da cozinha e só o restante no almoxarifado." % disp)
    div = 0
    if org != "externo":
        so = saldo(c, org, iid, d)
        div = int(so < qtd)  # saldo da origem menor que o retirado: contagem da origem está desatualizada
        mover(c, u, org, iid, max(0.0, so - qtd), d)
    novo = saldo(c, est, iid, d) + qtd
    mover(c, u, est, iid, novo, d)
    c.execute("INSERT INTO movimentos(data,hora,origem,destino,id_item,qtd,por_usuario,divergente) VALUES(?,?,?,?,?,?,?,?)",
              (d, agora(), org, est, iid, qtd, u["id"], div))
    return {"ok": True, "saldo": novo, "divergente": bool(div)}


# ----------------------------------------------------------------------- admin
def painel(c, d):
    out = {"data": d, "setores": [], "estoques": [], "pendentes": c.execute("SELECT COUNT(*) FROM correcoes WHERE status='pendente'").fetchone()[0],
           "divergencias": c.execute("SELECT COUNT(*) FROM movimentos WHERE data=? AND divergente=1", (d,)).fetchone()[0]}
    for s in c.execute("SELECT id,nome FROM setores ORDER BY nome").fetchall():
        ls = linhas_mapa(c, s["id"], d)
        out["setores"].append({"id": s["id"], "nome": s["nome"], "leitos": len(ls), "ocupados": sum(l["ocupado"] for l in ls),
                               "mapa_atualizado": any(l["data_base"] == d for l in ls),
                               "refeicoes": sum(r["qtd"] for r in linhas_refeicoes(c, s["id"], d) if r["data_base"] == d)})
    n_itens = c.execute("SELECT COUNT(*) FROM itens").fetchone()[0]
    for e in ESTOQUES:
        r = c.execute("SELECT COUNT(*), MAX(atualizado_em) FROM estoque_dia WHERE data=? AND estoque=?", (d, e)).fetchone()
        out["estoques"].append({"estoque": e, "atualizados": r[0], "itens": n_itens, "ultima": r[1]})
    return out


def lista_correcoes(c, status):
    rs = c.execute("SELECT k.*,u.nome usuario FROM correcoes k JOIN usuarios u ON u.id=k.por_usuario WHERE k.status=? ORDER BY k.id", (status,))
    return [{**dict(r), "valor_atual": json.loads(r["valor_atual"]), "valor_proposto": json.loads(r["valor_proposto"])} for r in rs]


def decidir(c, u, cid, acao):
    k = c.execute("SELECT * FROM correcoes WHERE id=? AND status='pendente'", (cid,)).fetchone()
    if not k:
        raise Erro("Correção não encontrada ou já decidida.", 404)
    if acao not in ("aprovar", "recusar"):
        raise Erro("Ação inválida.")
    if acao == "aprovar":  # valor aprovado passa a valer como valor do administrador
        gravar(c, k["tipo"], k["data"], k["chave"], json.loads(k["valor_proposto"]), u["id"], "admin")
    c.execute("UPDATE correcoes SET status=?, decidido_em=? WHERE id=?", ("aprovada" if acao == "aprovar" else "recusada", agora(), cid))
    return {"ok": True}


def criar_setor(c, b):
    if b.get("id_setor"):
        sid = int(b["id_setor"])
    else:
        nome = str(b.get("nome", "")).strip()
        if not nome:
            raise Erro("Informe o nome do setor.")
        try:
            sid = c.execute("INSERT INTO setores(nome) VALUES(?)", (nome,)).lastrowid
        except sqlite3.IntegrityError:
            raise Erro("Esse setor já existe.")
    cods = [str(x).strip() for x in b.get("codigos", []) if str(x).strip()]
    if b.get("fim"):
        ini, fim, w = int(b.get("inicio", 1)), int(b["fim"]), int(b.get("largura", 2))
        if not 0 <= fim - ini < 200:
            raise Erro("Sequência de leitos inválida.")
        cods += ["%s%0*d" % (b.get("prefixo", ""), w, n) for n in range(ini, fim + 1)]
    for cod in cods:
        c.execute("INSERT OR IGNORE INTO leitos(id_setor,codigo) VALUES(?,?)", (sid, cod))
    return {"id": sid, "leitos_informados": len(cods)}


def exportar(c, d):
    def t(sql, *a):
        return [dict(r) for r in c.execute(sql, a)]
    return {"esquema": 1, "data": d, "gerado_em": agora(), "setores": t("SELECT * FROM setores"), "leitos": t("SELECT * FROM leitos"),
            "itens": t("SELECT * FROM itens"), "mapa": t("SELECT * FROM mapa_dia WHERE data=?", d),
            "refeicoes": t("SELECT * FROM refeicoes_dia WHERE data=?", d), "estoque": t("SELECT * FROM estoque_dia WHERE data=?", d),
            "movimentos": t("SELECT * FROM movimentos WHERE data=?", d), "correcoes_pendentes": lista_correcoes(c, "pendente")}


# ---------------------------------------------------------------------- rotas
def _rotear(c, ip, m, p, q, b, auth):
    if (m, p) == ("POST", "/api/login"):
        return login(c, ip, b)
    u = usuario(c, auth)
    adm = u["perfil"] == "admin"
    if (m, p) == ("GET", "/api/eu"):
        return {"usuario": pub(u), "hoje": hoje()}
    if (m, p) == ("GET", "/api/itens"):
        return {"itens": [dict(r) for r in c.execute("SELECT id,nome,unidade FROM itens ORDER BY nome")]}
    if (m, p) == ("GET", "/api/setores"):
        sql = "SELECT s.id,s.nome,(SELECT COUNT(*) FROM leitos WHERE id_setor=s.id) leitos FROM setores s %s ORDER BY s.nome"
        return {"setores": [dict(r) for r in c.execute(sql % ("" if adm else "WHERE s.id=%d" % (u["id_setor"] or 0)))]}
    if p in ("/api/mapa", "/api/refeicoes"):
        s, d = setor_alvo(c, u, q.get("setor") or b.get("setor")), dia_alvo(u, q.get("data") or b.get("data"))
        tipo, lin, post = ("mapa", linhas_mapa, post_mapa) if p == "/api/mapa" else ("refeicao", linhas_refeicoes, post_refeicoes)
        if m == "GET":
            return {"data": d, "setor": s, "linhas": lin(c, s["id"], d), "pendentes": pendentes(c, tipo, d)}
        return post(c, u, s, d, b.get("linhas", []))
    if p == "/api/estoque":
        est, d = estoque_alvo(u, q.get("estoque") or b.get("estoque")), dia_alvo(u, q.get("data") or b.get("data"))
        if m == "GET":
            origens = {o: {l["id_item"]: l["qtd"] for l in linhas_estoque(c, o, d)} for o in ORIGENS[est] if o != "externo"}
            return {"data": d, "estoque": est, "origens": ORIGENS[est], "saldos_origem": origens,
                    "linhas": linhas_estoque(c, est, d), "pendentes": pendentes(c, "estoque", d)}
        return post_estoque(c, u, est, d, b.get("linhas", []))
    if (m, p) == ("POST", "/api/estoque/reposicao"):
        return post_reposicao(c, u, estoque_alvo(u, b.get("estoque")), b)
    if p.startswith("/api/admin/"):
        if not adm:
            raise Erro("Somente o administrador.", 403)
        d = dia_alvo(u, q.get("data") or b.get("data"))
        if (m, p) == ("GET", "/api/admin/painel"):
            return painel(c, d)
        if (m, p) == ("GET", "/api/admin/exportar"):
            return exportar(c, d)
        if (m, p) == ("GET", "/api/admin/correcoes"):
            return {"correcoes": lista_correcoes(c, q.get("status", "pendente"))}
        if m == "POST" and p.startswith("/api/admin/correcoes/"):
            return decidir(c, u, int(p.rsplit("/", 1)[1]), b.get("acao"))
        if (m, p) == ("GET", "/api/admin/usuarios"):
            return {"usuarios": [{k: r[k] for k in ("id", "login", "nome", "perfil", "id_setor", "ativo")} for r in c.execute("SELECT * FROM usuarios ORDER BY login")]}
        if (m, p) == ("POST", "/api/admin/usuarios"):
            criar_usuario(c, b.get("login"), b.get("nome"), b.get("perfil"), b.get("id_setor"), b.get("senha", ""))
            return {"ok": True}
        if m == "POST" and p.startswith("/api/admin/usuarios/"):
            uid = int(p.rsplit("/", 1)[1])
            if "ativo" in b:
                if uid == u["id"] and not b["ativo"]:
                    raise Erro("Você não pode desativar o próprio usuário.")
                c.execute("UPDATE usuarios SET ativo=? WHERE id=?", (int(bool(b["ativo"])), uid))
            if b.get("senha"):
                definir_senha(c, uid, b["senha"])
            return {"ok": True}
        if (m, p) == ("POST", "/api/admin/setores"):
            return criar_setor(c, b)
        if (m, p) == ("POST", "/api/admin/itens"):
            try:
                c.execute("INSERT INTO itens(nome,unidade) VALUES(?,?)", (str(b.get("nome", "")).strip(), str(b.get("unidade", "un")).strip() or "un"))
            except sqlite3.IntegrityError:
                raise Erro("Esse item já existe.")
            return {"ok": True}
    raise Erro("Rota não encontrada.", 404)


def rotear(db, ip, m, p, q, b, auth):
    with LOCK:
        c = conectar(db)
        try:
            r = _rotear(c, ip, m, p, q, b, auth)
            c.commit()
            return r
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()


class Manipulador(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _enviar(self, cod, corpo, tipo="application/json; charset=utf-8"):
        if not isinstance(corpo, bytes):
            corpo = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(cod)
        for k, v in (("Content-Type", tipo), ("Content-Length", str(len(corpo))), ("Cache-Control", "no-store"),
                     ("X-Content-Type-Options", "nosniff"), ("X-Frame-Options", "DENY")):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def _tratar(self, m):
        try:
            if not ipaddress.ip_address(self.client_address[0]).is_private:
                raise Erro("Acesso permitido somente pela rede local.", 403)
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            if m == "GET" and not u.path.startswith("/api/"):
                return self._enviar(200, (AQUI / "static" / "index.html").read_bytes(), "text/html; charset=utf-8")
            b = {}
            if m == "POST":
                n = min(int(self.headers.get("Content-Length") or 0), 1_000_000)
                b = json.loads(self.rfile.read(n) or b"{}")
            self._enviar(200, rotear(self.server.db, self.client_address[0], m, u.path, q, b, self.headers.get("Authorization", "")))
        except Erro as e:
            self._enviar(e.cod, {"erro": e.msg})
        except (ValueError, KeyError, TypeError) as e:
            self._enviar(400, {"erro": "Dados inválidos (%s)." % e})
        except Exception:
            traceback.print_exc()
            self._enviar(500, {"erro": "Erro interno do servidor."})

    def do_GET(self):
        self._tratar("GET")

    def do_POST(self):
        self._tratar("POST")


def criar_servidor(db, porta=0, host="127.0.0.1"):
    srv = ThreadingHTTPServer((host, porta), Manipulador)
    srv.db = str(db)
    return srv


def ip_lan():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser(description="NutriLab Mobile - servidor da rede local")
    ap.add_argument("--porta", type=int, default=8765)
    ap.add_argument("--db", default=str(AQUI / "dados" / "mobile.db"))
    ap.add_argument("--redefinir-admin", action="store_true", help="gera uma nova senha para o usuário admin")
    a = ap.parse_args()
    senha = preparar_banco(a.db, a.redefinir_admin)
    srv = criar_servidor(a.db, a.porta, "0.0.0.0")
    print("NutriLab Mobile no ar. Banco: %s" % a.db)
    if senha:
        print("\n  USUÁRIO: admin    SENHA: %s    (anote agora: não será mostrada de novo)\n" % senha)
    print("  Administrador (este computador): http://localhost:%d" % a.porta)
    print("  Celulares (mesma rede/Wi-Fi):    http://%s:%d" % (ip_lan(), a.porta))
    print("  Feche esta janela (ou Ctrl+C) para desligar.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("Servidor encerrado.")


if __name__ == "__main__":
    main()
