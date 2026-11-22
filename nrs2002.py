# -*- coding: utf-8 -*-
"""NRS-2002: cálculo puro para triagem nutricional (interface e persistência ficam em módulos separados).

O escore segue o modelo de duas etapas: triagem inicial e, se positiva, pontuação
do estado nutricional + gravidade da doença + ponto de idade >= 70 anos.
Requer revisão do protocolo institucional antes de uso clínico.
"""
from datetime import date, timedelta

PERGUNTAS = (
    ("imc", "IMC < 20,5 kg/m²?"),
    ("perda", "Perda de peso nos últimos 3 meses?"),
    ("ingestao", "Ingestão alimentar reduzida na última semana?"),
    ("grave", "Paciente gravemente doente?"),
)
GRAUS = (
    ("triagem_negativa", "Triagem inicial negativa"),
    ("sem_risco", "Sem risco nutricional (escore < 3)"),
    ("risco", "Risco nutricional (escore 3 a 4)"),
    ("alto_risco", "Alto risco nutricional (escore >= 5)"),
)
DIAS_PADRAO = {codigo: 7 for codigo, _ in GRAUS}
LIMITE_RDC63 = 10

def classificar(respostas, estado=None, gravidade=None, idade=None):
    """Avalia respostas e retorna dicionário de estado, escore e classificação."""
    valores = [respostas.get(chave) for chave, _ in PERGUNTAS]
    if any(v is not None and type(v) is not bool for v in valores):
        raise ValueError("Respostas da triagem devem ser True, False ou None.")
    if any(v is None for v in valores):
        return {"completo": False, "etapa": 1, "escore": None, "grau": None,
                "rotulo": "Responda as 4 perguntas da triagem inicial"}
    if not any(valores):
        return {"completo": True, "etapa": 1, "escore": None,
                "grau": "triagem_negativa", "rotulo": GRAUS[0][1]}
    if estado is None or gravidade is None:
        return {"completo": False, "etapa": 2, "escore": None, "grau": None,
                "rotulo": "Informe estado nutricional e gravidade da doença"}
    for nome, valor in (("estado", estado), ("gravidade", gravidade)):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor not in range(4):
            raise ValueError(f"{nome} deve ser um inteiro entre 0 e 3.")
    if idade is not None and (isinstance(idade, bool) or not isinstance(idade, (int, float)) or idade < 0):
        raise ValueError("Idade deve ser um número não negativo.")
    escore = estado + gravidade + (1 if idade is not None and idade >= 70 else 0)
    grau = "sem_risco" if escore < 3 else "risco" if escore < 5 else "alto_risco"
    rotulos = dict(GRAUS)
    return {"completo": True, "etapa": 2, "escore": escore, "grau": grau,
            "rotulo": f"{escore} pontos — {rotulos[grau]}"}

def dias_para(grau, intervalos=None):
    """Intervalo de reavaliação em dias; o padrão do pacote é 7 dias."""
    if grau not in DIAS_PADRAO:
        raise ValueError("Grau de risco desconhecido.")
    valor = (intervalos or {}).get(grau, DIAS_PADRAO[grau])
    return max(1, int(valor))

def proxima_reavaliacao(base, grau, intervalos=None):
    """Calcula data-alvo a partir de uma data de avaliação."""
    if not isinstance(base, date):
        raise TypeError("base deve ser uma data.")
    return base + timedelta(days=dias_para(grau, intervalos))
