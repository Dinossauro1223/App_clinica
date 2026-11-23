"""Regressões dos fluxos clínicos e da integração de classificações no Mapa."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestFluxoClinicoUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (ROOT / "main.py").read_text(encoding="utf-8")
        cls.mapa = (ROOT / "mapa_ui.py").read_text(encoding="utf-8")

    def test_consulta_nao_e_item_independente_do_menu_lateral(self):
        menu = self.main.split("secoes_menu = [", 1)[1].split("self.menu_lateral =", 1)[0]
        self.assertNotIn('"Nova consulta"', menu)
        self.assertNotIn('"Consultas"', menu)

    def test_consulta_e_disponibilizada_no_cadastro_e_na_lista_de_pacientes(self):
        self.assertIn('text="Salvar e iniciar consulta"', self.main)
        self.assertIn('text="Nova consulta do paciente selecionado"', self.main)
        metodo = self.main.split("    def iniciar_consulta_paciente(self):", 1)[1].split(
            "    def salvar_paciente", 1
        )[0]
        self.assertIn("self.tree.selection()", metodo)
        self.assertIn('self.abrir_painel_lateral("Nova consulta", self.tela_consultas)', metodo)

    def test_nrs_e_avaliacao_estao_no_formulario_do_mapa(self):
        self.assertIn('self._secao("Triagem nutricional — NRS-2002")', self.mapa)
        self.assertIn('self._secao("Avaliação nutricional")', self.mapa)
        self.assertIn('text=f"Classificação NRS-2002:', self.mapa)
        self.assertIn('text=f"Classificação da avaliação:', self.mapa)
        coletar = self.mapa.split("    def _coletar(self):", 1)[1].split(
            "    def _recalcular(self):", 1
        )[0]
        self.assertIn('"nrs2002_json"', coletar)
        self.assertIn('"avaliacao_json"', coletar)

    def test_tela_de_consulta_nao_informa_integracao_nrs_pendente(self):
        self.assertNotIn("integração funcional depende da incorporação da outra branch", self.main)


if __name__ == "__main__":
    unittest.main()
