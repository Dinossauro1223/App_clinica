"""Testes prioritários do renderizador SVG e da identidade visual do NutriLab.

Executar antes do banco e do PyInstaller:
    python -m unittest discover -s tests -p "test_svg_pipeline.py" -v
"""
from __future__ import annotations

import io
import json
import unittest

import resvg_py
from PIL import Image

from tools import gerar_identidade_visual as pipeline


class TestPipelineSVG(unittest.TestCase):
    def test_00_importacao_e_renderizacao_svg_minimo(self):
        """Detecta imediatamente falha de importação do backend ou de geração PNG."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="16">'
            '<rect x="2" y="2" width="20" height="12" rx="2" fill="#168653"/>'
            "</svg>"
        )
        png = resvg_py.svg_to_bytes(svg_string=svg)
        self.assertTrue(png.startswith(b"\\x89PNG\\r\\n\\x1a\\n"))
        with Image.open(io.BytesIO(png)) as imagem:
            imagem.load()
            self.assertEqual(imagem.size, (24, 16))
            self.assertEqual(imagem.mode, "RGBA")
            self.assertGreater(imagem.getchannel("A").getbbox()[2], 0)

    def test_10_renderizacao_completa_da_identidade_visual(self):
        """Renderiza os SVGs reais e valida saídas, dimensões e transparência."""
        pipeline.main()

        for caminho, dimensoes in (
            (pipeline.PNG, (1533, 1026)),
            (pipeline.ICON_PNG, (512, 512)),
        ):
            self.assertTrue(caminho.is_file(), f"Arquivo não gerado: {caminho}")
            with Image.open(caminho) as imagem:
                imagem.load()
                self.assertEqual(imagem.size, dimensoes, str(caminho))
                self.assertEqual(imagem.mode, "RGBA", str(caminho))

        self.assertTrue(pipeline.ICO.is_file(), "Ícone ICO não foi gerado")
        with Image.open(pipeline.ICO) as imagem:
            imagem.verify()

        for nome in pipeline.CAMADAS:
            caminho = pipeline.RENDERIZADOS / f"{nome}.png"
            self.assertTrue(caminho.is_file(), f"Camada ausente: {nome}")
            with Image.open(caminho) as imagem:
                imagem.load()
                self.assertEqual(imagem.mode, "RGBA", nome)
                self.assertGreater(imagem.width, 0, nome)
                self.assertGreater(imagem.height, 0, nome)
                alpha = imagem.getchannel("A")
                self.assertIsNotNone(alpha.getbbox(), f"Camada vazia: {nome}")
                self.assertLess(alpha.getextrema()[0], 255, f"Camada sem transparência: {nome}")

        manifesto_path = pipeline.RENDERIZADOS / "folhas.json"
        self.assertTrue(manifesto_path.is_file(), "Manifesto das folhas ausente")
        manifesto = json.loads(manifesto_path.read_text(encoding="utf-8"))
        self.assertEqual(len(manifesto), 5, "A identidade deve conter cinco folhas independentes")
        for item in manifesto:
            caminho = pipeline.RENDERIZADOS / item["arquivo"]
            self.assertTrue(caminho.is_file(), f"Folha ausente: {item['arquivo']}")
            with Image.open(caminho) as imagem:
                imagem.load()
                self.assertEqual(imagem.mode, "RGBA", item["arquivo"])
                self.assertGreater(imagem.width, 0, item["arquivo"])
                self.assertGreater(imagem.height, 0, item["arquivo"])
                self.assertIsNotNone(imagem.getchannel("A").getbbox(), item["arquivo"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
