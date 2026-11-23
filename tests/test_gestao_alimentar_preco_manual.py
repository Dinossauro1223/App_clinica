"""Testes do preço manual de ingredientes nas fichas técnicas."""
import tempfile
import unittest
from pathlib import Path

import gestao_alimentar_db as ga


class TestPrecoManualFicha(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "gestao.db")
        ga.inicializar(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_formulario_exibe_preco_em_linha_propria_e_vinculo_separado(self):
        from pathlib import Path
        fonte = (Path(__file__).resolve().parents[1] / "gestao_alimentar_ui.py").read_text(encoding="utf-8")
        inicio = fonte.index("    def adicionar_linha(self, item=None):")
        fim = fonte.index("    def _selecionar_tbca(self, registro, valor):", inicio)
        metodo = fonte[inicio:fim]
        self.assertIn("linha_estoque", metodo)
        self.assertIn('text="Almoxarifado:"', metodo)
        self.assertIn('text="Preço manual (R$/unid.):"', metodo)
        self.assertIn('placeholder_text="0,00"', metodo)
        self.assertIn('"preco": preco', metodo)
        self.assertIn('"tbca": tbca', metodo)

    def test_preco_manual_calcula_custo_sem_vinculo_ao_almoxarifado(self):
        ficha = ga.salvar_ficha(self.db, "Arroz", "Acompanhamento", 1, [{
            "nome": "Arroz", "unidade": "g", "qtd_per_capita": 100,
            "fator_correcao": 1, "preco_unitario_manual": "0,02",
        }])
        resultado = ga.calcular_ficha(self.db, ficha)
        self.assertEqual(resultado["custos_faltantes"], 0)
        self.assertAlmostEqual(resultado["custo_total"], 2.0)
        self.assertAlmostEqual(resultado["custo_por_porcao"], 2.0)

    def test_preco_manual_prevalece_sobre_preco_sincronizado_do_almoxarifado(self):
        ga.sincronizar_produtos_almox(self.db, [{
            "id_item": 7, "nome": "Arroz", "unidade": "g",
            "preco_unitario": 5, "embalagem_qtd": 1000,
            "embalagem_un": "g", "qtd": 10,
        }])
        ficha = ga.salvar_ficha(self.db, "Arroz", "Acompanhamento", 1, [{
            "nome": "Arroz", "unidade": "g", "qtd_per_capita": 100,
            "fator_correcao": 1, "id_produto_mobile": 7,
            "preco_unitario_manual": 0.02,
        }])
        resultado = ga.calcular_ficha(self.db, ficha)
        self.assertAlmostEqual(resultado["custo_total"], 2.0)
        self.assertEqual(resultado["custos_faltantes"], 0)

    def test_preco_manual_negativo_e_rejeitado(self):
        with self.assertRaisesRegex(ValueError, "não pode ser negativo"):
            ga.salvar_ficha(self.db, "Arroz", "Acompanhamento", 1, [{
                "nome": "Arroz", "unidade": "g", "qtd_per_capita": 100,
                "preco_unitario_manual": -0.01,
            }])

    def test_migracao_adiciona_coluna_em_banco_existente(self):
        with ga._conexao(self.db) as conn:
            colunas = {r[1] for r in conn.execute("PRAGMA table_info(GA_Ficha_Ingredientes)")}
        self.assertIn("preco_unitario_manual", colunas)


if __name__ == "__main__":
    unittest.main()
