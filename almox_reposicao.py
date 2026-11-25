# -*- coding: utf-8 -*-
"""Pedidos de reposição do almoxarifado desktop e prazo médio real."""
from contextlib import closing
from decimal import Decimal
import sqlite3
import almox_db as adb

DDL = """
CREATE TABLE IF NOT EXISTS Almox_Pedidos_Reposicao(
 id_pedido INTEGER PRIMARY KEY AUTOINCREMENT,
 id_item INTEGER NOT NULL,
 quantidade REAL NOT NULL CHECK(quantidade > 0),
 solicitado_em TEXT NOT NULL,
 solicitado_por TEXT,
 fornecedor TEXT,
 observacao TEXT,
 status TEXT NOT NULL DEFAULT 'pendente'
   CHECK(status IN ('pendente','recebido','cancelado')),
 recebido_em TEXT,
 recebido_por TEXT,
 id_movimento INTEGER UNIQUE
);
CREATE INDEX IF NOT EXISTS ix_almox_pedido_item_data
 ON Almox_Pedidos_Reposicao(id_item, solicitado_em);
"""

def inicializar(db):
    with closing(adb.conectar(db)) as c:
        c.executescript(DDL)
        c.commit()

def solicitar(db, id_item, quantidade, *, solicitado_por=None, fornecedor=None, observacao=None, quando=None):
    qtd = adb._d(quantidade, "quantidade solicitada", True, Decimal("0.0000001"))
    data = adb._data(quando or adb.hoje())
    nome = str(solicitado_por or "").strip() or None
    with closing(adb.conectar(db)) as c:
        c.execute("BEGIN IMMEDIATE")
        try:
            item = c.execute("SELECT id_item FROM Almox_Itens WHERE id_item=? AND ativo=1", (int(id_item),)).fetchone()
            if not item:
                raise ValueError("Item não encontrado ou inativo.")
            cur = c.execute(
                """INSERT INTO Almox_Pedidos_Reposicao
                   (id_item,quantidade,solicitado_em,solicitado_por,fornecedor,observacao,status)
                   VALUES(?,?,?,?,?,?,'pendente')""",
                (int(id_item), float(qtd), data, nome,
                 str(fornecedor or "").strip() or None,
                 str(observacao or "").strip() or None))
            c.commit()
            return int(cur.lastrowid)
        except Exception:
            c.rollback()
            raise

def receber(db, id_pedido, *, recebido_por=None, quando=None, valor_unitario=None):
    data = adb._data(quando or adb.hoje())
    nome = str(recebido_por or "").strip() or None
    with closing(adb.conectar(db)) as c:
        c.execute("BEGIN IMMEDIATE")
        try:
            pedido = c.execute(
                "SELECT p.*,i.valor_unitario FROM Almox_Pedidos_Reposicao p "
                "JOIN Almox_Itens i ON i.id_item=p.id_item WHERE p.id_pedido=?",
                (int(id_pedido),)).fetchone()
            if not pedido:
                raise ValueError("Pedido de reposição não encontrado.")
            if pedido["status"] != "pendente":
                raise ValueError("Este pedido já foi finalizado.")
            if data < pedido["solicitado_em"]:
                raise ValueError("A data de recebimento não pode anteceder a solicitação.")
            if pedido["valor_unitario"] is None and valor_unitario in (None, ""):
                raise ValueError("Informe o valor unitário da compra para registrar a entrada.")
            preco = adb._d(valor_unitario if valor_unitario not in (None, "") else pedido["valor_unitario"],
                           "valor unitário recebido", True, 0)
            saldo = Decimal(str(adb._saldo(c, int(pedido["id_item"]))))
            anterior = adb._d(pedido["valor_unitario"], "valor atual", minimo=0)
            media = ((saldo * anterior) + (Decimal(str(pedido["quantidade"])) * preco)) / (saldo + Decimal(str(pedido["quantidade"]))) if saldo > 0 and anterior is not None else preco
            c.execute("UPDATE Almox_Itens SET valor_unitario=?,atualizado_em=? WHERE id_item=?",
                      (float(media), adb.agora(), int(pedido["id_item"])))
            c.execute("INSERT INTO Almox_Historico_Preco(id_item,valor_unitario,origem,fonte,registrado_em) VALUES(?,?,?,?,?)",
                      (int(pedido["id_item"]), float(media), "compra", "Pedido de reposição #%s" % id_pedido, adb.agora()))
            mid = adb._insert_mov(c, data, int(pedido["id_item"]), "entrada", "compra",
                                  Decimal(str(pedido["quantidade"])), preco,
                                  obs=("Recebimento do pedido #%s. %s" %
                                       (id_pedido, pedido["observacao"] or "")).strip(),
                                  usuario=nome, origem="pedido_reposicao")
            cur = c.execute(
                """UPDATE Almox_Pedidos_Reposicao
                   SET status='recebido',recebido_em=?,recebido_por=?,id_movimento=?
                   WHERE id_pedido=? AND status='pendente'""",
                (data, nome, mid, int(id_pedido)))
            if cur.rowcount != 1:
                raise ValueError("Não foi possível finalizar o pedido.")
            c.commit()
            return mid
        except Exception:
            c.rollback()
            raise

def cancelar(db, id_pedido):
    with closing(adb.conectar(db)) as c:
        cur = c.execute(
            "UPDATE Almox_Pedidos_Reposicao SET status='cancelado' "
            "WHERE id_pedido=? AND status='pendente'", (int(id_pedido),))
        if cur.rowcount != 1:
            raise ValueError("Somente pedidos pendentes podem ser cancelados.")
        c.commit()

def listar(db, id_item=None, status=None):
    sql = """SELECT p.*,i.nome AS item,i.unidade,m.data AS data_movimento
             FROM Almox_Pedidos_Reposicao p
             JOIN Almox_Itens i ON i.id_item=p.id_item
             LEFT JOIN Almox_Movimentos m ON m.id_movimento=p.id_movimento
             WHERE 1=1"""
    args = []
    if id_item is not None:
        sql += " AND p.id_item=?"; args.append(int(id_item))
    if status:
        if status not in ("pendente", "recebido", "cancelado"):
            raise ValueError("Status de pedido inválido.")
        sql += " AND p.status=?"; args.append(status)
    sql += " ORDER BY CASE p.status WHEN 'pendente' THEN 0 ELSE 1 END,p.solicitado_em DESC,p.id_pedido DESC"
    with closing(adb.conectar(db)) as c:
        return [dict(r) for r in c.execute(sql, args)]

def prazos_medios(db):
    sql = """SELECT i.id_item,i.nome,i.unidade,
                    COUNT(p.id_pedido) AS pedidos_recebidos,
                    ROUND(AVG(julianday(p.recebido_em)-julianday(p.solicitado_em)),1) AS prazo_medio_dias,
                    MIN(julianday(p.recebido_em)-julianday(p.solicitado_em)) AS menor_prazo_dias,
                    MAX(julianday(p.recebido_em)-julianday(p.solicitado_em)) AS maior_prazo_dias,
                    (SELECT COUNT(*) FROM Almox_Pedidos_Reposicao x
                     WHERE x.id_item=i.id_item AND x.status='pendente') AS pedidos_pendentes
             FROM Almox_Itens i
             LEFT JOIN Almox_Pedidos_Reposicao p
               ON p.id_item=i.id_item AND p.status='recebido'
             GROUP BY i.id_item,i.nome,i.unidade
             HAVING COUNT(p.id_pedido)>0 OR pedidos_pendentes>0
             ORDER BY prazo_medio_dias DESC,i.nome COLLATE NOCASE"""
    with closing(adb.conectar(db)) as c:
        return [dict(r) for r in c.execute(sql)]
