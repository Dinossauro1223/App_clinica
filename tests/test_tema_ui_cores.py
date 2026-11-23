"""Garante que as telas operacionais usem a paleta dinâmica do tema."""
import re
import unittest
from pathlib import Path

import tema


class TestTemaGlobal(unittest.TestCase):
    def test_telas_nao_contem_cores_hex_fixas(self):
        raiz = Path(__file__).resolve().parents[1]
        modulos = (
            "main.py", "tela_boas_vindas.py", "ambulatorial_ui.py",
            "gestao_alimentar_ui.py", "mapa_ui.py", "condutas_alta_ui.py",
            "almox_ui.py", "mobile_ui.py", "configuracoes_ui.py",
        )
        padrao = re.compile(r"""["']#[0-9a-fA-F]{3,8}["']""")
        for modulo in modulos:
            fonte = (raiz / modulo).read_text(encoding="utf-8")
            self.assertIsNone(padrao.search(fonte), f"{modulo} ainda contém cor fixa")

    def test_telas_nao_usam_cores_nomeadas_fixadas_em_cartoes(self):
        raiz = Path(__file__).resolve().parents[1]
        modulos = (
            "gestao_alimentar_ui.py", "mapa_ui.py", "condutas_alta_ui.py",
            "almox_ui.py",
        )
        padrao = re.compile(r"""(?:fg_color|background)\s*=\s*["'](?:white|black)["']""", re.IGNORECASE)
        for modulo in modulos:
            fonte = (raiz / modulo).read_text(encoding="utf-8")
            self.assertIsNone(padrao.search(fonte), f"{modulo} ainda fixa branco/preto")

    def test_paleta_cobre_estados_de_erro_e_informacao(self):
        for nome in ("ERRO", "ERRO_HOVER", "AZUL", "AZUL_HOVER"):
            valor = getattr(tema, nome)
            self.assertEqual(len(valor), 2)
            self.assertNotEqual(valor[0], valor[1])


if __name__ == "__main__":
    unittest.main()
