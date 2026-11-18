# -*- coding: utf-8 -*-
"""Testes do PDF/impressão das condutas de alta. O layout é verificado com o simulador (tests/fake_fpdf.py); quando a
biblioteca fpdf está instalada, também se gera o PDF de verdade. Dados 100% sintéticos.

    python -m unittest tests.test_condutas_alta_export -v
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import condutas_alta as ca  # noqa: E402
import condutas_alta_export as ex  # noqa: E402
from fake_fpdf import FakePDF  # noqa: E402
from test_condutas_alta import novo_banco, registrar  # noqa: E402

AGORA = datetime(2026, 11, 15, 10, 0, 0)
def _tem_fpdf_de_verdade():
    """True só se o fpdf importável é a biblioteca real (um substituto vazio de ambiente de teste não conta)."""
    if importlib.util.find_spec("fpdf") is None:
        return False
    try:
        from fpdf import FPDF
    except ImportError:
        return False
    return callable(getattr(FPDF, "get_string_width", None)) and callable(getattr(FPDF, "output", None))


TEM_FPDF = _tem_fpdf_de_verdade()


def modelo_completo():
    """Modelo real: catálogo de verdade, paciente sintético com via enteral e diabetes, tudo confirmado."""
    db = novo_banco()
    try:
        reg = registrar(db, nome="Maria Sintética da Silva", via="Enteral", dm=1)
        s = ca.SessaoCondutasAlta(db, reg["id_paciente"], agora=AGORA)
        for cod in s.pendentes():
            s.confirmar(cod)
        s.salvar_cabecalho("Nutri Teste", "CRN-6 0000", "Voltar ao ambulatório em 30 dias.\n- Trazer o registro do peso.")
        return s.modelo_exportacao()
    finally:
        os.remove(db)


def modelo_misto():
    db = novo_banco()
    try:
        reg = registrar(db, nome="João Sintético", via="Enteral", dm=1)
        s = ca.SessaoCondutasAlta(db, reg["id_paciente"], agora=AGORA)
        s.confirmar("ENT-01", texto_paciente="- Dieta: Fórmula X, 1500 mL por dia, em 6 horários.")
        s.nao_se_aplica("ENT-02", "Família já recebe a fórmula pelo serviço.")
        return s.modelo_exportacao()                         # as demais ficam pendentes
    finally:
        os.remove(db)


class TestTexto(unittest.TestCase):
    def test_latin1(self):
        self.assertEqual(ex._l1("a\u2013b ≥ 5 “aspas” • x…"), 'a-b >= 5 "aspas" - x...')
        self.assertEqual(ex._l1("ação, 30° e µg"), "ação, 30° e µg")
        self.assertEqual(ex._l1("emoji \U0001f600"), "emoji ?")
        self.assertEqual(ex._l1(None), "")

    def test_quebra_de_linha(self):
        pdf = FakePDF()
        pdf.add_page()
        pdf.set_font("Arial", "", 10)
        texto = "Lave as mãos com água e sabão por pelo menos 30 segundos antes de mexer na dieta ou na sonda."
        linhas = ex._quebrar(pdf, texto, 60.0)
        self.assertGreater(len(linhas), 1)
        self.assertTrue(all(pdf.get_string_width(ln) <= 60.0 for ln in linhas))
        self.assertEqual(" ".join(linhas).split(), texto.split())          # nenhuma palavra se perde

    def test_palavra_maior_que_a_linha_e_quebrada_por_caracteres(self):
        pdf = FakePDF()
        pdf.add_page()
        pdf.set_font("Arial", "", 8)
        link = "https://www.exemplo.gov.br/" + "caminho-muito-longo/" * 8 + "arquivo.pdf"
        linhas = ex._quebrar(pdf, "Disponível em: " + link, 90.0)
        self.assertTrue(all(pdf.get_string_width(ln) <= 90.0 for ln in linhas))
        self.assertEqual("".join(linhas).replace(" ", ""), ("Disponível em: " + link).replace(" ", ""))

    def test_nome_sugerido(self):
        m = {"paciente": "José da Conceição Ávila", "data": "15/11/2026"}
        self.assertEqual(ex.nome_sugerido(m), "Orientacoes_de_alta_Jose_da_Conceicao_Avila_2026-11-15.pdf")
        self.assertTrue(ex.nome_sugerido(m, "profissional").startswith("Condutas_de_alta_nutricionista_"))
        self.assertEqual(ex.nome_sugerido({"paciente": "", "data": ""}), "Orientacoes_de_alta_paciente_sem-data.pdf")


class TestFolhaDoPaciente(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modelo = modelo_completo()

    def gerar(self, modelo=None, perfil="paciente"):
        pdf = FakePDF()
        pasta = tempfile.mkdtemp()
        try:
            caminho = os.path.join(pasta, "a.pdf")
            fn = ex.exportar_pdf_paciente if perfil == "paciente" else ex.exportar_pdf_profissional
            paginas = fn(caminho, modelo or self.modelo, pdf_factory=lambda **kw: pdf)
            existe = os.path.getsize(caminho) > 0
        finally:
            shutil.rmtree(pasta, ignore_errors=True)
        return pdf, paginas, existe

    def test_folha_compacta_e_dentro_da_pagina(self):
        pdf, paginas, existe = self.gerar()
        self.assertTrue(existe)
        self.assertEqual(paginas, len(pdf.paginas))
        self.assertLessEqual(paginas, 2, "as 9 condutas de enteral devem caber em até 2 folhas")
        for _pag, x, y, txt, _cor in pdf.textos:
            self.assertGreaterEqual(x, ex.MARG - 0.01, txt)
            self.assertLessEqual(y, ex.Y_RODAPE + 0.01, txt)

    def test_texto_cabe_na_largura_util(self):
        pdf, _p, _e = self.gerar()
        largura = ex.LARG - 2 * ex.MARG
        for _pag, x, _y, txt, _cor in pdf.textos:
            pdf.set_font("Arial", "", 8)
            self.assertLessEqual(x - ex.MARG, largura, txt)

    def test_so_condutas_confirmadas_vao_para_o_paciente(self):
        m = modelo_misto()
        pdf, _p, _e = self.gerar(m)
        corpo = " ".join(t[3] for t in pdf.textos)
        self.assertIn("Sua dieta pela sonda", corpo)               # ENT-01 confirmada
        self.assertIn("Fórmula X", corpo)                          # texto editado pela nutricionista
        self.assertNotIn("Misturas e dieta caseira", corpo)        # ENT-02 não se aplica
        self.assertNotIn("Validade da dieta", corpo)               # ENT-04 pendente
        self.assertNotIn("Conferir", corpo)                        # nada do lado técnico
        self.assertNotIn("BISCHOFF", corpo)

    def test_cabecalho_rodape_e_recado(self):
        pdf, paginas, _e = self.gerar()
        corpo = [t[3] for t in pdf.textos]
        self.assertTrue(any("Maria Sintética da Silva" in t for t in corpo))
        self.assertTrue(any("15/11/2026" in t for t in corpo))
        self.assertTrue(any("Nutricionista: Nutri Teste (CRN-6 0000)" in t for t in corpo))
        self.assertIn(f"Página 1 de {paginas}", corpo)
        self.assertIn("Recado da nutricionista", corpo)
        self.assertTrue(any("Voltar ao ambulatório" in t for t in corpo))
        self.assertEqual(sum(1 for t in corpo if t.startswith("Página ")), paginas)

    def test_campos_em_branco_sao_mantidos_para_preencher_a_mao(self):
        pdf, _p, _e = self.gerar()
        self.assertTrue(any("______" in t[3] for t in pdf.textos))

    def test_sem_condutas_confirmadas_nao_gera_folha(self):
        vazio = dict(self.modelo, itens=[dict(i, estado="pendente") for i in self.modelo["itens"]])
        with self.assertRaises(ca.ErroCondutasAlta):
            self.gerar(vazio)
        with self.assertRaises(ca.ErroCondutasAlta):
            ex.contar_paginas(vazio, "paciente", pdf_factory=lambda **kw: FakePDF())

    def test_sem_nome_da_nutricionista_rodape_neutro(self):
        pdf, _p, _e = self.gerar(dict(self.modelo, nutricionista="", crn=""))
        self.assertTrue(any(t[3] == "Nutrição" for t in pdf.textos))

    def test_nenhum_travessao_no_pdf(self):
        pdf, _p, _e = self.gerar()
        self.assertFalse(any("\u2013" in t[3] or "\u2014" in t[3] for t in pdf.textos))

    def test_contar_paginas_igual_ao_pdf(self):
        pdf, paginas, _e = self.gerar()
        self.assertEqual(ex.contar_paginas(self.modelo, "paciente", pdf_factory=lambda **kw: FakePDF()), paginas)

    def test_gera_imagens_para_conferencia_visual(self):
        destino = os.environ.get("NUTRILAB_PNG_DIR")
        if not destino:
            self.skipTest("defina NUTRILAB_PNG_DIR para salvar as páginas como PNG")
        pdf, _p, _e = self.gerar()
        pdf.salvar_pngs(os.path.join(destino, "paciente"))
        pdf2, _p2, _e2 = self.gerar(modelo_misto(), "profissional")
        pdf2.salvar_pngs(os.path.join(destino, "profissional"))


class TestRelatorioDoNutricionista(unittest.TestCase):
    def test_visao_integral_com_situacao_conferencia_e_referencias(self):
        pdf = FakePDF()
        pasta = tempfile.mkdtemp()
        try:
            paginas = ex.exportar_pdf_profissional(os.path.join(pasta, "p.pdf"), modelo_misto(), pdf_factory=lambda **kw: pdf)
        finally:
            shutil.rmtree(pasta, ignore_errors=True)
        corpo = " ".join(t[3] for t in pdf.textos)
        self.assertEqual(paginas, len(pdf.paginas))
        for trecho in ("Uso interno, não entregar ao paciente", "Situação: CONFIRMADA (texto editado)",
                       "Situação: NÃO SE APLICA", "Situação: PENDENTE", "Conferir antes de confirmar:",
                       "Texto que vai ao paciente:", "Motivo: Família já recebe a fórmula pelo serviço.",
                       "Referências", "BISCHOFF, S. C.", "Confirmadas: 1", "Não se aplicam: 1", "Pendentes: 7",
                       "Via enteral, Diabetes mellitus", "Visão do nutricionista - uso interno"):
            self.assertIn(trecho, corpo)
        self.assertNotIn("\u2013", corpo)

    def test_relatorio_funciona_mesmo_com_tudo_pendente(self):
        m = modelo_misto()
        m = dict(m, itens=[dict(i, estado="pendente") for i in m["itens"]])
        pdf = FakePDF()
        ex.exportar_pdf_profissional(None, m, pdf_factory=lambda **kw: pdf) if False else ex._gerar(
            m, "profissional", None, lambda **kw: pdf)
        self.assertGreaterEqual(len(pdf.paginas), 1)


class TestImpressao(unittest.TestCase):
    def setUp(self):
        fd, self.arq = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)

    def tearDown(self):
        os.remove(self.arq)

    def test_windows_usa_o_verbo_print(self):
        chamadas = []
        estado, msg = ex.imprimir_pdf(self.arq, plataforma="win32", startfile=lambda *a: chamadas.append(a))
        self.assertEqual((estado, chamadas), ("impresso", [(self.arq, "print")]))
        self.assertIn("impressora", msg)

    def test_windows_sem_verbo_print_abre_o_pdf(self):
        chamadas = []

        def startfile(caminho, verbo=None):
            chamadas.append(verbo)
            if verbo == "print":
                raise OSError("sem aplicativo associado")

        estado, msg = ex.imprimir_pdf(self.arq, plataforma="win32", startfile=startfile)
        self.assertEqual((estado, chamadas), ("aberto", ["print", None]))
        self.assertIn("Ctrl+P", msg)

    def test_linux_usa_lp_quando_existe(self):
        class R:
            returncode = 0
        chamadas = []
        estado, _m = ex.imprimir_pdf(self.arq, plataforma="linux", localizar=lambda n: "/usr/bin/" + n,
                                     executar=lambda cmd, **kw: chamadas.append(cmd) or R())
        self.assertEqual((estado, chamadas), ("impresso", [["/usr/bin/lp", self.arq]]))

    def test_linux_sem_lp_abre_o_arquivo_e_sem_nada_avisa(self):
        class R:
            returncode = 0
        chamadas = []
        estado, _m = ex.imprimir_pdf(self.arq, plataforma="linux", localizar=lambda n: "/x/xdg-open" if n == "xdg-open" else None,
                                     executar=lambda cmd, **kw: chamadas.append(cmd) or R())
        self.assertEqual((estado, chamadas), ("aberto", [["/x/xdg-open", self.arq]]))
        estado, _m = ex.imprimir_pdf(self.arq, plataforma="linux", localizar=lambda n: None, executar=None)
        self.assertEqual(estado, "erro")

    def test_arquivo_inexistente_e_falha_do_sistema(self):
        self.assertEqual(ex.imprimir_pdf(self.arq + ".nao", plataforma="linux")[0], "erro")

        def quebra(*a, **k):
            raise OSError("falhou")
        self.assertEqual(ex.imprimir_pdf(self.arq, plataforma="linux", localizar=lambda n: "/x/" + n, executar=quebra)[0],
                         "erro")


@unittest.skipUnless(TEM_FPDF, "biblioteca fpdf não instalada neste Python (pip install -r requirements.txt)")
class TestComFpdfReal(unittest.TestCase):
    def test_gera_pdfs_de_verdade(self):
        m = modelo_misto()
        pasta = tempfile.mkdtemp()
        try:
            a, b = os.path.join(pasta, "paciente.pdf"), os.path.join(pasta, "nutri.pdf")
            n1, n2 = ex.exportar_pdf_paciente(a, m), ex.exportar_pdf_profissional(b, m)
            for arq, n in ((a, n1), (b, n2)):
                with open(arq, "rb") as f:
                    dados = f.read()
                self.assertTrue(dados.startswith(b"%PDF"), arq)
                self.assertGreater(len(dados), 1500)
                self.assertGreaterEqual(n, 1)
            self.assertEqual(ex.contar_paginas(m, "paciente"), n1)
        finally:
            shutil.rmtree(pasta, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
