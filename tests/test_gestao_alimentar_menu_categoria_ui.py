"""Regressões do seletor de categoria do editor de menu diário."""
import unittest
from pathlib import Path


class TestCategoriaMenuUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fonte = (Path(__file__).resolve().parents[1] / "gestao_alimentar_ui.py").read_text(encoding="utf-8")

    def test_menu_principal_expoe_seis_categorias_na_ordem_definida(self):
        trecho = self.fonte.split("CATEGORIAS_MENU_PRINCIPAIS = [", 1)[1].split("]", 1)[0]
        categorias = ["salada", "entrada", "prato_principal", "acompanhamento", "sobremesa", "suco_fruta"]
        posicoes = [trecho.index('"'+categoria+'"') for categoria in categorias]
        self.assertEqual(posicoes, sorted(posicoes))

    def test_refeicoes_menores_usam_categoria_geral(self):
        self.assertIn('return [("Geral", "geral")]', self.fonte)
        self.assertIn('if refeicao in ("almoco", "jantar"):', self.fonte)

    def test_editor_persiste_categoria_na_selecao_do_dia(self):
        self.assertIn('"categoria":categoria', self.fonte)
        self.assertIn('ga.salvar_preparacoes_dia(self.db,self.e_data.get().strip(),self.cb_ref.get(),self.rows)', self.fonte)
        self.assertIn('("categoria","Grupo",125,"w")', self.fonte)


if __name__ == "__main__":
    unittest.main()
