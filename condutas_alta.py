# -*- coding: utf-8 -*-
"""Condutas de alta: orientações nutricionais para o paciente levar para casa.

As condutas são SUGERIDAS a partir das doenças e da via de dieta relatadas no Mapa Nutricional e só entram na folha do
paciente depois que a nutricionista as CONFIRMA (ou as corrige) uma a uma.

Sem dependência de interface gráfica nem de fpdf (tela em condutas_alta_ui.py, PDF em condutas_alta_export.py).

Regras de segurança (CLAUDE.md e AGENTS.md):
  * o catálogo só sugere; nada vai para a folha do paciente sem confirmação individual;
  * nenhuma dose, volume ou valor é inventado: o que depende da prescrição fica em branco ("____") no texto;
  * a decisão grava uma CÓPIA do texto, da lista de conferência e das referências (o catálogo pode mudar depois);
  * documento entregue é imutável (gatilhos no banco, migração 2); corrigir é criar uma nova versão.

Catálogo: arquivos JSON da pasta `condutas_alta/` (um por grupo de doenças). Para conferir: `python condutas_alta.py`.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import mapa_db as mdb

PASTA_CATALOGO = "condutas_alta"
DECISOES = ("confirmada", "nao_se_aplica")
CFG_NUTRICIONISTA = "condutas_nutricionista"
CFG_CRN = "condutas_crn"
_RE_CODIGO = re.compile(r"^[A-Z]{2,5}-\d{2,3}$")
_RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RE_LACUNA = re.compile(r"_{3,}")
_ROTULOS_CARAC = {"dm": "Diabetes mellitus", "has": "Hipertensão arterial", "drc": "Doença renal"}


class ErroCondutasAlta(Exception):
    """Erro com mensagem pronta para mostrar à nutricionista."""


class ErroCatalogo(ErroCondutasAlta):
    def __init__(self, problemas):
        self.problemas = list(problemas)
        super().__init__("Catálogo de condutas inválido:\n- " + "\n- ".join(self.problemas))


# ------------------------------------------------------------------------------------------------ catálogo
@dataclass(frozen=True)
class Conduta:
    codigo: str
    grupo: str
    grupo_titulo: str
    titulo: str
    titulo_paciente: str
    gatilhos_qualquer: tuple
    gatilhos_todas: tuple
    profissional: str
    conferir: tuple
    paciente: str
    fontes: tuple          # referências ABNT completas, já resolvidas a partir das chaves do grupo
    versao: str
    revisado_em: str

    @property
    def automatica(self):
        """Só é sugerida pelo Mapa se tiver gatilho; sem gatilho entra apenas quando a nutricionista a adiciona."""
        return bool(self.gatilhos_qualquer or self.gatilhos_todas)


@dataclass
class Catalogo:
    condutas: dict = field(default_factory=dict)     # codigo -> Conduta, na ordem dos arquivos
    grupos: dict = field(default_factory=dict)       # grupo -> {"titulo", "versao", "revisado_em"}

    def obter(self, codigo):
        return self.condutas.get(codigo)

    def do_grupo(self, grupo):
        return [c for c in self.condutas.values() if c.grupo == grupo]


def tokens_validos():
    """Tokens aceitos em `gatilhos`: via:<via>, campo de CARACTERISTICAS (dm, has, drc...) e cond:<código>."""
    return ({f"via:{v}" for v in mdb.VIAS} | {c for c, _s, _n in mdb.CARACTERISTICAS}
            | {f"cond:{c}" for c, _n in mdb.CONDICOES})


def pasta_catalogo(base_dir=None):
    if base_dir:
        return Path(base_dir) / PASTA_CATALOGO
    base = getattr(sys, "_MEIPASS", None) if getattr(sys, "frozen", False) else None
    return Path(base or os.path.dirname(os.path.abspath(__file__))) / PASTA_CATALOGO


def _como_texto(valor):
    if isinstance(valor, (list, tuple)):
        return "\n".join(str(v).rstrip() for v in valor)
    return "" if valor is None else str(valor)


def _converter_grupo(dados, arquivo):
    """(meta | None, [Conduta], [problemas])."""
    problemas = []
    p = lambda msg: problemas.append(f"{arquivo}: {msg}")
    if not isinstance(dados, dict):
        return None, [], [f"{arquivo}: o arquivo deve conter um objeto JSON"]
    for chave in ("grupo", "titulo", "versao", "revisado_em"):
        if not isinstance(dados.get(chave), str) or not dados[chave].strip():
            p(f"campo obrigatório ausente: {chave}")
    if isinstance(dados.get("revisado_em"), str) and not _RE_DATA.match(dados["revisado_em"]):
        p("revisado_em deve ser AAAA-MM-DD")
    refs = dados.get("referencias")
    if not isinstance(refs, dict) or not refs:
        p("referencias deve ser um objeto {chave: referência ABNT}")
        refs = {}
    for chave, ref in refs.items():
        if not isinstance(ref, str) or "Disponível em:" not in ref or "Acesso em:" not in ref:
            p(f"referência '{chave}' deve ter link ('Disponível em:') e data de acesso ('Acesso em:')")
    brutas = dados.get("condutas")
    if not isinstance(brutas, list) or not brutas:
        p("condutas deve ser uma lista não vazia")
        brutas = []
    validos = tokens_validos()
    meta = {"grupo": str(dados.get("grupo", "")), "titulo": str(dados.get("titulo", "")),
            "versao": str(dados.get("versao", "")), "revisado_em": str(dados.get("revisado_em", ""))}
    lista, vistos = [], set()
    for i, b in enumerate(brutas, start=1):
        if not isinstance(b, dict):
            p(f"conduta #{i} deve ser um objeto")
            continue
        cod = b.get("codigo")
        rotulo = cod if isinstance(cod, str) else f"#{i}"
        if not isinstance(cod, str) or not _RE_CODIGO.match(cod):
            p(f"conduta {rotulo}: codigo deve seguir o padrão AAA-01")
            continue
        if cod in vistos:
            p(f"conduta {cod}: codigo repetido no arquivo")
        vistos.add(cod)
        titulo = str(b.get("titulo") or "").strip()
        prof = _como_texto(b.get("profissional")).strip()
        pac = _como_texto(b.get("paciente")).strip()
        for nome, valor in (("titulo", titulo), ("profissional", prof), ("paciente", pac)):
            if not valor:
                p(f"conduta {cod}: campo obrigatório vazio: {nome}")
        conferir = b.get("conferir", [])
        if not isinstance(conferir, list) or any(not isinstance(x, str) or not x.strip() for x in conferir):
            p(f"conduta {cod}: conferir deve ser uma lista de textos")
            conferir = []
        chaves = b.get("fontes")
        if not isinstance(chaves, list) or not chaves:
            p(f"conduta {cod}: informe ao menos uma fonte (nunca publique conduta sem referência)")
            chaves = []
        fontes = []
        for k in chaves:
            if k not in refs:
                p(f"conduta {cod}: fonte '{k}' não existe em referencias")
            else:
                fontes.append(refs[k])
        gat = b.get("gatilhos") or {}
        if not isinstance(gat, dict) or set(gat) - {"qualquer", "todas"}:
            p(f"conduta {cod}: gatilhos aceita apenas 'qualquer' e 'todas'")
            gat = {}
        qualquer, todas = gat.get("qualquer") or [], gat.get("todas") or []
        for t in list(qualquer) + list(todas):
            if t not in validos:
                p(f"conduta {cod}: gatilho desconhecido '{t}'")
        lista.append(Conduta(
            codigo=cod, grupo=meta["grupo"], grupo_titulo=meta["titulo"], titulo=titulo,
            titulo_paciente=str(b.get("titulo_paciente") or titulo).strip(),
            gatilhos_qualquer=tuple(qualquer), gatilhos_todas=tuple(todas), profissional=prof,
            conferir=tuple(x.strip() for x in conferir), paciente=pac, fontes=tuple(fontes),
            versao=meta["versao"], revisado_em=meta["revisado_em"]))
    return meta, lista, problemas


def carregar_catalogo(pasta=None):
    """Lê e valida todos os .json da pasta. Lança ErroCatalogo listando TODOS os problemas de uma vez."""
    pasta = Path(pasta) if pasta else pasta_catalogo()
    arquivos = sorted(pasta.glob("*.json")) if pasta.is_dir() else []
    if not arquivos:
        raise ErroCatalogo([f"nenhum arquivo .json encontrado em {pasta}"])
    leituras, problemas = [], []
    for arq in arquivos:
        try:
            dados = json.loads(arq.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as erro:
            problemas.append(f"{arq.name}: não foi possível ler ({erro})")
            continue
        ordem = dados.get("ordem") if isinstance(dados, dict) else None
        leituras.append((ordem if isinstance(ordem, int) else 100, arq.name, dados))
    cat = Catalogo()
    for _ordem, nome, dados in sorted(leituras, key=lambda x: (x[0], x[1])):
        meta, lista, probs = _converter_grupo(dados, nome)
        problemas += probs
        if meta:
            cat.grupos[meta["grupo"]] = {k: meta[k] for k in ("titulo", "versao", "revisado_em")}
        for c in lista:
            if c.codigo in cat.condutas:
                problemas.append(f"{nome}: codigo {c.codigo} já existe em outro arquivo")
            cat.condutas[c.codigo] = c
    if problemas:
        raise ErroCatalogo(problemas)
    return cat


# ------------------------------------------------------------------------------- regras pelo Mapa
def tokens_do_registro(reg):
    """Conjunto de tokens do registro do Mapa (ex.: {'via:Enteral', 'dm', 'drc', 'cond:tb'})."""
    t = set()
    if not reg:
        return t
    if reg.get("via"):
        t.add(f"via:{reg['via']}")
    for campo, _sigla, _nome in mdb.CARACTERISTICAS:
        if reg.get(campo):
            t.add(campo)
    for cod in mdb.codigos_condicoes(reg.get("condicoes")):
        t.add(f"cond:{cod}")
    return t


def rotulos_do_registro(reg):
    """Doenças e condições relatadas, em palavras (para cabeçalhos): ['Via enteral', 'Doença renal', ...]."""
    if not reg:
        return []
    r = []
    if reg.get("via") == "Enteral":
        r.append("Via enteral")
    r += [nome for campo, nome in _ROTULOS_CARAC.items() if reg.get(campo)]
    return r + mdb.nomes_condicoes(reg.get("condicoes"))


def condutas_aplicaveis(catalogo, tokens):
    """Condutas sugeridas para o conjunto de tokens: (algum de `qualquer`, se houver) E (todos de `todas`)."""
    tokens = set(tokens)
    saida = []
    for c in catalogo.condutas.values():
        if not c.automatica:
            continue
        if c.gatilhos_qualquer and not (set(c.gatilhos_qualquer) & tokens):
            continue
        if not set(c.gatilhos_todas) <= tokens:
            continue
        saida.append(c)
    return saida


def registro_mais_recente(db_path, id_paciente):
    """Registro mais recente do paciente no Mapa (é ele que diz as doenças atuais) ou None."""
    if not id_paciente:
        return None
    try:
        hist = mdb.historico_paciente(db_path, id_paciente=id_paciente)
    except sqlite3.OperationalError:
        return None
    return hist[0] if hist else None


# --------------------------------------------------------------------------------------- texto
def normalizar_texto(txt):
    """Quebras de linha unificadas, sem espaços no fim das linhas e sem linhas em branco repetidas."""
    linhas = [ln.rstrip() for ln in (txt or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    saida = []
    for ln in linhas:
        if ln == "" and (not saida or saida[-1] == ""):
            continue
        saida.append(ln)
    while saida and saida[-1] == "":
        saida.pop()
    return "\n".join(saida)


def linhas_do_texto(txt):
    """[(tipo, texto)]: tipo 'item' para linhas que começam com '- ', '* ' ou '• '; senão 'texto'."""
    saida = []
    for ln in normalizar_texto(txt).split("\n"):
        if not ln.strip():
            continue
        m = re.match(r"^\s*[-*•]\s+(.*)$", ln)
        saida.append(("item", m.group(1).strip()) if m else ("texto", ln.strip()))
    return saida


def contar_lacunas(txt):
    """Quantos campos em branco ('____') ainda há no texto (a nutricionista preenche ou escreve à mão)."""
    return len(_RE_LACUNA.findall(txt or ""))


# ---------------------------------------------------------------------------------------- banco
def _agora(agora=None):
    return (agora or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def _conn(db_path):
    conn = mdb.conectar(db_path)
    try:
        yield conn
    except sqlite3.IntegrityError as erro:               # inclui as mensagens dos gatilhos de imutabilidade
        conn.rollback()
        raise ErroCondutasAlta(str(erro)) from erro
    except sqlite3.OperationalError as erro:
        conn.rollback()
        if "no such table" in str(erro) and "Condutas_Alta" in str(erro):
            raise ErroCondutasAlta("As tabelas de condutas de alta não existem neste banco (migração 2 não aplicada). "
                                   "Feche e abra o programa; se persistir, avise o responsável técnico.") from erro
        raise
    finally:
        conn.close()


def documento_atual(db_path, id_paciente):
    """Documento mais recente do paciente (rascunho ou entregue) ou None."""
    with _conn(db_path) as c:
        r = c.execute("SELECT * FROM Condutas_Alta_Docs WHERE id_paciente=? ORDER BY id_doc DESC LIMIT 1",
                      (id_paciente,)).fetchone()
        return dict(r) if r else None


def listar_documentos(db_path, id_paciente):
    with _conn(db_path) as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM Condutas_Alta_Docs WHERE id_paciente=? ORDER BY id_doc DESC", (id_paciente,))]


def listar_itens(db_path, id_doc):
    with _conn(db_path) as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM Condutas_Alta_Itens WHERE id_doc=? ORDER BY id_item", (id_doc,))]


def _padrao_cabecalho(db_path):
    try:
        return (mdb.obter_config(db_path, CFG_NUTRICIONISTA, "") or "", mdb.obter_config(db_path, CFG_CRN, "") or "")
    except sqlite3.OperationalError:
        return "", ""


def abrir_rascunho(db_path, id_paciente, agora=None):
    """Devolve o rascunho aberto do paciente. Sem documento: cria um. Se o último estava ENTREGUE: cria uma NOVA VERSÃO
    (copia decisões e cabeçalho; o documento entregue não é alterado)."""
    ultimo = documento_atual(db_path, id_paciente)
    if ultimo and ultimo["status"] == "rascunho":
        return ultimo
    quando = _agora(agora)
    with _conn(db_path) as c:
        if ultimo:
            cur = c.execute(
                "INSERT INTO Condutas_Alta_Docs (id_paciente, criado_em, atualizado_em, nutricionista, crn, recado, "
                "substitui_id_doc) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (id_paciente, quando, quando, ultimo["nutricionista"], ultimo["crn"], ultimo["recado"],
                 ultimo["id_doc"]))
            novo = cur.lastrowid
            c.execute(
                "INSERT INTO Condutas_Alta_Itens (id_doc, codigo, versao_catalogo, decisao, origem, titulo, "
                "titulo_paciente, texto_paciente, texto_profissional, conferir, referencias, editado, justificativa, "
                "decidido_em) SELECT ?, codigo, versao_catalogo, decisao, origem, titulo, titulo_paciente, "
                "texto_paciente, texto_profissional, conferir, referencias, editado, justificativa, decidido_em "
                "FROM Condutas_Alta_Itens WHERE id_doc=? ORDER BY id_item", (novo, ultimo["id_doc"]))
        else:
            nome, crn = _padrao_cabecalho(db_path)
            cur = c.execute(
                "INSERT INTO Condutas_Alta_Docs (id_paciente, criado_em, atualizado_em, nutricionista, crn) "
                "VALUES (?, ?, ?, ?, ?)", (id_paciente, quando, quando, nome, crn))
            novo = cur.lastrowid
        c.commit()
        return dict(c.execute("SELECT * FROM Condutas_Alta_Docs WHERE id_doc=?", (novo,)).fetchone())


def decidir(db_path, id_doc, conduta, decisao, *, texto_paciente=None, texto_profissional=None, justificativa=None,
            origem="regra", agora=None):
    """Grava (ou substitui) a decisão da nutricionista sobre uma conduta, com cópia dos textos."""
    if decisao not in DECISOES:
        raise ErroCondutasAlta("Decisão inválida.")
    if origem not in ("regra", "manual"):
        raise ErroCondutasAlta("Origem inválida.")
    justificativa = (justificativa or "").strip()
    if decisao == "confirmada":
        texto_paciente = normalizar_texto(conduta.paciente if texto_paciente is None else texto_paciente)
        if not texto_paciente:
            raise ErroCondutasAlta(f"O texto para o paciente da conduta {conduta.codigo} não pode ficar vazio.")
        editado = int(texto_paciente != normalizar_texto(conduta.paciente))
    else:
        if len(justificativa) < 3:
            raise ErroCondutasAlta("Informe o motivo de a conduta não se aplicar a este paciente.")
        texto_paciente, editado = None, 0
    texto_profissional = normalizar_texto(conduta.profissional if texto_profissional is None else texto_profissional)
    quando = _agora(agora)
    with _conn(db_path) as c:
        c.execute(
            "INSERT INTO Condutas_Alta_Itens (id_doc, codigo, versao_catalogo, decisao, origem, titulo, titulo_paciente, "
            "texto_paciente, texto_profissional, conferir, referencias, editado, justificativa, decidido_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id_doc, codigo) DO UPDATE SET versao_catalogo=excluded.versao_catalogo, "
            "decisao=excluded.decisao, origem=excluded.origem, titulo=excluded.titulo, "
            "titulo_paciente=excluded.titulo_paciente, texto_paciente=excluded.texto_paciente, "
            "texto_profissional=excluded.texto_profissional, conferir=excluded.conferir, "
            "referencias=excluded.referencias, editado=excluded.editado, justificativa=excluded.justificativa, "
            "decidido_em=excluded.decidido_em",
            (id_doc, conduta.codigo, conduta.versao, decisao, origem, conduta.titulo, conduta.titulo_paciente,
             texto_paciente, texto_profissional, "\n".join(conduta.conferir), "\n".join(conduta.fontes), editado,
             justificativa or None, quando))
        c.execute("UPDATE Condutas_Alta_Docs SET atualizado_em=? WHERE id_doc=?", (quando, id_doc))
        c.commit()


def corrigir_texto_paciente(db_path, id_doc, codigo, texto_paciente, conduta=None, agora=None):
    """Corrige SÓ o texto do paciente de uma conduta já confirmada, no rascunho.

    O resto do instantâneo (texto técnico, itens a conferir, referências e versão do catálogo) fica como estava na
    confirmação: assim, mesmo que o catálogo tenha mudado depois, a folha nunca mistura texto antigo com texto novo.
    Em documento entregue o banco recusa (gatilhos de imutabilidade)."""
    texto = normalizar_texto(texto_paciente)
    if not texto:
        raise ErroCondutasAlta(f"O texto para o paciente da conduta {codigo} não pode ficar vazio.")
    quando = _agora(agora)
    with _conn(db_path) as c:
        item = c.execute("SELECT decisao, versao_catalogo, texto_paciente, editado FROM Condutas_Alta_Itens "
                         "WHERE id_doc=? AND codigo=?", (id_doc, codigo)).fetchone()
        if not item or item["decisao"] != "confirmada":
            raise ErroCondutasAlta("Só uma conduta já confirmada pode ter o texto corrigido. Confirme-a primeiro.")
        if conduta is not None and item["versao_catalogo"] == conduta.versao:
            editado = int(texto != normalizar_texto(conduta.paciente))
        else:   # o catálogo mudou depois da confirmação: não dá para comparar com o texto original; mantém a marca
            editado = int(bool(item["editado"]) or texto != normalizar_texto(item["texto_paciente"] or ""))
        c.execute("UPDATE Condutas_Alta_Itens SET texto_paciente=?, editado=?, decidido_em=? "
                  "WHERE id_doc=? AND codigo=?", (texto, editado, quando, id_doc, codigo))
        c.execute("UPDATE Condutas_Alta_Docs SET atualizado_em=? WHERE id_doc=?", (quando, id_doc))
        c.commit()


def desfazer_decisao(db_path, id_doc, codigo, agora=None):
    """Volta a conduta para 'pendente' (apaga a decisão do rascunho). Em documento entregue o banco recusa."""
    with _conn(db_path) as c:
        c.execute("DELETE FROM Condutas_Alta_Itens WHERE id_doc=? AND codigo=?", (id_doc, codigo))
        c.execute("UPDATE Condutas_Alta_Docs SET atualizado_em=? WHERE id_doc=?", (_agora(agora), id_doc))
        c.commit()


def salvar_cabecalho(db_path, id_doc, nutricionista, crn, recado, agora=None):
    """Nome e CRN de quem assina a folha e o recado livre ao paciente. Guarda nome/CRN como padrão para o próximo."""
    nutricionista, crn = (nutricionista or "").strip(), (crn or "").strip()
    with _conn(db_path) as c:
        c.execute("UPDATE Condutas_Alta_Docs SET nutricionista=?, crn=?, recado=?, atualizado_em=? WHERE id_doc=?",
                  (nutricionista, crn, normalizar_texto(recado), _agora(agora), id_doc))
        c.commit()
    try:
        if nutricionista:
            mdb.salvar_config(db_path, CFG_NUTRICIONISTA, nutricionista)
        mdb.salvar_config(db_path, CFG_CRN, crn)
    except sqlite3.OperationalError:
        pass


def marcar_entregue(db_path, id_doc, agora=None):
    """Fecha o documento: depois disso ele não pode mais ser alterado (só nova versão). Exige nutricionista e pelo
    menos uma conduta confirmada."""
    with _conn(db_path) as c:
        doc = c.execute("SELECT * FROM Condutas_Alta_Docs WHERE id_doc=?", (id_doc,)).fetchone()
        if not doc:
            raise ErroCondutasAlta("Documento não encontrado.")
        if doc["status"] == "entregue":
            raise ErroCondutasAlta("Este documento já foi marcado como entregue.")
        if not (doc["nutricionista"] or "").strip():
            raise ErroCondutasAlta("Informe o nome da nutricionista responsável antes de marcar como entregue.")
        n = c.execute("SELECT COUNT(*) FROM Condutas_Alta_Itens WHERE id_doc=? AND decisao='confirmada'",
                      (id_doc,)).fetchone()[0]
        if not n:
            raise ErroCondutasAlta("Confirme pelo menos uma conduta antes de marcar como entregue.")
        quando = _agora(agora)
        c.execute("UPDATE Condutas_Alta_Docs SET status='entregue', entregue_em=?, atualizado_em=? WHERE id_doc=?",
                  (quando, quando, id_doc))
        c.commit()


# --------------------------------------------------------------------- resumo (coluna do Mapa)
def resumo_por_registro(db_path, registros, catalogo=None):
    """{id_paciente: {'aplicaveis', 'pendentes', 'estado', 'texto'}} para as linhas do mapa.

    estado: 'sem' (nada sugerido nem decidido), 'pendente' (há sugestão sem decisão), 'decidido' (tudo o que foi
    sugerido já tem decisão, confirmada ou "não se aplica") ou 'entregue'. As doenças vêm do registro dado (o do dia
    mostrado no Mapa); a janela das condutas usa o registro mais recente do paciente.
    """
    catalogo = catalogo or carregar_catalogo()
    regs = [r for r in registros if r and r.get("id_paciente")]
    if not regs:
        return {}
    ids = sorted({r["id_paciente"] for r in regs})
    marcas = ",".join("?" * len(ids))
    with _conn(db_path) as c:
        docs = {d["id_paciente"]: dict(d) for d in c.execute(
            "SELECT d.* FROM Condutas_Alta_Docs d JOIN (SELECT MAX(id_doc) AS m FROM Condutas_Alta_Docs "
            f"WHERE id_paciente IN ({marcas}) GROUP BY id_paciente) x ON x.m = d.id_doc", ids)}
        decididas = {}
        if docs:
            ids_doc = [d["id_doc"] for d in docs.values()]
            for r in c.execute("SELECT id_doc, codigo FROM Condutas_Alta_Itens WHERE id_doc IN (%s)"
                               % ",".join("?" * len(ids_doc)), ids_doc):
                decididas.setdefault(r["id_doc"], set()).add(r["codigo"])
    saida = {}
    for r in regs:
        aplic = [x.codigo for x in condutas_aplicaveis(catalogo, tokens_do_registro(r))]
        doc = docs.get(r["id_paciente"])
        feitas = decididas.get(doc["id_doc"], set()) if doc else set()
        pend = [cod for cod in aplic if cod not in feitas]
        if pend:
            estado, texto = "pendente", f"{len(pend)} pendente" + ("s" if len(pend) > 1 else "")
            if doc and doc["status"] == "entregue":
                texto += " (nova versão)"
        elif doc and doc["status"] == "entregue":
            estado, texto = "entregue", "Entregue"
        elif feitas:
            estado, texto = "decidido", "Decididas"
        else:
            estado, texto = "sem", ""
        saida[r["id_paciente"]] = {"aplicaveis": len(aplic), "pendentes": len(pend), "estado": estado, "texto": texto}
    return saida


# ----------------------------------------------------------------------------------------- sessão
class SessaoCondutasAlta:
    """Estado das condutas de alta de UM paciente (sem interface). A tela só chama estes métodos."""

    def __init__(self, db_path, id_paciente, nome_paciente="", catalogo=None, agora=None):
        self.db, self.id_paciente = db_path, id_paciente
        self.nome_paciente = nome_paciente or ""
        self.catalogo = catalogo or carregar_catalogo()
        self._agora = agora
        self.registro, self.tokens = None, set()
        self.doc, self.itens, self.manuais = None, {}, []
        self.carregar()

    # --- leitura
    def carregar(self):
        self.registro = registro_mais_recente(self.db, self.id_paciente)
        self.tokens = tokens_do_registro(self.registro)
        if not self.nome_paciente and self.registro:
            self.nome_paciente = self.registro.get("nome_paciente") or ""
        self.doc = documento_atual(self.db, self.id_paciente)
        self.itens = {i["codigo"]: i for i in listar_itens(self.db, self.doc["id_doc"])} if self.doc else {}

    @property
    def entregue(self):
        return bool(self.doc and self.doc["status"] == "entregue")

    @property
    def rotulos(self):
        return rotulos_do_registro(self.registro)

    def aplicaveis(self):
        return condutas_aplicaveis(self.catalogo, self.tokens)

    def pendentes(self):
        return [c.codigo for c in self.aplicaveis() if c.codigo not in self.itens]

    def cartoes(self):
        """Um dict por conduta: sugeridas pelo Mapa, já decididas (mesmo que a regra tenha mudado) e adicionadas à mão."""
        sugeridas = [c.codigo for c in self.aplicaveis()]
        ordem = list(sugeridas)
        for cod in list(self.itens) + self.manuais:
            if cod not in ordem:
                ordem.append(cod)
        return [self._cartao(cod, cod in sugeridas) for cod in ordem]

    def _cartao(self, cod, sugerida):
        cond, item = self.catalogo.obter(cod), self.itens.get(cod)
        if item:
            return {
                "codigo": cod, "estado": item["decisao"], "origem": item["origem"], "titulo": item["titulo"],
                "titulo_paciente": item["titulo_paciente"] or item["titulo"],
                "texto_paciente": item["texto_paciente"] or "", "texto_profissional": item["texto_profissional"] or "",
                "conferir": [x for x in (item["conferir"] or "").split("\n") if x],
                "fontes": [x for x in (item["referencias"] or "").split("\n") if x],
                "editado": bool(item["editado"]), "justificativa": item["justificativa"] or "",
                "versao_catalogo": item["versao_catalogo"] or "",
                "catalogo_mudou": bool(cond and item["versao_catalogo"] != cond.versao),
                "grupo": cond.grupo if cond else cod.split("-")[0], "decidido_em": item["decidido_em"]}
        return {
            "codigo": cod, "estado": "pendente", "origem": "regra" if sugerida else "manual", "titulo": cond.titulo,
            "titulo_paciente": cond.titulo_paciente, "texto_paciente": cond.paciente,
            "texto_profissional": cond.profissional, "conferir": list(cond.conferir), "fontes": list(cond.fontes),
            "editado": False, "justificativa": "", "versao_catalogo": cond.versao, "catalogo_mudou": False,
            "grupo": cond.grupo, "decidido_em": ""}

    # --- escrita (só em rascunho)
    def _rascunho(self):
        if self.entregue:
            raise ErroCondutasAlta("Este documento já foi entregue e não pode ser alterado. "
                                   "Use \"Criar nova versão\" para fazer correções.")
        if not self.doc:
            self.doc = abrir_rascunho(self.db, self.id_paciente, self._agora)
        return self.doc

    def _conduta(self, codigo):
        c = self.catalogo.obter(codigo)
        if not c:
            raise ErroCondutasAlta(f"Conduta {codigo} não existe no catálogo atual.")
        return c

    def _origem(self, codigo):
        sugeridas = {c.codigo for c in self.aplicaveis()}
        return "regra" if codigo in sugeridas else "manual"

    def confirmar(self, codigo, texto_paciente=None, texto_profissional=None):
        cond = self._conduta(codigo)
        decidir(self.db, self._rascunho()["id_doc"], cond, "confirmada", texto_paciente=texto_paciente,
                texto_profissional=texto_profissional, origem=self._origem(codigo), agora=self._agora)
        self.carregar()

    def corrigir_texto(self, codigo, texto_paciente):
        """Corrige só o texto do paciente de uma conduta já confirmada (o texto técnico fica como foi confirmado)."""
        if not self.doc or codigo not in self.itens:       # nada confirmado ainda: não cria documento à toa
            raise ErroCondutasAlta("Só uma conduta já confirmada pode ter o texto corrigido. Confirme-a primeiro.")
        corrigir_texto_paciente(self.db, self._rascunho()["id_doc"], codigo, texto_paciente,
                                conduta=self.catalogo.obter(codigo), agora=self._agora)
        self.carregar()

    def nao_se_aplica(self, codigo, justificativa):
        cond = self._conduta(codigo)
        decidir(self.db, self._rascunho()["id_doc"], cond, "nao_se_aplica", justificativa=justificativa,
                origem=self._origem(codigo), agora=self._agora)
        self.carregar()

    def desfazer(self, codigo):
        if self.doc and not self.entregue:
            desfazer_decisao(self.db, self.doc["id_doc"], codigo, self._agora)
            self.carregar()

    def adicionar_manual(self, codigo):
        """Põe uma conduta do catálogo na lista (como pendente) mesmo sem gatilho no Mapa."""
        self._conduta(codigo)
        if codigo not in self.manuais:
            self.manuais.append(codigo)

    def salvar_cabecalho(self, nutricionista, crn, recado):
        salvar_cabecalho(self.db, self._rascunho()["id_doc"], nutricionista, crn, recado, self._agora)
        self.carregar()

    def nova_versao(self):
        if not self.entregue:
            raise ErroCondutasAlta("Só um documento entregue precisa de nova versão.")
        abrir_rascunho(self.db, self.id_paciente, self._agora)
        self.carregar()

    def marcar_entregue(self):
        if not self.doc:
            raise ErroCondutasAlta("Não há documento para marcar como entregue.")
        pend = self.pendentes()
        if pend:
            raise ErroCondutasAlta("Ainda há condutas pendentes: " + ", ".join(pend) +
                                   ". Confirme ou marque como \"não se aplica\".")
        marcar_entregue(self.db, self.doc["id_doc"], self._agora)
        self.carregar()

    # --- exportação
    def cabecalho(self):
        d = self.doc or {}
        if not d:
            nome, crn = _padrao_cabecalho(self.db)
            return {"nutricionista": nome, "crn": crn, "recado": ""}
        return {"nutricionista": d.get("nutricionista") or "", "crn": d.get("crn") or "", "recado": d.get("recado") or ""}

    def modelo_exportacao(self):
        """Dicionário entregue aos geradores de PDF (condutas_alta_export), sem nenhuma dependência de banco."""
        cab = self.cabecalho()
        quando = ((self.doc or {}).get("entregue_em") or _agora(self._agora))[:10]
        return {
            "paciente": self.nome_paciente, "data": mdb.iso_para_br(quando), "condicoes": self.rotulos,
            "nutricionista": cab["nutricionista"], "crn": cab["crn"], "recado": cab["recado"],
            "status": (self.doc or {}).get("status", "rascunho"),
            "catalogo": [f"{g['titulo']} ({g['versao']})" for g in self.catalogo.grupos.values()],
            "itens": self.cartoes()}


def _principal():
    try:
        cat = carregar_catalogo()
    except ErroCatalogo as erro:
        print(erro)
        return 1
    versoes = ", ".join(k + " " + v["versao"] for k, v in cat.grupos.items())
    print(f"Catálogo ok: {len(cat.condutas)} condutas em {len(cat.grupos)} grupos ({versoes}).")
    return 0


if __name__ == "__main__":
    sys.exit(_principal())
