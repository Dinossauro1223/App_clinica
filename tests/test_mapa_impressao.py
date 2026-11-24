# -*- coding: utf-8 -*-
"""Testes dos filtros exclusivos da impressão do Mapa Nutricional."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import mapa_export as mex


def item(grupo, ocupado=True, codigo="1"):
    return {
        "leito": {"codigo": codigo, "grupo_setor": grupo},
        "registro": {"nome_paciente": "Paciente sintético"} if ocupado else None,
    }


class TestFiltrosImpressao(unittest.TestCase):
    def setUp(self):
        self.linhas = [
            item("Internos", True, "OP-1"),
            item("Internos", False, "OP-2"),
            item("Externos", True, "SVA-1"),
            item("Externos", False, "SVA-2"),
            item("Outros", True, "LEG-1"),
        ]

    def test_ambos_inclui_os_dois_grupos_e_exclui_outros(self):
        resultado = mex.filtrar_para_impressao(self.linhas, "Ambos", True)
        self.assertEqual([x["leito"]["codigo"] for x in resultado],
                         ["OP-1", "OP-2", "SVA-1", "SVA-2"])

    def test_filtra_somente_internos(self):
        resultado = mex.filtrar_para_impressao(self.linhas, "Internos", True)
        self.assertEqual([x["leito"]["codigo"] for x in resultado], ["OP-1", "OP-2"])

    def test_filtra_somente_externos(self):
        resultado = mex.filtrar_para_impressao(self.linhas, "Externos", True)
        self.assertEqual([x["leito"]["codigo"] for x in resultado], ["SVA-1", "SVA-2"])

    def test_exclui_leitos_vazios(self):
        resultado = mex.filtrar_para_impressao(self.linhas, "Ambos", False)
        self.assertEqual([x["leito"]["codigo"] for x in resultado], ["OP-1", "SVA-1"])

    def test_nao_altera_lista_original(self):
        original = list(self.linhas)
        mex.filtrar_para_impressao(self.linhas, "Internos", False)
        self.assertEqual(self.linhas, original)

    def test_rejeita_grupo_invalido(self):
        with self.assertRaises(ValueError):
            mex.filtrar_para_impressao(self.linhas, "Pediatria", True)

    def test_pdf_filtrado_mantem_coluna_de_setor(self):
        chaves = [c[0] for c in mex._colunas("Grupo_Internos")]
        self.assertIn("setor", chaves)


if __name__ == "__main__":
    unittest.main()
