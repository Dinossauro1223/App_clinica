# -*- coding: utf-8 -*-
"""Verificações de montagem da guia do Almoxarifado sem abrir uma janela real."""
import unittest
from pathlib import Path


class TestAlmoxUI(unittest.TestCase):
    def test_guia_tem_as_quatro_areas_operacionais(self):
        raiz = Path(__file__).resolve().parents[1]
        fonte = (raiz / "almox_ui.py").read_text(encoding="utf-8")
        for nome in ("Resumo e custos", "Itens", "Movimentações", "Programação"):
            self.assertIn(nome, fonte)
        for metodo in ("def _resumo(", "def _itens_ui(", "def _movimentos(", "def _programacao("):
            self.assertIn(metodo, fonte)
        self.assertIn("def _atualizar_resumo(", fonte)
        self.assertIn("def _realizar_programacao(", fonte)


if __name__ == "__main__":
    unittest.main()
