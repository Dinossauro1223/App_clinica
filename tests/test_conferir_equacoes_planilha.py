"""Testes de tools/conferir_equacoes_planilha.py — planilhas SINTÉTICAS (sem dados de pacientes)."""
import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

from tools import conferir_equacoes_planilha as cf

TEM_OPENPYXL = importlib.util.find_spec("openpyxl") is not None

ROTULO_COR = {"branca": "BRANCA", "negra": "PRETAS"}
ROTULO_SEXO = {("F", "6-18"): "MENINAS", ("M", "6-18"): "MENINOS", ("F", "19-59"): "MULHERES",
               ("M", "19-59"): "HOMENS", ("F", "60-80"): "MULHERES", ("M", "60-80"): "HOMENS"}


def _formula_peso(a, b, c):
    return f"=B4*{a}+B5*{b}-{c}"


def _formula_estatura(c, a, d):
    return f"=({c}+{a}*B4-{d}*B3)/100" if d else f"=({c}+{a}*B4)/100"


def criar_planilha_sintetica(caminho, ajustes=None, remover=(), cabecalhos=None):
    """Replica o layout da aba Peso-Alt a partir do catálogo; `ajustes` troca fórmulas (celula -> texto)."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Peso-Alt"
    ws["A3"], ws["A4"], ws["A5"] = "Idade:", "AJ:", "PB:"
    for linha, texto in cf.CABECALHOS.items():
        ws[f"A{linha}"] = texto + (" anos:" if texto[0].isdigit() else "")
    for linha, (faixa, sexo, cor) in cf.LINHAS.items():
        ws[f"A{linha - (1 if cor == 'branca' else 2)}"] = ROTULO_SEXO[(sexo, faixa)]
        ws[f"A{linha}"] = ROTULO_COR[cor]
        ws[f"B{linha}"] = _formula_peso(*cf.PESO_REFERENCIA[(faixa, sexo, cor)])
        ws[f"F{linha}"] = _formula_estatura(*cf.ESTATURA_REFERENCIA[(faixa, sexo, cor)])
    ws["A41"], ws["A42"] = "Idade:", "Alt. estimada"
    ws["B45"] = "=(64.19-0.04*B41-B42)/-2.02"
    ws["C45"] = "=(84.88-0.24*B41-B42)/-1.83"
    for celula, texto in (ajustes or {}).items():
        ws[celula] = texto
    for celula in remover:
        ws[celula] = None
    for celula, texto in (cabecalhos or {}).items():
        ws[celula] = texto
    wb.save(caminho)
    return Path(caminho)


class TestExtracao(unittest.TestCase):
    def test_formulas_reais_da_planilha_do_setor(self):
        self.assertEqual(cf.extrair_peso("=B4*0.77+B5*2.47-50.16"), (0.77, 2.47, 50.16))
        self.assertEqual(cf.extrair_peso("=B4*1.5+B5*2.58-84.22"), (1.5, 2.58, 84.22))
        self.assertEqual(cf.extrair_estatura("=(43.21+2.14*B4)/100"), (43.21, 2.14, 0.0))
        self.assertEqual(cf.extrair_estatura("=(70.25+1.87*B4-0.06*B3)/100"), (70.25, 1.87, 0.06))
        self.assertEqual(cf.extrair_estatura("=(75+1.91*B4-0.17*B3)/100"), (75.0, 1.91, 0.17))
        self.assertEqual(cf.extrair_amputado("=(64.19-0.04*B41-B42)/-2.02"), (64.19, 0.04, 2.02))

    def test_formulas_fora_do_formato_previsto(self):
        for f in ("=B4*0.77+B5*2.47", "=SUM(B4:B5)", "=(43.21+2.14*B5)/100", "texto", None, "=B4*0.77+B5*2.47+50.16"):
            with self.subTest(f=f):
                self.assertIsNone(cf.extrair_peso(f))
        self.assertIsNone(cf.extrair_estatura("=(43.21+2.14*B4)/10"))
        self.assertIsNone(cf.extrair_amputado("=(64.19-0.04*B41-B42)/2.02"))

    def test_espacos_sao_ignorados(self):
        self.assertEqual(cf.extrair_peso("= B4 * 0.77 + B5 * 2.47 - 50.16"), (0.77, 2.47, 50.16))


class TestCatalogo(unittest.TestCase):
    def test_catalogo_completo_e_consistente_com_o_layout(self):
        grupos = {(f, s, c) for f in ("6-18", "19-59", "60-80") for s in "MF" for c in ("branca", "negra")}
        self.assertEqual(set(cf.PESO_REFERENCIA), grupos)
        self.assertEqual(set(cf.ESTATURA_REFERENCIA), grupos)
        self.assertEqual(set(cf.LINHAS.values()), grupos)

    def test_so_mulheres_de_19_a_59_e_brancas_de_60_a_80_usam_idade(self):
        com_idade = {k for k, (_, _, d) in cf.ESTATURA_REFERENCIA.items() if d}
        self.assertEqual(com_idade, {("19-59", "F", "branca"), ("19-59", "F", "negra"), ("60-80", "F", "branca")})


@unittest.skipUnless(TEM_OPENPYXL, "openpyxl não instalado")
class TestConferencia(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def _itens(self, **kw):
        caminho = criar_planilha_sintetica(self.dir / "p.xlsx", **kw)
        return cf.conferir(cf.carregar_aba(caminho))

    def test_planilha_igual_a_referencia_nao_tem_problemas(self):
        itens = self._itens()
        self.assertEqual(len(itens), 12 + 12 + 2)
        self.assertTrue(all(i.estado == cf.OK for i in itens), [i for i in itens if i.estado != cf.OK])

    def test_detecta_o_coeficiente_2_14_das_meninas_brancas(self):
        itens = self._itens(ajustes={"F10": "=(43.21+2.14*B4)/100"})
        problemas = [i for i in itens if i.estado != cf.OK]
        self.assertEqual(len(problemas), 1)
        self.assertEqual((problemas[0].tipo, problemas[0].chave, problemas[0].celula, problemas[0].estado),
                         ("estatura", "6-18 F branca", "F10", cf.DIVERGENTE))
        self.assertIn("2.14", problemas[0].planilha.replace("2,14", "2.14") if "," in problemas[0].planilha else problemas[0].planilha)

    def test_detecta_peso_divergente_formula_ausente_e_nao_reconhecida(self):
        itens = self._itens(ajustes={"B20": "=B4*1.01+B5*2.81-66.40", "F23": "=SUM(B4:B5)"}, remover=("F24",))
        estados = {(i.celula): i.estado for i in itens if i.estado != cf.OK}
        self.assertEqual(estados, {"B20": cf.DIVERGENTE, "F23": cf.NAO_RECONHECIDA, "F24": cf.AUSENTE})

    def test_detecta_amputado_alterado(self):
        itens = self._itens(ajustes={"B45": "=(64.19-0.04*B41-B42)/-2.04"})
        problemas = [i for i in itens if i.estado != cf.OK]
        self.assertEqual([(i.tipo, i.chave, i.estado) for i in problemas], [("amputado", "M", cf.DIVERGENTE)])

    def test_layout_trocado_e_sinalizado(self):
        itens = self._itens(cabecalhos={"A9": "MENINOS"})
        self.assertTrue(any(i.estado == cf.LAYOUT and i.celula == "A9" for i in itens))

    def test_aba_inexistente_e_arquivo_invalido(self):
        caminho = criar_planilha_sintetica(self.dir / "p.xlsx")
        with self.assertRaises(cf.ErroConferencia):
            cf.carregar_aba(caminho, "Outra")
        ruim = self.dir / "ruim.xlsx"
        ruim.write_bytes(b"nao e um xlsx")
        with self.assertRaises(cf.ErroConferencia):
            cf.carregar_aba(ruim)

    def test_main_codigos_de_saida_e_formatos(self):
        ok = criar_planilha_sintetica(self.dir / "ok.xlsx")
        ruim = criar_planilha_sintetica(self.dir / "div.xlsx", ajustes={"F10": "=(43.21+2.14*B4)/100"})
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            self.assertEqual(cf.main([str(ok)]), 0)
            self.assertEqual(cf.main([str(ruim)]), 1)
            self.assertEqual(cf.main([str(ruim), "--markdown"]), 1)
        texto = saida.getvalue()
        self.assertIn("26 de 26 itens iguais", texto)
        self.assertIn("[DIVERGENTE] estatura 6-18 F branca (F10)", texto)
        self.assertIn("| estatura | 6-18 F branca | F10 |", texto)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cf.main([str(self.dir / "nao-existe.xlsx")]), 2)


if __name__ == "__main__":
    unittest.main()
