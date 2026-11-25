# -*- coding: utf-8 -*-
"""Contratos do layout institucional do Mapa (PDF e XLSX)."""
import os
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import mapa_export as mex
from fake_fpdf import FakePDF


def leito(codigo="16", sigla="CM"):
    return {"codigo": codigo, "setor": "Clínica médica", "sigla_setor": sigla,
            "grupo_setor": "Internos"}


def registro(**extra):
    base = {
        "nome_paciente": "Paciente Exemplo", "acompanhante": 1, "sexo": "F", "cor": "B",
        "idade_anos": 67, "idade_meses": 0, "aj_cm": 50.3, "pp_cm": 19.8, "pb_cm": 21.9,
        "altura_cm": 1.56, "altura_origem": "E", "peso_kg": 66.6, "peso_origem": "A",
        "imc": 27.0, "imc_class": "Sobrepeso", "data": "2026-11-20",
        "data_reavaliacao": "2026-11-27", "via": "Enteral", "dm": 1, "has": 1,
        "laxativa": 1, "constipante": 0, "drc": 1, "consistencia": "Pastosa",
        "obs_sim": "Mamão, aveia", "obs_nao": "Leite", "fi_estado": "P",
        "fi_freq": 1, "fi_dias_ausente": None,
        "nrs2002_json": '{"completo": true, "escore": 4, "grau": "risco"}',
        "nrs2002_classificacao": "risco", "condicoes": "Doença renal crônica",
        "suplementos": [{"nome": "Trophic Soya 1,5", "qtd_dia": 200,
                         "unidade": "mL", "refeicoes": ["desjejum", "almoco"]}],
        "meta_kcal": 1998, "meta_proteina_g": 79.92,
    }
    base.update(extra)
    return base


class TestContratoTextoMapa(unittest.TestCase):
    def test_identificacao_leito_e_acompanhante(self):
        t = mex.textos_linha(leito(), registro())
        self.assertEqual(t["leito"], "CM 16")
        self.assertEqual(t["acomp"], "X")

    def test_paciente_em_um_bloco_com_antropometria_e_metas(self):
        t = mex.textos_linha(leito(), registro())
        p = t["paciente"]
        self.assertIsInstance(p, str)
        self.assertIn("Paciente Exemplo", p.splitlines()[0])
        self.assertIn("20/11/2026", p)
        self.assertIn("AJ (cm): 50,3", p)
        self.assertIn("PP (cm): 19,8", p)
        self.assertIn("PB: 21,9", p)
        self.assertIn("ALT (E): 1,56", p)
        self.assertIn("Peso (A): 66,6 Kg", p)
        self.assertIn("IMC (Kg/m²): 27", p)
        self.assertIn("(Sobrepeso)", p)
        self.assertIn("Kcal: 1.998", p)
        self.assertIn("Proteínas: 79,92 g", p)

    def test_antropometria_medida_omite_medidas_estimativas(self):
        t = mex.textos_linha(leito(), registro(altura_origem="M", peso_origem="M"))
        p = t["paciente"]
        self.assertNotIn("AJ (cm)", p)
        self.assertNotIn("PP (cm)", p)
        self.assertNotIn("PB:", p)
        self.assertIn("ALT (A): 1,56", p)
        self.assertIn("Peso (A): 66,6 Kg", p)

    def test_consistencia_em_colunas_separadas_e_caracteristicas(self):
        t = mex.textos_linha(leito(), registro())
        self.assertEqual(t["consistencias"], {"LV": "", "BR": "", "PAS": "X",
                                             "LÍQ. PAS": "", "LÍQ": ""})
        self.assertEqual(t["carac"], "DM, HAS, LAX, DRC")

    def test_fi_suplementos_preferencias_diagnosticos(self):
        t = mex.textos_linha(leito(), registro())
        self.assertEqual(t["fi"], "P. 1x/dia")
        self.assertIn("Trophic Soya 1,5: 200 mL/Etapa", t["supl"])
        self.assertIn("Desj", t["supl"])
        self.assertIn("ALM", t["supl"])
        self.assertTrue(t["preferencias"].startswith("Sim"))
        self.assertIn("Mamão", t["preferencias"])
        self.assertIn("Não", t["preferencias"])
        self.assertIn("Leite", t["preferencias"])
        self.assertIn("Doença renal crônica", t["diagnosticos"])

    def test_reavaliacao_usa_classificacao_nrs_e_data_antropometria(self):
        # NRS 3-4: sete dias após a última antropometria; não usa data manual antiga.
        with patch("nrs2002.ler_intervalos", return_value={
            "triagem_negativa": 30, "sem_risco": 30, "risco": 7, "alto_risco": 7
        }):
            t = mex.textos_linha(leito(), registro(data="2026-11-20", data_reavaliacao="2026-12-31"))
        self.assertEqual(t["reav"], "27/11/2026")

    def test_leito_vago_tem_campos_vazios(self):
        t = mex.textos_linha(leito(), None)
        self.assertEqual(t["acomp"], "")
        self.assertIsNone(t["paciente"])
        self.assertEqual(t["consistencias"]["PAS"], "")


class TestExportacaoXLSX(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "mapa.xlsx")

    def tearDown(self):
        self.tmp.cleanup()

    def test_cabecalho_hierarquico_estilos_e_conteudo(self):
        mex.exportar_excel(self.path, [{"leito": leito(), "registro": registro()},
                                       {"leito": leito("17"), "registro": None}],
                           "2026-11-24", "Clínica médica")
        from openpyxl import load_workbook
        wb = load_workbook(self.path)
        ws = wb.active
        self.assertEqual(ws["A1"].value, "SETOR DE NUTRIÇÃO")
        self.assertTrue(any("MAPA DE DIETAS - SETOR GERAL" in str(c.value)
                            for row in ws.iter_rows(min_row=2, max_row=3) for c in row))
        self.assertTrue(any("IMPRESSO EM" in str(c.value)
                            for row in ws.iter_rows(min_row=1, max_row=3) for c in row))
        cabecalhos = [str(c.value) for row in ws.iter_rows() for c in row if c.value]
        for titulo in ("LV", "BR", "PAS", "LÍQ. PAS", "LÍQ", "Via ALM.", "Preferências",
                       "Observações", "Diagnósticos"):
            self.assertIn(titulo, cabecalhos)
        texto = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value)
        for trecho in ("Paciente Exemplo", "AJ (cm): 50,3", "IMC (Kg/m²): 27",
                       "Kcal: 1.998", "Proteínas: 79,92 g", "Trophic Soya 1,5",
                       "Mamão", "Doença renal crônica"):
            self.assertIn(trecho, texto)
        self.assertTrue(ws.sheet_properties.pageSetUpPr.fitToPage)
        self.assertEqual(ws.page_setup.orientation, "landscape")

    def test_suplementacao_colorida_apenas_quando_preenchida(self):
        mex.exportar_excel(self.path, [{"leito": leito(), "registro": registro()},
                                       {"leito": leito("17"), "registro": None}],
                           "2026-11-24", "Clínica médica")
        from openpyxl import load_workbook
        ws = load_workbook(self.path).active
        # Localiza a coluna pelo cabeçalho, sem acoplar o teste à posição física.
        cab = {str(c.value): c.column for row in ws.iter_rows(min_row=1, max_row=4) for c in row if c.value}
        col = cab["Suplementação / Dieta enteral"]
        celulas = [ws.cell(r, col) for r in range(5, ws.max_row + 1)]
        preenchida = next(c for c in celulas if c.value)
        vazia = next(c for c in celulas if not c.value)
        self.assertEqual(preenchida.fill.fgColor.rgb[-6:], "FCE4D6")
        self.assertNotEqual(vazia.fill.fgColor.rgb[-6:], "FCE4D6")


class TestExportacaoPDF(unittest.TestCase):
    def test_pdf_contem_cabecalho_hierarquico_e_campos_clinicos(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            path = os.path.join(tmp.name, "mapa.pdf")
            holder = {}
            def factory(**kwargs):
                holder["pdf"] = FakePDF(**kwargs)
                return holder["pdf"]
            mex.exportar_pdf(path, [{"leito": leito(), "registro": registro()}],
                             "2026-11-24", "Clínica médica", pdf_factory=factory)
            pdf = holder["pdf"]
            textos = [x[3] for x in pdf.textos]
            for trecho in ("SETOR DE NUTRICAO", "MAPA DE DIETAS - SETOR GERAL",
                           "IMPRESSO EM", "Via ALM.", "Preferencias", "Observacoes",
                           "Diagnosticos", "AJ (cm): 50,3", "Trophic Soya 1,5"):
                self.assertTrue(any(trecho in x for x in textos), trecho)
            self.assertGreater(os.path.getsize(path), 1000)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
