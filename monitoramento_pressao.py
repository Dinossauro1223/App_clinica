"""Registro de pressão arterial e comparação observacional antes/depois de troca de suplemento."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta


def criar_tabelas(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS PA_Registros (
        id_pa INTEGER PRIMARY KEY AUTOINCREMENT,
        id_paciente INTEGER NOT NULL,
        sistolica_mmhg INTEGER NOT NULL CHECK(sistolica_mmhg BETWEEN 30 AND 300),
        diastolica_mmhg INTEGER NOT NULL CHECK(diastolica_mmhg BETWEEN 20 AND 200),
        medido_em TEXT NOT NULL,
        posicao TEXT,
        braco TEXT,
        contexto TEXT,
        observacoes TEXT,
        autor TEXT,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT,
        ativo INTEGER NOT NULL DEFAULT 1 CHECK(ativo IN (0,1)),
        CHECK(sistolica_mmhg > diastolica_mmhg)
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pa_paciente_data ON PA_Registros(id_paciente, medido_em, ativo)")
    conn.execute("""CREATE TABLE IF NOT EXISTS Suplemento_Substituicoes (
        id_substituicao INTEGER PRIMARY KEY AUTOINCREMENT,
        id_paciente INTEGER NOT NULL,
        substituido_em TEXT NOT NULL,
        suplemento_anterior TEXT,
        suplemento_novo TEXT NOT NULL,
        motivo TEXT,
        autor TEXT,
        criado_em TEXT NOT NULL,
        ativo INTEGER NOT NULL DEFAULT 1 CHECK(ativo IN (0,1))
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_substituicao_paciente_data ON Suplemento_Substituicoes(id_paciente, substituido_em, ativo)")
    colunas = {r[1] for r in conn.execute("PRAGMA table_info(HGT_Registros)")}
    if "autor" not in colunas:
        conn.execute("ALTER TABLE HGT_Registros ADD COLUMN autor TEXT")


def salvar_pressao(caminho, id_paciente, sistolica, diastolica, medido_em,
                   posicao=None, braco=None, contexto=None, observacoes="", autor=None,
                   id_pa=None, agora=None):
    sistolica, diastolica = int(sistolica), int(diastolica)
    if not 30 <= sistolica <= 300 or not 20 <= diastolica <= 200 or sistolica <= diastolica:
        raise ValueError("Informe valores válidos: sistólica maior que diastólica.")
    dt = datetime.strptime(medido_em, "%Y-%m-%d %H:%M")
    carimbo = (agora or datetime.now()).isoformat(timespec="seconds")
    with sqlite3.connect(caminho) as conn:
        criar_tabelas(conn)
        if id_pa is None:
            cur = conn.execute("""INSERT INTO PA_Registros
                (id_paciente,sistolica_mmhg,diastolica_mmhg,medido_em,posicao,braco,contexto,observacoes,autor,criado_em)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (int(id_paciente),sistolica,diastolica,dt.strftime("%Y-%m-%d %H:%M:00"),
                 posicao,braco,contexto,(observacoes or "").strip(),autor,carimbo))
            return cur.lastrowid
        cur = conn.execute("""UPDATE PA_Registros SET sistolica_mmhg=?,diastolica_mmhg=?,medido_em=?,
            posicao=?,braco=?,contexto=?,observacoes=?,autor=?,atualizado_em=?
            WHERE id_pa=? AND id_paciente=? AND ativo=1""",
            (sistolica,diastolica,dt.strftime("%Y-%m-%d %H:%M:00"),posicao,braco,contexto,
             (observacoes or "").strip(),autor,carimbo,int(id_pa),int(id_paciente)))
        if cur.rowcount != 1:
            raise LookupError("Aferição não encontrada ou inativada.")
        return int(id_pa)


def listar_pressao(caminho, id_paciente, inicio=None, fim=None):
    sql = """SELECT id_pa,sistolica_mmhg,diastolica_mmhg,medido_em,posicao,braco,contexto,observacoes,autor
             FROM PA_Registros WHERE id_paciente=? AND ativo=1"""
    args = [int(id_paciente)]
    if inicio:
        sql += " AND medido_em>=?"; args.append(inicio)
    if fim:
        sql += " AND medido_em<=?"; args.append(fim)
    sql += " ORDER BY medido_em,id_pa"
    with sqlite3.connect(caminho) as conn:
        criar_tabelas(conn)
        return conn.execute(sql,args).fetchall()


def inativar_pressao(caminho, id_paciente, id_pa, agora=None):
    with sqlite3.connect(caminho) as conn:
        criar_tabelas(conn)
        cur=conn.execute("UPDATE PA_Registros SET ativo=0,atualizado_em=? WHERE id_pa=? AND id_paciente=? AND ativo=1",
                         ((agora or datetime.now()).isoformat(timespec="seconds"),int(id_pa),int(id_paciente)))
        return cur.rowcount == 1


def registrar_substituicao(caminho,id_paciente,substituido_em,suplemento_anterior,suplemento_novo,
                           motivo="",autor=None,agora=None):
    dt=datetime.strptime(substituido_em,"%Y-%m-%d %H:%M")
    novo=(suplemento_novo or "").strip()
    if not novo:
        raise ValueError("Informe o suplemento novo.")
    carimbo=(agora or datetime.now()).isoformat(timespec="seconds")
    with sqlite3.connect(caminho) as conn:
        criar_tabelas(conn)
        cur=conn.execute("""INSERT INTO Suplemento_Substituicoes
            (id_paciente,substituido_em,suplemento_anterior,suplemento_novo,motivo,autor,criado_em)
            VALUES (?,?,?,?,?,?,?)""",
            (int(id_paciente),dt.strftime("%Y-%m-%d %H:%M:00"),(suplemento_anterior or "").strip() or None,
             novo,(motivo or "").strip() or None,autor,carimbo))
        return cur.lastrowid


def _resumo(valores, chave):
    dias=sorted({v[0][:10] for v in valores})
    nums=[float(v[1]) for v in valores if v[1] is not None]
    return {"media": sum(nums)/len(nums) if nums else None,
            "afericoes":len(nums),"dias_com_dados":len(dias),"dias_cobertos":dias}


def comparar_tres_dias(caminho,id_paciente,substituido_em):
    """Compara janelas [troca-3d,troca) e [troca,troca+3d), sem incluir a hora da troca no período anterior."""
    troca=datetime.strptime(substituido_em,"%Y-%m-%d %H:%M")
    ini_antes=(troca-timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    fim_antes=troca.strftime("%Y-%m-%d %H:%M:%S")
    fim_depois=(troca+timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(caminho) as conn:
        criar_tabelas(conn)
        hgt_antes=conn.execute("""SELECT medido_em,valor_mg_dl FROM HGT_Registros
            WHERE id_paciente=? AND ativo=1 AND medido_em>=? AND medido_em<? ORDER BY medido_em""",
            (int(id_paciente),ini_antes,fim_antes)).fetchall()
        hgt_depois=conn.execute("""SELECT medido_em,valor_mg_dl FROM HGT_Registros
            WHERE id_paciente=? AND ativo=1 AND medido_em>=? AND medido_em<? ORDER BY medido_em""",
            (int(id_paciente),fim_antes,fim_depois)).fetchall()
        pa_antes=conn.execute("""SELECT medido_em,sistolica_mmhg,diastolica_mmhg FROM PA_Registros
            WHERE id_paciente=? AND ativo=1 AND medido_em>=? AND medido_em<? ORDER BY medido_em""",
            (int(id_paciente),ini_antes,fim_antes)).fetchall()
        pa_depois=conn.execute("""SELECT medido_em,sistolica_mmhg,diastolica_mmhg FROM PA_Registros
            WHERE id_paciente=? AND ativo=1 AND medido_em>=? AND medido_em<? ORDER BY medido_em""",
            (int(id_paciente),fim_antes,fim_depois)).fetchall()
    def resumo_pa(rows,idx):
        return _resumo([(r[0],r[idx]) for r in rows],"valor")
    return {
        "periodo_antes":{"inicio":ini_antes,"fim_exclusivo":fim_antes,
            "hgt":_resumo(hgt_antes,"valor"),"sistolica":resumo_pa(pa_antes,1),"diastolica":resumo_pa(pa_antes,2)},
        "periodo_depois":{"inicio":fim_antes,"fim_exclusivo":fim_depois,
            "hgt":_resumo(hgt_depois,"valor"),"sistolica":resumo_pa(pa_depois,1),"diastolica":resumo_pa(pa_depois,2)}
    }
