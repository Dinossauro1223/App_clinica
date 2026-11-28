# -*- coding: utf-8 -*-
"""Registro factual da administração de dieta enteral.

Os eventos são fatos de administração, não estimativas de oferta. Horário, volume,
taxa e pausas devem ser informados pelo usuário/equipamento. O módulo não altera
prescrição nem infere velocidade ou fator de gotejamento.
"""
from __future__ import annotations

import math
import sqlite3
from contextlib import closing
from datetime import datetime


def criar_tabela(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Enteral_Administracoes (
            id_administracao INTEGER PRIMARY KEY AUTOINCREMENT,
            id_paciente INTEGER NOT NULL,
            id_registro_mapa INTEGER,
            inicio_em TEXT NOT NULL,
            fim_em TEXT,
            volume_prescrito_ml REAL,
            volume_administrado_ml REAL,
            taxa_ml_h REAL,
            pausado_min REAL DEFAULT 0,
            via_administracao TEXT NOT NULL CHECK(via_administracao IN ('bomba','gravitacional','manual')),
            fator_gotas_ml REAL,
            observacoes TEXT,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_enteral_adm_paciente_tempo
        ON Enteral_Administracoes(id_paciente, inicio_em, fim_em)
    """)


def _dt(valor, campo):
    try:
        return datetime.fromisoformat(str(valor))
    except (TypeError, ValueError):
        raise ValueError(f"Informe {campo} em data e hora válidas (AAAA-MM-DD HH:MM).") from None


def _num(valor, campo, minimo=0):
    if valor in (None, ""):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ValueError(f"{campo} inválido.") from None
    if not math.isfinite(numero) or numero < minimo:
        raise ValueError(f"{campo} inválido.")
    return numero


def salvar_administracao(caminho, id_paciente, inicio_em, fim_em=None, *,
                         volume_prescrito_ml=None, volume_administrado_ml=None,
                         taxa_ml_h=None, pausado_min=0, via_administracao="bomba",
                         fator_gotas_ml=None, observacoes="", id_registro_mapa=None,
                         agora=None, id_administracao=None):
    inicio = _dt(inicio_em, "o início")
    fim = _dt(fim_em, "o fim") if fim_em not in (None, "") else None
    if fim and fim < inicio:
        raise ValueError("O fim da administração não pode ser anterior ao início.")
    if via_administracao not in ("bomba", "gravitacional", "manual"):
        raise ValueError("Via de administração enteral inválida.")
    prescrito = _num(volume_prescrito_ml, "Volume prescrito", 0)
    administrado = _num(volume_administrado_ml, "Volume administrado", 0)
    taxa = _num(taxa_ml_h, "Taxa (mL/h)", 0)
    pausa = _num(pausado_min, "Tempo de pausa (min)", 0)
    fator = _num(fator_gotas_ml, "Fator de gotas (mL/gota)", 0)
    if via_administracao == "gravitacional" and fator is not None and fator <= 0:
        raise ValueError("O fator de gotas deve ser maior que zero.")
    carimbo = (agora or datetime.now()).isoformat(timespec="seconds")
    with closing(sqlite3.connect(caminho)) as conn, conn:
        criar_tabela(conn)
        dados = (
            int(id_paciente), id_registro_mapa,
            inicio.strftime("%Y-%m-%d %H:%M:00"),
            fim.strftime("%Y-%m-%d %H:%M:00") if fim else None,
            prescrito, administrado, taxa, pausa, via_administracao, fator,
            str(observacoes or "").strip()
        )
        if id_administracao is None:
            cur = conn.execute("""
                INSERT INTO Enteral_Administracoes(
                    id_paciente,id_registro_mapa,inicio_em,fim_em,volume_prescrito_ml,
                    volume_administrado_ml,taxa_ml_h,pausado_min,via_administracao,
                    fator_gotas_ml,observacoes,criado_em
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """, dados + (carimbo,))
            return cur.lastrowid
        cur = conn.execute("""
            UPDATE Enteral_Administracoes SET inicio_em=?,fim_em=?,
                volume_prescrito_ml=?,volume_administrado_ml=?,taxa_ml_h=?,
                pausado_min=?,via_administracao=?,fator_gotas_ml=?,
                observacoes=?,atualizado_em=?
            WHERE id_administracao=? AND id_paciente=?
        """, (
            dados[2],dados[3],dados[4],dados[5],dados[6],dados[7],
            dados[8],dados[9],dados[10],carimbo,int(id_administracao),int(id_paciente)
        ))
        if cur.rowcount != 1:
            raise LookupError("Administração enteral não encontrada.")
        return int(id_administracao)


def listar_administracoes(caminho, id_paciente, inicio=None, fim=None):
    sql = "SELECT * FROM Enteral_Administracoes WHERE id_paciente=?"
    args = [int(id_paciente)]
    if inicio:
        sql += " AND (fim_em IS NULL OR fim_em >= ?)"; args.append(str(inicio))
    if fim:
        sql += " AND inicio_em <= ?"; args.append(str(fim))
    sql += " ORDER BY inicio_em,id_administracao"
    with closing(sqlite3.connect(caminho)) as conn, conn:
        conn.row_factory = sqlite3.Row
        criar_tabela(conn)
        return [dict(r) for r in conn.execute(sql,args)]


def classificar_hgt_em_relacao_a_administracao(medido_em, administracao,
                                                janela_antes_min=30,
                                                janela_depois_min=120):
    """Classifica temporalmente uma aferição sem inferir efeito fisiológico."""
    medido = _dt(medido_em, "o HGT")
    inicio = _dt(administracao["inicio_em"], "o início da administração")
    fim = _dt(administracao["fim_em"], "o fim da administração") if administracao.get("fim_em") else None
    try:
        antes = float(janela_antes_min); depois = float(janela_depois_min)
    except (TypeError, ValueError):
        raise ValueError("Janelas temporais inválidas.") from None
    if antes < 0 or depois < 0:
        raise ValueError("As janelas temporais não podem ser negativas.")
    if fim and inicio <= medido <= fim:
        return {"classificacao":"durante","minutos_desde_inicio":int((medido-inicio).total_seconds()/60)}
    delta_inicio = (medido-inicio).total_seconds()/60
    if -antes <= delta_inicio < 0:
        return {"classificacao":"antes","minutos_desde_inicio":int(delta_inicio)}
    if fim:
        delta_fim = (medido-fim).total_seconds()/60
        if 0 <= delta_fim <= depois:
            return {"classificacao":"apos_fim","minutos_desde_fim":int(delta_fim)}
    else:
        if 0 <= delta_inicio <= depois:
            return {"classificacao":"apos_inicio","minutos_desde_inicio":int(delta_inicio)}
    return {"classificacao":"fora_janela","minutos_desde_inicio":int(delta_inicio)}


def gotas_por_minuto(taxa_ml_h, fator_gotas_ml):
    """Calcula gotas/min apenas quando taxa e fator do equipo foram informados."""
    taxa = _num(taxa_ml_h, "Taxa", 0)
    fator = _num(fator_gotas_ml, "Fator de gotas", 0)
    if taxa is None or fator is None or fator <= 0:
        return None
    return taxa / 60.0 / fator



def resumir_administracoes_dia(caminho, id_paciente, data):
    """Resume eventos enterais que intersectam o dia solicitado.

    Inclui administrações iniciadas antes da data e ainda sem término, para que
    permaneçam visíveis como pendentes no resumo atual. Eventos abertos, sem volume
    real ou que atravessam a meia-noite não têm o volume rateado automaticamente:
    são retornados para revisão manual, sem inventar a parcela diária.
    """
    try:
        dia = datetime.strptime(str(data), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError("Data inválida; use AAAA-MM-DD.") from None
    inicio = f"{dia.isoformat()} 00:00:00"
    fim = f"{dia.isoformat()} 23:59:59"
    eventos = listar_administracoes(caminho, id_paciente, inicio, fim)
    completos, pendentes = [], []
    for evento in eventos:
        inicio_evento = _dt(evento.get("inicio_em"), "o início da administração")
        fim_evento = _dt(evento.get("fim_em"), "o fim da administração") if evento.get("fim_em") else None
        if fim_evento is None or inicio_evento.date() != dia or fim_evento.date() != dia:
            pendentes.append(evento)
            continue
        if evento.get("volume_administrado_ml") in (None, ""):
            pendentes.append(evento)
            continue
        completos.append(evento)
    total_volume = sum(float(e["volume_administrado_ml"]) for e in completos)
    total_prescrito = sum(float(e["volume_prescrito_ml"]) for e in completos if e.get("volume_prescrito_ml") not in (None, ""))
    return {
        "data": dia.isoformat(),
        "administracoes_completas": completos,
        "administracoes_pendentes": pendentes,
        "volume_administrado_ml": total_volume,
        "volume_prescrito_ml": total_prescrito,
        "cobertura_volume_pct": (total_volume / total_prescrito * 100) if total_prescrito > 0 else None,
        "volume_calculavel": bool(completos) and not pendentes,
    }
