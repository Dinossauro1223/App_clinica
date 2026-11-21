# -*- coding: utf-8 -*-
"""Atalhos de teclado de edição, no estilo do Google Planilhas, para todos os campos do NutriLab.

O que muda para quem digita (vale para todas as telas, sem alterar cada campo):

* Campos de uma linha (CTkEntry, CTkComboBox editável): o Tk não tem "desfazer" neles. Aqui cada campo ganha
  um histórico próprio. Ctrl+Z desfaz, Ctrl+Y, Ctrl+Shift+Z e F4 refazem. Digitar em sequência conta como uma
  etapa por palavra, como nas planilhas.
* Caixas de texto de várias linhas (CTkTextbox): usam o desfazer nativo do Tk, ligado automaticamente.
* Colar: uma célula copiada do Google Planilhas chega com quebra de linha no fim e várias células chegam
  separadas por tabulação. Em campo de uma linha isso vira texto limpo.
* Ctrl+A seleciona tudo, Ctrl+Backspace e Ctrl+Delete apagam por palavra.
* Tabelas (ttk.Treeview: Mapa, pacientes, suplementos): Ctrl+A seleciona todas as linhas e Ctrl+C copia as
  linhas selecionadas com as colunas separadas por tabulação, que o Planilhas cola em células.
* F1 mostra a lista de atalhos.

A lógica (histórico, limites de palavra, tratamento do texto colado, texto copiado das tabelas) é Python puro e
fica no topo do arquivo; a ligação com o Tk vem depois e é instalada uma única vez por `instalar(raiz)`.
"""
import re
import sys
import time
import traceback

try:  # este módulo também é importado em ambientes sem Tk (testes da lógica pura)
    from tkinter import TclError
except ImportError:  # pragma: no cover
    class TclError(Exception):
        pass


# ----------------------------------------------------------------------------- lista de atalhos (F1 e documentação)
ATALHOS = (
    ("Campos de texto", (
        ("Copiar", "Ctrl+C"),
        ("Recortar", "Ctrl+X"),
        ("Colar (uma célula do Planilhas entra sem a quebra de linha)", "Ctrl+V"),
        ("Colar só o texto, sem formatação", "Ctrl+Shift+V"),
        ("Desfazer", "Ctrl+Z"),
        ("Refazer", "Ctrl+Y, Ctrl+Shift+Z ou F4"),
        ("Selecionar tudo", "Ctrl+A"),
        ("Apagar a palavra anterior", "Ctrl+Backspace"),
        ("Apagar a próxima palavra", "Ctrl+Delete"),
        ("Pular de palavra em palavra (com Shift, seleciona)", "Ctrl+Seta esquerda ou direita"),
    )),
    ("Tabelas (Mapa, pacientes, suplementos)", (
        ("Selecionar todas as linhas", "Ctrl+A"),
        ("Copiar as linhas selecionadas (cola em colunas no Planilhas)", "Ctrl+C"),
    )),
    ("Em qualquer tela", (
        ("Mostrar esta lista de atalhos", "F1"),
    )),
)


def texto_ajuda():
    """Texto da janela do F1 (e base do documento ATALHOS_DE_TECLADO.md)."""
    partes = []
    for titulo, itens in ATALHOS:
        partes.append(titulo)
        partes.extend(f"  {tecla}:  {acao}" for acao, tecla in itens)
        partes.append("")
    return "\n".join(partes).rstrip()


# ----------------------------------------------------------------------------- lógica pura
LIMITE_HISTORICO = 300      # etapas de desfazer guardadas por campo
PAUSA_AGRUPAR = 1.0         # segundos: uma pausa maior que isso começa uma nova etapa


def _classe(c):
    if c.isspace():
        return "espaco"
    if c.isalnum() or c == "_":
        return "palavra"
    return "simbolo"


def prefixo_sufixo(a, b):
    """Tamanho do começo e do fim iguais entre dois textos (sem sobreposição)."""
    n = min(len(a), len(b))
    p = 0
    while p < n and a[p] == b[p]:
        p += 1
    s = 0
    while s < n - p and a[len(a) - 1 - s] == b[len(b) - 1 - s]:
        s += 1
    return p, s


def posicao_apos_troca(antes, depois):
    """Onde fica o cursor em `depois` logo após trocar `antes` por ele: no fim do trecho que mudou."""
    _, s = prefixo_sufixo(antes, depois)
    return len(depois) - s


def inicio_palavra_anterior(texto, pos):
    """Índice onde começa a palavra à esquerda de `pos` (Ctrl+Backspace apaga até aqui)."""
    i = max(0, min(pos, len(texto)))
    while i > 0 and texto[i - 1].isspace():
        i -= 1
    if i > 0:
        c = _classe(texto[i - 1])
        while i > 0 and _classe(texto[i - 1]) == c:
            i -= 1
    return i


def fim_palavra_seguinte(texto, pos):
    """Índice onde termina a palavra à direita de `pos`, levando os espaços que vêm depois (Ctrl+Delete)."""
    n = len(texto)
    i = max(0, min(pos, n))
    if i < n:
        c = _classe(texto[i])
        while i < n and _classe(texto[i]) == c:
            i += 1
        if c != "espaco":
            while i < n and texto[i].isspace():
                i += 1
    return i


def texto_para_campo_simples(texto):
    """Prepara um texto colado para um campo de uma linha.

    Uma célula copiada do Planilhas termina com quebra de linha e várias células vêm separadas por tabulação ou
    quebra de linha: tudo vira um texto só, separado por espaço. Caracteres de controle invisíveis são removidos.
    """
    if not texto:
        return ""
    t = str(texto).replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    t = re.sub(r"[\t\n\x0b\x0c]+", " ", t)
    return re.sub(r"[\x00-\x08\x0e-\x1f\x7f]", "", t)


def linhas_para_tsv(linhas):
    """Texto no formato que o Planilhas e o Excel colam em células: colunas por tabulação, linhas por quebra."""
    def celula(v):
        s = "" if v is None else str(v)
        return re.sub(r"[\t\r\n]+", " ", s)
    return "\n".join("\t".join(celula(v) for v in linha) for linha in linhas)


def _classificar(antigo, novo):
    """('ins'|'del', caractere) se foi exatamente um caractere digitado/apagado; senão (None, '')."""
    p, s = prefixo_sufixo(antigo, novo)
    if len(novo) == len(antigo) + 1 and p + s >= len(antigo):
        return "ins", novo[p]
    if len(novo) == len(antigo) - 1 and p + s >= len(novo):
        return "del", antigo[p]
    return None, ""


class HistoricoEdicao:
    """Desfazer/refazer de um campo de uma linha.

    Guarda só o texto de cada etapa; a posição do cursor é calculada comparando os textos. Caracteres digitados
    (ou apagados) em sequência formam uma etapa só, até uma pausa, uma troca de direção, o cursor mudar de lugar
    ou começar outra palavra. Colar, recortar e substituir seleção são etapas próprias.
    """

    def __init__(self, texto="", limite=LIMITE_HISTORICO):
        self.atual = texto
        self._desfazer, self._refazer = [], []
        self._limite = limite
        self._tipo, self._instante, self._ultimo = None, 0.0, ""

    def pode_desfazer(self):
        return bool(self._desfazer)

    def pode_refazer(self):
        return bool(self._refazer)

    def sincronizar(self, texto):
        """Aceita o conteúdo atual do campo sem criar etapa (usado depois de aplicar desfazer/refazer)."""
        self.atual = texto

    def registrar(self, texto, agora=None):
        """Informa o conteúdo do campo depois de uma edição. Devolve True se o texto mudou."""
        agora = time.monotonic() if agora is None else agora
        antigo = self.atual
        if texto == antigo:
            return False
        tipo, caractere = _classificar(antigo, texto)
        nova_palavra = self._ultimo.isspace() and caractere != "" and not caractere.isspace()
        agrupa = (tipo is not None and tipo == self._tipo and bool(self._desfazer)
                  and agora - self._instante <= PAUSA_AGRUPAR and not nova_palavra)
        if not agrupa:
            self._desfazer.append(antigo)
            if len(self._desfazer) > self._limite:
                del self._desfazer[0]
        self._refazer.clear()
        self.atual = texto
        self._tipo, self._instante, self._ultimo = tipo, agora, caractere
        return True

    def quebrar_grupo(self):
        """O cursor mudou de lugar ou o campo trocou de foco: a próxima digitação abre uma nova etapa."""
        self._tipo = None

    def desfazer(self):
        """Texto da etapa anterior, ou None se não há o que desfazer."""
        if not self._desfazer:
            return None
        self._refazer.append(self.atual)
        self.atual = self._desfazer.pop()
        self._tipo = None
        return self.atual

    def refazer(self):
        """Texto da etapa desfeita, ou None se não há o que refazer."""
        if not self._refazer:
            return None
        self._desfazer.append(self.atual)
        self.atual = self._refazer.pop()
        self._tipo = None
        return self.atual


# ----------------------------------------------------------------------------- ligação com o Tk
_ENTRADAS = ("Entry", "TEntry", "TCombobox")
_TEXTO = "Text"
_TABELA = "Treeview"
_MASCARA_SHIFT = 0x1
_MASCARA_ALT = 0x20000 if sys.platform == "win32" else 0x8
_HIST = {}   # caminho do widget -> HistoricoEdicao


def _seguro(funcao):
    """Um atalho nunca pode derrubar a tela: qualquer erro vira mensagem no console e o Tk segue normal."""
    def envolvido(ev=None):
        try:
            return funcao(ev)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            return None
    envolvido.__name__ = getattr(funcao, "__name__", "atalho")
    return envolvido


def _com_alt(ev):
    return bool(getattr(ev, "state", 0) & _MASCARA_ALT)


def _com_shift(ev):
    return bool(getattr(ev, "state", 0) & _MASCARA_SHIFT)


# ------------------------------------------------------------------ campos de uma linha
def _e_editavel(w):
    try:
        return str(w.cget("state")) in ("normal", "")
    except Exception:  # noqa: BLE001
        return False


def _historico(w):
    """Histórico do campo, já sincronizado com o que está escrito agora."""
    chave = str(w)
    texto = w.get()
    h = _HIST.get(chave)
    if h is None:
        h = _HIST[chave] = HistoricoEdicao(texto)
    else:
        h.registrar(texto)
    return h


def _e_aplicar(w, texto, antes):
    w.delete(0, "end")
    w.insert(0, texto)
    w.icursor(posicao_apos_troca(antes, texto))
    try:
        w.selection_clear()
    except TclError:
        pass


def _e_ao_focar(ev):
    w = ev.widget
    texto = w.get()
    h = _HIST.get(str(w))
    if h is None or h.atual != texto:   # o programa trocou o texto enquanto o campo estava sem foco
        _HIST[str(w)] = HistoricoEdicao(texto)
    else:
        h.quebrar_grupo()


_TECLAS_DE_CURSOR = frozenset({"Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next"})


def _e_apos_alteracao(ev):
    """Depois de digitar, recortar ou limpar: se o texto mudou, vira etapa do desfazer."""
    h = _HIST.get(str(ev.widget))
    if h is None:
        return
    mudou = h.registrar(ev.widget.get())
    if not mudou and getattr(ev, "keysym", "") in _TECLAS_DE_CURSOR:
        h.quebrar_grupo()   # andar com o cursor encerra o agrupamento da digitação


def _e_clique(ev):
    h = _HIST.get(str(ev.widget))
    if h is not None:
        h.quebrar_grupo()


def _e_ao_destruir(ev):
    _HIST.pop(str(ev.widget), None)


def _e_desfazer_ou_refazer(w, refazer):
    if not _e_editavel(w):
        return
    h = _historico(w)
    antes = w.get()
    novo = h.refazer() if refazer else h.desfazer()
    if novo is not None:
        _e_aplicar(w, novo, antes)
        h.sincronizar(w.get())   # se o campo recusou o texto (validação), o histórico acompanha o que ficou


def _e_tecla_z(ev):
    if _com_alt(ev):
        return None
    _e_desfazer_ou_refazer(ev.widget, refazer=_com_shift(ev))
    return "break"


def _e_tecla_y(ev):
    if _com_alt(ev):
        return None
    _e_desfazer_ou_refazer(ev.widget, refazer=True)
    return "break"


def _e_tecla_f4(ev):
    if _com_alt(ev):   # Alt+F4 é do sistema (fechar a janela)
        return None
    _e_desfazer_ou_refazer(ev.widget, refazer=True)
    return "break"


def _e_selecionar_tudo(ev):
    if _com_alt(ev):
        return None
    w = ev.widget
    w.selection_range(0, "end")
    w.icursor("end")
    return "break"


def _e_apagar_selecao(w):
    try:
        if w.selection_present():
            w.delete("sel.first", "sel.last")
            return True
    except TclError:
        pass
    return False


def _e_apagar_palavra(ev, direcao):
    w = ev.widget
    if not _e_editavel(w):
        return "break"
    _historico(w)
    if not _e_apagar_selecao(w):
        texto, pos = w.get(), w.index("insert")
        if direcao < 0:
            w.delete(inicio_palavra_anterior(texto, pos), pos)
        else:
            w.delete(pos, fim_palavra_seguinte(texto, pos))
    _historico(w)
    return "break"


def _e_colar(ev):
    w = ev.widget
    if not _e_editavel(w):
        return "break"
    try:
        bruto = w.clipboard_get()
    except TclError:   # área de transferência vazia ou sem texto
        return "break"
    texto = texto_para_campo_simples(bruto)
    if not texto:
        return "break"
    _historico(w)
    _e_apagar_selecao(w)
    w.insert("insert", texto)
    _historico(w)
    return "break"


# ------------------------------------------------------------------ caixas de texto (várias linhas)
def _t_ao_focar(ev):
    w = ev.widget
    try:
        if str(w.cget("undo")).lower() not in ("1", "true", "yes", "on"):
            w.configure(undo=True, autoseparators=True, maxundo=-1)
    except TclError:
        pass


def _t_desfazer_ou_refazer(w, refazer):
    try:
        w.edit_redo() if refazer else w.edit_undo()
    except TclError:   # nada para desfazer/refazer
        pass


def _t_tecla_z(ev):
    if _com_alt(ev):
        return None
    _t_desfazer_ou_refazer(ev.widget, refazer=_com_shift(ev))
    return "break"


def _t_tecla_y(ev):
    if _com_alt(ev):
        return None
    _t_desfazer_ou_refazer(ev.widget, refazer=True)
    return "break"


def _t_tecla_f4(ev):
    if _com_alt(ev):
        return None
    _t_desfazer_ou_refazer(ev.widget, refazer=True)
    return "break"


def _t_selecionar_tudo(ev):
    if _com_alt(ev):
        return None
    w = ev.widget
    w.tag_add("sel", "1.0", "end-1c")
    w.mark_set("insert", "end-1c")
    return "break"


def _t_editavel(w):
    try:
        return str(w.cget("state")) == "normal"
    except Exception:  # noqa: BLE001
        return False


def _t_apagar_palavra(ev, direcao):
    w = ev.widget
    if not _t_editavel(w):
        return "break"
    if w.tag_ranges("sel"):
        w.delete("sel.first", "sel.last")
        return "break"
    linha, coluna = (int(x) for x in str(w.index("insert")).split("."))
    if direcao < 0:
        antes = w.get(f"{linha}.0", f"{linha}.{coluna}")
        if antes:
            w.delete(f"{linha}.{inicio_palavra_anterior(antes, len(antes))}", f"{linha}.{coluna}")
        elif linha > 1:
            w.delete(f"{linha - 1}.end", f"{linha}.0")   # início da linha: junta com a linha de cima
    else:
        depois = w.get(f"{linha}.0", f"{linha}.end")[coluna:]
        if depois:
            w.delete(f"{linha}.{coluna}", f"{linha}.{coluna + fim_palavra_seguinte(depois, 0)}")
        elif linha < int(str(w.index("end-1c")).split(".")[0]):
            w.delete(f"{linha}.end", f"{linha + 1}.0")   # fim da linha: junta com a linha de baixo
    return "break"


def _t_colar_sem_formatacao(ev):
    if _com_alt(ev):
        return None
    ev.widget.event_generate("<<Paste>>")
    return "break"


# ------------------------------------------------------------------ tabelas
def _tabela_todos_os_itens(t, pai=""):
    itens = []
    for item in t.get_children(pai):
        itens.append(item)
        itens.extend(_tabela_todos_os_itens(t, item))
    return itens


def _tabela_selecionar_tudo(ev):
    if _com_alt(ev):
        return None
    t = ev.widget
    if str(t.cget("selectmode")) == "extended":
        t.selection_set(_tabela_todos_os_itens(t))
    return "break"


def _tabela_copiar(ev):
    if _com_alt(ev):
        return None
    t = ev.widget
    escolhidos = set(t.selection())
    if not escolhidos:
        return None
    mostra_arvore = "tree" in str(t.cget("show"))
    linhas = []
    for item in _tabela_todos_os_itens(t):
        if item in escolhidos:
            valores = list(t.item(item, "values"))
            linhas.append(([t.item(item, "text")] if mostra_arvore else []) + valores)
    t.clipboard_clear()
    t.clipboard_append(linhas_para_tsv(linhas))
    return "break"


# ------------------------------------------------------------------ ajuda (F1)
def _mostrar_ajuda(ev=None):
    from tkinter import messagebox
    pai = None
    try:
        pai = ev.widget.winfo_toplevel()
    except Exception:  # noqa: BLE001
        pass
    messagebox.showinfo("Atalhos de teclado", texto_ajuda(), parent=pai)
    return "break"


# ------------------------------------------------------------------ instalação
def _ligar(raiz, classe, sequencias, funcao, acrescentar=False):
    for seq in sequencias:
        try:
            raiz.bind_class(classe, seq, _seguro(funcao), add="+" if acrescentar else None)
        except TclError:
            pass   # sequência não aceita por esta versão do Tk: o atalho nativo continua valendo


def _ligar_entrada(raiz, classe):
    _ligar(raiz, classe, ("<Control-Key-z>", "<Control-Key-Z>"), _e_tecla_z)
    _ligar(raiz, classe, ("<Control-Key-y>", "<Control-Key-Y>"), _e_tecla_y)
    _ligar(raiz, classe, ("<F4>",), _e_tecla_f4)
    _ligar(raiz, classe, ("<Alt-Key-F4>",), lambda ev: None)      # fechar a janela continua com o sistema
    _ligar(raiz, classe, ("<Control-Key-a>", "<Control-Key-A>"), _e_selecionar_tudo)
    _ligar(raiz, classe, ("<Control-Key-BackSpace>",), lambda ev: _e_apagar_palavra(ev, -1))
    _ligar(raiz, classe, ("<Control-Key-Delete>",), lambda ev: _e_apagar_palavra(ev, +1))
    _ligar(raiz, classe, ("<<Paste>>", "<Control-Shift-Key-V>"), _e_colar)
    _ligar(raiz, classe, ("<FocusIn>",), _e_ao_focar, acrescentar=True)
    _ligar(raiz, classe, ("<KeyRelease>", "<<Cut>>", "<<Clear>>"), _e_apos_alteracao, acrescentar=True)
    _ligar(raiz, classe, ("<ButtonRelease-1>",), _e_clique, acrescentar=True)
    _ligar(raiz, classe, ("<Destroy>",), _e_ao_destruir, acrescentar=True)


def _ligar_texto(raiz, classe):
    _ligar(raiz, classe, ("<Control-Key-z>", "<Control-Key-Z>"), _t_tecla_z)
    _ligar(raiz, classe, ("<Control-Key-y>", "<Control-Key-Y>"), _t_tecla_y)
    _ligar(raiz, classe, ("<F4>",), _t_tecla_f4)
    _ligar(raiz, classe, ("<Alt-Key-F4>",), lambda ev: None)
    _ligar(raiz, classe, ("<Control-Key-a>", "<Control-Key-A>"), _t_selecionar_tudo)
    _ligar(raiz, classe, ("<Control-Key-BackSpace>",), lambda ev: _t_apagar_palavra(ev, -1))
    _ligar(raiz, classe, ("<Control-Key-Delete>",), lambda ev: _t_apagar_palavra(ev, +1))
    _ligar(raiz, classe, ("<Control-Shift-Key-V>",), _t_colar_sem_formatacao)
    _ligar(raiz, classe, ("<FocusIn>",), _t_ao_focar, acrescentar=True)


def _ligar_tabela(raiz, classe):
    _ligar(raiz, classe, ("<Control-Key-a>", "<Control-Key-A>"), _tabela_selecionar_tudo)
    _ligar(raiz, classe, ("<Control-Key-c>", "<Control-Key-C>", "<Control-Key-Insert>"), _tabela_copiar)


def instalar(raiz):
    """Liga os atalhos em todos os campos e tabelas do programa (janelas já abertas e futuras).

    Pode ser chamada mais de uma vez; só a primeira tem efeito. Devolve True quando instalou agora.
    """
    if getattr(raiz, "_nutrilab_atalhos_instalados", False):
        return False
    for classe in _ENTRADAS:
        _ligar_entrada(raiz, classe)
    _ligar_texto(raiz, _TEXTO)
    _ligar_tabela(raiz, _TABELA)
    try:
        raiz.bind_all("<F1>", _seguro(_mostrar_ajuda), add="+")
    except TclError:
        pass
    raiz._nutrilab_atalhos_instalados = True
    return True
