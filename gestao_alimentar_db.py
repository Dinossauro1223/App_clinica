# -*- coding: utf-8 -*-
"""Persistência e regras de negócio da Gestão alimentar (Fichas técnicas).

A base TBCA é importada do arquivo fornecido pelo usuário; produtos/preços/saldos
são sincronizados do banco do Almoxarifado mobile. O módulo não altera o banco
mobile nem presume conversão entre unidades incompatíveis.
"""
from __future__ import annotations

import os
import math
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime

TABELA_TBCA = "GA_TBCA_Alimentos"
TABELA_PRODUTOS = "GA_Produtos_Almox"
TABELA_FICHAS = "GA_Fichas"
TABELA_INGREDIENTES = "GA_Ficha_Ingredientes"

NUTRIENTES = (
    "kcal", "proteina", "carboidrato", "lipidio", "saturados", "polinsaturados",
    "monoinsaturados", "trans", "colesterol", "fibra", "sodio", "ferro",
    "vitamina_c", "folato", "umidade", "selenio", "cobre", "potassio",
    "fosforo", "magnesio", "vitamina_d", "tiamina", "riboflavina", "niacina",
    "vitamina_b6", "vitamina_e", "zinco", "calcio", "vitamina_a_re", "vitamina_a_rae", "vitamina_b12",
)

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {TABELA_TBCA} (
    id_tbca TEXT PRIMARY KEY,
    tipo TEXT,
    npu REAL,
    fc_referencia REAL,
    fc_menucontrol TEXT,
    medida_caseira TEXT,
    per_capita TEXT,
    alimento TEXT NOT NULL,
    {', '.join(c + ' REAL' for c in NUTRIENTES)},
    fonte TEXT NOT NULL DEFAULT 'TBCA (2024)',
    importado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ga_tbca_alimento ON {TABELA_TBCA}(alimento);
CREATE TABLE IF NOT EXISTS {TABELA_PRODUTOS} (
    id_mobile INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    unidade_estoque TEXT,
    preco_unitario REAL,
    embalagem_qtd REAL,
    embalagem_un TEXT,
    estoque_qtd REAL,
    estoque_data TEXT,
    sincronizado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ga_produto_nome ON {TABELA_PRODUTOS}(nome);
CREATE TABLE IF NOT EXISTS {TABELA_FICHAS} (
    id_ficha INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    categoria TEXT,
    porcoes REAL NOT NULL DEFAULT 1 CHECK(porcoes > 0),
    descricao TEXT,
    ativa INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ga_ficha_nome ON {TABELA_FICHAS}(nome);
CREATE TABLE IF NOT EXISTS {TABELA_INGREDIENTES} (
    id_ingrediente INTEGER PRIMARY KEY AUTOINCREMENT,
    id_ficha INTEGER NOT NULL REFERENCES {TABELA_FICHAS}(id_ficha) ON DELETE CASCADE,
    ordem INTEGER NOT NULL DEFAULT 0,
    tbca_id TEXT,
    nome TEXT NOT NULL,
    id_produto_mobile INTEGER,
    unidade TEXT NOT NULL DEFAULT 'g',
    qtd_per_capita REAL NOT NULL CHECK(qtd_per_capita > 0),
    fator_correcao REAL NOT NULL DEFAULT 1 CHECK(fator_correcao > 0),
    medida_caseira TEXT,
    densidade_g_ml REAL,
    npu REAL,
    observacao TEXT
);
CREATE INDEX IF NOT EXISTS idx_ga_ingredientes_ficha ON {TABELA_INGREDIENTES}(id_ficha, ordem);
"""


def _agora():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def conectar(db_path):
    conn = sqlite3.connect(str(db_path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


@contextmanager
def _conexao(db_path):
    """Contexto transacional que também fecha a conexão SQLite ao sair."""
    conn = conectar(db_path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def inicializar(db_path):
    """Cria o esquema da função de modo idempotente, sem alterar tabelas clínicas."""
    os.makedirs(os.path.dirname(os.path.abspath(str(db_path))), exist_ok=True)
    with _conexao(db_path) as conn:
        conn.executescript(_SCHEMA)


def _normalizar_cabecalho(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch)).lower()
    return "".join(ch for ch in texto if ch.isalnum())


def _numero(valor):
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float)):
        numero = float(valor)
        return numero if math.isfinite(numero) else None
    texto = str(valor).strip().replace("R$", "").replace(" ", "")
    if not texto:
        return None
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        numero = float(texto)
        return numero if math.isfinite(numero) else None
    except (TypeError, ValueError):
        return None


_CABECALHOS_TBCA = {
    # Chaves já normalizadas: acentos, espaços, parênteses e unidades são removidos.
    "id": "id_tbca", "tipo": "tipo", "npu": "npu",
    "fatordecorrecaofcalimentospercapita1997": "fc_referencia",
    "fcmenucontrolcom": "fc_menucontrol", "medidacaseiramd": "medida_caseira",
    "percapita": "per_capita", "alimento": "alimento",
    "kcal": "kcal", "proteina": "proteina", "carboidrato": "carboidrato",
    "lipidio": "lipidio", "acidosgraxossaturados": "saturados",
    "acidosgraxospolinsaturados": "polinsaturados",
    "acidosgraxosmonoinsaturados": "monoinsaturados",
    "acidosgraxostrans": "trans", "colesterol": "colesterol",
    "fibraalimentar": "fibra", "sodio": "sodio", "ferro": "ferro",
    "vitaminac": "vitamina_c", "equivalentedefolato": "folato",
    "umidadeg": "umidade", "selenio": "selenio", "cobre": "cobre",
    "potassio": "potassio", "fosforo": "fosforo", "magnesio": "magnesio",
    "vitaminad": "vitamina_d", "tiamina": "tiamina", "riboflavina": "riboflavina",
    "niacina": "niacina", "vitaminab6": "vitamina_b6",
    "alfa0tocoferolvitaminae": "vitamina_e", "zinco": "zinco",
    "calcio": "calcio", "vitaminaare": "vitamina_a_re",
    "vitaminaarae": "vitamina_a_rae", "vitaminab12": "vitamina_b12",
}


def importar_tbca_excel(db_path, caminho_xlsx, nome_aba="TBCA (2024)"):
    """Importa a aba de composição TBCA; requer openpyxl (já previsto no requirements)."""
    if not os.path.isfile(caminho_xlsx):
        raise FileNotFoundError(caminho_xlsx)
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - depende do ambiente de instalação
        raise RuntimeError("A importação da TBCA requer openpyxl. Instale as dependências do NutriLab.") from exc

    livro = load_workbook(caminho_xlsx, read_only=True, data_only=True)
    try:
        if nome_aba not in livro.sheetnames:
            raise ValueError("A planilha não contém a aba '%s'. Abas encontradas: %s" %
                             (nome_aba, ", ".join(livro.sheetnames)))
        aba = livro[nome_aba]
        cabecalhos = [_normalizar_cabecalho(v) for v in next(aba.iter_rows(min_row=1, max_row=1, values_only=True))]
        indices = {}
        for i, cab in enumerate(cabecalhos):
            campo = _CABECALHOS_TBCA.get(cab)
            if campo:
                indices[campo] = i
        if "id_tbca" not in indices or "alimento" not in indices:
            raise ValueError("A aba TBCA precisa ter as colunas ID e ALIMENTO.")

        campos = ["id_tbca", "tipo", "npu", "fc_referencia", "fc_menucontrol", "medida_caseira", "per_capita", "alimento", *NUTRIENTES]
        colunas_sql = ",".join(campos) + ",fonte,importado_em"
        placeholders = ",".join("?" for _ in range(len(campos) + 2))
        updates = ",".join(f"{c}=excluded.{c}" for c in campos if c != "id_tbca") + ",fonte=excluded.fonte,importado_em=excluded.importado_em"
        sql = f"INSERT INTO {TABELA_TBCA} ({colunas_sql}) VALUES ({placeholders}) ON CONFLICT(id_tbca) DO UPDATE SET {updates}"
        momento = _agora()
        lote, importados = [], 0
        conn = conectar(db_path)
        try:
            for linha in aba.iter_rows(min_row=2, values_only=True):
                identificador = linha[indices["id_tbca"]] if indices["id_tbca"] < len(linha) else None
                alimento = linha[indices["alimento"]] if indices["alimento"] < len(linha) else None
                if identificador in (None, "") or alimento in (None, ""):
                    continue
                valores = []
                for campo in campos:
                    idx = indices.get(campo)
                    bruto = linha[idx] if idx is not None and idx < len(linha) else None
                    if campo in ("id_tbca", "tipo", "fc_menucontrol", "medida_caseira", "per_capita", "alimento"):
                        valores.append(str(bruto).strip() if bruto is not None else None)
                    else:
                        valores.append(_numero(bruto))
                lote.append(tuple(valores) + ("TBCA (2024)", momento))
                if len(lote) >= 500:
                    conn.executemany(sql, lote)
                    importados += len(lote)
                    lote.clear()
            if lote:
                conn.executemany(sql, lote)
                importados += len(lote)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return importados
    finally:
        livro.close()


def listar_alimentos(db_path, termo="", limite=60):
    termo = (termo or "").strip()
    with _conexao(db_path) as conn:
        if termo:
            like = "%" + termo.replace("%", "\\%").replace("_", "\\_") + "%"
            rows = conn.execute(
                f"SELECT id_tbca,tipo,npu,fc_referencia,medida_caseira,per_capita,alimento,{','.join(NUTRIENTES)} "
                f"FROM {TABELA_TBCA} WHERE alimento LIKE ? ESCAPE '\\' OR id_tbca=? ORDER BY alimento LIMIT ?",
                (like, termo, max(1, min(int(limite), 500)))
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT id_tbca,tipo,npu,fc_referencia,medida_caseira,per_capita,alimento,{','.join(NUTRIENTES)} "
                f"FROM {TABELA_TBCA} ORDER BY alimento LIMIT ?", (max(1, min(int(limite), 500)),)
            ).fetchall()
        return [dict(r) for r in rows]


def contar_alimentos(db_path):
    with _conexao(db_path) as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {TABELA_TBCA}").fetchone()[0])


def sincronizar_produtos_almox(db_path, linhas_mobile):
    """Atualiza o espelho local dos produtos e saldos do estoque almoxarifado."""
    agora = _agora()
    sql = f"""INSERT INTO {TABELA_PRODUTOS}
        (id_mobile,nome,unidade_estoque,preco_unitario,embalagem_qtd,embalagem_un,estoque_qtd,estoque_data,sincronizado_em)
        VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id_mobile) DO UPDATE SET
        nome=excluded.nome,unidade_estoque=excluded.unidade_estoque,preco_unitario=excluded.preco_unitario,
        embalagem_qtd=excluded.embalagem_qtd,embalagem_un=excluded.embalagem_un,
        estoque_qtd=excluded.estoque_qtd,estoque_data=excluded.estoque_data,sincronizado_em=excluded.sincronizado_em"""
    normalizados = []
    for item in linhas_mobile or []:
        iid = item.get("id_item", item.get("id"))
        nome = str(item.get("nome") or "").strip()
        if iid is None or not nome:
            continue
        normalizados.append((int(iid), nome, item.get("unidade"), _numero(item.get("preco_unitario")),
                             _numero(item.get("embalagem_qtd")), item.get("embalagem_un"),
                             _numero(item.get("qtd")), item.get("data_base"), agora))
    with _conexao(db_path) as conn:
        conn.executemany(sql, normalizados)
    return len(normalizados)


def listar_produtos_almox(db_path, termo=""):
    with _conexao(db_path) as conn:
        if termo:
            rows = conn.execute(f"SELECT * FROM {TABELA_PRODUTOS} WHERE nome LIKE ? ORDER BY nome", (f"%{termo}%",)).fetchall()
        else:
            rows = conn.execute(f"SELECT * FROM {TABELA_PRODUTOS} ORDER BY nome").fetchall()
        return [dict(r) for r in rows]


def listar_fichas(db_path, incluir_inativas=False):
    filtro = "" if incluir_inativas else "WHERE ativa=1"
    with _conexao(db_path) as conn:
        rows = conn.execute(f"SELECT * FROM {TABELA_FICHAS} {filtro} ORDER BY nome COLLATE NOCASE").fetchall()
        return [dict(r) for r in rows]


def obter_ficha(db_path, id_ficha):
    with _conexao(db_path) as conn:
        ficha = conn.execute(f"SELECT * FROM {TABELA_FICHAS} WHERE id_ficha=?", (int(id_ficha),)).fetchone()
        if not ficha:
            return None
        itens = conn.execute(
            f"SELECT i.*, t.alimento AS alimento_tbca, p.nome AS nome_produto "
            f"FROM {TABELA_INGREDIENTES} i LEFT JOIN {TABELA_TBCA} t ON t.id_tbca=i.tbca_id "
            f"LEFT JOIN {TABELA_PRODUTOS} p ON p.id_mobile=i.id_produto_mobile "
            "WHERE i.id_ficha=? ORDER BY i.ordem,i.id_ingrediente", (int(id_ficha),)
        ).fetchall()
        return {**dict(ficha), "ingredientes": [dict(r) for r in itens]}


def salvar_ficha(db_path, nome, categoria, porcoes, ingredientes, descricao="", id_ficha=None):
    nome = str(nome or "").strip()
    porcoes = _numero(porcoes)
    if not nome:
        raise ValueError("Informe o nome da preparação.")
    if porcoes is None or porcoes <= 0:
        raise ValueError("O número de porções precisa ser maior que zero.")
    if not ingredientes:
        raise ValueError("Adicione pelo menos um ingrediente à ficha.")
    preparados = []
    for ordem, item in enumerate(ingredientes, 1):
        nome_item = str(item.get("nome") or "").strip()
        qtd = _numero(item.get("qtd_per_capita"))
        fc = _numero(item.get("fator_correcao", 1))
        if not nome_item or qtd is None or qtd <= 0:
            raise ValueError("Cada ingrediente precisa ter nome e quantidade per capita maior que zero.")
        if fc is None or fc <= 0:
            raise ValueError("O fator de correção deve ser maior que zero.")
        unidade = str(item.get("unidade") or "g").strip().lower()
        if unidade not in {"g", "kg", "mg", "ml", "l", "un"}:
            raise ValueError("Unidade não suportada: %s. Use g, kg, mg, ml, L ou un." % unidade)
        preparados.append((ordem, item.get("tbca_id"), nome_item, item.get("id_produto_mobile"), unidade,
                           qtd, fc, item.get("medida_caseira"), _numero(item.get("densidade_g_ml")),
                           _numero(item.get("npu")), item.get("observacao")))
    agora = _agora()
    with _conexao(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            if id_ficha is None:
                cur = conn.execute(
                    f"INSERT INTO {TABELA_FICHAS}(nome,categoria,porcoes,descricao,criado_em,atualizado_em) VALUES(?,?,?,?,?,?)",
                    (nome, categoria, porcoes, descricao, agora, agora)
                )
                id_ficha = cur.lastrowid
            else:
                cur = conn.execute(
                    f"UPDATE {TABELA_FICHAS} SET nome=?,categoria=?,porcoes=?,descricao=?,atualizado_em=? WHERE id_ficha=? AND ativa=1",
                    (nome, categoria, porcoes, descricao, agora, int(id_ficha))
                )
                if cur.rowcount != 1:
                    raise ValueError("Ficha não encontrada ou inativa.")
                conn.execute(f"DELETE FROM {TABELA_INGREDIENTES} WHERE id_ficha=?", (int(id_ficha),))
            conn.executemany(
                f"INSERT INTO {TABELA_INGREDIENTES}(id_ficha,ordem,tbca_id,nome,id_produto_mobile,unidade,qtd_per_capita,fator_correcao,medida_caseira,densidade_g_ml,npu,observacao) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                [(int(id_ficha), *x) for x in preparados]
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return int(id_ficha)


def inativar_ficha(db_path, id_ficha):
    with _conexao(db_path) as conn:
        cur = conn.execute(f"UPDATE {TABELA_FICHAS} SET ativa=0,atualizado_em=? WHERE id_ficha=?", (_agora(), int(id_ficha)))
        return cur.rowcount == 1


_UNIDADES_BASE = {
    "g": ("massa", 1.0), "kg": ("massa", 1000.0), "mg": ("massa", 0.001),
    "ml": ("volume", 1.0), "l": ("volume", 1000.0), "un": ("unidade", 1.0),
}


def _para_base(quantidade, unidade):
    regra = _UNIDADES_BASE.get(str(unidade or "").strip().lower())
    if regra is None:
        return None, None
    return regra[0], float(quantidade) * regra[1]


def calcular_ficha(db_path, id_ficha):
    ficha = obter_ficha(db_path, id_ficha)
    if not ficha:
        raise ValueError("Ficha não encontrada.")
    porcoes = float(ficha["porcoes"])
    linhas, totais_nutri = [], {n: 0.0 for n in NUTRIENTES}
    nutrientes_faltantes = {n: 0 for n in NUTRIENTES}
    custo_parcial = 0.0
    custos_faltantes = 0
    estoque_faltante = 0
    estoque_incompleto = 0

    for item in ficha["ingredientes"]:
        qtd_pc = float(item["qtd_per_capita"])
        fc = float(item["fator_correcao"] or 1)
        qtd_liquida_total = qtd_pc * porcoes
        qtd_bruta_total = qtd_liquida_total * fc
        dimensao_item, qtd_pc_base = _para_base(qtd_pc, item["unidade"])
        _, qtd_bruta_base = _para_base(qtd_bruta_total, item["unidade"])
        if dimensao_item is None:
            raise ValueError("Unidade inválida na ficha: %s" % item["unidade"])

        # A TBCA informa composição por 100 g; volume só é convertido com densidade fornecida.
        gramas_pc = None
        if dimensao_item == "massa":
            gramas_pc = qtd_pc_base
        elif dimensao_item == "volume" and item["densidade_g_ml"] not in (None, 0):
            _, ml = _para_base(qtd_pc, item["unidade"])
            gramas_pc = ml * float(item["densidade_g_ml"])

        dados_tbca = {n: item.get(n) for n in NUTRIENTES}
        # obter_ficha inclui apenas os campos do ingrediente; composição numérica é carregada aqui.
        if item.get("tbca_id"):
            with _conexao(db_path) as conn:
                registro = conn.execute(f"SELECT {','.join(NUTRIENTES)} FROM {TABELA_TBCA} WHERE id_tbca=?", (item["tbca_id"],)).fetchone()
            if registro:
                dados_tbca = dict(registro)
        dados_linha = {}
        for nutriente in NUTRIENTES:
            valor = dados_tbca.get(nutriente)
            if gramas_pc is None or valor is None:
                nutrientes_faltantes[nutriente] += 1
                dados_linha[nutriente] = None
            else:
                contribuicao = (gramas_pc / 100.0) * float(valor)
                totais_nutri[nutriente] += contribuicao
                dados_linha[nutriente] = contribuicao

        produto = None
        if item.get("id_produto_mobile") is not None:
            with _conexao(db_path) as conn:
                produto = conn.execute(f"SELECT * FROM {TABELA_PRODUTOS} WHERE id_mobile=?", (item["id_produto_mobile"],)).fetchone()
            produto = dict(produto) if produto else None

        custo_linha = None
        estoque_disp_base = None
        status_estoque = None
        if produto:
            if produto.get("embalagem_qtd") not in (None, 0):
                dimensao_emb, conteudo_base = _para_base(produto["embalagem_qtd"], produto.get("embalagem_un"))
                if dimensao_emb == dimensao_item and conteudo_base:
                    # O estoque pode ser conferido mesmo quando o preço ainda não foi cadastrado.
                    if produto.get("estoque_qtd") is not None:
                        estoque_disp_base = float(produto["estoque_qtd"]) * conteudo_base
                        status_estoque = estoque_disp_base + 1e-9 >= qtd_bruta_base
                        if not status_estoque:
                            estoque_faltante += 1
                    else:
                        estoque_incompleto += 1
                    if produto.get("preco_unitario") is not None:
                        custo_linha = (qtd_bruta_base / conteudo_base) * float(produto["preco_unitario"])
                    else:
                        custos_faltantes += 1
                else:
                    custos_faltantes += 1
                    estoque_incompleto += 1
            else:
                custos_faltantes += 1
                estoque_incompleto += 1
        else:
            custos_faltantes += 1
            estoque_incompleto += 1
        if custo_linha is not None:
            custo_parcial += custo_linha

        linhas.append({
            **dict(item), "qtd_liquida_total": qtd_liquida_total, "qtd_bruta_total": qtd_bruta_total,
            "qtd_bruta_base": qtd_bruta_base, "custo_total": custo_linha,
            "custo_per_capita": (custo_linha / porcoes) if custo_linha is not None else None,
            "estoque_disponivel_base": estoque_disp_base, "estoque_suficiente": status_estoque,
            "nutrientes_per_capita": dados_linha,
        })

    return {
        "ficha": ficha, "linhas": linhas, "porcoes": porcoes,
        "custo_parcial_total": custo_parcial,
        "custo_total": custo_parcial if custos_faltantes == 0 else None,
        "custo_por_porcao": custo_parcial / porcoes if custos_faltantes == 0 else None,
        "custos_faltantes": custos_faltantes,
        "estoque_insuficiente": estoque_faltante,
        "estoque_incompleto": estoque_incompleto,
        "nutrientes_per_capita": totais_nutri,
        "nutrientes_total": {n: v * porcoes for n, v in totais_nutri.items()},
        "nutrientes_faltantes": nutrientes_faltantes,
    }
