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
from contextlib import closing
from datetime import datetime

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
    unidade TEXT, qtd REAL, divergente INTEGER, PRIMARY KEY (data, id_mobile));
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
    with closing(mdb.conectar(db)) as c:
        c.executescript(_SCHEMA)
        c.commit()


def caminho_mobile_db(db, base_dir):
    padrao = os.path.join(base_dir, "mobile", "dados", "mobile.db")
    return mdb.obter_config(db, "mobile_db", padrao) or padrao


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
    """Lê itens, metadados de embalagem e saldo atual do Almoxarifado mobile.

    Retorna o mesmo contrato de linhas usado pela API de estoque, sem escrever
    no banco mobile ou alterar quantidades. Campos comerciais ficam ausentes
    (None) em bancos legados até que o administrador os cadastre.
    """
    sv, c = _abrir_mobile(mobile_db)
    try:
        if not hasattr(sv, "linhas_estoque"):
            raise ErroMobile("A versão mobile não disponibiliza a leitura do saldo do Almoxarifado. Atualize o módulo mobile.")
        linhas = sv.linhas_estoque(c, "almox", sv.hoje())
        # O mobile exibe saldo zero quando nunca houve lançamento; para a ficha isso
        # é dado desconhecido, diferente de um zero explicitamente registrado.
        for linha in linhas:
            if linha.get("data_base") is None:
                linha["qtd"] = None
        return linhas
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
        return "Enteral"
    c = reg.get("consistencia") or ""
    return "Geral" if c == "Livre" else c


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
    m = {"nome_paciente": _t(row.get("nome")), "idade_anos": _n(row.get("idade_anos")), "idade_meses": _n(row.get("idade_meses")),
         "acompanhante": int(bool(row.get("acompanhante"))), "obs_sim": _t(row.get("pref_sim")), "obs_nao": _t(row.get("pref_nao"))}
    m.update(dieta_para_desktop(row.get("dieta")))
    return m


def _cmp(campo, v):
    """Valor normalizado, só para comparar."""
    if campo in ("idade_meses", "acompanhante"):
        return int(v or 0)
    if campo == "idade_anos":
        return _n(v)
    return _t(v).casefold()


def _vazio(campo, v):
    return _cmp(campo, v) in (None, 0, "")


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
        for m in ex["movimentos"]:
            nome, un = itens.get(m["id_item"], ("?", ""))
            c.execute("INSERT OR REPLACE INTO Mobile_Movimentos (data, id_mobile, hora, origem, destino, item, unidade, qtd, divergente) "
                      "VALUES (?,?,?,?,?,?,?,?,?)", (m["data"], m["id"], m["hora"], m["origem"], m["destino"], nome, un, m["qtd"], m["divergente"]))
        c.commit()
    return len(ex["estoque"]), len(ex["movimentos"])


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
    return {"nome": reg["nome_paciente"], "idade_anos": reg.get("idade_anos"), "idade_meses": reg.get("idade_meses"),
            "acompanhante": bool(reg.get("acompanhante")), "pref_sim": reg.get("obs_sim") or "", "pref_nao": reg.get("obs_nao") or "",
            "dieta": dieta_para_mobile(reg) or vivo.get("dieta", ""),
            "diagnostico": diagnostico_para_mobile(reg) or vivo.get("diagnostico", "")}


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
        elif enviados.get((nome, cod)):  # foi o desktop que pôs o paciente aí e agora o leito está vazio: libera na copa
            linhas.append({"id_leito": lid})
            marcas.append((cod, lid, 0))
        # leito vazio no desktop e nunca preenchido por ele: pode ter dado novo da copa; não mexe
    if not linhas:
        return {"setor": nome, "leitos": 0}
    s = {"id": sid, "nome": nome}
    sv.post_mapa(c, adm, s, data_iso, linhas)
    try:
        n = sv.publicar(c, adm, s, data_iso, texto)["leitos"]
    except sv.Erro as e:
        if "Não há alterações" not in e.msg:
            raise
        n = 0
    depois = {l["id_leito"]: l for l in sv.linhas_mapa(c, sid, data_iso)}
    with closing(mdb.conectar(db)) as d:  # o que acabou de ser enviado não volta como "novidade do mobile"
        for cod, lid, com in marcas:
            d.execute("INSERT OR REPLACE INTO Mobile_Visto (data, setor, leito, assinatura) VALUES (?,?,?,?)", (data_iso, nome, cod, _assinatura(depois[lid])))
            d.execute("INSERT OR REPLACE INTO Mobile_Enviado (setor, leito, com_paciente, data) VALUES (?,?,?,?)", (nome, cod, com, data_iso))
        d.commit()
    return {"setor": nome, "leitos": n}


def enviar_mapa(db, mobile_db, data_iso, id_setor=None, texto=None):
    """Envia o mapa do dia do desktop para o mobile e publica para a copa. Devolve [{'setor', 'leitos'}] com os leitos alterados."""
    garantir_tabelas(db)
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
