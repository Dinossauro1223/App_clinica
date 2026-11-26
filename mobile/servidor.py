"""NutriLab Mobile - servidor da rede local (LAN). Somente biblioteca padrão do Python.

Criado em 12/11/2026 (revisado no mesmo dia: nutricionista, mapa com paciente e publicação, avisos, janelas de refeição).
Descrição completa e contrato de dados: docs/mobile/INTEGRACAO_MOBILE.md
Uso:  python mobile/servidor.py [--porta 8765] [--db CAMINHO] [--redefinir-admin]
"""
import argparse
import hashlib
import hmac
import ipaddress
import json
import mimetypes
import re
import secrets
import socket
import sqlite3
import sys
import threading
import time
import traceback
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import refeicoes_db as refeicoes_operacionais
TZ = timezone(timedelta(hours=-3))  # America/Recife (sem horário de verão)
REFEICOES = ["desjejum", "colacao", "almoco", "lanche", "jantar", "ceia"]
ESTOQUES = ["almox", "cozinha", "copa"]
PERFIS = ["admin", "nutricionista", "copa", "estoque_cozinha", "estoque_almox"]
STAFF = ("admin", "nutricionista")  # escolhem o dia; o que gravam só muda com autorização deles quando a copa discorda
EST_PERFIL = {"copa": "copa", "estoque_cozinha": "cozinha", "estoque_almox": "almox"}
# Hierarquia de abastecimento: de quem cada estoque pode receber.
ORIGENS = {"almox": ["externo", "cozinha"], "cozinha": ["almox"], "copa": ["cozinha", "almox"]}
CAMPOS = ["id_paciente", "id_ocupacao", "nome", "idade_anos", "idade_meses", "dieta", "diagnostico", "pref_sim", "pref_nao",
          "acompanhante", "cor", "consistencia", "via", "dm", "has", "laxativa", "constipante", "drc", "suplementos_json"]
# Refeições conferidas hoje: almoço e jantar. As demais ficam desligadas até o administrador habilitar (com horário).
CFG_INICIAL = [("desjejum", 0, None, None), ("colacao", 0, None, None), ("almoco", 1, "09:00", "16:00"),
               ("lanche", 0, None, None), ("jantar", 1, "16:00", "22:00"), ("ceia", 0, None, None)]
LOCK = threading.Lock()
SESSOES, FALHAS = {}, {}
SENHA_ADMIN_INICIAL = "123456789"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS sistema_config(chave TEXT PRIMARY KEY, valor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS operacoes_idempotentes(
  operation_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, resultado_json TEXT NOT NULL, criado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_operacoes_idempotentes_criado ON operacoes_idempotentes(criado_em);
CREATE TABLE IF NOT EXISTS usuarios(id INTEGER PRIMARY KEY, login TEXT UNIQUE NOT NULL, nome TEXT NOT NULL,
  perfil TEXT NOT NULL, id_setor INTEGER, salt TEXT NOT NULL, senha TEXT NOT NULL, ativo INTEGER DEFAULT 1, criado_em TEXT);
CREATE TABLE IF NOT EXISTS setores(id INTEGER PRIMARY KEY, nome TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS leitos(id INTEGER PRIMARY KEY, id_setor INTEGER NOT NULL, codigo TEXT NOT NULL, UNIQUE(id_setor, codigo));
CREATE TABLE IF NOT EXISTS itens(id INTEGER PRIMARY KEY, nome TEXT UNIQUE NOT NULL, unidade TEXT NOT NULL,
  preco_unitario REAL, embalagem_qtd REAL, embalagem_un TEXT, tbca_id TEXT,
  categoria TEXT NOT NULL DEFAULT 'Gêneros alimentícios', validade TEXT);
CREATE TABLE IF NOT EXISTS mapa_dia(data TEXT, id_leito INTEGER, id_paciente INTEGER, id_ocupacao TEXT, ocupado INTEGER, acompanhante INTEGER, dieta TEXT, nome TEXT,
  idade_anos INTEGER, idade_meses INTEGER, diagnostico TEXT, pref_sim TEXT, pref_nao TEXT,
  cor TEXT, consistencia TEXT, via TEXT, dm INTEGER DEFAULT 0, has INTEGER DEFAULT 0, laxativa INTEGER DEFAULT 0,
  constipante INTEGER DEFAULT 0, drc INTEGER DEFAULT 0, suplementos_json TEXT DEFAULT '[]',
  por_usuario INTEGER, por_perfil TEXT, atualizado_em TEXT, PRIMARY KEY(data, id_leito));
CREATE TABLE IF NOT EXISTS suplementos_catalogo(
  id_suplemento INTEGER PRIMARY KEY, nome TEXT NOT NULL, modulo TEXT, emb_qtd REAL, emb_un TEXT,
  kcal_100 REAL, ptn_100 REAL, lip_100 REAL, carb_100 REAL, sod_100 REAL, ativo INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS mapa_historico(
  id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, id_setor INTEGER, id_leito INTEGER NOT NULL,
  por_usuario INTEGER, por_nome TEXT NOT NULL, por_perfil TEXT NOT NULL, atualizado_em TEXT NOT NULL,
  origem TEXT NOT NULL DEFAULT 'mobile', campos_alterados TEXT NOT NULL,
  antes_json TEXT, depois_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_mapa_historico_periodo ON mapa_historico(atualizado_em, por_usuario);
CREATE INDEX IF NOT EXISTS ix_mapa_historico_leito ON mapa_historico(data, id_setor, id_leito, atualizado_em);
CREATE TABLE IF NOT EXISTS mapa_rascunho(data TEXT, id_leito INTEGER, campos TEXT, por_usuario INTEGER, atualizado_em TEXT,
  PRIMARY KEY(data, id_leito));
CREATE TABLE IF NOT EXISTS refeicoes_cfg(refeicao TEXT PRIMARY KEY, ativa INTEGER, abre TEXT, fecha TEXT);
CREATE TABLE IF NOT EXISTS janelas(id_setor INTEGER, refeicao TEXT, abre TEXT, fecha TEXT, PRIMARY KEY(id_setor, refeicao));
CREATE TABLE IF NOT EXISTS refeicoes_dia(data TEXT, id_setor INTEGER, refeicao TEXT, qtd REAL,
  por_usuario INTEGER, por_perfil TEXT, atualizado_em TEXT, PRIMARY KEY(data, id_setor, refeicao));
CREATE TABLE IF NOT EXISTS pedidos_estoque(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 id_item INTEGER NOT NULL REFERENCES itens(id),
 qtd REAL NOT NULL CHECK(qtd>0),
 solicitado_em TEXT NOT NULL,
 solicitado_por INTEGER,
 solicitado_nome TEXT,
 fornecedor TEXT,
 observacao TEXT,
 status TEXT NOT NULL DEFAULT 'pendente' CHECK(status IN ('pendente','recebido','cancelado')),
 recebido_em TEXT,
 recebido_por INTEGER,
 recebido_nome TEXT,
 id_movimento INTEGER
);
CREATE INDEX IF NOT EXISTS idx_pedidos_estoque_item_status ON pedidos_estoque(id_item,status);
CREATE TABLE IF NOT EXISTS estoque_dia(data TEXT, estoque TEXT, id_item INTEGER, qtd REAL,
  por_usuario INTEGER, por_perfil TEXT, atualizado_em TEXT, PRIMARY KEY(data, estoque, id_item));
CREATE TABLE IF NOT EXISTS movimentos(id INTEGER PRIMARY KEY, data TEXT, hora TEXT, origem TEXT, destino TEXT,
  id_item INTEGER, qtd REAL, por_usuario INTEGER, divergente INTEGER DEFAULT 0,
  preco_unitario_snapshot REAL, custo_snapshot REAL, observacao TEXT);
CREATE TABLE IF NOT EXISTS correcoes(id INTEGER PRIMARY KEY, tipo TEXT, data TEXT, chave TEXT, rotulo TEXT, id_setor INTEGER,
  valor_atual TEXT, valor_proposto TEXT, por_usuario INTEGER, criado_em TEXT, status TEXT DEFAULT 'pendente', decidido_em TEXT);
CREATE TABLE IF NOT EXISTS avisos(id INTEGER PRIMARY KEY, criado_em TEXT, por_usuario INTEGER, tipo TEXT, id_setor INTEGER,
  titulo TEXT, texto TEXT, leitos TEXT);
CREATE TABLE IF NOT EXISTS avisos_lidos(id_aviso INTEGER, id_usuario INTEGER, lido_em TEXT, PRIMARY KEY(id_aviso, id_usuario));
CREATE TABLE IF NOT EXISTS orientacoes(id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, titulo TEXT NOT NULL,
  texto TEXT NOT NULL, ordem INTEGER NOT NULL DEFAULT 0, atualizado_por INTEGER, atualizado_em TEXT NOT NULL);
"""


ORIENTACOES_INICIAIS = [
    ("diluicao", "Como preparar uma bebida com pó",
     "Siga sempre a quantidade escrita na prescrição, na ficha técnica ou no rótulo do produto. Não use uma medida padrão para todos os pós: cada produto pode precisar de uma quantidade diferente.\n\n1. Separe o produto correto e confira a quantidade indicada.\n2. Meça a água ou outro líquido autorizado em um copo dosador graduado. Leia a marca dos mililitros (mL) na altura dos olhos.\n3. Coloque o pó em uma balança limpa e confira o peso em gramas (g), ou use somente a medida que acompanha o produto quando a orientação permitir. Não use colher de cozinha como estimativa.\n4. Coloque o pó no líquido e mexa até dissolver e ficar uniforme. O volume pode mudar depois que o pó é acrescentado.\n5. Se a orientação pedir VOLUME FINAL, complete somente até a marca final indicada, depois de misturar. Se pedir quantidade de líquido inicial, não complete por conta própria.\n\nUse somente o líquido autorizado para aquele produto e paciente. Não acrescente açúcar. Higienize mãos e utensílios, identifique o preparo e respeite o prazo, a temperatura e o descarte definidos pelo fabricante e pelo serviço. Em caso de dúvida, pare e pergunte à Nutrição.", 10),
    ("intestino", "Frutas, fibras e funcionamento intestinal",
     "Para auxiliar o trânsito intestinal, prefira a fruta inteira, respeitando a consistência prescrita; mantenha a casca comestível quando estiver higienizada e for permitida. Fibras precisam de líquido adequado, conforme a prescrição e as restrições de cada pessoa.\\n\\nA quantidade de fibras varia conforme a fruta, a variedade, a porção e o preparo. A composição nutricional deve ser conferida na ficha específica do alimento, considerando a parte comestível e a forma de preparo. A quantidade de fibras, isoladamente, não mede o efeito laxativo de uma porção nem substitui avaliação clínica.\\n\\nNão existe uma lista universal de frutas constipantes. A maturação, a presença de casca, o preparo, a porção e a tolerância individual podem alterar a resposta. Suco coado costuma fornecer menos fibra que a fruta inteira.\\n\\nAjuste a escolha à dieta prescrita, à aceitação, à mastigação/deglutição e à tolerância. Não transforme uma orientação laxativa ou constipante em mudança de cardápio sem confirmação da Nutrição. Para consultar valores de composição, use a ficha do alimento na TBCA/USP.",
     20),
    ("potassio", "Potássio das frutas: como comparar",
     "O gráfico mostra a quantidade de potássio em 100 g da parte comestível de cada fruta, usando alimentos in natura identificados na TBCA/USP. A quantidade na porção servida será diferente: depende do peso da porção, da variedade e do preparo.\n\nValores menores no gráfico indicam menos potássio por 100 g em comparação com as outras frutas mostradas. Isso não significa que uma fruta esteja automaticamente liberada ou proibida. Pessoas com doença renal podem ter necessidades diferentes conforme exames, função dos rins, medicamentos, porção e orientação individual.\n\nUse o gráfico como apoio para conversar com a Nutrição. Não exclua nem ofereça frutas por conta própria. Confira sempre a ficha TBCA correspondente ao alimento realmente comprado e servido.", 30),
    ("diabetes", "Montagem da dieta para diabetes",
     "Dieta para diabetes não significa retirar todas as frutas ou preparar refeições sem carboidratos. Arroz, feijão, leite, frutas, pães e outros alimentos fornecem carboidratos e precisam entrar na quantidade e na distribuição definidas na prescrição.\\n\\nPrefira fruta inteira, sem açúcar adicionado. Não troque fruta por suco por conta própria: o suco pode concentrar carboidratos em menor volume e geralmente contém menos fibra que a fruta inteira. Não ofereça refresco adoçado, açúcar, mel ou xaropes como rotina.\\n\\nA composição de carboidratos varia conforme a fruta, a variedade, a porção e o preparo. Consulte a ficha específica na TBCA/USP; a consulta não classifica uma fruta como proibida ou liberada. Respeite porção, horário e consistência prescritos. Para pessoas com esquema fixo de insulina, a regularidade da quantidade e do horário de carboidratos é especialmente importante.\\n\\nA equipe da cozinha e da copa deve seguir o cardápio e a identificação da dieta. Dúvidas, substituições, hipoglicemia ou mudança de consistência devem ser encaminhadas à Nutrição/Enfermagem; não ajuste a dieta por iniciativa própria.",
     40),
]


class Erro(Exception):
    def __init__(self, msg, cod=400):
        super().__init__(msg)
        self.msg, self.cod = msg, cod


# ------------------------------------------------------------------ utilidades
def agora_dt():
    return datetime.now(TZ)


def hoje():
    return agora_dt().date().isoformat()


def agora():
    return agora_dt().isoformat(timespec="seconds")


def num(v, nome="valor"):
    try:
        if isinstance(v, str):
            v = v.strip().replace(".", "").replace(",", ".") if "," in v else v.strip()
        x = float(v)
    except (TypeError, ValueError):
        raise Erro("Número inválido em %s." % nome)
    if not 0 <= x <= 1e9:
        raise Erro("Valor fora do limite em %s." % nome)
    return x


def normalizar_embalagem(qtd, unidade):
    """Converte unidades equivalentes para g/mL; não converte massa em volume."""
    if qtd is None:
        return None, None
    unidade = str(unidade or "").strip().lower()
    fatores = {"g": (1.0, "g"), "kg": (1000.0, "g"), "mg": (0.001, "g"),
               "ml": (1.0, "ml"), "l": (1000.0, "ml"), "un": (1.0, "un")}
    if unidade not in fatores:
        raise Erro("Escolha a unidade do conteúdo: gramas (g), mililitros (mL) ou unidade.")
    fator, base = fatores[unidade]
    return qtd * fator, base


def dia_valido(txt):
    try:
        return date.fromisoformat(str(txt)).isoformat()
    except ValueError:
        raise Erro("Data inválida (use AAAA-MM-DD).")


def hora(v):
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(v or "")):
        raise Erro("Horário inválido (use HH:MM).")
    return str(v)


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
    sid = id_setor if perfil == "nutricionista" and id_setor not in (None, "") else None
    if sid is not None and not c.execute("SELECT 1 FROM setores WHERE id=?", (sid,)).fetchone():
        raise Erro("Setor inexistente.")
    try:
        c.execute("INSERT INTO usuarios(login,nome,perfil,id_setor,salt,senha,criado_em) VALUES(?,?,?,?,'','',?)",
                  (login, str(nome).strip(), perfil, sid, agora()))
    except sqlite3.IntegrityError:
        raise Erro("Esse login já existe.")
    definir_senha(c, c.execute("SELECT id FROM usuarios WHERE login=?", (login,)).fetchone()["id"], senha)


def migrar(c):
    """Atualiza bancos da primeira versão (12/11/2026) e carrega a configuração inicial das refeições."""
    def cols(t):
        return {r[1] for r in c.execute("PRAGMA table_info(%s)" % t)}
    if "id_paciente" not in cols("mapa_dia"):
        c.execute("ALTER TABLE mapa_dia ADD COLUMN id_paciente INTEGER")
    if "id_ocupacao" not in cols("mapa_dia"):
        c.execute("ALTER TABLE mapa_dia ADD COLUMN id_ocupacao TEXT")
    # Atribui IDs estáveis aos pacientes já existentes, mantendo o mesmo ID
    # entre snapshots diários enquanto nome e ocupação permanecem contínuos.
    ocupacao_atual = {}
    for row in c.execute("SELECT data,id_leito,ocupado,nome,id_ocupacao FROM mapa_dia ORDER BY id_leito,data").fetchall():
        lid = int(row["id_leito"])
        if not row["ocupado"] or not str(row["nome"] or "").strip():
            ocupacao_atual.pop(lid, None)
            continue
        nome = str(row["nome"] or "").strip().casefold()
        anterior = ocupacao_atual.get(lid)
        if anterior and anterior[0] == nome:
            identificador = row["id_ocupacao"] or anterior[1]
        else:
            identificador = row["id_ocupacao"] or secrets.token_hex(16)
        ocupacao_atual[lid] = (nome, identificador)
        if not row["id_ocupacao"]:
            c.execute("UPDATE mapa_dia SET id_ocupacao=? WHERE data=? AND id_leito=?",
                      (identificador, row["data"], lid))
    for col, tipo in (("nome", "TEXT"), ("idade_anos", "INTEGER"), ("idade_meses", "INTEGER"),
                      ("diagnostico", "TEXT"), ("pref_sim", "TEXT"), ("pref_nao", "TEXT"),
                      ("cor", "TEXT"), ("consistencia", "TEXT"), ("via", "TEXT"),
                      ("dm", "INTEGER DEFAULT 0"), ("has", "INTEGER DEFAULT 0"),
                      ("laxativa", "INTEGER DEFAULT 0"), ("constipante", "INTEGER DEFAULT 0"),
                      ("drc", "INTEGER DEFAULT 0"), ("suplementos_json", "TEXT")):
        if col not in cols("mapa_dia"):
            c.execute("ALTER TABLE mapa_dia ADD COLUMN %s %s" % (col, tipo))
    # Metadados comerciais e snapshots de custo são aditivos: bancos antigos mantêm todo o histórico.
    for col, tipo in (("preco_unitario", "REAL"), ("embalagem_qtd", "REAL"), ("embalagem_un", "TEXT"), ("ativo", "INTEGER NOT NULL DEFAULT 1"), ("categoria", "TEXT NOT NULL DEFAULT 'Gêneros alimentícios'"), ("validade", "TEXT")):
        if col not in cols("itens"):
            c.execute("ALTER TABLE itens ADD COLUMN %s %s" % (col, tipo))
    if "observacao" not in cols("movimentos"):
        c.execute("ALTER TABLE movimentos ADD COLUMN observacao TEXT")
    # Unidades antigas são convertidas para a unidade-base, preservando o conteúdo físico.
    # O valor por embalagem/preço não muda; apenas a representação da quantidade é normalizada.
    c.execute("UPDATE itens SET embalagem_qtd=embalagem_qtd*1000, embalagem_un='g' "
              "WHERE lower(trim(embalagem_un))='kg' AND embalagem_qtd IS NOT NULL")
    c.execute("UPDATE itens SET embalagem_qtd=embalagem_qtd/1000, embalagem_un='g' "
              "WHERE lower(trim(embalagem_un))='mg' AND embalagem_qtd IS NOT NULL")
    c.execute("UPDATE itens SET embalagem_qtd=embalagem_qtd*1000, embalagem_un='ml' "
              "WHERE lower(trim(embalagem_un))='l' AND embalagem_qtd IS NOT NULL")
    c.execute("UPDATE itens SET embalagem_un=lower(trim(embalagem_un)) "
              "WHERE embalagem_un IS NOT NULL")
    for col in ("preco_unitario_snapshot", "custo_snapshot"):
        if col not in cols("movimentos"):
            c.execute("ALTER TABLE movimentos ADD COLUMN %s REAL" % col)
    if "id_setor" not in cols("correcoes"):
        c.execute("ALTER TABLE correcoes ADD COLUMN id_setor INTEGER")
    c.execute("UPDATE usuarios SET perfil='copa' WHERE perfil IN ('setor','estoque_copa')")
    # A copa passa a compartilhar o mapa inteiro; o setor continua identificando cada leito.
    c.execute("UPDATE usuarios SET id_setor=NULL WHERE perfil='copa'")
    c.executemany("INSERT OR IGNORE INTO refeicoes_cfg VALUES(?,?,?,?)", CFG_INICIAL)
    for slug, titulo, texto, ordem in ORIENTACOES_INICIAIS:
        c.execute("INSERT OR IGNORE INTO orientacoes(slug,titulo,texto,ordem,atualizado_em) VALUES(?,?,?,?,?)",
                  (slug, titulo, texto, ordem, agora()))
    for slug, titulo, texto, _ordem in ORIENTACOES_INICIAIS:
        c.execute("UPDATE orientacoes SET titulo=?, texto=?, atualizado_em=? "
                  "WHERE slug=? AND atualizado_por IS NULL",
                  (titulo, texto, agora(), slug))


def preparar_banco(db, redefinir=False):
    """Prepara o banco e aplica a senha inicial fixa do admin uma única vez.

    Bancos antigos recebem a credencial inicial solicitada na primeira atualização;
    depois disso, alterações de senha feitas pelo administrador são preservadas.
    """
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    c = conectar(db)
    try:
        c.executescript(ESQUEMA)
        migrar(c)
        adm = c.execute("SELECT id FROM usuarios WHERE login='admin'").fetchone()
        senha = None
        inicializada = c.execute(
            "SELECT valor FROM sistema_config WHERE chave='senha_admin_inicial_aplicada'"
        ).fetchone()
        if adm is None:
            criar_usuario(c, "admin", "Administrador", "admin", None, SENHA_ADMIN_INICIAL)
            adm = c.execute("SELECT id FROM usuarios WHERE login='admin'").fetchone()
            senha = SENHA_ADMIN_INICIAL
        elif redefinir:
            senha = secrets.token_urlsafe(8)
            definir_senha(c, adm["id"], senha)
        elif inicializada is None:
            definir_senha(c, adm["id"], SENHA_ADMIN_INICIAL)
            senha = SENHA_ADMIN_INICIAL
        c.execute(
            "INSERT OR REPLACE INTO sistema_config(chave,valor) VALUES('senha_admin_inicial_aplicada','1')"
        )
        c.commit()
        return senha
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def pub(u):
    return {"id": u["id"], "nome": u["nome"], "perfil": u["perfil"], "id_setor": u["id_setor"], "estoque": EST_PERFIL.get(u["perfil"])}


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
    """Admin, nutrição sem setor e copa global escolhem o setor; contas setoriais ficam no próprio."""
    p, sid = u["perfil"], u["id_setor"]
    if p == "admin" or (p in ("nutricionista", "copa") and sid is None):
        sid = pedido
        if p == "copa" and not sid:
            primeiro = c.execute("SELECT id FROM setores ORDER BY id LIMIT 1").fetchone()
            sid = primeiro["id"] if primeiro else None
    elif p not in ("nutricionista", "copa"):
        raise Erro("Sem permissão para este setor.", 403)
    if not sid:
        raise Erro("Escolha o setor." if p in STAFF or p == "copa" else "Seu usuário não tem setor definido. Fale com o administrador.")
    s = c.execute("SELECT * FROM setores WHERE id=?", (int(sid),)).fetchone()
    if not s:
        raise Erro("Setor não encontrado.", 404)
    return dict(s)


def estoque_alvo(u, pedido):
    est = pedido if u["perfil"] == "admin" else EST_PERFIL.get(u["perfil"])
    if est not in ESTOQUES:
        raise Erro("Sem permissão para este estoque.", 403)
    return est


def dia_alvo(u, pedido):
    """Copa e estoquistas só mexem no PRÓPRIO DIA (data do servidor); só admin e nutricionista escolhem a data."""
    return dia_valido(pedido) if (u["perfil"] in STAFF and pedido) else hoje()


# --------------------------------------------- mapa: normalização e gravação
def norm(l):
    """Normaliza o mapa da Copa e os detalhes estruturados da dieta e suplementação."""
    def t(k, n=120):
        return str(l.get(k) or "").strip()[:n]

    def i(k, mx):
        v = l.get(k)
        if v in (None, ""):
            return None
        try:
            x = int(float(v))
        except (TypeError, ValueError):
            raise Erro("Idade inválida.")
        if not 0 <= x <= mx:
            raise Erro("Idade fora do limite.")
        return x

    def flag(k):
        return int(bool(l.get(k)))

    consistencias = ("Livre", "Branda", "Pastosa", "Líq/Past", "Líquida")
    vias = ("Oral", "Enteral", "Zero")
    cor = t("cor", 4)
    if cor and cor not in ("B", "N"):
        raise Erro("Cor inválida.")
    consistencia = t("consistencia", 40)
    via = t("via", 20)
    if consistencia and consistencia not in consistencias:
        raise Erro("Consistência inválida.")
    if via and via not in vias:
        raise Erro("Via de alimentação inválida.")

    suplementos = l.get("suplementos") or []
    if not isinstance(suplementos, list) or len(suplementos) > 20:
        raise Erro("Lista de suplementos inválida.")
    sup_norm = []
    refeicoes_validas = set(REFEICOES)
    for s in suplementos:
        if not isinstance(s, dict):
            raise Erro("Suplemento inválido.")
        try:
            sid = int(s.get("id_suplemento"))
            ml = float(s.get("ml_oferta") or 0)
            agua = float(s.get("agua_ml") or 0)
        except (TypeError, ValueError):
            raise Erro("Volume do suplemento inválido.")
        if sid <= 0 or not 0 < ml <= 5000 or not 0 <= agua <= 5000:
            raise Erro("Confira os volumes do suplemento e da água.")
        refs = list(dict.fromkeys(str(x) for x in (s.get("refeicoes") or []) if str(x) in refeicoes_validas))
        if not refs:
            raise Erro("Selecione ao menos uma refeição para cada suplemento.")
        sup_norm.append({
            "id_suplemento": sid, "nome": str(s.get("nome") or "").strip()[:120],
            "modulo": str(s.get("modulo") or "").strip()[:80],
            "ml_oferta": ml, "agua_ml": agua, "refeicoes": refs,
            "ofertas_dia": len(refs), "qtd_dia": ml * len(refs),
            "batido_fruta": bool(s.get("batido_fruta")), "unidade": "ml"
        })

    try:
        id_paciente = int(l.get("id_paciente")) if l.get("id_paciente") not in (None, "") else None
    except (TypeError, ValueError):
        raise Erro("Identificador do paciente inválido.")
    if id_paciente is not None and id_paciente <= 0:
        raise Erro("Identificador do paciente inválido.")
    id_ocupacao = str(l.get("id_ocupacao") or "").strip()[:100] or None
    if id_ocupacao and not id_ocupacao.startswith(("offline:", "paciente:")):
        id_ocupacao = None
    n = {"id_paciente": id_paciente, "id_ocupacao": id_ocupacao, "nome": t("nome"), "idade_anos": i("idade_anos", 130), "idade_meses": i("idade_meses", 11),
         "dieta": t("dieta", 60), "diagnostico": t("diagnostico", 200),
         "pref_sim": t("pref_sim", 200), "pref_nao": t("pref_nao", 200),
         "acompanhante": int(bool(l.get("acompanhante"))), "cor": cor,
         "consistencia": consistencia, "via": via, "dm": flag("dm"), "has": flag("has"),
         "laxativa": flag("laxativa"), "constipante": flag("constipante"), "drc": flag("drc"),
         "suplementos": sup_norm, "suplementos_json": json.dumps(sup_norm, ensure_ascii=False)}
    if not n["nome"]:
        n.update(id_paciente=None, id_ocupacao=None, idade_anos=None, idade_meses=None, dieta="", diagnostico="", pref_sim="", pref_nao="",
                 acompanhante=0, cor="", consistencia="", via="", dm=0, has=0, laxativa=0,
                 constipante=0, drc=0, suplementos=[], suplementos_json="[]")
    n["ocupado"] = int(bool(n["nome"]))
    return n


def timestamp_novo(novo, atual):
    """Compara timestamps ISO, aceitando registros antigos sem fuso e novos com fuso."""
    if not novo:
        return False
    if not atual:
        return True
    try:
        a = datetime.fromisoformat(str(novo).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(atual).replace("Z", "+00:00"))
        if a.tzinfo is None:
            a = a.replace(tzinfo=TZ)
        if b.tzinfo is None:
            b = b.replace(tzinfo=TZ)
        return a > b
    except (TypeError, ValueError):
        return str(novo).replace("T", " ") > str(atual).replace("T", " ")


def atual(c, tipo, data, chave):
    if tipo == "mapa":
        r = c.execute("SELECT id_paciente,id_ocupacao,ocupado,acompanhante,COALESCE(dieta,'') dieta,COALESCE(nome,'') nome,idade_anos,idade_meses,"
                      "COALESCE(diagnostico,'') diagnostico,COALESCE(pref_sim,'') pref_sim,COALESCE(pref_nao,'') pref_nao,"
                      "COALESCE(cor,'') cor,COALESCE(consistencia,'') consistencia,COALESCE(via,'') via,"
                      "COALESCE(dm,0) dm,COALESCE(has,0) has,COALESCE(laxativa,0) laxativa,"
                      "COALESCE(constipante,0) constipante,COALESCE(drc,0) drc,"
                      "COALESCE(suplementos_json,'[]') suplementos_json,por_perfil "
                      "FROM mapa_dia WHERE data=? AND id_leito=?", (data, int(chave)))
    elif tipo == "refeicao":
        sid, ref = chave.split("|")
        r = c.execute("SELECT qtd,por_perfil FROM refeicoes_dia WHERE data=? AND id_setor=? AND refeicao=?", (data, int(sid), ref))
    else:
        est, iid = chave.split("|")
        r = c.execute("SELECT qtd,por_perfil FROM estoque_dia WHERE data=? AND estoque=? AND id_item=?", (data, est, int(iid)))
    r = r.fetchone()
    return dict(r) if r else None


def gravar(c, tipo, data, chave, v, uid, perfil, origem="mobile"):
    t = v.get("_atualizado_em") or agora()
    if tipo == "mapa":
        anterior = atual(c, "mapa", data, chave)
        if not anterior:
            # O primeiro registro do dia pode substituir um paciente herdado do dia anterior.
            # Esse estado anterior também precisa entrar na trilha para reconciliar serviços offline.
            leito_ref = c.execute("SELECT id_setor FROM leitos WHERE id=?", (int(chave),)).fetchone()
            if leito_ref:
                herdado = next((x for x in linhas_mapa(c, leito_ref["id_setor"], data)
                                if int(x["id_leito"]) == int(chave)), None)
                if herdado and herdado.get("data_base") not in (None, data):
                    anterior = {k: herdado.get(k) for k in CAMPOS}
                    anterior["ocupado"] = herdado.get("ocupado")
                    anterior["id_paciente"] = herdado.get("id_paciente")
                    anterior["id_ocupacao"] = herdado.get("id_ocupacao")
                    anterior["por_perfil"] = herdado.get("por_perfil")
        if anterior:
            anterior.pop("por_perfil", None)
        anterior_ocupacao = c.execute("SELECT id_paciente,id_ocupacao,nome,ocupado FROM mapa_dia WHERE id_leito=? AND data<=? ORDER BY data DESC LIMIT 1",
                                       (int(chave), data)).fetchone()
        nome_novo = str(v.get("nome") or "").strip()
        if v.get("ocupado") and nome_novo:
            id_paciente = v.get("id_paciente")
            mesmo_paciente = (anterior_ocupacao and anterior_ocupacao["ocupado"]
                              and str(anterior_ocupacao["nome"] or "").strip().casefold() == nome_novo.casefold())
            if (not v.get("_origem_desktop") and id_paciente is not None
                    and anterior_ocupacao and anterior_ocupacao["id_paciente"] == id_paciente
                    and not mesmo_paciente):
                id_paciente = None
                v["id_paciente"] = None
            if id_paciente is None and mesmo_paciente and anterior_ocupacao["id_paciente"]:
                id_paciente = anterior_ocupacao["id_paciente"]
                v["id_paciente"] = id_paciente
            if id_paciente is not None:
                id_ocupacao = "paciente:" + str(id_paciente)
            elif (v.get("id_ocupacao") or "").startswith("offline:") and not mesmo_paciente:
                id_ocupacao = v["id_ocupacao"]
            else:
                id_ocupacao = (anterior_ocupacao["id_ocupacao"] if mesmo_paciente else None) or secrets.token_hex(16)
        else:
            v["id_paciente"] = None
            id_ocupacao = None
        v["id_ocupacao"] = id_ocupacao
        campos = [k for k in CAMPOS if (anterior or {}).get(k) != v.get(k)]
        if campos:
            leito = c.execute("SELECT id_setor FROM leitos WHERE id=?", (int(chave),)).fetchone()
            usuario = c.execute("SELECT nome FROM usuarios WHERE id=?", (int(uid),)).fetchone()
            c.execute(
                "INSERT INTO mapa_historico(data,id_setor,id_leito,por_usuario,por_nome,por_perfil,atualizado_em,origem,campos_alterados,antes_json,depois_json) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (data, leito["id_setor"] if leito else None, int(chave), uid,
                 usuario["nome"] if usuario else "Usuário removido", perfil, t, origem,
                 json.dumps(campos, ensure_ascii=False),
                 json.dumps(anterior, ensure_ascii=False) if anterior is not None else None,
                 json.dumps({**{k: v.get(k) for k in CAMPOS}, "ocupado": v.get("ocupado"),
                             "id_ocupacao": id_ocupacao}, ensure_ascii=False)),
            )
        c.execute("INSERT INTO mapa_dia(data,id_leito,id_paciente,id_ocupacao,ocupado,acompanhante,dieta,nome,idade_anos,idade_meses,diagnostico,pref_sim,pref_nao,"
                  "cor,consistencia,via,dm,has,laxativa,constipante,drc,suplementos_json,por_usuario,por_perfil,atualizado_em) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(data,id_leito) DO UPDATE SET "
                  "id_paciente=excluded.id_paciente,id_ocupacao=excluded.id_ocupacao,ocupado=excluded.ocupado,acompanhante=excluded.acompanhante,dieta=excluded.dieta,nome=excluded.nome,"
                  "idade_anos=excluded.idade_anos,idade_meses=excluded.idade_meses,diagnostico=excluded.diagnostico,"
                  "pref_sim=excluded.pref_sim,pref_nao=excluded.pref_nao,cor=excluded.cor,consistencia=excluded.consistencia,"
                  "via=excluded.via,dm=excluded.dm,has=excluded.has,laxativa=excluded.laxativa,"
                  "constipante=excluded.constipante,drc=excluded.drc,suplementos_json=excluded.suplementos_json,"
                  "por_usuario=excluded.por_usuario,por_perfil=excluded.por_perfil,atualizado_em=excluded.atualizado_em",
                  (data, int(chave), v.get("id_paciente"), id_ocupacao, v["ocupado"], v.get("acompanhante", 0), v.get("dieta", ""), v.get("nome", ""),
                   v.get("idade_anos"), v.get("idade_meses"), v.get("diagnostico", ""), v.get("pref_sim", ""),
                   v.get("pref_nao", ""), v.get("cor", ""), v.get("consistencia", ""), v.get("via", ""),
                   v.get("dm", 0), v.get("has", 0), v.get("laxativa", 0), v.get("constipante", 0), v.get("drc", 0),
                   v.get("suplementos_json", "[]"), uid, perfil, t))
    else:
        tab, cols = ("refeicoes_dia", "id_setor,refeicao") if tipo == "refeicao" else ("estoque_dia", "estoque,id_item")
        a, b = chave.split("|")
        a, b = (int(a), b) if tipo == "refeicao" else (a, int(b))
        c.execute("INSERT INTO %s(data,%s,qtd,por_usuario,por_perfil,atualizado_em) VALUES(?,?,?,?,?,?,?) ON CONFLICT(data,%s) DO UPDATE SET "
                  "qtd=excluded.qtd,por_usuario=excluded.por_usuario,por_perfil=excluded.por_perfil,atualizado_em=excluded.atualizado_em"
                  % (tab, cols, cols), (data, a, b, v["qtd"], uid, perfil, t))


def salvar(c, u, tipo, data, chave, rotulo, novo, sid=None):
    """Devolve 'ok', 'igual' ou 'pendente'. Se admin/nutricionista já gravou este dado no dia e a copa (ou estoquista)
    manda valor diferente, nada é sobrescrito: nasce uma correção pendente para eles aprovarem ou recusarem."""
    a = atual(c, tipo, data, chave)
    if a:
        por = a.pop("por_perfil")
        subst = "UPDATE correcoes SET status='substituida' WHERE tipo=? AND data=? AND chave=? AND status='pendente'"
        if all(a.get(k) == v for k, v in novo.items()):
            c.execute(subst, (tipo, data, chave))
            return "igual"
        if por in STAFF and u["perfil"] not in STAFF:
            c.execute(subst, (tipo, data, chave))
            c.execute("INSERT INTO correcoes(tipo,data,chave,rotulo,id_setor,valor_atual,valor_proposto,por_usuario,criado_em) VALUES(?,?,?,?,?,?,?,?,?)",
                      (tipo, data, chave, rotulo, sid, json.dumps(a), json.dumps(novo), u["id"], agora()))
            return "pendente"
    gravar(c, tipo, data, chave, novo, u["id"], u["perfil"])
    return "ok"


def pendentes(c, tipo, data):
    return [r[0] for r in c.execute("SELECT chave FROM correcoes WHERE tipo=? AND data=? AND status='pendente'", (tipo, data))]


# ----------------------------------------- leituras (já com a base do dia anterior)
def linhas_mapa(c, sid, d, rascunho=False):
    sql = ("SELECT l.id id_leito,l.codigo,h.id_paciente,h.id_ocupacao,COALESCE(h.ocupado,0) ocupado,COALESCE(h.acompanhante,0) acompanhante,COALESCE(h.dieta,'') dieta,"
           "COALESCE(h.nome,'') nome,h.idade_anos,h.idade_meses,COALESCE(h.diagnostico,'') diagnostico,COALESCE(h.pref_sim,'') pref_sim,"
           "COALESCE(h.pref_nao,'') pref_nao,COALESCE(h.cor,'') cor,COALESCE(h.consistencia,'') consistencia,COALESCE(h.via,'') via,COALESCE(h.dm,0) dm,COALESCE(h.has,0) has,COALESCE(h.laxativa,0) laxativa,COALESCE(h.constipante,0) constipante,COALESCE(h.drc,0) drc,COALESCE(h.suplementos_json,'[]') suplementos_json,h.data data_base,h.por_perfil,h.atualizado_em FROM leitos l "
           "LEFT JOIN mapa_dia h ON h.id_leito=l.id AND h.data=(SELECT MAX(data) FROM mapa_dia WHERE id_leito=l.id AND data<=?) "
           "WHERE l.id_setor=? ORDER BY l.codigo")
    out = []
    sql = sql.replace("h.por_perfil,h.atualizado_em FROM", "h.por_perfil,h.atualizado_em,u.nome por_nome FROM", 1)
    sql = sql.replace("WHERE l.id_setor=?", "LEFT JOIN usuarios u ON u.id=h.por_usuario WHERE l.id_setor=?", 1)
    for r in c.execute(sql, (d, sid)):
        item = dict(r)
        try:
            item["suplementos"] = json.loads(item.get("suplementos_json", "[]") or "[]")
        except (TypeError, ValueError):
            item["suplementos"] = []
        item.update(herdado=item["data_base"] not in (None, d), rascunho=False)
        out.append(item)
    if rascunho:  # visão da nutrição: o que está salvo + o que ainda não foi publicado para a copa
        rs = {r["id_leito"]: json.loads(r["campos"]) for r in c.execute("SELECT id_leito,campos FROM mapa_rascunho WHERE data=?", (d,))}
        for l in out:
            if l["id_leito"] in rs:
                l.update(rs[l["id_leito"]])
                try:
                    l["suplementos"] = json.loads(l.get("suplementos_json") or "[]")
                except (TypeError, ValueError):
                    l["suplementos"] = []
                l["rascunho"] = True
    return out


def cfg_refeicoes(c):
    return {r["refeicao"]: dict(r) for r in c.execute("SELECT * FROM refeicoes_cfg")}


def janela(c, sid, ref, cfg):
    """Horário de contagem da refeição no setor (None se a refeição não está habilitada)."""
    g = cfg.get(ref)
    if not g or not g["ativa"]:
        return None
    j = c.execute("SELECT abre,fecha FROM janelas WHERE id_setor=? AND refeicao=?", (sid, ref)).fetchone()
    return (j["abre"], j["fecha"]) if j else (g["abre"], g["fecha"])


def linhas_refeicoes(c, sid, d):
    cfg, h, out = cfg_refeicoes(c), agora_dt().strftime("%H:%M"), []
    for ref in REFEICOES:
        jn = janela(c, sid, ref, cfg)
        if not jn:
            continue
        r = c.execute("SELECT qtd,data data_base,por_perfil,atualizado_em FROM refeicoes_dia WHERE id_setor=? AND refeicao=? AND data=?",
                      (sid, ref, d)).fetchone()  # a contagem recomeça do zero a cada dia
        x = dict(r) if r else {"qtd": 0, "data_base": None, "por_perfil": None, "atualizado_em": None}
        out.append({**x, "refeicao": ref, "herdado": False, "abre": jn[0], "fecha": jn[1], "aberta": jn[0] <= h <= jn[1]})
    return out


def linhas_estoque(c, est, d):
    sql = ("SELECT i.id id_item,i.nome,i.unidade,i.categoria,i.validade,COALESCE(h.qtd,0) qtd,h.data data_base,h.por_perfil,h.atualizado_em FROM itens i "
           "LEFT JOIN estoque_dia h ON h.id_item=i.id AND h.estoque=? AND "
           "h.data=(SELECT MAX(data) FROM estoque_dia WHERE id_item=i.id AND estoque=? AND data<=?) "
           "ORDER BY CASE WHEN i.validade IS NULL OR i.validade='' THEN 1 ELSE 0 END,i.validade,i.categoria COLLATE NOCASE,i.nome COLLATE NOCASE")
    return [{**dict(r), "herdado": r["data_base"] not in (None, d)} for r in c.execute(sql, (est, est, d))]


def saldo(c, est, iid, d):
    r = c.execute("SELECT qtd FROM estoque_dia WHERE estoque=? AND id_item=? AND data<=? ORDER BY data DESC LIMIT 1", (est, iid, d)).fetchone()
    return r["qtd"] if r else 0.0


# ------------------------------------------------------------ operações (POST)
def post_mapa(c, u, s, d, linhas, completo=False, origem_desktop=False):
    """Grava o mapa. No modo completo, aplica por leito somente o estado com timestamp mais novo."""
    cods = {r["id"]: r["codigo"] for r in c.execute("SELECT id,codigo FROM leitos WHERE id_setor=?", (s["id"],))}
    staff = u["perfil"] in STAFF
    vivo = {l["id_leito"]: l for l in linhas_mapa(c, s["id"], d)}
    res = {"ok": 0, "igual": 0, "pendente": 0, "rascunho": 0, "ignorados": 0}
    for l in linhas:
        lid = int(l["id_leito"])
        if lid not in cods:
            raise Erro("Leito de outro setor.", 403)
        n = norm(l)
        n.pop("suplementos", None)
        n["_origem_desktop"] = bool(origem_desktop)
        if completo:
            n["_atualizado_em"] = l.get("atualizado_em")
            atual_l = vivo.get(lid) or {}
            if not n["_atualizado_em"] and not n.get("ocupado"):
                res["ignorados"] += 1
                continue
            if n["_atualizado_em"] and not timestamp_novo(n["_atualizado_em"], atual_l.get("atualizado_em")):
                res["igual"] += 1
                continue
            gravar(c, "mapa", d, str(lid), n, u["id"], u["perfil"])
            res["ok"] += 1
            continue
        if not staff:
            res[salvar(c, u, "mapa", d, str(lid), "Leito %s (%s)" % (cods[lid], s["nome"]), n, s["id"])] += 1
        elif all(vivo[lid].get(k) == v for k, v in n.items() if k != "suplementos_json") and vivo[lid].get("suplementos", []) == json.loads(n["suplementos_json"]):
            c.execute("DELETE FROM mapa_rascunho WHERE data=? AND id_leito=?", (d, lid))
            res["igual"] += 1
        else:
            c.execute("INSERT INTO mapa_rascunho(data,id_leito,campos,por_usuario,atualizado_em) VALUES(?,?,?,?,?) ON CONFLICT(data,id_leito) "
                      "DO UPDATE SET campos=excluded.campos,por_usuario=excluded.por_usuario,atualizado_em=excluded.atualizado_em",
                      (d, lid, json.dumps(n), u["id"], agora()))
            res["rascunho"] += 1
    return res


def publicar(c, u, s, d, texto):
    """'Atualizar as informações para a copa': aplica o rascunho do setor e registra UM aviso listando os leitos alterados."""
    cods = {r["id"]: r["codigo"] for r in c.execute("SELECT id,codigo FROM leitos WHERE id_setor=?", (s["id"],))}
    vivo = {l["id_leito"]: l for l in linhas_mapa(c, s["id"], d)}
    mud = []
    for r in c.execute("SELECT id_leito,campos FROM mapa_rascunho WHERE data=? AND id_leito IN (SELECT id FROM leitos WHERE id_setor=?)",
                       (d, s["id"])).fetchall():
        lid, n, b = r["id_leito"], json.loads(r["campos"]), vivo[r["id_leito"]]
        tipo = "liberado" if b["ocupado"] and not n["ocupado"] else ("novo" if n["ocupado"] and not b["ocupado"] else "alterado")
        mud.append({"leito": cods[lid], "tipo": tipo, "campos": [k for k in CAMPOS if b[k] != n[k]]})
        gravar(c, "mapa", d, str(lid), n, u["id"], u["perfil"], origem="publicacao")
    if not mud:
        raise Erro("Não há alterações do mapa para publicar neste setor e dia.")
    c.execute("DELETE FROM mapa_rascunho WHERE data=? AND id_leito IN (SELECT id FROM leitos WHERE id_setor=?)", (d, s["id"]))
    c.execute("INSERT INTO avisos(criado_em,por_usuario,tipo,id_setor,titulo,texto,leitos) VALUES(?,?,?,?,?,?,?)",
              (agora(), u["id"], "mapa", s["id"], "Mapa de %s/%s atualizado pela nutrição" % (d[8:10], d[5:7]), str(texto or "").strip()[:300],
               json.dumps(mud)))
    return {"ok": True, "leitos": len(mud)}


def post_refeicoes(c, u, s, d, itens):
    """Copa só conta refeição habilitada e dentro do horário (relógio do servidor). Nutrição/admin: a qualquer hora."""
    cfg, res, h = cfg_refeicoes(c), {"ok": 0, "igual": 0, "pendente": 0}, agora_dt().strftime("%H:%M")
    for i in itens:
        ref = i["refeicao"]
        jn = janela(c, s["id"], ref, cfg)
        if jn is None:
            raise Erro("A refeição '%s' não está habilitada para contagem." % ref, 403)
        if u["perfil"] not in STAFF and not jn[0] <= h <= jn[1]:
            raise Erro("A contagem de '%s' só fica aberta das %s às %s." % (ref, jn[0], jn[1]), 403)
        res[salvar(c, u, "refeicao", d, "%d|%s" % (s["id"], ref), "%s - %s" % (s["nome"], ref), {"qtd": num(i["qtd"], ref)}, s["id"])] += 1
    return res


def definir_janela(c, s, b):
    """Horário de contagem de uma refeição NESTE setor (nutricionista responsável ou admin)."""
    ref = b.get("refeicao")
    if ref not in REFEICOES:
        raise Erro("Refeição inválida.")
    ab, fe = hora(b.get("abre")), hora(b.get("fecha"))
    if ab >= fe:
        raise Erro("O horário de abertura precisa ser anterior ao de fechamento.")
    c.execute("INSERT INTO janelas(id_setor,refeicao,abre,fecha) VALUES(?,?,?,?) ON CONFLICT(id_setor,refeicao) DO UPDATE SET "
              "abre=excluded.abre,fecha=excluded.fecha", (s["id"], ref, ab, fe))
    return {"ok": True}


def definir_refeicao(c, b):
    """Habilita/desabilita uma refeição para contagem em todo o hospital e define o horário padrão (admin)."""
    ref = b.get("refeicao")
    if ref not in REFEICOES:
        raise Erro("Refeição inválida.")
    ativa = int(bool(b.get("ativa")))
    ab, fe = (hora(b["abre"]) if b.get("abre") else None), (hora(b["fecha"]) if b.get("fecha") else None)
    if ativa and (ab is None or fe is None or ab >= fe):
        raise Erro("Para habilitar, informe abertura e fechamento (abertura antes do fechamento).")
    c.execute("UPDATE refeicoes_cfg SET ativa=?,abre=?,fecha=? WHERE refeicao=?", (ativa, ab, fe, ref))
    return {"ok": True}


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
    """Ajuste de saldo por reposição: se admin/nutrição já tinha gravado o dia, a marca é mantida."""
    a = atual(c, "estoque", d, "%s|%d" % (est, iid))
    gravar(c, "estoque", d, "%s|%d" % (est, iid), {"qtd": qtd}, u["id"], a["por_perfil"] if a and a["por_perfil"] in STAFF else u["perfil"])


def post_reposicao(c, u, est, b):
    iid, qtd, org, d = int(b["id_item"]), num(b["qtd"], "quantidade"), b.get("origem"), hoje()
    item = c.execute("SELECT * FROM itens WHERE id=?", (iid,)).fetchone()
    if qtd <= 0 or not item:
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
    preco = item["preco_unitario"]
    custo = qtd * float(preco) if preco is not None else None
    observacao = str(b.get("observacao") or "").strip()[:1000] or None
    c.execute("""INSERT INTO movimentos
        (data,hora,origem,destino,id_item,qtd,por_usuario,divergente,preco_unitario_snapshot,custo_snapshot,observacao)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (d, agora(), org, est, iid, qtd, u["id"], div, preco, custo, observacao))
    return {"ok": True, "saldo": novo, "divergente": bool(div)}


# --------------------------------------------------------------------- avisos
def novo_aviso(c, u, b):
    t = str(b.get("texto", "")).strip()
    if not t:
        raise Erro("Escreva o aviso.")
    sid = u["id_setor"] if u["perfil"] == "nutricionista" and u["id_setor"] else (int(b["id_setor"]) if b.get("id_setor") else None)
    c.execute("INSERT INTO avisos(criado_em,por_usuario,tipo,id_setor,titulo,texto,leitos) VALUES(?,?,?,?,?,?,?)",
              (agora(), u["id"], "texto", sid, "Aviso da nutrição", t[:500], "[]"))
    return {"ok": True}


def avisos_do_usuario(c, u):
    """Avisos ainda não lidos pela copa (do setor dela ou gerais, criados depois do cadastro dela)."""
    if u["perfil"] != "copa":
        return []
    rs = c.execute("SELECT a.*,x.nome por_nome FROM avisos a JOIN usuarios x ON x.id=a.por_usuario "
                   "WHERE (a.id_setor IS NULL OR a.id_setor=? OR ? IS NULL) "
                   "AND a.criado_em>=? AND a.id NOT IN (SELECT id_aviso FROM avisos_lidos WHERE id_usuario=?) ORDER BY a.id",
                   (u["id_setor"], u["id_setor"], u["criado_em"], u["id"]))
    return [{**dict(r), "leitos": json.loads(r["leitos"] or "[]")} for r in rs]


def marcar_lidos(c, u, ids):
    for i in ids:
        c.execute("INSERT OR IGNORE INTO avisos_lidos VALUES(?,?,?)", (int(i), u["id"], agora()))
    return {"ok": True}


# ------------------------------------------------------------ painel e admin
def painel(c, u, d):
    nutri = u["perfil"] == "nutricionista"
    sid = u["id_setor"] if nutri else None
    out = {"data": d, "setores": [], "estoques": [], "pendentes": len(lista_correcoes(c, "pendente", u)),
           "divergencias": 0 if nutri else c.execute("SELECT COUNT(*) FROM movimentos WHERE data=? AND divergente=1", (d,)).fetchone()[0]}
    for s in c.execute("SELECT id,nome FROM setores WHERE (? IS NULL OR id=?) ORDER BY nome", (sid, sid)).fetchall():
        ls = linhas_mapa(c, s["id"], d)
        out["setores"].append({
            "id": s["id"], "nome": s["nome"], "leitos": len(ls), "ocupados": sum(l["ocupado"] for l in ls),
            "mapa_atualizado": any(l["data_base"] == d for l in ls),
            "rascunhos": c.execute("SELECT COUNT(*) FROM mapa_rascunho r JOIN leitos l ON l.id=r.id_leito WHERE r.data=? AND l.id_setor=?",
                                   (d, s["id"])).fetchone()[0],
            "refeicoes": sum(r["qtd"] for r in linhas_refeicoes(c, s["id"], d) if r["data_base"] == d)})
    if not nutri:
        n_itens = c.execute("SELECT COUNT(*) FROM itens").fetchone()[0]
        for e in ESTOQUES:
            r = c.execute("SELECT COUNT(*), MAX(atualizado_em) FROM estoque_dia WHERE data=? AND estoque=?", (d, e)).fetchone()
            out["estoques"].append({"estoque": e, "atualizados": r[0], "itens": n_itens, "ultima": r[1]})
    return out


def lista_correcoes(c, status, u=None):
    sql, a = "SELECT k.*,x.nome usuario FROM correcoes k JOIN usuarios x ON x.id=k.por_usuario WHERE k.status=?", [status]
    if u and u["perfil"] == "nutricionista":  # nutrição decide mapa e refeições do seu setor; estoque é do administrador
        sql += " AND k.tipo!='estoque'"
        if u["id_setor"]:
            sql, a = sql + " AND k.id_setor=?", a + [u["id_setor"]]
    return [{**dict(r), "valor_atual": json.loads(r["valor_atual"]), "valor_proposto": json.loads(r["valor_proposto"])}
            for r in c.execute(sql + " ORDER BY k.id", a)]


def decidir(c, u, cid, acao):
    k = c.execute("SELECT * FROM correcoes WHERE id=? AND status='pendente'", (cid,)).fetchone()
    if not k:
        raise Erro("Correção não encontrada ou já decidida.", 404)
    if u["perfil"] == "nutricionista" and (k["tipo"] == "estoque" or (u["id_setor"] and k["id_setor"] != u["id_setor"])):
        raise Erro("Esta correção não é do seu setor.", 403)
    if acao not in ("aprovar", "recusar"):
        raise Erro("Ação inválida.")
    if acao == "aprovar":  # valor aprovado passa a valer como valor da equipe (admin/nutrição)
        gravar(c, k["tipo"], k["data"], k["chave"], json.loads(k["valor_proposto"]), u["id"], u["perfil"], origem="aprovacao")
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
    setores = t("SELECT * FROM setores")
    leitos = t("SELECT * FROM leitos")
    mapa_completo = []
    # O estado sincronizado é sempre um snapshot completo: cada leito é enviado,
    # mesmo vazio, herdando o último registro até que exista uma alta explícita.
    for setor in setores:
        for linha in linhas_mapa(c, setor["id"], d):
            linha["id_setor"] = setor["id"]
            linha["data"] = d
            mapa_completo.append(linha)
    return {"esquema": 4, "data": d, "gerado_em": agora(), "setores": setores, "leitos": leitos,
            "suplementos_catalogo": t("SELECT * FROM suplementos_catalogo WHERE ativo=1 ORDER BY nome"),
            "itens": t("SELECT * FROM itens"), "mapa": mapa_completo,
            "mapa_rascunho": t("SELECT * FROM mapa_rascunho WHERE data=?", d),
            "refeicoes_cfg": t("SELECT * FROM refeicoes_cfg"), "janelas": t("SELECT * FROM janelas"),
            "refeicoes": t("SELECT * FROM refeicoes_dia WHERE data=?", d), "estoque": t("SELECT * FROM estoque_dia WHERE data=?", d),
            "movimentos": t("SELECT * FROM movimentos WHERE data=?", d), "avisos": t("SELECT * FROM avisos WHERE criado_em>=?", d),
            "correcoes_pendentes": lista_correcoes(c, "pendente")}


# ---------------------------------------------------------------------- rotas
def _regra_refeicao(funcao, *args, **kwargs):
    """Converte validações do módulo de refeições em erros HTTP 400."""
    try:
        return funcao(*args, **kwargs)
    except ValueError as exc:
        raise Erro(str(exc)) from None


def _rotear(c, ip, m, p, q, b, auth):
    if (m, p) == ("GET", "/api/status"):
        cfg = {r["chave"]: r["valor"] for r in c.execute(
            "SELECT chave,valor FROM sistema_config WHERE chave IN ('rede_ip_registrado','rede_ip_registrado_em')")}
        return {"status": "online", "ip_lan": ip_lan(), "porta": 8765,
                "ip_registrado": cfg.get("rede_ip_registrado"),
                "registrado_em": cfg.get("rede_ip_registrado_em")}
    if (m, p) == ("POST", "/api/login"):
        return login(c, ip, b)
    # Reutiliza o mesmo arquivo SQLite para os módulos operacionais compartilhados.
    db = c.execute("PRAGMA database_list").fetchone()[2]
    u = usuario(c, auth)
    perfil = u["perfil"]
    adm, staff = perfil == "admin", perfil in STAFF
    if (m, p) == ("GET", "/api/eu"):
        return {"usuario": pub(u), "hoje": hoje()}
    if (m, p) == ("POST", "/api/admin/rede/registrar"):
        if not adm:
            raise Erro("Somente o administrador pode registrar o endereço da rede.", 403)
        endereco = ip_lan()
        instante = agora()
        c.execute("INSERT INTO sistema_config(chave,valor) VALUES('rede_ip_registrado',?) "
                  "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (endereco,))
        c.execute("INSERT INTO sistema_config(chave,valor) VALUES('rede_ip_registrado_em',?) "
                  "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (instante,))
        return {"ok": True, "ip_lan": endereco, "registrado_em": instante}
    if (m, p) == ("GET", "/api/itens"):
        return {"itens": [dict(r) for r in c.execute(
            "SELECT id,nome,unidade,preco_unitario,embalagem_qtd,embalagem_un,categoria,validade FROM itens ORDER BY CASE WHEN validade IS NULL OR validade='' THEN 1 ELSE 0 END,validade,categoria COLLATE NOCASE,nome COLLATE NOCASE")]}
    if (m, p) == ("GET", "/api/orientacoes"):
        return {"orientacoes": [dict(r) for r in c.execute(
            "SELECT id,slug,titulo,texto,ordem,atualizado_em FROM orientacoes ORDER BY ordem,id")]}
    if (m, p) == ("GET", "/api/suplementos"):
        return {"suplementos": [dict(r) for r in c.execute(
            "SELECT id_suplemento,nome,modulo,emb_qtd,emb_un,kcal_100,ptn_100,lip_100,carb_100,sod_100 "
            "FROM suplementos_catalogo WHERE ativo=1 ORDER BY nome")]}
    if (m, p) == ("GET", "/api/setores"):
        todos = adm or (perfil in ("nutricionista", "copa") and not u["id_setor"])
        sql = "SELECT s.id,s.nome,(SELECT COUNT(*) FROM leitos WHERE id_setor=s.id) leitos FROM setores s %s ORDER BY s.nome"
        return {"setores": [dict(r) for r in c.execute(sql % ("" if todos else "WHERE s.id=%d" % (u["id_setor"] or 0)))]}
    if (m, p) == ("GET", "/api/avisos"):
        return {"avisos": avisos_do_usuario(c, u)}
    if (m, p) == ("POST", "/api/avisos/lidos"):
        return marcar_lidos(c, u, b.get("ids", []))

    # Refeições individualizadas: o servidor resolve o paciente pelo mapa atual
    # e grava um identificador de ocupação imutável, nunca pelo leito isolado.
    if p == "/api/refeicoes/janelas":
        if m == "GET":
            refeicoes_operacionais.inicializar(db)
            return {"janelas": refeicoes_operacionais.listar_janelas(db)}
        if m == "POST":
            if not staff:
                raise Erro("Somente a nutrição e o administrador podem configurar horários.", 403)
            refeicoes_operacionais.inicializar(db)
            publico, ref = b.get("publico"), b.get("refeicao")
            if not b.get("inicio") and not b.get("fim"):
                return {"removida": _regra_refeicao(refeicoes_operacionais.remover_janela, db, publico, ref)}
            _regra_refeicao(refeicoes_operacionais.salvar_janela, db, publico, ref, b.get("inicio"), b.get("fim"))
            return {"ok": True}
    if p == "/api/refeicoes/precos":
        if m == "GET":
            refeicoes_operacionais.inicializar(db)
            return {"precos": refeicoes_operacionais.listar_precos_refeicoes(db)}
        if m == "POST":
            if not staff:
                raise Erro("Somente a nutrição e o administrador podem configurar preços.", 403)
            refeicoes_operacionais.inicializar(db)
            publico, ref = b.get("publico"), b.get("refeicao")
            if b.get("valor_unitario") in (None, ""):
                return {"removido": _regra_refeicao(refeicoes_operacionais.remover_preco_refeicao, db, publico, ref)}
            _regra_refeicao(refeicoes_operacionais.salvar_preco_refeicao, db, publico, ref, b.get("valor_unitario"))
            return {"ok": True}
    if p == "/api/refeicoes/servicos":
        if perfil not in ("admin", "nutricionista", "copa"):
            raise Erro("Sem permissão.", 403)
        refeicoes_operacionais.inicializar(db)
        if m == "GET":
            s = setor_alvo(c, u, q.get("setor"))
            d = dia_alvo(u, q.get("data"))
            pacientes = []
            for l in linhas_mapa(c, s["id"], d):
                if l.get("ocupado") and l.get("nome") and l.get("id_ocupacao"):
                    pacientes.append({"id_leito": l["id_leito"], "leito": l["codigo"],
                                      "id_paciente": l["id_ocupacao"], "nome": l["nome"]})
            ids = {x["id_paciente"] for x in pacientes}
            autorizacoes = [a for a in refeicoes_operacionais.listar_autorizacoes_acompanhante(db, situacao="ativa")
                            if a["id_paciente"] in ids]
            return {"data": d, "setor": s, "pacientes": pacientes,
                    "autorizacoes": autorizacoes, "janelas": refeicoes_operacionais.listar_janelas(db),
                    "precos": refeicoes_operacionais.listar_precos_refeicoes(db)}
        if m == "POST":
            s = setor_alvo(c, u, b.get("setor"))
            d = dia_alvo(u, b.get("data"))
            publico = b.get("publico")
            ref = b.get("refeicao")
            if publico not in ("paciente", "funcionario", "acompanhante"):
                raise Erro("Público inválido.")
            instante = b.get("servido_em") or agora()
            try:
                instante_dt = datetime.fromisoformat(str(instante).replace("Z", "+00:00"))
                instante_dt = instante_dt.replace(tzinfo=TZ) if instante_dt.tzinfo is None else instante_dt.astimezone(TZ)
            except ValueError:
                raise Erro("Data e hora do serviço inválidas.")
            if not staff and instante_dt.date() > agora_dt().date():
                raise Erro("A Copa não pode registrar refeições com data futura.", 403)
            d = instante_dt.date().isoformat()
            preco = b.get("valor_unitario")
            if preco in (None, ""):
                cadastrado = next((x for x in refeicoes_operacionais.listar_precos_refeicoes(db, publico)
                                   if x["refeicao"] == ref), None)
                if not cadastrado:
                    raise Erro("Cadastre o custo por porção desta refeição para este público nas Configurações.")
                preco = cadastrado["valor_unitario"]
            dados = {"servido_em": instante_dt.isoformat(timespec="seconds"), "refeicao": ref, "publico": publico,
                     "destinatario_nome": b.get("destinatario_nome") or "",
                     "quantidade": b.get("quantidade", 1), "unidade": b.get("unidade", "porcao"),
                     "valor_unitario": preco, "destinatario_id": b.get("destinatario_id"),
                     "usuario_registro": u["nome"], "observacao": b.get("observacao")}
            if publico in ("paciente", "acompanhante"):
                lid = int(b.get("id_leito") or 0)
                paciente_atual = next((x for x in linhas_mapa(c, s["id"], d)
                                       if int(x["id_leito"]) == lid), None)
                historicos = c.execute(
                    "SELECT atualizado_em,antes_json FROM mapa_historico WHERE data=? AND id_leito=? ORDER BY atualizado_em DESC",
                    (d, lid)).fetchall()
                estado = paciente_atual
                for evento in historicos:
                    try:
                        instante_mudanca = datetime.fromisoformat(str(evento["atualizado_em"]).replace("Z", "+00:00"))
                        instante_mudanca = instante_mudanca.replace(tzinfo=TZ) if instante_mudanca.tzinfo is None else instante_mudanca.astimezone(TZ)
                    except ValueError:
                        continue
                    if instante_mudanca > instante_dt:
                        estado = json.loads(evento["antes_json"]) if evento["antes_json"] else None
                id_informado = str(b.get("id_paciente") or "")
                if (not estado or not estado.get("ocupado") or not estado.get("id_ocupacao")
                        or not id_informado or str(estado.get("id_ocupacao")) != id_informado):
                    raise Erro("O paciente informado não corresponde à ocupação do leito no horário da refeição.")
                nome_snapshot = str(estado.get("nome") or b.get("nome_paciente") or "")
                leito_snapshot = str((estado.get("codigo") if estado else None)
                                     or b.get("leito") or (paciente_atual or {}).get("codigo") or "")
                destinatario = ("Acompanhante(s) de " + nome_snapshot
                                if publico == "acompanhante" else nome_snapshot)
                dados.update(id_paciente=id_informado, nome_paciente=nome_snapshot,
                             leito=leito_snapshot, destinatario_nome=destinatario)
            if publico == "acompanhante":
                dados["id_autorizacao_acompanhante"] = b.get("id_autorizacao_acompanhante")
            rid = _regra_refeicao(refeicoes_operacionais.registrar_refeicao_servida, db, **dados)
            return {"ok": True, "id_servico": rid}
    if p == "/api/refeicoes/autorizacoes":
        if perfil not in ("admin", "nutricionista", "copa"):
            raise Erro("Sem permissão.", 403)
        refeicoes_operacionais.inicializar(db)
        if m == "GET":
            s = setor_alvo(c, u, q.get("setor"))
            d = dia_alvo(u, q.get("data"))
            ids = {x["id_ocupacao"] for x in linhas_mapa(c, s["id"], d)
                   if x.get("ocupado") and x.get("id_ocupacao")}
            return {"autorizacoes": [a for a in refeicoes_operacionais.listar_autorizacoes_acompanhante(db)
                                     if a["id_paciente"] in ids]}
        if m == "POST":
            if not staff:
                raise Erro("Somente a nutrição e o administrador podem autorizar refeições de acompanhantes.", 403)
            s = setor_alvo(c, u, b.get("setor"))
            d = dia_alvo(u, b.get("data"))
            lid = int(b.get("id_leito") or 0)
            paciente = next((x for x in linhas_mapa(c, s["id"], d)
                             if int(x["id_leito"]) == lid and x.get("ocupado") and x.get("id_ocupacao")), None)
            if not paciente:
                raise Erro("O leito não possui paciente ativo para vincular a autorização.")
            aid = _regra_refeicao(refeicoes_operacionais.salvar_autorizacao_acompanhante,
                db, id_paciente=paciente["id_ocupacao"], nome_paciente=paciente["nome"],
                leito=paciente["codigo"], quantidade=b.get("quantidade"),
                refeicoes=b.get("refeicoes"), justificativa=b.get("justificativa"),
                autorizado_por=b.get("responsavel_autorizacao") or u["nome"],
                registrado_por=u["nome"], inicio_vigencia=b.get("inicio_vigencia") or agora(),
                fim_vigencia=b.get("fim_vigencia"))
            return {"ok": True, "id_autorizacao": aid}
    if p.startswith("/api/refeicoes/autorizacoes/") and m == "POST":
        if not staff:
            raise Erro("Somente a nutrição e o administrador podem encerrar autorizações.", 403)
        refeicoes_operacionais.inicializar(db)
        aid = int(p.rsplit("/", 1)[1])
        situacao = b.get("situacao", "encerrada")
        if not _regra_refeicao(refeicoes_operacionais.encerrar_autorizacao_acompanhante, db, aid, situacao):
            raise Erro("Autorização não encontrada ou já encerrada.", 404)
        return {"ok": True, "situacao": situacao}
    if p == "/api/refeicoes/relatorio" and m == "GET":
        if not staff:
            raise Erro("Somente a nutrição e o administrador podem consultar custos.", 403)
        refeicoes_operacionais.inicializar(db)
        inicio = q.get("inicio") or hoje()
        fim = q.get("fim") or inicio
        try:
            date.fromisoformat(inicio); date.fromisoformat(fim)
        except ValueError:
            raise Erro("Informe datas válidas no formato AAAA-MM-DD.")
        if fim < inicio:
            raise Erro("A data final não pode ser anterior à inicial.")
        return {"inicio": inicio, "fim": fim,
                "custos": refeicoes_operacionais.resumo_custos(db, inicio, fim),
                "servicos": refeicoes_operacionais.listar_refeicoes_servidas(db, inicio, fim)}
    if p in ("/api/mapa", "/api/refeicoes"):
        if perfil not in ("admin", "nutricionista", "copa"):
            raise Erro("Sem permissão.", 403)
        mapa = p == "/api/mapa"
        if m == "GET" and perfil == "copa" and q.get("setor"):
            s = c.execute("SELECT * FROM setores WHERE id=?", (int(q.get("setor")),)).fetchone()
            if not s:
                raise Erro("Setor não encontrado.", 404)
            s = dict(s)
            d = hoje()
            lin = linhas_mapa(c, s["id"], d, staff) if mapa else linhas_refeicoes(c, s["id"], d)
            return {"data": d, "setor": s, "linhas": lin, "pendentes": pendentes(c, "mapa" if mapa else "refeicao", d)}
        s, d = setor_alvo(c, u, q.get("setor") or b.get("setor")), dia_alvo(u, q.get("data") or b.get("data"))
        if m == "GET":
            lin = linhas_mapa(c, s["id"], d, staff) if mapa else linhas_refeicoes(c, s["id"], d)
            return {"data": d, "setor": s, "linhas": lin, "pendentes": pendentes(c, "mapa" if mapa else "refeicao", d)}
        return (post_mapa if mapa else post_refeicoes)(c, u, s, d, b.get("linhas", []), bool(b.get("completo"))) if mapa else post_refeicoes(c, u, s, d, b.get("linhas", []))
    if m == "POST" and p.startswith("/api/almox/itens/"):
        if perfil not in ("admin", "estoque_almox"):
            raise Erro("Somente o almoxarifado pode classificar os produtos e atualizar a validade.", 403)
        iid = int(p.rsplit("/", 1)[1])
        if not c.execute("SELECT 1 FROM itens WHERE id=?", (iid,)).fetchone():
            raise Erro("Item não encontrado.", 404)
        categoria = str(b.get("categoria") or "Gêneros alimentícios").strip()
        categorias = ("Gêneros alimentícios", "Grãos e cereais", "Hortifrúti", "Carnes e proteínas", "Laticínios", "Temperos e condimentos", "Dietas enterais", "Suplementos", "Materiais", "Limpeza", "Outros")
        if categoria not in categorias:
            raise Erro("Selecione uma categoria válida.")
        validade = str(b.get("validade") or "").strip() or None
        if validade:
            validade = dia_valido(validade)
        c.execute("UPDATE itens SET categoria=?,validade=? WHERE id=?", (categoria, validade, iid))
        return {"ok": True}
    if p == "/api/estoque":
        est, d = estoque_alvo(u, q.get("estoque") or b.get("estoque")), dia_alvo(u, q.get("data") or b.get("data"))
        if m == "GET":
            origens = {o: {l["id_item"]: l["qtd"] for l in linhas_estoque(c, o, d)} for o in ORIGENS[est] if o != "externo"}
            return {"data": d, "estoque": est, "origens": ORIGENS[est], "saldos_origem": origens,
                    "linhas": linhas_estoque(c, est, d), "pendentes": pendentes(c, "estoque", d)}
        return post_estoque(c, u, est, d, b.get("linhas", []))
    if (m, p) == ("POST", "/api/estoque/reposicao"):
        return post_reposicao(c, u, estoque_alvo(u, b.get("estoque")), b)
    if p.startswith("/api/nutri/"):  # nutricionista e administrador
        if not staff:
            raise Erro("Somente a nutrição e o administrador.", 403)
        if (m, p) == ("GET", "/api/nutri/painel"):
            return painel(c, u, dia_alvo(u, q.get("data")))
        if (m, p) == ("GET", "/api/nutri/correcoes"):
            return {"correcoes": lista_correcoes(c, q.get("status", "pendente"), u)}
        if m == "POST" and p.startswith("/api/nutri/correcoes/"):
            return decidir(c, u, int(p.rsplit("/", 1)[1]), b.get("acao"))
        if (m, p) == ("POST", "/api/nutri/publicar"):
            return publicar(c, u, setor_alvo(c, u, b.get("setor")), dia_alvo(u, b.get("data")), b.get("texto"))
        if (m, p) == ("POST", "/api/nutri/avisos"):
            return novo_aviso(c, u, b)
        if (m, p) == ("POST", "/api/nutri/janelas"):
            return definir_janela(c, setor_alvo(c, u, b.get("setor")), b)
    if p.startswith("/api/admin/"):
        if not adm:
            raise Erro("Somente o administrador.", 403)
        if (m, p) == ("POST", "/api/admin/orientacoes"):
            titulo = str(b.get("titulo", "")).strip()
            texto = str(b.get("texto", "")).strip()
            if not titulo or len(titulo) > 120:
                raise Erro("Informe um título com até 120 caracteres.")
            if not texto or len(texto) > 8000:
                raise Erro("Informe o texto (máximo de 8.000 caracteres).")
            if b.get("id") not in (None, ""):
                cur = c.execute("UPDATE orientacoes SET titulo=?,texto=?,atualizado_por=?,atualizado_em=? WHERE id=?",
                                (titulo, texto, u["id"], agora(), int(b["id"])))
                if not cur.rowcount:
                    raise Erro("Tópico não encontrado.", 404)
            else:
                ordem = c.execute("SELECT COALESCE(MAX(ordem),0)+10 FROM orientacoes").fetchone()[0]
                slug = "extra-" + secrets.token_hex(8)
                c.execute("INSERT INTO orientacoes(slug,titulo,texto,ordem,atualizado_por,atualizado_em) VALUES(?,?,?,?,?,?)",
                          (slug, titulo, texto, ordem, u["id"], agora()))
            return {"ok": True}
        if (m == "GET" and p == "/api/admin/mapa/atividade"):
            periodo = str(q.get("periodo") or "mes")
            ano = int(q.get("ano") or hoje()[:4])
            if not 2000 <= ano <= 2100:
                raise Erro("Ano inválido.")
            if periodo == "mes":
                mes = int(q.get("mes") or hoje()[5:7])
                if not 1 <= mes <= 12:
                    raise Erro("Mês inválido.")
                chave = "%04d-%02d" % (ano, mes)
                filtro = "substr(atualizado_em,1,7)=?"
            elif periodo == "ano":
                chave = "%04d" % ano
                filtro = "substr(atualizado_em,1,4)=?"
            else:
                raise Erro("Período inválido.")
            ranking = [dict(r) for r in c.execute(
                "SELECT por_usuario id_usuario,por_nome nome,por_perfil perfil,COUNT(*) atualizacoes,"
                "COUNT(DISTINCT data) dias_ativos,COUNT(DISTINCT id_setor) setores "
                "FROM mapa_historico WHERE por_perfil='copa' AND " + filtro +
                " GROUP BY por_usuario,por_nome,por_perfil ORDER BY atualizacoes DESC,nome COLLATE NOCASE",
                (chave,))]
            return {"periodo": periodo, "chave": chave, "ranking": ranking,
                    "total": sum(x["atualizacoes"] for x in ranking)}
        if (m, p) == ("GET", "/api/admin/exportar"):
            return exportar(c, dia_alvo(u, q.get("data")))
        if (m, p) == ("GET", "/api/admin/refeicoes"):
            return {"refeicoes": [cfg_refeicoes(c)[r] for r in REFEICOES]}
        if (m, p) == ("POST", "/api/admin/refeicoes"):
            return definir_refeicao(c, b)
        if (m, p) == ("GET", "/api/admin/usuarios"):
            return {"usuarios": [{k: r[k] for k in ("id", "login", "nome", "perfil", "id_setor", "ativo")}
                                 for r in c.execute("SELECT * FROM usuarios ORDER BY login")]}
        if (m, p) == ("POST", "/api/admin/usuarios"):
            criar_usuario(c, b.get("login"), b.get("nome"), b.get("perfil"), b.get("id_setor"), b.get("senha", ""))
            return {"ok": True}
        if m == "POST" and p.startswith("/api/admin/usuarios/"):
            uid = int(p.rsplit("/", 1)[1])
            if "ativo" in b:
                if uid == u["id"] and not b["ativo"]:
                    raise Erro("Você não pode desativar o próprio usuário.")
                c.execute("UPDATE usuarios SET ativo=? WHERE id=?", (int(bool(b["ativo"])), uid))
            if "id_setor" in b:
                if b["id_setor"] and not c.execute("SELECT 1 FROM setores WHERE id=?", (b["id_setor"],)).fetchone():
                    raise Erro("Setor inexistente.")
                c.execute("UPDATE usuarios SET id_setor=? WHERE id=? AND perfil='nutricionista'", (b["id_setor"] or None, uid))
            if b.get("senha"):
                definir_senha(c, uid, b["senha"])
            return {"ok": True}

        if (m, p) == ("GET", "/api/admin/almox/pedidos"):
            if not adm:
                raise Erro("Apenas administradores podem consultar pedidos.", 403)
            pedidos = [dict(r) for r in c.execute(
                """SELECT p.id,p.id_item,i.nome AS item,p.qtd,p.solicitado_em,p.solicitado_nome,
                          p.fornecedor,p.observacao,p.status,p.recebido_em,p.recebido_nome,p.id_movimento
                   FROM pedidos_estoque p JOIN itens i ON i.id=p.id_item
                   ORDER BY CASE p.status WHEN 'pendente' THEN 0 ELSE 1 END,p.solicitado_em DESC
                   LIMIT 200""")]
            return {"pedidos": pedidos}
        if (m, p) == ("GET", "/api/admin/almox/prazos"):
            if not adm:
                raise Erro("Apenas administradores podem consultar prazos.", 403)
            prazos = [dict(r) for r in c.execute(
                """SELECT i.id AS id_item,i.nome,
                          COUNT(CASE WHEN p.status='recebido' THEN 1 END) AS pedidos_recebidos,
                          ROUND(AVG(CASE WHEN p.status='recebido'
                              THEN julianday(substr(p.recebido_em,1,10))-julianday(substr(p.solicitado_em,1,10))
                              END),1) AS prazo_medio_dias,
                          SUM(CASE WHEN p.status='pendente' THEN 1 ELSE 0 END) AS pendentes
                   FROM itens i LEFT JOIN pedidos_estoque p ON p.id_item=i.id
                   GROUP BY i.id,i.nome
                   HAVING pedidos_recebidos>0 OR pendentes>0
                   ORDER BY prazo_medio_dias DESC,i.nome COLLATE NOCASE""")]
            return {"prazos": prazos}
        if (m, p) == ("POST", "/api/admin/almox/pedidos"):
            if not adm:
                raise Erro("Apenas administradores podem registrar pedidos.", 403)
            iid = int(b.get("id_item") or 0)
            qtd = num(b.get("qtd"), "quantidade solicitada")
            if qtd <= 0:
                raise Erro("A quantidade solicitada precisa ser maior que zero.")
            if not c.execute("SELECT 1 FROM itens WHERE id=? AND ativo=1", (iid,)).fetchone():
                raise Erro("Insumo não encontrado ou inativo.", 404)
            cur = c.execute(
                """INSERT INTO pedidos_estoque(id_item,qtd,solicitado_em,solicitado_por,
                           solicitado_nome,fornecedor,observacao,status)
                   VALUES(?,?,?,?,?,?,?,'pendente')""",
                (iid,qtd,agora(),u["id"],u["nome"],
                 str(b.get("fornecedor") or "").strip() or None,
                 str(b.get("observacao") or "").strip() or None))
            return {"ok": True, "id": cur.lastrowid}
        if m == "POST" and p.startswith("/api/admin/almox/pedidos/") and p.endswith("/receber"):
            if not adm:
                raise Erro("Apenas administradores podem registrar recebimentos.", 403)
            pid = int(p.split("/")[-2])
            pedido = c.execute("SELECT * FROM pedidos_estoque WHERE id=?", (pid,)).fetchone()
            if not pedido:
                raise Erro("Pedido não encontrado.", 404)
            if pedido["status"] != "pendente":
                raise Erro("Este pedido já foi finalizado.")
            saldo = post_reposicao(c,u,"almox",{
                "id_item": pedido["id_item"], "qtd": pedido["qtd"], "origem": "externo"
            })
            id_movimento = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            c.execute(
                """UPDATE pedidos_estoque SET status='recebido',recebido_em=?,
                   recebido_por=?,recebido_nome=?,id_movimento=? WHERE id=?""",
                (agora(),u["id"],u["nome"],id_movimento,pid))
            return {"ok": True, "saldo": saldo, "id_movimento": id_movimento}
        if (m, p) == ("POST", "/api/admin/setores"):
            return criar_setor(c, b)
        if (m == "POST" and p == "/api/admin/itens") or (m == "POST" and p.startswith("/api/admin/itens/")):
            nome = str(b.get("nome", "")).strip()
            unidade = str(b.get("unidade", "un")).strip() or "un"
            preco = None if b.get("preco_unitario") in (None, "") else num(b.get("preco_unitario"), "preço unitário")
            categoria = str(b.get("categoria") or "Gêneros alimentícios").strip()
            categorias = ("Gêneros alimentícios", "Grãos e cereais", "Hortifrúti", "Carnes e proteínas", "Laticínios", "Temperos e condimentos", "Dietas enterais", "Suplementos", "Materiais", "Limpeza", "Outros")
            if categoria not in categorias:
                raise Erro("Selecione uma categoria válida.")
            validade = str(b.get("validade") or "").strip() or None
            if validade:
                validade = dia_valido(validade)
            emb_qtd = None if b.get("embalagem_qtd") in (None, "") else num(b.get("embalagem_qtd"), "conteúdo da embalagem")
            emb_un = str(b.get("embalagem_un") or "").strip().lower() or None
            if emb_qtd is not None and emb_qtd <= 0:
                raise Erro("O conteúdo da embalagem precisa ser maior que zero.")
            emb_qtd, emb_un = normalizar_embalagem(emb_qtd, emb_un)
            tbca_id = str(b.get("tbca_id") or "").strip() or None
            if p == "/api/admin/itens":
                if not nome:
                    raise Erro("Informe o nome do item.")
                try:
                    cur = c.execute("INSERT INTO itens(nome,unidade,preco_unitario,embalagem_qtd,embalagem_un,tbca_id,categoria,validade) VALUES(?,?,?,?,?,?,?,?)",
                                    (nome, unidade, preco, emb_qtd, emb_un, tbca_id, categoria, validade))
                except sqlite3.IntegrityError:
                    raise Erro("Esse item já existe.")
                return {"ok": True, "id": cur.lastrowid}
            iid = int(p.rsplit("/", 1)[1])
            if not c.execute("SELECT 1 FROM itens WHERE id=?", (iid,)).fetchone():
                raise Erro("Item não encontrado.", 404)
            if "tbca_id" not in b:
                existente = c.execute("SELECT tbca_id FROM itens WHERE id=?", (iid,)).fetchone()
                tbca_id = existente["tbca_id"] if existente else None
            c.execute("UPDATE itens SET preco_unitario=?,embalagem_qtd=?,embalagem_un=?,tbca_id=?,categoria=?,validade=? WHERE id=?",
                      (preco, emb_qtd, emb_un, tbca_id, categoria, validade, iid))
            return {"ok": True}
    raise Erro("Rota não encontrada.", 404)


def rotear(db, ip, m, p, q, b, auth, operation_id=None):
    """Executa uma rota e, quando solicitado, torna POSTs repetidos idempotentes."""
    with LOCK:
        c = conectar(db)
        try:
            fingerprint = None
            if operation_id:
                if m != "POST" or p == "/api/login":
                    raise Erro("Identificador de operação inválido para esta rota.", 400)
                token = auth[7:] if auth.startswith("Bearer ") else ""
                sessao = SESSOES.get(token)
                if not sessao or sessao[1] < time.time():
                    raise Erro("Sessão expirada. Entre novamente.", 401)
                fingerprint = hashlib.sha256(json.dumps(
                    {"usuario": sessao[0], "metodo": m, "rota": p, "dados": b},
                    ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")).hexdigest()
                anterior = c.execute(
                    "SELECT fingerprint,resultado_json FROM operacoes_idempotentes WHERE operation_id=?",
                    (str(operation_id),)
                ).fetchone()
                if anterior:
                    if not hmac.compare_digest(anterior["fingerprint"], fingerprint):
                        raise Erro("Identificador de operação já utilizado com outros dados.", 409)
                    return json.loads(anterior["resultado_json"])
            r = _rotear(c, ip, m, p, q, b, auth)
            if operation_id:
                c.execute(
                    "INSERT INTO operacoes_idempotentes(operation_id,fingerprint,resultado_json,criado_em) VALUES(?,?,?,?)",
                    (str(operation_id), fingerprint, json.dumps(r, ensure_ascii=False), agora())
                )
                c.execute("DELETE FROM operacoes_idempotentes WHERE criado_em < ?",
                          ((datetime.now(TZ) - timedelta(days=30)).isoformat(timespec="seconds"),))
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

    def _enviar_apk(self, arquivo):
        corpo = arquivo.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.android.package-archive")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Content-Disposition", 'attachment; filename="NutriLab-Mobile.apk"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(corpo)

    def _tratar(self, m):
        try:
            if not ipaddress.ip_address(self.client_address[0]).is_private:
                raise Erro("Acesso permitido somente pela rede local.", 403)
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            if m == "GET" and u.path == "/download/NutriLab-Mobile.apk":
                apk = (AQUI / "apk" / "saida" / "NutriLab-Mobile.apk").resolve()
                if not apk.is_file() or AQUI.resolve() not in apk.parents:
                    raise Erro("APK não encontrado nesta instalação. Recompile o pacote do NutriLab.", 404)
                return self._enviar_apk(apk)
            if m == "GET" and not u.path.startswith("/api/"):
                raiz = (AQUI / "static").resolve()
                if u.path in ("/", "/index.html"):
                    return self._enviar(200, (raiz / "index.html").read_bytes(), "text/html; charset=utf-8")
                if u.path.startswith("/static/"):
                    nome = unquote(u.path[len("/static/"):])
                    arquivo = (raiz / nome).resolve()
                    if raiz not in arquivo.parents or not arquivo.is_file():
                        raise Erro("Arquivo estático não encontrado.", 404)
                    tipo = mimetypes.guess_type(arquivo.name)[0] or "application/octet-stream"
                    return self._enviar(200, arquivo.read_bytes(), tipo)
                raise Erro("Página não encontrada.", 404)
            b = {}
            if m == "POST":
                n = min(int(self.headers.get("Content-Length") or 0), 1_000_000)
                b = json.loads(self.rfile.read(n) or b"{}")
            self._enviar(200, rotear(self.server.db, self.client_address[0], m, u.path, q, b,
                self.headers.get("Authorization", ""), self.headers.get("X-Nutrilab-Operation-Id")))
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
