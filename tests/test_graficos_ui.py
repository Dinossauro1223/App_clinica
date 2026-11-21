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

from PIL import Image  # noqa: E402

import graficos_layout as gl  # noqa: E402


class TclErro(Exception):
    pass


class Evento:
    def __init__(self, **kw):
        self.width = kw.get("width", 0)
        self.x_root = kw.get("x_root", 0)
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

    def create_image(self, x, y, **kw):
        self.itens.append({"x": x, "y": y, **kw})
        return len(self.itens)

    def delete(self, *a):
        self.itens = []

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
