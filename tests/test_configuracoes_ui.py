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


    def test_configuracoes_admin_tem_grupos_e_blocos_recolhiveis(self):
        codigo = Path(cfg.__file__).read_text(encoding="utf-8")
        self.assertIn("def _grupo", codigo)
        self.assertIn("def _recolher_cards_config", codigo)
        for grupo in ("Contas e permissões", "Configurações clínicas", "Equipe de atendimento",
                      "Refeições e custos", "Dados e recuperação"):
            self.assertIn(grupo, codigo)
        self.assertIn("card_aberto=None", codigo)

    def test_perfis_de_contas_compartilhadas_sao_copa_e_almoxarifado(self):
        self.assertEqual(cfg.PERFIS_COMPARTILHADOS, {
            "Copa": "copa", "Almoxarifado": "estoque_almox"
        })
        codigo = Path(cfg.__file__).read_text(encoding="utf-8")
        self.assertIn("def _criar_conta_compartilhada", codigo)
        self.assertIn("def _atualizar_contas_compartilhadas", codigo)
        self.assertIn("def _alterar_estado_conta", codigo)
        self.assertIn("def _redefinir_senha_conta", codigo)

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
        self.assertIn("oms_classificacoes_pediatricas.json", spec)
        self.assertTrue((raiz / "dados" / "oms_classificacoes_pediatricas.json").is_file())

    def test_falha_de_escrita_retorna_false(self):
        with mock.patch.object(cfg.os, "makedirs", side_effect=OSError("sem permissão")):
            self.assertFalse(cfg._salvar({"aparencia": "Light"}))


if __name__ == "__main__":
    unittest.main()
