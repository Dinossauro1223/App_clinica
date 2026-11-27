# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import midias_usuario as midias


class TestMidiasUsuario(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.origem = self.home / "imagem.png"
        Image.new("RGB", (40, 30), "white").save(self.origem)
        self.patch_home = patch.object(Path, "home", return_value=self.home)
        self.patch_home.start()
        self.addCleanup(self.patch_home.stop)

    def test_salva_e_resolve_escala_persistente(self):
        destino = midias.salvar_imagem("escalas", "bristol", self.origem)
        self.assertTrue(destino.is_file())
        self.assertEqual(midias.resolver_imagem("escalas", "bristol"), destino)
        self.assertEqual(destino.parent, self.home / ".nutrilab" / "midias" / "escalas")

    def test_substitui_imagem_sem_manter_extensao_antiga(self):
        primeira = midias.salvar_imagem("orientacoes", "ENT-001", self.origem)
        jpg = self.home / "nova.jpg"
        Image.new("RGB", (20, 20), "black").save(jpg)
        segunda = midias.salvar_imagem("orientacoes", "ENT-001", jpg)
        self.assertEqual(segunda.suffix, ".jpg")
        self.assertFalse(primeira.exists())
        self.assertEqual(midias.resolver_imagem("orientacoes", "ENT-001"), segunda)

    def test_rejeita_formato_nao_suportado(self):
        txt = self.home / "imagem.txt"
        txt.write_text("não é imagem", encoding="utf-8")
        with self.assertRaises(ValueError):
            midias.salvar_imagem("escalas", "bristol", txt)

    def test_rejeita_identificador_vazio(self):
        with self.assertRaises(ValueError):
            midias.salvar_imagem("orientacoes", "", self.origem)


if __name__ == "__main__":
    unittest.main()
