# -*- coding: utf-8 -*-
"""NRS 2002 conforme o manual Avante/Nestlé Health Science e agenda de reavaliação.

Triagem inicial com 4 perguntas; havendo ao menos um "sim", etapa 2 = estado
nutricional (0 a 3) + gravidade da doença (0 a 3) + 1 ponto se idade >= 70.
Escore < 3: sem risco; >= 3: risco; >= 5: alto risco. Intervalos são configuráveis.
"""
import json
from datetime import date, timedelta

PERGUNTAS = (
    ("imc", "IMC < 20,5 kg/m²?"),
    ("perda", "Perdeu peso nos últimos 3 meses?"),
    ("ingestao", "Ingestão alimentar reduzida na última semana?"),
    ("grave", "Paciente gravemente doente?"),
)
ESTADO = {0: "0 — Normal", 1: "1 — Leve", 2: "2 — Moderado", 3: "3 — Grave"}
ESTADO_DICA = ("Estado nutricional (0 a 3 pontos)\n0: normal.\n1 (leve): perda de peso > 5% em 3 meses ou ingestão de 50 a 75% das "
               "necessidades na última semana.\n2 (moderado): perda > 5% em 2 meses, ou IMC 18,5 a 20,5 + condição geral "
               "prejudicada, ou ingestão de 25 a 50%.\n3 (grave): perda > 5% em 1 mês (> 15% em 3 meses), ou IMC < 18,5 + "
               "condição geral prejudicada, ou ingestão de 0 a 25%.")
GRAVIDADE = {0: "0 — Normal", 1: "1 — Leve", 2: "2 — Moderada", 3: "3 — Grave"}
GRAVIDADE_DICA = ("Gravidade da doença (0 a 3 pontos)\n0: necessidades nutricionais normais.\n1 (leve): fratura de quadril, "
                  "hemodiálise crônica, diabetes, câncer, cirrose ou DPOC com complicações agudas, paciente fraco que deambula."
                  "\n2 (moderada): cirurgia abdominal de grande porte, AVC, pneumonia grave, doença hematológica maligna, "
                  "paciente confinado ao leito.\n3 (grave): trauma craniano, transplante de medula óssea, paciente em terapia "
                  "intensiva (APACHE > 10).")
GRAUS = (
    ("triagem_negativa", "Triagem inicial negativa (4 respostas 'não')"),
    ("sem_risco", "Sem risco nutricional (escore < 3)"),
    ("risco", "Risco nutricional (escore 3 a 4)"),
    ("alto_risco", "Alto risco nutricional (escore >= 5)"),
)
ROTULO = dict(GRAUS)
DIAS_PADRAO = {codigo: 7 for codigo, _ in GRAUS}
LIMITE_RDC63 = 10
CHAVE_CONFIG = "nrs_dias_reavaliacao"

def classificar(respostas, estado=None, gravidade=None, idade=None):
    """Retorna completo, etapa, escore, grau e rótulo a partir das respostas."""
    valores = [respostas.get(c) for c, _ in PERGUNTAS]
    if any(v is not None and type(v) is not bool for v in valores):
        raise ValueError("Respostas da triagem devem ser True, False ou None.")
    if not any(v is True for v in valores):
        if any(v is None for v in valores):
            return {"completo": False, "etapa": 1, "escore": None, "grau": None,
                    "rotulo": "Responda as 4 perguntas da triagem inicial"}
        return {"completo": True, "etapa": 1, "escore": None, "grau": "triagem_negativa",
                "rotulo": ROTULO["triagem_negativa"]}
    if estado is None or gravidade is None:
        return {"completo": False, "etapa": 2, "escore": None, "grau": None,
                "rotulo": "Informe o estado nutricional e a gravidade da doença"}
    for nome, valor in (("estado", estado), ("gravidade", gravidade)):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor not in range(4):
            raise ValueError(f"{nome} deve ser um inteiro entre 0 e 3.")
    if idade is not None and (isinstance(idade, bool) or not isinstance(idade, (int, float)) or idade < 0):
        raise ValueError("Idade deve ser um número não negativo.")
    total = estado + gravidade + (1 if idade is not None and idade >= 70 else 0)
    grau = "sem_risco" if total < 3 else "risco" if total < 5 else "alto_risco"
    return {"completo": True, "etapa": 2, "escore": total, "grau": grau,
            "rotulo": f"{total} pontos — {ROTULO[grau]}"}

def dias_para(grau, intervalos=None):
    if grau not in DIAS_PADRAO:
        raise ValueError("Grau NRS-2002 desconhecido.")
    return max(1, int((intervalos or {}).get(grau, DIAS_PADRAO[grau])))

def proxima_reavaliacao(base, grau, intervalos=None):
    if not isinstance(base, date):
        raise TypeError("base deve ser date.")
    return base + timedelta(days=dias_para(grau, intervalos))

def ler_intervalos(db_path):
    import mapa_db as mdb
    mdb.inicializar(db_path)
    try:
        salvos = json.loads(mdb.obter_config(db_path, CHAVE_CONFIG, "{}") or "{}")
    except (ValueError, TypeError):
        salvos = {}
    return {c: (int(salvos[c]) if isinstance(salvos.get(c), (int, float)) and salvos[c] >= 1
                 else DIAS_PADRAO[c]) for c, _ in GRAUS}

def salvar_intervalos(db_path, dias):
    import mapa_db as mdb
    mdb.inicializar(db_path)
    limpo = {}
    for codigo, _ in GRAUS:
        valor = int(dias[codigo])
        if not 1 <= valor <= 90:
            raise ValueError("Use de 1 a 90 dias.")
        limpo[codigo] = valor
    mdb.salvar_config(db_path, CHAVE_CONFIG, json.dumps(limpo))
    return limpo
