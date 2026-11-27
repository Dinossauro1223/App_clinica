# -*- coding: utf-8 -*-
"""Faixa que se arrasta e painel de gráficos agrupados (graficos_ui) com widgets simulados.

Carrega uma cópia PRIVADA de graficos_ui.py com tkinter/customtkinter falsos só para esta cópia: não mexe nos módulos
do resto do processo (test_ui_smoke instala os dele). O relógio também é falso, então a animação de encaixe roda
em passos exatos, sem esperar. NÃO prova a aparência real; para isso há o teste com Tk de verdade
(tests/test_graficos_tk_real.py, que só roda onde existe janela).
"""
import importlib.util
import os
import sys
import types
import unittest
from unittest import mock

RAIZ = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.dirname(__file__))

from PIL import Image  # noqa: E402

import graficos_layout as gl  # noqa: E402


class TclErro(Exception):
    pass


class Evento:
    def __init__(self, **kw):
        self.width = kw.get("width", 0)
        self.x_root = kw.get("x_root", 0)
        self.x, self.y = kw.get("x", 0), kw.get("y", 0)
        self.delta = kw.get("delta", 0)


class Relogio:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t

    def avancar(self, s):
        self.t += s


class Base:
    def __init__(self, *args, **kw):
        self.master = args[0] if args else None
        self.opts = dict(kw)
        self.children, self.bindings = [], {}
        self.empacotado = False
        self.destruido = False
        if isinstance(self.master, Base):
            self.master.children.append(self)

    def configure(self, **kw):
        self.opts.update(kw)

    def cget(self, k):
        return self.opts.get(k)

    def pack(self, *a, **kw):
        self.empacotado = True
        self.opts["pack"] = kw

    def pack_forget(self):
        self.empacotado = False

    def bind(self, ev, fn, add=None):
        self.bindings[ev] = fn

    def winfo_exists(self):
        return not self.destruido


class Botao(Base):
    def clicar(self):
        if self.opts.get("state") != "disabled":
            self.opts["command"]()


class TelaFalsa(Base):
    """tk.Canvas falso: guarda o que foi desenhado e uma fila de `after` que o teste executa à mão."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.itens, self.fracoes, self.agendados, self.cancelados, self._n = [], [], {}, [], 0
        self.com_foco = False
        self.formas, self.chamadas, self._nf = {}, [], 0   # formas desenhadas e o que foi pedido ao Tk (coords, config)
        self.largura_tela, self.altura_tela = 1100, 400

    def create_image(self, x, y, **kw):
        self.itens.append({"x": x, "y": y, **kw})
        return len(self.itens)

    def _nova(self, tipo, coords, kw):
        self._nf += 1
        self.formas[self._nf] = {"t": tipo, "c": tuple(coords), **kw}
        self.chamadas.append(("criar", self._nf))
        return self._nf

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
        self.chamadas.append(("coords", item))
        self.formas[item]["c"] = tuple(c)

    def itemconfigure(self, item, **kw):
        self.chamadas.append(("config", item, tuple(sorted(kw))))
        self.formas[item].update(kw)

    def itemcget(self, item, chave):
        return self.formas[item].get(chave, "normal" if chave == "state" else "")

    def bbox(self, item):
        c = self.formas[item]["c"]
        if self.formas[item]["t"] == "arco":
            return c[0], c[1], c[2], c[3]
        return min(c[0::2]), min(c[1::2]), max(c[0::2]), max(c[1::2])

    def find_overlapping(self, x0, y0, x1, y1):
        achados = []
        for item in self.formas:
            a, b, c, d = self.bbox(item)
            if a <= x1 and c >= x0 and b <= y1 and d >= y0:
                achados.append(item)
        return tuple(achados)

    def tag_raise(self, item):
        self.chamadas.append(("topo", item))

    def canvasx(self, x):
        return x

    canvasy = canvasx

    def winfo_width(self):
        return self.largura_tela

    def winfo_height(self):
        return self.altura_tela

    def delete(self, *a):
        if a and a[0] != "all":
            for item in a:
                self.formas.pop(item, None)
            return
        self.itens, self.formas = [], {}

    def xview_moveto(self, f):
        self.fracoes.append(f)

    def focus_set(self):
        self.com_foco = True

    def after(self, ms, fn=None, *a):
        self._n += 1
        self.agendados[self._n] = (ms, fn)
        return self._n

    def after_cancel(self, i):
        self.cancelados.append(i)
        self.agendados.pop(i, None)

    def executar_agendados(self):
        """Roda (uma vez) tudo o que estava na fila; o que for agendado durante a execução fica para depois."""
        fila, self.agendados = self.agendados, {}
        for _, fn in fila.values():
            fn()
        return len(fila)


class FontesFalsas:
    """Fontes do Tk simuladas: cada letra mede 0,55 do tamanho (0,6 no negrito), como nos testes da cena."""

    def fonte(self, tam, negrito=False):
        return ("fonte", round(tam), bool(negrito))

    def medir(self, texto, tam, negrito=False):
        return len(texto) * tam * (0.6 if negrito else 0.55)


def carregar_graficos_ui(com_rastreador=None):
    tk = types.ModuleType("tkinter")
    tk.TclError, tk.Canvas = TclErro, TelaFalsa
    ctk = types.ModuleType("customtkinter")
    for nome in ("CTkFrame", "CTkLabel"):
        setattr(ctk, nome, type(nome, (Base,), {}))
    ctk.CTkButton = Botao
    ctk.CTkFont = lambda **kw: ("fonte", kw)
    ctk.CTkImage = lambda **kw: types.SimpleNamespace(**kw)
    if com_rastreador is not None:
        ctk.ScalingTracker = com_rastreador
    spec = importlib.util.spec_from_file_location("graficos_ui_isolado", os.path.join(RAIZ, "graficos_ui.py"))
    modulo = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, {"tkinter": tk, "customtkinter": ctk}):
        spec.loader.exec_module(modulo)
    return modulo


def imagem(largura=900, altura=400):
    return Image.new("RGB", (largura, altura), "#ffffff")


def png_de(largura=900, altura=400):
    import io
    buf = io.BytesIO()
    imagem(largura, altura).save(buf, format="PNG")
    return buf.getvalue()


class BaseDosTestes(unittest.TestCase):
    def setUp(self):
        self.ui = carregar_graficos_ui()
        self.relogio = Relogio()
        self.fotos = []
        padroes = [mock.patch.object(self.ui, "_agora", self.relogio),
                   mock.patch.object(self.ui.FaixaHorizontal, "espera_inicial_ms", 0),   # desenha na hora; o teste da espera religa
                   mock.patch.object(self.ui, "foto_tk", self._foto)]
        for p in padroes:
            p.start()
            self.addCleanup(p.stop)

    def _foto(self, img):
        self.fotos.append(img.size)
        return ("foto", img.size)

    def nova_faixa(self, n=3, escala=1.0, largura=1100, **kw):
        pai = Base()
        faixa = self.ui.FaixaHorizontal(pai, [imagem() for _ in range(n)], escala=escala, **kw)
        faixa.canvas.bindings["<Configure>"](Evento(width=largura))
        return faixa

    def rodar_animacao(self, faixa, passo=0.016, limite=200):
        """Avança o relógio e executa os quadros agendados até a animação de encaixe terminar."""
        for _ in range(limite):
            if not faixa.canvas.agendados:
                return
            self.relogio.avancar(passo)
            faixa.canvas.executar_agendados()
        self.fail("a animação de encaixe não terminou")


class TestFaixa(BaseDosTestes):
    def test_desenha_um_item_por_grafico_com_a_largura_certa(self):
        faixa = self.nova_faixa(3, largura=1100)
        c = faixa.canvas
        self.assertEqual([i["x"] for i in c.itens], [0, 856, 1712])
        self.assertEqual(self.fotos, [(840, 373)] * 3)       # 900x400 reduzido para 840 de largura, mesma proporção
        self.assertEqual(c.opts["height"], 373)
        self.assertEqual(c.opts["scrollregion"], (0, 0, 2552, 373))
        self.assertEqual(faixa.n_posicoes, 3)
        self.assertEqual(c.opts["cursor"], "hand2")          # dá para arrastar
        self.assertEqual(len(faixa.fotos), 3)                # referências guardadas (o Tk apaga o que ninguém segura)

    def test_janela_estreita_usa_a_largura_disponivel(self):
        faixa = self.nova_faixa(2, largura=500)
        self.assertEqual(faixa.carrossel.largura_card, 500 - gl.ESPIADA)
        self.assertEqual(self.fotos[0][0], 500 - gl.ESPIADA)

    def test_um_grafico_so_nao_arrasta(self):
        faixa = self.nova_faixa(1, largura=1100)
        self.assertTrue(faixa.cabe_sem_rolar())
        self.assertEqual(faixa.n_posicoes, 1)
        self.assertEqual(faixa.canvas.opts["cursor"], "")

    def test_escala_maior_do_windows_amplia_o_card_e_o_limite(self):
        faixa = self.nova_faixa(2, escala=1.5, largura=1900)
        self.assertEqual(faixa.carrossel.largura_card, 840 * 1.5)
        self.assertEqual(self.fotos[0], (1260, 560))
        self.assertEqual(faixa.carrossel.espaco, 24)

    def test_nao_estica_a_imagem_alem_do_tamanho_original(self):
        pai = Base()
        faixa = self.ui.FaixaHorizontal(pai, [imagem(400, 200)], escala=1.0)
        faixa.canvas.bindings["<Configure>"](Evento(width=1100))
        self.assertEqual(self.fotos, [(400, 200)])

    def test_primeiro_desenho_espera_e_usa_a_ultima_largura_avisada(self):
        # o Tk avisa antes a largura provisória do canvas e só depois a final: desenha-se uma vez, na final
        with mock.patch.object(self.ui.FaixaHorizontal, "espera_inicial_ms", self.ui.ESPERA_INICIAL_MS):
            faixa = self.ui.FaixaHorizontal(Base(), [imagem() for _ in range(3)], escala=1.0)
            c = faixa.canvas
            c.bindings["<Configure>"](Evento(width=378))
            self.assertIsNone(faixa.carrossel)
            self.assertEqual(self.fotos, [])
            self.assertEqual([ms for ms, _ in c.agendados.values()], [self.ui.ESPERA_INICIAL_MS])
            c.bindings["<Configure>"](Evento(width=1100))
            self.assertEqual(len(c.agendados), 1)                 # continua um desenho só, sem reagendar
            c.executar_agendados()
            self.assertEqual(faixa.carrossel.largura_visivel, 1100)
            self.assertEqual(len(self.fotos), 3)                  # nenhum desenho na largura provisória
            c.bindings["<Configure>"](Evento(width=1100))         # o Tk repete o aviso: já está firme
            self.assertEqual(len(c.agendados), 0)

    def test_desenho_direto_cancela_o_primeiro_desenho_agendado(self):
        with mock.patch.object(self.ui.FaixaHorizontal, "espera_inicial_ms", self.ui.ESPERA_INICIAL_MS):
            faixa = self.ui.FaixaHorizontal(Base(), [imagem() for _ in range(2)], escala=1.0)
            faixa.canvas.bindings["<Configure>"](Evento(width=378))
            faixa.ajustar(900)
            self.assertEqual(faixa.canvas.agendados, {})
            self.assertEqual(len(faixa.canvas.cancelados), 1)
            antes = len(self.fotos)
            faixa.canvas.executar_agendados()
            self.assertEqual(len(self.fotos), antes)              # nada foi desenhado de novo

    def test_destruir_antes_do_primeiro_desenho_cancela_o_agendado(self):
        with mock.patch.object(self.ui.FaixaHorizontal, "espera_inicial_ms", self.ui.ESPERA_INICIAL_MS):
            faixa = self.ui.FaixaHorizontal(Base(), [imagem()], escala=1.0)
            faixa.canvas.bindings["<Configure>"](Evento(width=700))
            faixa.canvas.bindings["<Destroy>"](Evento())
            self.assertEqual(faixa.canvas.agendados, {})
            self.assertEqual(self.fotos, [])

    def test_largura_minuscula_e_ignorada(self):
        pai = Base()
        faixa = self.ui.FaixaHorizontal(pai, [imagem()], escala=1.0)
        faixa.canvas.bindings["<Configure>"](Evento(width=1))   # o Tk manda 1 antes de a janela aparecer
        self.assertIsNone(faixa.carrossel)
        self.assertEqual(faixa.canvas.itens, [])
        self.assertEqual(faixa.n_posicoes, 1)

    def test_mudanca_pequena_de_largura_nao_redesenha_mas_a_grande_sim(self):
        faixa = self.nova_faixa(3, largura=1100)
        c = faixa.canvas
        antes = len(self.fotos)
        c.bindings["<Configure>"](Evento(width=1090))           # barra de rolagem aparecendo: balanço, ignora
        self.assertEqual((len(self.fotos), len(c.agendados)), (antes, 0))
        c.bindings["<Configure>"](Evento(width=900))
        self.assertEqual(len(c.agendados), 1)                   # redesenho agendado, não imediato
        c.bindings["<Configure>"](Evento(width=800))            # continua mexendo na janela: troca o agendamento
        self.assertEqual(len(c.agendados), 1)
        self.assertEqual(len(c.cancelados), 1)
        c.executar_agendados()
        self.assertEqual(faixa.carrossel.largura_visivel, 800)
        self.assertEqual(faixa.carrossel.largura_card, 800 - gl.ESPIADA)

    def test_redesenho_mantem_a_posicao_escolhida(self):
        faixa = self.nova_faixa(3, largura=1100)
        faixa.proximo()
        self.rodar_animacao(faixa)
        self.assertEqual(faixa.ativo, 1)
        faixa.ajustar(900)
        self.assertEqual(faixa.ativo, 1)
        self.assertEqual(faixa.deslocamento, faixa.carrossel.x_da_posicao(1))


class TestArraste(BaseDosTestes):
    def arrastar(self, faixa, de, para, dt_por_passo=0.05, passos=4, soltar_depois=0.2):
        c = faixa.canvas
        c.bindings["<ButtonPress-1>"](Evento(x_root=de))
        for i in range(1, passos + 1):
            self.relogio.avancar(dt_por_passo)
            c.bindings["<B1-Motion>"](Evento(x_root=de + (para - de) * i / passos))
        self.relogio.avancar(soltar_depois)
        c.bindings["<ButtonRelease-1>"](Evento(x_root=para))

    def test_arrastar_move_a_faixa_junto_com_o_mouse(self):
        faixa = self.nova_faixa(3)
        c = faixa.canvas
        c.bindings["<ButtonPress-1>"](Evento(x_root=500))
        self.assertTrue(c.com_foco)
        self.assertEqual(c.opts["cursor"], "fleur")
        c.bindings["<B1-Motion>"](Evento(x_root=300))           # mouse foi 200 px para a esquerda
        self.assertEqual(faixa.deslocamento, 200.0)
        self.assertAlmostEqual(c.fracoes[-1], 200.0 / 2552)
        c.bindings["<B1-Motion>"](Evento(x_root=900))           # passou do começo: trava em 0
        self.assertEqual(faixa.deslocamento, 0.0)

    def test_nao_passa_do_fim_da_faixa(self):
        faixa = self.nova_faixa(3)
        faixa.canvas.bindings["<ButtonPress-1>"](Evento(x_root=3000))
        faixa.canvas.bindings["<B1-Motion>"](Evento(x_root=-5000))
        self.assertEqual(faixa.deslocamento, faixa.carrossel.deslocamento_maximo)

    def test_soltar_perto_do_comeco_volta_e_perto_do_proximo_avanca(self):
        faixa = self.nova_faixa(3)
        self.arrastar(faixa, 500, 300)                          # 200 px: mais perto do 1º
        self.rodar_animacao(faixa)
        self.assertEqual((faixa.ativo, faixa.deslocamento), (0, 0.0))
        self.arrastar(faixa, 900, 400)                          # 500 px: mais perto do 2º
        self.rodar_animacao(faixa)
        self.assertEqual((faixa.ativo, faixa.deslocamento), (1, 856.0))
        self.assertEqual(faixa.canvas.opts["cursor"], "hand2")  # cursor volta ao normal

    def test_arremesso_rapido_vai_para_o_proximo_mesmo_com_arraste_curto(self):
        faixa = self.nova_faixa(3)
        c = faixa.canvas
        c.bindings["<ButtonPress-1>"](Evento(x_root=500))
        self.relogio.avancar(0.01)
        c.bindings["<B1-Motion>"](Evento(x_root=470))           # 30 px em 10 ms: 3000 px/s
        self.relogio.avancar(0.01)
        c.bindings["<ButtonRelease-1>"](Evento(x_root=470))
        self.rodar_animacao(faixa)
        self.assertEqual(faixa.ativo, 1)

    def test_parar_antes_de_soltar_cancela_o_arremesso(self):
        faixa = self.nova_faixa(3)
        c = faixa.canvas
        c.bindings["<ButtonPress-1>"](Evento(x_root=500))
        self.relogio.avancar(0.01)
        c.bindings["<B1-Motion>"](Evento(x_root=470))
        self.relogio.avancar(0.5)                               # segurou parado por meio segundo
        c.bindings["<ButtonRelease-1>"](Evento(x_root=470))
        self.rodar_animacao(faixa)
        self.assertEqual(faixa.ativo, 0)

    def test_clique_sem_arrastar_nao_move_nada(self):
        faixa = self.nova_faixa(3)
        c = faixa.canvas
        movimentos = len(c.fracoes)
        c.bindings["<ButtonPress-1>"](Evento(x_root=500))
        c.bindings["<B1-Motion>"](Evento(x_root=502))           # tremida de 2 px
        self.relogio.avancar(0.1)
        c.bindings["<ButtonRelease-1>"](Evento(x_root=502))
        self.assertEqual(c.agendados, {})
        self.assertEqual((faixa.ativo, faixa.deslocamento), (0, 0.0))   # continua exatamente no encaixe
        self.assertEqual(len(c.fracoes), movimentos)                    # nem chegou a mexer na tela

    def test_sem_arraste_em_andamento_movimento_e_soltar_sao_ignorados(self):
        faixa = self.nova_faixa(3)
        faixa.canvas.bindings["<B1-Motion>"](Evento(x_root=100))
        faixa.canvas.bindings["<ButtonRelease-1>"](Evento(x_root=100))
        self.assertEqual(faixa.deslocamento, 0.0)

    def test_novo_clique_interrompe_a_animacao_em_andamento(self):
        faixa = self.nova_faixa(3)
        faixa.proximo()
        self.assertTrue(faixa.canvas.agendados)
        faixa.canvas.bindings["<ButtonPress-1>"](Evento(x_root=10))
        self.assertEqual(faixa.canvas.agendados, {})


class TestSetasTecladoRoda(BaseDosTestes):
    def test_proximo_e_anterior_animam_ate_o_encaixe(self):
        faixa = self.nova_faixa(3)
        faixa.proximo()
        self.rodar_animacao(faixa)
        self.assertEqual((faixa.ativo, faixa.deslocamento), (1, 856.0))
        faixa.proximo()
        self.rodar_animacao(faixa)
        self.assertEqual((faixa.ativo, faixa.deslocamento), (2, 1452.0))
        faixa.proximo()                                         # já no fim: não anda
        self.assertEqual(faixa.canvas.agendados, {})
        faixa.anterior()
        self.rodar_animacao(faixa)
        self.assertEqual(faixa.ativo, 1)

    def test_anterior_no_comeco_nao_faz_nada(self):
        faixa = self.nova_faixa(3)
        faixa.anterior()
        self.assertEqual((faixa.canvas.agendados, faixa.deslocamento), ({}, 0.0))

    def test_animacao_tem_quadros_no_meio_e_termina_exatamente_no_alvo(self):
        faixa = self.nova_faixa(3)
        faixa.proximo()
        meio = []
        for _ in range(100):
            if not faixa.canvas.agendados:
                break
            self.relogio.avancar(0.016)
            faixa.canvas.executar_agendados()
            meio.append(faixa.deslocamento)
        self.assertGreater(len(meio), 5)                        # não é um salto único
        self.assertEqual(meio, sorted(meio))                    # só avança
        self.assertEqual(meio[-1], 856.0)
        self.assertLess(meio[0], 856.0)
        passos = [b - a for a, b in zip(meio, meio[1:])]
        self.assertGreater(passos[0], passos[-1])               # desacelera no fim

    def test_animacao_demora_pelo_tempo_e_nao_pelo_numero_de_quadros(self):
        # computador lento: o relógio anda 0,2 s entre quadros; chega no alvo em poucos quadros, sem arrastar
        faixa = self.nova_faixa(3)
        faixa.proximo()
        quadros = 0
        while faixa.canvas.agendados:
            self.relogio.avancar(0.2)
            faixa.canvas.executar_agendados()
            quadros += 1
            self.assertLess(quadros, 5)
        self.assertEqual(faixa.deslocamento, 856.0)

    def test_teclas_de_seta(self):
        faixa = self.nova_faixa(3)
        faixa.canvas.bindings["<Right>"](Evento())
        self.rodar_animacao(faixa)
        self.assertEqual(faixa.ativo, 1)
        faixa.canvas.bindings["<Left>"](Evento())
        self.rodar_animacao(faixa)
        self.assertEqual(faixa.ativo, 0)

    def test_shift_roda_anda_uma_posicao_por_vez(self):
        faixa = self.nova_faixa(3)
        c = faixa.canvas
        self.assertEqual(c.bindings["<Shift-MouseWheel>"](Evento(delta=-120)), "break")   # roda para baixo = adiante
        self.rodar_animacao(faixa)
        self.assertEqual(faixa.ativo, 1)
        c.bindings["<Shift-MouseWheel>"](Evento(delta=-120))
        self.relogio.avancar(0.01)
        c.bindings["<Shift-MouseWheel>"](Evento(delta=-120))      # girou rápido demais: só uma conta
        self.rodar_animacao(faixa)
        self.assertEqual(faixa.ativo, 2)
        self.relogio.avancar(1)
        c.bindings["<Shift-MouseWheel>"](Evento(delta=120))
        self.rodar_animacao(faixa)
        self.assertEqual(faixa.ativo, 1)

    def test_rolagem_horizontal_no_linux(self):
        faixa = self.nova_faixa(3)
        faixa.canvas.bindings["<Shift-Button-5>"](Evento())
        self.rodar_animacao(faixa)
        self.assertEqual(faixa.ativo, 1)
        self.relogio.avancar(1)
        faixa.canvas.bindings["<Shift-Button-4>"](Evento())
        self.rodar_animacao(faixa)
        self.assertEqual(faixa.ativo, 0)

    def test_avisa_quando_a_posicao_muda(self):
        avisos = []
        faixa = self.nova_faixa(3, ao_mudar=avisos.append)
        faixa.proximo()
        self.rodar_animacao(faixa)
        faixa.proximo()
        self.rodar_animacao(faixa)
        self.assertEqual(avisos, [1, 2])


class TestDestruicao(BaseDosTestes):
    def test_destruir_cancela_a_animacao_e_o_redesenho(self):
        faixa = self.nova_faixa(3)
        faixa.proximo()
        faixa.canvas.bindings["<Configure>"](Evento(width=700))
        self.assertEqual(len(faixa.canvas.agendados), 2)
        faixa.canvas.bindings["<Destroy>"](Evento())
        self.assertEqual(faixa.canvas.agendados, {})
        self.assertTrue(faixa._morto)

    def test_evento_depois_de_destruir_nao_estoura_erro(self):
        faixa = self.nova_faixa(3)
        faixa.canvas.bindings["<Destroy>"](Evento())
        movimentos = len(faixa.canvas.fracoes)
        for nome in ("<Configure>", "<ButtonPress-1>", "<B1-Motion>", "<ButtonRelease-1>", "<Left>", "<Right>",
                     "<Shift-MouseWheel>"):
            faixa.canvas.bindings[nome](Evento(width=800, x_root=5, delta=120))
        faixa.proximo()
        self.assertEqual(faixa.deslocamento, 0.0)
        # depois de destruída, a faixa ignora até um arraste completo
        faixa.canvas.bindings["<ButtonPress-1>"](Evento(x_root=500))
        faixa.canvas.bindings["<B1-Motion>"](Evento(x_root=300))
        faixa.canvas.bindings["<ButtonRelease-1>"](Evento(x_root=300))
        self.assertEqual((faixa.deslocamento, faixa.canvas.agendados), (0.0, {}))
        self.assertEqual(len(faixa.canvas.fracoes), movimentos)

    def test_widget_ja_destruido_no_tk_nao_vira_erro_na_tela(self):
        faixa = self.nova_faixa(3)

        def quebrado(*a, **kw):
            raise TclErro("invalid command name")
        faixa.canvas.xview_moveto = quebrado
        faixa.canvas.bindings["<ButtonPress-1>"](Evento(x_root=10))
        faixa.canvas.bindings["<B1-Motion>"](Evento(x_root=-400))     # só não pode levantar exceção


def grupos_de_teste():
    def itens(*chaves):
        return [(c, c.title(), png_de()) for c in chaves]
    return [
        {"id": "a", "titulo": "Atendimentos", "cor": "#4caf50", "descricao": "texto", "graficos": itens("x1", "x2", "x3")},
        {"id": "b", "titulo": "Dieta", "cor": "#ef6c00", "descricao": "", "graficos": itens("y1", "y2")},
        {"id": "c", "titulo": "Doenças crônicas", "cor": "#1565c0", "descricao": "texto", "graficos": itens("z1")},
    ]


class TestPainel(BaseDosTestes):
    def textos(self, no):
        achados = []
        if "text" in no.opts and no.opts["text"]:
            achados.append(no.opts["text"])
        for f in no.children:
            achados.extend(self.textos(f))
        return achados

    def test_lado_a_lado_cria_uma_faixa_por_grupo(self):
        pai = Base()
        painel = self.ui.PainelGraficos(pai, grupos_de_teste(), gl.DISPOSICAO_LADO_A_LADO)
        self.assertEqual(len(painel.faixas), 3)
        self.assertEqual(len(painel.imagens), 6)                  # uma por gráfico, mesmo antes de a janela aparecer
        self.assertTrue(all(isinstance(i, Image.Image) for i in painel.imagens))
        self.assertEqual(len(pai.children), 3)                    # uma seção por grupo
        titulos = self.textos(pai)
        for esperado in ("Atendimentos", "Dieta", "Doenças crônicas"):
            self.assertIn(esperado, titulos)

    def test_setas_e_pontos_so_aparecem_quando_ha_para_onde_ir(self):
        pai = Base()
        painel = self.ui.PainelGraficos(pai, grupos_de_teste(), gl.DISPOSICAO_LADO_A_LADO)
        painel.ajustar_todas(1100)
        tres, dois, um = painel.controles
        self.assertTrue(tres.visivel)
        self.assertTrue(tres.caixa.empacotado)
        self.assertEqual(tres.pontos.opts["text"], gl.pontos(3, 0))
        self.assertTrue(dois.visivel)
        self.assertEqual(dois.pontos.opts["text"], gl.pontos(2, 0))
        self.assertFalse(um.visivel)                              # um gráfico só: nada para arrastar
        self.assertFalse(um.caixa.empacotado)

    def test_setas_andam_e_ficam_cinzas_nas_pontas(self):
        pai = Base()
        painel = self.ui.PainelGraficos(pai, grupos_de_teste(), gl.DISPOSICAO_LADO_A_LADO)
        painel.ajustar_todas(1100)
        faixa, ctrl = painel.faixas[0], painel.controles[0]
        self.assertEqual(ctrl.b_ant.opts["state"], "disabled")
        self.assertEqual(ctrl.b_prox.opts["state"], "normal")
        ctrl.b_prox.clicar()
        self.rodar_animacao(faixa)
        self.assertEqual(ctrl.pontos.opts["text"], gl.pontos(3, 1))
        self.assertEqual((ctrl.b_ant.opts["state"], ctrl.b_prox.opts["state"]), ("normal", "normal"))
        ctrl.b_prox.clicar()
        self.rodar_animacao(faixa)
        self.assertEqual(ctrl.pontos.opts["text"], gl.pontos(3, 2))
        self.assertEqual(ctrl.b_prox.opts["state"], "disabled")
        ctrl.b_prox.clicar()                                      # desligado: não faz nada
        self.assertEqual(faixa.canvas.agendados, {})
        ctrl.b_ant.clicar()
        self.rodar_animacao(faixa)
        self.assertEqual(faixa.ativo, 1)

    def test_janela_larga_esconde_controles_que_nao_fazem_falta(self):
        pai = Base()
        painel = self.ui.PainelGraficos(pai, grupos_de_teste(), gl.DISPOSICAO_LADO_A_LADO)
        painel.ajustar_todas(1100)
        self.assertTrue(painel.controles[1].visivel)
        painel.ajustar_todas(2000)                                # 2 gráficos de 840 cabem juntos em 2000 px
        self.assertFalse(painel.controles[1].visivel)
        self.assertFalse(painel.controles[1].caixa.empacotado)
        painel.ajustar_todas(1100)
        self.assertTrue(painel.controles[1].caixa.empacotado)     # voltou a precisar

    def test_de_cima_para_baixo_empilha_e_nao_cria_faixas(self):
        pai = Base()
        painel = self.ui.PainelGraficos(pai, grupos_de_teste(), gl.DISPOSICAO_VERTICAL)
        self.assertEqual(painel.faixas, [])
        self.assertEqual(len(painel.imagens), 6)
        self.assertEqual(len(pai.children), 3)                    # continua agrupado: uma seção por grupo
        for sec, esperado in zip(pai.children, (3, 2, 1)):
            rotulos = [f for f in sec.children if "image" in f.opts]
            self.assertEqual(len(rotulos), esperado)
        primeira = painel.imagens[0]
        self.assertEqual(primeira.size, (840, 373))               # mesmo limite de largura que a tela tinha antes

    def test_disposicao_desconhecida_cai_em_lado_a_lado(self):
        painel = self.ui.PainelGraficos(Base(), grupos_de_teste(), "qualquer coisa")
        self.assertEqual(painel.disposicao, gl.DISPOSICAO_LADO_A_LADO)
        self.assertEqual(len(painel.faixas), 3)

    def test_sem_grupos_nao_cria_nada(self):
        pai = Base()
        painel = self.ui.PainelGraficos(pai, [], gl.DISPOSICAO_LADO_A_LADO)
        self.assertEqual((painel.imagens, painel.faixas, pai.children), ([], [], []))


class TestEscalaDaTela(unittest.TestCase):
    def test_usa_o_rastreador_do_customtkinter_quando_existe(self):
        rastreador = types.SimpleNamespace(get_widget_scaling=lambda w: 1.25)
        self.assertEqual(carregar_graficos_ui(rastreador).escala_da_tela(Base()), 1.25)

    def test_sem_rastreador_usa_o_dpi_do_tk(self):
        class Tela(Base):
            def winfo_fpixels(self, medida):
                return 144.0
        self.assertEqual(carregar_graficos_ui().escala_da_tela(Tela()), 1.5)

    def test_sem_nenhuma_informacao_e_um(self):
        self.assertEqual(carregar_graficos_ui().escala_da_tela(Base()), 1.0)

    def test_rastreador_que_falha_cai_no_dpi(self):
        def falha(w):
            raise KeyError(w)

        class Tela(Base):
            def winfo_fpixels(self, medida):
                return 120.0
        rastreador = types.SimpleNamespace(get_widget_scaling=falha)
        self.assertEqual(carregar_graficos_ui(rastreador).escala_da_tela(Tela()), 1.25)


# ====================================================================== gráficos desenhados na tela (animados)
from test_graficos_nativos import SPECS  # noqa: E402
import graficos_nativos as gn  # noqa: E402
import graficos_pintor as gp  # noqa: E402
sys.path.insert(0, os.path.join(RAIZ, "tools"))
from medir_desempenho_graficos import PintorAntigo  # noqa: E402  (o pintor de antes: referência única)


def cena(extensao=-90.0, texto="42", visivel=True, dx=0):
    """Uma forma de cada tipo, como o graficos_nativos monta."""
    return [
        {"t": "poli", "c": [dx, 0, dx + 10, 0, dx + 10, 10, dx, 10], "fill": "#fff", "outline": "#ccc", "suave": True},
        {"t": "ret", "c": (dx + 1, 1, dx + 5, 5), "fill": "#000"},
        {"t": "linha", "c": [dx, 0, dx + 5, 5], "fill": "#111", "largura": 2, "tracejado": (5, 3)},
        {"t": "texto", "c": (dx + 3, 3), "texto": texto, "tam": 11, "negrito": False, "fill": "#222", "ancora": "nw",
         "dica": "balão"},
        {"t": "oval", "c": (dx + 1, 1, dx + 3, 3), "fill": "#333", "visivel": visivel},
        {"t": "arco", "c": (dx, 0, dx + 20, 20), "inicio": 90.0, "extensao": extensao, "fill": "#444", "largura": 6},
    ]


class TestPintor(unittest.TestCase):
    def setUp(self):
        self.tela = TelaFalsa()
        self.dicas = {}
        self.pintor = gp.PintorCanvas(self.tela, FontesFalsas(), self.dicas)

    def pedidos(self):
        return [c[0] for c in self.tela.chamadas]

    def test_cria_uma_forma_de_cada_tipo_com_as_opcoes_certas(self):
        self.pintor.desenhar(cena(), 100, 5)
        f = [self.tela.formas[i] for i in sorted(self.tela.formas)]
        self.assertEqual([x["t"] for x in f], ["poli", "ret", "linha", "texto", "oval", "arco"])
        self.assertEqual(f[0]["c"], (100, 5, 110, 5, 110, 15, 100, 15))            # deslocada em (dx, dy)
        self.assertEqual((f[0]["smooth"], f[0]["outline"]), (True, "#ccc"))
        self.assertEqual((f[2]["dash"], f[2]["width"], f[2]["capstyle"]), ((5, 3), 2, "round"))
        self.assertEqual((f[3]["text"], f[3]["anchor"], f[3]["font"]), ("42", "nw", ("fonte", 11, False)))
        self.assertEqual((f[5]["start"], f[5]["extent"], f[5]["style"], f[5]["width"]), (90.0, -90.0, "arc", 6))
        self.assertEqual(f[5]["outline"], "#444")                                   # o traço do anel é a cor da fatia
        self.assertEqual(f[1]["outline"], "")

    def test_linha_sem_tracejado_nao_pede_dash(self):
        forma = {"t": "linha", "c": [0, 0, 5, 5], "fill": "#111", "largura": 2, "tracejado": None}
        self.pintor.desenhar([forma])
        self.assertNotIn("dash", self.tela.formas[1])

    def test_segundo_quadro_so_atualiza_o_que_mudou(self):
        self.pintor.desenhar(cena())
        self.tela.chamadas.clear()
        self.pintor.desenhar(cena())                       # nada mudou: nenhum pedido ao Tk
        self.assertEqual(self.tela.chamadas, [])
        self.pintor.desenhar(cena(extensao=-180.0))        # só o arco mudou
        self.assertEqual(self.tela.chamadas, [("config", 6, ("extent", "start"))])
        self.assertEqual(self.tela.formas[6]["extent"], -180.0)
        self.tela.chamadas.clear()
        self.pintor.desenhar(cena(extensao=-180.0, texto="43"))
        self.assertEqual(self.tela.chamadas, [("config", 4, ("text",))])
        self.tela.chamadas.clear()
        self.pintor.desenhar(cena(extensao=-180.0, texto="43", dx=7))   # tudo andou para o lado: só coordenadas
        self.assertEqual(set(self.pedidos()), {"coords"})
        self.assertEqual(self.pedidos().count("coords"), 6)

    def test_visibilidade_liga_e_desliga(self):
        self.pintor.desenhar(cena(visivel=False))
        self.assertEqual(self.tela.formas[5]["state"], "hidden")          # já nasce escondida
        self.assertNotIn("state", self.tela.formas[4])
        self.tela.chamadas.clear()
        self.pintor.desenhar(cena(visivel=True))
        self.assertEqual(self.tela.chamadas, [("config", 5, ("state",))])
        self.assertEqual(self.tela.formas[5]["state"], "normal")

    def test_dicas_ficam_registradas_pelo_numero_do_item(self):
        self.pintor.desenhar(cena())
        self.assertEqual(self.dicas, {4: "balão"})

    def test_cena_de_outra_forma_recria_tudo_e_limpa_as_dicas_velhas(self):
        self.pintor.desenhar(cena())
        self.pintor.desenhar(cena()[:3])
        self.assertEqual(sorted(self.tela.formas), [7, 8, 9])
        self.assertEqual(self.dicas, {})

    def test_apagar(self):
        self.pintor.desenhar(cena())
        self.pintor.apagar()
        self.assertEqual((self.tela.formas, self.dicas, self.pintor.itens), ({}, {}, []))
        self.pintor.desenhar(cena())                                      # e dá para desenhar de novo
        self.assertEqual(len(self.tela.formas), 6)

    def test_forma_desconhecida_avisa(self):
        with self.assertRaises(ValueError):
            self.pintor.desenhar([{"t": "estrela", "c": (0, 0)}])

    def test_cenas_reais_passam_pelo_pintor_em_todos_os_progressos(self):
        for nome, spec in SPECS.items():
            tela = TelaFalsa()
            pintor = gp.PintorCanvas(tela, FontesFalsas())
            fontes = FontesFalsas()
            for prog in (0.0, 0.3, 0.6, 1.0):
                formas, _ = gn.construir(spec, 840, prog, fontes.medir, 1.0)
                pintor.desenhar(formas, 12, 0)
            self.assertEqual(len(tela.formas), len(formas), nome)         # nunca criou formas a mais durante a animação
            self.assertEqual(self.contar("criar", tela), len(formas), nome)

    def test_poligono_suave_leva_os_passos_da_curva(self):
        self.pintor.desenhar(cena())
        suave = self.tela.formas[1]
        self.assertTrue(suave["smooth"])
        self.assertEqual(suave["splinesteps"], gp.PASSOS_DA_CURVA)
        # poligono sem curva (ou outro tipo de forma) nao pede o ajuste
        reto = [{"t": "poli", "c": [0, 0, 5, 0, 5, 5], "fill": "#fff", "outline": "", "suave": False}]
        tela = TelaFalsa()
        gp.PintorCanvas(tela, FontesFalsas()).desenhar(reto)
        self.assertNotIn("splinesteps", tela.formas[1])
        self.assertFalse(tela.formas[1]["smooth"])
        self.assertNotIn("splinesteps", self.tela.formas[2])

    def test_passos_da_curva_podem_ser_trocados(self):
        tela = TelaFalsa()
        gp.PintorCanvas(tela, FontesFalsas(), passos_da_curva=5).desenhar(cena())
        self.assertEqual(tela.formas[1]["splinesteps"], 5)

    def test_so_o_deslocamento_mudou_move_tudo_uma_vez(self):
        self.pintor.desenhar(cena(), 0, 0)
        self.tela.chamadas.clear()
        self.pintor.desenhar(cena(), 7, 3)                  # a mesma cena, em outro lugar da faixa
        self.assertEqual(self.pedidos(), ["coords"] * 6)
        self.assertEqual(self.tela.formas[2]["c"], (8, 4, 12, 8))
        self.tela.chamadas.clear()
        self.pintor.desenhar(cena(), 7, 3)                  # e de novo no mesmo lugar: nada a fazer
        self.assertEqual(self.tela.chamadas, [])
        self.pintor.desenhar(cena(), 0, 0)                  # voltou
        self.assertEqual(self.pedidos(), ["coords"] * 6)
        self.assertEqual(self.tela.formas[2]["c"], (1, 1, 5, 5))

    def test_pede_ao_tk_exatamente_o_mesmo_que_o_pintor_de_antes(self):
        """O pintor foi reescrito para gastar menos Python por quadro. Em todos os gráficos reais, numa sequência com
        progresso que vai, volta e repete, e com o deslocamento mudando, ele pede ao Tk as MESMAS coisas, na mesma
        ordem, que o pintor antigo (copiado aqui como referência), e a tela termina igual."""
        fontes = FontesFalsas()
        progressos = (0.0, 0.1, 0.1, 0.5, 0.35, 1.0, 1.0, 1.0, 0.0, 0.8, 0.8)
        deslocamentos = (10, 10, 10, 10, 10, 10, 10, 25, 25, 25, 10)
        for nome, spec in SPECS.items():
            novo_tela, velho_tela = TelaFalsa(), TelaFalsa()
            novo = gp.PintorCanvas(novo_tela, fontes)
            velho = PintorAntigo(velho_tela, fontes)
            for prog, dx in zip(progressos, deslocamentos):
                formas, _ = gn.construir(spec, 840, prog, fontes.medir, 1.0)
                novo.desenhar(formas, dx, 0)
                velho.desenhar(formas, dx, 0)
                self.assertEqual(novo_tela.chamadas, velho_tela.chamadas, f"{nome} p={prog} dx={dx}")
            self.assertEqual(novo_tela.formas, velho_tela.formas, nome)
            self.assertGreater(len(novo_tela.chamadas), len(formas), nome)       # a sequência não foi trivial

    def test_cena_alterada_por_fora_continua_certa(self):
        """As coordenadas guardadas são cópias: mexer na lista da cena depois de desenhar não confunde o pintor."""
        forma = {"t": "linha", "c": [0, 0, 5, 5], "fill": "#111", "largura": 2, "tracejado": None}
        self.pintor.desenhar([forma])
        self.pintor.desenhar([forma])                        # o 2º quadro já passa pela atualização (nada muda)
        self.assertEqual(self.tela.chamadas, [("criar", 1)])
        forma["c"][2] = 9                                    # a MESMA lista, alterada por fora
        self.pintor.desenhar([forma])
        self.assertEqual(self.tela.formas[1]["c"], (0, 0, 9, 5))

    @staticmethod
    def contar(tipo, tela):
        return sum(1 for c in tela.chamadas if c[0] == tipo)


class TestCartasNativas(BaseDosTestes):
    def nova_faixa_nativa(self, nomes=("barras_v", "linhas", "roscas"), largura=1100, escala=1.0, **kw):
        pai = Base()
        cartas = [self.ui.CardNativo(SPECS[n]) for n in nomes]
        faixa = self.ui.FaixaHorizontal(pai, cartas, escala=escala, fontes=FontesFalsas(), **kw)
        faixa.canvas.bindings["<Configure>"](Evento(width=largura))
        return faixa

    @staticmethod
    def textos(faixa):
        return [f["text"] for f in faixa.canvas.formas.values() if f["t"] == "texto"]

    @staticmethod
    def barras(faixa):
        """As barras do gráfico de barras (a mais alta tem um tom mais escuro)."""
        cores = ("#4caf50", gn.escurecer("#4caf50"))
        return [f for f in faixa.canvas.formas.values() if f["t"] == "poli" and f.get("fill") in cores]

    def test_desenha_logo_a_moldura_de_todos_e_so_anima_os_que_aparecem(self):
        faixa = self.nova_faixa_nativa(largura=1100)
        self.assertEqual(self.textos(faixa).count("Título do gráfico"), 3)         # os três já têm moldura e título
        self.assertEqual([c.inicio is not None for c in faixa.cards], [True, False, False])
        self.assertEqual(len(faixa.canvas.agendados), 1)                           # um único relógio da animação
        self.assertEqual(faixa.canvas.itens, [])                                   # nenhuma imagem
        self.assertEqual(faixa.imagens, [])

    def test_antes_de_comecar_nada_de_dados_aparece(self):
        faixa = self.nova_faixa_nativa(("barras_v",), largura=1100)
        barras = self.barras(faixa)
        self.assertEqual(len(barras), len(SPECS["barras_v"]["x"]))
        self.assertTrue(all(b.get("state") == "hidden" for b in barras))

    def test_entrada_progride_com_o_relogio_e_termina_sozinha(self):
        faixa = self.nova_faixa_nativa(("barras_v",), largura=1100)
        carta = faixa.cards[0]
        progressos = []
        for _ in range(100):
            if not faixa.canvas.agendados:
                break
            self.relogio.avancar(0.016)
            faixa.canvas.executar_agendados()
            progressos.append(carta.p)
        self.assertEqual(progressos, sorted(progressos))                          # só cresce
        self.assertEqual(progressos[-1], 1.0)
        self.assertTrue(carta.pronto)
        self.assertEqual(faixa.canvas.agendados, {})                              # parou de agendar quadros
        self.assertAlmostEqual(len(progressos) * 0.016, gl.DURACAO_ENTRADA, delta=0.05)
        barras = self.barras(faixa)
        self.assertEqual(sum(1 for b in barras if b.get("state") != "hidden"),
                         sum(1 for v in SPECS["barras_v"]["y"] if v))             # todas as barras com valor aparecem

    def test_quadro_final_e_igual_ao_da_cena_calculada_direto(self):
        faixa = self.nova_faixa_nativa(("linhas",), largura=1100)
        self.rodar_animacao(faixa)
        carta = faixa.cards[0]
        esperado, _ = gn.construir(SPECS["linhas"], carta.largura, 1.0, faixa.fontes.medir, 1.0, carta.altura)
        desenhado = [faixa.canvas.formas[i] for i in sorted(faixa.canvas.formas)]
        self.assertEqual([f["t"] for f in desenhado], [f["t"] for f in esperado])
        for d, e in zip(desenhado, esperado):
            self.assertEqual(d["c"], tuple(e["c"]))

    def test_so_um_pouco_depois_do_anterior_e_com_atraso_inicial(self):
        faixa = self.nova_faixa_nativa(largura=1900, atraso=0.5)    # cabem dois gráficos inteiros
        a, b, c = faixa.cards
        self.assertEqual(a.inicio, self.relogio() + 0.5)
        self.assertAlmostEqual(b.inicio - a.inicio, gl.ATRASO_ENTRE_CARDS)
        self.assertIsNone(c.inicio)
        # durante o atraso nada é redesenhado
        self.relogio.avancar(0.3)
        faixa.canvas.chamadas.clear()
        faixa.canvas.executar_agendados()
        self.assertEqual(faixa.canvas.chamadas, [])
        self.assertEqual((a.p, b.p), (0.0, 0.0))

    def test_o_gafico_que_aparece_depois_anima_uma_vez_so(self):
        faixa = self.nova_faixa_nativa(largura=1100)
        self.rodar_animacao(faixa)
        a, b, c = faixa.cards
        self.assertTrue(a.pronto)
        self.assertEqual((b.p, c.p, b.inicio, c.inicio), (0.0, 0.0, None, None))
        faixa.ir_para(1)                                                         # o segundo passa a aparecer
        self.rodar_animacao(faixa)                                               # (encaixe e entrada juntos)
        self.assertIsNotNone(b.inicio)
        self.assertIsNone(c.inicio)
        self.assertTrue(b.pronto)
        inicio_b = b.inicio
        faixa.ir_para(0)
        self.rodar_animacao(faixa)
        faixa.ir_para(1)
        self.rodar_animacao(faixa)
        self.assertEqual(b.inicio, inicio_b)                                     # não repete a entrada
        self.assertTrue(a.pronto and b.pronto)

    def test_arrastar_ate_ver_o_terceiro_tambem_inicia_a_entrada_dele(self):
        faixa = self.nova_faixa_nativa(largura=1100)
        c = faixa.canvas
        c.bindings["<ButtonPress-1>"](Evento(x_root=900))
        c.bindings["<B1-Motion>"](Evento(x_root=100))                            # 800 px para a esquerda
        self.assertIsNotNone(faixa.cards[1].inicio)
        self.assertIsNone(faixa.cards[2].inicio)
        c.bindings["<B1-Motion>"](Evento(x_root=-700))
        self.assertIsNotNone(faixa.cards[2].inicio)

    def test_todos_os_graficos_da_faixa_tem_a_mesma_altura(self):
        faixa = self.nova_faixa_nativa(("barras_h", "roscas", "barras_v"), largura=1100)
        alturas = {c.altura for c in faixa.cards}
        self.assertEqual(len(alturas), 1)
        naturais = [gn.altura_natural(c.spec, c.largura, faixa.fontes.medir) for c in faixa.cards]
        self.assertEqual(alturas, {max(naturais)})
        self.assertEqual(faixa.canvas.opts["height"], max(naturais))
        self.assertEqual(faixa.canvas.opts["scrollregion"][3], max(naturais))

    def test_mudar_a_largura_no_meio_da_entrada_continua_de_onde_parou(self):
        faixa = self.nova_faixa_nativa(("barras_v",), largura=1100)
        carta = faixa.cards[0]
        for _ in range(20):
            self.relogio.avancar(0.016)
            faixa.canvas.executar_agendados()
        parcial = carta.p
        self.assertTrue(0 < parcial < 1)
        faixa.canvas.bindings["<Configure>"](Evento(width=700))
        faixa.canvas.executar_agendados()                                        # o redesenho com espera de 120 ms
        self.assertEqual(carta.largura, 700 - 0)
        self.assertEqual(carta.p, parcial)                                       # não voltou ao zero nem pulou ao fim
        self.assertTrue(faixa.canvas.agendados)                                  # e a animação continua
        self.rodar_animacao(faixa)
        self.assertTrue(carta.pronto)

    def test_gráfico_pronto_continua_pronto_depois_de_redimensionar(self):
        faixa = self.nova_faixa_nativa(("barras_v",), largura=1100)
        self.rodar_animacao(faixa)
        faixa.canvas.bindings["<Configure>"](Evento(width=700))
        faixa.canvas.executar_agendados()
        self.assertTrue(faixa.cards[0].pronto)
        self.assertEqual(faixa.canvas.agendados, {})                             # sem repetir a animação
        barras = self.barras(faixa)
        self.assertTrue(any(b.get("state") != "hidden" for b in barras))         # e já redesenhado cheio

    def test_destruir_a_faixa_para_a_animacao(self):
        faixa = self.nova_faixa_nativa(("barras_v",), largura=1100)
        c = faixa.canvas
        self.assertTrue(c.agendados)
        c.bindings["<Destroy>"](Evento())
        self.assertEqual(c.agendados, {})
        self.assertTrue(c.cancelados)
        formas = dict(c.formas)
        c.executar_agendados()                                                   # um `after` que chegou tarde
        faixa._passo_entrada()
        self.assertEqual(c.formas, formas)

    def test_escala_do_windows_aumenta_a_fonte_e_a_largura_do_grafico(self):
        faixa = self.nova_faixa_nativa(("barras_v",), largura=1900, escala=1.5)
        carta = faixa.cards[0]
        self.assertEqual(carta.largura, 840 * 1.5)
        titulo = next(f for f in faixa.canvas.formas.values() if f["t"] == "texto" and f["text"] == "Título do gráfico")
        self.assertEqual(titulo["font"], ("fonte", round(gn.TAM_TITULO * 1.5), True))

    def test_imagens_e_graficos_na_mesma_faixa(self):
        pai = Base()
        faixa = self.ui.FaixaHorizontal(pai, [imagem(), self.ui.CardNativo(SPECS["roscas"])], escala=1.0,
                                        fontes=FontesFalsas())
        faixa.canvas.bindings["<Configure>"](Evento(width=1100))
        self.assertEqual((len(faixa.canvas.itens), len(faixa.imagens)), (1, 1))
        self.assertTrue(faixa.canvas.formas)

    def test_gráfico_unico_fica_no_meio_quando_pedido(self):
        faixa = self.nova_faixa_nativa(("barras_v",), largura=1100, centralizar=True)
        fundo = faixa.canvas.formas[1]
        self.assertEqual(fundo["t"], "poli")
        self.assertAlmostEqual(min(fundo["c"][0::2]), (1100 - 840) / 2 + 0.5)    # (1100 - 840) / 2 + a borda
        sem = self.nova_faixa_nativa(("barras_v",), largura=1100)
        self.assertAlmostEqual(min(sem.canvas.formas[1]["c"][0::2]), 0.5)


class TestBalao(BaseDosTestes):
    def faixa_pronta(self):
        pai = Base()
        faixa = self.ui.FaixaHorizontal(pai, [self.ui.CardNativo(SPECS["barras_v"])], escala=1.0,
                                        fontes=FontesFalsas())
        faixa.canvas.bindings["<Configure>"](Evento(width=1100))
        self.rodar_animacao(faixa)
        return faixa

    @staticmethod
    def barra_do_dia(faixa, dica):
        item = next(i for i, texto in faixa.dicas.items() if texto == dica)
        x0, y0, x1, y1 = faixa.canvas.bbox(item)
        return item, (x0 + x1) / 2, (y0 + y1) / 2

    def balao(self, faixa):
        fundo, texto = faixa._dica
        return faixa.canvas.formas[fundo], faixa.canvas.formas[texto]

    def test_mostra_o_valor_da_barra_sob_o_ponteiro(self):
        faixa = self.faixa_pronta()
        _, x, y = self.barra_do_dia(faixa, "Dia 9: 9")
        faixa.canvas.bindings["<Motion>"](Evento(x=x, y=y))
        fundo, texto = self.balao(faixa)
        self.assertEqual((texto["text"], texto["state"], fundo["state"]), ("Dia 9: 9", "normal", "normal"))
        # o balão fica perto do ponteiro, à direita e abaixo
        self.assertGreater(fundo["c"][0], x)
        self.assertGreater(fundo["c"][1], y)
        self.assertGreater(fundo["c"][2] - fundo["c"][0], 30)

    def test_sai_do_canvas_ou_arrasta_e_o_balao_some(self):
        faixa = self.faixa_pronta()
        _, x, y = self.barra_do_dia(faixa, "Dia 9: 9")
        faixa.canvas.bindings["<Motion>"](Evento(x=x, y=y))
        faixa.canvas.bindings["<Leave>"](Evento())
        self.assertEqual(self.balao(faixa)[1]["state"], "hidden")
        faixa.canvas.bindings["<Motion>"](Evento(x=x, y=y))
        faixa.canvas.bindings["<ButtonPress-1>"](Evento(x_root=10))
        self.assertEqual(self.balao(faixa)[1]["state"], "hidden")
        faixa.canvas.bindings["<Motion>"](Evento(x=x, y=y))                       # com o botão apertado: sem balão
        self.assertEqual(self.balao(faixa)[1]["state"], "hidden")
        faixa.canvas.bindings["<ButtonRelease-1>"](Evento(x_root=10))
        faixa.canvas.bindings["<Motion>"](Evento(x=x, y=y))
        self.assertEqual(self.balao(faixa)[1]["state"], "normal")

    def test_longe_de_qualquer_barra_esconde(self):
        faixa = self.faixa_pronta()
        _, x, y = self.barra_do_dia(faixa, "Dia 9: 9")
        faixa.canvas.bindings["<Motion>"](Evento(x=x, y=y))
        faixa.canvas.bindings["<Motion>"](Evento(x=x, y=2))                       # em cima, no título
        self.assertEqual(self.balao(faixa)[1]["state"], "hidden")

    def test_barra_ainda_escondida_pela_animacao_nao_mostra_balao(self):
        pai = Base()
        faixa = self.ui.FaixaHorizontal(pai, [self.ui.CardNativo(SPECS["barras_v"])], escala=1.0, fontes=FontesFalsas())
        faixa.canvas.bindings["<Configure>"](Evento(width=1100))                  # p = 0: barras escondidas
        item, x, y = self.barra_do_dia(faixa, "Dia 9: 9")
        self.assertEqual(faixa.canvas.formas[item]["state"], "hidden")
        faixa.canvas.bindings["<Motion>"](Evento(x=x, y=y))
        self.assertIsNone(faixa._dica)

    def test_perto_da_borda_direita_o_balao_vai_para_a_esquerda(self):
        faixa = self.faixa_pronta()
        item, x, y = self.barra_do_dia(faixa, "Dia 31: 5")
        faixa.canvas.largura_tela = int(x + 20)                                    # só 20 px sobram à direita
        faixa.canvas.bindings["<Motion>"](Evento(x=x, y=y))
        fundo, _ = self.balao(faixa)
        self.assertLess(fundo["c"][2], x)

    def test_perto_do_fundo_o_balao_vai_para_cima(self):
        faixa = self.faixa_pronta()
        _, x, y = self.barra_do_dia(faixa, "Dia 9: 9")
        faixa.canvas.altura_tela = int(y + 5)
        faixa.canvas.bindings["<Motion>"](Evento(x=x, y=y))
        fundo, _ = self.balao(faixa)
        self.assertLess(fundo["c"][3], y)

    def test_roda_do_mouse_esconde_o_balao_sem_impedir_a_tela_de_rolar(self):
        faixa = self.faixa_pronta()
        _, x, y = self.barra_do_dia(faixa, "Dia 9: 9")
        faixa.canvas.bindings["<Motion>"](Evento(x=x, y=y))
        resultado = faixa.canvas.bindings["<MouseWheel>"](Evento(delta=120))
        self.assertIsNone(resultado)                                               # nunca "break": a tela continua rolando
        self.assertEqual(self.balao(faixa)[1]["state"], "hidden")

    def test_faixa_de_imagens_nao_tem_balao(self):
        faixa = self.nova_faixa(2, largura=1100)
        faixa.canvas.bindings["<Motion>"](Evento(x=10, y=10))
        self.assertIsNone(faixa._dica)

    def test_redesenhar_a_faixa_zera_os_baloes_antigos(self):
        faixa = self.faixa_pronta()
        _, x, y = self.barra_do_dia(faixa, "Dia 9: 9")
        faixa.canvas.bindings["<Motion>"](Evento(x=x, y=y))
        faixa.ajustar(900)
        self.assertIsNone(faixa._dica)
        self.assertTrue(faixa.dicas)                                               # os novos já estão registrados
        self.assertTrue(all(i in faixa.canvas.formas for i in faixa.dicas))        # e nenhum aponta para item apagado


def grupos_nativos():
    def itens(*nomes):
        return [(n, n, SPECS[n]) for n in nomes]
    return [
        {"id": "a", "titulo": "Atendimentos", "cor": "#4caf50", "descricao": "texto",
         "graficos": itens("barras_v", "linhas", "roscas")},
        {"id": "b", "titulo": "Dieta", "cor": "#ef6c00", "descricao": "", "graficos": itens("barras_h", "vazio")},
    ]


class TestPainelNativo(BaseDosTestes):
    def test_conteudo_decide_o_tipo_da_carta(self):
        painel = self.ui.PainelGraficos(Base(), grupos_nativos(), gl.DISPOSICAO_LADO_A_LADO, fontes=FontesFalsas())
        tipos_ = [[type(c).__name__ for c in f.cards] for f in painel.faixas]
        self.assertEqual(tipos_, [["CardNativo"] * 3, ["CardNativo"] * 2])
        self.assertEqual(painel.imagens, [])
        misto = [{"id": "m", "titulo": "M", "cor": "#000000", "descricao": "",
                  "graficos": [("a", "A", png_de()), ("b", "B", SPECS["barras_v"])]}]
        painel = self.ui.PainelGraficos(Base(), misto, gl.DISPOSICAO_LADO_A_LADO, fontes=FontesFalsas())
        self.assertEqual([type(c).__name__ for c in painel.faixas[0].cards], ["CardImagem", "CardNativo"])
        self.assertEqual(len(painel.imagens), 1)

    def test_fontes_so_sao_criadas_quando_ha_grafico_animado(self):
        painel = self.ui.PainelGraficos(Base(), grupos_de_teste(), gl.DISPOSICAO_LADO_A_LADO)
        self.assertIsNone(painel._fontes)                                          # só imagens: nada de Tk font
        self.assertTrue(all(f._fontes is None for f in painel.faixas))

    def test_as_faixas_dividem_as_mesmas_fontes(self):
        fontes = FontesFalsas()
        painel = self.ui.PainelGraficos(Base(), grupos_nativos(), gl.DISPOSICAO_LADO_A_LADO, fontes=fontes)
        self.assertTrue(all(f.fontes is fontes for f in painel.faixas))

    def test_de_cima_para_baixo_um_grafico_por_faixa_cada_um_no_meio(self):
        painel = self.ui.PainelGraficos(Base(), grupos_nativos(), gl.DISPOSICAO_VERTICAL, fontes=FontesFalsas())
        self.assertEqual((painel.faixas, painel.controles), ([], []))
        self.assertEqual(len(painel.faixas_empilhadas), 5)
        self.assertTrue(all(f.centralizar and len(f.cards) == 1 for f in painel.faixas_empilhadas))
        # dentro do grupo, cada gráfico começa um pouco depois do anterior
        self.assertEqual([round(f.atraso, 2) for f in painel.faixas_empilhadas],
                         [0.0, 0.12, 0.24, 0.0, 0.12])
        painel.ajustar_todas(1100)
        self.assertTrue(all(f.cards[0].largura == 840 for f in painel.faixas_empilhadas))
        self.assertTrue(all(f.cards[0].x == 130 for f in painel.faixas_empilhadas))
        self.assertTrue(all(f.canvas.opts["cursor"] == "" for f in painel.faixas_empilhadas))   # não arrasta

    def test_de_cima_para_baixo_com_imagens_continua_como_antes(self):
        painel = self.ui.PainelGraficos(Base(), grupos_de_teste(), gl.DISPOSICAO_VERTICAL)
        self.assertEqual(painel.faixas_empilhadas, [])
        self.assertEqual(len(painel.imagens), 6)

    def test_ajustar_todas_desenha_lado_a_lado_e_empilhadas(self):
        painel = self.ui.PainelGraficos(Base(), grupos_nativos(), gl.DISPOSICAO_LADO_A_LADO, fontes=FontesFalsas())
        painel.ajustar_todas(1100)
        self.assertTrue(all(f.canvas.formas for f in painel.faixas))
        self.assertTrue(all(c.inicio is not None for f in painel.faixas for c in f.cards[:1]))


class RitmoGravador(gl.Ritmo):
    """Ritmo que também guarda o que o desenho informou, quadro a quadro."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.registros = []

    def registrar_quadro(self, custo, periodo=None):
        self.registros.append((custo, periodo))
        super().registrar_quadro(custo, periodo)


class TestRitmoNasFaixas(BaseDosTestes):
    """A animação segue o ritmo: completa (16 ms, 100%), reduzida (33 ms, 60%) ou nenhuma (gráfico já pronto)."""

    def nova_faixa_nativa(self, nomes=("barras_v", "linhas", "roscas"), largura=1100, ritmo=None, **kw):
        cartas = [self.ui.CardNativo(SPECS[n]) for n in nomes]
        faixa = self.ui.FaixaHorizontal(Base(), cartas, escala=1.0, fontes=FontesFalsas(), ritmo=ritmo, **kw)
        faixa.canvas.bindings["<Configure>"](Evento(width=largura))
        return faixa

    @staticmethod
    def intervalos(faixa):
        return sorted(ms for ms, _ in faixa.canvas.agendados.values())

    def rodar_quadros(self, faixa, passo, limite=200):
        quadros = 0
        while faixa.canvas.agendados:
            quadros += 1
            self.assertLess(quadros, limite, "a animação não terminou")
            self.relogio.avancar(passo)
            faixa.canvas.executar_agendados()
        return quadros

    def estado_final(self, faixa):
        """Formas que o canvas deveria ter com todos os gráficos prontos (cena calculada direto, progresso 1)."""
        esperado = []
        for carta in faixa.cards:
            formas, _ = gn.construir(carta.spec, carta.largura, 1.0, faixa.fontes.medir, 1.0, carta.altura)
            esperado += [(f["t"], tuple(x + (carta.x if i % 2 == 0 else 0) for i, x in enumerate(f["c"])),
                          f.get("texto"), "normal" if f.get("visivel", True) else "hidden") for f in formas]
        return esperado

    @staticmethod
    def desenhado(faixa):
        return [(f["t"], f["c"], f.get("text"), f.get("state", "normal"))
                for _, f in sorted(faixa.canvas.formas.items())]

    # ------------------------------------------------------------------ completo (o que já existia)
    def test_sem_ritmo_informado_a_animacao_e_completa(self):
        faixa = self.nova_faixa_nativa(("barras_v",))
        self.assertEqual(faixa.ritmo.modo, gl.DESEMPENHO_COMPLETO)
        self.assertEqual(self.intervalos(faixa), [16])

    # ------------------------------------------------------------------ reduzido
    def test_reduzido_usa_33_ms_e_dura_60_por_cento(self):
        ritmo = gl.Ritmo(gl.DESEMPENHO_AUTOMATICO, gl.NIVEL_REDUZIDO, "teste")
        faixa = self.nova_faixa_nativa(("barras_v",), ritmo=ritmo)
        self.assertEqual(self.intervalos(faixa), [33])
        quadros = self.rodar_quadros(faixa, 0.033)
        self.assertTrue(faixa.cards[0].pronto)
        self.assertAlmostEqual(quadros * 0.033, gl.DURACAO_ENTRADA * 0.6, delta=0.07)
        completo = self.nova_faixa_nativa(("barras_v",), ritmo=gl.Ritmo(gl.DESEMPENHO_COMPLETO))
        quadros_completo = self.rodar_quadros(completo, 0.016)
        self.assertLess(quadros, quadros_completo / 2.5)                  # muito menos quadros para o mesmo gráfico

    def test_reduzido_encurta_tambem_o_atraso_entre_graficos(self):
        ritmo = gl.Ritmo(gl.DESEMPENHO_AUTOMATICO, gl.NIVEL_REDUZIDO)
        faixa = self.nova_faixa_nativa(largura=1900, atraso=0.5, ritmo=ritmo)
        a, b, _ = faixa.cards
        fator = gl.FATOR_DURACAO[gl.NIVEL_REDUZIDO]
        self.assertAlmostEqual(a.inicio, self.relogio() + 0.5 * fator)
        self.assertAlmostEqual(b.inicio - a.inicio, gl.ATRASO_ENTRE_CARDS * fator)

    def test_reduzido_encaixa_mais_rapido_e_com_menos_quadros(self):
        completo = self.nova_faixa_nativa(ritmo=gl.Ritmo(gl.DESEMPENHO_COMPLETO))
        self.rodar_quadros(completo, 0.016)
        completo.ir_para(1)
        quadros_c = 0
        while completo.canvas.agendados and quadros_c < 200:
            quadros_c += 1
            self.relogio.avancar(0.016)
            completo.canvas.executar_agendados()
        reduzido = self.nova_faixa_nativa(ritmo=gl.Ritmo(gl.DESEMPENHO_AUTOMATICO, gl.NIVEL_REDUZIDO))
        self.rodar_quadros(reduzido, 0.033)
        reduzido.ir_para(1)
        quadros_r = 0
        while reduzido.canvas.agendados and quadros_r < 200:
            quadros_r += 1
            self.relogio.avancar(0.033)
            reduzido.canvas.executar_agendados()
        self.assertEqual(reduzido.deslocamento, completo.deslocamento)   # chegou ao mesmo lugar
        self.assertLess(quadros_r, quadros_c)

    def test_o_quadro_do_encaixe_tambem_espera_o_intervalo_do_nivel(self):
        for nivel, esperado in ((gl.NIVEL_COMPLETO, 16), (gl.NIVEL_REDUZIDO, 33)):
            faixa = self.nova_faixa_nativa(ritmo=gl.Ritmo(gl.DESEMPENHO_AUTOMATICO, nivel))
            self.rodar_quadros(faixa, 0.033)
            faixa.ir_para(1)
            self.assertEqual(faixa.canvas.agendados[faixa._job_animacao][0], esperado, nivel)

    def test_encaixe_cancelado_e_retomado_comeca_sem_quadro_anterior(self):
        ritmo = RitmoGravador(gl.DESEMPENHO_COMPLETO)
        faixa = self.nova_faixa_nativa(ritmo=ritmo)
        self.rodar_quadros(faixa, 0.016)
        faixa.ir_para(1)
        for _ in range(3):
            self.relogio.avancar(0.016)
            faixa.canvas.executar_agendados()
        faixa.canvas.bindings["<ButtonPress-1>"](Evento(x_root=500))             # o dedo pega a faixa: cancela o encaixe
        self.assertIsNone(faixa._job_animacao)
        antes = len(ritmo.registros)
        self.relogio.avancar(30.0)
        faixa.ir_para(0)
        self.assertEqual(ritmo.registros[antes][1], None)                        # nada de "30 s desde o quadro anterior"

    # ------------------------------------------------------------------ sem animação
    def test_sem_animacao_pinta_tudo_pronto_e_sem_relogio(self):
        faixa = self.nova_faixa_nativa(ritmo=gl.Ritmo(gl.DESEMPENHO_ECONOMICO))
        self.assertEqual(faixa.canvas.agendados, {})                               # nenhum quadro agendado
        self.assertTrue(all(c.pronto and c.p == 1.0 for c in faixa.cards))        # inclusive os que nem apareceram
        self.assertEqual(self.desenhado(faixa), self.estado_final(faixa))        # e é o mesmo desenho final
        self.assertEqual([c for c in faixa.canvas.chamadas if c[0] == "coords"], [])   # pintou uma vez só
        self.assertEqual([c.inicio is not None for c in faixa.cards], [True, False, False])

    def test_o_desenho_final_e_igual_em_qualquer_nivel(self):
        finais = []
        for ritmo, passo in ((gl.Ritmo(gl.DESEMPENHO_COMPLETO), 0.016),
                             (gl.Ritmo(gl.DESEMPENHO_AUTOMATICO, gl.NIVEL_REDUZIDO), 0.033),
                             (gl.Ritmo(gl.DESEMPENHO_ECONOMICO), 0.016)):
            faixa = self.nova_faixa_nativa(("barras_v", "linhas"), largura=1900, ritmo=ritmo)
            self.rodar_quadros(faixa, passo)
            finais.append(self.desenhado(faixa))
        self.assertEqual(finais[0], finais[1])
        self.assertEqual(finais[0], finais[2])

    def test_sem_animacao_o_grafico_que_aparece_depois_ja_esta_pronto(self):
        faixa = self.nova_faixa_nativa(ritmo=gl.Ritmo(gl.DESEMPENHO_ECONOMICO))
        faixa.ir_para(1)
        self.assertEqual(faixa.canvas.agendados, {})
        self.assertEqual(faixa.deslocamento, faixa.carrossel.x_da_posicao(1))    # foi direto, sem encaixe animado
        self.assertEqual(faixa.ativo, 1)
        self.assertIsNotNone(faixa.cards[1].inicio)
        self.assertTrue(all(c.pronto for c in faixa.cards))

    def test_sem_animacao_arrastar_continua_seguindo_o_mouse(self):
        faixa = self.nova_faixa_nativa(ritmo=gl.Ritmo(gl.DESEMPENHO_ECONOMICO))
        c = faixa.canvas
        c.bindings["<ButtonPress-1>"](Evento(x_root=900))
        c.bindings["<B1-Motion>"](Evento(x_root=500))                             # 400 px para a esquerda
        self.assertEqual(faixa.deslocamento, 400)
        c.bindings["<ButtonRelease-1>"](Evento(x_root=500))
        self.assertEqual(faixa.deslocamento, faixa.carrossel.x_da_posicao(faixa.ativo))   # soltou: encaixou na hora
        self.assertEqual(c.agendados, {})

    def test_sem_animacao_redimensionar_nao_agenda_nada(self):
        faixa = self.nova_faixa_nativa(("barras_v",), ritmo=gl.Ritmo(gl.DESEMPENHO_ECONOMICO))
        faixa.canvas.bindings["<Configure>"](Evento(width=700))
        faixa.canvas.executar_agendados()                                        # o redesenho com espera de 120 ms
        self.assertEqual(faixa.cards[0].largura, 700)
        self.assertTrue(faixa.cards[0].pronto)
        self.assertEqual(faixa.canvas.agendados, {})

    def test_faixa_de_imagens_nao_muda_com_o_ritmo(self):
        faixa = self.ui.FaixaHorizontal(Base(), [imagem(), imagem()], escala=1.0,
                                        ritmo=gl.Ritmo(gl.DESEMPENHO_ECONOMICO))
        faixa.canvas.bindings["<Configure>"](Evento(width=1100))
        self.assertEqual(len(faixa.canvas.itens), 2)
        faixa.ir_para(1)
        self.assertEqual(faixa.deslocamento, faixa.carrossel.x_da_posicao(1))

    # ------------------------------------------------------------------ o ritmo muda no meio da animação
    def test_ao_descer_para_sem_animacao_a_entrada_termina_no_proximo_quadro(self):
        ritmo = gl.Ritmo()
        faixa = self.nova_faixa_nativa(("barras_v",), ritmo=ritmo)
        for _ in range(5):
            self.relogio.avancar(0.016)
            faixa.canvas.executar_agendados()
        self.assertTrue(0 < faixa.cards[0].p < 1)
        for _ in range(2 * gl.AMOSTRAS_PARA_DECIDIR):                           # o computador "ficou lento"
            ritmo.registrar_quadro(0.5, 1.0)
        self.assertEqual(ritmo.nivel, gl.NIVEL_SEM_ANIMACAO)
        self.relogio.avancar(0.016)
        faixa.canvas.executar_agendados()
        self.assertEqual(faixa.cards[0].p, 1.0)
        self.assertEqual(faixa.canvas.agendados, {})
        self.assertEqual(self.desenhado(faixa), self.estado_final(faixa))

    def test_ao_descer_para_sem_animacao_o_encaixe_termina_no_proximo_quadro(self):
        ritmo = gl.Ritmo()
        faixa = self.nova_faixa_nativa(ritmo=ritmo)
        faixa.ir_para(1)
        self.relogio.avancar(0.016)
        faixa.canvas.executar_agendados()
        self.assertLess(faixa.deslocamento, faixa.carrossel.x_da_posicao(1))     # no meio do caminho
        ritmo.modo = gl.DESEMPENHO_ECONOMICO
        self.relogio.avancar(0.016)
        faixa.canvas.executar_agendados()
        self.assertEqual(faixa.deslocamento, faixa.carrossel.x_da_posicao(1))
        self.relogio.avancar(0.016)
        faixa.canvas.executar_agendados()
        self.assertEqual(faixa.canvas.agendados, {})
        self.assertTrue(faixa.cards[1].pronto)

    # ------------------------------------------------------------------ o que é informado ao ritmo
    def test_cada_quadro_que_pintou_e_informado_com_custo_e_intervalo(self):
        ritmo = RitmoGravador(gl.DESEMPENHO_COMPLETO)
        faixa = self.nova_faixa_nativa(("barras_v",), ritmo=ritmo)
        for _ in range(6):
            self.relogio.avancar(0.016)
            faixa.canvas.executar_agendados()
        self.assertEqual(len(ritmo.registros), 6)
        self.assertIsNone(ritmo.registros[0][1])                                 # o 1º quadro não tem anterior
        for custo, periodo in ritmo.registros[1:]:
            self.assertAlmostEqual(periodo, 0.016, places=6)
            self.assertEqual(custo, 0.0)                                         # relógio falso: pintar não "demora"

    def test_quadro_de_espera_nao_conta(self):
        ritmo = RitmoGravador(gl.DESEMPENHO_COMPLETO)
        faixa = self.nova_faixa_nativa(("barras_v",), ritmo=ritmo, atraso=0.5)
        for _ in range(10):                                                      # 160 ms: ainda no atraso inicial
            self.relogio.avancar(0.016)
            faixa.canvas.executar_agendados()
        self.assertEqual(ritmo.registros, [])

    def test_sequencia_nova_comeca_sem_quadro_anterior(self):
        ritmo = RitmoGravador(gl.DESEMPENHO_COMPLETO)
        faixa = self.nova_faixa_nativa(("barras_v", "linhas", "roscas"), ritmo=ritmo)
        self.rodar_quadros(faixa, 0.016)
        antes = len(ritmo.registros)
        self.relogio.avancar(30.0)                                               # fica parado por muito tempo
        faixa.ir_para(1)                                                         # o 2º gráfico passa a aparecer
        self.rodar_quadros(faixa, 0.016)
        novos = ritmo.registros[antes:]
        self.assertTrue(novos)
        self.assertTrue(all(periodo is None or periodo < 1.0 for _, periodo in novos))   # nada de "30 s entre quadros"

    # ------------------------------------------------------------------ o modo automático, de ponta a ponta
    def test_computador_rapido_continua_com_animacao_completa(self):
        ritmo = gl.Ritmo()
        faixa = self.nova_faixa_nativa(("barras_v", "linhas"), largura=1900, ritmo=ritmo)
        original = self.ui.CardNativo.desenhar

        def rapido(carta):
            self.relogio.avancar(0.001)
            original(carta)
        with mock.patch.object(self.ui.CardNativo, "desenhar", rapido):
            self.rodar_quadros(faixa, 0.016)
        self.assertEqual(ritmo.nivel, gl.NIVEL_COMPLETO)

    def test_computador_lento_reduz_sozinho_e_o_grafico_termina_igual(self):
        ritmo = gl.Ritmo()
        faixa = self.nova_faixa_nativa(("barras_v", "linhas"), largura=1900, ritmo=ritmo)
        original = self.ui.CardNativo.desenhar

        def lento(carta):
            self.relogio.avancar(0.012)                                          # cada pintura "demora" 12 ms
            original(carta)
        intervalos = []
        with mock.patch.object(self.ui.CardNativo, "desenhar", lento):
            quadros = 0
            while faixa.canvas.agendados:
                quadros += 1
                self.assertLess(quadros, 200)
                intervalos += self.intervalos(faixa)
                self.relogio.avancar(0.016)
                faixa.canvas.executar_agendados()
        self.assertGreater(ritmo.nivel, gl.NIVEL_COMPLETO)                       # percebeu e reduziu
        self.assertIn("cada quadro levou", ritmo.motivo)
        self.assertEqual(intervalos[0], 16)
        self.assertIn(33, intervalos)                                            # e passou a pedir quadros a cada 33 ms
        self.assertEqual(self.desenhado(faixa), self.estado_final(faixa))        # o gráfico final é o mesmo


class TestRitmoNoPainel(BaseDosTestes):
    def test_todas_as_faixas_dividem_o_mesmo_ritmo(self):
        ritmo = gl.Ritmo(gl.DESEMPENHO_COMPLETO)
        for disposicao in (gl.DISPOSICAO_LADO_A_LADO, gl.DISPOSICAO_VERTICAL):
            painel = self.ui.PainelGraficos(Base(), grupos_nativos(), disposicao, fontes=FontesFalsas(), ritmo=ritmo)
            faixas = painel.faixas + painel.faixas_empilhadas
            self.assertTrue(faixas)
            self.assertTrue(all(f.ritmo is ritmo for f in faixas), disposicao)
            self.assertIs(painel.ritmo, ritmo)

    def test_sem_ritmo_informado_e_um_so_completo_para_todas(self):
        painel = self.ui.PainelGraficos(Base(), grupos_nativos(), gl.DISPOSICAO_LADO_A_LADO, fontes=FontesFalsas())
        self.assertEqual(painel.ritmo.modo, gl.DESEMPENHO_COMPLETO)
        self.assertEqual(len({id(f.ritmo) for f in painel.faixas}), 1)

    def test_de_cima_para_baixo_sem_animacao_tudo_aparece_pronto(self):
        painel = self.ui.PainelGraficos(Base(), grupos_nativos(), gl.DISPOSICAO_VERTICAL, fontes=FontesFalsas(),
                                        ritmo=gl.Ritmo(gl.DESEMPENHO_ECONOMICO))
        painel.ajustar_todas(1100)
        for faixa in painel.faixas_empilhadas:
            self.assertEqual(faixa.canvas.agendados, {})
            self.assertTrue(faixa.cards[0].pronto)

    def test_uma_montagem_nova_com_ritmo_completo_volta_a_animar(self):
        ritmo = gl.Ritmo(gl.DESEMPENHO_ECONOMICO)
        sem = self.ui.PainelGraficos(Base(), grupos_nativos(), gl.DISPOSICAO_LADO_A_LADO, fontes=FontesFalsas(),
                                     ritmo=ritmo)
        sem.ajustar_todas(1100)
        self.assertTrue(all(not f.canvas.agendados for f in sem.faixas))
        ritmo.modo = gl.DESEMPENHO_COMPLETO
        com = self.ui.PainelGraficos(Base(), grupos_nativos(), gl.DISPOSICAO_LADO_A_LADO, fontes=FontesFalsas(),
                                     ritmo=ritmo)
        com.ajustar_todas(1100)
        self.assertTrue(all(f.canvas.agendados for f in com.faixas))


if __name__ == "__main__":
    unittest.main(verbosity=2)
