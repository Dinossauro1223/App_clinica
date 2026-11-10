"""Testes de tools/verificar_ambiente.py — só biblioteca padrão e dados sintéticos."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import verificar_ambiente as va


def _fuso_ok():
    return True, "fuso de teste disponível"


def _fuso_falha():
    return False, "fuso de teste indisponível"


class TestLerRequirements(unittest.TestCase):
    def test_le_versoes_fixadas_e_ignora_ruido(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            arq = Path(d) / "requirements.txt"
            arq.write_text(
                "# comentário\n"
                "\n"
                "-r outro.txt\n"
                "Pillow==12.3.0   # comentário na linha\n"
                "fpdf2 == 2.8.9\n"
                "Custom_Pacote.x==1.0\n"
                "sem-pin-exato>=1.0\n",
                encoding="utf-8")
            self.assertEqual(va.ler_requirements(arq),
                             {"pillow": "12.3.0", "fpdf2": "2.8.9", "custom-pacote-x": "1.0"})


class TestVerificar(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.req = Path(tmp.name) / "requirements.txt"
        self.req.write_text("customtkinter==5.2.2\nfpdf2==2.8.9\ntzdata==2026.5\n", encoding="utf-8")
        self.instaladas = {"customtkinter": "5.2.2", "fpdf2": "2.8.9", "tzdata": "2026.5"}

    def _verificar(self, **kw):
        base = dict(versao_python=(3, 12, 3), instalada=self.instaladas.get, fuso=_fuso_ok,
                    tkinter_ok=lambda: True)
        base.update(kw)
        return va.verificar(self.req, **base)

    def test_ambiente_correto_passa(self):
        rel = self._verificar()
        self.assertTrue(rel.ok, rel.erros)
        self.assertEqual(rel.erros, [])
        self.assertIn("customtkinter==5.2.2", rel.infos)

    def test_python_anterior_ao_minimo_e_erro(self):
        rel = self._verificar(versao_python=(3, 9, 18))
        self.assertFalse(rel.ok)
        self.assertTrue(any("anterior ao mínimo" in e for e in rel.erros))

    def test_python_diferente_da_referencia_e_so_aviso(self):
        rel = self._verificar(versao_python=(3, 11, 9))
        self.assertTrue(rel.ok)
        self.assertTrue(any("referência" in a for a in rel.avisos))

    def test_pacote_ausente_e_erro(self):
        del self.instaladas["fpdf2"]
        rel = self._verificar()
        self.assertFalse(rel.ok)
        self.assertTrue(any("fpdf2==2.8.9 não está instalado" in e for e in rel.erros))

    def test_versao_divergente_e_aviso_e_no_modo_estrito_e_erro(self):
        self.instaladas["customtkinter"] = "6.0.0"
        rel = self._verificar()
        self.assertTrue(rel.ok)
        self.assertTrue(any("customtkinter: instalado 6.0.0, fixado 5.2.2" in a for a in rel.avisos))
        self.assertFalse(self._verificar(estrito=True).ok)

    def test_conflito_entre_fpdf2_e_fpdf_legado(self):
        for legado in ("fpdf", "pyfpdf"):
            with self.subTest(legado=legado):
                self.instaladas[legado] = "1.7.2"
                rel = self._verificar()
                self.assertFalse(rel.ok)
                self.assertTrue(any("Conflito de PDF" in e for e in rel.erros))
                del self.instaladas[legado]

    def test_somente_fpdf_legado_instalado(self):
        del self.instaladas["fpdf2"]
        self.instaladas["fpdf"] = "1.7.2"
        rel = self._verificar()
        self.assertFalse(rel.ok)
        self.assertTrue(any("legado" in e for e in rel.erros))
        self.assertTrue(any("fpdf2==2.8.9 não está instalado" in e for e in rel.erros))

    def test_fuso_indisponivel_e_erro(self):
        rel = self._verificar(fuso=_fuso_falha)
        self.assertFalse(rel.ok)
        self.assertIn("fuso de teste indisponível", rel.erros)

    def test_tkinter_ausente_e_so_aviso(self):
        rel = self._verificar(tkinter_ok=lambda: False)
        self.assertTrue(rel.ok)
        self.assertTrue(any("tkinter indisponível" in a for a in rel.avisos))

    def test_requirements_inexistente_e_erro(self):
        rel = va.verificar(self.req.parent / "nao-existe.txt", versao_python=(3, 12, 0),
                           instalada=self.instaladas.get, fuso=_fuso_ok, tkinter_ok=lambda: True)
        self.assertFalse(rel.ok)
        self.assertTrue(any("não encontrado" in e for e in rel.erros))

    def test_requirements_sem_versoes_fixadas_e_erro(self):
        self.req.write_text("# só comentário\nfpdf2>=2.0\n", encoding="utf-8")
        rel = self._verificar()
        self.assertFalse(rel.ok)
        self.assertTrue(any("nenhuma versão fixada" in e for e in rel.erros))

    def test_formatar_mostra_resultado(self):
        self.assertIn("Resultado: OK", va.formatar(self._verificar()))
        del self.instaladas["tzdata"]
        self.assertIn("Resultado: FALHA", va.formatar(self._verificar()))


class TestMain(unittest.TestCase):
    def test_codigo_de_saida(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            req = Path(d) / "requirements.txt"
            req.write_text("fpdf2==2.8.9\n", encoding="utf-8")
            instaladas = {"fpdf2": "2.8.9"}
            with mock.patch.object(va, "versao_instalada", side_effect=instaladas.get), \
                    mock.patch.object(va, "fuso_disponivel", return_value=(True, "ok")), \
                    mock.patch.object(va, "tkinter_disponivel", return_value=True):
                with contextlib.redirect_stdout(io.StringIO()) as saida:
                    self.assertEqual(va.main(["--requirements", str(req)]), 0)
                self.assertIn("Resultado: OK", saida.getvalue())
                instaladas.clear()
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(va.main(["--requirements", str(req)]), 1)


if __name__ == "__main__":
    unittest.main()
