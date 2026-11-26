# -*- coding: utf-8 -*-
"""Integração do NutriLab (desktop) com o NutriLab Mobile. Criado em 12/11/2026.

Desktop e servidor mobile ficam no MESMO computador: aqui usamos as funções de mobile/servidor.py sobre o banco do
servidor (mobile/dados/mobile.db), sem HTTP, sem senha e sem compartilhar arquivo pela rede.

RECEBER (mobile -> desktop)
  ler_mobile()       lê o que o mobile tem de um dia;
  propostas_mapa()   compara o mapa que chegou (inclusive correções da copa que esperam autorização) com o do desktop;
  aplicar_mapa()     grava no desktop só o que o nutricionista aprovou (e aprova a correção no mobile);
  ignorar_mapa()     ignora (leito) ou recusa (correção); importar_refeicoes()/importar_estoque() guardam as
                     contagens nas tabelas Mobile_*.
ENVIAR (desktop -> mobile)
  enviar_mapa()      grava o mapa do dia no mobile e PUBLICA para a copa (a copa recebe o aviso com os leitos alterados).
Descrição completa: docs/mobile/INTEGRACAO_DESKTOP.md
"""
import hashlib
import json
import os
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone, timedelta

import mapa_db as mdb

_SCHEMA = """
CREATE TABLE IF NOT EXISTS Mobile_Extra (data TEXT, setor TEXT, leito TEXT, dieta TEXT, diagnostico TEXT, atualizado_em TEXT,
    PRIMARY KEY (data, setor, leito));
CREATE TABLE IF NOT EXISTS Mobile_Visto (data TEXT, setor TEXT, leito TEXT, assinatura TEXT, PRIMARY KEY (data, setor, leito));
CREATE TABLE IF NOT EXISTS Mobile_Enviado (setor TEXT, leito TEXT, com_paciente INTEGER, data TEXT, PRIMARY KEY (setor, leito));
CREATE TABLE IF NOT EXISTS Mobile_Refeicoes (data TEXT, setor TEXT, refeicao TEXT, qtd REAL, atualizado_em TEXT,
    PRIMARY KEY (data, setor, refeicao));
CREATE TABLE IF NOT EXISTS Mobile_Estoque_Dia (data TEXT, estoque TEXT, item TEXT, unidade TEXT, qtd REAL, atualizado_em TEXT,
    PRIMARY KEY (data, estoque, item));
CREATE TABLE IF NOT EXISTS Mobile_Movimentos (data TEXT, id_mobile INTEGER, hora TEXT, origem TEXT, destino TEXT, item TEXT,
    unidade TEXT, qtd REAL, divergente INTEGER, id_item_mobile INTEGER, por_usuario INTEGER,
    valor_unitario_snapshot REAL, custo_snapshot REAL, observacao TEXT, PRIMARY KEY (data, id_mobile));
"""

# Campos do registro do desktop que o mobile conhece (o resto do registro nunca é tocado).
_BASE_NOVO = {"acompanhante": 0, "dm": 0, "has": 0, "laxativa": 0, "constipante": 0, "drc": 0}
_CONSISTENCIAS = {"geral": "Livre", "livre": "Livre", "branda": "Branda", "pastosa": "Pastosa", "líquida": "Líquida",
                  "liquida": "Líquida", "líq/past": "Líq/Past", "liq/past": "Líq/Past"}


class ErroMobile(Exception):
    """Problema que o usuário consegue resolver (servidor ausente, banco não encontrado...)."""


def _agora():
    return datetime.now().isoformat(timespec="seconds")


def garantir_tabelas(db):
    """Garante as tabelas locais e acrescenta metadados às versões antigas sem apagar histórico."""
    with closing(mdb.conectar(db)) as c:
        c.executescript(_SCHEMA)
        colunas = {r[1] for r in c.execute("PRAGMA table_info(Mobile_Movimentos)")}
        for nome, tipo in (("id_item_mobile", "INTEGER"), ("por_usuario", "INTEGER"),
                           ("valor_unitario_snapshot", "REAL"), ("custo_snapshot", "REAL"), ("observacao", "TEXT")):
            if nome not in colunas:
                c.execute("ALTER TABLE Mobile_Movimentos ADD COLUMN %s %s" % (nome, tipo))
        c.commit()


def caminho_mobile_db(db, base_dir):
    # No executável, _MEIPASS é temporário e não pode guardar o banco gravável.
    if getattr(sys, "frozen", False):
        raiz = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        padrao = os.path.join(raiz, "NutriLab", "mobile", "mobile.db")
    else:
        padrao = os.path.join(base_dir, "mobile", "dados", "mobile.db")
    configurado = mdb.obter_config(db, "mobile_db", padrao)
    return configurado or padrao


# ---------------------------------------------------------------- servidor mobile
def _servidor():
    try:
        from mobile import servidor
    except ImportError as e:
        raise ErroMobile("Não encontrei o servidor do mobile (pasta 'mobile'). Aplique antes o pacote "
                         "'Att 14.11.26 Mobile Completo'.") from e
    return servidor


def _abrir_mobile(mobile_db):
    sv = _servidor()
    if not all(hasattr(sv, n) for n in ("migrar", "publicar", "decidir", "linhas_mapa", "exportar")):
        raise ErroMobile("O servidor mobile instalado é de uma versão antiga e não serve para esta integração.\n"
                         "Aplique o pacote 'Att 14.11.26 Mobile Completo', que atualiza o servidor.")
    if not os.path.exists(mobile_db):
        raise ErroMobile("O banco do mobile ainda não existe:\n%s\nLigue o servidor uma vez (mobile\\iniciar_servidor.bat)." % mobile_db)
    c = sv.conectar(mobile_db)
    try:
        c.execute("PRAGMA busy_timeout=15000")
        c.executescript(sv.ESQUEMA)  # bancos criados pela primeira versão do mobile
        sv.migrar(c)
        c.commit()
    except Exception:
        c.close()  # no Windows, conexão esquecida aberta trava o arquivo
        raise
    return sv, c


def _admin(c):
    r = c.execute("SELECT * FROM usuarios WHERE perfil='admin' AND ativo=1 ORDER BY id LIMIT 1").fetchone()
    if not r:
        raise ErroMobile("O banco do mobile não tem o usuário administrador. Ligue o servidor uma vez.")
    return dict(r)


def ler_mobile(mobile_db, data_iso):
    """Tudo o que o mobile tem do dia (mapa, refeições, estoque, movimentos) + correções pendentes."""
    sv, c = _abrir_mobile(mobile_db)
    try:
        return sv.exportar(c, data_iso)
    finally:
        c.close()


def ler_produtos_almox(mobile_db):
    """Lê produtos, preço/embalagem e o saldo mais recente do Almoxarifado, sem misturar outros estoques."""
    sv, c = _abrir_mobile(mobile_db)
    try:
        with sv.LOCK:
            rows = c.execute("""SELECT i.id AS id_item,i.nome,i.unidade,i.preco_unitario,
                    i.embalagem_qtd,i.embalagem_un,i.tbca_id,i.categoria,i.validade,e.qtd,e.data AS data_base
                FROM itens i
                LEFT JOIN estoque_dia e ON e.id_item=i.id AND e.estoque='almox'
                  AND e.data=(SELECT MAX(e2.data) FROM estoque_dia e2
                              WHERE e2.id_item=i.id AND e2.estoque='almox')
                ORDER BY CASE WHEN i.validade IS NULL OR i.validade='' THEN 1 ELSE 0 END,i.validade,i.categoria COLLATE NOCASE,i.nome COLLATE NOCASE""").fetchall()
            return [dict(row) for row in rows]
    finally:
        c.close()



def importar_classificacao_almox_mobile(db, mobile_db):
    """Importa categoria e validade preenchidas pelo almoxarifado no mobile para o cadastro desktop.

    Só aplica categoria não padrão e validade preenchida; valores vazios do mobile antigo não apagam dados do desktop.
    Para limpar uma validade, use o cadastro desktop.
    """
    import almox_db as adb
    adb.inicializar(db)
    sv, mobile = _abrir_mobile(mobile_db)
    atualizados, sem_vinculo = 0, 0
    try:
        with closing(mdb.conectar(db)) as local:
            tabelas = {r[0] for r in local.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "Almox_Mobile_Vinculos" not in tabelas:
                return {"atualizados": 0, "sem_vinculo": 0}
            vinculos = [dict(r) for r in local.execute(
                "SELECT id_item_desktop,id_item_mobile FROM Almox_Mobile_Vinculos").fetchall()]
            for v in vinculos:
                item = mobile.execute("SELECT categoria,validade FROM itens WHERE id=?", (v["id_item_mobile"],)).fetchone()
                if not item:
                    sem_vinculo += 1
                    continue
                categoria = item["categoria"] if item["categoria"] and item["categoria"] != "Gêneros alimentícios" else None
                validade = item["validade"] or None
                if categoria is None and validade is None:
                    continue
                local.execute("UPDATE Almox_Itens SET categoria=COALESCE(?,categoria),validade=COALESCE(?,validade),atualizado_em=? WHERE id_item=?",
                              (categoria, validade, _agora(), v["id_item_desktop"]))
                atualizados += 1
            local.commit()
    finally:
        mobile.close()
    return {"atualizados": atualizados, "sem_vinculo": sem_vinculo}


def sincronizar_catalogo_almox_desktop(db, mobile_db):
    """Publica itens do Almoxarifado desktop no catálogo central mobile e atualiza o espelho da Gestão Alimentar.

    O vínculo entre IDs é persistente e independente dos autoincrementos dos dois bancos. A sincronização
    nunca replica saldos/movimentos: cada estoque mantém seu próprio livro-razão.
    """
    import unicodedata
    import almox_db as adb
    import gestao_alimentar_db as gadb

    adb.inicializar(db)
    with closing(mdb.conectar(db)) as local:
        local.executescript("""
            CREATE TABLE IF NOT EXISTS Almox_Mobile_Vinculos(
                id_item_desktop INTEGER PRIMARY KEY,
                id_item_mobile INTEGER NOT NULL UNIQUE,
                sincronizado_em TEXT NOT NULL
            );
        """)
        local.commit()
        itens = [dict(r) for r in local.execute(
            "SELECT * FROM Almox_Itens ORDER BY id_item").fetchall()]

    sv, mobile = _abrir_mobile(mobile_db)
    sincronizados, criados, atualizados, erros = [], 0, 0, []
    try:
        with sv.LOCK:
            mobile.execute("BEGIN IMMEDIATE")
            try:
                for item in itens:
                    nome = str(item.get("nome") or "").strip()
                    unidade = str(item.get("unidade") or "").strip()
                    if not nome or not unidade:
                        erros.append({"id_item": item["id_item"], "erro": "Nome ou unidade vazios."})
                        continue
                    vinculo = mdb.conectar(db)
                    try:
                        link = vinculo.execute(
                            "SELECT id_item_mobile FROM Almox_Mobile_Vinculos WHERE id_item_desktop=?",
                            (item["id_item"],)).fetchone()
                    finally:
                        vinculo.close()
                    mobile_id = int(link["id_item_mobile"]) if link else None
                    existente = mobile.execute("SELECT id,nome,unidade FROM itens WHERE id=?", (mobile_id,)).fetchone() if mobile_id else None
                    if mobile_id and not existente:
                        mobile_id = None
                    if mobile_id is None:
                        normalizar = lambda v: "".join(ch for ch in unicodedata.normalize("NFKD", str(v or "").casefold())
                                                       if not unicodedata.combining(ch)).strip()
                        iguais = mobile.execute("SELECT id,nome,unidade FROM itens WHERE lower(trim(nome))=lower(trim(?))",
                                                 (nome,)).fetchall()
                        correspondentes = [r for r in iguais if normalizar(r["unidade"]) == normalizar(unidade)]
                        if len(correspondentes) > 1:
                            erros.append({"id_item": item["id_item"], "erro": "Mais de um produto correspondente no catálogo mobile."})
                            continue
                        if correspondentes:
                            mobile_id = int(correspondentes[0]["id"])
                            existente = correspondentes[0]
                        elif iguais:
                            erros.append({"id_item": item["id_item"], "erro": "Já existe produto com o mesmo nome e unidade diferente no mobile; revise o cadastro antes de sincronizar."})
                            continue
                    valores = (nome, unidade, item.get("valor_unitario"), item.get("embalagem_qtd"),
                               item.get("embalagem_un"), int(bool(item.get("ativo", 1))),
                               item.get("categoria") or "Gêneros alimentícios", item.get("validade"))
                    if mobile_id is None:
                        try:
                            cur = mobile.execute(
                                "INSERT INTO itens(nome,unidade,preco_unitario,embalagem_qtd,embalagem_un,ativo,categoria,validade) VALUES(?,?,?,?,?,?,?,?)",
                                valores)
                        except sqlite3.IntegrityError:
                            erros.append({"id_item": item["id_item"], "erro": "Conflito de nome no catálogo mobile; nenhum item foi duplicado."})
                            continue
                        mobile_id = int(cur.lastrowid)
                        criados += 1
                    else:
                        mobile.execute(
                            "UPDATE itens SET nome=?,unidade=?,preco_unitario=?,embalagem_qtd=?,embalagem_un=?,ativo=?,categoria=?,validade=? WHERE id=?",
                            (*valores, mobile_id))
                        atualizados += 1
                    sincronizados.append((int(item["id_item"]), mobile_id))
                mobile.commit()
            except Exception:
                mobile.rollback()
                raise
    finally:
        mobile.close()

    agora = _agora()
    with closing(mdb.conectar(db)) as local:
        local.executemany(
            "INSERT INTO Almox_Mobile_Vinculos(id_item_desktop,id_item_mobile,sincronizado_em) VALUES(?,?,?) "
            "ON CONFLICT(id_item_desktop) DO UPDATE SET id_item_mobile=excluded.id_item_mobile,sincronizado_em=excluded.sincronizado_em",
            [(a, b, agora) for a, b in sincronizados])
        local.commit()

    produtos = ler_produtos_almox(mobile_db)
    gadb.inicializar(db)
    gadb.sincronizar_produtos_almox(db, produtos)
    return {"sincronizados": len(sincronizados), "criados": criados, "atualizados": atualizados,
            "erros": erros, "produtos_espelhados": len(produtos)}


def ler_janelas_refeicoes(mobile_db):
    """Lê os horários ativos configurados no servidor mobile para classificar retiradas por refeição."""
    sv, c = _abrir_mobile(mobile_db)
    try:
        with sv.LOCK:
            return {
                str(r["refeicao"]).strip().lower(): {"abre": r["abre"], "fecha": r["fecha"]}
                for r in c.execute("SELECT refeicao,abre,fecha FROM refeicoes_cfg WHERE ativa=1")
            }
    finally:
        c.close()

def criar_pedido_almox(mobile_db, id_item, qtd, fornecedor=None, observacao=None, usuario_nome=None):
    sv, c = _abrir_mobile(mobile_db)
    try:
        with sv.LOCK:
            iid = int(id_item)
            quantidade = sv.num(qtd, "quantidade solicitada")
            if quantidade <= 0:
                raise ErroMobile("A quantidade solicitada precisa ser maior que zero.")
            if not c.execute("SELECT 1 FROM itens WHERE id=? AND ativo=1", (iid,)).fetchone():
                raise ErroMobile("Insumo não encontrado ou inativo.")
            admin = _admin(c)
            nome = str(usuario_nome or admin["nome"]).strip()
            cur = c.execute(
                """INSERT INTO pedidos_estoque(id_item,qtd,solicitado_em,solicitado_por,
                           solicitado_nome,fornecedor,observacao,status)
                   VALUES(?,?,?,?,?,?,?,'pendente')""",
                (iid,quantidade,sv.agora(),admin["id"],nome,
                 str(fornecedor or "").strip() or None,
                 str(observacao or "").strip() or None))
            c.commit()
            return int(cur.lastrowid)
    finally:
        c.close()


def receber_pedido_almox(mobile_db, id_pedido, usuario_nome=None):
    sv, c = _abrir_mobile(mobile_db)
    try:
        with sv.LOCK:
            pid = int(id_pedido)
            pedido = c.execute("SELECT * FROM pedidos_estoque WHERE id=?", (pid,)).fetchone()
            if not pedido:
                raise ErroMobile("Pedido não encontrado.")
            if pedido["status"] != "pendente":
                raise ErroMobile("Este pedido já foi finalizado.")
            admin = _admin(c)
            nome = str(usuario_nome or admin["nome"]).strip()
            saldo = sv.post_reposicao(c, admin, "almox", {
                "id_item": pedido["id_item"], "qtd": pedido["qtd"], "origem": "externo"
            })
            id_movimento = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            c.execute(
                """UPDATE pedidos_estoque SET status='recebido',recebido_em=?,
                   recebido_por=?,recebido_nome=?,id_movimento=? WHERE id=?""",
                (sv.agora(),admin["id"],nome,id_movimento,pid))
            c.commit()
            return {"saldo": saldo, "id_movimento": id_movimento}
    finally:
        c.close()


def listar_pedidos_almox(mobile_db, apenas_pendentes=False):
    sv, c = _abrir_mobile(mobile_db)
    try:
        with sv.LOCK:
            where = "WHERE p.status='pendente'" if apenas_pendentes else ""
            return [dict(r) for r in c.execute(
                """SELECT p.*,i.nome AS item FROM pedidos_estoque p
                   JOIN itens i ON i.id=p.id_item """ + where +
                " ORDER BY CASE p.status WHEN 'pendente' THEN 0 ELSE 1 END,p.solicitado_em DESC LIMIT 300")]
    finally:
        c.close()


def listar_prazos_almox(mobile_db):
    sv, c = _abrir_mobile(mobile_db)
    try:
        with sv.LOCK:
            return [dict(r) for r in c.execute(
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
    finally:
        c.close()


def prazo_medio_produto(mobile_db, id_item):
    return next((p for p in listar_prazos_almox(mobile_db)
                 if int(p["id_item"]) == int(id_item)), None)


def salvar_produto_almox(mobile_db, dados, id_item=None, estoque_inicial=None):
    """Cria/edita um item compartilhado pelo desktop, preservando o histórico do saldo inicial."""
    sv, c = _abrir_mobile(mobile_db)
    try:
        with sv.LOCK:
            nome = str(dados.get("nome") or "").strip()
            unidade = str(dados.get("unidade") or "").strip()
            if not nome:
                raise ErroMobile("Informe o nome do produto.")
            if not unidade:
                raise ErroMobile("Informe a unidade de estoque (ex.: pacote, frasco ou lata).")
            preco = None if dados.get("preco_unitario") in (None, "") else sv.num(dados.get("preco_unitario"), "preço unitário")
            if preco is not None and preco < 0:
                raise ErroMobile("O preço unitário não pode ser negativo.")
            emb_qtd = None if dados.get("embalagem_qtd") in (None, "") else sv.num(dados.get("embalagem_qtd"), "conteúdo da embalagem")
            emb_un = str(dados.get("embalagem_un") or "").strip().lower() or None
            if emb_qtd is not None and emb_qtd <= 0:
                raise ErroMobile("O conteúdo da embalagem precisa ser maior que zero.")
            emb_qtd, emb_un = sv.normalizar_embalagem(emb_qtd, emb_un)
            tbca_id = str(dados.get("tbca_id") or "").strip() or None
            if id_item is None:
                try:
                    cur = c.execute(
                        "INSERT INTO itens(nome,unidade,preco_unitario,embalagem_qtd,embalagem_un,tbca_id) VALUES(?,?,?,?,?,?)",
                        (nome, unidade, preco, emb_qtd, emb_un, tbca_id))
                except sqlite3.IntegrityError as exc:
                    raise ErroMobile("Já existe um produto com esse nome.") from exc
                iid = int(cur.lastrowid)
            else:
                iid = int(id_item)
                if not c.execute("SELECT 1 FROM itens WHERE id=?", (iid,)).fetchone():
                    raise ErroMobile("Produto não encontrado.")
                try:
                    c.execute(
                        "UPDATE itens SET nome=?,unidade=?,preco_unitario=?,embalagem_qtd=?,embalagem_un=?,tbca_id=? WHERE id=?",
                        (nome, unidade, preco, emb_qtd, emb_un, tbca_id, iid))
                except sqlite3.IntegrityError as exc:
                    raise ErroMobile("Já existe outro produto com esse nome.") from exc
            if estoque_inicial not in (None, ""):
                qtd = sv.num(estoque_inicial, "quantidade inicial em estoque")
                if qtd < 0:
                    raise ErroMobile("O estoque inicial não pode ser negativo.")
                admin = _admin(c)
                sv.gravar(c, "estoque", sv.hoje(), "almox|%d" % iid, {"qtd": qtd}, admin["id"], "admin")
            c.commit()
            return iid
    finally:
        c.close()


# ------------------------------------------------- mapeamento mobile <-> desktop
def dieta_para_desktop(txt):
    """'Pastosa' -> {'consistencia': 'Pastosa'}; 'Enteral' -> {'via': 'Enteral'}; o resto não tem campo no desktop."""
    k = (txt or "").strip().casefold()
    if k == "enteral":
        return {"via": "Enteral"}
    return {"consistencia": _CONSISTENCIAS[k]} if k in _CONSISTENCIAS else {}


def dieta_para_mobile(reg):
    if reg.get("via") == "Enteral":
        base = "Enteral"
    else:
        c = reg.get("consistencia") or ""
        base = "Geral" if c == "Livre" else c
    operacional = (reg.get("dados_copa") or {}).get("instrucao")
    if operacional:
        base = (base + " · " + str(operacional)).strip(" ·")
    return base[:60]


def diagnostico_para_mobile(reg):
    return ", ".join(sigla for campo, sigla in (("dm", "DM"), ("has", "HAS"), ("drc", "DRC")) if reg.get(campo))


def _t(v):
    return ("" if v is None else str(v)).strip()


def _n(v):
    try:
        return None if v in (None, "") else int(v)
    except (TypeError, ValueError):
        return None


def _mapear(row):
    """Linha do mapa do mobile -> campos equivalentes do registro do desktop."""
    suplementos = row.get("suplementos")
    if suplementos is None and row.get("suplementos_json"):
        try:
            suplementos = json.loads(row["suplementos_json"])
        except (TypeError, ValueError):
            suplementos = []
    m = {"nome_paciente": _t(row.get("nome")), "idade_anos": _n(row.get("idade_anos")), "idade_meses": _n(row.get("idade_meses")),
         "acompanhante": int(bool(row.get("acompanhante"))), "obs_sim": _t(row.get("pref_sim")),
         "obs_nao": _t(row.get("pref_nao")), "cor": _t(row.get("cor")),
         "via": _t(row.get("via")), "consistencia": _t(row.get("consistencia")),
         "dm": int(bool(row.get("dm"))), "has": int(bool(row.get("has"))),
         "laxativa": int(bool(row.get("laxativa"))), "constipante": int(bool(row.get("constipante"))),
         "drc": int(bool(row.get("drc"))), "suplementos": list(suplementos or [])}
    if not m["via"] and not m["consistencia"]:
        m.update(dieta_para_desktop(row.get("dieta")))
    return m


def _cmp(campo, v):
    """Valor normalizado, só para comparar sem confundir NULL e falso/vazio."""
    if campo in ("idade_meses", "acompanhante", "dm", "has", "laxativa", "constipante", "drc"):
        return int(bool(v)) if campo not in ("idade_meses",) else int(v or 0)
    if campo == "idade_anos":
        return _n(v)
    if campo == "suplementos":
        campos = ("id_suplemento", "nome", "modulo", "ml_oferta", "agua_ml", "refeicoes", "qtd_dia", "batido_fruta", "unidade")
        itens = []
        for s in (v or []):
            if not isinstance(s, dict):
                continue
            refeicoes = s.get("refeicoes")
            if refeicoes is None:
                try:
                    refeicoes = json.loads(s.get("refeicoes_json") or "[]")
                except (TypeError, ValueError):
                    refeicoes = []
            itens.append({k: (refeicoes if k == "refeicoes" else s.get(k)) for k in campos})
        return json.dumps(itens, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return _t(v).casefold()


def _vazio(campo, v):
    if campo == "suplementos":
        return not v
    return _cmp(campo, v) in (None, 0, "")


def _timestamp_maior(novo, atual):
    if not novo:
        return True
    if not atual:
        return True
    try:
        a = datetime.fromisoformat(str(novo).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(atual).replace("Z", "+00:00"))
        local = timezone(timedelta(hours=-3))
        if a.tzinfo is None: a = a.replace(tzinfo=local)
        if b.tzinfo is None: b = b.replace(tzinfo=local)
        return a > b
    except (TypeError, ValueError):
        return str(novo).replace("T", " ") > str(atual).replace("T", " ")


def _assinatura(row):
    base = [_mapear(row), _t(row.get("dieta")), _t(row.get("diagnostico"))]
    return hashlib.sha1(json.dumps(base, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _achar_leito(c, setor, codigo):
    r = c.execute("SELECT L.id_leito FROM Mapa_Leitos L JOIN Mapa_Setores S ON S.id_setor = L.id_setor "
                  "WHERE lower(S.nome)=lower(?) AND lower(L.codigo)=lower(?)", (setor, codigo)).fetchone()
    return r["id_leito"] if r else None


def _garantir_leito(c, setor, codigo):
    r = c.execute("SELECT id_setor FROM Mapa_Setores WHERE lower(nome)=lower(?)", (setor,)).fetchone()
    sid = r["id_setor"] if r else c.execute("INSERT INTO Mapa_Setores (nome) VALUES (?)", (setor,)).lastrowid
    if _achar_leito(c, setor, codigo) is None:
        ordem = c.execute("SELECT COALESCE(MAX(ordem),0)+1 FROM Mapa_Leitos WHERE id_setor=?", (sid,)).fetchone()[0]
        c.execute("INSERT INTO Mapa_Leitos (id_setor, codigo, ordem) VALUES (?,?,?)", (sid, codigo, ordem))
    return _achar_leito(c, setor, codigo)


# ----------------------------------------------------------- receber: mapa
def propostas_mapa(db, ex):
    """Compara o mapa que chegou do mobile com o do desktop e devolve o que o nutricionista precisa conferir.

    Tipos: 'novo' (leito sem registro no desktop), 'alterado' (mesmo paciente, dados novos), 'troca' (outro nome no leito:
    aplicar começa um registro limpo) e 'liberar' (mobile sem paciente). Valor vazio do mobile nunca apaga dado do desktop.
    Correções da copa que esperam autorização no mobile entram aqui também (campo id_correcao)."""
    garantir_tabelas(db)
    setor_de = {s["id"]: s["nome"] for s in ex["setores"]}
    leito_de = {l["id"]: (setor_de.get(l["id_setor"], "?"), l["codigo"]) for l in ex["leitos"]}
    origem = {(r["data"], r["id_leito"]): (r, None) for r in ex["mapa"]}
    for k in ex.get("correcoes_pendentes", []):  # a proposta da copa vale mais que a linha que o admin/nutrição gravou
        if k["tipo"] == "mapa":
            origem[(k["data"], int(k["chave"]))] = ({**k["valor_proposto"], "id_leito": int(k["chave"]), "data": k["data"]}, k["id"])
    out, extras = [], []
    with closing(mdb.conectar(db)) as c:
        for (data, lid), (row, id_corr) in origem.items():
            if lid not in leito_de:
                continue
            setor, codigo = leito_de[lid]
            mob = _mapear(row)
            extra = {"dieta": _t(row.get("dieta")), "diagnostico": _t(row.get("diagnostico"))}
            if id_corr is None and (extra["dieta"] or extra["diagnostico"]):
                extras.append((data, setor, codigo, extra["dieta"], extra["diagnostico"], _agora()))
            ass = _assinatura(row)
            if c.execute("SELECT 1 FROM Mobile_Visto WHERE data=? AND setor=? AND leito=? AND assinatura=?",
                         (data, setor, codigo, ass)).fetchone():
                continue
            id_leito = _achar_leito(c, setor, codigo)
            reg = mdb.obter_registro(db, data, id_leito) if id_leito else None
            # Estado sincronizado usa "última alteração" como autoridade. Uma cópia mobile
            # mais antiga não pode ressuscitar ou apagar um estado que o PC já atualizou.
            if reg and row.get("atualizado_em") and reg.get("atualizado_em") and not _timestamp_maior(row.get("atualizado_em"), reg.get("atualizado_em")):
                continue
            if reg is None:
                if not mob["nome_paciente"]:
                    continue
                tipo, padrao, campos = "novo", True, [k for k in mob if k == "acompanhante" or not _vazio(k, mob[k])]
            elif not mob["nome_paciente"]:
                tipo, padrao, campos = "liberar", False, ["nome_paciente"]
            else:
                campos = [k for k in mob if (k == "acompanhante" or not _vazio(k, mob[k])) and _cmp(k, mob[k]) != _cmp(k, reg.get(k))]
                if not campos:
                    continue
                if "nome_paciente" in campos:
                    tipo, padrao = "troca", False
                else:
                    tipo, padrao = "alterado", all(_vazio(k, reg.get(k)) for k in campos)
            out.append({"data": data, "chave": "%s|%s" % (setor, codigo), "setor": setor, "leito": codigo, "tipo": tipo,
                        "campos": campos, "mobile": mob, "extra": extra, "desktop": {k: reg.get(k) for k in mob} if reg else {},
                        "padrao": padrao, "assinatura": ass, "id_correcao": id_corr})
    if extras:
        with closing(mdb.conectar(db)) as c:
            c.executemany("INSERT OR REPLACE INTO Mobile_Extra (data, setor, leito, dieta, diagnostico, atualizado_em) VALUES (?,?,?,?,?,?)", extras)
            c.commit()
    return sorted(out, key=lambda p: (p["data"], p["setor"], p["leito"]))


def _montar_registro(p, reg, id_leito):
    if reg and p["tipo"] != "troca":
        novo = dict(reg)  # mesmo paciente: mantém antropometria, suplementos e vínculo com o cadastro
    else:
        novo = dict(_BASE_NOVO, suplementos=[])  # leito novo ou outro paciente: começa limpo
    for k, v in p["mobile"].items():  # campos vazios do mobile não apagam o que o desktop já tem
        if p["tipo"] in ("novo", "troca") or k == "acompanhante" or not _vazio(k, v):
            novo[k] = v
    novo["data"], novo["id_leito"] = p["data"], id_leito
    return novo


def _decidir_mobile(mobile_db, ids, acao):
    if not ids:
        return
    sv, c = _abrir_mobile(mobile_db)
    try:
        with sv.LOCK:
            adm = _admin(c)
            for i in ids:
                try:
                    sv.decidir(c, adm, int(i), acao)
                except sv.Erro:
                    pass  # já decidida no painel web
            c.commit()
    finally:
        c.close()


def _marcar_visto(db, p):
    with closing(mdb.conectar(db)) as c:
        c.execute("INSERT OR REPLACE INTO Mobile_Visto (data, setor, leito, assinatura) VALUES (?,?,?,?)",
                  (p["data"], p["setor"], p["leito"], p["assinatura"]))
        c.execute("INSERT OR REPLACE INTO Mobile_Extra (data, setor, leito, dieta, diagnostico, atualizado_em) VALUES (?,?,?,?,?,?)",
                  (p["data"], p["setor"], p["leito"], p["extra"]["dieta"], p["extra"]["diagnostico"], _agora()))
        c.commit()


def aplicar_mapa(db, propostas, mobile_db=None, criterio_idoso="lipschitz", lms=None):
    """Grava no desktop as propostas aprovadas. Se vieram de correção da copa, aprova a correção no mobile também."""
    garantir_tabelas(db)
    aplicados, erros, aprovar = 0, [], []
    for p in propostas:
        try:
            with closing(mdb.conectar(db)) as c:
                id_leito = _garantir_leito(c, p["setor"], p["leito"])
                c.commit()
            reg = mdb.obter_registro(db, p["data"], id_leito)
            if p["tipo"] == "liberar":
                if reg:
                    mdb.remover_registro(db, reg["id_registro"])
            else:
                mdb.salvar_registro(db, _montar_registro(p, reg, id_leito), criterio_idoso, lms)
            _marcar_visto(db, p)
            aplicados += 1
            if p.get("id_correcao"):
                aprovar.append(p["id_correcao"])
        except (ValueError, KeyError) as e:
            erros.append("%s %s: %s" % (p["setor"], p["leito"], e))
    if mobile_db:
        _decidir_mobile(mobile_db, aprovar, "aprovar")
    return {"aplicados": aplicados, "erros": erros}


def ignorar_mapa(db, propostas, mobile_db=None):
    """Leito vindo da copa: não propõe de novo enquanto o mobile não mudar. Correção pendente: é recusada no mobile."""
    garantir_tabelas(db)
    recusar = []
    for p in propostas:
        if p.get("id_correcao"):
            recusar.append(p["id_correcao"])
        else:
            _marcar_visto(db, p)
    if mobile_db:
        _decidir_mobile(mobile_db, recusar, "recusar")
    return len(propostas)


# ------------------------------------------------- receber: refeições e estoque
def importar_refeicoes(db, ex):
    garantir_tabelas(db)
    setor_de = {s["id"]: s["nome"] for s in ex["setores"]}
    with closing(mdb.conectar(db)) as c:
        for r in ex["refeicoes"]:
            c.execute("INSERT OR REPLACE INTO Mobile_Refeicoes (data, setor, refeicao, qtd, atualizado_em) VALUES (?,?,?,?,?)",
                      (r["data"], setor_de.get(r["id_setor"], "?"), r["refeicao"], r["qtd"], r.get("atualizado_em") or _agora()))
        c.commit()
    return len(ex["refeicoes"])


def importar_estoque(db, ex):
    garantir_tabelas(db)
    itens = {i["id"]: (i["nome"], i["unidade"]) for i in ex["itens"]}
    with closing(mdb.conectar(db)) as c:
        for r in ex["estoque"]:
            nome, un = itens.get(r["id_item"], ("?", ""))
            c.execute("INSERT OR REPLACE INTO Mobile_Estoque_Dia (data, estoque, item, unidade, qtd, atualizado_em) VALUES (?,?,?,?,?,?)",
                      (r["data"], r["estoque"], nome, un, r["qtd"], r.get("atualizado_em") or _agora()))
        cols_mov = {r[1] for r in c.execute("PRAGMA table_info(Mobile_Movimentos)")}
        for m in ex["movimentos"]:
            nome, un = itens.get(m["id_item"], ("?", ""))
            preco = m.get("preco_unitario_snapshot")
            custo = m.get("custo_snapshot")
            if custo is None and preco is not None:
                custo = float(m["qtd"]) * float(preco)
            c.execute("""INSERT INTO Mobile_Movimentos
                (data,id_mobile,hora,origem,destino,item,unidade,qtd,divergente,id_item_mobile,por_usuario,
                 valor_unitario_snapshot,custo_snapshot)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(data,id_mobile) DO UPDATE SET
                 hora=excluded.hora,origem=excluded.origem,destino=excluded.destino,item=excluded.item,
                 unidade=excluded.unidade,qtd=excluded.qtd,divergente=excluded.divergente,
                 id_item_mobile=excluded.id_item_mobile,por_usuario=excluded.por_usuario,
                 valor_unitario_snapshot=COALESCE(excluded.valor_unitario_snapshot,Mobile_Movimentos.valor_unitario_snapshot),
                 custo_snapshot=COALESCE(excluded.custo_snapshot,Mobile_Movimentos.custo_snapshot)""",
                (m["data"],m["id"],m["hora"],m["origem"],m["destino"],nome,un,m["qtd"],m["divergente"],
                 m["id_item"],m.get("por_usuario"),preco,custo))
        c.commit()
    return len(ex["estoque"]), len(ex["movimentos"])



def importar_movimentos_cozinha(db, mobile_db, inicio, fim):
    """Importa transferências do mobile por intervalo, preservando IDs, usuário e preço histórico.

    A chave (data, id_mobile) torna a operação idempotente. A função não altera o saldo do mobile.
    """
    from datetime import date
    try:
        inicio = date.fromisoformat(str(inicio)).isoformat()
        fim = date.fromisoformat(str(fim)).isoformat()
    except (TypeError, ValueError):
        raise ErroMobile("Informe as datas no formato AAAA-MM-DD.")
    if fim < inicio:
        raise ErroMobile("A data final deve ser igual ou posterior à data inicial.")
    sv, origem = _abrir_mobile(mobile_db)
    try:
        cols_mov = {r[1] for r in origem.execute("PRAGMA table_info(movimentos)")}
        cols_item = {r[1] for r in origem.execute("PRAGMA table_info(itens)")}
        if not {"id", "data", "hora", "origem", "destino", "id_item", "qtd"}.issubset(cols_mov):
            raise ErroMobile("O histórico de movimentações do mobile está incompleto.")
        preco_select = "i.preco_unitario" if "preco_unitario" in cols_item else "NULL"
        user_select = "m.por_usuario" if "por_usuario" in cols_mov else "NULL"
        price_select = "m.preco_unitario_snapshot" if "preco_unitario_snapshot" in cols_mov else "NULL"
        cost_select = "m.custo_snapshot" if "custo_snapshot" in cols_mov else "NULL"
        obs_select = "m.observacao" if "observacao" in cols_mov else "NULL"
        rows = origem.execute(f"""SELECT m.data,m.id,m.hora,m.origem,m.destino,m.id_item,m.qtd,m.divergente,
                    {user_select} AS por_usuario,COALESCE({price_select},NULL) AS preco_unitario_snapshot,
                    COALESCE({cost_select},NULL) AS custo_snapshot,{obs_select} AS observacao,i.nome AS item,i.unidade,
                    {preco_select} AS preco_atual
                FROM movimentos m LEFT JOIN itens i ON i.id=m.id_item
                WHERE m.data BETWEEN ? AND ? ORDER BY m.data,m.hora,m.id""", (inicio, fim)).fetchall()
        preparados = []
        for r in rows:
            preco = r["preco_unitario_snapshot"]
            custo = r["custo_snapshot"]
            # Só calcula com preço atual quando o registro histórico é anterior ao recurso de snapshot;
            # o custo resultante fica marcado como estimado pela ausência de valor histórico.
            if custo is None and preco is not None:
                custo = float(r["qtd"]) * float(preco)
            preparados.append((
                r["data"], r["id"], r["hora"], r["origem"], r["destino"], r["item"] or ("Item #%s" % r["id_item"]),
                r["unidade"] or "", r["qtd"], int(r["divergente"] or 0), r["id_item"], r["por_usuario"],
                preco, custo, r["observacao"]
            ))
    finally:
        origem.close()
    garantir_tabelas(db)
    with closing(mdb.conectar(db)) as destino:
        destino.executemany("""INSERT INTO Mobile_Movimentos
            (data,id_mobile,hora,origem,destino,item,unidade,qtd,divergente,id_item_mobile,por_usuario,
             valor_unitario_snapshot,custo_snapshot,observacao)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(data,id_mobile) DO UPDATE SET
             hora=excluded.hora,origem=excluded.origem,destino=excluded.destino,item=excluded.item,
             unidade=excluded.unidade,qtd=excluded.qtd,divergente=excluded.divergente,
             id_item_mobile=excluded.id_item_mobile,por_usuario=excluded.por_usuario,
             valor_unitario_snapshot=COALESCE(excluded.valor_unitario_snapshot,Mobile_Movimentos.valor_unitario_snapshot),
             custo_snapshot=COALESCE(excluded.custo_snapshot,Mobile_Movimentos.custo_snapshot),
             observacao=COALESCE(excluded.observacao,Mobile_Movimentos.observacao)""", preparados)
        destino.commit()
    return {"importados": len(preparados), "inicio": inicio, "fim": fim,
            "retiradas_cozinha": sum(1 for x in preparados if str(x[3]).lower()=="almox" and str(x[4]).lower()=="cozinha")}


def resumo(db, data_iso):
    garantir_tabelas(db)
    with closing(mdb.conectar(db)) as c:
        ref = [dict(r) for r in c.execute("SELECT setor, refeicao, qtd FROM Mobile_Refeicoes WHERE data=? ORDER BY setor, refeicao", (data_iso,))]
        est = [dict(r) for r in c.execute("SELECT estoque, COUNT(*) AS itens, MAX(atualizado_em) AS ultima FROM Mobile_Estoque_Dia "
                                          "WHERE data=? GROUP BY estoque", (data_iso,))]
        mov = c.execute("SELECT COUNT(*), COALESCE(SUM(divergente),0) FROM Mobile_Movimentos WHERE data=?", (data_iso,)).fetchone()
    return {"refeicoes": ref, "estoques": est, "movimentos": mov[0], "divergentes": mov[1]}


# ------------------------------------------------------------- enviar: mapa
def _linha_mobile(reg, vivo):
    """Registro do desktop -> linha do mapa do mobile. Dieta/diagnóstico que o desktop não tem não apagam o do mobile."""
    suplementos = []
    for s in reg.get("suplementos") or []:
        suplementos.append({
            "id_suplemento": s.get("id_suplemento"), "nome": s.get("nome"), "modulo": s.get("modulo"),
            "ml_oferta": s.get("ml_oferta"), "agua_ml": s.get("agua_ml"),
            "refeicoes": s.get("refeicoes") or [], "qtd_dia": s.get("qtd_dia"),
            "batido_fruta": bool(s.get("batido_fruta")), "unidade": s.get("unidade") or "ml"
        })
    return {"id_paciente": reg.get("id_paciente"), "nome": reg["nome_paciente"],
            "idade_anos": reg.get("idade_anos"), "idade_meses": reg.get("idade_meses"),
            "acompanhante": bool(reg.get("acompanhante")), "pref_sim": reg.get("obs_sim") or "", "pref_nao": reg.get("obs_nao") or "",
            "cor": reg.get("cor") or "", "via": reg.get("via") or "", "consistencia": reg.get("consistencia") or "",
            "dm": bool(reg.get("dm")), "has": bool(reg.get("has")), "laxativa": bool(reg.get("laxativa")),
            "constipante": bool(reg.get("constipante")), "drc": bool(reg.get("drc")),
            "suplementos": suplementos,
            "dieta": dieta_para_mobile(reg) or vivo.get("dieta", ""),
            "diagnostico": diagnostico_para_mobile(reg) or vivo.get("diagnostico", ""),
            "atualizado_em": reg.get("atualizado_em"),
            "alta_em": reg.get("alta_em")}


def _enviar_setor(db, sv, c, adm, nome, itens, data_iso, texto):
    codigos = [i["leito"]["codigo"] for i in itens]
    r = c.execute("SELECT id FROM setores WHERE nome=?", (nome,)).fetchone()
    sid = sv.criar_setor(c, {"id_setor": r["id"], "codigos": codigos} if r else {"nome": nome, "codigos": codigos})["id"]
    ids = {l["codigo"]: l["id"] for l in c.execute("SELECT id, codigo FROM leitos WHERE id_setor=?", (sid,))}
    vivo = {l["id_leito"]: l for l in sv.linhas_mapa(c, sid, data_iso)}  # o que a copa vê agora
    with closing(mdb.conectar(db)) as d:
        enviados = {(r["setor"], r["leito"]): r["com_paciente"] for r in d.execute("SELECT * FROM Mobile_Enviado")}
    linhas, marcas = [], []
    for it in itens:
        cod, reg = it["leito"]["codigo"], it["registro"]
        lid = ids[cod]
        if reg:
            linhas.append({"id_leito": lid, **_linha_mobile(reg, vivo.get(lid, {}))})
            marcas.append((cod, lid, 1))
        else:
            # Envio completo: até leitos vazios entram na fotografia. Sem timestamp, o servidor não
            # sobrescreve um estado que possa ter sido criado pela copa.
            ultimo = mdb.ultimo_registro_leito(db, it["leito"]["id_leito"], data_iso)
            linhas.append({"id_leito": lid, "nome": "", "ocupado": 0,
                           "atualizado_em": (ultimo or {}).get("atualizado_em"),
                           "alta_em": (ultimo or {}).get("alta_em")})
            marcas.append((cod, lid, 0))
    if not linhas:
        return {"setor": nome, "leitos": 0}
    s = {"id": sid, "nome": nome}
    sync = sv.post_mapa(c, adm, s, data_iso, linhas, completo=True, origem_desktop=True)
    n = sync.get("ok", 0)
    if n:
        mud = [{"leito": cod, "tipo": "alterado" if com else "liberado"} for cod, _, com in marcas]
        c.execute("INSERT INTO avisos(criado_em,por_usuario,tipo,id_setor,titulo,texto,leitos) VALUES(?,?,?,?,?,?,?)",
                  (sv.agora(), adm["id"], "mapa", sid,
                   "Mapa de %s/%s sincronizado" % (data_iso[8:10], data_iso[5:7]),
                   str(texto or "").strip()[:300], json.dumps(mud, ensure_ascii=False)))
    depois = {l["id_leito"]: l for l in sv.linhas_mapa(c, sid, data_iso)}
    with closing(mdb.conectar(db)) as d:  # o que acabou de ser enviado não volta como "novidade do mobile"
        for cod, lid, com in marcas:
            d.execute("INSERT OR REPLACE INTO Mobile_Visto (data, setor, leito, assinatura) VALUES (?,?,?,?)", (data_iso, nome, cod, _assinatura(depois[lid])))
            d.execute("INSERT OR REPLACE INTO Mobile_Enviado (setor, leito, com_paciente, data) VALUES (?,?,?,?)", (nome, cod, com, data_iso))
        d.commit()
    return {"setor": nome, "leitos": n}


def sincronizar_catalogo_suplementos(db, mobile_db):
    """Atualiza o catálogo mobile com os suplementos ativos cadastrados no desktop."""
    sv = _servidor()
    with sv.LOCK:
        with closing(sv.conectar(mobile_db)) as c:
            c.executescript(sv.ESQUEMA)
            sv.migrar(c)
            c.execute("DELETE FROM suplementos_catalogo")
            itens = mdb.listar_suplementos(db, apenas_ativos=True)
            for s in itens:
                c.execute("""INSERT INTO suplementos_catalogo
                    (id_suplemento,nome,modulo,emb_qtd,emb_un,kcal_100,ptn_100,lip_100,carb_100,sod_100,ativo)
                    VALUES (?,?,?,?,?,?,?,?,?,?,1)""",
                    (s["id_suplemento"], s["nome"], s.get("modulo"), s.get("emb_qtd"), s.get("emb_un"),
                     s.get("kcal_100"), s.get("ptn_100"), s.get("lip_100"), s.get("carb_100"), s.get("sod_100")))
            c.commit()
    return len(itens)


def enviar_mapa(db, mobile_db, data_iso, id_setor=None, texto=None):
    """Envia o mapa do dia do desktop para o mobile e publica para a copa. Devolve [{'setor', 'leitos'}] com os leitos alterados."""
    garantir_tabelas(db)
    sincronizar_catalogo_suplementos(db, mobile_db)
    sv, c = _abrir_mobile(mobile_db)
    try:
        with sv.LOCK:
            adm = _admin(c)
            grupos = {}
            for item in mdb.mapa_do_dia(db, data_iso, id_setor):
                grupos.setdefault(item["leito"]["setor"], []).append(item)
            res = [_enviar_setor(db, sv, c, adm, nome, itens, data_iso, texto) for nome, itens in grupos.items()]
            c.commit()
        return res
    except sv.Erro as e:
        c.rollback()
        raise ErroMobile(e.msg) from e
    finally:
        c.close()


def sincronizar_automaticamente(db, mobile_db, data_iso):
    """Troca dados operacionais com o servidor local sem aprovar alterações clínicas automaticamente.

    Desktop -> mobile: publica o mapa do dia de todos os setores e atualiza o catálogo.
    Mobile -> desktop: importa refeições, contagens e movimentos idempotentes; devolve propostas
    de mapa para revisão humana, sem aplicá-las ao prontuário.
    """
    if not os.path.isfile(mobile_db):
        raise ErroMobile("O servidor local ainda não criou o banco mobile.")
    enviados = enviar_mapa(db, mobile_db, data_iso)
    exportado = ler_mobile(mobile_db, data_iso)
    propostas = propostas_mapa(db, exportado)
    refeicoes = importar_refeicoes(db, exportado)
    estoque, movimentos = importar_estoque(db, exportado)
    return {
        "leitos_enviados": sum(int(x.get("leitos") or 0) for x in enviados),
        "propostas_mapa": len(propostas),
        "outras_correcoes": len([x for x in exportado.get("correcoes_pendentes", []) if x.get("tipo") != "mapa"]),
        "revisoes_pendentes": len(propostas) + len([x for x in exportado.get("correcoes_pendentes", []) if x.get("tipo") != "mapa"]),
        "refeicoes_importadas": refeicoes,
        "itens_estoque_importados": estoque,
        "movimentos_importados": movimentos,
    }
