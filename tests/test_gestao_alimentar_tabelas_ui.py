"""Regressões das linhas alternadas nas tabelas de consumo e destinação."""
import unittest
from pathlib import Path


class TestTabelasConsumoUI(unittest.TestCase):
    def test_renderizadores_aplicam_linhas_alternadas(self):
        fonte = (Path(__file__).resolve().parents[1] / "gestao_alimentar_ui.py").read_text(encoding="utf-8")
        for classe, proxima in (
            ("class PreparacoesDiaDialog:", "class AlocarRetiradaDialog:"),
            ("class AlocarRetiradaDialog:", None),
        ):
            inicio = fonte.index(classe)
            fim = fonte.index(proxima, inicio + 1) if proxima else len(fonte)
            trecho = fonte[inicio:fim]
            render = trecho.split("    def _render(self):", 1)[1]
            esperado = ('"linha_par" if indice % 2 == 0 else "linha_impar"'\n                        if classe.startswith("class PreparacoesDiaDialog:")\n                        else '"linha_par" if i % 2 == 0 else "linha_impar"')\n            self.assertIn(esperado, render)


if __name__ == "__main__":
    unittest.main()
