"""Testes das preferências locais exibidas pela tela de Configurações."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import configuracoes_ui as cfg


class TestPreferenciasConfiguracoes(unittest.TestCase):
    def test_opcoes_de_aparencia_sao_mapeadas(self):
        self.assertEqual(cfg.ConfiguracoesUI.OPCOES, {
            "Claro": "Light", "Escuro": "Dark", "Sistema": "System"
        })

    def test_le_e_salva_preferencias_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "perfil" / "preferencias.json"
            with mock.patch.object(cfg, "CAMINHO", str(caminho)):
                self.assertEqual(cfg._ler(), {})
                self.assertTrue(cfg._salvar({"aparencia": "Dark"}))
                self.assertEqual(cfg._ler(), {"aparencia": "Dark"})
                dados = json.loads(caminho.read_text(encoding="utf-8"))
                self.assertEqual(dados["aparencia"], "Dark")

    def test_json_invalido_ou_arquivo_ausente_retorna_vazio(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "preferencias.json"
            with mock.patch.object(cfg, "CAMINHO", str(caminho)):
                self.assertEqual(cfg._ler(), {})
                caminho.write_text("{inválido", encoding="utf-8")
                self.assertEqual(cfg._ler(), {})

    def test_falha_de_escrita_retorna_false(self):
        with mock.patch.object(cfg.os, "makedirs", side_effect=OSError("sem permissão")):
            self.assertFalse(cfg._salvar({"aparencia": "Light"}))


if __name__ == "__main__":
    unittest.main()
