"""Regressões das linhas alternadas nas tabelas de consumo e destinação."""
import unittest
from pathlib import Path


class TestTabelasConsumoUI(unittest.TestCase):
    def test_renderizadores_aplicam_linhas_alternadas(self):
        fonte = (Path(__file__).resolve().parents[1] / "gestao_alimentar_ui.py").read_text(encoding="utf-8")
        for classe, proxima, variavel in (
            ("class PreparacoesDiaDialog:", "class AlocarRetiradaDialog:", "indice"),
            ("class AlocarRetiradaDialog:", None, "i"),
        ):
            inicio = fonte.index(classe)
            fim = fonte.index(proxima, inicio + 1) if proxima else len(fonte)
            trecho = fonte[inicio:fim]
            render = trecho.split("    def _render(self):", 1)[1]
            esperado = f'"linha_par" if {variavel} % 2 == 0 else "linha_impar"'
            self.assertIn(esperado, render)


if __name__ == "__main__":
    unittest.main()
