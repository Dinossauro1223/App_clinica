"""Verifica que o tema também atualiza as cores das linhas das tabelas ttk."""
import unittest
from unittest.mock import Mock, patch

import tema


class TreeFake:
    def __init__(self):
        self.tags = {}

    def winfo_class(self):
        return "Treeview"

    def winfo_children(self):
        return []

    def tag_configure(self, nome, **kwargs):
        self.tags[nome] = kwargs


class RootFake:
    def __init__(self, filhos):
        self.filhos = filhos

    def winfo_children(self):
        return self.filhos


class TestTemaTreeview(unittest.TestCase):
    def test_mudanca_de_aparencia_recolore_linhas_e_selecao(self):
        arvore = TreeFake()
        raiz = RootFake([arvore])
        with patch.object(tema.ttk, "Style", return_value=Mock()):
            with patch.object(tema.ctk, "get_appearance_mode", return_value="Light"):
                tema.aplicar_tema_ttk(raiz)
                claro = dict(arvore.tags)
            with patch.object(tema.ctk, "get_appearance_mode", return_value="Dark"):
                tema.aplicar_tema_ttk(raiz)
                escuro = dict(arvore.tags)

        for tag in ("linha_par", "linha_impar", "tbca_par", "tbca_impar"):
            self.assertIn(tag, claro)
            self.assertIn(tag, escuro)
        self.assertNotEqual(
            claro["linha_par"]["background"],
            escuro["linha_par"]["background"],
        )
        self.assertNotEqual(
            claro["linha_impar"]["foreground"],
            escuro["linha_impar"]["foreground"],
        )


if __name__ == "__main__":
    unittest.main()
