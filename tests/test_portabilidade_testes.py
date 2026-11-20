# -*- coding: utf-8 -*-
"""Guarda de portabilidade dos testes (Windows e Linux).

O CI do GitHub roda a suíte em windows-latest e em ubuntu-latest. Em 19/11/2026 o pull request #5 falhou lá por três
motivos que NÃO apareciam na máquina Linux onde os testes foram escritos e rodados:

  1. o PDF simulado (tests/fake_fpdf.py) procurava a fonte num caminho fixo do Linux: no Windows, 32 testes quebraram;
  2. um teste gravava numa pasta fixa dessa máquina: no Linux do CI nem era possível criá-la;
  3. um banco de teste continuava aberto quando o arquivo era apagado: no Windows o arquivo fica travado.

Estes testes seguram os itens 1 e 2, e também o uso do nome "Arial" no PDF das condutas (apelido antigo de Helvetica que o
fpdf2 avisa que vai remover). O item 3 só o Windows revela, por isso quem o pega é o próprio CI.

    python -m unittest tests.test_portabilidade_testes -v
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import condutas_alta_export as ex  # noqa: E402
import fake_fpdf  # noqa: E402
from test_condutas_alta_export import modelo_completo  # noqa: E402

PASTA_DOS_TESTES = Path(__file__).resolve().parent
# Pastas que só existem na máquina onde os testes foram escritos. Montadas por concatenação para este arquivo não se achar.
PASTAS_DE_UMA_MAQUINA_SO = ("/ho" + "me/claude", "/tm" + "p/claude", "/mn" + "t/user-data")


class TestSemCaminhoFixo(unittest.TestCase):
    def test_nenhum_teste_depende_de_pasta_de_uma_maquina_so(self):
        achados = []
        for arquivo in sorted(PASTA_DOS_TESTES.glob("*.py")):
            texto = arquivo.read_text(encoding="utf-8")
            achados += [f"{arquivo.name}: {fixo}" for fixo in PASTAS_DE_UMA_MAQUINA_SO if fixo in texto]
        self.assertEqual(achados, [], "use tempfile.mkdtemp()/TemporaryDirectory() em vez de um caminho fixo")


class TestPdfSimulado(unittest.TestCase):
    def test_acha_a_fonte_pelos_nomes_do_windows(self):
        """No Windows a fonte é arial.ttf (métricas iguais às da Liberation Sans): o simulador precisa achá-la."""
        esperado = {"": "arial.ttf", "B": "arialbd.ttf", "I": "ariali.ttf", "BI": "arialbi.ttf"}
        with tempfile.TemporaryDirectory() as pasta:
            for nome in esperado.values():
                Path(pasta, nome).touch()          # só a busca é testada; o arquivo não precisa ser uma fonte de verdade
            with mock.patch.object(fake_fpdf, "_PASTAS", (pasta,)):
                achadas = {estilo: os.path.basename(fake_fpdf._achar_fonte(estilo) or "") for estilo in esperado}
        self.assertEqual(achadas, esperado)

    def test_sem_nenhuma_fonte_conhecida_cai_na_fonte_padrao_do_pillow(self):
        """Máquina sem Liberation, DejaVu nem Arial: o simulador não pode quebrar (era o que acontecia no Windows)."""
        with tempfile.TemporaryDirectory() as vazia, mock.patch.object(fake_fpdf, "_PASTAS", (vazia,)):
            for estilo in ("", "B", "I", "BI"):
                self.assertIsNone(fake_fpdf._achar_fonte(estilo), estilo)
                pdf = fake_fpdf.FakePDF()
                pdf.set_font("Helvetica", estilo, 10)
                self.assertGreater(pdf.get_string_width("Orientações de alta"), 0, estilo)
                pdf.add_page()
                pdf.text(10, 10, "Orientações de alta")
            for perfil in ("paciente", "profissional"):          # o PDF inteiro das condutas, sem fonte instalada
                self.assertGreaterEqual(ex.contar_paginas(modelo_completo(), perfil, pdf_factory=fake_fpdf.FakePDF), 1)


class TestFontePadraoDoPdf(unittest.TestCase):
    def test_pdf_das_condutas_usa_so_o_nome_oficial_helvetica(self):
        """"Arial" é apelido antigo: o fpdf2 emite DeprecationWarning ("will soon be removed") ao substituí-lo."""
        usadas = set()

        class Espiao(fake_fpdf.FakePDF):
            def set_font(self, familia, estilo="", tamanho=12):
                usadas.add(familia)
                super().set_font(familia, estilo, tamanho)

        modelo = modelo_completo()
        for perfil in ("paciente", "profissional"):
            ex.contar_paginas(modelo, perfil, pdf_factory=Espiao)
        self.assertEqual({familia.lower() for familia in usadas}, {"helvetica"})
        self.assertEqual(ex.FONTE.lower(), "helvetica")


if __name__ == "__main__":
    unittest.main()
