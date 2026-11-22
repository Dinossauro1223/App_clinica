"""Regressões da composição vetorial e das camadas da tela inicial do NutriLab."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

RAIZ = Path(__file__).resolve().parent.parent
IDENTIDADE = RAIZ / "assets" / "identidade"
COMPONENTES = IDENTIDADE / "componentes"


class TestTelaInicialEmCamadas(unittest.TestCase):
    def test_componentes_da_cena_sao_svg_independentes(self):
        obrigatorios = (
            "arco.svg", "assinatura.svg", "dna.svg", "facisa_ufrn.svg",
            "folhas.svg", "frasco.svg", "maca.svg", "wordmark.svg",
            "topo_temas.svg", "boas_vindas.svg", "decoracao_inferior.svg",
            "haste_folhas.svg",
        )
        for nome in obrigatorios:
            caminho = COMPONENTES / nome
            self.assertTrue(caminho.is_file(), nome)
            raiz = ET.parse(caminho).getroot()
            self.assertTrue(raiz.tag.endswith("svg"), nome)

    def test_folhas_tem_ids_individuais_para_extracao_e_animacao(self):
        svg = (COMPONENTES / "folhas.svg").read_text(encoding="utf-8")
        for indice in range(1, 6):
            self.assertIn(f'id="folha-{indice}"', svg)
        gerador = (RAIZ / "tools" / "gerar_identidade_visual.py").read_text(encoding="utf-8")
        self.assertIn("renderizar_folhas_individuais", gerador)
        self.assertIn("folhas.json", gerador)
        self.assertIn("getbbox()", gerador)

    def test_tela_inicial_usa_canvas_e_png_rgba_individuais(self):
        tela = (RAIZ / "tela_boas_vindas.py").read_text(encoding="utf-8")
        self.assertIn("ImageTk.PhotoImage", tela)
        self.assertIn('create_image(', tela)
        self.assertIn('tags=("folha-animada",)', tela)
        self.assertIn('fg_color="transparent"', tela)
        self.assertIn("identidade_camadas", tela)

    def test_janela_abre_maximizada_sem_fullscreen_exclusivo(self):
        main = (RAIZ / "main.py").read_text(encoding="utf-8")
        self.assertIn('self.state("zoomed")', main)
        self.assertNotIn('self.attributes("-fullscreen", True)', main)
        self.assertIn("TelaBoasVindas", main)

    def test_spec_e_inicializador_incluem_as_camadas(self):
        spec = (RAIZ / "app_clinica.spec").read_text(encoding="utf-8")
        launcher = (RAIZ / "Gerar_e_Abrir_NutriLab.bat").read_text(encoding="utf-8")
        self.assertIn("assets', 'identidade', 'renderizados", spec)
        self.assertIn("tools\\\\gerar_identidade_visual.py", launcher)
        self.assertLess(
            launcher.index("gerar_identidade_visual.py"),
            launcher.index("-m PyInstaller")
        )


if __name__ == "__main__":
    unittest.main()
