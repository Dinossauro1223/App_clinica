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
    tbca_id TEXT,
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
    observacao TEXT,
    preco_unitario_manual REAL
);
CREATE INDEX IF NOT EXISTS idx_ga_ingredientes_ficha ON {TABELA_INGREDIENTES}(id_ficha, ordem);
CREATE TABLE IF NOT EXISTS GA_Preparacoes_Dia (
 id_preparacao_dia INTEGER PRIMARY KEY AUTOINCREMENT,
 data TEXT NOT NULL,
 refeicao TEXT NOT NULL,
 nome TEXT NOT NULL,
 porcoes_previstas REAL,
 id_ficha INTEGER REFERENCES GA_Fichas(id_ficha),
 ativa INTEGER NOT NULL DEFAULT 1,
 criado_em TEXT NOT NULL,
 atualizado_em TEXT NOT NULL,
 UNIQUE(data, refeicao, nome)
);
CREATE INDEX IF NOT EXISTS idx_ga_preparacoes_dia_data ON GA_Preparacoes_Dia(data, refeicao, ativa);
CREATE TABLE IF NOT EXISTS GA_Consumo_Alocacoes (
 id_alocacao INTEGER PRIMARY KEY AUTOINCREMENT,
 data_movimento TEXT NOT NULL,
 id_movimento_mobile INTEGER NOT NULL,
 id_item_mobile INTEGER,
 id_preparacao_dia INTEGER,
 data_preparacao TEXT,
 refeicao_snapshot TEXT,
 preparacao_nome_snapshot TEXT NOT NULL,
 porcoes_previstas_snapshot REAL,
 tipo_destino TEXT NOT NULL CHECK(tipo_destino IN ('preparacao','uso_geral','perda')),
 quantidade REAL NOT NULL CHECK(quantidade > 0),
 unidade TEXT NOT NULL,
 valor_unitario_snapshot REAL,
 custo_snapshot REAL,
 origem_preco_snapshot TEXT,
 revisao INTEGER NOT NULL DEFAULT 1,
 ativa INTEGER NOT NULL DEFAULT 1,
 usuario TEXT,
 observacao TEXT,
 criado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ga_alocacoes_movimento ON GA_Consumo_Alocacoes(data_movimento, id_movimento_mobile, ativa);
CREATE INDEX IF NOT EXISTS idx_ga_alocacoes_preparacao ON GA_Consumo_Alocacoes(data_preparacao, refeicao_snapshot, preparacao_nome_snapshot, ativa);
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
        colunas_ingredientes = {r[1] for r in conn.execute(f"PRAGMA table_info({TABELA_INGREDIENTES})")}
        if "preco_unitario_manual" not in colunas_ingredientes:
            conn.execute(f"ALTER TABLE {TABELA_INGREDIENTES} ADD COLUMN preco_unitario_manual REAL")
        colunas_produtos = {r[1] for r in conn.execute(f"PRAGMA table_info({TABELA_PRODUTOS})")}
        if "tbca_id" not in colunas_produtos:
            conn.execute(f"ALTER TABLE {TABELA_PRODUTOS} ADD COLUMN tbca_id TEXT")


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
            # A busca da TBCA é por prefixo: ao digitar "arroz", lista todos os alimentos
            # cujo nome começa com "arroz", sem misturar ocorrências no meio do nome.
            prefixo = termo.replace("%", "\\%").replace("_", "\\_") + "%"
            rows = conn.execute(
                f"SELECT id_tbca,tipo,npu,fc_referencia,medida_caseira,per_capita,alimento,{','.join(NUTRIENTES)} "
                f"FROM {TABELA_TBCA} WHERE alimento LIKE ? ESCAPE '\\' COLLATE NOCASE OR id_tbca=? "
                f"ORDER BY CASE WHEN alimento LIKE ? ESCAPE '\\' COLLATE NOCASE THEN 0 ELSE 1 END, alimento COLLATE NOCASE LIMIT ?",
                (prefixo, termo, prefixo, max(1, min(int(limite), 10000)))
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
        (id_mobile,nome,unidade_estoque,preco_unitario,embalagem_qtd,embalagem_un,tbca_id,estoque_qtd,estoque_data,sincronizado_em)
        VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id_mobile) DO UPDATE SET
        nome=excluded.nome,unidade_estoque=excluded.unidade_estoque,preco_unitario=excluded.preco_unitario,
        embalagem_qtd=excluded.embalagem_qtd,embalagem_un=excluded.embalagem_un,tbca_id=excluded.tbca_id,
        estoque_qtd=excluded.estoque_qtd,estoque_data=excluded.estoque_data,sincronizado_em=excluded.sincronizado_em"""
    normalizados = []
    for item in linhas_mobile or []:
        iid = item.get("id_item", item.get("id"))
        nome = str(item.get("nome") or "").strip()
        if iid is None or not nome:
            continue
        normalizados.append((int(iid), nome, item.get("unidade"), _numero(item.get("preco_unitario")),
                             _numero(item.get("embalagem_qtd")), item.get("embalagem_un"), item.get("tbca_id"),
                             _numero(item.get("qtd")), item.get("data_base"), agora))
    with _conexao(db_path) as conn:
        conn.executemany(sql, normalizados)
    return len(normalizados)


def listar_produtos_almox(db_path, termo=""):
    with _conexao(db_path) as conn:
        sql = (f"SELECT p.*,t.alimento AS tbca_alimento FROM {TABELA_PRODUTOS} p "
               f"LEFT JOIN {TABELA_TBCA} t ON t.id_tbca=p.tbca_id ")
        if termo:
            rows = conn.execute(sql + "WHERE p.nome LIKE ? ORDER BY p.nome", (f"%{termo}%",)).fetchall()
        else:
            rows = conn.execute(sql + "ORDER BY p.nome").fetchall()
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
        preco_manual = _numero(item.get("preco_unitario_manual"))
        if preco_manual is not None and preco_manual < 0:
            raise ValueError("O preço manual não pode ser negativo.")
        preparados.append((ordem, item.get("tbca_id"), nome_item, item.get("id_produto_mobile"), unidade,
                           qtd, fc, item.get("medida_caseira"), _numero(item.get("densidade_g_ml")),
                           _numero(item.get("npu")), preco_manual, item.get("observacao")))
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
                f"INSERT INTO {TABELA_INGREDIENTES}(id_ficha,ordem,tbca_id,nome,id_produto_mobile,unidade,qtd_per_capita,fator_correcao,medida_caseira,densidade_g_ml,npu,preco_unitario_manual,observacao) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
        preco_manual = _numero(item.get("preco_unitario_manual"))
        if produto:
            if produto.get("embalagem_qtd") not in (None, 0):
                dimensao_emb, conteudo_base = _para_base(produto["embalagem_qtd"], produto.get("embalagem_un"))
                if dimensao_emb == dimensao_item and conteudo_base:
                    # Estoque continua sendo calculado pelo vínculo, independentemente da origem do preço.
                    if produto.get("estoque_qtd") is not None:
                        estoque_disp_base = float(produto["estoque_qtd"]) * conteudo_base
                        status_estoque = estoque_disp_base + 1e-9 >= qtd_bruta_base
                        if not status_estoque:
                            estoque_faltante += 1
                    else:
                        estoque_incompleto += 1
                else:
                    estoque_incompleto += 1
            else:
                estoque_incompleto += 1
            # Preço manual por unidade da medida selecionada prevalece; sem ele, usa o preço sincronizado.
            if preco_manual is not None:
                custo_linha = qtd_bruta_total * preco_manual
            elif (produto.get("embalagem_qtd") not in (None, 0)
                  and produto.get("preco_unitario") is not None):
                dimensao_emb, conteudo_base = _para_base(produto["embalagem_qtd"], produto.get("embalagem_un"))
                if dimensao_emb == dimensao_item and conteudo_base:
                    custo_linha = (qtd_bruta_base / conteudo_base) * float(produto["preco_unitario"])
                else:
                    custos_faltantes += 1
            else:
                custos_faltantes += 1
        else:
            estoque_incompleto += 1
            if preco_manual is not None:
                custo_linha = qtd_bruta_total * preco_manual
            else:
                custos_faltantes += 1
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


# --------------------------------------------------------- consumo observado
_REFEICOES_CONSUMO = {"desjejum", "colacao", "almoco", "lanche", "jantar", "ceia"}
_TIPOS_ALOCACAO = {"preparacao", "uso_geral", "perda"}


def _data_iso(valor, campo="data"):
    from datetime import date
    try:
        return date.fromisoformat(str(valor)).isoformat()
    except (TypeError, ValueError):
        raise ValueError("Informe %s no formato AAAA-MM-DD." % campo)


def salvar_preparacoes_dia(db_path, data, refeicao, preparacoes):
    """Registra o cardápio esperado sem exigir que as fichas técnicas já estejam prontas."""
    data = _data_iso(data)
    refeicao = str(refeicao or "").strip().lower()
    if refeicao not in _REFEICOES_CONSUMO:
        raise ValueError("Selecione uma refeição válida.")
    if not isinstance(preparacoes, (list, tuple)):
        raise ValueError("A lista de preparações precisa ser informada.")

    preparados, vistos = [], set()
    for item in preparacoes:
        if isinstance(item, str):
            item = {"nome": item}
        nome = str(item.get("nome") or "").strip()
        chave = nome.casefold()
        if not nome or chave in vistos:
            continue
        vistos.add(chave)
        porcoes = _numero(item.get("porcoes_previstas"))
        if porcoes is not None and porcoes <= 0:
            raise ValueError("As porções previstas precisam ser maiores que zero.")
        ficha_id = item.get("id_ficha")
        if ficha_id not in (None, ""):
            ficha_id = int(ficha_id)
        else:
            ficha_id = None
        preparados.append((nome, porcoes, ficha_id))

    agora = _agora()
    with _conexao(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            if any(x[2] is not None and not conn.execute(
                f"SELECT 1 FROM {TABELA_FICHAS} WHERE id_ficha=? AND ativa=1", (x[2],)
            ).fetchone() for x in preparados):
                raise ValueError("Uma das fichas vinculadas não existe ou está inativa.")
            conn.execute(
                "UPDATE GA_Preparacoes_Dia SET ativa=0, atualizado_em=? WHERE data=? AND refeicao=?",
                (agora, data, refeicao)
            )
            for nome, porcoes, ficha_id in preparados:
                conn.execute("""INSERT INTO GA_Preparacoes_Dia
                    (data,refeicao,nome,porcoes_previstas,id_ficha,ativa,criado_em,atualizado_em)
                    VALUES(?,?,?,?,?,1,?,?)
                    ON CONFLICT(data,refeicao,nome) DO UPDATE SET
                    porcoes_previstas=excluded.porcoes_previstas,id_ficha=excluded.id_ficha,
                    ativa=1,atualizado_em=excluded.atualizado_em""",
                    (data, refeicao, nome, porcoes, ficha_id, agora, agora))
        except Exception:
            conn.rollback()
            raise
    return len(preparados)


def listar_preparacoes_dia(db_path, data, refeicao=None):
    data = _data_iso(data)
    sql = f"""SELECT p.*,f.nome AS nome_ficha
        FROM GA_Preparacoes_Dia p LEFT JOIN {TABELA_FICHAS} f ON f.id_ficha=p.id_ficha
        WHERE p.data=? AND p.ativa=1"""
    args = [data]
    if refeicao:
        refeicao = str(refeicao).strip().lower()
        if refeicao not in _REFEICOES_CONSUMO:
            raise ValueError("Selecione uma refeição válida.")
        sql += " AND p.refeicao=?"
        args.append(refeicao)
    sql += """ ORDER BY CASE p.refeicao WHEN 'desjejum' THEN 1 WHEN 'colacao' THEN 2
        WHEN 'almoco' THEN 3 WHEN 'lanche' THEN 4 WHEN 'jantar' THEN 5 ELSE 6 END,
        p.nome COLLATE NOCASE"""
    with _conexao(db_path) as conn:
        return [dict(r) for r in conn.execute(sql, args)]


def _colunas_mobile_movimentos(conn):
    return {r[1] for r in conn.execute("PRAGMA table_info(Mobile_Movimentos)")}


def listar_movimentos_cozinha(db_path, inicio, fim):
    """Lista retiradas Almoxarifado → Cozinha e devoluções Cozinha → Almoxarifado, sem duplicar Cozinha → Copa."""
    inicio, fim = _data_iso(inicio, "data inicial"), _data_iso(fim, "data final")
    if fim < inicio:
        raise ValueError("A data final deve ser igual ou posterior à inicial.")
    with _conexao(db_path) as conn:
        existe = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='Mobile_Movimentos'"
        ).fetchone()
        if not existe:
            return []
        cols = _colunas_mobile_movimentos(conn)
        id_item = "m.id_item_mobile" if "id_item_mobile" in cols else "NULL"
        preco_mov = "m.valor_unitario_snapshot" if "valor_unitario_snapshot" in cols else "NULL"
        custo_mov = "m.custo_snapshot" if "custo_snapshot" in cols else "NULL"
        por_usuario = "m.por_usuario" if "por_usuario" in cols else "NULL"
        observacao = "m.observacao" if "observacao" in cols else "NULL"
        rows = conn.execute(f"""SELECT m.data,m.id_mobile,m.hora,m.origem,m.destino,m.item,m.unidade,
                    {observacao} AS observacao,
                    CASE WHEN lower(m.origem)='cozinha' AND lower(m.destino)='almox' THEN -m.qtd ELSE m.qtd END AS qtd,
                    m.divergente,{id_item} AS id_item_mobile,{por_usuario} AS por_usuario,
                    COALESCE({preco_mov},p.preco_unitario) AS preco_unitario_snapshot,
                    CASE WHEN {preco_mov} IS NOT NULL THEN 'historico'
                         WHEN p.preco_unitario IS NOT NULL THEN 'atual_estimado' ELSE 'pendente' END AS origem_preco,
                    CASE WHEN lower(m.origem)='cozinha' AND lower(m.destino)='almox'
                         THEN -COALESCE({custo_mov},m.qtd*COALESCE({preco_mov},p.preco_unitario))
                         ELSE COALESCE({custo_mov},m.qtd*COALESCE({preco_mov},p.preco_unitario)) END AS custo_retirada,
                    COALESCE((SELECT SUM(a.quantidade) FROM GA_Consumo_Alocacoes a
                      WHERE a.data_movimento=m.data AND a.id_movimento_mobile=m.id_mobile AND a.ativa=1),0) AS qtd_alocada,
                    COALESCE((SELECT SUM(a.custo_snapshot) FROM GA_Consumo_Alocacoes a
                      WHERE a.data_movimento=m.data AND a.id_movimento_mobile=m.id_mobile AND a.ativa=1),0) AS custo_alocado,
                    COALESCE((SELECT SUM(CASE WHEN a.custo_snapshot IS NULL THEN 1 ELSE 0 END)
                      FROM GA_Consumo_Alocacoes a
                      WHERE a.data_movimento=m.data AND a.id_movimento_mobile=m.id_mobile AND a.ativa=1),0)
                      AS custos_alocados_faltantes
                FROM Mobile_Movimentos m
                LEFT JOIN {TABELA_PRODUTOS} p ON
                    (p.id_mobile={id_item}) OR ({id_item} IS NULL AND lower(p.nome)=lower(m.item)
                    AND lower(COALESCE(p.unidade_estoque,''))=lower(COALESCE(m.unidade,'')))
                WHERE m.data BETWEEN ? AND ? AND (
                    (lower(m.origem)='almox' AND lower(m.destino)='cozinha') OR
                    (lower(m.origem)='cozinha' AND lower(m.destino)='almox'))
                ORDER BY m.data DESC,m.hora DESC,m.id_mobile DESC""", (inicio, fim)).fetchall()
        resultado = []
        for row in rows:
            item = dict(row)
            item["qtd_disponivel_para_alocar"] = max(
                0.0, float(item["qtd"] or 0) - float(item["qtd_alocada"] or 0)
            )
            item["qtd_devolvida"] = 0.0
            item["qtd_devolvida_alocada"] = 0.0
            item["devolucao_sobre_alocada"] = 0.0
            item["custo_retirada"] = (
                float(item["custo_retirada"]) if item["custo_retirada"] is not None else None
            )
            item["custo_alocado"] = (
                None if item["custos_alocados_faltantes"] else float(item["custo_alocado"])
            )
            resultado.append(item)

        # A devolução consome primeiro o saldo ainda não destinado da retirada anterior.
        # Assim, 20 g devolvidos de uma retirada de 100 g deixam só 80 g disponíveis
        # para a preparação original; uma nova retirada poderá ser destinada à refeição seguinte.
        anteriores_por_item = {}
        cronologico = sorted(resultado, key=lambda x: (x["data"], x["hora"], int(x["id_mobile"])))
        for movimento in cronologico:
            chave_item = (movimento.get("id_item_mobile"), movimento["item"], movimento["unidade"])
            quantidade = float(movimento["qtd"] or 0)
            if quantidade > 0:
                anteriores_por_item.setdefault(chave_item, []).append(movimento)
            elif quantidade < 0:
                restante = abs(quantidade)
                for retirada in reversed(anteriores_por_item.get(chave_item, [])):
                    disponivel = float(retirada["qtd_disponivel_para_alocar"] or 0)
                    aplicado = min(restante, disponivel)
                    if aplicado > 0:
                        retirada["qtd_disponivel_para_alocar"] = max(0.0, disponivel - aplicado)
                        retirada["qtd_devolvida"] += aplicado
                        restante -= aplicado
                    if restante > 1e-8:
                        alocado = max(0.0, float(retirada["qtd_alocada"] or 0) - float(retirada["qtd_devolvida_alocada"] or 0))
                        aplicado_alocado = min(restante, alocado)
                        if aplicado_alocado > 0:
                            retirada["qtd_devolvida_alocada"] += aplicado_alocado
                            restante -= aplicado_alocado
                    if restante <= 1e-8:
                        break
                movimento["devolucao_sobre_alocada"] = restante
        return resultado


def salvar_alocacoes_retirada(db_path, data, id_movimento_mobile, alocacoes, usuario=None):
    """Distribui a retirada por preparação, uso geral ou perda; revisões anteriores ficam no histórico."""
    data = _data_iso(data, "data do movimento")
    if not isinstance(alocacoes, (list, tuple)):
        raise ValueError("Informe as destinações da retirada.")
    with _conexao(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='Mobile_Movimentos'"
            ).fetchone():
                raise ValueError("O histórico mobile ainda não foi importado.")
            cols = _colunas_mobile_movimentos(conn)
            mov = conn.execute(
                "SELECT * FROM Mobile_Movimentos WHERE data=? AND id_mobile=?",
                (data, int(id_movimento_mobile))
            ).fetchone()
            if not mov:
                raise ValueError("Retirada mobile não encontrada.")
            if str(mov["origem"]).lower() != "almox" or str(mov["destino"]).lower() != "cozinha":
                raise ValueError("Somente retiradas do almoxarifado para a cozinha podem ser distribuídas aqui.")

            qtd_mov = float(mov["qtd"] or 0)
            id_item = mov["id_item_mobile"] if "id_item_mobile" in cols else None
            preco = mov["valor_unitario_snapshot"] if "valor_unitario_snapshot" in cols else None
            origem_preco = "historico" if preco is not None else None
            if preco is None and id_item is not None:
                produto = conn.execute(
                    f"SELECT preco_unitario FROM {TABELA_PRODUTOS} WHERE id_mobile=?", (id_item,)
                ).fetchone()
                preco = produto["preco_unitario"] if produto else None
                if preco is not None:
                    origem_preco = "atual_estimado"
            if preco is None:
                produto = conn.execute(
                    f"SELECT preco_unitario FROM {TABELA_PRODUTOS} WHERE lower(nome)=lower(?) "
                    "AND lower(COALESCE(unidade_estoque,''))=lower(COALESCE(?,''))",
                    (mov["item"], mov["unidade"])
                ).fetchone()
                preco = produto["preco_unitario"] if produto else None
                if preco is not None:
                    origem_preco = "atual_estimado"
            preco = float(preco) if preco is not None else None

            preparados, total = [], 0.0
            for item in alocacoes:
                tipo = str(item.get("tipo_destino") or "preparacao").strip().lower()
                if tipo not in _TIPOS_ALOCACAO:
                    raise ValueError("Tipo de destinação inválido.")
                quantidade = _numero(item.get("quantidade"))
                if quantidade is None or quantidade <= 0:
                    raise ValueError("Cada destinação precisa de quantidade maior que zero.")
                pid = item.get("id_preparacao_dia")
                nome, data_prep, refeicao, porcoes = None, None, None, None
                if tipo == "preparacao":
                    if pid in (None, ""):
                        raise ValueError("Selecione a preparação de destino.")
                    prep = conn.execute(
                        "SELECT * FROM GA_Preparacoes_Dia WHERE id_preparacao_dia=? AND ativa=1",
                        (int(pid),)
                    ).fetchone()
                    if not prep:
                        raise ValueError("A preparação selecionada não existe ou foi inativada.")
                    nome, data_prep, refeicao, porcoes = (
                        prep["nome"], prep["data"], prep["refeicao"], prep["porcoes_previstas"]
                    )
                    pid = int(pid)
                else:
                    pid = None
                    nome = "Uso geral / não identificado" if tipo == "uso_geral" else "Perda"
                total += quantidade
                preparados.append((pid, nome, data_prep, refeicao, porcoes, tipo, quantidade))
            if total > qtd_mov + 1e-8:
                raise ValueError(
                    "A soma das destinações excede a quantidade retirada (%s %s)." % (qtd_mov, mov["unidade"])
                )

            revisao = conn.execute(
                "SELECT COALESCE(MAX(revisao),0)+1 FROM GA_Consumo_Alocacoes "
                "WHERE data_movimento=? AND id_movimento_mobile=?",
                (data, int(id_movimento_mobile))
            ).fetchone()[0]
            conn.execute(
                "UPDATE GA_Consumo_Alocacoes SET ativa=0 WHERE data_movimento=? AND id_movimento_mobile=? AND ativa=1",
                (data, int(id_movimento_mobile))
            )
            agora = _agora()
            for pid, nome, data_prep, refeicao, porcoes, tipo, quantidade in preparados:
                custo = quantidade * preco if preco is not None else None
                conn.execute("""INSERT INTO GA_Consumo_Alocacoes
                    (data_movimento,id_movimento_mobile,id_item_mobile,id_preparacao_dia,data_preparacao,
                     refeicao_snapshot,preparacao_nome_snapshot,porcoes_previstas_snapshot,tipo_destino,
                     quantidade,unidade,valor_unitario_snapshot,custo_snapshot,origem_preco_snapshot,revisao,ativa,usuario,criado_em)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)""",
                    (data, int(id_movimento_mobile), id_item, pid, data_prep, refeicao, nome, porcoes,
                     tipo, quantidade, mov["unidade"], preco, custo, origem_preco, revisao, usuario, agora))
            conn.commit()
            alocada = sum(x[-1] for x in preparados)
            return {"revisao": int(revisao), "alocada": alocada, "pendente": max(0.0, qtd_mov-alocada)}
        except Exception:
            conn.rollback()
            raise



def gerar_rascunhos_por_horario(db_path, data, movimentos, janelas):
    """Aloca retiradas sem destinação quando horário identifica uma única refeição e cria fichas preliminares."""
    data = _data_iso(data)
    preparacoes = listar_preparacoes_dia(db_path, data)
    por_refeicao = {}
    for prep in preparacoes:
        por_refeicao.setdefault(str(prep["refeicao"]).lower(), []).append(prep)

    def corresponde(hora, janela):
        if not hora or not janela:
            return False
        try:
            h = datetime.strptime(str(hora).strip()[:5], "%H:%M").time()
            abre = datetime.strptime(str(janela.get("abre") or "").strip()[:5], "%H:%M").time()
            fecha = datetime.strptime(str(janela.get("fecha") or "").strip()[:5], "%H:%M").time()
        except (TypeError, ValueError):
            return False
        return abre <= h <= fecha if abre <= fecha else (h >= abre or h <= fecha)

    relatorio = {
        "alocadas": 0, "rascunhos": 0, "sem_horario": 0,
        "horario_ambiguo": 0, "sem_preparacao": 0, "varias_preparacoes": 0,
        "ja_alocadas": 0, "sem_porcoes": 0, "erros": [],
    }
    for mov in movimentos:
        restante = float(mov.get("qtd_disponivel_para_alocar") or 0)
        if restante <= 0 or float(mov.get("qtd_alocada") or 0) > 0:
            relatorio["ja_alocadas"] += 1
            continue
        matches = [ref for ref, janela in (janelas or {}).items() if corresponde(mov.get("hora"), janela)]
        if len(matches) == 0:
            relatorio["sem_horario"] += 1
            continue
        if len(matches) > 1:
            relatorio["horario_ambiguo"] += 1
            continue
        opcoes = por_refeicao.get(matches[0], [])
        if not opcoes:
            relatorio["sem_preparacao"] += 1
            continue
        if len(opcoes) != 1:
            relatorio["varias_preparacoes"] += 1
            continue
        prep = opcoes[0]
        try:
            salvar_alocacoes_retirada(
                db_path, data, mov["id_mobile"],
                [{"tipo_destino": "preparacao",
                  "id_preparacao_dia": prep["id_preparacao_dia"],
                  "quantidade": restante}],
                usuario="Automático por horário",
            )
            relatorio["alocadas"] += 1
        except Exception as exc:
            relatorio["erros"].append("Movimento %s: %s" % (mov.get("id_mobile"), exc))

    alimentos = {str(a["id_tbca"]): a for a in listar_alimentos(db_path, limite=10000)}
    for prep in preparacoes:
        if prep.get("id_ficha"):
            continue
        porcoes = _numero(prep.get("porcoes_previstas"))
        if porcoes is None or porcoes <= 0:
            relatorio["sem_porcoes"] += 1
            continue
        with _conexao(db_path) as conn:
            itens = [dict(r) for r in conn.execute(
                f"""SELECT a.id_item_mobile,SUM(a.quantidade) AS qtd_estoque,
                           COALESCE(p.nome,m.item) AS nome,p.embalagem_qtd,p.embalagem_un,p.tbca_id
                    FROM GA_Consumo_Alocacoes a
                    JOIN Mobile_Movimentos m
                      ON m.data=a.data_movimento AND m.id_mobile=a.id_movimento_mobile
                    LEFT JOIN {TABELA_PRODUTOS} p ON p.id_mobile=a.id_item_mobile
                    WHERE a.id_preparacao_dia=? AND a.data_movimento=?
                      AND a.ativa=1 AND a.tipo_destino='preparacao'
                    GROUP BY a.id_item_mobile,p.nome,m.item,p.embalagem_qtd,p.embalagem_un,p.tbca_id
                    ORDER BY nome COLLATE NOCASE""",
                (prep["id_preparacao_dia"], data))]
        ingredientes = []
        for item in itens:
            qtd_estoque = _numero(item.get("qtd_estoque"))
            if qtd_estoque is None or qtd_estoque <= 0:
                continue
            conteudo = _numero(item.get("embalagem_qtd"))
            unidade = str(item.get("embalagem_un") or "").strip().lower()
            if conteudo is not None and conteudo > 0 and unidade in {"g", "ml", "un"}:
                quantidade_total = qtd_estoque * conteudo
            else:
                quantidade_total, unidade = qtd_estoque, "un"
            alimento = alimentos.get(str(item.get("tbca_id") or ""))
            fc = _numero(alimento.get("fc_referencia")) if alimento else None
            if fc is None or fc <= 0:
                fc = 1.0
            ingredientes.append({
                "tbca_id": item.get("tbca_id"),
                "nome": item.get("nome") or "Insumo sem nome",
                "id_produto_mobile": item.get("id_item_mobile"),
                "unidade": unidade,
                "qtd_per_capita": quantidade_total / porcoes,
                "fator_correcao": fc,
                "medida_caseira": alimento.get("medida_caseira") if alimento else None,
                "npu": _numero(alimento.get("npu")) if alimento else None,
                "observacao": ("Quantidade calculada a partir das retiradas do almoxarifado; revisar."
                               if not alimento else "Rascunho automático por horário; revisar antes de validar."),
            })
        if not ingredientes:
            continue
        descricao = (
            "RASCUNHO AUTOMÁTICO — gerado a partir das retiradas do almoxarifado para a cozinha em %s. "
            "A associação por refeição usou os horários configurados no mobile. Revise ingredientes, "
            "quantidades, unidades, fatores de correção e vínculos TBCA antes de aprovar."
        ) % data
        try:
            id_ficha = salvar_ficha(
                db_path, prep["nome"], "Rascunho automático", porcoes,
                ingredientes, descricao=descricao,
            )
            with _conexao(db_path) as conn:
                atualizado = conn.execute(
                    "UPDATE GA_Preparacoes_Dia SET id_ficha=?,atualizado_em=? "
                    "WHERE id_preparacao_dia=? AND id_ficha IS NULL",
                    (id_ficha, _agora(), prep["id_preparacao_dia"]),
                ).rowcount
            if atualizado:
                relatorio["rascunhos"] += 1
            else:
                inativar_ficha(db_path, id_ficha)
        except Exception as exc:
            relatorio["erros"].append("Preparação %s: %s" % (prep.get("nome"), exc))
    return relatorio

def listar_alocacoes_retirada(db_path, data, id_movimento_mobile, incluir_revisoes=False):
    """Lista destinações de uma retirada; por padrão retorna somente a revisão ativa."""
    data = _data_iso(data, "data do movimento")
    sql = """SELECT a.*,COALESCE(p.nome,a.preparacao_nome_snapshot) AS preparacao
        FROM GA_Consumo_Alocacoes a
        LEFT JOIN GA_Preparacoes_Dia p ON p.id_preparacao_dia=a.id_preparacao_dia
        WHERE a.data_movimento=? AND a.id_movimento_mobile=?"""
    if not incluir_revisoes:
        sql += " AND a.ativa=1"
    sql += " ORDER BY a.revisao,a.id_alocacao"
    with _conexao(db_path) as conn:
        return [dict(r) for r in conn.execute(sql, (data, int(id_movimento_mobile)))]


def resumo_consumo_observado(db_path, inicio, fim):
    """Apresenta retiradas por ingrediente, pendências de destinação e médias por preparação."""
    from datetime import date
    inicio, fim = _data_iso(inicio, "data inicial"), _data_iso(fim, "data final")
    if fim < inicio:
        raise ValueError("A data final deve ser igual ou posterior à inicial.")
    dias_periodo = (date.fromisoformat(fim) - date.fromisoformat(inicio)).days + 1
    movimentos = listar_movimentos_cozinha(db_path, inicio, fim)
    por_item = {}
    for mov in movimentos:
        chave = (mov.get("id_item_mobile"), mov["item"], mov["unidade"])
        item = por_item.setdefault(chave, {
            "id_item_mobile":mov.get("id_item_mobile"),"item":mov["item"],"unidade":mov["unidade"],
            "total_retirado":0.0,"movimentos":0,"dias":set(),"custo_total":0.0,"preco_completo":True,
            "total_alocado":0.0,"total_pendente":0.0,"custo_alocado":0.0,"custo_alocado_completo":True,
            "precos_historicos":0,"precos_estimados":0
        })
        quantidade = float(mov["qtd"] or 0)
        item["total_retirado"] += quantidade
        item["movimentos"] += 1
        if quantidade > 0:
            item["dias"].add(mov["data"])
        if mov.get("custo_retirada") is None:
            item["preco_completo"] = False
        else:
            item["custo_total"] += float(mov["custo_retirada"])
        if mov.get("origem_preco") == "historico":
            item["precos_historicos"] += 1
        elif mov.get("origem_preco") == "atual_estimado":
            item["precos_estimados"] += 1
        devolvida_alocada = float(mov.get("qtd_devolvida_alocada") or 0)
        alocado_liquido = max(0.0, float(mov["qtd_alocada"] or 0) - devolvida_alocada)
        item["total_alocado"] += alocado_liquido
        item["total_pendente"] += float(mov["qtd_disponivel_para_alocar"] or 0)
        if mov.get("custos_alocados_faltantes", 0) or (
            float(mov["qtd_alocada"] or 0) > 1e-8 and mov.get("custo_alocado") is None
        ) or (devolvida_alocada > 1e-8 and mov.get("preco_unitario_snapshot") is None):
            item["custo_alocado_completo"] = False
        elif mov.get("custo_alocado") is not None:
            preco_devolvido = float(mov.get("preco_unitario_snapshot") or 0)
            item["custo_alocado"] += max(0.0, float(mov["custo_alocado"]) - devolvida_alocada * preco_devolvido)
    itens = []
    for item in por_item.values():
        dias = sorted(item["dias"])
        intervalo = ((date.fromisoformat(dias[-1])-date.fromisoformat(dias[0])).days/(len(dias)-1)) if len(dias)>1 else None
        itens.append({
            "id_item_mobile":item["id_item_mobile"],"item":item["item"],"unidade":item["unidade"],
            "total_retirado":item["total_retirado"],"movimentos":item["movimentos"],"dias_com_retirada":len(dias),
            "media_diaria_periodo":item["total_retirado"]/dias_periodo,
            "media_dia_com_retirada":item["total_retirado"]/len(dias) if dias else 0,
            "intervalo_medio_dias":intervalo,
            "custo_total":item["custo_total"] if item["preco_completo"] else None,
            "precos_historicos":item["precos_historicos"],"precos_estimados":item["precos_estimados"],
            "total_alocado":item["total_alocado"],"total_pendente":item["total_pendente"],
            "custo_alocado":item["custo_alocado"] if item["custo_alocado_completo"] else None
        })
    itens.sort(key=lambda x:x["item"].casefold())

    # Primeiro agrega cada execução da preparação; depois calcula médias entre execuções.
    execucoes = {}
    with _conexao(db_path) as conn:
        rows = conn.execute("""SELECT a.data_preparacao,a.refeicao_snapshot,a.preparacao_nome_snapshot,
                    a.id_item_mobile,a.unidade,SUM(a.quantidade) AS quantidade,
                    SUM(a.custo_snapshot) AS custo,
                    SUM(CASE WHEN a.custo_snapshot IS NULL THEN 1 ELSE 0 END) AS custos_faltantes,
                    MAX(a.porcoes_previstas_snapshot) AS porcoes_previstas,
                    COALESCE(p.nome, MAX(a.preparacao_nome_snapshot)) AS nome_item
                FROM GA_Consumo_Alocacoes a
                LEFT JOIN GA_Produtos_Almox p ON p.id_mobile=a.id_item_mobile
                WHERE a.ativa=1 AND a.tipo_destino='preparacao'
                  AND a.data_movimento BETWEEN ? AND ?
                GROUP BY a.data_preparacao,a.refeicao_snapshot,a.preparacao_nome_snapshot,a.id_item_mobile,a.unidade
                ORDER BY a.data_preparacao,a.refeicao_snapshot,a.preparacao_nome_snapshot,nome_item""",
            (inicio, fim)).fetchall()
    agregado = {}
    por_execucao = []
    for row in rows:
        r = dict(row)
        q = float(r["quantidade"] or 0)
        exec_key = (r["data_preparacao"],r["refeicao_snapshot"],r["preparacao_nome_snapshot"],
                    r["id_item_mobile"],r["unidade"])
        por_execucao.append({
            "data":r["data_preparacao"],"refeicao":r["refeicao_snapshot"],
            "preparacao":r["preparacao_nome_snapshot"],
            "id_item_mobile":r["id_item_mobile"],"item":r["nome_item"] or ("Item #%s" % r["id_item_mobile"]),
            "quantidade":q,"unidade":r["unidade"],
            "custo":None if r["custos_faltantes"] else float(r["custo"] or 0),
            "porcoes_previstas":float(r["porcoes_previstas"]) if r["porcoes_previstas"] else None
        })
        key=(r["refeicao_snapshot"],r["preparacao_nome_snapshot"],r["id_item_mobile"],r["unidade"])
        a=agregado.setdefault(key,{
            "refeicao":key[0],"preparacao":key[1],"id_item_mobile":key[2],
            "item":r["nome_item"] or ("Item #%s" % r["id_item_mobile"]),
            "unidade":key[3],"quantidade_total":0.0,"custo_total":0.0,
            "custo_completo":True,"execucoes":0,"porcoes_previstas_total":0.0,
            "porcoes_conhecidas":0,"datas":[]
        })
        a["quantidade_total"]+=q
        a["execucoes"]+=1
        a["datas"].append(r["data_preparacao"])
        if r["custos_faltantes"]:
            a["custo_completo"]=False
        else:
            a["custo_total"]+=float(r["custo"] or 0)
        if r["porcoes_previstas"] not in (None,0):
            a["porcoes_previstas_total"]+=float(r["porcoes_previstas"])
            a["porcoes_conhecidas"]+=1
    por_preparacao=[]
    for a in agregado.values():
        por_preparacao.append({
            "refeicao":a["refeicao"],"preparacao":a["preparacao"],
            "id_item_mobile":a["id_item_mobile"],"item":a["item"],"unidade":a["unidade"],
            "quantidade_total":a["quantidade_total"],"execucoes":a["execucoes"],
            "media_por_execucao":a["quantidade_total"]/a["execucoes"] if a["execucoes"] else 0,
            "porcoes_previstas_total":a["porcoes_previstas_total"] if a["porcoes_conhecidas"]==a["execucoes"] else None,
            "media_por_porcao_prevista":(a["quantidade_total"]/a["porcoes_previstas_total"])
                if a["porcoes_conhecidas"]==a["execucoes"] and a["porcoes_previstas_total"]>0 else None,
            "custo_total":a["custo_total"] if a["custo_completo"] else None,
            "datas":sorted(set(a["datas"]))
        })
    por_preparacao.sort(key=lambda x:(x["preparacao"].casefold(),x["refeicao"] or "",x["item"].casefold()))
    return {"inicio":inicio,"fim":fim,"dias_periodo":dias_periodo,"itens":itens,
            "por_preparacao":por_preparacao,"por_execucao":por_execucao,"movimentos":len(movimentos),
            "movimentos_pendentes":sum(1 for m in movimentos if m["qtd_disponivel_para_alocar"]>1e-8)}
