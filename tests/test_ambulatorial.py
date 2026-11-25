"""Testes do módulo ambulatorial. Os registros e documentos de teste são sintéticos."""
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
import ambulatorial as amb

DDL = (
    """CREATE TABLE Consulta_Dados_Estruturados (
      id_consulta INTEGER PRIMARY KEY, anamnese_guiada_json TEXT NOT NULL,
      recordatorio_24h TEXT, antropometria_json TEXT NOT NULL, necessidades_json TEXT NOT NULL, criado_em TEXT)""",
    """CREATE TABLE Consulta_Medicamentos (
      id_medicamento INTEGER PRIMARY KEY, id_consulta INTEGER, nome TEXT, dose TEXT, via TEXT,
      frequencia TEXT, indicacao TEXT, observacao TEXT)""",
    """CREATE TABLE Consulta_Metas (
      id_meta INTEGER PRIMARY KEY, id_consulta INTEGER, descricao TEXT, indicador TEXT, prazo TEXT, status TEXT)""",
    """CREATE TABLE Recomendacoes_Docs (
      id_recomendacao INTEGER PRIMARY KEY, titulo TEXT NOT NULL, caso_clinico TEXT NOT NULL, tags TEXT,
      nome_original TEXT NOT NULL, arquivo_relativo TEXT NOT NULL, tamanho_bytes INTEGER, sha256 TEXT,
      ativo INTEGER, criado_em TEXT, atualizado_em TEXT)""",
    """CREATE TABLE Consulta_Recomendacoes (
      id_associacao INTEGER PRIMARY KEY, id_consulta INTEGER, id_paciente INTEGER, id_recomendacao INTEGER,
      conduta_relacionada TEXT, observacao TEXT, associado_em TEXT, UNIQUE(id_consulta,id_recomendacao))""",
    """CREATE TABLE Exames_Associacoes (
      id_associacao INTEGER PRIMARY KEY, id_exame TEXT, tipo_associacao TEXT, valor_relacionado TEXT,
      justificativa TEXT, fonte TEXT, ativo INTEGER, criado_em TEXT)""",
    """CREATE TABLE Consulta_Triagens (
      id_triagem INTEGER PRIMARY KEY, id_consulta INTEGER, instrumento TEXT, versao TEXT,
      pontuacao_total REAL, classificacao TEXT, resultado_json TEXT, origem TEXT, criado_em TEXT)""",
)


class TestCalculos(unittest.TestCase):
    def test_exemplo_dri_2023_publicado(self):
        # Exemplo do relatório DRI Energy 2023: mulher, 22 anos, 165 cm, 63 kg, pouco ativa.
        self.assertAlmostEqual(amb.calcular_dri_2023_adulto(22, "Feminino", 63, 165, "pouco_ativo"), 2275.37, places=2)

    def test_dri_2023_masculino(self):
        esperado = 1004.82 - 10.83 * 30 + 6.52 * 180 + 15.91 * 80
        self.assertAlmostEqual(amb.calcular_dri_2023_adulto(30, "Masculino", 80, 180, "ativo"), esperado)

    def test_imc_bolso_e_proteina(self):
        self.assertAlmostEqual(amb.calcular_imc("70,0", "1,75"), 70 / 1.75**2)
        self.assertEqual(amb.calcular_formula_bolso(70, 30), 2100)
        self.assertEqual(amb.calcular_necessidade_proteica(70, 1.2), 84)

    def test_faixas_e_validacoes(self):
        for fn, args in (
            (amb.calcular_dri_2023_adulto, (18, "Feminino", 55, 160, "ativo")),
            (amb.calcular_formula_bolso, (60, 36)),
            (amb.calcular_necessidade_proteica, (60, 0)),
        ):
            with self.subTest(fn=fn.__name__), self.assertRaises(amb.ErroAmbulatorial):
                fn(*args)

    def test_texto_da_consulta_inclui_escores_e_classificacao_oms(self):
        snapshot = {
            "status": "calculado", "data_nascimento": "2019-01-15",
            "idade_dias": 2500, "idade_meses_completos": 82,
            "resultados": {
                "imc_idade": {"status": "calculado", "escore_z": 1.25, "classificacao": "Sobrepeso"},
                "peso_idade": {"status": "calculado", "escore_z": 0.3, "classificacao": "Sem baixo peso pelo indicador"},
                "estatura_idade": {"status": "calculado", "escore_z": -0.2, "classificacao": "Estatura dentro da faixa de referência"},
            },
            "fonte": "OMS 2006 / OMS 2007",
        }
        texto = amb.montar_texto_anamnese(
            {}, "", {"peso_kg": 30, "altura_m": 1.3, "imc_kg_m2": 17.75, "pediatria_oms": snapshot})
        self.assertIn("AVALIAÇÃO ANTROPOMÉTRICA PEDIÁTRICA — OMS", texto)
        self.assertIn("IMC/idade: z=+1.25 - Sobrepeso", texto)
        self.assertIn("Peso/idade: z=+0.30 - Sem baixo peso pelo indicador", texto)
        self.assertIn("Estatura/idade: z=-0.20 - Estatura dentro da faixa de referência", texto)

    def test_texto_pronto_para_copiar(self):
        texto = amb.montar_texto_anamnese(
            {"queixa_principal": "Fadiga", "apetite": "Reduzido", "observacoes": ""},
            "Desjejum: pão e leite",
            {"peso_kg": 60, "altura_m": 1.6, "imc_kg_m2": 23.44},
            {"dri_2023_kcal_dia": 1900, "formula_bolso_kcal_dia": 1800,
             "formula_bolso_fator_kcal_kg": 30, "proteina_g_dia": 72, "proteina_fator_g_kg": 1.2},
            [{"nome": "Medicamento A", "dose": "10 mg"}],
            [{"descricao": "Meta A", "prazo": "30 dias"}],
        )
        self.assertIn("Queixa principal: Fadiga", texto)
        self.assertNotIn("Observações adicionais:", texto)
        self.assertIn("RECORDATÓRIO ALIMENTAR DE 24 HORAS", texto)
        self.assertIn("MEDICAMENTOS EM USO", texto)
        self.assertIn("METAS NUTRICIONAIS", texto)


class TestPersistencia(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        for sql in DDL:
            self.conn.execute(sql)

    def tearDown(self):
        self.conn.close()

    def test_anamnese_medicamentos_metas(self):
        dados = {
            "anamnese_guiada": {"queixa_principal": "Fadiga"},
            "recordatorio_24h": "Desjejum: pão",
            "antropometria": {"peso_kg": 70, "altura_m": 1.75, "pediatria_oms": {"resultados": {"imc_idade": {"status": "calculado", "escore_z": 0.5, "classificacao": "Eutrofia"}}}},
            "necessidades": {"dri_2023_kcal_dia": 2200},
            "medicamentos": [{"nome": "Medicamento A", "dose": "10 mg", "via": "oral", "frequencia": "1x/dia"}],
            "metas": [{"descricao": "Meta A", "indicador": "25 g/dia", "prazo": "30 dias", "status": "Em acompanhamento"}],
        }
        amb.salvar_dados_estruturados(self.conn, 5, dados)
        row = self.conn.execute("SELECT anamnese_guiada_json, recordatorio_24h, antropometria_json, necessidades_json FROM Consulta_Dados_Estruturados").fetchone()
        self.assertEqual(json.loads(row[0])["queixa_principal"], "Fadiga")
        self.assertEqual(row[1], "Desjejum: pão")
        self.assertEqual(json.loads(row[2])["peso_kg"], 70)
        self.assertEqual(json.loads(row[2])["pediatria_oms"]["resultados"]["imc_idade"]["escore_z"], 0.5)
        self.assertEqual(json.loads(row[3])["dri_2023_kcal_dia"], 2200)
        self.assertEqual(self.conn.execute("SELECT nome FROM Consulta_Medicamentos").fetchone()[0], "Medicamento A")
        self.assertEqual(self.conn.execute("SELECT descricao FROM Consulta_Metas").fetchone()[0], "Meta A")

    def test_associacoes_exame_e_diagnostico(self):
        aid = amb.salvar_associacao_exame(
            self.conn, "EXM-FERRITINA", "diagnostico_nutricional",
            "Risco de deficiência de ferro", "Correlacionar com hemograma e história clínica", "Referência de teste")
        item = amb.associacoes_do_exame(self.conn, "EXM-FERRITINA")[0]
        self.assertEqual(item["id_associacao"], aid)
        self.assertEqual(item["tipo_associacao"], "diagnostico_nutricional")

    def test_contrato_de_armazenamento_nrs_2002(self):
        tid = amb.registrar_resultado_triagem(
            self.conn, 5, "NRS-2002", "versão fornecida pelo módulo emissor", 3,
            "risco nutricional", {"pontuacao_total": 3, "itens": {"estado_nutricional": 2}}, "módulo NRS-2002")
        row = self.conn.execute("SELECT instrumento, pontuacao_total, classificacao, resultado_json FROM Consulta_Triagens WHERE id_triagem=?", (tid,)).fetchone()
        self.assertEqual(row[:3], ("NRS-2002", 3.0, "risco nutricional"))
        self.assertEqual(json.loads(row[3])["pontuacao_total"], 3)

    def test_docx_validado_e_associado(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            docx = base / "orientacao.docx"
            with zipfile.ZipFile(docx, "w") as pacote:
                pacote.writestr("[Content_Types].xml", "<Types/>")
                pacote.writestr("word/document.xml", "<document/>")
            rid = amb.cadastrar_recomendacao_docx(self.conn, docx, base, "Orientação", "Caso renal", "renal")
            item = amb.listar_recomendacoes(self.conn)[0]
            self.assertTrue(amb.caminho_recomendacao(base, item["arquivo_relativo"]).is_file())
            amb.associar_recomendacoes(self.conn, 5, 12, [rid], "Plano de cuidado")
            link = self.conn.execute("SELECT id_paciente, conduta_relacionada FROM Consulta_Recomendacoes").fetchone()
            self.assertEqual(link, (12, "Plano de cuidado"))
            bad = base / "arquivo_invalido.docx"
            bad.write_text("não é DOCX", encoding="utf-8")
            with self.assertRaises(amb.ErroAmbulatorial):
                amb.validar_docx(bad)


if __name__ == "__main__":
    unittest.main()
