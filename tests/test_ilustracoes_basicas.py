# -*- coding: utf-8 -*-
"""Smoke tests para ilustracoes clínicas geradas em código."""
import unittest
import ilustracoes


class TestIlustracoesBasicas(unittest.TestCase):
    def test_ascite_retorna_imagem(self):
        im = ilustracoes.ascite()
        self.assertIsNotNone(im)
        self.assertGreater(im.width, 0)
        self.assertGreater(im.height, 0)

    def test_edema_nivel_limite(self):
        for nivel in (0, 1, 2, 3, 4, 10, -2):
            im = ilustracoes.edema(nivel)
            self.assertEqual(im.size, (240, 360))

    def test_amputacao_variantes(self):
        for local in ("Mão", "Antebraço + mão", "Braço inteiro", "Pé", "Perna abaixo do joelho", "Perna inteira"):
            im = ilustracoes.amputacao(local, f"Ilustração de {local}")
            self.assertEqual(im.size, (240, 360))


if __name__ == "__main__":
    unittest.main()
