# -*- coding: utf-8 -*-
"""Fumaça da tela Avaliação e evolução, da barra lateral fluida, da caixa de seleção e das configurações,
com widgets simulados (reaproveita os de test_ui_smoke). Pega erros de lógica e chamadas inexistentes;
não valida a aparência real: isso se confere abrindo o programa."""
import gc
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from test_ui_smoke import W, Combo, Frame, AppFalso, MB  # noqa: E402  (instala customtkinter/tkinter falsos)

_tk, _ctk = sys.modules["tkinter"], sys.modules["customtkinter"]
_ponteiro, _foco = [10, 10], [None]


class Paned(W):
    sash = 0

    def add(self, painel, **kw):
        if painel.master is not self:  # regra do Tk: o painel precisa ser filho direto do divisor
            raise ValueError("o painel do divisor precisa ser filho direto dele")

    def sash_coord(self, i):
        return (self.sash, 0)

    def sash_place(self, i, x, y):
        self.sash = x

    def winfo_width(self):
        return 1000


class _Entrada:  # no lugar de tk.Entry / tk.Text / ttk.Entry
    pass


_tk.PanedWindow, _tk.Entry, _tk.Text, _tk.TclError = Paned, _Entrada, _Entrada, RuntimeError
for _n in ("Entry", "Combobox"):
    if not hasattr(_tk.ttk, _n):
        setattr(_tk.ttk, _n, _Entrada)
_nada = lambda s, *a, **k: None  # noqa: E731
for _n, _f in {"grid_columnconfigure": _nada, "grid_rowconfigure": _nada, "pack_propagate": _nada, "transient": _nada,
               "clipboard_clear": _nada, "clipboard_append": _nada, "wait_window": _nada, "lift": _nada,
               "tkraise": _nada, "after_cancel": _nada, "winfo_rootx": lambda s: 0,
               "winfo_rooty": lambda s: 0, "winfo_height": lambda s: 900, "winfo_width": lambda s: 1300,
               "winfo_pointerxy": lambda s: tuple(_ponteiro), "focus_get": lambda s: _foco[0]}.items():
    if not hasattr(W, _n):
        setattr(W, _n, _f)
def _place_estrito(self, **k):
    """Como o customtkinter real: width/height só no construtor ou em configure(), nunca no place()."""
    if "width" in k or "height" in k:
        raise ValueError("'width' and 'height' arguments must be passed to the constructor of the widget, not the place method")
    self.opts.setdefault("_place", {}).update(k)


W.place = W.place_configure = _place_estrito
Combo._open_dropdown_menu = lambda self: setattr(self, "aberta", True)
Combo.select = lambda self: self.set("1")
_ctk.CTkImage = lambda *a, **k: ("imagem", a, k)
try:
    import mapa_db as mdb  # noqa: E402
    import pep_db as pep  # noqa: E402
    import tema  # noqa: E402
    import avaliacao_ui as ui  # noqa: E402
    import configuracoes_ui  # noqa: E402
    from PIL import Image as PILImage  # noqa: E402
except ImportError as erro:  # ex.: Pillow ausente
    raise unittest.SkipTest(str(erro))


class AppTeste(AppFalso):
    def __init__(self, prefs):
        super().__init__()
        self.prefs, self.paginas = prefs, []

    def mostrar_pagina(self, pagina):
        self.paginas.append(pagina)


class Base(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.pasta = tempfile.mkdtemp()
        self.caminho_prefs = os.path.join(self.pasta, "prefs.json")
        mdb.inicializar(self.db)
        con = mdb.conectar(self.db)
        try:
            con.execute("INSERT INTO Mapa_Suplementos(nome, modulo, emb_un, kcal_100, ptn_100) "
                        "VALUES('Fórmula Teste', 'Fórmula completa', 'ml', 150, 6)")
            con.commit()
        finally:
            con.close()
        MB.chamadas.clear()
        MB.resposta = True
        _ponteiro[:], _foco[0] = [10, 10], None
        self.app = AppTeste(tema.Preferencias(self.caminho_prefs))

    def tearDown(self):
        gc.collect()
        os.remove(self.db)
        shutil.rmtree(self.pasta, ignore_errors=True)


class TestTelaAvaliacao(Base):
    def setUp(self):
        super().setUp()
        self.ui = ui.AvaliacaoUI(self.app, self.db, self.app.area_principal)
        self.ui.mostrar()

    def _preencher(self, **campos):
        for k, v in campos.items():
            w = self.ui.w[k]
            if isinstance(w, Combo):
                w.set(v)
            else:
                w.delete(0, "end")
                w.insert(0, v)

    def test_montada_uma_vez_e_pagina_trocada_sem_recriar(self):
        divisor = self.ui.divisor
        self.ui.mostrar()
        self.assertIs(self.ui.divisor, divisor)
        self.assertEqual(self.app.paginas, [self.app.area_principal] * 2)

    def test_calculo_ao_vivo_com_edema_e_amputacao(self):
        self.assertIn("Informe o paciente", self.ui.chip.opts["text"])
        self._preencher(paciente="Paciente Teste", sexo="Mulher", cor="Branca", idade="68", aj="49", pb="17,5",
                        edema="+++ raiz da coxa (5,5 kg)")
        self.ui.w["amp_Perna abaixo do joelho"].set("1")
        self.ui.atualizar()
        self.assertEqual(self.ui.kpi["peso"].opts["text"], "31,1 kg")  # (34,8 − 5,5) / (1 − 0,059)
        self.assertIn("Novo paciente", self.ui.chip.opts["text"])
        self.assertIn("NOVO PACIENTE", self.ui.saida.get())

    def test_teclado_tab_e_setas(self):
        self.assertIsInstance(self.ui.w["sexo"], tema.Selecao)
        self.assertIn("<Tab>", self.ui.w["obs"].bindings)  # caixa de texto: Tab passa ao próximo campo
        self.assertIn("<Shift-Tab>", self.ui.w["cx"].bindings)
        self.assertIn("<Down>", self.ui.w["sexo"].bindings)

    def test_divisor_lembra_a_posicao(self):
        self.ui.divisor.sash = 700
        self.ui._salvar_divisor()
        self.assertEqual(tema.Preferencias(self.caminho_prefs).get("avaliacao_divisor"), 0.7)
        self.ui.divisor.sash = 0
        self.ui._restaurar_divisor()
        self.assertEqual(self.ui.divisor.sash, 700)

    def test_suplementos_assinatura_e_evolucao_anterior(self):
        self._preencher(paciente="Paciente Teste", sexo="Mulher", cor="Branca", idade="50", peso="60", altura="160")
        self.ui.sel_sup.set("Fórmula Teste")
        self.ui.qtd_sup.insert(0, "400")
        self.ui._add_sup()
        self.assertIn("600 kcal", self.ui.res_sup.opts["text"])
        self.assertIn("40% da meta", self.ui.res_sup.opts["text"])
        self.assertIn("Suplementação: Fórmula Teste 400 ml/dia (600 kcal; 24,0 g PTN)", self.ui.saida.get())
        pendente = next(k for k in self.ui.catalogo if k.endswith("(ficha pendente)"))
        self.ui.sel_sup.set(pendente)
        self.ui.qtd_sup.insert(0, "200")
        self.ui._add_sup()
        self.assertIn("ficha pendente", self.ui.res_sup.opts["text"])
        uid = pep.criar_usuario(self.db, "ana", "Ana Teste", "12345", "segredo1")
        self.ui.usuario = pep.autenticar(self.db, uid, "segredo1")
        self.ui.assinar()
        self.assertEqual(pep.ultima_evolucao(self.db, "Paciente Teste")["cabecalho"]["peso"], 60.0)
        self.ui.atualizar()
        self.assertIn("Evolução anterior em", self.ui.chip.opts["text"])
        self.assertIn("Assinatura eletrônica: Ana Teste – CRN 12345 –", self.ui.saida.get())
        self.ui._limpar_sups()
        self.assertEqual(self.ui.res_sup.opts["text"], "Nenhum suplemento adicionado.")

    def test_construir_recomeca_limpo_se_falhar_no_meio(self):
        nova = ui.AvaliacaoUI(self.app, self.db, Frame())
        with mock.patch.object(ui.AvaliacaoUI, "_painel", side_effect=RuntimeError("falha")):
            with self.assertRaises(RuntimeError):
                nova.construir()
        self.assertFalse(nova.pronto)
        nova.construir()
        self.assertTrue(nova.pronto)
        self.assertEqual(len([c for c in nova.raiz.children if isinstance(c, Paned) and not c.destroyed]), 1)

    def test_erro_ao_montar_mostra_mensagem_e_nao_troca_de_pagina(self):
        with mock.patch.object(self.ui, "construir", side_effect=RuntimeError("falha")):
            antes = len(self.app.paginas)
            self.ui.mostrar()
        self.assertEqual(MB.chamadas[-1][0], "showerror")
        self.assertEqual(len(self.app.paginas), antes)

    def test_fake_recusa_width_no_place(self):  # garante que o teste simulado é tão estrito quanto o customtkinter
        with self.assertRaises(ValueError):
            W().place(x=0, width=10)

    def test_sem_dados_nao_assina(self):
        self.ui.assinar()
        self.assertEqual(MB.chamadas[-1][0], "showwarning")

    def test_login_e_carimbo(self):
        d = ui._Login(self.app, self.db)  # etapa do hospital
        pep.definir_senha_hospital(self.db, "hospital1")
        d._novo()
        pep.criar_usuario(self.db, "bia", "Bia Teste", "999", "segredo2")
        d._usuarios()
        buf = io.BytesIO()
        PILImage.new("RGB", (8, 8), "white").save(buf, "PNG")
        user = {"id": 1, "nome_completo": "Bia Teste", "crn": "999", "assinatura": buf.getvalue()}
        with mock.patch.object(ui, "_Login", lambda *a: mock.Mock(usuario=user)):
            self.ui._entrar()
        self.assertIn("CRN 999", self.ui.carimbo.opts["text"])


class TestComponentes(Base):
    SECOES = [("AMBULATORIAL", [("☺", "Pacientes", "Lista de pacientes", None)]),
              ("HOSPITALAR", [("▦", "Mapa nutricional", "Mapa dos leitos", None)])]

    def _barra(self, chamadas):
        secoes = [(n, [(i, t, d, (lambda t=t: chamadas.append(t))) for i, t, d, _ in itens]) for n, itens in self.SECOES]
        return tema.BarraLateral(self.app, "NutriLab", secoes, ("⚙", "Configurações", "Ajustes", lambda: chamadas.append("cfg")),
                                 "© 2026 Neis B. A. & Thiago S. S.", self.app.prefs)

    def test_barra_abre_ao_passar_o_mouse_e_fecha_ao_sair(self):
        barra = self._barra([])
        self.assertFalse(barra.aberta)
        self.assertEqual(barra.opts["width"], tema.RAIL)
        self.assertEqual(barra.itens["Pacientes"][1].opts["text"], "☺")  # fina: só o ícone
        barra._vigiar()  # mouse sobre a barra
        self.assertTrue(barra.aberta)
        self.assertEqual(barra.opts["width"], tema.ABERTA)
        self.assertIn("Pacientes", barra.itens["Pacientes"][1].opts["text"])
        self.assertIn("Neis B. A. & Thiago S. S.", barra.lbl_rodape.opts["text"])
        _ponteiro[:] = [3000, 10]
        barra._vigiar()
        barra._vigiar()
        self.assertFalse(barra.aberta)
        self.assertEqual(barra.opts["width"], tema.RAIL)

    def test_barra_marca_item_chama_funcao_e_tem_descricao(self):
        chamadas = []
        barra = self._barra(chamadas)
        barra.itens["Mapa nutricional"][1].opts["command"]()
        barra.itens["Configurações"][1].opts["command"]()
        self.assertEqual(chamadas, ["Mapa nutricional", "cfg"])
        self.assertEqual(barra.itens["Configurações"][0].opts["fg_color"], tema.LARANJA)
        self.assertEqual(barra.itens["Mapa nutricional"][0].opts["fg_color"], "transparent")
        self.assertIn("<Enter>", barra.itens["Pacientes"][1].bindings)  # balão de descrição

    def test_fixar_lembra_e_atalho_do_apostrofo_respeita_campos_de_texto(self):
        barra = self._barra([])
        barra.alternar()
        self.assertTrue(barra.fixa and barra.aberta)
        self.assertIs(tema.Preferencias(self.caminho_prefs).get("barra_fixa"), True)
        _foco[0] = _Entrada()  # digitando em um campo: o apóstrofo não aciona a barra
        self.assertIsNone(barra._atalho_apostrofo(None))
        self.assertTrue(barra.fixa)
        _foco[0] = None
        self.assertEqual(barra._atalho_apostrofo(None), "break")
        self.assertFalse(barra.fixa)

    def test_selecao_setas_e_limites(self):
        escolhas = []
        s = tema.Selecao(Frame(), ["A", "B", "C"], command=escolhas.append)
        self.assertEqual(s.get(), "A")
        self.assertIn("<Down>", s.bindings)
        for _ in range(3):
            self.assertEqual(s._mover(1), "break")
        self.assertEqual((s.get(), escolhas), ("C", ["B", "C", "C"]))
        s._mover(-5)
        self.assertEqual(s.get(), "A")  # para no primeiro item, sem dar a volta

    def test_preferencias_ignoram_arquivo_quebrado(self):
        tema.Preferencias(self.caminho_prefs).set("x", 0.5)
        self.assertEqual(tema.Preferencias(self.caminho_prefs).get("x"), 0.5)
        with open(self.caminho_prefs, "w") as f:
            f.write("{quebrado")
        self.assertEqual(tema.Preferencias(self.caminho_prefs).get("x", "padrão"), "padrão")

    @mock.patch.object(_ctk, "CTkSegmentedButton", Combo)  # só neste teste: não afeta os falsos dos outros testes
    @mock.patch.object(_ctk, "CTkSwitch", Combo, create=True)
    def test_configuracoes_abre_na_secao_da_aba_atual(self, *_):
        self.app.menu_lateral = self._barra([])
        self.app.mapa = mock.Mock()
        self.app.menu_lateral.marcar("Mapa nutricional")
        configuracoes_ui.ConfiguracoesUI(self.app).mostrar()
        seg = next(c for c in self.app.area_principal.children if isinstance(c, Combo))
        self.assertEqual(seg.get(), "Mapa e antropometria")
        self.app.menu_lateral.marcar("Pacientes")
        configuracoes_ui.ConfiguracoesUI(self.app).mostrar()
        seg = next(c for c in self.app.area_principal.children if isinstance(c, Combo))
        self.assertEqual(seg.get(), "Aparência")


if __name__ == "__main__":
    unittest.main()
