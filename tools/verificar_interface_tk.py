# -*- coding: utf-8 -*-
"""Verificação da interface com Tk de VERDADE: atalhos de edição e gráficos agrupados.

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
            print(f"[OK] {nome}", flush=True)


def bombear(raiz, segundos=0.3):
    """Deixa o Tk processar eventos e agendamentos (after) por algum tempo."""
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        raiz.update()
        time.sleep(0.004)
    raiz.update()


def igual(a, b, tolerancia=0.0, rotulo=""):
    assert abs(a - b) <= tolerancia, f"{rotulo} esperado {b}, veio {a}"


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
    import mapa_graficos as mgr
    return mgr.gerar_por_grupo(mgr.agregar_mes(registros_sinteticos(), 2026, 10))


# --------------------------------------------------------------------------------------------- gráficos agrupados
class Graficos:
    def __init__(self, raiz, ctk, erros):
        import graficos_layout as gl
        import graficos_ui
        self.raiz, self.ctk, self.erros, self.gl, self.ui = raiz, ctk, erros, gl, graficos_ui
        self.grupos = grupos_sinteticos()
        self.quadro = self.painel = None

    def montar(self, disposicao):
        if self.quadro is not None:
            self.quadro.destroy()
            bombear(self.raiz, 0.3)
        self.quadro = self.ctk.CTkScrollableFrame(self.raiz, fg_color="white")
        self.quadro.pack(fill="both", expand=True)
        self.painel = self.ui.PainelGraficos(self.quadro, self.grupos, disposicao)
        bombear(self.raiz, 0.9)
        return self.painel

    def faixa_com_rolagem(self):
        for faixa, ctrl in zip(self.painel.faixas, self.painel.controles):
            if faixa.n_posicoes > 2:
                return faixa, ctrl
        raise AssertionError("nenhum grupo com 3 posições para arrastar")

    def na_posicao(self, faixa, posicao, rotulo):
        """A faixa parou no encaixe e o Tk mostra exatamente essa parte do Canvas."""
        alvo = faixa.carrossel.x_da_posicao(posicao)
        assert faixa.ativo == posicao, f"{rotulo}: posição ativa {faixa.ativo}, esperada {posicao}"
        igual(faixa.deslocamento, alvo, 0.6, f"{rotulo}: deslocamento")
        igual(faixa.canvas.canvasx(0), alvo, 1.5, f"{rotulo}: borda esquerda que o Tk mostra")

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
    def desenho_inicial(self):
        p = self.montar(self.gl.DISPOSICAO_LADO_A_LADO)
        assert len(p.faixas) == 4, f"{len(p.faixas)} faixas, esperadas 4 (um por grupo)"
        assert len(p.imagens) == 8, f"{len(p.imagens)} imagens, esperadas 8"
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

    def arraste_lento_volta_ao_encaixe(self):
        faixa, _ = self.faixa_com_rolagem()
        self.arrastar(faixa, 700, 440, pausa_final=0.2)          # 260 px para a esquerda, depois soltou parado
        bombear(self.raiz, 0.7)
        self.na_posicao(faixa, 0, "arraste curto")

    def arraste_lento_avanca(self):
        faixa, _ = self.faixa_com_rolagem()
        c = faixa.canvas
        self.evento_de_mouse(c, "<ButtonPress-1>", 900)
        for i in range(1, 9):
            self.evento_de_mouse(c, "<B1-Motion>", 900 - i * 75)
            self.raiz.update()
            time.sleep(0.02)
        igual(faixa.deslocamento, 600.0, 0.6, "durante o arraste")
        igual(c.canvasx(0), 600.0, 1.5, "o Tk acompanha o mouse")
        time.sleep(0.2)
        self.evento_de_mouse(c, "<ButtonRelease-1>", 300)
        bombear(self.raiz, 0.7)
        self.na_posicao(faixa, 1, "arraste longo")

    def arremesso_rapido(self):
        faixa, _ = self.faixa_com_rolagem()
        self.arrastar(faixa, 500, 440, passos=3, espera=0.0)     # 60 px em poucos milissegundos, soltou na hora
        bombear(self.raiz, 0.7)
        self.na_posicao(faixa, 2, "arremesso")

    def botoes_e_pontos(self):
        faixa, ctrl = self.faixa_com_rolagem()
        while faixa.ativo > 0:
            ctrl.b_ant.invoke()
            bombear(self.raiz, 0.7)
        self.na_posicao(faixa, 0, "botão anterior")
        assert ctrl.b_ant.cget("state") == "disabled", "seta da esquerda deveria estar desligada no começo"
        ctrl.b_prox.invoke()
        bombear(self.raiz, 0.7)
        self.na_posicao(faixa, 1, "botão próximo")
        texto = ctrl.pontos.cget("text")
        assert texto == self.gl.pontos(faixa.n_posicoes, 1), f"pontos: {texto!r}"
        ctrl.b_prox.invoke()
        bombear(self.raiz, 0.7)
        self.na_posicao(faixa, faixa.n_posicoes - 1, "botão próximo, fim")
        assert ctrl.b_prox.cget("state") == "disabled", "seta da direita deveria estar desligada no fim"

    def setas_do_teclado(self):
        faixa, _ = self.faixa_com_rolagem()
        c = faixa.canvas
        c.focus_force()
        bombear(self.raiz, 0.2)
        if self.raiz.focus_get() is not c:
            raise Pulou("a janela de teste não recebeu o foco do teclado")
        c.event_generate("<Left>")
        bombear(self.raiz, 0.6)
        self.na_posicao(faixa, faixa.n_posicoes - 2, "seta esquerda")
        c.event_generate("<Right>")
        bombear(self.raiz, 0.6)
        self.na_posicao(faixa, faixa.n_posicoes - 1, "seta direita")

    def shift_com_a_roda(self):
        faixa, _ = self.faixa_com_rolagem()
        c = faixa.canvas
        time.sleep(0.3)
        c.event_generate("<Shift-MouseWheel>", delta=120)         # para cima: volta uma posição
        bombear(self.raiz, 0.6)
        self.na_posicao(faixa, faixa.n_posicoes - 2, "Shift + roda")

    def janela_menor_redesenha(self):
        faixa, _ = self.faixa_com_rolagem()
        antes = faixa.carrossel.largura_visivel
        self.raiz.geometry("900x700")
        bombear(self.raiz, 0.9)
        agora = faixa.canvas.winfo_width()
        assert agora < antes - 100, f"a faixa não encolheu junto com a janela ({antes} -> {agora})"
        igual(faixa.carrossel.largura_visivel, agora, 2, "largura usada no desenho")
        assert faixa.carrossel.largura_card <= agora, "o gráfico ficou mais largo que a faixa"
        self.na_posicao(faixa, faixa.ativo, "depois de redimensionar")
        self.raiz.geometry("1240x800")
        bombear(self.raiz, 0.9)

    def de_cima_para_baixo(self):
        p = self.montar(self.gl.DISPOSICAO_VERTICAL)
        assert p.faixas == [], "no modo de cima para baixo não há faixas"
        assert len(p.imagens) == 8, f"{len(p.imagens)} imagens"
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
        self.montar(self.gl.DISPOSICAO_LADO_A_LADO)
        faixa, _ = self.faixa_com_rolagem()
        faixa.proximo()                                           # animação em andamento ao destruir
        self.quadro.destroy()
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



def verificar_paineis_configuracoes_suplementos(raiz, ctk):
    """Abre as duas telas pelo mesmo fluxo de guias do desktop, com Tk real e banco sintético."""
    import tempfile
    from pathlib import Path
    from unittest import mock
    import db_service
    import mapa_db
    import mapa_ui
    import configuracoes_ui
    from navegacao_ui import PilhaAbasLaterais

    class AppHarness:
        def __init__(self):
            self.host = ctk.CTkFrame(raiz, fg_color="transparent")
            self.host.pack(fill="both", expand=True)
            self.pilha = PilhaAbasLaterais(self.host)
            self.pilha.pack(fill="both", expand=True)
            self.area_principal = self.pilha.pagina_atual
            self.mapa = None

        def __getattr__(self, nome):
            return getattr(raiz, nome)

        def limpar_area_principal(self):
            for widget in self.area_principal.winfo_children():
                widget.destroy()

        def tela_inicial(self):
            return None

        def abrir_painel_lateral(self, titulo, comando):
            frame = self.pilha.abrir(titulo)
            self.area_principal = frame
            comando()
            return frame

    def textos(widget):
        saida = []
        try:
            valor = widget.cget("text")
            if valor:
                saida.append(str(valor))
        except Exception:
            pass
        for filho in widget.winfo_children():
            saida.extend(textos(filho))
        return saida

    with tempfile.TemporaryDirectory(prefix="nutrilab-ui-") as tmp:
        banco = str(Path(tmp) / "clinica_teste.db")
        mapa_db.inicializar(banco)
        app = AppHarness()
        app.mapa = type("MapaBanco", (), {"db": banco})()
        with mock.patch.object(db_service, "caminho_banco", return_value=banco):
            app.abrir_painel_lateral("Configurações", lambda: configuracoes_ui.ConfiguracoesUI(app).mostrar())
            bombear(raiz, 0.2)
            rotulos = textos(app.area_principal)
            assert "Configurações" in rotulos, "a tela de Configurações não foi renderizada"
            assert "Aparência do aplicativo" in rotulos, "opções de aparência não foram renderizadas"
            assert "Reavaliação nutricional (NRS-2002)" in rotulos, "opções NRS não foram renderizadas"

        app.mapa = mapa_ui.MapaUI(app, banco, RAIZ)
        app.abrir_painel_lateral("Suplementos", app.mapa.mostrar_suplementos)
        bombear(raiz, 0.3)
        assert app.mapa.tree_sup.winfo_exists(), "a tabela de suplementos não foi criada"
        linhas = app.mapa.tree_sup.get_children()
        assert len(linhas) >= 6, f"catálogo inicial deveria mostrar pelo menos seis suplementos, mostrou {len(linhas)}"
        assert app.pilha.quantidade == 2, "as duas telas deveriam permanecer em guias independentes"
        app.pilha.limpar()
        app.host.destroy()

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
    raiz.geometry("1240x800+0+0")
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
    for nome, f in (("gráficos: desenho inicial por grupo", g.desenho_inicial),
                    ("gráficos: arraste curto volta ao encaixe", g.arraste_lento_volta_ao_encaixe),
                    ("gráficos: arraste longo avança uma posição", g.arraste_lento_avanca),
                    ("gráficos: arremesso rápido vai para a próxima", g.arremesso_rapido),
                    ("gráficos: botões e pontos", g.botoes_e_pontos),
                    ("gráficos: setas do teclado", g.setas_do_teclado),
                    ("gráficos: Shift + roda do mouse", g.shift_com_a_roda),
                    ("gráficos: janela menor redesenha", g.janela_menor_redesenha),
                    ("gráficos: de cima para baixo", g.de_cima_para_baixo),
                    ("gráficos: escala de tela de 150%", g.escala_do_windows),
                    ("gráficos: destruir durante a animação", g.destruir_sem_erros)):
        rel.checar(nome, f)

    rel.checar(
        "navegação: Configurações e Suplementos em guias com Tk real",
        verificar_paineis_configuracoes_suplementos, raiz, ctk
    )

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
