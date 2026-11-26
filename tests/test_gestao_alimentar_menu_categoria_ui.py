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


    def test_almoco_e_jantar_usam_grupos_recolhiveis(self):
        self.assertIn('self.tree.configure(show="tree headings")', self.fonte)
        self.assertIn('self.tree.insert("","end",iid=gid', self.fonte)
        self.assertIn('self.tree.insert(parent,"end",iid=f"prep:{indice}"', self.fonte)
        self.assertIn('if not itens:', self.fonte)

    def test_refeicoes_menores_continuam_em_lista_unica(self):
        inicio = self.fonte.index('# Desjejum, colação, lanche e ceia permanecem em lista única')
        fim = self.fonte.index('self._render_iniciado=True', inicio)
        trecho = self.fonte[inicio:fim]
        self.assertIn('inserir_preparacao("",indice,r,True)', trecho)
        self.assertNotIn('grupo:', trecho)

    def test_troca_de_refeicao_pede_confirmacao_antes_de_descartar_edicoes(self):
        self.assertIn('messagebox.askyesno(', self.fonte)
        self.assertIn('Alterações ainda não salvas serão descartadas.', self.fonte)
        self.assertIn('self._carregar()', self.fonte)


if __name__ == "__main__":
    unittest.main()
