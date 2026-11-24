# -*- coding: utf-8 -*-
"""Núcleo isolado de avaliação antropométrica pediátrica pelas referências OMS.

As tabelas numéricas oficiais são carregadas externamente; nenhum parâmetro LMS
é presumido ou sintetizado neste módulo. Funções puras para facilitar testes.
"""
import csv
import math
from datetime import date
from pathlib import Path


_FAIXAS = {
    "imc_idade": ((0, 60, "oms_2006"), (61, 228, "oms_2007")),
    "peso_idade": ((0, 60, "oms_2006"), (61, 120, "oms_2007")),
    "estatura_idade": ((0, 60, "oms_2006"), (61, 228, "oms_2007")),
}


def calcular_escore_z(valor, l, m, s):
    """Calcula escore-z LMS clássico; entradas inválidas geram ValueError."""
    try:
        x, l_, m_, s_ = (float(v) for v in (valor, l, m, s))
    except (TypeError, ValueError):
        raise ValueError("Valor e parâmetros LMS devem ser numéricos.")
    if not all(math.isfinite(v) for v in (x, l_, m_, s_)):
        raise ValueError("Valor e parâmetros LMS devem ser finitos.")
    if x <= 0 or m_ <= 0 or s_ <= 0:
        raise ValueError("Valor observado, M e S devem ser maiores que zero.")
    if l_ == 0:
        return math.log(x / m_) / s_
    return (((x / m_) ** l_) - 1.0) / (l_ * s_)


def calcular_idade_meses(nascimento, referencia):
    """Retorna meses completos entre datas ISO (AAAA-MM-DD)."""
    try:
        nasc = date.fromisoformat(str(nascimento))
        ref = date.fromisoformat(str(referencia))
    except (TypeError, ValueError):
        raise ValueError("Informe datas válidas no formato AAAA-MM-DD.")
    if ref < nasc:
        raise ValueError("A data de referência não pode anteceder o nascimento.")
    meses = (ref.year - nasc.year) * 12 + ref.month - nasc.month
    if ref.day < nasc.day:
        meses -= 1
    return meses


def _referencia_para(indicador, idade_meses):
    if indicador not in _FAIXAS:
        raise ValueError("Indicador antropométrico desconhecido.")
    for minimo, maximo, referencia in _FAIXAS[indicador]:
        if minimo <= idade_meses <= maximo:
            return referencia
    raise ValueError("Idade fora da faixa coberta pelo indicador OMS.")


def classificar_escore_z(indicador, zscore, idade_meses):
    """Classifica um escore-z conforme indicador e faixa OMS 2006/2007."""
    if isinstance(idade_meses, bool) or not isinstance(idade_meses, int) or idade_meses < 0:
        raise ValueError("Idade deve ser informada em meses completos.")
    referencia = _referencia_para(indicador, idade_meses)
    try:
        z = float(zscore)
    except (TypeError, ValueError):
        raise ValueError("Escore-z inválido.")
    if not math.isfinite(z):
        raise ValueError("Escore-z deve ser finito.")

    if indicador == "imc_idade":
        if z < -3:
            return "Magreza acentuada"
        if z < -2:
            return "Magreza"
        if z <= 1:
            return "Eutrofia"
        if referencia == "oms_2006":
            if z <= 2:
                return "Risco de sobrepeso"
            if z <= 3:
                return "Sobrepeso"
            return "Obesidade"
        if z <= 2:
            return "Sobrepeso"
        return "Obesidade"

    if indicador == "peso_idade":
        if z < -3:
            return "Peso muito baixo para idade"
        if z < -2:
            return "Peso baixo para idade"
        return "Peso adequado para idade"

    if indicador == "estatura_idade":
        if z < -3:
            return "Estatura muito baixa para idade"
        if z < -2:
            return "Estatura baixa para idade"
        return "Estatura adequada para idade"

    raise ValueError("Indicador antropométrico desconhecido.")


class TabelaReferenciaOMS:
    """Tabela LMS indexada por indicador, referência, sexo e idade em meses.

    CSV: indicador,referencia,sexo,idade_meses,L,M,S.
    Sexo interno: H (masculino) ou M (feminino). Não há interpolação nem
    extrapolação: ausência de uma linha exata significa resultado indisponível.
    """

    def __init__(self, linhas):
        self._dados = {}
        for linha in linhas:
            indicador = str(linha["indicador"]).strip().lower()
            referencia = str(linha["referencia"]).strip().lower()
            sexo = str(linha["sexo"]).strip().upper()
            if sexo not in ("H", "M"):
                raise ValueError("Sexo LMS deve ser H (masculino) ou M (feminino).")
            idade = int(float(linha["idade_meses"]))
            if idade < 0:
                raise ValueError("Idade LMS não pode ser negativa.")
            try:
                l_, m_, s_ = (float(linha[k]) for k in ("L", "M", "S"))
            except (TypeError, ValueError, KeyError):
                raise ValueError("Linha LMS incompleta ou não numérica.")
            if not all(math.isfinite(v) for v in (l_, m_, s_)) or m_ <= 0 or s_ <= 0:
                raise ValueError("Parâmetros LMS inválidos.")
            chave = (indicador, referencia, sexo, idade)
            if chave in self._dados:
                raise ValueError("Linha LMS duplicada: " + repr(chave))
            self._dados[chave] = (l_, m_, s_)

    @classmethod
    def de_linhas(cls, linhas):
        return cls(linhas)

    @classmethod
    def de_csv(cls, caminho):
        with open(caminho, newline="", encoding="utf-8-sig") as arquivo:
            amostra = arquivo.read(4096)
            arquivo.seek(0)
            delimitador = ";" if amostra.count(";") > amostra.count(",") else ","
            leitor = csv.DictReader(arquivo, delimiter=delimitador)
            obrigatorias = {"indicador", "referencia", "sexo", "idade_meses", "L", "M", "S"}
            if not leitor.fieldnames or not obrigatorias.issubset(
                    {c.strip() for c in leitor.fieldnames}):
                raise ValueError("CSV deve conter indicador, referencia, sexo, idade_meses, L, M e S.")
            return cls(leitor)

    def calcular(self, indicador, sexo, idade_meses, valor):
        """Calcula escore-z ou retorna None quando não existe linha oficial exata."""
        if isinstance(idade_meses, bool) or not isinstance(idade_meses, int):
            raise ValueError("Idade deve ser informada em meses completos.")
        referencia = _referencia_para(indicador, idade_meses)
        sexo = str(sexo or "").strip().upper()
        if sexo not in ("H", "M"):
            return None
        parametros = self._dados.get((indicador, referencia, sexo, idade_meses))
        if parametros is None:
            return None
        return calcular_escore_z(valor, *parametros)


def avaliar_indicador(indicador, valor, sexo, idade_meses, tabela):
    """Retorna estado explícito, escore-z e classe; nunca presume dado ausente."""
    try:
        referencia = _referencia_para(indicador, idade_meses)
    except ValueError as exc:
        return {"status": "fora_faixa", "referencia": None,
                "escore_z": None, "classificacao": None, "aviso": str(exc)}
    if valor is None or sexo not in ("H", "M") or tabela is None:
        return {"status": "pendente", "referencia": referencia,
                "escore_z": None, "classificacao": None,
                "aviso": "Medida, sexo ou tabela LMS oficial indisponível."}
    z = tabela.calcular(indicador, sexo, idade_meses, valor)
    if z is None:
        return {"status": "pendente", "referencia": referencia,
                "escore_z": None, "classificacao": None,
                "aviso": "Não existe parâmetro LMS oficial para esta combinação."}
    classe = classificar_escore_z(indicador, z, idade_meses)
    return {"status": "calculado", "referencia": referencia,
            "escore_z": z, "classificacao": classe, "aviso": None}
