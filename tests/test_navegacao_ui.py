"""Testes unitários sem display para a barra v4 e a pilha de guias."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from navegacao_ui import BarraLateral, PilhaAbasLaterais


class WidgetFake:
    def __init__(self):
        self.destroyed = False
        self.packed = False
        self.configs = []

    def destroy(self):
        self.destroyed = True

    def pack(self, **_kwargs):
        self.packed = True

    def pack_forget(self):
        self.packed = False

    def configure(self, **kwargs):
        self.configs.append(kwargs)

    def grid_remove(self):
        pass

    def grid_configure(self, **_kwargs):
        pass

    def grid_info(self):
        return {"row": 0, "column": 1, "sticky": "ns"}

    def grid(self, **kwargs):
        self.grid_args = kwargs

    def grid_remove(self):
        self.grid_removed = True


class TestNavegacaoV4(unittest.TestCase):
    def test_widgets_reais_customtkinter_em_processo_isolado(self):
        import os
        import subprocess
        import sys
        from pathlib import Path

        codigo = r"""
import customtkinter as ctk
from navegacao_ui import BarraLateral, PilhaAbasLaterais

root = ctk.CTk()
root.geometry("900x600")
root.grid_columnconfigure(1, weight=1)
host = ctk.CTkFrame(root)
host.grid(row=0, column=1, sticky="nsew")
pilha = PilhaAbasLaterais(host)
pilha.pack(fill="both", expand=True)
base = pilha.pagina_atual
pilha.abrir("Pacientes")
root.update()
assert pilha.quantidade == 1
assert pilha.fechar_ultima() is base
barra = BarraLateral(
    root, [("CLÍNICA", [("👥", "Pacientes", lambda: None)])],
    ("⚙️", "Configurações", lambda: None), persistir=False
)
root.update()
barra.definir_fixa(True)
root.update()
assert int(barra.cget("width")) == 250
barra.definir_fixa(False)
root.update()
assert int(barra.cget("width")) == 58
assert not barra.rolagem._scrollbar.grid_info(), "scrollbar deveria liberar a largura no modo recolhido"
barra._abrir(True)
root.update()
assert barra.rolagem._scrollbar.grid_info(), "scrollbar deveria reaparecer no modo expandido"
barra._abrir(False)
root.update()
# Os formulários de mapa e fichas devem criar e fechar guias, não Toplevels.
from types import SimpleNamespace
from gestao_alimentar_ui import _PainelJanela
from mapa_ui import _Janela

class AppFake:
    def __init__(self, pilha):
        self.pilha = pilha
        self.area_principal = pilha.pagina_atual
    def abrir_painel_lateral(self, titulo, comando):
        frame = self.pilha.abrir(titulo)
        self.area_principal = frame
        comando()
        return frame
    def fechar_painel_lateral(self, frame):
        self.area_principal = self.pilha.fechar(frame)

app = AppFake(pilha)
ficha = _PainelJanela(app, "Ficha técnica")
assert pilha.quantidade == 1
ficha.destroy()
assert pilha.quantidade == 0

mapa_dialogo = _Janela(SimpleNamespace(app=app), "Registro do mapa", "860x780")
assert pilha.quantidade == 1
mapa_dialogo.destroy()
assert pilha.quantidade == 0
# DialogoAssociacoesExames também deve ser uma guia lateral.
import os
import sqlite3
import tempfile
from contextlib import closing
from ambulatorial_ui import DialogoAssociacoesExames
fd, caminho_db = tempfile.mkstemp(suffix=".db")
os.close(fd)
try:
    with closing(sqlite3.connect(caminho_db)) as conn:
        conn.execute("CREATE TABLE Exames_Catalogo (id_exame TEXT, nome_amigavel TEXT)")
        conn.commit()
    dialogo_exames = DialogoAssociacoesExames(app, caminho_db)
    assert pilha.quantidade == 1
    dialogo_exames.destroy()
    assert pilha.quantidade == 0
finally:
    os.remove(caminho_db)

root.destroy()
"""
        raiz = Path(__file__).resolve().parents[1]
        resultado = subprocess.run(
            [sys.executable, "-c", codigo], cwd=raiz,
            env={**os.environ, "PYTHONPATH": str(raiz)},
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)

    def test_fontes_de_interface_nao_criam_janelas_secundarias(self):
        from pathlib import Path
        raiz = Path(__file__).resolve().parents[1]
        for nome in ("main.py", "ambulatorial_ui.py", "mapa_ui.py",
                     "gestao_alimentar_ui.py", "condutas_alta_ui.py"):
            fonte = (raiz / nome).read_text(encoding="utf-8")
            self.assertNotIn("CTkToplevel", fonte, f"{nome} ainda abre janela secundária")

    def test_dimensoes_padronizadas_da_barra(self):
        self.assertEqual(BarraLateral.RECOLHIDA, 58)
        self.assertEqual(BarraLateral.EXPANDIDA, 250)

    def test_icones_ficam_centralizados_no_modo_recolhido(self):
        botao = WidgetFake()
        titulo = WidgetFake()
        rodape = WidgetFake()
        barra = SimpleNamespace(
            aberta=False, itens={"Pacientes": (WidgetFake(), botao, "👥")},
            titulos=[(titulo, "CLÍNICA")], lbl_titulo=WidgetFake(),
            lbl_rodape=rodape, rodape="© NutriLab",
        )
        BarraLateral._rotular(barra, False)
        self.assertEqual(botao.configs[-1]["text"], "👥")
        self.assertEqual(botao.configs[-1]["anchor"], "center")
        self.assertEqual(titulo.configs[-1]["text"], "•")


    def test_scrollbar_nao_desloca_icones_recolhidos_e_reaparece_expandido(self):
        scrollbar = WidgetFake()
        barra = SimpleNamespace(
            aberta=False, itens={}, titulos=[], lbl_titulo=WidgetFake(),
            lbl_rodape=WidgetFake(), rodape="© NutriLab",
            rolagem=SimpleNamespace(_scrollbar=scrollbar),
            _scrollbar_grid={"row": 0, "column": 1, "sticky": "ns"},
        )
        BarraLateral._rotular(barra, False)
        self.assertTrue(scrollbar.grid_removed)
        BarraLateral._rotular(barra, True)
        self.assertEqual(scrollbar.grid_args, {"row": 0, "column": 1, "sticky": "ns"})

    def test_rotulos_aparecem_alinhados_no_modo_expandido(self):
        botao = WidgetFake()
        barra = SimpleNamespace(
            aberta=False, itens={"Pacientes": (WidgetFake(), botao, "👥")},
            titulos=[], lbl_titulo=WidgetFake(), lbl_rodape=WidgetFake(),
            rodape="© NutriLab",
        )
        BarraLateral._rotular(barra, True)
        self.assertEqual(botao.configs[-1]["text"], "  👥    Pacientes")
        self.assertEqual(botao.configs[-1]["anchor"], "w")

    def test_fixacao_define_largura_da_coluna_e_persiste_preferencia(self):
        app = Mock()
        salvar = Mock()
        barra = SimpleNamespace(
            fixa=False, app=app, EXPANDIDA=250, RECOLHIDA=58,
            _ler_preferencias=lambda: {"aparencia": "system"},
            _salvar_preferencias=salvar, _abrir=Mock(),
        )
        BarraLateral.definir_fixa(barra, True)
        app.grid_columnconfigure.assert_called_once_with(0, minsize=250)
        self.assertTrue(salvar.call_args.args[0]["barra_fixa"])
        barra._abrir.assert_called_once_with(True)

    def test_pilha_fecha_somente_a_pagina_principal_atual(self):
        base, pagina = WidgetFake(), WidgetFake()
        pilha = SimpleNamespace(_ativa=pagina, _base=base, _titulo="Mapa")
        resultado = PilhaAbasLaterais.fechar_ultima(pilha)
        self.assertIs(resultado, base)
        self.assertTrue(pagina.destroyed)
        self.assertTrue(base.packed)
        self.assertEqual(PilhaAbasLaterais.quantidade.fget(pilha), 0)

    def test_pilha_nao_expoe_navegacao_de_historico(self):
        from pathlib import Path
        raiz = Path(__file__).resolve().parents[1]
        fonte = (raiz / "navegacao_ui.py").read_text(encoding="utf-8")
        classe = fonte[fonte.index("class PilhaAbasLaterais"):]
        self.assertNotIn("self._nav", classe)
        self.assertNotIn("self._abas", classe)
        self.assertIn("Substitui a página principal atual", classe)


if __name__ == "__main__":
    unittest.main()
