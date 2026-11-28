# -*- coding: utf-8 -*-
"""Verificação da interface com Tk de VERDADE: atalhos de edição e gráficos agrupados (animados e em imagem).

Os testes automáticos usam widgets falsos: são rápidos e não abrem janela, mas não provam como o Tk real se
comporta (eventos, rolagem do Canvas, imagens, botões do CustomTkinter). Este script abre uma janela de verdade,
usa só dados sintéticos, simula mouse e teclado com event_generate e confere o resultado.

    python tools/verificar_interface_tk.py

Roda no CI (Windows e Linux com Xvfb) pelo teste tests/test_interface_tk_real.py. Código de saída:
0 = tudo certo, 1 = alguma verificação falhou, 77 = sem Tk ou sem tela (nada foi verificado).
Cada linha da saída é [OK], [FALHA] ou [PULOU] seguida do nome da verificação.
"""
import os
import sys
import time
import traceback

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

SEM_TELA = 77


class Pulou(Exception):
    """A verificação não pôde ser feita neste ambiente (ex.: a janela de teste não recebeu o foco)."""


class Relatorio:
    def __init__(self):
        self.falhas = 0
        self.ok = 0
        self.puladas = 0

    def checar(self, nome, funcao, *args):
        inicio = time.monotonic()
        try:
            funcao(*args)
        except Pulou as p:
            self.puladas += 1
            print(f"[PULOU] {nome}: {p}", flush=True)
        except AssertionError as e:
            self.falhas += 1
            print(f"[FALHA] {nome}: {e or 'afirmação falhou'}", flush=True)
        except Exception:  # noqa: BLE001
            self.falhas += 1
            resumo = " | ".join(traceback.format_exc(limit=5).strip().splitlines()[-6:])
            print(f"[FALHA] {nome}: {resumo}", flush=True)
        else:
            self.ok += 1
            print(f"[OK] {nome} ({time.monotonic() - inicio:.1f} s)", flush=True)


def bombear(raiz, segundos=0.3):
    """Deixa o Tk processar eventos e agendamentos (after) por algum tempo."""
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        raiz.update()
        time.sleep(0.004)
    raiz.update()


def igual(a, b, tolerancia=0.0, rotulo=""):
    assert abs(a - b) <= tolerancia, f"{rotulo} esperado {b}, veio {a}"


def destruir_rolavel(quadro):
    """Destrói um CTkScrollableFrame por inteiro. O destroy() dele deixa o quadro externo (canvas e barra de rolagem)
    ocupando a janela; os quadros seguintes ficavam espremidos, estreitos (largura natural) e sem receber o foco."""
    externo = getattr(quadro, "_parent_frame", None)
    try:
        quadro.destroy()
    finally:
        if externo is not None:
            try:
                externo.destroy()
            except Exception:  # noqa: BLE001  (já destruído pelo próprio destroy)
                pass


# --------------------------------------------------------------------------------------------- dados sintéticos
def registros_sinteticos():
    """Um mês de registros inventados (nenhum dado de paciente real)."""
    regs = []
    for dia in range(1, 29):
        for i in range(1 + dia % 4):
            regs.append({
                "data": f"2026-10-{dia:02d}", "id_paciente": f"P{i}-{dia // 5}",
                "consistencia": ("Livre", "Branda", "Pastosa")[(i + dia) % 3],
                "via": "Enteral" if i % 3 == 2 else "Oral", "acompanhante": (i + dia) % 2,
                "suplementos": ([{"nome": f"Suplemento {i % 3}", "modulo": f"Módulo {i % 2}"}]
                                if (i + dia) % 3 == 0 else []),
                "dm": int(i % 2 == 0), "has": int(dia % 3 == 0), "laxativa": int(i == 1), "constipante": 0,
                "drc": int(dia % 7 == 0),
            })
    return regs


def grupos_sinteticos():
    """Os gráficos do mês em PNG (estilo "imagens simples")."""
    import mapa_graficos as mgr
    return mgr.gerar_por_grupo(mgr.agregar_mes(registros_sinteticos(), 2026, 10))


def especificacoes_sinteticas():
    """Os mesmos gráficos como especificações (estilo animado, desenhado na tela)."""
    import mapa_graficos as mgr
    return mgr.especificar_por_grupo(mgr.agregar_mes(registros_sinteticos(), 2026, 10))


# --------------------------------------------------------------------------------------------- gráficos agrupados
class Graficos:
    def __init__(self, raiz, ctk, erros):
        import graficos_layout as gl
        import graficos_ui
        self.raiz, self.ctk, self.erros, self.gl, self.ui = raiz, ctk, erros, gl, graficos_ui
        self.grupos = grupos_sinteticos()
        self.especs = especificacoes_sinteticas()
        self.quadro = self.painel = None

    def montar(self, disposicao, estilo="animado", espera=0.9, ritmo=None):
        """Monta a tela de gráficos. `espera`: quanto o Tk processa eventos antes de devolver (0 = já no 1º quadro).
        `ritmo`: o graficos_layout.Ritmo da animação (sem ele, animação completa)."""
        if self.quadro is not None:
            destruir_rolavel(self.quadro)
            bombear(self.raiz, 0.3)
        self.quadro = self.ctk.CTkScrollableFrame(self.raiz, fg_color="white")
        self.quadro.pack(fill="both", expand=True)
        grupos = self.especs if estilo == "animado" else self.grupos
        self.painel = self.ui.PainelGraficos(self.quadro, grupos, disposicao, ritmo=ritmo)
        bombear(self.raiz, espera)
        return self.painel

    def faixa_com_rolagem(self):
        for faixa, ctrl in zip(self.painel.faixas, self.painel.controles):
            if faixa.n_posicoes > 2:
                largura = faixa.carrossel.largura_visivel
                assert largura >= 0.45 * self.raiz.winfo_width(), (
                    f"a faixa tem só {largura:.0f} px numa janela de {self.raiz.winfo_width()} px: o quadro dos "
                    f"gráficos não esticou (sobrou quadro antigo na janela?)")
                return faixa, ctrl
        raise AssertionError("nenhum grupo com 3 posições para arrastar")

    def na_posicao(self, faixa, posicao, rotulo):
        """A faixa parou no encaixe e o Tk mostra exatamente essa parte do Canvas."""
        alvo = faixa.carrossel.x_da_posicao(posicao)
        assert faixa.ativo == posicao, f"{rotulo}: posição ativa {faixa.ativo}, esperada {posicao}"
        igual(faixa.deslocamento, alvo, 0.6, f"{rotulo}: deslocamento")
        igual(faixa.canvas.canvasx(0), alvo, 1.5, f"{rotulo}: borda esquerda que o Tk mostra")

    def mover_ate(self, faixa, alvo, acao, rotulo, espera=0.7):
        """Avança o carrossel com limite explícito; falha com diagnóstico em vez de travar o CI."""
        tentativas = max(4, faixa.n_posicoes + 2)
        for _ in range(tentativas):
            if faixa.ativo == alvo:
                break
            acao()
            bombear(self.raiz, espera)
        assert faixa.ativo == alvo, (
            f"{rotulo}: carrossel não chegou à posição {alvo}; ficou em {faixa.ativo} "
            f"após {tentativas} tentativas"
        )

    def evento_de_mouse(self, canvas, sequencia, x, y=40):
        """Evento de mouse com as coordenadas da tela (x_root) já preenchidas, como um clique de verdade."""
        canvas.event_generate(sequencia, x=int(x), y=y, rootx=canvas.winfo_rootx() + int(x),
                              rooty=canvas.winfo_rooty() + y)

    def arrastar(self, faixa, de, para, passos=8, espera=0.02, pausa_final=0.0):
        c = faixa.canvas
        self.evento_de_mouse(c, "<ButtonPress-1>", de)
        for i in range(1, passos + 1):
            self.evento_de_mouse(c, "<B1-Motion>", de + (para - de) * i / passos)
            self.raiz.update()
            if espera:
                time.sleep(espera)
        if pausa_final:
            time.sleep(pausa_final)
        self.evento_de_mouse(c, "<ButtonRelease-1>", para)

    # ------------------------------------------------------------------ verificações
    def primeiro_desenho_na_largura_final(self):
        """O Tk avisa uma largura provisória do canvas (a padrão, uns 380 px) antes da final. A faixa espera um instante
        e se desenha na largura final; sem isso os gráficos apareciam estreitos e depois pulavam. Conta os desenhos."""
        desenhos = []
        original = self.ui.FaixaHorizontal.ajustar
        t0 = time.perf_counter()

        def espiar(faixa, largura_px):
            desenhos.append((id(faixa), round((time.perf_counter() - t0) * 1000), int(largura_px)))
            return original(faixa, largura_px)

        self.ui.FaixaHorizontal.ajustar = espiar
        try:
            p = self.montar(self.gl.DISPOSICAO_LADO_A_LADO, "animado", espera=1.0)
        finally:
            self.ui.FaixaHorizontal.ajustar = original
        por_faixa = {}
        for chave, ms, largura in desenhos:
            por_faixa.setdefault(chave, []).append((ms, largura))
        resumo = ", ".join(f"{len(v)}x {[w for _, w in v]} px" for v in por_faixa.values())
        print(f"[INFO] primeiro desenho das {len(p.faixas)} faixas (largura de cada desenho): {resumo}; "
              f"último em {max(ms for _, ms, _ in desenhos)} ms", flush=True)
        assert len(por_faixa) == len(p.faixas), "alguma faixa não chegou a desenhar"
        for faixa in p.faixas:
            v = por_faixa[id(faixa)]
            assert len(v) <= 2, f"a faixa se desenhou {len(v)} vezes ao abrir: {v}"
            igual(v[-1][1], faixa.canvas.winfo_width(), 2, "o último desenho usou a largura da faixa")
            igual(faixa.carrossel.largura_visivel, faixa.canvas.winfo_width(), 2, "largura usada")

    def desenho_inicial(self):
        """Estilo animado (o padrão): os gráficos são desenhados direto no canvas, sem imagens."""
        p = self.montar(self.gl.DISPOSICAO_LADO_A_LADO, "animado")
        assert len(p.faixas) == 4, f"{len(p.faixas)} faixas, esperadas 4 (um por grupo)"
        assert p.imagens == [], "no estilo animado não há imagens"
        for faixa in p.faixas:
            assert faixa.carrossel is not None, "a faixa não recebeu o tamanho (evento Configure)"
            assert faixa.canvas.winfo_width() > 300, f"largura da faixa {faixa.canvas.winfo_width()}"
            assert all(type(c).__name__ == "CardNativo" for c in faixa.cards), "os gráficos deveriam ser nativos"
            desenhadas = len(faixa.canvas.find_all())
            esperadas = sum(len(c.pintor.itens) for c in faixa.cards)
            assert desenhadas == esperadas, f"{desenhadas} formas no canvas, a cena do grupo tem {esperadas}"
            assert all(c.spec.get("tipo") == "vazio" or len(c.pintor.itens) >= 8 for c in faixa.cards), \
                f"gráfico com quase nada desenhado: {[len(c.pintor.itens) for c in faixa.cards]} formas"
            assert faixa.fotos == [], "não deveria haver foto no estilo animado"
            alturas = {c.altura for c in faixa.cards}
            assert len(alturas) == 1, f"gráficos do grupo com alturas diferentes: {alturas}"
            assert faixa.canvas.winfo_height() >= max(alturas) - 1, "faixa mais baixa que os gráficos"
            assert faixa.dicas, "nenhum balão registrado"
        visiveis = [c.visivel for c in p.controles]
        assert visiveis[0] and visiveis[1], f"setas deveriam aparecer nos grupos com 3 e 2 gráficos: {visiveis}"
        assert not visiveis[3], "o grupo com um gráfico só não deveria ter setas"

    def desenho_inicial_imagem(self):
        """Estilo "imagens simples": os PNG do matplotlib, como antes."""
        p = self.montar(self.gl.DISPOSICAO_LADO_A_LADO, "imagem")
        assert len(p.faixas) == 4, f"{len(p.faixas)} faixas, esperadas 4 (um por grupo)"
        assert len(p.imagens) == 10, f"{len(p.imagens)} imagens, esperadas 10"
        for faixa in p.faixas:
            assert faixa.carrossel is not None, "a faixa não recebeu o tamanho (evento Configure)"
            assert faixa.canvas.winfo_width() > 300, f"largura da faixa {faixa.canvas.winfo_width()}"
            n = len(faixa.canvas.find_all())
            assert n == len(faixa.imagens), f"{n} itens desenhados para {len(faixa.imagens)} gráficos"
            assert faixa.canvas.winfo_height() > 100, f"altura da faixa {faixa.canvas.winfo_height()}"
            assert len(faixa.fotos) == len(faixa.imagens)
        visiveis = [c.visivel for c in p.controles]
        assert visiveis[0] and visiveis[1], f"setas deveriam aparecer nos grupos com 3 e 2 gráficos: {visiveis}"
        assert not visiveis[3], "o grupo com um gráfico só não deveria ter setas"

    # ------------------------------------------------------------------ gráficos animados
    def entrada_anima_ate_o_fim(self):
        p = self.montar(self.gl.DISPOSICAO_LADO_A_LADO, "animado", espera=0.0)
        primeira = p.faixas[0].cards[0]
        amostras = []
        fim = time.monotonic() + 4.0
        while time.monotonic() < fim and not primeira.pronto:
            bombear(self.raiz, 0.07)
            amostras.append(round(primeira.p, 3))
        assert primeira.pronto, f"a entrada do primeiro gráfico não terminou: {amostras}"
        assert amostras == sorted(amostras), f"o progresso voltou atrás: {amostras}"
        assert len([a for a in amostras if 0 < a < 1]) >= 2, f"nenhum quadro intermediário visto: {amostras}"
        bombear(self.raiz, 1.0)
        for faixa in p.faixas:
            for carta in faixa.cards:
                if carta.inicio is None:     # fora da faixa: espera aparecer, sem gastar nada
                    assert carta.p == 0.0, f"gráfico fora da tela animou: p={carta.p}"
                else:
                    assert carta.pronto, f"gráfico visível não terminou a entrada: p={carta.p}"
            assert faixa._job_entrada is None, "o relógio da animação continuou depois de todos terminarem"

    def entrada_do_grafico_que_aparece_depois(self):
        p = self.montar(self.gl.DISPOSICAO_LADO_A_LADO, "animado")
        faixa, _ = self.faixa_com_rolagem()
        ultima = faixa.cards[-1]
        assert ultima.inicio is None and ultima.p == 0.0, "o último gráfico não deveria ter começado a animar"
        faixa.ir_para(faixa.n_posicoes - 1)
        bombear(self.raiz, 1.8)
        assert ultima.inicio is not None, "o último gráfico não começou ao aparecer"
        assert ultima.pronto, f"o último gráfico não terminou a entrada: p={ultima.p}"
        faixa.ir_para(0)
        bombear(self.raiz, 0.8)
        assert p is self.painel and ultima.pronto, "voltar não deveria repetir a animação"

    def balao_com_o_valor(self):
        p = self.montar(self.gl.DISPOSICAO_LADO_A_LADO, "animado")
        bombear(self.raiz, 1.2)
        faixa = p.faixas[0]
        c = faixa.canvas
        visiveis = [(i, t) for i, t in faixa.dicas.items() if c.itemcget(i, "state") != "hidden"]
        assert visiveis, "depois da entrada deveria haver itens com balão visíveis"
        alvo = None
        for item, texto in visiveis:
            x0, y0, x1, y1 = c.bbox(item)
            wx, wy = (x0 + x1) / 2 - c.canvasx(0), (y0 + y1) / 2 - c.canvasy(0)
            if 20 < wx < c.winfo_width() - 20 and 5 < wy < c.winfo_height() - 5:
                alvo = (item, texto, wx, wy)
                break
        assert alvo, "nenhum item com balão dentro da parte visível"
        item, texto, wx, wy = alvo
        c.event_generate("<Motion>", x=int(wx), y=int(wy))
        bombear(self.raiz, 0.05)
        assert faixa._dica is not None, "o balão não foi criado ao passar o mouse"
        fundo, rotulo = faixa._dica
        assert c.itemcget(rotulo, "state") == "normal", "o balão não ficou visível"
        achado = c.itemcget(rotulo, "text")
        assert achado, "balão sem texto"
        # o texto é o do item sob o ponteiro (vários itens podem se sobrepor: confere que é um dos candidatos)
        candidatos = {faixa.dicas[i] for i in c.find_overlapping(wx - 6, wy - 6, wx + 6, wy + 6) if i in faixa.dicas}
        assert achado in candidatos, f"balão {achado!r} não é de nenhum item sob o ponteiro ({candidatos})"
        bx0, by0, bx1, by1 = c.bbox(fundo)
        assert bx0 >= c.canvasx(0) - 1 and bx1 <= c.canvasx(c.winfo_width()) + 1, "balão saiu pela lateral"
        c.event_generate("<Leave>")
        bombear(self.raiz, 0.05)
        assert c.itemcget(rotulo, "state") == "hidden", "o balão não sumiu ao sair do gráfico"

    def textos_cabem_nos_cartoes_com_a_fonte_real(self):
        p = self.montar(self.gl.DISPOSICAO_LADO_A_LADO, "animado")
        bombear(self.raiz, 1.5)
        for faixa in p.faixas:
            c = faixa.canvas
            for carta in faixa.cards:
                dentro = 0
                for item in c.find_all():
                    if c.type(item) != "text" or c.itemcget(item, "state") == "hidden":
                        continue
                    x0, y0, x1, y1 = c.bbox(item)
                    if not (carta.x <= (x0 + x1) / 2 <= carta.x + carta.largura):
                        continue
                    dentro += 1
                    assert x0 >= carta.x - 3 and x1 <= carta.x + carta.largura + 3, \
                        f"texto {c.itemcget(item, 'text')!r} passa da borda do cartão ({x0:.0f}..{x1:.0f})"
                    assert y1 <= carta.altura + 3, f"texto {c.itemcget(item, 'text')!r} abaixo do cartão"
                assert dentro >= 3, f"só {dentro} textos no cartão"

    def custo_dos_quadros(self):
        """Mede (e mostra no relatório) quanto custa desenhar um quadro da animação neste computador."""
        p = self.montar(self.gl.DISPOSICAO_LADO_A_LADO, "animado")
        bombear(self.raiz, 1.5)
        cena, tela = [], []
        for faixa in p.faixas:
            for carta in faixa.cards:
                for prog in (0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 1.0):
                    carta.p = prog
                    t0 = time.perf_counter()
                    carta.desenhar()
                    t1 = time.perf_counter()
                    faixa.canvas.update()
                    t2 = time.perf_counter()
                    cena.append((t1 - t0) * 1000)
                    tela.append((t2 - t0) * 1000)
        media = lambda v: sum(v) / len(v)  # noqa: E731
        print(f"[INFO] custo de um quadro da animação ({len(cena)} quadros): cena e formas "
              f"média {media(cena):.2f} ms, máx {max(cena):.2f} ms; com redesenho da tela "
              f"média {media(tela):.2f} ms, máx {max(tela):.2f} ms", flush=True)
        assert max(tela) < 400, f"um quadro levou {max(tela):.0f} ms (limite de segurança 400 ms)"

    # ------------------------------------------------------------------ ritmo: animação conforme o computador
    @staticmethod
    def cartas_animadas(painel):
        return [c for f in painel.faixas + painel.faixas_empilhadas for c in f.cards if c.animado]

    def esperar_primeiro_desenho(self, painel, limite=4.0):
        faixas = painel.faixas + painel.faixas_empilhadas
        fim = time.monotonic() + limite
        while time.monotonic() < fim and not all(f.carrossel is not None for f in faixas):
            bombear(self.raiz, 0.03)
        assert all(f.carrossel is not None for f in faixas), "alguma faixa não fez o primeiro desenho"

    def esperar_entradas(self, painel, limite=20.0):
        """Espera terminarem todas as entradas que começaram (as que ainda não apareceram não contam)."""
        fim = time.monotonic() + limite
        while time.monotonic() < fim:
            bombear(self.raiz, 0.05)
            if all(c.inicio is None or c.pronto for c in self.cartas_animadas(painel)):
                bombear(self.raiz, 0.1)
                return
        raise AssertionError(f"as entradas não terminaram em {limite:.0f} s: "
                             f"{[round(c.p, 2) for c in self.cartas_animadas(painel) if c.inicio is not None]}")

    @staticmethod
    def formas_no_canvas(faixa):
        """Quantas formas dos gráficos há no canvas da faixa (sem o balão, que só existe depois de passar o mouse)."""
        return len(faixa.canvas.find_all()) - (2 if faixa._dica is not None else 0)

    @staticmethod
    def foto_da_carta(carta):
        """O que a carta desenhou no canvas de verdade: (tipo, coordenadas, texto, estado) de cada forma."""
        c = carta.faixa.canvas
        fotos = []
        for _tipo, item in carta.pintor.itens:
            tipo = c.type(item)
            fotos.append((tipo, tuple(round(v, 2) for v in c.coords(item)),
                          c.itemcget(item, "text") if tipo == "text" else "", c.itemcget(item, "state") or "normal"))
        return fotos

    def fotos_das_cartas_prontas(self, painel):
        return {(i, j): self.foto_da_carta(c) for i, f in enumerate(painel.faixas)
                for j, c in enumerate(f.cards) if c.animado and c.pronto}

    def sem_animacao_aparece_pronto(self):
        gl = self.gl
        p = self.montar(gl.DISPOSICAO_LADO_A_LADO, "animado", espera=0.0, ritmo=gl.Ritmo(gl.DESEMPENHO_ECONOMICO))
        self.esperar_primeiro_desenho(p)
        bombear(self.raiz, 0.15)
        cartas = self.cartas_animadas(p)
        assert len(cartas) >= 8, f"poucos gráficos animados na tela: {len(cartas)}"
        meio = [round(c.p, 2) for c in cartas if not c.pronto]
        assert not meio, f"sem animação, mas há gráficos no meio da entrada: p={meio}"
        for faixa in p.faixas:
            assert faixa._job_entrada is None and faixa._job_animacao is None, "sobrou relógio de animação"
            desenhadas = self.formas_no_canvas(faixa)
            esperadas = sum(len(c.pintor.itens) for c in faixa.cards)
            assert desenhadas == esperadas, f"{desenhadas} formas no canvas, a cena do grupo tem {esperadas}"
        faixa, _ = self.faixa_com_rolagem()
        faixa.ir_para(faixa.n_posicoes - 1)
        bombear(self.raiz, 0.12)                                  # sem encaixe animado: já está no lugar
        self.na_posicao(faixa, faixa.n_posicoes - 1, "sem animação: encaixe imediato")
        assert faixa._job_animacao is None, "o encaixe deveria ser imediato"
        assert faixa.cards[-1].pronto, "o gráfico que apareceu deveria estar pronto"

    def contar_quadros(self, ritmo):
        """Monta a tela, espera as entradas e conta quantos quadros intermediários os gráficos desenharam."""
        contagem = {"quadros": 0}
        original = self.ui.CardNativo.desenhar

        def contando(carta):
            if 0 < carta.p < 1:
                contagem["quadros"] += 1
            original(carta)
        self.ui.CardNativo.desenhar = contando
        try:
            p = self.montar(self.gl.DISPOSICAO_LADO_A_LADO, "animado", espera=0.0, ritmo=ritmo)
            self.esperar_primeiro_desenho(p)
            self.esperar_entradas(p)
        finally:
            self.ui.CardNativo.desenhar = original
        return p, contagem["quadros"]

    def animacao_reduzida_usa_menos_quadros(self):
        gl = self.gl
        completo, n_completo = self.contar_quadros(gl.Ritmo(gl.DESEMPENHO_COMPLETO))
        fotos_completo = self.fotos_das_cartas_prontas(completo)
        reduzido, n_reduzido = self.contar_quadros(gl.Ritmo(gl.DESEMPENHO_AUTOMATICO, gl.NIVEL_REDUZIDO, "teste"))
        fotos_reduzido = self.fotos_das_cartas_prontas(reduzido)
        print(f"[INFO] quadros intermediários desenhados na entrada de todos os gráficos: "
              f"completo {n_completo}, reduzido {n_reduzido}", flush=True)
        assert n_completo > 20, f"a animação completa quase não desenhou quadros ({n_completo})"
        assert n_reduzido < 0.8 * n_completo, f"reduzido desenhou {n_reduzido} quadros, completo {n_completo}"
        assert fotos_completo and set(fotos_completo) <= set(fotos_reduzido), "o reduzido não terminou os mesmos gráficos"
        for chave, foto in fotos_completo.items():
            assert foto == fotos_reduzido[chave], f"o desenho final do gráfico {chave} muda com o ritmo"

    def computador_lento_reduz_sozinho(self):
        gl = self.gl
        ritmo = gl.Ritmo()                                        # automático, partindo da animação completa
        original = self.ui.CardNativo.desenhar

        def lento(carta):
            time.sleep(0.03)                                      # como se pintar um gráfico demorasse 30 ms a mais
            original(carta)
        self.ui.CardNativo.desenhar = lento
        try:
            p = self.montar(gl.DISPOSICAO_LADO_A_LADO, "animado", espera=0.0, ritmo=ritmo)
            self.esperar_primeiro_desenho(p)
            self.esperar_entradas(p, limite=30.0)
        finally:
            self.ui.CardNativo.desenhar = original
        print(f"[INFO] computador lento simulado: o automático ficou em '{gl.NOMES_NIVEL[ritmo.nivel]}'. "
              f"{ritmo.motivo}", flush=True)
        assert ritmo.nivel > gl.NIVEL_COMPLETO, "o ritmo não percebeu o computador lento"
        assert "cada quadro levou" in ritmo.motivo, f"motivo inesperado: {ritmo.motivo!r}"
        for faixa in p.faixas:
            assert faixa._job_entrada is None, "sobrou relógio de animação"
            assert all(c.inicio is None or c.pronto for c in faixa.cards), "entrada parada no meio"
            desenhadas = self.formas_no_canvas(faixa)
            esperadas = sum(len(c.pintor.itens) for c in faixa.cards)
            assert desenhadas == esperadas, f"{desenhadas} formas no canvas, a cena do grupo tem {esperadas}"

    def cronometros(self):
        """Quantos agendamentos (after) o Tk tem pendentes agora, de qualquer parte do programa."""
        return len(self.raiz.tk.splitlist(self.raiz.tk.call("after", "info")))

    def menor_numero_de_cronometros(self):
        vistos = []
        for _ in range(8):
            bombear(self.raiz, 0.05)
            vistos.append(self.cronometros())
        return min(vistos)

    def sem_cronometro_depois_da_entrada(self):
        """Terminada a entrada, os gráficos não deixam relógio nenhum ligado: parado, o programa não gasta nada."""
        gl = self.gl
        self.montar(gl.DISPOSICAO_LADO_A_LADO, "animado", espera=1.2, ritmo=gl.Ritmo(gl.DESEMPENHO_ECONOMICO))
        sem_animacao = self.menor_numero_de_cronometros()          # sem animação nunca há relógio dos gráficos
        p = self.montar(gl.DISPOSICAO_LADO_A_LADO, "animado", espera=0.0, ritmo=gl.Ritmo(gl.DESEMPENHO_COMPLETO))
        self.esperar_primeiro_desenho(p)
        self.esperar_entradas(p)
        bombear(self.raiz, 0.5)
        com_animacao = self.menor_numero_de_cronometros()
        print(f"[INFO] agendamentos pendentes no Tk depois da entrada: {com_animacao} "
              f"(sem animação: {sem_animacao})", flush=True)
        assert com_animacao <= sem_animacao, \
            f"sobraram {com_animacao - sem_animacao} agendamento(s) depois que a animação terminou"

    def consulta_ao_sistema(self):
        """O que o Windows diz sobre acesso remoto e animações (e se as constantes da API valem de verdade)."""
        gl = self.gl
        nivel, motivo = gl.sistema_pede_economia()
        print(f"[INFO] o sistema pede: {gl.NOMES_NIVEL[nivel]}" + (f" ({motivo})" if motivo else ""), flush=True)
        if not sys.platform.startswith("win"):
            assert (nivel, motivo) == (gl.NIVEL_COMPLETO, ""), "fora do Windows não há o que declarar"
            return
        import ctypes
        usuario = ctypes.windll.user32
        remoto = usuario.GetSystemMetrics(gl.SM_REMOTESESSION)
        ligado = ctypes.c_int(-1)
        ok = usuario.SystemParametersInfoW(gl.SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(ligado), 0)
        print(f"[INFO] Windows: sessão remota={remoto}; animações ligadas={ligado.value}; consulta ok={ok}", flush=True)
        if not ok:
            raise Pulou("o Windows não respondeu à consulta de animações (constante errada ou sem permissão)")
        assert ligado.value in (0, 1), f"valor inesperado para 'animações ligadas': {ligado.value}"
        esperado = gl.NIVEL_REDUZIDO if (remoto or not ligado.value) else gl.NIVEL_COMPLETO
        assert nivel == esperado, f"sistema_pede_economia deu {nivel}, esperado {esperado}"

    def entrada_durante_o_redimensionamento(self):
        p = self.montar(self.gl.DISPOSICAO_LADO_A_LADO, "animado", espera=0.2)
        largura_janela, altura_janela = self.raiz.winfo_width(), self.raiz.winfo_height()
        self.raiz.geometry(f"{int(largura_janela * 0.72)}x{altura_janela}")
        bombear(self.raiz, 2.0)
        for faixa in p.faixas:
            assert faixa.canvas.winfo_width() < 0.72 * largura_janela, "a faixa não encolheu"
            assert faixa.carrossel.largura_card <= faixa.canvas.winfo_width(), "gráfico mais largo que a faixa"
            for carta in faixa.cards:
                assert carta.inicio is None or carta.pronto, f"entrada parada no meio depois de redimensionar: p={carta.p}"
        self.raiz.geometry(f"{largura_janela}x{altura_janela}")
        bombear(self.raiz, 0.9)

    def de_cima_para_baixo_animado(self):
        p = self.montar(self.gl.DISPOSICAO_VERTICAL, "animado")
        assert p.faixas == [], "no modo de cima para baixo não há faixas com setas"
        assert len(p.faixas_empilhadas) == 10, f"{len(p.faixas_empilhadas)} gráficos empilhados, esperados 10"
        for faixa in p.faixas_empilhadas:
            assert faixa.carrossel is not None, "a faixa não recebeu o tamanho"
            (carta,) = faixa.cards
            largura = faixa.canvas.winfo_width()
            assert carta.largura <= largura, "gráfico mais largo que a tela"
            igual(carta.x, (largura - carta.largura) / 2, 1.5, "gráfico no meio da tela")
            assert faixa.canvas.winfo_height() >= carta.altura - 1, "faixa mais baixa que o gráfico"
        bombear(self.raiz, 1.8)
        assert all(f.cards[0].pronto for f in p.faixas_empilhadas), "a entrada não terminou em todos os gráficos"

    def voltar_ao_inicio(self, faixa):
        faixa.ir_para(0)
        bombear(self.raiz, 0.6)
        self.na_posicao(faixa, 0, "voltar ao começo")

    def arraste_lento_volta_ao_encaixe(self):
        faixa, _ = self.faixa_com_rolagem()
        self.voltar_ao_inicio(faixa)
        inicio = int(faixa.canvas.winfo_width() * 0.8)
        # 30% de um gráfico para a esquerda, depois soltou parado: não chega à metade, então volta
        self.arrastar(faixa, inicio, inicio - int(0.3 * faixa.carrossel.passo), pausa_final=0.2)
        bombear(self.raiz, 0.7)
        self.na_posicao(faixa, 0, "arraste curto")

    def arraste_lento_avanca(self):
        faixa, _ = self.faixa_com_rolagem()
        c = faixa.canvas
        inicio = int(c.winfo_width() * 0.9)
        fim = int(inicio - 0.7 * faixa.carrossel.passo)          # 70% de um gráfico: passa da metade
        self.evento_de_mouse(c, "<ButtonPress-1>", inicio)
        for i in range(1, 9):
            self.evento_de_mouse(c, "<B1-Motion>", inicio + (fim - inicio) * i / 8)
            self.raiz.update()
            time.sleep(0.02)
        igual(faixa.deslocamento, float(inicio - fim), 0.6, "durante o arraste")
        igual(c.canvasx(0), float(inicio - fim), 1.5, "o Tk acompanha o mouse")
        time.sleep(0.2)
        self.evento_de_mouse(c, "<ButtonRelease-1>", fim)
        bombear(self.raiz, 0.7)
        self.na_posicao(faixa, 1, "arraste longo")

    def arremesso_rapido(self):
        faixa, _ = self.faixa_com_rolagem()
        meio = int(faixa.canvas.winfo_width() * 0.5)
        self.arrastar(faixa, meio, meio - 60, passos=3, espera=0.0)     # 60 px em poucos milissegundos, soltou na hora
        bombear(self.raiz, 0.7)
        self.na_posicao(faixa, 2, "arremesso")

    def botoes_e_pontos(self):
        faixa, ctrl = self.faixa_com_rolagem()
        self.mover_ate(faixa, 0, ctrl.b_ant.invoke, "botão anterior")
        self.na_posicao(faixa, 0, "botão anterior")
        assert ctrl.b_ant.cget("state") == "disabled", "seta da esquerda deveria estar desligada no começo"
        ctrl.b_prox.invoke()
        bombear(self.raiz, 0.7)
        self.na_posicao(faixa, 1, "botão próximo")
        texto = ctrl.pontos.cget("text")
        assert texto == self.gl.pontos(faixa.n_posicoes, 1), f"pontos: {texto!r}"
        self.mover_ate(faixa, faixa.n_posicoes - 1, ctrl.b_prox.invoke, "botão próximo, fim")
        self.na_posicao(faixa, faixa.n_posicoes - 1, "botão próximo, fim")
        assert ctrl.b_prox.cget("state") == "disabled", "seta da direita deveria estar desligada no fim"

    def setas_do_teclado(self):
        faixa, _ = self.faixa_com_rolagem()
        c = faixa.canvas
        c.focus_force()
        bombear(self.raiz, 0.2)
        if self.raiz.focus_get() is not c:
            raise Pulou("a janela de teste não recebeu o foco do teclado")
        self.mover_ate(faixa, faixa.n_posicoes - 1, faixa.proximo, "setas do teclado", espera=0.3)
        c.event_generate("<Left>")
        bombear(self.raiz, 0.6)
        self.na_posicao(faixa, faixa.n_posicoes - 2, "seta esquerda")
        c.event_generate("<Right>")
        bombear(self.raiz, 0.6)
        self.na_posicao(faixa, faixa.n_posicoes - 1, "seta direita")

    def shift_com_a_roda(self):
        faixa, _ = self.faixa_com_rolagem()
        c = faixa.canvas
        self.mover_ate(faixa, faixa.n_posicoes - 1, faixa.proximo, "Shift + roda", espera=0.3)
        time.sleep(0.3)
        c.event_generate("<Shift-MouseWheel>", delta=120)         # para cima: volta uma posição
        bombear(self.raiz, 0.6)
        self.na_posicao(faixa, faixa.n_posicoes - 2, "Shift + roda")

    def janela_menor_redesenha(self):
        faixa, _ = self.faixa_com_rolagem()
        antes = faixa.carrossel.largura_visivel
        largura_janela, altura_janela = self.raiz.winfo_width(), self.raiz.winfo_height()
        self.raiz.geometry(f"{int(largura_janela * 0.72)}x{altura_janela}")
        bombear(self.raiz, 0.9)
        agora = faixa.canvas.winfo_width()
        assert agora < antes - 100, f"a faixa não encolheu junto com a janela ({antes} -> {agora})"
        igual(faixa.carrossel.largura_visivel, agora, 2, "largura usada no desenho")
        assert faixa.carrossel.largura_card <= agora, "o gráfico ficou mais largo que a faixa"
        self.na_posicao(faixa, faixa.ativo, "depois de redimensionar")
        self.raiz.geometry(f"{largura_janela}x{altura_janela}")
        bombear(self.raiz, 0.9)

    def de_cima_para_baixo_imagem(self):
        p = self.montar(self.gl.DISPOSICAO_VERTICAL, "imagem")
        assert p.faixas == [], "no modo de cima para baixo não há faixas"
        assert len(p.imagens) == 10, f"{len(p.imagens)} imagens"
        assert all(type(i).__name__ == "CTkImage" for i in p.imagens), "as imagens deveriam ser CTkImage"

    def escala_do_windows(self):
        rastreador = getattr(self.ctk, "ScalingTracker", None)
        info = "ScalingTracker exposto" if rastreador is not None else "ScalingTracker NÃO exposto"
        esc = self.ui.escala_da_tela(self.raiz)
        assert 0.9 <= esc <= 4.0, f"escala fora do esperado: {esc} ({info})"
        self.ctk.set_widget_scaling(1.5)
        try:
            bombear(self.raiz, 0.4)
            p = self.montar(self.gl.DISPOSICAO_LADO_A_LADO)
            assert abs(p.escala - 1.5) < 0.01, f"escala lida {p.escala}, esperada 1.5 ({info})"
            faixa, _ = self.faixa_com_rolagem()
            assert faixa.carrossel.largura_card <= 840 * 1.5 + 0.5, "card passou do limite escalado"
            assert faixa.carrossel.largura_card <= faixa.canvas.winfo_width(), "card maior que a faixa"
        finally:
            self.ctk.set_widget_scaling(1.0)
            bombear(self.raiz, 0.4)

    def destruir_sem_erros(self):
        p = self.montar(self.gl.DISPOSICAO_LADO_A_LADO, "animado", espera=0.0)
        fim = time.monotonic() + 3.0
        while time.monotonic() < fim and not all(f.carrossel is not None for f in p.faixas):
            bombear(self.raiz, 0.03)                              # espera o primeiro desenho de cada faixa
        bombear(self.raiz, 0.15)                                  # e deixa a entrada andar um pouco
        faixa, _ = self.faixa_com_rolagem()
        assert any(c.inicio is not None and not c.pronto for f in p.faixas for c in f.cards), \
            "a entrada já tinha terminado: o teste não pegaria a destruição no meio da animação"
        faixa.proximo()                                           # animação em andamento ao destruir
        destruir_rolavel(self.quadro)
        self.quadro = None
        bombear(self.raiz, 0.6)


# --------------------------------------------------------------------------------------------- atalhos de edição
def digitar(widget, texto, raiz, ler):
    """Digita tecla por tecla. Se o Tk deste sistema não transforma a tecla simulada em letra, insere o caractere
    direto; o que interessa aqui é o KeyRelease depois de cada tecla, que é o que alimenta o histórico do desfazer."""
    nomes = {" ": "space", "\n": "Return"}
    for ch in texto:
        antes = ler()
        widget.event_generate("<KeyPress>", keysym=nomes.get(ch, ch))
        if ler() == antes:
            widget.insert("insert", ch)
        widget.event_generate("<KeyRelease>", keysym=nomes.get(ch, ch))
    raiz.update()


def com_foco(raiz, widget):
    widget.focus_force()
    bombear(raiz, 0.2)
    if raiz.focus_get() is not widget:
        raise Pulou("a janela de teste não recebeu o foco do teclado")


class Atalhos:
    def __init__(self, raiz, ctk, tk, ttk):
        import atalhos_edicao
        self.raiz, self.ctk, self.tk, self.ttk = raiz, ctk, tk, ttk
        atalhos_edicao.instalar(raiz)

    def campo_de_uma_linha(self):
        entrada = self.ctk.CTkEntry(self.raiz)
        entrada.pack(padx=10, pady=4)
        e = entrada._entry
        com_foco(self.raiz, e)
        digitar(e, "ola mundo", self.raiz, e.get)
        assert e.get() == "ola mundo", f"digitação simulada: {e.get()!r}"
        e.event_generate("<Control-z>")
        bombear(self.raiz, 0.05)
        depois = e.get()
        assert depois != "ola mundo" and "ola mundo".startswith(depois), f"Ctrl+Z deixou {depois!r}"
        for _ in range(5):
            e.event_generate("<Control-z>")
        assert e.get() == "", f"várias vezes Ctrl+Z deveriam esvaziar o campo, ficou {e.get()!r}"
        e.event_generate("<Control-y>")
        assert e.get() != "", "Ctrl+Y não refez nada"
        for _ in range(5):
            e.event_generate("<F4>")
        assert e.get() == "ola mundo", f"Ctrl+Y e F4 deveriam refazer tudo, ficou {e.get()!r}"
        e.event_generate("<Control-a>")
        assert e.selection_present(), "Ctrl+A não selecionou o texto"
        entrada.destroy()

    def colar_da_planilha(self):
        entrada = self.ctk.CTkEntry(self.raiz)
        entrada.pack(padx=10, pady=4)
        e = entrada._entry
        com_foco(self.raiz, e)
        try:
            self.raiz.clipboard_clear()
            self.raiz.clipboard_append("120\n")
        except self.tk.TclError as erro:
            raise Pulou(f"sem área de transferência: {erro}")
        e.event_generate("<Control-v>")
        bombear(self.raiz, 0.05)
        assert e.get() == "120", f"colar célula do Planilhas deveria dar '120', deu {e.get()!r}"
        entrada.destroy()

    def tabela(self):
        tree = self.ttk.Treeview(self.raiz, columns=("a", "b"), show="headings", selectmode="extended", height=3)
        for i in range(3):
            tree.insert("", "end", values=(f"item{i}", i))
        tree.pack(padx=10, pady=4)
        com_foco(self.raiz, tree)
        tree.event_generate("<Control-a>")
        assert len(tree.selection()) == 3, f"Ctrl+A selecionou {len(tree.selection())} de 3 linhas"
        tree.event_generate("<Control-c>")
        try:
            copiado = self.raiz.clipboard_get()
        except self.tk.TclError as erro:
            raise Pulou(f"sem área de transferência: {erro}")
        assert copiado.splitlines() == ["item0\t0", "item1\t1", "item2\t2"], f"copiado: {copiado!r}"
        tree.destroy()

    def caixa_de_texto(self):
        caixa = self.ctk.CTkTextbox(self.raiz, height=60)
        caixa.pack(padx=10, pady=4)
        t = caixa._textbox
        com_foco(self.raiz, t)
        digitar(t, "abc", self.raiz, lambda: t.get("1.0", "end-1c"))
        assert t.get("1.0", "end-1c") == "abc", f"digitação simulada: {t.get('1.0', 'end-1c')!r}"
        t.event_generate("<Control-z>")
        assert t.get("1.0", "end-1c") != "abc", "Ctrl+Z não desfez nada na caixa de texto"
        t.event_generate("<Control-y>")
        assert t.get("1.0", "end-1c") == "abc", f"Ctrl+Y não refez: {t.get('1.0', 'end-1c')!r}"
        caixa.destroy()


# --------------------------------------------------------------------------------------------- principal
def main():
    try:
        import tkinter as tk
        from tkinter import ttk
        import customtkinter as ctk
    except Exception as e:  # noqa: BLE001
        print(f"[PULOU] tudo: sem tkinter/customtkinter ({e})")
        return SEM_TELA
    try:
        raiz = ctk.CTk()
    except tk.TclError as e:
        print(f"[PULOU] tudo: sem tela para abrir a janela ({e})")
        return SEM_TELA

    erros = []
    raiz.report_callback_exception = lambda *info: erros.append("".join(traceback.format_exception(*info)))
    raiz.geometry(f"{min(1240, raiz.winfo_screenwidth())}x{min(800, raiz.winfo_screenheight())}+0+0")
    try:                                                          # invisível no Windows; o Xvfb ignora
        raiz.attributes("-alpha", 0.0)
    except Exception:  # noqa: BLE001
        pass
    bombear(raiz, 0.5)

    rel = Relatorio()
    atalhos = Atalhos(raiz, ctk, tk, ttk)
    for nome, f in (("atalhos: campo de uma linha (Ctrl+Z, Ctrl+Y, F4, Ctrl+A)", atalhos.campo_de_uma_linha),
                    ("atalhos: colar célula do Planilhas", atalhos.colar_da_planilha),
                    ("atalhos: tabela (Ctrl+A e Ctrl+C)", atalhos.tabela),
                    ("atalhos: caixa de texto de várias linhas", atalhos.caixa_de_texto)):
        rel.checar(nome, f)

    g = Graficos(raiz, ctk, erros)
    for nome, f in (("gráficos animados: primeiro desenho na largura final", g.primeiro_desenho_na_largura_final),
                    ("gráficos animados: desenho inicial por grupo", g.desenho_inicial),
                    ("gráficos animados: a entrada anima até o fim", g.entrada_anima_ate_o_fim),
                    ("gráficos animados: entrada do gráfico que aparece depois", g.entrada_do_grafico_que_aparece_depois),
                    ("gráficos animados: balão com o valor", g.balao_com_o_valor),
                    ("gráficos animados: textos cabem nos cartões (fonte real)", g.textos_cabem_nos_cartoes_com_a_fonte_real),
                    ("gráficos animados: custo de um quadro", g.custo_dos_quadros),
                    ("gráficos: sem animação, tudo aparece pronto", g.sem_animacao_aparece_pronto),
                    ("gráficos: animação reduzida usa menos quadros e chega ao mesmo desenho",
                     g.animacao_reduzida_usa_menos_quadros),
                    ("gráficos: computador lento reduz a animação sozinho", g.computador_lento_reduz_sozinho),
                    ("gráficos: nenhum agendamento sobra depois da entrada", g.sem_cronometro_depois_da_entrada),
                    ("sistema: consulta ao Windows (acesso remoto e animações)", g.consulta_ao_sistema),
                    ("gráficos: arraste curto volta ao encaixe", g.arraste_lento_volta_ao_encaixe),
                    ("gráficos: arraste longo avança uma posição", g.arraste_lento_avanca),
                    ("gráficos: arremesso rápido vai para a próxima", g.arremesso_rapido),
                    ("gráficos: botões e pontos", g.botoes_e_pontos),
                    ("gráficos: setas do teclado", g.setas_do_teclado),
                    ("gráficos: Shift + roda do mouse", g.shift_com_a_roda),
                    ("gráficos: janela menor redesenha", g.janela_menor_redesenha),
                    ("gráficos animados: redimensionar durante a entrada", g.entrada_durante_o_redimensionamento),
                    ("gráficos animados: de cima para baixo", g.de_cima_para_baixo_animado),
                    ("gráficos: escala de tela de 150%", g.escala_do_windows),
                    ("gráficos: destruir durante a animação", g.destruir_sem_erros),
                    ("gráficos em imagem: desenho inicial por grupo", g.desenho_inicial_imagem),
                    ("gráficos em imagem: de cima para baixo", g.de_cima_para_baixo_imagem)):
        rel.checar(nome, f)

    bombear(raiz, 0.3)
    if erros:
        rel.falhas += 1
        print(f"[FALHA] erros escondidos dentro de callbacks do Tk ({len(erros)}):", flush=True)
        for e in erros[:3]:
            print("    " + e.strip().replace("\n", "\n    "), flush=True)
    else:
        rel.ok += 1
        print("[OK] nenhum erro escondido em callbacks do Tk", flush=True)
    try:
        raiz.destroy()
    except Exception:  # noqa: BLE001
        pass
    print(f"Resumo: {rel.ok} ok, {rel.falhas} falha(s), {rel.puladas} pulada(s)", flush=True)
    return 1 if rel.falhas else 0


if __name__ == "__main__":
    sys.exit(main())
