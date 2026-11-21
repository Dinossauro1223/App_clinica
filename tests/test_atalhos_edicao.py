# -*- coding: utf-8 -*-
"""Atalhos de edição no estilo do Google Planilhas (atalhos_edicao.py).

A lógica pura (histórico de desfazer, limites de palavra, texto colado, texto copiado das tabelas) é testada
direto. A ligação com o Tk é testada com widgets simulados: o teste "digita" caractere a caractere, dispara os
mesmos eventos que o Tk dispararia (<KeyRelease>, Ctrl+Z, <<Paste>>...) e confere o conteúdo do campo. Não abre
janelas e roda igual no Windows e no Linux. A aparência e o comportamento real do Tk NÃO são validados aqui.

    python -m unittest tests.test_atalhos_edicao -v
"""
import contextlib
import io
import os
import re
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import atalhos_edicao as ae  # noqa: E402

RAIZ_DO_PROJETO = Path(__file__).resolve().parent.parent
SHIFT, ALT = ae._MASCARA_SHIFT, ae._MASCARA_ALT


# ================================================================================== lógica pura
class TestTextoPuro(unittest.TestCase):
    def test_prefixo_sufixo(self):
        self.assertEqual(ae.prefixo_sufixo("casa", "casaco"), (4, 0))
        self.assertEqual(ae.prefixo_sufixo("casaco", "casa"), (4, 0))
        self.assertEqual(ae.prefixo_sufixo("abc", "abc"), (3, 0))
        self.assertEqual(ae.prefixo_sufixo("abxc", "abyc"), (2, 1))
        self.assertEqual(ae.prefixo_sufixo("", "xyz"), (0, 0))

    def test_cursor_depois_de_desfazer_fica_no_fim_do_trecho_que_mudou(self):
        self.assertEqual(ae.posicao_apos_troca("olá mundo", "olá "), 4)      # desfez "mundo"
        self.assertEqual(ae.posicao_apos_troca("olá ", "olá mundo"), 9)      # refez "mundo"
        self.assertEqual(ae.posicao_apos_troca("ab cd", "ab XX cd"), 6)      # trecho do meio ("XX ")
        self.assertEqual(ae.posicao_apos_troca("", "abc"), 3)

    def test_palavra_anterior(self):
        f = ae.inicio_palavra_anterior
        self.assertEqual(f("hello world", 11), 6)
        self.assertEqual(f("hello world", 6), 0)          # depois do espaço: leva a palavra e o espaço
        self.assertEqual(f("hello   ", 8), 0)
        self.assertEqual(f("a, b", 4), 3)
        self.assertEqual(f("a, b", 3), 1)                 # espaço pulado, depois a vírgula como bloco
        self.assertEqual(f("abc", 0), 0)
        self.assertEqual(f("ação_1 x", 6), 0)             # acento, sublinhado e número contam como palavra
        self.assertEqual(f("abc", 99), 0)                 # posição fora do texto não quebra

    def test_palavra_seguinte(self):
        f = ae.fim_palavra_seguinte
        self.assertEqual(f("hello world", 0), 6)          # leva a palavra e o espaço que vem depois
        self.assertEqual(f("hello world", 6), 11)
        self.assertEqual(f("hello   world", 5), 8)        # parado no espaço: só os espaços
        self.assertEqual(f("a, b", 1), 3)                 # a vírgula e o espaço que vem depois
        self.assertEqual(f("abc", 3), 3)
        self.assertEqual(f("abc", -5), 3)

    def test_colar_em_campo_de_uma_linha(self):
        f = ae.texto_para_campo_simples
        self.assertEqual(f("72,5\n"), "72,5")                       # uma célula do Planilhas
        self.assertEqual(f("72,5\r\n"), "72,5")
        self.assertEqual(f("a\tb\tc"), "a b c")                      # várias células
        self.assertEqual(f("a\tb\nc\td\n"), "a b c d")
        self.assertEqual(f("linha 1\r\n\r\nlinha 2"), "linha 1 linha 2")
        self.assertEqual(f("  com espaços  "), "  com espaços  ")    # espaços do usuário são preservados
        self.assertEqual(f("a\x00b\x07c"), "abc")                    # controle invisível sai
        self.assertEqual(f(""), "")
        self.assertEqual(f(None), "")

    def test_linhas_para_tsv(self):
        self.assertEqual(ae.linhas_para_tsv([("1", "Maria", "02/03/1950"), (2, "José", None)]),
                         "1\tMaria\t02/03/1950\n2\tJosé\t")
        self.assertEqual(ae.linhas_para_tsv([("a\tb", "c\nd")]), "a b\tc d")   # tab/quebra dentro da célula
        self.assertEqual(ae.linhas_para_tsv([]), "")

    def test_ajuda_lista_todos_os_atalhos(self):
        texto = ae.texto_ajuda()
        for _, itens in ae.ATALHOS:
            for acao, tecla in itens:
                self.assertIn(tecla, texto)
                self.assertIn(acao, texto)
        self.assertNotIn(chr(0x2014), texto)    # o projeto não usa travessão nos textos da tela
        self.assertNotIn(chr(0x2013), texto)

    def test_documento_dos_atalhos_cita_cada_atalho(self):
        doc = (RAIZ_DO_PROJETO / "docs" / "desenvolvimento" / "ATALHOS_DE_TECLADO.md").read_text(encoding="utf-8")
        for _, itens in ae.ATALHOS:
            for _, tecla in itens:
                self.assertIn(tecla, doc, tecla)


class TestHistoricoEdicao(unittest.TestCase):
    def digitar(self, h, texto, t0=0.0, passo=0.05):
        """Simula digitar `texto` no fim do campo, um caractere por vez, sem pausas grandes."""
        t = t0
        for c in texto:
            t += passo
            h.registrar(h.atual + c, agora=t)
        return t

    def test_digitar_vira_uma_etapa_por_palavra(self):
        h = ae.HistoricoEdicao("")
        self.digitar(h, "olá mundo")
        self.assertEqual(h.atual, "olá mundo")
        self.assertEqual(h.desfazer(), "olá ")
        self.assertEqual(h.desfazer(), "")
        self.assertIsNone(h.desfazer())
        self.assertEqual(h.refazer(), "olá ")
        self.assertEqual(h.refazer(), "olá mundo")
        self.assertIsNone(h.refazer())

    def test_pausa_longa_abre_nova_etapa(self):
        h = ae.HistoricoEdicao("")
        t = self.digitar(h, "abc", 0.0)
        self.digitar(h, "def", t + ae.PAUSA_AGRUPAR + 0.5)
        self.assertEqual(h.atual, "abcdef")
        self.assertEqual(h.desfazer(), "abc")
        self.assertEqual(h.desfazer(), "")

    def test_apagar_em_sequencia_tambem_agrupa_e_troca_de_direcao_separa(self):
        h = ae.HistoricoEdicao("")
        t = self.digitar(h, "abcd", 0.0)
        for i in range(3):                                   # apaga "d", "c", "b"
            t += 0.05
            h.registrar(h.atual[:-1], agora=t)
        self.assertEqual(h.atual, "a")
        self.assertEqual(h.desfazer(), "abcd")               # as três exclusões foram uma etapa
        self.assertEqual(h.desfazer(), "")

    def test_colar_e_substituir_sao_etapas_proprias(self):
        h = ae.HistoricoEdicao("")
        t = self.digitar(h, "ab", 0.0)
        h.registrar("abXYZ", agora=t + 0.05)                  # colou 3 caracteres de uma vez
        h.registrar("abXYZ!", agora=t + 0.10)                 # digitou logo depois
        self.assertEqual(h.desfazer(), "abXYZ")
        self.assertEqual(h.desfazer(), "ab")

    def test_nova_edicao_apaga_o_refazer(self):
        h = ae.HistoricoEdicao("")
        self.digitar(h, "um")
        h.desfazer()
        self.assertTrue(h.pode_refazer())
        h.registrar("dois", agora=99.0)
        self.assertFalse(h.pode_refazer())
        self.assertIsNone(h.refazer())

    def test_mesmo_texto_nao_cria_etapa(self):
        h = ae.HistoricoEdicao("x")
        self.assertFalse(h.registrar("x"))
        self.assertFalse(h.pode_desfazer())

    def test_mover_o_cursor_quebra_o_agrupamento(self):
        h = ae.HistoricoEdicao("")
        t = self.digitar(h, "ab", 0.0)
        h.quebrar_grupo()
        self.digitar(h, "cd", t)
        self.assertEqual(h.desfazer(), "ab")
        self.assertEqual(h.desfazer(), "")

    def test_limite_de_etapas(self):
        h = ae.HistoricoEdicao("", limite=5)
        for i in range(20):
            h.registrar(f"texto {i}", agora=float(i) * 10)    # cada um é uma etapa (substituição)
        desfeitas = 0
        while h.desfazer() is not None:
            desfeitas += 1
        self.assertEqual(desfeitas, 5)

    def test_sincronizar_nao_cria_etapa(self):
        h = ae.HistoricoEdicao("a")
        h.sincronizar("b")
        self.assertEqual(h.atual, "b")
        self.assertFalse(h.pode_desfazer())


# ================================================================================== widgets simulados
class Evento:
    def __init__(self, widget, keysym="", state=0):
        self.widget, self.keysym, self.state = widget, keysym, state


class RaizFalsa:
    def __init__(self):
        self.ligacoes, self.todas = {}, {}

    def bind_class(self, classe, sequencia, funcao, add=None):
        lista = self.ligacoes.setdefault((classe, sequencia), [])
        if add != "+":
            lista.clear()   # sem "+" o Tk substitui o que já estava ligado
        lista.append(funcao)

    def bind_all(self, sequencia, funcao, add=None):
        self.todas.setdefault(sequencia, []).append(funcao)

    def disparar(self, classe, sequencia, widget, keysym="", state=0):
        """Roda o que está ligado a (classe, sequência), como o Tk faria. Devolve o último retorno."""
        resultado = None
        for funcao in self.ligacoes.get((classe, sequencia), []):
            resultado = funcao(Evento(widget, keysym, state))
            if resultado == "break":
                break
        return resultado


class AreaDeTransferencia:
    def __init__(self, texto=None):
        self.texto = texto


class EntradaFalsa:
    """Imita o tk.Entry no que os atalhos usam (conteúdo, cursor, seleção, estado, área de transferência)."""
    _contador = 0

    def __init__(self, texto="", estado="normal", area=None):
        EntradaFalsa._contador += 1
        self.caminho = f".quadro.entrada{EntradaFalsa._contador}"
        self.texto, self.cursor, self.sel, self.estado = texto, len(texto), None, estado
        self.area = area or AreaDeTransferencia()

    def __str__(self):
        return self.caminho

    def _i(self, v):
        if v == "end":
            return len(self.texto)
        if v == "insert":
            return self.cursor
        if v == "sel.first":
            return self.sel[0]
        if v == "sel.last":
            return self.sel[1]
        return max(0, min(int(v), len(self.texto)))

    def get(self):
        return self.texto

    def cget(self, chave):
        return self.estado if chave == "state" else ""

    def index(self, v):
        return self._i(v)

    def icursor(self, v):
        self.cursor = self._i(v)

    def delete(self, a, b=None):
        ia = self._i(a)
        ib = ia + 1 if b is None else self._i(b)
        if ib <= ia:
            return
        self.texto = self.texto[:ia] + self.texto[ib:]
        self.cursor = self.cursor - (ib - ia) if self.cursor >= ib else min(self.cursor, ia)
        self.sel = None

    def insert(self, v, s):
        pos = self._i(v)
        self.texto = self.texto[:pos] + s + self.texto[pos:]
        if self.cursor >= pos:
            self.cursor += len(s)

    def selection_present(self):
        return self.sel is not None and self.sel[0] != self.sel[1]

    def selection_range(self, a, b):
        self.sel = (self._i(a), self._i(b))

    def selection_clear(self):
        self.sel = None

    def clipboard_get(self):
        if self.area.texto is None:
            raise ae.TclError("CLIPBOARD selection doesn't exist or form \"STRING\" not defined")
        return self.area.texto


class TextoFalso:
    """Imita o tk.Text (linhas 1.., colunas 0..) com o que os atalhos usam."""

    def __init__(self, texto="", estado="normal", undo=False):
        self.linhas = texto.split("\n")
        self.cursor = (1, 0)
        self.sel = None
        self.estado = estado
        self.opcoes = {"undo": undo}
        self.chamadas, self.gerados = [], []

    def _pos(self, idx):
        if idx == "insert":
            return self.cursor
        if idx == "end-1c":
            return len(self.linhas), len(self.linhas[-1])
        if idx == "sel.first":
            return self.sel[0]
        if idx == "sel.last":
            return self.sel[1]
        linha, coluna = idx.split(".")
        linha = int(linha)
        return linha, (len(self.linhas[linha - 1]) if coluna == "end" else int(coluna))

    def _abs(self, pos):
        linha, coluna = pos
        return sum(len(x) + 1 for x in self.linhas[:linha - 1]) + coluna

    def _de_abs(self, n):
        for i, x in enumerate(self.linhas):
            if n <= len(x):
                return i + 1, n
            n -= len(x) + 1
        return len(self.linhas), len(self.linhas[-1])

    def todo(self):
        return "\n".join(self.linhas)

    def index(self, idx):
        linha, coluna = self._pos(idx)
        return f"{linha}.{coluna}"

    def get(self, a, b):
        return self.todo()[self._abs(self._pos(a)):self._abs(self._pos(b))]

    def delete(self, a, b):
        ia, ib = self._abs(self._pos(a)), self._abs(self._pos(b))
        t = self.todo()
        self.linhas = (t[:ia] + t[ib:]).split("\n")
        self.cursor = self._de_abs(ia)
        self.sel = None

    def tag_ranges(self, nome):
        return ("x", "y") if (nome == "sel" and self.sel) else ()

    def tag_add(self, nome, a, b):
        if nome == "sel":
            self.sel = (self._pos(a), self._pos(b))

    def mark_set(self, nome, idx):
        if nome == "insert":
            self.cursor = self._pos(idx)

    def cget(self, chave):
        return self.estado if chave == "state" else self.opcoes.get(chave, "")

    def configure(self, **kw):
        self.opcoes.update(kw)

    def edit_undo(self):
        self.chamadas.append("undo")

    def edit_redo(self):
        self.chamadas.append("redo")

    def event_generate(self, nome):
        self.gerados.append(nome)


class TabelaFalsa:
    def __init__(self, linhas, modo="extended", mostra="headings"):
        self.itens = {f"I{i}": tuple(linha) for i, linha in enumerate(linhas)}
        self.modo, self.mostra, self.escolhidos, self.copiado = modo, mostra, (), None

    def get_children(self, pai=""):
        return tuple(self.itens) if pai == "" else ()

    def selection(self):
        return self.escolhidos

    def selection_set(self, itens):
        self.escolhidos = tuple(itens)

    def cget(self, chave):
        return {"selectmode": self.modo, "show": self.mostra}.get(chave, "")

    def item(self, item, opcao):
        return self.itens[item] if opcao == "values" else f"texto de {item}"

    def clipboard_clear(self):
        self.copiado = ""

    def clipboard_append(self, texto):
        self.copiado += texto


def instalado():
    ae._HIST.clear()
    raiz = RaizFalsa()
    assert ae.instalar(raiz) is True
    return raiz


def digitar(raiz, campo, texto, classe="Entry"):
    """Digita caractere a caractere: o Tk insere e, ao soltar a tecla, dispara <KeyRelease>."""
    for c in texto:
        if campo.selection_present():
            campo.delete("sel.first", "sel.last")
        campo.insert("insert", c)
        raiz.disparar(classe, "<KeyRelease>", campo, keysym=c)


def teclas(raiz, campo, sequencia, keysym="", state=0, classe="Entry"):
    return raiz.disparar(classe, sequencia, campo, keysym, state)


# ================================================================================== instalação
SEQUENCIA_VALIDA = re.compile(r"^<(?:(?:Control|Shift|Alt)-)*[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9_]+)?>$|^<<[A-Za-z]+>>$")


class TestInstalacao(unittest.TestCase):
    def test_liga_entradas_texto_e_tabela(self):
        raiz = instalado()
        classes = {c for c, _ in raiz.ligacoes}
        self.assertEqual(classes, {"Entry", "TEntry", "TCombobox", "Text", "Treeview"})
        for classe in ("Entry", "TEntry", "TCombobox"):
            for seq in ("<Control-Key-z>", "<Control-Key-Z>", "<Control-Key-y>", "<Control-Key-Y>", "<F4>",
                        "<Control-Key-a>", "<Control-Key-BackSpace>", "<Control-Key-Delete>", "<<Paste>>",
                        "<Control-Shift-Key-V>", "<KeyRelease>", "<FocusIn>", "<Destroy>"):
                self.assertIn((classe, seq), raiz.ligacoes, f"{classe} {seq}")
        for seq in ("<Control-Key-z>", "<Control-Key-y>", "<F4>", "<Control-Key-a>", "<FocusIn>"):
            self.assertIn(("Text", seq), raiz.ligacoes)
        for seq in ("<Control-Key-a>", "<Control-Key-c>", "<Control-Key-C>", "<Control-Key-Insert>"):
            self.assertIn(("Treeview", seq), raiz.ligacoes)
        self.assertNotIn(("Text", "<<Paste>>"), raiz.ligacoes, "caixa de várias linhas mantém a colagem nativa")
        self.assertIn("<F1>", raiz.todas)

    def test_todas_as_sequencias_sao_validas_para_o_tk(self):
        raiz = instalado()
        invalidas = [s for _, s in raiz.ligacoes if not SEQUENCIA_VALIDA.match(s)] + \
                    [s for s in raiz.todas if not SEQUENCIA_VALIDA.match(s)]
        self.assertEqual(invalidas, [])

    def test_so_instala_uma_vez(self):
        raiz = instalado()
        antes = {k: len(v) for k, v in raiz.ligacoes.items()}
        self.assertFalse(ae.instalar(raiz))
        self.assertEqual({k: len(v) for k, v in raiz.ligacoes.items()}, antes)

    def test_sequencia_recusada_pelo_tk_nao_derruba_a_instalacao(self):
        class RaizQueRecusa(RaizFalsa):
            def bind_class(self, classe, sequencia, funcao, add=None):
                if sequencia == "<F4>":
                    raise ae.TclError("bad event type or keysym")
                super().bind_class(classe, sequencia, funcao, add)
        ae._HIST.clear()
        raiz = RaizQueRecusa()
        self.assertTrue(ae.instalar(raiz))
        self.assertNotIn(("Entry", "<F4>"), raiz.ligacoes)
        self.assertIn(("Entry", "<Control-Key-z>"), raiz.ligacoes)

    def test_erro_dentro_de_um_atalho_nao_chega_ao_tk(self):
        def estoura(ev):
            raise RuntimeError("falha de teste")
        envolvida = ae._seguro(estoura)
        erro = io.StringIO()
        with contextlib.redirect_stderr(erro):
            self.assertIsNone(envolvida(Evento(None)))
        self.assertIn("falha de teste", erro.getvalue())

    def test_f1_mostra_a_lista_de_atalhos(self):
        raiz = instalado()
        caixa = types.ModuleType("tkinter.messagebox")
        chamadas = []
        caixa.showinfo = lambda titulo, texto, **kw: chamadas.append((titulo, texto, kw))
        pacote = types.ModuleType("tkinter")
        pacote.messagebox = caixa
        campo = EntradaFalsa("x")
        campo.winfo_toplevel = lambda: "janela"
        with mock.patch.dict(sys.modules, {"tkinter": pacote, "tkinter.messagebox": caixa}):
            self.assertEqual(raiz.todas["<F1>"][0](Evento(campo)), "break")
        self.assertEqual(chamadas, [("Atalhos de teclado", ae.texto_ajuda(), {"parent": "janela"})])


# ================================================================================== campos de uma linha
class TestCamposDeUmaLinha(unittest.TestCase):
    def setUp(self):
        self.raiz = instalado()

    def test_desfazer_e_refazer_com_ctrl_z_ctrl_y_e_f4(self):
        campo = EntradaFalsa("")
        self.raiz.disparar("Entry", "<FocusIn>", campo)
        digitar(self.raiz, campo, "olá mundo")
        self.assertEqual(teclas(self.raiz, campo, "<Control-Key-z>"), "break")
        self.assertEqual((campo.texto, campo.cursor), ("olá ", 4))
        teclas(self.raiz, campo, "<Control-Key-z>")
        self.assertEqual(campo.texto, "")
        teclas(self.raiz, campo, "<Control-Key-z>")                      # nada mais a desfazer: sem erro
        self.assertEqual(campo.texto, "")
        teclas(self.raiz, campo, "<Control-Key-y>")
        self.assertEqual(campo.texto, "olá ")
        teclas(self.raiz, campo, "<F4>")
        self.assertEqual((campo.texto, campo.cursor), ("olá mundo", 9))
        teclas(self.raiz, campo, "<Control-Key-Z>", state=SHIFT)         # Ctrl+Shift+Z também refaz? (nada a refazer)
        self.assertEqual(campo.texto, "olá mundo")

    def test_ctrl_shift_z_refaz_e_caps_lock_sem_shift_desfaz(self):
        campo = EntradaFalsa("")
        self.raiz.disparar("Entry", "<FocusIn>", campo)
        digitar(self.raiz, campo, "ab")
        teclas(self.raiz, campo, "<Control-Key-Z>", state=0)             # Caps Lock: letra maiúscula, sem Shift = desfazer
        self.assertEqual(campo.texto, "")
        teclas(self.raiz, campo, "<Control-Key-Z>", state=SHIFT)         # com Shift = refazer
        self.assertEqual(campo.texto, "ab")
        teclas(self.raiz, campo, "<Control-Key-Y>")                      # Caps Lock no Ctrl+Y: nada a refazer, sem erro
        self.assertEqual(campo.texto, "ab")

    def test_alt_f4_e_ctrl_alt_ficam_com_o_sistema(self):
        campo = EntradaFalsa("")
        self.raiz.disparar("Entry", "<FocusIn>", campo)
        digitar(self.raiz, campo, "ab")
        teclas(self.raiz, campo, "<Control-Key-z>")
        self.assertEqual(campo.texto, "")
        self.assertIsNone(teclas(self.raiz, campo, "<Alt-Key-F4>"))
        self.assertIsNone(teclas(self.raiz, campo, "<F4>", state=ALT))   # F4 com Alt não refaz
        self.assertEqual(campo.texto, "")
        self.assertIsNone(teclas(self.raiz, campo, "<Control-Key-y>", state=ALT))
        self.assertEqual(campo.texto, "")

    def test_digitar_depois_de_desfazer_descarta_o_refazer(self):
        campo = EntradaFalsa("")
        self.raiz.disparar("Entry", "<FocusIn>", campo)
        digitar(self.raiz, campo, "abc")
        teclas(self.raiz, campo, "<Control-Key-z>")
        digitar(self.raiz, campo, "x")
        teclas(self.raiz, campo, "<Control-Key-y>")
        self.assertEqual(campo.texto, "x")

    def test_texto_posto_pelo_programa_nao_pode_ser_desfeito_para_o_valor_antigo(self):
        campo = EntradaFalsa("")
        self.raiz.disparar("Entry", "<FocusIn>", campo)
        digitar(self.raiz, campo, "antigo")
        campo.delete(0, "end")                                            # o programa preenche o formulário...
        campo.insert(0, "Maria Souza")
        self.raiz.disparar("Entry", "<FocusIn>", campo)                   # ...e o usuário volta ao campo
        teclas(self.raiz, campo, "<Control-Key-z>")
        self.assertEqual(campo.texto, "Maria Souza")

    def test_foco_sem_mudanca_mantem_o_historico(self):
        campo = EntradaFalsa("")
        self.raiz.disparar("Entry", "<FocusIn>", campo)
        digitar(self.raiz, campo, "ab")
        self.raiz.disparar("Entry", "<FocusIn>", campo)                   # saiu e voltou, texto igual
        teclas(self.raiz, campo, "<Control-Key-z>")
        self.assertEqual(campo.texto, "")

    def test_campo_somente_leitura_ou_desativado_nao_muda(self):
        for estado in ("readonly", "disabled"):
            campo = EntradaFalsa("fixo", estado=estado)
            self.raiz.disparar("Entry", "<FocusIn>", campo)
            teclas(self.raiz, campo, "<Control-Key-z>")
            teclas(self.raiz, campo, "<Control-Key-y>")
            self.raiz.disparar("Entry", "<<Paste>>", campo)
            teclas(self.raiz, campo, "<Control-Key-BackSpace>")
            self.assertEqual(campo.texto, "fixo", estado)

    def test_ctrl_a_seleciona_tudo(self):
        campo = EntradaFalsa("Maria Souza")
        campo.cursor = 3
        self.assertEqual(teclas(self.raiz, campo, "<Control-Key-a>"), "break")
        self.assertEqual((campo.sel, campo.cursor), ((0, 11), 11))
        campo.sel = None
        teclas(self.raiz, campo, "<Control-Key-A>")                        # Caps Lock
        self.assertEqual(campo.sel, (0, 11))
        campo.sel = None
        self.assertIsNone(teclas(self.raiz, campo, "<Control-Key-a>", state=ALT))   # AltGr+A: não é atalho
        self.assertIsNone(campo.sel)

    def test_ctrl_backspace_e_ctrl_delete_apagam_por_palavra(self):
        campo = EntradaFalsa("o paciente Maria Souza")
        self.raiz.disparar("Entry", "<FocusIn>", campo)
        teclas(self.raiz, campo, "<Control-Key-BackSpace>")
        self.assertEqual(campo.texto, "o paciente Maria ")
        teclas(self.raiz, campo, "<Control-Key-BackSpace>")
        self.assertEqual(campo.texto, "o paciente ")
        campo.cursor = 2
        teclas(self.raiz, campo, "<Control-Key-Delete>")
        self.assertEqual(campo.texto, "o ")                                 # apaga "paciente " e o que sobra fica
        teclas(self.raiz, campo, "<Control-Key-z>")
        self.assertEqual(campo.texto, "o paciente ")                       # cada exclusão por palavra é uma etapa

    def test_ctrl_backspace_com_selecao_apaga_so_a_selecao(self):
        campo = EntradaFalsa("abc def ghi")
        self.raiz.disparar("Entry", "<FocusIn>", campo)
        campo.selection_range(4, 7)
        teclas(self.raiz, campo, "<Control-Key-BackSpace>")
        self.assertEqual(campo.texto, "abc  ghi")

    def test_colar_celula_do_planilhas_entra_sem_quebra_de_linha(self):
        campo = EntradaFalsa("Peso: ")
        campo.area.texto = "72,5\r\n"
        self.raiz.disparar("Entry", "<FocusIn>", campo)
        self.assertEqual(self.raiz.disparar("Entry", "<<Paste>>", campo), "break")
        self.assertEqual((campo.texto, campo.cursor), ("Peso: 72,5", 10))

    def test_colar_varias_celulas_vira_texto_unico(self):
        campo = EntradaFalsa("")
        campo.area.texto = "Maria\tSouza\n72,5\t1,60\n"
        self.raiz.disparar("Entry", "<FocusIn>", campo)
        self.raiz.disparar("Entry", "<<Paste>>", campo)
        self.assertEqual(campo.texto, "Maria Souza 72,5 1,60")

    def test_colar_substitui_a_selecao_e_pode_ser_desfeito(self):
        campo = EntradaFalsa("Nome: XXXX fim")
        campo.area.texto = "Ana"
        self.raiz.disparar("Entry", "<FocusIn>", campo)
        campo.selection_range(6, 10)
        campo.cursor = 10
        self.raiz.disparar("Entry", "<<Paste>>", campo)
        self.assertEqual(campo.texto, "Nome: Ana fim")
        teclas(self.raiz, campo, "<Control-Key-z>")
        self.assertEqual(campo.texto, "Nome: XXXX fim")
        teclas(self.raiz, campo, "<Control-Key-y>")
        self.assertEqual(campo.texto, "Nome: Ana fim")

    def test_ctrl_shift_v_cola_so_o_texto(self):
        campo = EntradaFalsa("")
        campo.area.texto = "a\tb\n"
        self.raiz.disparar("Entry", "<FocusIn>", campo)
        self.assertEqual(teclas(self.raiz, campo, "<Control-Shift-Key-V>"), "break")
        self.assertEqual(campo.texto, "a b")

    def test_colar_com_area_de_transferencia_vazia_ou_so_quebra_de_linha_nao_muda_nada(self):
        campo = EntradaFalsa("igual")
        self.raiz.disparar("Entry", "<FocusIn>", campo)
        self.raiz.disparar("Entry", "<<Paste>>", campo)             # sem nada copiado: o Tk avisa com erro
        campo.area.texto = "\n"
        self.raiz.disparar("Entry", "<<Paste>>", campo)
        self.assertEqual(campo.texto, "igual")

    def test_recortar_vira_etapa_do_desfazer(self):
        campo = EntradaFalsa("")
        self.raiz.disparar("Entry", "<FocusIn>", campo)
        digitar(self.raiz, campo, "abc def")
        campo.selection_range(0, 3)
        campo.delete("sel.first", "sel.last")                              # o Tk apaga a seleção no <<Cut>>
        self.raiz.disparar("Entry", "<<Cut>>", campo)
        self.assertEqual(campo.texto, " def")
        teclas(self.raiz, campo, "<Control-Key-z>")
        self.assertEqual(campo.texto, "abc def")

    def test_destruir_o_campo_apaga_o_historico(self):
        campo = EntradaFalsa("")
        self.raiz.disparar("Entry", "<FocusIn>", campo)
        digitar(self.raiz, campo, "abc")
        self.assertIn(str(campo), ae._HIST)
        self.raiz.disparar("Entry", "<Destroy>", campo)
        self.assertNotIn(str(campo), ae._HIST)

    def test_seta_e_clique_separam_as_etapas_da_digitacao(self):
        campo = EntradaFalsa("")
        self.raiz.disparar("Entry", "<FocusIn>", campo)
        digitar(self.raiz, campo, "ab")
        self.raiz.disparar("Entry", "<KeyRelease>", campo, keysym="Left")
        digitar(self.raiz, campo, "cd")
        teclas(self.raiz, campo, "<Control-Key-z>")
        self.assertEqual(campo.texto, "ab")
        digitar(self.raiz, campo, "ef")
        self.raiz.disparar("Entry", "<ButtonRelease-1>", campo)
        digitar(self.raiz, campo, "gh")
        teclas(self.raiz, campo, "<Control-Key-z>")
        self.assertEqual(campo.texto, "abef")

    def test_ttk_combobox_usa_as_mesmas_regras(self):
        campo = EntradaFalsa("")
        self.raiz.disparar("TCombobox", "<FocusIn>", campo)
        digitar(self.raiz, campo, "xy", classe="TCombobox")
        teclas(self.raiz, campo, "<Control-Key-z>", classe="TCombobox")
        self.assertEqual(campo.texto, "")


# ================================================================================== caixas de várias linhas
class TestCaixasDeTexto(unittest.TestCase):
    def setUp(self):
        self.raiz = instalado()

    def test_ao_receber_foco_liga_o_desfazer_nativo(self):
        caixa = TextoFalso("x")
        self.raiz.disparar("Text", "<FocusIn>", caixa)
        self.assertEqual((caixa.opcoes["undo"], caixa.opcoes["autoseparators"], caixa.opcoes["maxundo"]),
                         (True, True, -1))
        caixa2 = TextoFalso("x", undo=True)
        caixa2.opcoes["maxundo"] = 7
        self.raiz.disparar("Text", "<FocusIn>", caixa2)
        self.assertEqual(caixa2.opcoes["maxundo"], 7, "quem já ligou o desfazer não é alterado")

    def test_ctrl_z_ctrl_y_f4_e_ctrl_shift_z(self):
        caixa = TextoFalso("x", undo=True)
        teclas(self.raiz, caixa, "<Control-Key-z>", classe="Text")
        teclas(self.raiz, caixa, "<Control-Key-y>", classe="Text")
        teclas(self.raiz, caixa, "<F4>", classe="Text")
        teclas(self.raiz, caixa, "<Control-Key-Z>", state=SHIFT, classe="Text")
        teclas(self.raiz, caixa, "<Control-Key-Z>", state=0, classe="Text")
        self.assertEqual(caixa.chamadas, ["undo", "redo", "redo", "redo", "undo"])

    def test_nada_a_desfazer_nao_gera_erro(self):
        caixa = TextoFalso("x", undo=True)
        caixa.edit_undo = mock.Mock(side_effect=ae.TclError("nothing to undo"))
        self.assertEqual(teclas(self.raiz, caixa, "<Control-Key-z>", classe="Text"), "break")

    def test_alt_f4_nao_e_interceptado(self):
        caixa = TextoFalso("x", undo=True)
        self.assertIsNone(teclas(self.raiz, caixa, "<Alt-Key-F4>", classe="Text"))
        self.assertIsNone(teclas(self.raiz, caixa, "<F4>", state=ALT, classe="Text"))
        self.assertEqual(caixa.chamadas, [])

    def test_ctrl_a_seleciona_tudo(self):
        caixa = TextoFalso("linha 1\nlinha 2")
        teclas(self.raiz, caixa, "<Control-Key-a>", classe="Text")
        self.assertEqual((caixa.sel, caixa.cursor), (((1, 0), (2, 7)), (2, 7)))

    def test_ctrl_shift_v_usa_a_colagem_nativa(self):
        caixa = TextoFalso("")
        teclas(self.raiz, caixa, "<Control-Shift-Key-V>", classe="Text")
        self.assertEqual(caixa.gerados, ["<<Paste>>"])

    def test_ctrl_backspace_apaga_palavra_e_junta_linhas(self):
        caixa = TextoFalso("primeira linha\nsegunda linha")
        caixa.cursor = (2, 13)
        teclas(self.raiz, caixa, "<Control-Key-BackSpace>", classe="Text")
        self.assertEqual(caixa.todo(), "primeira linha\nsegunda ")
        caixa.cursor = (2, 0)
        teclas(self.raiz, caixa, "<Control-Key-BackSpace>", classe="Text")        # início da linha: junta com a de cima
        self.assertEqual(caixa.todo(), "primeira linhasegunda ")
        caixa.cursor = (1, 0)
        teclas(self.raiz, caixa, "<Control-Key-BackSpace>", classe="Text")        # início do texto: nada
        self.assertEqual(caixa.todo(), "primeira linhasegunda ")

    def test_ctrl_delete_apaga_palavra_e_junta_linhas(self):
        caixa = TextoFalso("primeira linha\nsegunda linha")
        caixa.cursor = (1, 0)
        teclas(self.raiz, caixa, "<Control-Key-Delete>", classe="Text")
        self.assertEqual(caixa.todo(), "linha\nsegunda linha")
        caixa.cursor = (1, 5)
        teclas(self.raiz, caixa, "<Control-Key-Delete>", classe="Text")           # fim da linha: junta com a de baixo
        self.assertEqual(caixa.todo(), "linhasegunda linha")
        caixa.cursor = (1, 18)
        teclas(self.raiz, caixa, "<Control-Key-Delete>", classe="Text")           # fim do texto: nada
        self.assertEqual(caixa.todo(), "linhasegunda linha")

    def test_ctrl_backspace_com_selecao_apaga_so_a_selecao(self):
        caixa = TextoFalso("abc def ghi")
        caixa.sel = ((1, 4), (1, 7))
        teclas(self.raiz, caixa, "<Control-Key-BackSpace>", classe="Text")
        self.assertEqual(caixa.todo(), "abc  ghi")

    def test_texto_desativado_nao_muda(self):
        caixa = TextoFalso("só leitura", estado="disabled")
        caixa.cursor = (1, 10)
        teclas(self.raiz, caixa, "<Control-Key-BackSpace>", classe="Text")
        teclas(self.raiz, caixa, "<Control-Key-Delete>", classe="Text")
        self.assertEqual(caixa.todo(), "só leitura")


# ================================================================================== tabelas
class TestTabelas(unittest.TestCase):
    def setUp(self):
        self.raiz = instalado()
        self.linhas = [(1, "Maria Souza", "02/03/1950", "Feminino"), (2, "José Lima", "10/11/1948", "Masculino"),
                       (3, "Ana\tPaula", "05/05/1960", "Feminino")]

    def test_ctrl_a_seleciona_todas_as_linhas(self):
        tabela = TabelaFalsa(self.linhas)
        self.assertEqual(teclas(self.raiz, tabela, "<Control-Key-a>", classe="Treeview"), "break")
        self.assertEqual(tabela.escolhidos, ("I0", "I1", "I2"))

    def test_ctrl_a_respeita_selecao_unica(self):
        tabela = TabelaFalsa(self.linhas, modo="browse")
        teclas(self.raiz, tabela, "<Control-Key-a>", classe="Treeview")
        self.assertEqual(tabela.escolhidos, ())

    def test_ctrl_c_copia_as_linhas_na_ordem_da_tela_em_colunas(self):
        tabela = TabelaFalsa(self.linhas)
        tabela.escolhidos = ("I2", "I0")                                 # o Tk não garante a ordem da seleção
        self.assertEqual(teclas(self.raiz, tabela, "<Control-Key-c>", classe="Treeview"), "break")
        self.assertEqual(tabela.copiado, "1\tMaria Souza\t02/03/1950\tFeminino\n3\tAna Paula\t05/05/1960\tFeminino")

    def test_ctrl_c_tambem_com_caps_lock_e_ctrl_insert(self):
        for seq in ("<Control-Key-C>", "<Control-Key-Insert>"):
            tabela = TabelaFalsa(self.linhas)
            tabela.escolhidos = ("I1",)
            teclas(self.raiz, tabela, seq, classe="Treeview")
            self.assertEqual(tabela.copiado, "2\tJosé Lima\t10/11/1948\tMasculino", seq)

    def test_ctrl_c_sem_selecao_nao_apaga_a_area_de_transferencia(self):
        tabela = TabelaFalsa(self.linhas)
        self.assertIsNone(teclas(self.raiz, tabela, "<Control-Key-c>", classe="Treeview"))
        self.assertIsNone(tabela.copiado)

    def test_tabela_com_coluna_de_arvore_leva_o_texto_primeiro(self):
        tabela = TabelaFalsa([("a",), ("b",)], mostra="tree headings")
        tabela.escolhidos = ("I1",)
        teclas(self.raiz, tabela, "<Control-Key-c>", classe="Treeview")
        self.assertEqual(tabela.copiado, "texto de I1\tb")

    def test_atalhos_com_alt_ficam_com_o_sistema(self):
        tabela = TabelaFalsa(self.linhas)
        tabela.escolhidos = ("I0",)
        self.assertIsNone(teclas(self.raiz, tabela, "<Control-Key-c>", state=ALT, classe="Treeview"))
        self.assertIsNone(teclas(self.raiz, tabela, "<Control-Key-a>", state=ALT, classe="Treeview"))
        self.assertIsNone(tabela.copiado)


if __name__ == "__main__":
    unittest.main(verbosity=2)
