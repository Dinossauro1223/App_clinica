# -*- coding: utf-8 -*-
"""Cálculos e persistência do módulo ambulatorial.

As estimativas são apoio à decisão. As equações EER DRI 2023 deste módulo
cobrem adultos de 19 anos ou mais, não gestantes/não lactantes. Não extrapolar
para pediatria, gestação, lactação ou condições especiais sem equação validada.
"""
from __future__ import annotations
import hashlib
import json
import math
import shutil
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

DRI_2023_ADULTOS = {
    "H": {
        "inativo": (753.07, -10.83, 6.50, 14.10),
        "pouco_ativo": (581.47, -10.83, 8.30, 14.94),
        "ativo": (1004.82, -10.83, 6.52, 15.91),
        "muito_ativo": (-517.88, -10.83, 15.61, 19.11),
    },
    "M": {
        "inativo": (584.90, -7.01, 5.72, 11.71),
        "pouco_ativo": (575.77, -7.01, 6.60, 12.14),
        "ativo": (710.25, -7.01, 6.54, 12.34),
        "muito_ativo": (511.83, -7.01, 9.07, 12.56),
    },
}
MAX_DOCX_BYTES = 25 * 1024 * 1024


class ErroAmbulatorial(ValueError):
    pass


def numero(valor, nome="valor"):
    if isinstance(valor, bool) or valor is None:
        raise ErroAmbulatorial(f"Informe {nome}.")
    s = str(valor).strip().replace(" ", "")
    if not s:
        raise ErroAmbulatorial(f"Informe {nome}.")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        n = float(s)
    except (ValueError, TypeError):
        raise ErroAmbulatorial(f"{nome.capitalize()} deve ser numérico.")
    if not math.isfinite(n):
        raise ErroAmbulatorial(f"{nome.capitalize()} deve ser finito.")
    return n


def normalizar_sexo(sexo):
    s = str(sexo or "").strip().casefold()
    if s in {"h", "homem", "masculino", "male"}:
        return "H"
    if s in {"m", "mulher", "feminino", "female", "f"}:
        return "M"
    raise ErroAmbulatorial("Sexo não compatível com a equação DRI 2023. Confira o cadastro.")


def calcular_imc(peso_kg, altura_m):
    peso = numero(peso_kg, "peso em kg")
    altura = numero(altura_m, "altura em metros")
    if not 1 <= peso <= 500 or not 0.3 <= altura <= 2.7:
        raise ErroAmbulatorial("Peso ou altura fora da faixa plausível. Confira as medidas.")
    return peso / (altura ** 2)


def calcular_dri_2023_adulto(idade_anos, sexo, peso_kg, altura_cm, nivel_atividade="inativo"):
    """EER de adultos pela Tabela 5-16 de Dietary Reference Intakes for Energy (NASEM, 2023)."""
    idade = numero(idade_anos, "idade")
    peso = numero(peso_kg, "peso em kg")
    altura = numero(altura_cm, "altura em cm")
    if not 19 <= idade <= 120:
        raise ErroAmbulatorial("Esta equação DRI 2023 está habilitada somente para adultos a partir de 19 anos.")
    if not 1 <= peso <= 500 or not 30 <= altura <= 270:
        raise ErroAmbulatorial("Peso ou altura fora da faixa plausível.")
    sexo = normalizar_sexo(sexo)
    pal = str(nivel_atividade or "").strip().casefold()
    if pal not in DRI_2023_ADULTOS[sexo]:
        raise ErroAmbulatorial("Selecione Inativo, Pouco ativo, Ativo ou Muito ativo.")
    a, b, c, d = DRI_2023_ADULTOS[sexo][pal]
    eer = a + b * idade + c * altura + d * peso
    if not math.isfinite(eer) or eer <= 0:
        raise ErroAmbulatorial("Resultado DRI inválido. Confira idade, sexo, peso, altura e atividade.")
    return eer


def calcular_formula_bolso(peso_kg, fator_kcal_kg=25):
    peso = numero(peso_kg, "peso em kg")
    fator = numero(fator_kcal_kg, "fator kcal/kg")
    if not 1 <= peso <= 500:
        raise ErroAmbulatorial("Peso fora da faixa plausível.")
    if not 25 <= fator <= 35:
        raise ErroAmbulatorial("A fórmula de bolso deve ficar entre 25 e 35 kcal/kg/dia.")
    return peso * fator


def calcular_necessidade_proteica(peso_kg, fator_g_kg):
    peso = numero(peso_kg, "peso em kg")
    fator = numero(fator_g_kg, "fator proteico em g/kg")
    if not 1 <= peso <= 500 or not 0 < fator <= 10:
        raise ErroAmbulatorial("Confira o peso e o fator proteico (maior que 0 e até 10 g/kg).")
    return peso * fator


def calcular_resumo_nutricional(peso_kg, altura_m, idade_anos, sexo, nivel_atividade="inativo",
                                fator_bolso=25, fator_proteico=None):
    peso = numero(peso_kg, "peso em kg")
    altura = numero(altura_m, "altura em metros")
    resultado = {
        "peso_kg": peso, "altura_m": altura, "imc_kg_m2": calcular_imc(peso, altura),
        "idade_anos": int(numero(idade_anos, "idade")), "sexo": normalizar_sexo(sexo),
        "nivel_atividade": nivel_atividade,
        "dri_2023_kcal_dia": calcular_dri_2023_adulto(idade_anos, sexo, peso, altura * 100, nivel_atividade),
        "formula_bolso_fator_kcal_kg": numero(fator_bolso, "fator kcal/kg"),
        "formula_bolso_kcal_dia": calcular_formula_bolso(peso, fator_bolso),
        "proteina_fator_g_kg": None, "proteina_g_dia": None,
        "base_energetica": "DRI 2023 - necessidade energética estimada (EER)",
    }
    if fator_proteico not in (None, ""):
        resultado["proteina_fator_g_kg"] = numero(fator_proteico, "fator proteico em g/kg")
        resultado["proteina_g_dia"] = calcular_necessidade_proteica(peso, fator_proteico)
    return resultado


def montar_texto_anamnese(campos, recordatorio_24h="", antropometria=None, necessidades=None,
                          medicamentos=None, metas=None):
    rotulos = {
        "queixa_principal": "Queixa principal", "objetivos": "Objetivos/expectativas",
        "historia_atual": "História da condição atual", "diagnosticos": "Diagnósticos e antecedentes relatados",
        "historico_familiar": "Histórico familiar", "rotina": "Rotina e horários", "apetite": "Apetite",
        "preferencias": "Preferências alimentares", "aversoes": "Aversões/restrições",
        "alergias_intolerancias": "Alergias/intolerâncias relatadas", "ingestao_hidrica": "Ingestão hídrica",
        "recordatorio_habitual": "Padrão alimentar habitual", "sintomas_gastrointestinais": "Sintomas gastrointestinais",
        "mastigacao_degluticao": "Mastigação/deglutição", "funcao_intestinal": "Função intestinal/evacuação",
        "sono_estresse": "Sono/estresse", "atividade_fisica": "Atividade física",
        "contexto_social": "Contexto social/segurança alimentar", "observacoes": "Observações adicionais",
    }
    linhas = ["ANAMNESE NUTRICIONAL"]
    for chave, rotulo in rotulos.items():
        valor = str((campos or {}).get(chave) or "").strip()
        if valor:
            linhas.append(f"{rotulo}: {valor}")
    antro = antropometria or {}
    if any(antro.get(k) not in (None, "") for k in ("peso_kg", "altura_m", "gordura_percentual")):
        linhas.append("\nANTROPOMETRIA")
        for chave, rotulo, unidade in (("peso_kg", "Peso", "kg"), ("altura_m", "Altura", "m"),
                                       ("gordura_percentual", "% de gordura", "%")):
            if antro.get(chave) not in (None, ""):
                linhas.append(f"{rotulo}: {antro[chave]} {unidade}")
        if antro.get("imc_kg_m2") is not None:
            linhas.append(f"IMC: {antro['imc_kg_m2']:.2f} kg/m²")
    nec = necessidades or {}
    if nec:
        linhas.append("\nESTIMATIVA DE NECESSIDADES NUTRICIONAIS")
        if nec.get("dri_2023_kcal_dia") is not None:
            linhas.append(f"DRI 2023 (EER): {nec['dri_2023_kcal_dia']:.0f} kcal/dia")
        if nec.get("formula_bolso_kcal_dia") is not None:
            linhas.append(f"Fórmula de bolso ({nec.get('formula_bolso_fator_kcal_kg')} kcal/kg): "
                          f"{nec['formula_bolso_kcal_dia']:.0f} kcal/dia")
        if nec.get("proteina_g_dia") is not None:
            linhas.append(f"Proteína ({nec.get('proteina_fator_g_kg')} g/kg): {nec['proteina_g_dia']:.1f} g/dia")
    recordatorio = str(recordatorio_24h or "").strip()
    if recordatorio:
        linhas.extend(["\nRECORDATÓRIO ALIMENTAR DE 24 HORAS", recordatorio])
    meds = list(medicamentos or [])
    if meds:
        linhas.append("\nMEDICAMENTOS EM USO (RELATO/CONFERÊNCIA)")
        for item in meds:
            partes = [str(item.get(k) or "").strip() for k in ("nome", "dose", "via", "frequencia", "indicacao")]
            partes = [p for p in partes if p]
            if partes:
                linhas.append(" - " + " | ".join(partes))
    objetivos = list(metas or [])
    if objetivos:
        linhas.append("\nMETAS NUTRICIONAIS")
        for item in objetivos:
            partes = [str(item.get(k) or "").strip() for k in ("descricao", "indicador", "prazo", "status")]
            partes = [p for p in partes if p]
            if partes:
                linhas.append(" - " + " | ".join(partes))
    return "\n".join(linhas).strip()


def _json(dados):
    return json.dumps(dados if dados is not None else {}, ensure_ascii=False, separators=(",", ":"))


def salvar_dados_estruturados(conn, id_consulta, dados):
    dados = dados or {}
    conn.execute(
        """INSERT INTO Consulta_Dados_Estruturados
           (id_consulta, anamnese_guiada_json, recordatorio_24h, antropometria_json, necessidades_json, criado_em)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(id_consulta) DO UPDATE SET
             anamnese_guiada_json=excluded.anamnese_guiada_json, recordatorio_24h=excluded.recordatorio_24h,
             antropometria_json=excluded.antropometria_json, necessidades_json=excluded.necessidades_json,
             criado_em=excluded.criado_em""",
        (id_consulta, _json(dados.get("anamnese_guiada")), dados.get("recordatorio_24h", ""),
         _json(dados.get("antropometria")), _json(dados.get("necessidades")),
         datetime.now().isoformat(timespec="seconds")),
    )
    conn.execute("DELETE FROM Consulta_Medicamentos WHERE id_consulta=?", (id_consulta,))
    for item in dados.get("medicamentos", []) or []:
        if any(str(item.get(k) or "").strip() for k in ("nome", "dose", "via", "frequencia", "indicacao")):
            conn.execute(
                """INSERT INTO Consulta_Medicamentos
                   (id_consulta, nome, dose, via, frequencia, indicacao, observacao)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (id_consulta, *(str(item.get(k) or "").strip() for k in
                                ("nome", "dose", "via", "frequencia", "indicacao", "observacao"))),
            )
    conn.execute("DELETE FROM Consulta_Metas WHERE id_consulta=?", (id_consulta,))
    for item in dados.get("metas", []) or []:
        if any(str(item.get(k) or "").strip() for k in ("descricao", "indicador", "prazo")):
            conn.execute(
                "INSERT INTO Consulta_Metas (id_consulta, descricao, indicador, prazo, status) VALUES (?, ?, ?, ?, ?)",
                (id_consulta, *(str(item.get(k) or "").strip() for k in ("descricao", "indicador", "prazo", "status"))),
            )


def validar_docx(caminho):
    origem = Path(caminho).expanduser().resolve()
    if origem.suffix.lower() != ".docx" or not origem.is_file():
        raise ErroAmbulatorial("Selecione um arquivo DOCX existente.")
    tamanho = origem.stat().st_size
    if tamanho <= 0 or tamanho > MAX_DOCX_BYTES:
        raise ErroAmbulatorial("O DOCX deve ter conteúdo e no máximo 25 MB.")
    try:
        with zipfile.ZipFile(origem, "r") as pacote:
            nomes = set(pacote.namelist())
            if "[Content_Types].xml" not in nomes or "word/document.xml" not in nomes or pacote.testzip():
                raise ErroAmbulatorial("O arquivo não parece ser um DOCX válido.")
    except (zipfile.BadZipFile, OSError):
        raise ErroAmbulatorial("O arquivo selecionado não é um DOCX válido.")
    return origem, tamanho, hashlib.sha256(origem.read_bytes()).hexdigest()


def cadastrar_recomendacao_docx(conn, arquivo_origem, pasta_dados, titulo, caso_clinico, tags=""):
    origem, tamanho, digest = validar_docx(arquivo_origem)
    titulo, caso = str(titulo or "").strip(), str(caso_clinico or "").strip()
    if not titulo or not caso:
        raise ErroAmbulatorial("Informe o título e o caso clínico da recomendação.")
    base = Path(pasta_dados).expanduser().resolve()
    pasta = base / "recomendacoes_clinicas"
    pasta.mkdir(parents=True, exist_ok=True)
    relativo = f"recomendacoes_clinicas/{uuid.uuid4().hex}.docx"
    destino = base / relativo
    shutil.copy2(origem, destino)
    try:
        cur = conn.execute(
            """INSERT INTO Recomendacoes_Docs
               (titulo, caso_clinico, tags, nome_original, arquivo_relativo, tamanho_bytes, sha256, ativo, criado_em, atualizado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (titulo, caso, str(tags or "").strip(), origem.name, relativo, tamanho, digest,
             datetime.now().isoformat(timespec="seconds"), datetime.now().isoformat(timespec="seconds")),
        )
        return int(cur.lastrowid)
    except Exception:
        destino.unlink(missing_ok=True)
        raise


def listar_recomendacoes(conn):
    return [dict(zip(("id_recomendacao", "titulo", "caso_clinico", "tags", "nome_original", "arquivo_relativo"), r))
            for r in conn.execute(
                """SELECT id_recomendacao, titulo, caso_clinico, tags, nome_original, arquivo_relativo
                   FROM Recomendacoes_Docs WHERE ativo=1 ORDER BY titulo COLLATE NOCASE""").fetchall()]


def caminho_recomendacao(pasta_dados, relativo):
    base = Path(pasta_dados).expanduser().resolve()
    caminho = (base / str(relativo or "")).resolve()
    if base not in caminho.parents or not caminho.is_file():
        raise ErroAmbulatorial("Arquivo DOCX não encontrado na pasta de dados.")
    return caminho


def associar_recomendacoes(conn, id_consulta, id_paciente, ids, conduta_relacionada=""):
    for rid in sorted({int(x) for x in (ids or [])}):
        conn.execute(
            """INSERT OR IGNORE INTO Consulta_Recomendacoes
               (id_consulta, id_paciente, id_recomendacao, conduta_relacionada, observacao, associado_em)
               VALUES (?, ?, ?, ?, '', ?)""",
            (id_consulta, id_paciente, rid, str(conduta_relacionada or "").strip(),
             datetime.now().isoformat(timespec="seconds")),
        )


def associacoes_do_exame(conn, id_exame):
    return [dict(zip(("id_associacao", "tipo_associacao", "valor_relacionado", "justificativa", "fonte"), r))
            for r in conn.execute(
                """SELECT id_associacao, tipo_associacao, valor_relacionado, justificativa, fonte
                   FROM Exames_Associacoes WHERE id_exame=? AND ativo=1 ORDER BY tipo_associacao, valor_relacionado""",
                (id_exame,)).fetchall()]


def salvar_associacao_exame(conn, id_exame, tipo, valor, justificativa="", fonte=""):
    if tipo not in {"exame_recomendado", "diagnostico_clinico", "diagnostico_nutricional"}:
        raise ErroAmbulatorial("Tipo de associação inválido.")
    if not id_exame or not str(valor or "").strip():
        raise ErroAmbulatorial("Selecione o exame e informe o item relacionado.")
    cur = conn.execute(
        """INSERT INTO Exames_Associacoes
           (id_exame, tipo_associacao, valor_relacionado, justificativa, fonte, ativo, criado_em)
           VALUES (?, ?, ?, ?, ?, 1, ?)""",
        (id_exame, tipo, str(valor).strip(), str(justificativa or "").strip(), str(fonte or "").strip(),
         datetime.now().isoformat(timespec="seconds")),
    )
    return int(cur.lastrowid)


def registrar_resultado_triagem(conn, id_consulta, instrumento, versao, pontuacao_total,
                                 classificacao, resultado, origem=""):
    """Recebe o resultado calculado por outro módulo; não calcula nem altera a NRS-2002."""
    nome = str(instrumento or "").strip()
    if not nome:
        raise ErroAmbulatorial("Informe o instrumento de triagem.")
    score = None if pontuacao_total in (None, "") else numero(pontuacao_total, "pontuação")
    cur = conn.execute(
        """INSERT INTO Consulta_Triagens
           (id_consulta, instrumento, versao, pontuacao_total, classificacao, resultado_json, origem, criado_em)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (id_consulta, nome, str(versao or "").strip(), score, str(classificacao or "").strip(), _json(resultado),
         str(origem or "").strip(), datetime.now().isoformat(timespec="seconds")),
    )
    return int(cur.lastrowid)
