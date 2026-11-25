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
    # WHO AnthroPlus usa 60 <= idade_em_meses < 229 (peso/idade < 121).
    # O parâmetro inteiro de 229/121 meses serve apenas como âncora de interpolação.
    "imc_idade": ((0, 59, "oms_2006"), (60, 228, "oms_2007")),
    "peso_idade": ((0, 59, "oms_2006"), (60, 120, "oms_2007")),
    "estatura_idade": ((0, 59, "oms_2006"), (60, 228, "oms_2007")),
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
        z = math.log(x / m_) / s_
    else:
        z = (((x / m_) ** l_) - 1.0) / (l_ * s_)

    # Correção OMS das caudas: não extrapolar LMS além de +/-3 DP.
    if z > 3:
        sd2 = _valor_lms_no_z(2, l_, m_, s_)
        sd3 = _valor_lms_no_z(3, l_, m_, s_)
        return 3.0 + (x - sd3) / (sd3 - sd2)
    if z < -3:
        sd_menos2 = _valor_lms_no_z(-2, l_, m_, s_)
        sd_menos3 = _valor_lms_no_z(-3, l_, m_, s_)
        return -3.0 + (x - sd_menos3) / (sd_menos2 - sd_menos3)
    return z


def _valor_lms_no_z(z, l_, m_, s_):
    """Valor observado correspondente a um escore-z LMS teórico."""
    base = 1.0 + l_ * s_ * z
    if l_ == 0:
        return m_ * math.exp(s_ * z)
    if base <= 0:
        raise ValueError("Parâmetros LMS não permitem calcular a cauda solicitada.")
    return m_ * (base ** (1.0 / l_))


def interpolar_lms(idade, tabela):
    """Interpola L, M e S linearmente; não extrapola além das idades fornecidas."""
    if isinstance(idade, bool):
        raise ValueError("Idade deve ser numérica.")
    try:
        idade = float(idade)
    except (TypeError, ValueError):
        raise ValueError("Idade deve ser numérica.")
    if not math.isfinite(idade):
        raise ValueError("Idade deve ser finita.")
    if not tabela:
        return None
    pontos = sorted((float(k), v) for k, v in tabela.items())
    exato = next((v for k, v in pontos if math.isclose(k, idade, abs_tol=1e-9)), None)
    if exato is not None:
        return tuple(float(v) for v in exato)
    if idade < pontos[0][0] or idade > pontos[-1][0]:
        return None
    for (idade_a, parametros_a), (idade_b, parametros_b) in zip(pontos, pontos[1:]):
        if idade_a < idade < idade_b:
            proporcao = (idade - idade_a) / (idade_b - idade_a)
            return tuple(float(a) + (float(b) - float(a)) * proporcao
                         for a, b in zip(parametros_a, parametros_b))
    return None


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


def calcular_idade_dias(nascimento, referencia):
    """Retorna dias corridos entre datas ISO (AAAA-MM-DD), sem arredondar."""
    try:
        nasc = date.fromisoformat(str(nascimento))
        ref = date.fromisoformat(str(referencia))
    except (TypeError, ValueError):
        raise ValueError("Informe datas válidas no formato AAAA-MM-DD.")
    if ref < nasc:
        raise ValueError("A data de referência não pode anteceder o nascimento.")
    return (ref - nasc).days


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
    """Tabelas OMS oficiais, indexadas por indicador, referência, sexo e unidade de idade.

    CSV aceita idade_dias (OMS 2006) ou idade_meses (OMS 2007), além de L, M e S.
    Linhas sintéticas antigas com apenas idade_meses continuam aceitas para testes.
    """

    def __init__(self, linhas):
        self._dados_dias = {}
        self._dados_meses = {}
        self._medidas = {}
        for linha in linhas:
            indicador = str(linha["indicador"]).strip().lower()
            referencia = str(linha["referencia"]).strip().lower()
            sexo = str(linha["sexo"]).strip().upper()
            if sexo not in ("H", "M"):
                raise ValueError("Sexo LMS deve ser H (masculino) ou M (feminino).")
            try:
                l_, m_, s_ = (float(linha[k]) for k in ("L", "M", "S"))
            except (TypeError, ValueError, KeyError):
                raise ValueError("Linha LMS incompleta ou não numérica.")
            if not all(math.isfinite(v) for v in (l_, m_, s_)) or m_ <= 0 or s_ <= 0:
                raise ValueError("Parâmetros LMS inválidos.")
            idade_dias = linha.get("idade_dias")
            idade_meses = linha.get("idade_meses")
            if idade_dias not in (None, ""):
                unidade, idade, destino = "dias", float(idade_dias), self._dados_dias
            elif idade_meses not in (None, ""):
                unidade, idade, destino = "meses", float(idade_meses), self._dados_meses
            else:
                raise ValueError("Linha LMS deve informar idade_dias ou idade_meses.")
            if idade < 0 or not math.isfinite(idade):
                raise ValueError("Idade LMS inválida.")
            chave = (indicador, referencia, sexo)
            pontos = destino.setdefault(chave, {})
            if idade in pontos:
                raise ValueError("Linha LMS duplicada: " + repr(chave + (idade,)))
            pontos[idade] = (l_, m_, s_)
            medida = str(linha.get("medida") or "").strip().upper()
            if medida:
                self._medidas[(unidade, chave, idade)] = medida

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
            obrigatorias = {"indicador", "referencia", "sexo", "L", "M", "S"}
            campos = {c.strip() for c in (leitor.fieldnames or [])}
            if not obrigatorias.issubset(campos) or not ({"idade_dias", "idade_meses"} & campos):
                raise ValueError("CSV deve conter indicador, referencia, sexo, idade_dias ou idade_meses, L, M e S.")
            return cls(leitor)

    @classmethod
    def carregar_padrao(cls, base_dir):
        """Carrega o arquivo versionado dados/oms_lms_pediatricos.csv, se existir."""
        caminho = Path(base_dir) / "dados" / "oms_lms_pediatricos.csv"
        if not caminho.exists():
            return None
        return cls.de_csv(caminho)

    def _parametros(self, indicador, referencia, sexo, idade_meses, idade_dias=None):
        chave = (indicador, referencia, sexo)
        if referencia == "oms_2006" and idade_dias is not None:
            pontos = self._dados_dias.get(chave, {})
            return interpolar_lms(idade_dias, pontos)
        pontos = self._dados_meses.get(chave, {})
        if pontos and referencia == "oms_2007" and 59.9 <= float(idade_meses) < 60 and 60.0 in pontos:
            # Ajuste apenas o arredondamento de dias na fronteira dos 60 meses;
            # nunca desloca uma idade para o primeiro ponto disponível da tabela.
            idade_meses = 60.0
        return interpolar_lms(idade_meses, pontos)

    def calcular(self, indicador, sexo, idade_meses, valor, idade_dias=None, idade_meses_completos=None):
        """Calcula escore-z; interpola LMS dentro da cobertura e nunca extrapola."""
        try:
            idade_ref = int(math.floor(float(idade_meses if idade_meses_completos is None else idade_meses_completos)))
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Idade deve ser informada em meses.")
        if idade_ref < 0:
            raise ValueError("Idade não pode ser negativa.")
        referencia = _referencia_para(indicador, idade_ref)
        sexo = str(sexo or "").strip().upper()
        if sexo not in ("H", "M"):
            return None
        parametros = self._parametros(indicador, referencia, sexo,
                                      float(idade_meses), idade_dias)
        if parametros is None:
            return None
        return calcular_escore_z(valor, *parametros)

    def curva(self, indicador, sexo, referencia):
        """Retorna pontos da curva LMS (idade, z=-3,-2,0,+2,+3), sem extrapolar."""
        sexo = str(sexo or "").strip().upper()
        chave = (indicador, referencia, sexo)
        unidade = "dias" if referencia == "oms_2006" else "meses"
        pontos = (self._dados_dias if unidade == "dias" else self._dados_meses).get(chave, {})
        saida = []
        for idade, parametros in sorted(pontos.items()):
            # Inclui todas as linhas-fonte, inclusive âncoras superiores de interpolação.
            # A camada de visualização decide quais pontos são limites clínicos.
            l_, m_, s_ = parametros
            saida.append({
                "idade": idade,
                "medida": self._medidas.get((unidade, chave, idade), ""),
                "z_menos3": _valor_lms_no_z(-3, l_, m_, s_),
                "z_menos2": _valor_lms_no_z(-2, l_, m_, s_),
                "z_zero": m_,
                "z_mais2": _valor_lms_no_z(2, l_, m_, s_),
                "z_mais3": _valor_lms_no_z(3, l_, m_, s_),
            })
        return saida


def avaliar_indicador(indicador, valor, sexo, idade_meses, tabela, idade_dias=None, idade_meses_completos=None):
    """Retorna estado explícito, escore-z e classe; nunca presume dado ausente."""
    try:
        idade_ref = int(math.floor(float(idade_meses if idade_meses_completos is None else idade_meses_completos)))
        referencia = _referencia_para(indicador, idade_ref)
    except (TypeError, ValueError, OverflowError) as exc:
        return {"status": "fora_faixa", "referencia": None,
                "escore_z": None, "classificacao": None, "aviso": str(exc)}
    if valor is None or sexo not in ("H", "M") or tabela is None:
        return {"status": "pendente", "referencia": referencia,
                "escore_z": None, "classificacao": None,
                "aviso": "Medida, sexo ou tabela LMS oficial indisponível."}
    z = tabela.calcular(indicador, sexo, idade_meses, valor, idade_dias=idade_dias,
                        idade_meses_completos=idade_ref)
    if z is None:
        motivo = ("Idade exata em dias ou parâmetro LMS oficial indisponível."
                  if referencia == "oms_2006" else
                  "Não existe parâmetro LMS oficial para esta combinação.")
        return {"status": "pendente", "referencia": referencia,
                "escore_z": None, "classificacao": None, "aviso": motivo}
    classe = classificar_escore_z(indicador, z, idade_ref)
    return {"status": "calculado", "referencia": referencia,
            "escore_z": z, "classificacao": classe, "aviso": None}
