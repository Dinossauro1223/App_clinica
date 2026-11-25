# -*- coding: utf-8 -*-
"""Núcleo isolado de avaliação antropométrica pediátrica pelas referências OMS.

As tabelas numéricas oficiais são carregadas externamente; nenhum parâmetro LMS
é presumido ou sintetizado neste módulo. Funções puras para facilitar testes.
"""
import csv
import json
import math
from datetime import date, datetime
from pathlib import Path


_INDICADORES_JSON = {
    "imc_idade": "bmi_for_age",
    "peso_idade": "weight_for_age",
    "estatura_idade": "height_for_age",
}


def _carregar_classificacoes_oms():
    caminho = Path(__file__).resolve().parent / "dados" / "oms_classificacoes_pediatricas.json"
    try:
        with caminho.open(encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        if dados.get("status") != "lms_oficial_incluido" or not isinstance(dados.get("indicators"), dict):
            return None
        return dados
    except (OSError, ValueError, TypeError):
        return None


_CLASSIFICACOES_OMS = _carregar_classificacoes_oms()


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
    if indicador not in _INDICADORES_JSON:
        raise ValueError("Indicador antropométrico desconhecido.")
    if _CLASSIFICACOES_OMS is None:
        raise RuntimeError("Metadados de classificação OMS indisponíveis.")
    configuracao = _CLASSIFICACOES_OMS["indicators"].get(_INDICADORES_JSON[indicador]) or {}
    for faixa in configuracao.get("available_age_months", []):
        if int(faixa["min"]) <= idade_meses <= int(faixa["max"]):
            return "oms_2006" if faixa["reference"] == "who_2006" else "oms_2007"
    raise ValueError("Idade fora da faixa coberta pelo indicador OMS.")


def classificar_escore_z(indicador, zscore, idade_meses):
    """Aplica os pontos de corte versionados em oms_classificacoes_pediatricas.json."""
    if isinstance(idade_meses, bool) or not isinstance(idade_meses, int) or idade_meses < 0:
        raise ValueError("Idade deve ser informada em meses completos.")
    referencia = _referencia_para(indicador, idade_meses)
    try:
        z = float(zscore)
    except (TypeError, ValueError):
        raise ValueError("Escore-z inválido.")
    if not math.isfinite(z):
        raise ValueError("Escore-z deve ser finito.")
    if _CLASSIFICACOES_OMS is None:
        raise ValueError("Arquivo de pontos de corte OMS indisponível.")
    chave = _INDICADORES_JSON[indicador]
    regras = _CLASSIFICACOES_OMS["indicators"][chave].get("classification", [])
    referencia_json = "who_2006" if referencia == "oms_2006" else "who_2007"
    for regra in regras:
        if regra.get("reference") and regra["reference"] != referencia_json:
            continue
        if "z_lt" in regra and not z < float(regra["z_lt"]):
            continue
        if "z_lte" in regra and not z <= float(regra["z_lte"]):
            continue
        if "z_gt" in regra and not z > float(regra["z_gt"]):
            continue
        if "z_gte" in regra and not z >= float(regra["z_gte"]):
            continue
        return regra["label"]
    raise ValueError("Pontos de corte OMS não cobrem este escore-z.")


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
            # Inclui âncoras superiores oficiais para interpolação sem extrapolação.
            # A interface filtra os pontos exibidos pelos limites clínicos do indicador.
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
    except RuntimeError as exc:
        return {"status": "pendente", "referencia": None,
                "escore_z": None, "classificacao": None, "aviso": str(exc)}
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


def avaliar_paciente(sexo, peso_kg, altura_cm, data_nascimento, data_avaliacao, tabela, imc=None):
    """Calcula os três indicadores OMS a partir do cadastro e das medidas de uma consulta."""
    hoje = data_avaliacao if isinstance(data_avaliacao, date) else (
        date.fromisoformat(str(data_avaliacao)) if data_avaliacao else date.today())
    bruto = str(data_nascimento or "").strip()
    nascimento = None
    for formato in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            nascimento = datetime.strptime(bruto, formato).date()
            break
        except ValueError:
            continue
    if nascimento is None:
        return {
            "status": "pendente", "aviso": "Data de nascimento ausente ou inválida no cadastro.",
            "data_avaliacao": hoje.isoformat(), "data_nascimento": None, "resultados": {},
        }
    try:
        idade_dias = calcular_idade_dias(nascimento.isoformat(), hoje.isoformat())
        idade_meses = calcular_idade_meses(nascimento.isoformat(), hoje.isoformat())
    except ValueError as exc:
        return {
            "status": "pendente", "aviso": str(exc), "data_avaliacao": hoje.isoformat(),
            "data_nascimento": nascimento.isoformat(), "resultados": {},
        }
    meses_decimais = idade_dias / 30.4375
    def numero(valor):
        if valor in (None, ""):
            return None
        try:
            return float(str(valor).replace(",", "."))
        except (TypeError, ValueError):
            return None
    peso = numero(peso_kg)
    altura = numero(altura_cm)
    if peso is not None and peso <= 0:
        peso = None
    if altura is not None and altura <= 0:
        altura = None
    imc_num = numero(imc)
    if imc_num is None and peso is not None and altura is not None:
        imc_num = peso / ((altura / 100.0) ** 2)
    snapshot = {
        "data_avaliacao": hoje.isoformat(), "data_nascimento": nascimento.isoformat(),
        "idade_dias": idade_dias, "idade_meses_completos": idade_meses,
        "idade_meses_decimais": round(meses_decimais, 4), "sexo": sexo,
        "peso_kg": peso, "altura_cm": altura, "imc": imc_num,
        "fonte": "OMS 2006 / OMS 2007 - WHO anthro 1.1.0 e anthroplus 1.1.0",
    }
    if idade_meses >= 240:
        return {"status": "nao_aplicavel", "resultados": {}, **snapshot}
    medidas = {
        "imc_idade": imc_num,
        "peso_idade": peso,
        "estatura_idade": altura,
    }
    resultados = {
        indicador: avaliar_indicador(
            indicador, valor, sexo, meses_decimais, tabela,
            idade_dias=idade_dias, idade_meses_completos=idade_meses)
        for indicador, valor in medidas.items()
    }
    estados = {r.get("status") for r in resultados.values()}
    status = ("calculado" if "calculado" in estados else
              "fora_faixa" if estados == {"fora_faixa"} else "pendente")
    return {"status": status, "resultados": resultados, **snapshot}
