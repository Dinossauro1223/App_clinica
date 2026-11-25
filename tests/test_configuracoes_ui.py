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


    def test_telas_carregadas_dinamicamente_estao_no_pacote_windows(self):
        raiz = Path(__file__).resolve().parents[1]
        spec = (raiz / "app_clinica.spec").read_text(encoding="utf-8")
        for modulo in ("configuracoes_ui", "mobile_ui", "almox_ui",
                       "gestao_alimentar_ui", "nrs_ui", "avaliacao_ui", "pediatria_oms"):
            self.assertIn(f"'{modulo}'", spec, f"{modulo} precisa ser incluído no PyInstaller")
        self.assertIn("oms_lms_pediatricos.csv", spec)
        self.assertTrue((raiz / "dados" / "oms_lms_pediatricos.csv").is_file())

    def test_falha_de_escrita_retorna_false(self):
        with mock.patch.object(cfg.os, "makedirs", side_effect=OSError("sem permissão")):
            self.assertFalse(cfg._salvar({"aparencia": "Light"}))


if __name__ == "__main__":
    unittest.main()
