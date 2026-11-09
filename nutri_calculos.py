# -*- coding: utf-8 -*-
"""Cálculos antropométricos do NutriLab, sem dependência de interface gráfica.

Equações e pontos de corte conforme o "Relatório de fórmulas e estimativas
antropométricas em nutrição clínica" (seções 4, 5 e 7). Tudo aqui é apoio à
decisão: valores estimados devem ser sempre identificados como "estimados".

Convenções internas: sexo 'H' (homem) ou 'M' (mulher); cor 'B' (branca) ou
'N' (negra); AJ = altura do joelho (cm); PB/CB = perímetro do braço (cm).
"""
import csv
import math
import os
from collections import namedtuple

# ----------------------------------------------------------------- entrada/saída


def parse_num(txt):
    """Converte '12,5', '12.5' ou '1.234,5' em float. Vazio/inválido -> None."""
    if txt is None:
        return None
    if isinstance(txt, (int, float)):
        return float(txt) if math.isfinite(txt) else None
    s = str(txt).strip().replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def fmt_num(valor, casas=1, vazio="-"):
    """Formata com vírgula decimal (padrão brasileiro). None -> vazio."""
    if valor is None:
        return vazio
    return f"{valor:.{casas}f}".replace(".", ",")


def norm_sexo(x):
    """Aceita 'H', 'Homem', 'Masculino', 'M', 'Mulher', 'Feminino'. -> 'H'/'M'/None.
    Atenção: 'M' sozinho significa Mulher nesta convenção interna."""
    if x is None:
        return None
    s = str(x).strip().lower()
    if s.startswith("h") or s.startswith("masc"):
        return "H"
    if s.startswith("mul") or s.startswith("fem") or s == "m" or s == "f":
        return "M"
    return None


def norm_cor(x):
    """Aceita 'B', 'Branco/a', 'N', 'Negro/a', 'Preto/a'. -> 'B'/'N'/None."""
    if x is None:
        return None
    s = str(x).strip().lower()
    if s.startswith("b"):
        return "B"
    if s.startswith("n") or s.startswith("p"):
        return "N"
    return None


# ------------------------------------------------------------------------ faixas


def faixa_etaria(idade_anos):
    """'crianca' (< 19 anos), 'adulto' (19 a 59) ou 'idoso' (>= 60)."""
    if idade_anos is None:
        return None
    if idade_anos < 19:
        return "crianca"
    if idade_anos < 60:
        return "adulto"
    return "idoso"


# ---------------------------------------------------- estimativa de altura e peso

Estimativa = namedtuple("Estimativa", "valor equacao avisos")


class EstimativaIndisponivel(ValueError):
    """Não há equação aplicável (ou faltam dados) para estimar o valor."""


# Estatura = intercepto + b_AJ * AJ + b_idade * idade
# Chumlea, Guo e Steinbaugh (1994): 6-18 anos e 18-60 anos, por sexo e cor.
_ALTURA_1994 = {
    ("crianca", "H", "B"): (40.54, 2.22, 0.0),
    ("crianca", "H", "N"): (39.60, 2.18, 0.0),
    ("crianca", "M", "B"): (43.21, 2.15, 0.0),
    ("crianca", "M", "N"): (46.59, 2.02, 0.0),
    ("adulto", "H", "B"): (71.85, 1.88, 0.0),
    ("adulto", "H", "N"): (73.42, 1.79, 0.0),
    ("adulto", "M", "B"): (70.25, 1.87, -0.06),
    ("adulto", "M", "N"): (68.10, 1.86, -0.06),
}
# Chumlea, Roche e Steinbaugh (1985): 60-90 anos, só sexo.
_ALTURA_1985 = {"H": (64.19, 2.02, -0.04), "M": (84.88, 1.83, -0.24)}
# Chumlea et al. (1998), NHANES III, 60 anos ou mais, sexo + cor.
_ALTURA_1998 = {
    ("H", "B"): (78.31, 1.94, -0.14),
    ("H", "N"): (79.69, 1.85, -0.14),
    ("M", "B"): (82.21, 1.85, -0.21),
    ("M", "N"): (89.58, 1.61, -0.17),
}
# Peso = b_AJ * AJ + b_CB * CB + intercepto (Chumlea; tabela do POP.EMTN.002).
_PESO_CHUMLEA = {
    ("crianca", "H", "B"): (0.68, 2.64, -50.08),
    ("crianca", "H", "N"): (0.59, 2.73, -48.32),
    ("crianca", "M", "B"): (0.77, 2.47, -50.16),
    ("crianca", "M", "N"): (0.71, 2.59, -50.43),
    ("adulto", "H", "B"): (1.19, 3.21, -86.82),
    ("adulto", "H", "N"): (1.09, 3.14, -83.72),
    ("adulto", "M", "B"): (1.01, 2.81, -66.04),
    ("adulto", "M", "N"): (1.24, 2.97, -82.48),
    ("idoso", "H", "B"): (1.10, 3.07, -75.81),
    ("idoso", "H", "N"): (0.44, 2.86, -39.21),
    ("idoso", "M", "B"): (1.09, 2.68, -65.51),
    ("idoso", "M", "N"): (1.50, 2.58, -84.22),
}

METODOS_ALTURA_IDOSO = {
    "chumlea1985": "Chumlea et al. (1985), 60-90 anos (só sexo)",
    "chumlea1998": "Chumlea et al. (1998), NHANES III (sexo + cor)",
}
CRITERIOS_IMC_IDOSO = {
    "lipschitz": "Lipschitz (1994): <22 / 22-27 / >27",
    "opas": "OPAS (2001): <23 / 23-28 / 28-30 / >=30",
}


def _validar_aj(aj):
    if aj is None or aj <= 0:
        raise EstimativaIndisponivel("Informe a altura do joelho (AJ).")
    if not 20 <= aj <= 90:
        raise EstimativaIndisponivel("AJ fora da faixa plausível (20 a 90 cm). Confira a medida.")


def estimar_altura(aj_cm, sexo, cor, idade_anos, metodo_idoso="chumlea1985"):
    """Estatura estimada (cm) pela altura do joelho. Levanta EstimativaIndisponivel."""
    aj = parse_num(aj_cm)
    idade = parse_num(idade_anos)
    _validar_aj(aj)
    if idade is None:
        raise EstimativaIndisponivel("Informe a idade.")
    s = norm_sexo(sexo)
    c = norm_cor(cor)
    if s is None:
        raise EstimativaIndisponivel("Informe o sexo (Homem/Mulher).")
    if idade < 6:
        raise EstimativaIndisponivel(
            "Não há equação de AJ validada para menores de 6 anos. Use o comprimento/estatura medidos.")
    faixa = faixa_etaria(idade)
    avisos = []
    if faixa == "idoso":
        if metodo_idoso == "chumlea1998":
            if c is None:
                raise EstimativaIndisponivel("Informe a cor (Branco/Negro) para esta equação.")
            a, b, k = _ALTURA_1998[(s, c)]
            nome = "Chumlea et al. (1998), NHANES III"
        else:
            a, b, k = _ALTURA_1985[s]
            nome = "Chumlea et al. (1985), 60-90 anos"
            if idade > 90:
                avisos.append("Idade acima da faixa validada (60 a 90 anos).")
        if s == "M" or idade >= 70:
            avisos.append("Precisão reduzida em mulheres idosas e a partir dos 70 anos (Lima et al., 2018).")
    else:
        if c is None:
            raise EstimativaIndisponivel("Informe a cor (Branco/Negro) para esta equação.")
        a, b, k = _ALTURA_1994[(faixa, s, c)]
        nome = "Chumlea et al. (1994), " + ("6-18 anos" if faixa == "crianca" else "18-60 anos")
        if faixa == "crianca":
            avisos.append("Equação derivada de crianças norte-americanas.")
    valor = a + b * aj + k * idade
    return Estimativa(round(valor, 1), nome, avisos)


def estimar_peso(aj_cm, pb_cm, sexo, cor, idade_anos):
    """Peso estimado (kg) por AJ + perímetro do braço (Chumlea). Levanta EstimativaIndisponivel."""
    aj = parse_num(aj_cm)
    pb = parse_num(pb_cm)
    idade = parse_num(idade_anos)
    _validar_aj(aj)
    if pb is None or pb <= 0:
        raise EstimativaIndisponivel("Informe o perímetro do braço (PB).")
    if not 10 <= pb <= 60:
        raise EstimativaIndisponivel("PB fora da faixa plausível (10 a 60 cm). Confira a medida.")
    if idade is None:
        raise EstimativaIndisponivel("Informe a idade.")
    s = norm_sexo(sexo)
    c = norm_cor(cor)
    if s is None:
        raise EstimativaIndisponivel("Informe o sexo (Homem/Mulher).")
    if c is None:
        raise EstimativaIndisponivel("Informe a cor (Branco/Negro).")
    if idade < 6:
        raise EstimativaIndisponivel("Não há equação de Chumlea para menores de 6 anos. Pese a criança.")
    faixa = faixa_etaria(idade)
    a, b, k = _PESO_CHUMLEA[(faixa, s, c)]
    valor = a * aj + b * pb + k
    if valor <= 0 or valor > 300:
        raise EstimativaIndisponivel("Resultado fora do plausível. Confira AJ e PB.")
    faixa_txt = {"crianca": "6-18 anos", "adulto": "19-59 anos", "idoso": "60-80 anos"}[faixa]
    avisos = ["Estimativa: o erro típico é de vários kg. Pese sempre que possível."]
    if idade > 80:
        avisos.append("Idade acima da faixa validada (até 80 anos).")
    return Estimativa(round(valor, 1), f"Chumlea (AJ + PB), {faixa_txt}", avisos)


# ------------------------------------------------------------------ IMC e classe


def calcular_imc(peso_kg, altura_cm):
    peso = parse_num(peso_kg)
    alt = parse_num(altura_cm)
    if not peso or not alt or peso <= 0 or alt <= 0:
        return None
    m = alt / 100.0
    return peso / (m * m)


ClassifIMC = namedtuple("ClassifIMC", "rotulo faixa criterio pendente zscore")


def _classe_adulto(imc):
    if imc < 16.0:
        return "Magreza grau III"
    if imc < 17.0:
        return "Magreza grau II"
    if imc < 18.5:
        return "Magreza grau I"
    if imc < 25.0:
        return "Eutrofia"
    if imc < 30.0:
        return "Sobrepeso"
    if imc < 35.0:
        return "Obesidade grau I"
    if imc < 40.0:
        return "Obesidade grau II"
    return "Obesidade grau III"


def _classe_idoso(imc, criterio):
    if criterio == "opas":
        if imc < 23.0:
            return "Baixo peso"
        if imc < 28.0:
            return "Eutrofia"
        if imc < 30.0:
            return "Sobrepeso"
        return "Obesidade"
    # Lipschitz (padrão do programa)
    if imc < 22.0:
        return "Baixo peso"
    if imc <= 27.0:
        return "Eutrofia"
    return "Sobrepeso"


def _classe_zscore(z, meses):
    """SISVAN/Ministério da Saúde: 0 a <5 anos (OMS 2006) e 5 a 19 anos (OMS 2007)."""
    if z < -3:
        return "Magreza acentuada"
    if z < -2:
        return "Magreza"
    if z <= 1:
        return "Eutrofia"
    if meses < 60:
        if z <= 2:
            return "Risco de sobrepeso"
        if z <= 3:
            return "Sobrepeso"
        return "Obesidade"
    if z <= 2:
        return "Sobrepeso"
    if z <= 3:
        return "Obesidade"
    return "Obesidade grave"


def classificar_imc(imc, idade_anos, sexo=None, idade_meses_extra=0,
                    criterio_idoso="lipschitz", lms=None):
    """Classifica o IMC para a idade. Retorna ClassifIMC.

    - >= 60 anos: Lipschitz ou OPAS (criterio_idoso).
    - 19 a 59 anos: OMS.
    - < 19 anos: escore z do IMC/idade (OMS 2006/2007). Sem a tabela LMS carregada
      ou sem sexo, devolve pendente=True (o programa nunca "chuta" a classe).
    """
    if imc is None or idade_anos is None:
        return ClassifIMC("", None, None, False, None)
    faixa = faixa_etaria(idade_anos)
    if faixa == "idoso":
        crit = criterio_idoso if criterio_idoso in CRITERIOS_IMC_IDOSO else "lipschitz"
        return ClassifIMC(_classe_idoso(imc, crit), faixa, crit, False, None)
    if faixa == "adulto":
        return ClassifIMC(_classe_adulto(imc), faixa, "oms", False, None)
    s = norm_sexo(sexo)
    meses = int(idade_anos) * 12 + int(idade_meses_extra or 0)
    if lms is not None and s is not None:
        z = lms.zscore_imc(imc, s, meses)
        if z is not None:
            return ClassifIMC(_classe_zscore(z, meses), faixa, "oms-z", False, z)
    return ClassifIMC("", faixa, "oms-z", True, None)


def texto_classificacao(c):
    """Texto curto para exibir/imprimir entre parênteses ('' se não houver IMC)."""
    if c is None or (not c.rotulo and not c.pendente):
        return ""
    return c.rotulo if c.rotulo else "tabela OMS pendente"


# ---------------------------------------------------- tabelas LMS da OMS (opcional)


class TabelaLMS:
    """Tabelas L, M, S do IMC para idade (OMS 2006: 0-60 meses; OMS 2007: 61-228).

    Arquivo CSV com cabeçalho: sexo;idade_meses;L;M;S  (separador ; ou ,).
    sexo: 'masculino'/'feminino' (ou menino/menina, boys/girls, 1/2). 'M' sozinho
    é recusado por ser ambíguo (Masculino x Mulher).
    """

    def __init__(self):
        self.dados = {"H": {}, "M": {}}

    @staticmethod
    def _sexo_csv(valor):
        v = str(valor).strip().lower()
        if v in ("masculino", "homem", "menino", "boys", "boy", "1"):
            return "H"
        if v in ("feminino", "mulher", "menina", "girls", "girl", "2", "f"):
            return "M"
        raise ValueError(f"Sexo inválido no CSV LMS: '{valor}'. Use 'masculino' ou 'feminino'.")

    @classmethod
    def de_csv(cls, caminho):
        t = cls()
        with open(caminho, newline="", encoding="utf-8-sig") as f:
            amostra = f.read(2048)
            f.seek(0)
            delim = ";" if amostra.count(";") >= amostra.count(",") else ","
            leitor = csv.DictReader(f, delimiter=delim)
            for linha in leitor:
                k = {str(a).strip().lower(): v for a, v in linha.items()}
                s = cls._sexo_csv(k["sexo"])
                meses = int(float(parse_num(k["idade_meses"])))
                t.dados[s][meses] = (parse_num(k["l"]), parse_num(k["m"]), parse_num(k["s"]))
        if not t.dados["H"] or not t.dados["M"]:
            raise ValueError("O CSV LMS precisa ter linhas para os dois sexos.")
        return t

    @classmethod
    def carregar_padrao(cls, base_dir):
        """Procura dados/oms_imc_idade_lms.csv ao lado do programa. None se ausente/inválido."""
        caminho = os.path.join(base_dir, "dados", "oms_imc_idade_lms.csv")
        if not os.path.exists(caminho):
            return None
        try:
            return cls.de_csv(caminho)
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def zscore_imc(self, imc, sexo, meses):
        tab = self.dados.get(sexo) or {}
        if not tab:
            return None
        if meses in tab:
            l_, m_, s_ = tab[meses]
        else:
            anteriores = [k for k in tab if k <= meses]
            if not anteriores or meses > max(tab) + 1:
                return None
            l_, m_, s_ = tab[max(anteriores)]
        if None in (l_, m_, s_) or m_ <= 0 or s_ <= 0 or imc <= 0:
            return None
        if l_ == 0:
            return math.log(imc / m_) / s_
        return ((imc / m_) ** l_ - 1.0) / (l_ * s_)


# ------------------------------------------------------------------------- datas


def idade_em_anos(nascimento_br, referencia):
    """Idade completa em anos a partir de 'DD/MM/AAAA'. None se inválido."""
    from datetime import datetime
    try:
        n = datetime.strptime(nascimento_br.strip(), "%d/%m/%Y").date()
    except (ValueError, AttributeError):
        return None
    anos = referencia.year - n.year - ((referencia.month, referencia.day) < (n.month, n.day))
    return anos if anos >= 0 else None
