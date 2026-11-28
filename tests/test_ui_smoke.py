# -*- coding: utf-8 -*-
"""Teste de fumaça da interface (mapa_ui) com widgets simulados.

Não abre janelas: injeta versões falsas de tkinter/customtkinter que guardam o estado
dos campos, e percorre os fluxos principais (mapa, registro, histórico, leitos,
suplementos, gráficos). Pega erros de lógica e chamadas inexistentes; NÃO valida a
aparência real nem opções específicas de cada widget do CustomTkinter.
"""
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))


# ------------------------------------------------------------------ widgets falsos
class W:
    def __init__(self, *args, **kw):
        self.master = args[0] if args else kw.get("master")
        self.opts = dict(kw)
        self.children, self.bindings, self.destroyed = [], {}, False
        self.packed = False
        if isinstance(self.master, W):
            self.master.children.append(self)
        self._text, self._val = "", ""

    def configure(self, **kw):
        self.opts.update(kw)

    config = configure

    def cget(self, k):
        return self.opts.get(k)

    def pack(self, *a, **kw):
        self.packed = True

    def pack_forget(self):
        self.packed = False

    def grid(self, *a, **kw):
        pass

    def bind(self, ev, fn, add=None):
        self.bindings[ev] = fn

    def after(self, ms, fn=None, *a):
        return "id"

    def destroy(self):
        self.destroyed = True
        for c in self.children:
            c.destroy()

    def winfo_children(self):
        return [c for c in self.children if not c.destroyed]

    def winfo_exists(self):
        return not self.destroyed

    def focus_set(self):
        pass

    def icursor(self, *args):
        pass

    def winfo_width(self):
        return 1300

    def winfo_screenheight(self):
        return 900

    def title(self, *a):
        pass

    def geometry(self, *a):
        pass

    def attributes(self, *a):
        pass

    def protocol(self, *a):
        pass

    def lift(self):
        pass

    def focus_force(self):
        pass

    def grab_set(self):
        pass

    def update_idletasks(self):
        pass

    def yview(self, *a):
        pass

    def set(self, *a):  # Scrollbar.set (Combo/Seg sobrescrevem)
        pass

    def heading(self, *a, **kw):
        pass

    def column(self, *a, **kw):
        pass

    def tag_configure(self, *a, **kw):
        pass


class Entry(W):
    def get(self):
        return self._text

    def insert(self, i, t):
        self._text = (str(t) + self._text) if i == 0 else self._text + str(t)

    def delete(self, a, b=None):
        self._text = ""


class Combo(W):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._text = kw.get("values", [""])[0] if False else ""

    def get(self):
        return self._text

    def set(self, v):
        self._text = v


class Seg(W):
    def get(self):
        return self._val

    def set(self, v):
        self._val = v

    def click(self, v):
        self._val = v
        if self.opts.get("command"):
            self.opts["command"](v)


class Textbox(W):
    def get(self, a=None, b=None):
        return self._text

    def insert(self, i, t):
        self._text += t

    def delete(self, a, b=None):
        self._text = ""


class Tree(W):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.items, self.tags, self._sel, self._n = {}, {}, [], 0

    def insert(self, parent, index, iid=None, values=(), tags=()):
        iid = iid if iid is not None else f"I{self._n}"
        self._n += 1
        self.items[iid] = tuple(values)
        self.tags[iid] = tuple(tags)
        return iid

    def delete(self, *ids):
        for i in ids:
            self.items.pop(i, None)
            self.tags.pop(i, None)

    def get_children(self, *a):
        return list(self.items)

    def selection(self):
        return list(self._sel)

    def selection_set(self, i):
        self._sel = [i]

    def xview(self, *a):
        pass


class Canvas(W):
    """tk.Canvas falso: guarda as imagens e as formas desenhadas e a posição da rolagem horizontal."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.itens, self.rolagem = [], 0.0
        self.formas, self._n = {}, 0          # número do item -> {"t": tipo, "c": coordenadas, ...opções}

    def _nova(self, tipo, coords, kw):
        self._n += 1
        self.formas[self._n] = {"t": tipo, "c": tuple(coords), **kw}
        return self._n

    def create_image(self, x, y, **kw):
        self.itens.append((x, y, kw.get("image")))
        return len(self.itens)

    def create_rectangle(self, *c, **kw):
        return self._nova("ret", c, kw)

    def create_polygon(self, *c, **kw):
        return self._nova("poli", c, kw)

    def create_line(self, *c, **kw):
        return self._nova("linha", c, kw)

    def create_text(self, *c, **kw):
        return self._nova("texto", c, kw)

    def create_oval(self, *c, **kw):
        return self._nova("oval", c, kw)

    def create_arc(self, *c, **kw):
        return self._nova("arco", c, kw)

    def coords(self, item, *c):
        self.formas[item]["c"] = tuple(c)

    def itemconfigure(self, item, **kw):
        self.formas[item].update(kw)

    def itemcget(self, item, chave):
        return self.formas[item].get(chave, "normal" if chave == "state" else "")

    def delete(self, *a):
        if a and a[0] != "all":
            for item in a:
                self.formas.pop(item, None)
            return
        self.itens, self.formas = [], {}

    def bbox(self, item):
        c = self.formas[item]["c"]
        return min(c[0::2]), min(c[1::2]), max(c[0::2]), max(c[1::2])

    def find_overlapping(self, x0, y0, x1, y1):
        achados = []
        for item, f in self.formas.items():
            a, b, c, d = self.bbox(item)
            if a <= x1 and c >= x0 and b <= y1 and d >= y0:
                achados.append(item)
        return tuple(achados)

    def tag_raise(self, item):
        pass

    def canvasx(self, x):
        return x

    canvasy = canvasx

    def winfo_height(self):
        return 400

    def xview_moveto(self, fracao):
        self.rolagem = fracao

    def after_cancel(self, i):
        pass


class Fonte:
    """tkinter.font.Font falso: cada letra mede 0,55 do tamanho."""

    def __init__(self, root=None, family="Fonte Falsa", size=12, weight="normal"):
        self.family, self.size, self.weight = family, size, weight

    def measure(self, texto):
        return len(texto) * abs(self.size) * 0.55

    def actual(self, opcao=None):
        return self.family if opcao == "family" else {"family": self.family}


class IntVar:
    def __init__(self, value=0):
        self.v = value

    def get(self):
        return self.v

    def set(self, v):
        self.v = v


class Frame(W):
    pass


class Image:
    def __init__(self, **kw):
        self.kw = kw


class Caixas:
    """messagebox falso: registra as chamadas e responde 'sim'."""

    def __init__(self):
        self.chamadas = []
        self.resposta = True

    def _reg(self, nome):
        def f(titulo, msg, **kw):
            self.chamadas.append((nome, titulo, msg))
            return self.resposta
        return f

    def __getattr__(self, nome):
        return self._reg(nome)


def instalar_falsos():
    ctk = types.ModuleType("customtkinter")
    for n in ("CTkFrame", "CTkLabel", "CTkButton", "CTkCheckBox", "CTkScrollableFrame", "CTkToplevel"):
        setattr(ctk, n, type(n, (W,), {}))
    ctk.CTkEntry, ctk.CTkComboBox, ctk.CTkSegmentedButton, ctk.CTkTextbox = Entry, Combo, Seg, Textbox
    ctk.CTkFont = lambda **kw: ("font", kw)
    ctk.CTkImage = Image
    tk = types.ModuleType("tkinter")
    tk.TclError = type("TclError", (Exception,), {})
    tk.IntVar, tk.Canvas = IntVar, Canvas
    ttk = types.ModuleType("tkinter.ttk")
    ttk.Treeview, ttk.Scrollbar = Tree, W
    ttk.Style = type("Style", (), {"configure": lambda s, *a, **k: None, "map": lambda s, *a, **k: None,
                                   "theme_use": lambda s, *a: None})
    fonte = types.ModuleType("tkinter.font")
    fonte.Font = Fonte
    fonte.nametofont = lambda nome, root=None: Fonte(root=root, family="Fonte Falsa", size=-12)
    tk.font = fonte
    mb = Caixas()
    fd = types.SimpleNamespace(asksaveasfilename=lambda **kw: fd.destino, askdirectory=lambda **kw: fd.pasta,
                               destino="", pasta="")
    tk.ttk, tk.messagebox, tk.filedialog = ttk, mb, fd
    sys.modules.update({"customtkinter": ctk, "tkinter": tk, "tkinter.ttk": ttk, "tkinter.messagebox": mb,
                        "tkinter.filedialog": fd, "tkinter.font": fonte})
    return mb, fd


MB, FD = instalar_falsos()
import mapa_db as mdb  # noqa: E402
import mapa_ui  # noqa: E402
import mapa_export as mex  # noqa: E402
from fake_fpdf import FakePDF  # noqa: E402


class AppFalso(W):
    def __init__(self):
        super().__init__()
        self.area_principal = Frame()

    def limpar_area_principal(self):
        self.area_principal.destroy()   # como no main.py: os widgets da tela anterior deixam de existir
        self.area_principal = Frame()


class TestInterface(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        mdb.inicializar(self.db)
        self.setor = mdb.criar_setor(self.db, "Setor de teste")
        mdb.criar_leitos_sequencia(self.db, self.setor, "L", 1, 4)
        self.app = AppFalso()
        self.ui = mapa_ui.MapaUI(self.app, self.db, os.path.dirname(self.db))
        self.ui.id_setor = self.setor
        MB.chamadas.clear()
        MB.resposta = True

    def tearDown(self):
        os.remove(self.db)

    def _primeiro_leito(self):
        return self.ui.linhas[0]

    def test_mapa_lista_leitos_e_vagos(self):
        self.ui.mostrar_mapa()
        self.assertEqual(len(self.ui.tree.items), 4)
        self.assertTrue(all(v[4] == "— vago —" for v in self.ui.tree.items.values()))
        self.assertIn("Primeiro preenchimento", self.ui.lbl_inicio.opts["text"])
        self.assertIn("0 de 4 leitos", self.ui.lbl_resumo.opts["text"])

    def _preencher_form(self, form, nome="Maria de Souza"):
        form.e_nome.insert(0, nome)
        form.seg_acomp.set("Sim")
        form.e_idade.insert(0, "72")
        form.seg_sexo.set("Mulher")
        form.seg_cor.set("Negro")
        form.e_aj.insert(0, "46,5")
        form.e_pp.insert(0, "31")
        form.e_pb.insert(0, "26,5")

    def test_registro_estimar_calcular_salvar(self):
        self.ui.mostrar_mapa()
        form = mapa_ui.FormRegistro(self.ui, self._primeiro_leito())
        self._preencher_form(form)
        form._estimar_altura()  # Chumlea 1985 (padrão): 84,88 - 0,24*72 + 1,83*46,5 = 152,7
        self.assertEqual(form.e_altura.get(), "152,7")
        self.assertEqual(form.seg_alt.get(), "Estimada")
        form._estimar_peso()  # 1,50*46,5 + 2,58*26,5 - 84,22 = 53,9
        self.assertEqual(form.e_peso.get(), "53,9")
        self.assertEqual(form.seg_peso.get(), "Estimado")
        self.assertEqual(form.lbl_imc.opts["text"], "23,1")
        self.assertEqual(form.lbl_class.opts["text"], "(Eutrofia)")  # Lipschitz 22-27
        # altera para peso real
        form.e_peso.delete(0)
        form.e_peso.insert(0, "70")
        form.seg_peso.click("Real")
        self.assertEqual(form.lbl_class.opts["text"], "(Sobrepeso)")  # 70 kg / 1,527 m = 30,0 -> idoso > 27
        form.seg_via.set("Oral")
        form.seg_cons.set("Pastosa")
        form.var_carac["dm"].set(1)
        form.var_carac["constipante"].set(1)
        form.e_reav.insert(0, "30/10/2026")
        form.t_sim.insert("1.0", "mamão")
        form.t_nao.insert("1.0", "leite")
        form.seg_fi.click("Presente")
        self.assertEqual(form.e_fi_freq.get(), "1")
        # suplemento: filtra por módulo e adiciona
        form.cb_mod.set("Módulo probiótico/simbiótico")
        form._filtrar_sup()
        self.assertEqual(form.cb_sup.get(), "Simbioflora")
        form.e_qtd.insert(0, "1")
        form._add_sup()
        self.assertEqual(len(form._suplementos), 1)
        form.cb_sup.set("Simbioflora")
        form._add_sup()  # duplicado
        self.assertEqual(len(form._suplementos), 1)
        form._salvar()
        self.assertTrue(form.destroyed)
        reg = mdb.obter_registro(self.db, self.ui.data.isoformat(), self._primeiro_leito()["leito"]["id_leito"])
        self.assertEqual((reg["nome_paciente"], reg["sexo"], reg["cor"], reg["idade_anos"]), ("Maria de Souza", "M", "N", 72))
        self.assertEqual((reg["altura_cm"], reg["altura_origem"], reg["peso_kg"], reg["peso_origem"]), (152.7, "E", 70.0, "R"))
        self.assertEqual(reg["altura_metodo"], "Chumlea et al. (1985), 60-90 anos")
        self.assertIsNone(reg["peso_metodo"])  # peso real não guarda método
        self.assertEqual((reg["via"], reg["consistencia"], reg["dm"], reg["constipante"], reg["has"]), ("Oral", "Pastosa", 1, 1, 0))
        self.assertEqual((reg["data_reavaliacao"], reg["obs_sim"], reg["obs_nao"]), ("2026-10-30", "mamão", "leite"))
        self.assertEqual((reg["fi_estado"], reg["fi_freq"]), ("P", 1.0))
        self.assertEqual(reg["suplementos"][0]["nome"], "Simbioflora")
        self.assertEqual(reg["suplementos"][0]["qtd_dia"], 1.0)
        # a lista do mapa foi atualizada
        linha = self.ui.tree.items[str(self._primeiro_leito()["leito"]["id_leito"])]
        self.assertEqual(linha[4], "Maria de Souza")
        self.assertIn("Sobrepeso", linha[6])
        self.assertIn("1 de 4 leitos", self.ui.lbl_resumo.opts["text"])
        self.assertIn("1 em dieta pastosa", self.ui.lbl_resumo.opts["text"])
        self.assertIn("1 com acompanhante", self.ui.lbl_resumo.opts["text"])

    def test_troca_automatica_suplementacao_oral_para_dieta_enteral(self):
        self.ui.mostrar_mapa()
        form = mapa_ui.FormRegistro(self.ui, self._primeiro_leito())
        self._preencher_form(form)
        form.seg_via.set("Oral")
        form._via_mudou("Oral", preservar=True)
        form.cb_mod.set("Módulo probiótico/simbiótico")
        form._filtrar_sup()
        form.cb_sup.set("Simbioflora")
        form.e_qtd.insert(0, "1")
        form._add_sup()
        self.assertEqual(len(form._suplementos), 1)

        # Selecionar via enteral substitui a suplementação oral, mas o catálogo permanece integralmente visível.
        form.seg_via.click("Enteral")
        self.assertEqual(form._suplementos, [])
        self.assertEqual(form.cb_mod.get(), "Todos os módulos")
        self.assertTrue(form._catalogo_visivel)
        nomes = [s["nome"] for s in form._catalogo_visivel]
        self.assertIn("Nutrison Energy 1.5", nomes)
        self.assertIn("Ensure Plus Advance", nomes)
        self.assertIn("Glucerna SR", nomes)
        self.assertIn("Ensure Plus Advance", [s["nome"] for s in form._catalogo_visivel])
        self.assertIn("Glucerna SR", [s["nome"] for s in form._catalogo_visivel])
        self.assertIn("Nutri R 2.0", [s["nome"] for s in form._catalogo_visivel])
        form.cb_sup.set("Nutrison Energy 1.5")
        form.e_qtd.insert(0, "250")
        form._add_sup()
        form.e_meta_kcal.insert(0, "1800")
        form.e_meta_ptn.insert(0, "90")
        form._salvar()

        reg = mdb.obter_registro(self.db, self.ui.data.isoformat(), self._primeiro_leito()["leito"]["id_leito"])
        self.assertEqual(reg["via"], "Enteral")
        self.assertEqual([s["nome"] for s in reg["suplementos"]], ["Nutrison Energy 1.5"])
        self.assertEqual((reg["suplementos"][0]["kcal_100"], reg["suplementos"][0]["ptn_100"]), (149.0, 6.0))
        self.assertTrue(reg["suplementos"][0]["ficha_snapshot_em"])
        self.assertEqual((reg["meta_kcal"], reg["meta_proteina_g"]), (1800.0, 90.0))
        self.assertIn("1 em dieta enteral", self.ui.lbl_resumo.opts["text"])
        self.assertIn("0 com suplementação oral", self.ui.lbl_resumo.opts["text"])
        linha = self.ui.tree.items[str(self._primeiro_leito()["leito"]["id_leito"])]
        self.assertIn("Dieta enteral", linha[9])

        # Ao retornar para via oral, a fórmula enteral é removida e não reaparece na lista de suplementos.
        form2 = mapa_ui.FormRegistro(self.ui, self._primeiro_leito())
        self.assertEqual([s["nome"] for s in form2._suplementos], ["Nutrison Energy 1.5"])
        form2.seg_via.click("Oral")
        self.assertEqual(form2._suplementos, [])
        self.assertIn("Nutrison Energy 1.5", [s["nome"] for s in form2._catalogo_visivel])
        self.assertIn("Glucerna 1.5 kcal", [s["nome"] for s in form2._catalogo_visivel])
        self.assertIn("Glucerna SR", [s["nome"] for s in form2._catalogo_visivel])
        self.assertIn("Nutri R 2.0", [s["nome"] for s in form2._catalogo_visivel])
        self.assertIn("Ensure Plus Advance", [s["nome"] for s in form2._catalogo_visivel])

    def test_reabrir_edita_e_vinculo_de_paciente(self):
        self.ui.mostrar_mapa()
        f1 = mapa_ui.FormRegistro(self.ui, self._primeiro_leito())
        self._preencher_form(f1)
        f1._salvar()
        self.ui._recarregar()
        f2 = mapa_ui.FormRegistro(self.ui, self._primeiro_leito())
        self.assertEqual(f2.e_nome.get(), "Maria de Souza")
        self.assertEqual((f2.seg_sexo.get(), f2.seg_cor.get(), f2.seg_acomp.get()), ("Mulher", "Negro", "Sim"))
        self.assertEqual(f2.e_aj.get(), "46,5")
        self.assertEqual(f2.e_pp.get(), "31")
        dados = f2._coletar()
        self.assertEqual((dados["aj_cm"], dados["pp_cm"], dados["pb_cm"], dados["idade_anos"]), (46.5, 31.0, 26.5, 72))
        id_pac = dados["id_paciente"]
        self.assertTrue(id_pac)
        f2.e_pb.delete(0)
        f2.e_pb.insert(0, "27")
        f2._salvar()
        reg = mdb.obter_registro(self.db, self.ui.data.isoformat(), self._primeiro_leito()["leito"]["id_leito"])
        self.assertEqual((reg["pb_cm"], reg["id_paciente"]), (27.0, id_pac))  # mesmo paciente, sem duplicar
        # troca o nome no mesmo leito: é outro paciente (novo cadastro)
        f3 = mapa_ui.FormRegistro(self.ui, self._primeiro_leito())
        f3.e_nome.delete(0)
        f3.e_nome.insert(0, "João Pereira")
        f3._salvar()
        reg3 = mdb.obter_registro(self.db, self.ui.data.isoformat(), self._primeiro_leito()["leito"]["id_leito"])
        self.assertNotEqual(reg3["id_paciente"], id_pac)
        # nome igual a cadastro existente em outro leito: pergunta e vincula ('sim')
        ocupado = [l for l in self.ui.linhas if l["registro"] is None][0]
        f4 = mapa_ui.FormRegistro(self.ui, ocupado)
        f4.e_nome.insert(0, "Maria de Souza")
        MB.resposta = True
        f4._salvar()
        self.assertTrue(any(c[0] == "askyesnocancel" for c in MB.chamadas))
        reg4 = mdb.obter_registro(self.db, self.ui.data.isoformat(), ocupado["leito"]["id_leito"])
        self.assertEqual(reg4["id_paciente"], id_pac)

    def test_validacoes_na_tela(self):
        self.ui.mostrar_mapa()
        form = mapa_ui.FormRegistro(self.ui, self._primeiro_leito())
        form._salvar()  # sem nome
        self.assertFalse(form.destroyed)
        self.assertEqual(MB.chamadas[-1][0], "showwarning")
        MB.chamadas.clear()
        form.e_nome.insert(0, "Fulano")
        form.e_peso.insert(0, "abc")
        form._salvar()
        self.assertIn("Peso", MB.chamadas[-1][2])
        form.e_peso.delete(0)
        form.e_reav.insert(0, "31/02/2026")
        form._salvar()
        self.assertIn("reavaliação", MB.chamadas[-1][2])
        MB.chamadas.clear()
        form.e_reav.delete(0)
        form._estimar_altura()  # faltam dados
        self.assertEqual(MB.chamadas[-1][0], "showwarning")

    def test_historico_copiar_remover(self):
        self.ui.mostrar_mapa()
        f = mapa_ui.FormRegistro(self.ui, self._primeiro_leito())
        self._preencher_form(f)
        f._salvar()
        # copia para o dia seguinte
        self.ui._mudar_dia(1)
        self.ui._copiar_ultimo()
        self.assertEqual(sum(1 for l in self.ui.linhas if l["registro"]), 1)
        self.assertIn("dia futuro", self.ui.lbl_aviso.opts["text"])
        self.ui.tree.selection_set(str(self._primeiro_leito()["leito"]["id_leito"]))
        self.ui._historico()
        # histórico em janela (último filho de nenhum pai: instanciar direto)
        h = mapa_ui.DialogHistorico(self.ui, self._primeiro_leito()["registro"])
        self.assertEqual(len(h.tree.items), 2)
        h.tree.selection_set(list(h.tree.items)[0])
        h._abrir()  # abre formulário somente leitura
        # remover
        self.ui._remover()
        self.assertTrue(all(l["registro"] is None for l in self.ui.linhas))
        self.ui._ir_hoje()
        self.assertEqual(self.ui.lbl_aviso.opts["text"], "")

    def test_somente_leitura_trava_campos(self):
        self.ui.mostrar_mapa()
        f = mapa_ui.FormRegistro(self.ui, self._primeiro_leito())
        self._preencher_form(f)
        f._salvar()
        self.ui._recarregar()
        ro = mapa_ui.FormRegistro(self.ui, self._primeiro_leito(), somente_leitura=True)
        self.assertEqual(ro.e_nome.opts.get("state"), "disabled")
        self.assertEqual(ro.seg_sexo.opts.get("state"), "disabled")

    def test_exportar_pelas_telas(self):
        self.ui.mostrar_mapa()
        f = mapa_ui.FormRegistro(self.ui, self._primeiro_leito())
        self._preencher_form(f)
        f._salvar()
        self.ui._recarregar()
        FD.destino = os.path.join(tempfile.gettempdir(), "teste_ui.xlsx")
        # a tela pergunta "Deseja abri-lo agora?" e o fake responde sim: sem este mock, no Windows o teste abria o
        # programa de verdade (o Excel, ou a janela "Selecione um aplicativo" quando não há nenhum associado)
        with mock.patch.object(os, "startfile", create=True) as abrir:
            self.ui._exportar_excel()
        self.assertTrue(os.path.exists(FD.destino))
        abrir.assert_called_once_with(FD.destino)
        # PDF com o FPDF simulado (a biblioteca real não existe neste ambiente de teste)
        original = mex.exportar_pdf
        mex.exportar_pdf = lambda c, l, d, s, **kw: original(c, l, d, s, pdf_factory=FakePDF)
        try:
            FD.destino = os.path.join(tempfile.gettempdir(), "teste_ui.pdf")
            with mock.patch.object(os, "startfile", create=True) as abrir:
                self.ui._exportar_pdf()
            self.assertTrue(os.path.exists(FD.destino))
            abrir.assert_called_once_with(FD.destino)
        finally:
            mex.exportar_pdf = original

    def test_adicionar_leitos_por_fluxo_simples(self):
        self.ui.mostrar_mapa()
        dialogo = mapa_ui.DialogAdicionarLeitos(self.ui)
        dialogo.cb_setor.set("Operação - OP")
        dialogo.e_de.insert(0, "10")
        dialogo.e_ate.insert(0, "12")
        dialogo._adicionar()
        setor_op = next(x for x in mdb.listar_setores(self.db) if x["sigla"] == "OP")
        codigos = [x["codigo"] for x in mdb.listar_leitos(self.db, setor_op["id_setor"])]
        self.assertEqual(codigos, [str(x) for x in range(1, 13)])
        self.assertEqual(self.ui.id_setor, setor_op["id_setor"])

    def test_dialogo_de_ordem_move_setor_sem_misturar_grupos(self):
        dialogo = mapa_ui.DialogOrdemSetores(self.ui)
        setores = mdb.listar_setores(self.db)
        cm = next(x for x in setores if x["sigla"] == "CM")
        dialogo.tree.selection_set(str(cm["id_setor"]))
        dialogo._subir()
        atuais = mdb.listar_setores(self.db)
        self.assertEqual([x["sigla"] for x in atuais if x["grupo"] == "Internos"],
                         ["CM", "OP", "PSI", "ISO"])
        dialogo.destroy()

    def test_leitos_suplementos_config(self):
        self.ui.mostrar_mapa()
        d = mapa_ui.DialogLeitos(self.ui)
        d.e_novo_setor.insert(0, "UTI")
        d._criar_setor()
        self.assertEqual(d.cb_setor.get(), "UTI")
        d.e_pref.insert(0, "U")
        d.e_de.insert(0, "1")
        d.e_ate.insert(0, "3")
        d._gerar()
        self.assertEqual(len(d.tree.items), 3)
        d.e_codigo.insert(0, "U10")
        d._adicionar()
        self.assertEqual(len(d.tree.items), 4)
        d._fechar()
        self.assertEqual(len(self.ui.tree.items), 4)  # mapa passou a mostrar o setor UTI (U01..U03 + U10)
        self.ui.mostrar_suplementos()
        self.assertEqual(len(self.ui.tree_sup.items), 25)
        ds = mapa_ui.DialogSuplemento(self.ui, None)
        ds.e["nome"].insert(0, "Módulo de fibra X")
        ds.cb_mod.set("Módulo de fibras")
        ds.e["kcal_100"].insert(0, "200,5")
        ds.e["preco"].insert(0, "19,9")
        ds.cb_un.set("g")
        ds._salvar()
        self.assertEqual(len(self.ui.tree_sup.items), 26)
        novo = [v for v in self.ui.tree_sup.items.values() if v[0] == "Módulo de fibra X"][0]
        self.assertEqual((novo[1], novo[3], novo[8]), ("Módulo de fibras", "200,5", "19,90"))
        dc = mapa_ui.DialogConfig(self.ui)
        self.assertEqual(dc.cb_graf.get(), mapa_ui.gl.ROTULOS_DISPOSICAO[mapa_ui.gl.DISPOSICAO_LADO_A_LADO])  # padrão
        dc.cb_imc.set(mapa_ui.nc.CRITERIOS_IMC_IDOSO["opas"])
        dc.cb_alt.set(mapa_ui.nc.METODOS_ALTURA_IDOSO["chumlea1998"])
        dc.cb_graf.set(mapa_ui.gl.ROTULOS_DISPOSICAO[mapa_ui.gl.DISPOSICAO_VERTICAL])
        dc._salvar()
        self.assertEqual((self.ui.criterio_idoso, self.ui.metodo_altura_idoso), ("opas", "chumlea1998"))
        self.assertEqual(self.ui.disposicao_graficos, mapa_ui.gl.DISPOSICAO_VERTICAL)
        self.assertEqual(mapa_ui.DialogConfig(self.ui).cb_graf.get(),
                         mapa_ui.gl.ROTULOS_DISPOSICAO[mapa_ui.gl.DISPOSICAO_VERTICAL])   # reabre já com o valor salvo

    def _cartas(self):
        """(desenhadas na tela, em imagem) de todas as faixas da tela de gráficos aberta."""
        painel = self.ui._painel
        cartas = [c for f in painel.faixas + painel.faixas_empilhadas for c in f.cards]
        return [c for c in cartas if c.animado], [c for c in cartas if not c.animado]

    def test_graficos(self):
        from test_mapa import popular_mes
        popular_mes(self.db, n_leitos=6)
        self.ui.mostrar_graficos()
        nativas, imagens = self._cartas()
        self.assertEqual((len(nativas), len(imagens), len(self.ui._imagens)), (10, 0, 0))   # padrão: desenhados na tela
        self.assertEqual(self.ui.cb_mes.get(), "Outubro")
        self.ui.cb_mes.set("Fevereiro")
        self.ui._gerar_graficos()  # mês sem dados: gráficos vazios, sem erro
        self.assertEqual(len(self._cartas()[0]), 10)
        FD.pasta = tempfile.mkdtemp()
        self.ui._salvar_graficos()   # exportar as imagens PNG continua igual (o matplotlib só entra aqui)
        self.assertEqual(len(os.listdir(FD.pasta)), 10)

    def test_graficos_agrupados_lado_a_lado_e_de_cima_para_baixo(self):
        from unittest import mock
        from test_mapa import popular_mes
        popular_mes(self.db, n_leitos=6)
        self.ui.mostrar_graficos()
        # padrão: uma faixa que se arrasta por grupo (atendimentos, dieta, suplementos, doenças crônicas)
        self.assertEqual(self.ui.disposicao_graficos, mapa_ui.gl.DISPOSICAO_LADO_A_LADO)
        self.assertEqual([g["id"] for g in self.ui._grupos], ["atendimentos", "dieta", "suplementos", "cronicas"])
        self.assertEqual(len(self.ui._painel.faixas), 4)
        self.assertEqual(len(self.ui.quadro_graf.winfo_children()), 4)
        # trocar nas Configurações redesenha a tela aberta SEM refazer as contas dos dados
        dc = mapa_ui.DialogConfig(self.ui)
        dc.cb_graf.set(mapa_ui.gl.ROTULOS_DISPOSICAO[mapa_ui.gl.DISPOSICAO_VERTICAL])
        with mock.patch.object(self.ui._mgr, "especificar_por_grupo") as espec, \
                mock.patch.object(self.ui._mgr, "gerar_por_grupo") as gerar:
            dc._salvar()
            espec.assert_not_called()
            gerar.assert_not_called()
        self.assertEqual(self.ui._painel.disposicao, mapa_ui.gl.DISPOSICAO_VERTICAL)
        self.assertEqual(self.ui._painel.faixas, [])
        self.assertEqual(len(self.ui._painel.faixas_empilhadas), 10)        # um gráfico por faixa, de cima para baixo
        self.assertEqual(len(self.ui.quadro_graf.winfo_children()), 4)    # continua agrupado: uma seção por grupo
        # a escolha vale também na próxima vez que a tela de gráficos é aberta
        self.ui.mostrar_graficos()
        self.assertEqual(self.ui._painel.disposicao, mapa_ui.gl.DISPOSICAO_VERTICAL)
        # e dá para voltar
        dc = mapa_ui.DialogConfig(self.ui)
        dc.cb_graf.set(mapa_ui.gl.ROTULOS_DISPOSICAO[mapa_ui.gl.DISPOSICAO_LADO_A_LADO])
        dc._salvar()
        self.assertEqual(len(self.ui._painel.faixas), 4)

    def test_estilo_dos_graficos_animado_ou_imagem_simples(self):
        from unittest import mock
        from test_mapa import popular_mes
        gl = mapa_ui.gl
        popular_mes(self.db, n_leitos=6)
        self.ui.mostrar_graficos()
        self.assertEqual(self.ui.estilo_graficos, gl.ESTILO_ANIMADO)
        dc = mapa_ui.DialogConfig(self.ui)
        self.assertEqual(dc.cb_estilo.get(), gl.ROTULOS_ESTILO[gl.ESTILO_ANIMADO])
        # imagens simples: os PNG são feitos uma vez, sem refazer as contas dos dados
        dc.cb_estilo.set(gl.ROTULOS_ESTILO[gl.ESTILO_IMAGEM])
        with mock.patch.object(self.ui._mgr, "especificar_por_grupo") as espec, \
                mock.patch.object(self.ui._mgr, "renderizar_grupos", wraps=self.ui._mgr.renderizar_grupos) as render:
            dc._salvar()
            espec.assert_not_called()
            render.assert_called_once()
        nativas, imagens = self._cartas()
        self.assertEqual((len(nativas), len(imagens), len(self.ui._imagens)), (0, 10, 10))
        self.assertEqual(self.ui.estilo_graficos, gl.ESTILO_IMAGEM)
        # mudar só a disposição não desenha os PNG de novo (ficam guardados)
        dc = mapa_ui.DialogConfig(self.ui)
        self.assertEqual(dc.cb_estilo.get(), gl.ROTULOS_ESTILO[gl.ESTILO_IMAGEM])   # reabre com o valor salvo
        dc.cb_graf.set(gl.ROTULOS_DISPOSICAO[gl.DISPOSICAO_VERTICAL])
        with mock.patch.object(self.ui._mgr, "renderizar_grupos") as render:
            dc._salvar()
            render.assert_not_called()
        self.assertEqual((self.ui._painel.faixas, self.ui._painel.faixas_empilhadas, len(self.ui._imagens)), ([], [], 10))
        # novo mês: as imagens antigas são descartadas, as novas valem para o mês novo
        antigos = self.ui._grupos_png
        self.ui.cb_mes.set("Fevereiro")
        self.ui._gerar_graficos()
        self.assertIsNot(self.ui._grupos_png, antigos)
        self.assertEqual(len(self.ui._imagens), 10)
        # volta para animado
        dc = mapa_ui.DialogConfig(self.ui)
        dc.cb_estilo.set(gl.ROTULOS_ESTILO[gl.ESTILO_ANIMADO])
        dc._salvar()
        nativas, imagens = self._cartas()
        self.assertEqual((len(nativas), len(imagens), len(self.ui._imagens)), (10, 0, 0))
        # valor desconhecido na configuração volta para o padrão
        mapa_ui.mdb.salvar_config(self.db, gl.CHAVE_ESTILO, "qualquer coisa")
        self.assertEqual(self.ui.estilo_graficos, gl.ESTILO_ANIMADO)

    def test_estilo_imagem_sem_matplotlib_mostra_o_animado_e_avisa(self):
        from unittest import mock
        from test_mapa import popular_mes
        gl = mapa_ui.gl
        popular_mes(self.db, n_leitos=6)
        self.ui.mostrar_graficos()
        dc = mapa_ui.DialogConfig(self.ui)
        dc.cb_estilo.set(gl.ROTULOS_ESTILO[gl.ESTILO_IMAGEM])
        with mock.patch.object(self.ui._mgr, "renderizar_grupos", side_effect=ImportError("No module named matplotlib")):
            dc._salvar()
        avisos = [c for c in MB.chamadas if c[0] == "showwarning"]
        self.assertEqual(len(avisos), 1)
        self.assertIn("pip install matplotlib", avisos[0][2])
        self.assertNotIn("\\n", avisos[0][2])          # quebra de linha de verdade, não a barra e o n escritos
        self.assertIn("\n", avisos[0][2])
        nativas, imagens = self._cartas()
        self.assertEqual((len(nativas), len(imagens)), (10, 0))     # a tela não fica em branco

    def test_desempenho_da_animacao_dos_graficos(self):
        from unittest import mock
        from test_mapa import popular_mes
        gl = mapa_ui.gl
        popular_mes(self.db, n_leitos=6)
        with mock.patch.object(gl, "sistema_pede_economia", return_value=(gl.NIVEL_COMPLETO, "")):
            self.ui.mostrar_graficos()
            # padrão: automático, com um só ritmo para o programa todo, entregue ao painel
            self.assertEqual(self.ui.desempenho_graficos, gl.DESEMPENHO_AUTOMATICO)
            ritmo = self.ui.ritmo_graficos
            self.assertIs(self.ui.ritmo_graficos, ritmo)
            self.assertIs(self.ui._painel.ritmo, ritmo)
            self.assertEqual((ritmo.modo, ritmo.nivel), (gl.DESEMPENHO_AUTOMATICO, gl.NIVEL_COMPLETO))
            dc = mapa_ui.DialogConfig(self.ui)
            self.assertEqual(dc.cb_desempenho.get(), gl.ROTULOS_DESEMPENHO[gl.DESEMPENHO_AUTOMATICO])
            self.assertEqual(dc.lb_ritmo.cget("text"), "Agora: animação completa.")
            # econômico: vale na hora e a tela aberta é refeita com os gráficos já prontos
            dc.cb_desempenho.set(gl.ROTULOS_DESEMPENHO[gl.DESEMPENHO_ECONOMICO])
            dc._atualizar_texto_ritmo()
            self.assertIn("Sem animação", dc.lb_ritmo.cget("text"))
            dc._salvar()
            self.assertEqual(self.ui.desempenho_graficos, gl.DESEMPENHO_ECONOMICO)
            self.assertIs(self.ui.ritmo_graficos, ritmo)               # o mesmo objeto, só mudou de modo
            self.assertEqual(ritmo.modo, gl.DESEMPENHO_ECONOMICO)
            self.assertIs(self.ui._painel.ritmo, ritmo)
            self.ui._painel.ajustar_todas(1300)
            nativas, _ = self._cartas()
            self.assertEqual(len(nativas), 10)
            self.assertTrue(all(c.pronto for c in nativas))            # tudo pronto, sem esperar animação
            # reabre com o valor salvo e volta para o completo: os gráficos voltam a animar
            dc = mapa_ui.DialogConfig(self.ui)
            self.assertEqual(dc.cb_desempenho.get(), gl.ROTULOS_DESEMPENHO[gl.DESEMPENHO_ECONOMICO])
            dc.cb_desempenho.set(gl.ROTULOS_DESEMPENHO[gl.DESEMPENHO_COMPLETO])
            dc._salvar()
            self.assertEqual((ritmo.modo, ritmo.nivel), (gl.DESEMPENHO_COMPLETO, gl.NIVEL_COMPLETO))
            self.ui._painel.ajustar_todas(1300)
            nativas, _ = self._cartas()
            self.assertFalse(any(c.pronto for c in nativas))           # ainda no começo da animação
        # valor desconhecido na configuração volta para o padrão
        mapa_ui.mdb.salvar_config(self.db, gl.CHAVE_DESEMPENHO, "qualquer coisa")
        self.assertEqual(self.ui.desempenho_graficos, gl.DESEMPENHO_AUTOMATICO)

    def test_o_que_o_programa_aprendeu_sobre_o_computador_vale_para_as_proximas_telas(self):
        from unittest import mock
        from test_mapa import popular_mes
        gl = mapa_ui.gl
        popular_mes(self.db, n_leitos=6)
        with mock.patch.object(gl, "sistema_pede_economia", return_value=(gl.NIVEL_COMPLETO, "")):
            self.ui.mostrar_graficos()
            for _ in range(gl.AMOSTRAS_PARA_DECIDIR):                  # o computador demorou em todos os quadros
                self.ui._painel.ritmo.registrar_quadro(0.03, 0.2)
            self.assertEqual(self.ui.ritmo_graficos.nivel, gl.NIVEL_REDUZIDO)
            self.ui.mostrar_graficos()                                 # abre a tela de novo
            self.assertIs(self.ui._painel.ritmo, self.ui.ritmo_graficos)
            self.assertEqual(self.ui._painel.ritmo.nivel, gl.NIVEL_REDUZIDO)
            dc = mapa_ui.DialogConfig(self.ui)                         # e a janela de Configurações conta o que houve
            texto = dc.lb_ritmo.cget("text")
            self.assertIn("animação reduzida", texto)
            self.assertIn("cada quadro levou 30 ms", texto)
            self.assertIn("escolha Completo", texto)

    def test_desempenho_automatico_comeca_reduzido_quando_o_sistema_pede(self):
        from unittest import mock
        gl = mapa_ui.gl
        motivo = "o programa está em acesso remoto (área de trabalho remota)"
        with mock.patch.object(gl, "sistema_pede_economia", return_value=(gl.NIVEL_REDUZIDO, motivo)):
            self.ui.mostrar_mapa()
            dc = mapa_ui.DialogConfig(self.ui)
            texto = dc.lb_ritmo.cget("text")
            self.assertIn("animação reduzida", texto)
            self.assertIn("acesso remoto", texto)
            # escolher Completo mostra que ali a animação é sempre completa, sem esconder o motivo do automático
            dc.cb_desempenho.set(gl.ROTULOS_DESEMPENHO[gl.DESEMPENHO_COMPLETO])
            dc._atualizar_texto_ritmo()
            self.assertEqual(dc.lb_ritmo.cget("text"), "Animação completa em qualquer computador.")

    def test_exportar_imagens_sem_matplotlib_avisa_em_vez_de_quebrar(self):
        from unittest import mock
        from test_mapa import popular_mes
        popular_mes(self.db, n_leitos=6)
        self.ui.mostrar_graficos()
        FD.pasta = tempfile.mkdtemp()
        with mock.patch.object(self.ui._mgr, "salvar_graficos", side_effect=ImportError("No module named matplotlib")):
            self.ui._salvar_graficos()
        erros = [c for c in MB.chamadas if c[0] == "showerror"]
        self.assertEqual(len(erros), 1)
        self.assertIn("pip install matplotlib", erros[0][2])
        self.assertNotIn("\\n", erros[0][2])            # quebra de linha de verdade, não a barra e o n escritos
        self.assertIn("\n", erros[0][2])

    def test_graficos_animados_tem_forma_desenhada_no_canvas(self):
        from test_mapa import popular_mes
        popular_mes(self.db, n_leitos=6)
        self.ui.mostrar_graficos()
        painel = self.ui._painel
        painel.ajustar_todas(1300)
        faixa = painel.faixas[0]
        textos = [f["text"] for f in faixa.canvas.formas.values() if f["t"] == "texto"]
        self.assertIn("Pacientes atendidos por dia", textos)       # o título do primeiro gráfico do grupo
        self.assertTrue(any(f["t"] == "poli" for f in faixa.canvas.formas.values()))   # moldura e barras
        self.assertEqual(faixa.canvas.itens, [])                    # nenhuma imagem: tudo desenhado
        self.assertTrue(faixa.dicas)                                # o balão tem o que mostrar

    def test_salvar_configuracoes_sem_a_tela_de_graficos_aberta_nao_da_erro(self):
        self.ui.mostrar_mapa()
        dc = mapa_ui.DialogConfig(self.ui)
        dc.cb_graf.set(mapa_ui.gl.ROTULOS_DISPOSICAO[mapa_ui.gl.DISPOSICAO_VERTICAL])
        dc._salvar()
        self.assertEqual(self.ui.disposicao_graficos, mapa_ui.gl.DISPOSICAO_VERTICAL)
        self.assertIsNone(self.ui._painel)
        # tela de gráficos aberta e depois fechada (o Tk destrói os widgets): salvar de novo não redesenha nada
        from unittest import mock
        self.ui.mostrar_graficos()
        self.ui.mostrar_mapa()
        dc = mapa_ui.DialogConfig(self.ui)
        with mock.patch.object(self.ui, "_montar_painel") as montar:
            dc._salvar()
            montar.assert_not_called()


    def test_atalhos_do_formulario_de_registro(self):
        self.ui.mostrar_mapa()
        form = mapa_ui.FormRegistro(self.ui, self._primeiro_leito())
        self.assertIn("<Control-s>", form.bindings)
        self.assertIn("<Control-S>", form.bindings)
        self.assertIn("<Escape>", form.bindings)
        with mock.patch.object(form, "_salvar") as salvar:
            form._atalho_salvar()
            salvar.assert_called_once()
        form._atalho_fechar()
        self.assertTrue(form.destroyed)

    def test_atalhos_da_busca_de_paciente(self):
        dialogo = mapa_ui.DialogBuscarPaciente(self.ui, lambda paciente: None)
        self.assertIn("<Return>", dialogo.tree.bindings)
        self.assertIn("<Escape>", dialogo.tree.bindings)
        self.assertIn("<Control-f>", dialogo.tree.bindings)
        self.assertIn("<Control-F>", dialogo.e_busca.bindings)
        dialogo._atalho_focar_busca()
        dialogo._atalho_fechar()
        self.assertTrue(dialogo.destroyed)

    def test_vincular_paciente_preenche_idade_em_anos_e_meses(self):
        self.ui.mostrar_mapa()
        self.ui.data = __import__("datetime").date(2026, 11, 22)
        form = mapa_ui.FormRegistro(self.ui, self._primeiro_leito())
        form.e_idade.insert(0, "20")
        form.e_meses.insert(0, "2")
        form._paciente_escolhido({
            "id_paciente": 99, "nome": "Paciente Teste",
            "data_nascimento": "15/05/1950", "sexo": "F"
        })
        self.assertEqual(form.e_idade.get(), "76")
        self.assertEqual(form.e_meses.get(), "6")
        self.assertEqual(form.seg_sexo.get(), "Mulher")
        self.assertEqual(form.e_nome.get(), "Paciente Teste")

if __name__ == "__main__":
    unittest.main(verbosity=2)
