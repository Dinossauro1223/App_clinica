# -*- coding: utf-8 -*-
"""Telas das condutas de alta (CustomTkinter).

  * PainelCondutasAlta: bloco fixo da tela de consulta. Mostra, sempre, quantas condutas de alta ainda estão sem
    decisão da nutricionista e abre a janela de trabalho.
  * JanelaCondutasAlta: uma conduta por cartão. A nutricionista lê o texto técnico completo, corrige o texto do
    paciente (leigo) e CONFIRMA ou marca "não se aplica" (com motivo). Daí exporta PDF, imprime e marca como entregue.
  * lembrar_condutas_pendentes: aviso depois de salvar a evolução.

Nenhuma regra clínica fica aqui: tudo vem de condutas_alta.SessaoCondutasAlta (testada sem interface). Os PDFs vêm
de condutas_alta_export. O catálogo só SUGERE: nada vai para o paciente sem confirmação da nutricionista.
"""
import os
import tempfile
import tkinter as tk
from tkinter import messagebox, filedialog

import customtkinter as ctk

import condutas_alta as ca\nimport midias_usuario
import condutas_alta_export as ex
import tema
import mapa_db as mdb
from mapa_ui import (VERDE_ESC, VERDE, VERDE_HOVER, FUNDO, CINZA_BTN, CINZA_HOVER, VERMELHO, LARANJA, _btn,
                     _set_entry, _tornar_modal)

AZUL, AZUL_HOVER = tema.AZUL, tema.AZUL_HOVER
LARANJA_HOVER = tema.LARANJA
COR_ESTADO = {"pendente": LARANJA, "confirmada": VERDE_ESC, "nao_se_aplica": tema.SUAVE}
ROTULO_ESTADO = {"pendente": "PENDENTE", "confirmada": "CONFIRMADA", "nao_se_aplica": "NÃO SE APLICA"}


# --------------------------------------------------------------------------------- textos (sem widgets)
def _plural(n, singular, plural):
    return singular if n == 1 else plural


def texto_status(sessao):
    """(mensagem, cor) que resume a situação das condutas de alta do paciente."""
    pend = sessao.pendentes()
    if pend:
        n = len(pend)
        sufixo = " (nova versão)" if sessao.entregue else ""
        return (f"{n} {_plural(n, 'conduta de alta pendente', 'condutas de alta pendentes')}{sufixo}: "
                "confirme antes de o paciente ir para casa.", LARANJA)
    if sessao.entregue:
        quando = mdb.iso_para_br(((sessao.doc or {}).get("entregue_em") or "")[:10])
        return f"Folha de alta entregue em {quando}. Para corrigir, crie uma nova versão.", VERDE_ESC
    if sessao.itens:
        return ("Todas as condutas de alta já foram decididas. Falta marcar como entregue quando a folha for dada.",
                VERDE_ESC)
    if sessao.sem_registro:      # sem registro o programa não sabe as doenças: "nenhuma sugerida" enganaria
        return ("Este paciente não tem registro no Mapa, então nenhuma conduta foi sugerida. Confira as doenças no "
                "prontuário e adicione as condutas do catálogo que se aplicarem.", LARANJA)
    return "Nenhuma conduta sugerida pelas doenças do Mapa. Você pode adicionar condutas do catálogo.", tema.SUAVE


def etiqueta_estado(c):
    """Texto do canto do cartão: estado da conduta e avisos que a nutricionista precisa ver."""
    partes = [ROTULO_ESTADO[c["estado"]]]
    if c["editado"]:
        partes.append("texto editado")
    if c["origem"] == "manual":
        partes.append("adicionada por você")
    if c["catalogo_mudou"]:
        partes.append("catálogo atualizado depois")
    return "  |  ".join(partes)


def texto_tecnico(c):
    """Visão integral da nutricionista: texto técnico, o que conferir antes de confirmar e as referências."""
    partes = ["TEXTO TÉCNICO (nutricionista)", c["texto_profissional"]]
    if c["conferir"]:
        partes += ["", "CONFERIR ANTES DE CONFIRMAR"] + ["- " + x for x in c["conferir"]]
    if c["fontes"]:
        partes += ["", "REFERÊNCIAS"] + list(c["fontes"])
    return "\n".join(partes)


def _canvas_rolagem(frame):
    return getattr(frame, "_parent_canvas", None)       # detalhe interno do CustomTkinter; pode não existir


def _posicao_rolagem(frame):
    canvas = _canvas_rolagem(frame)
    try:
        return canvas.yview()[0] if canvas is not None else None
    except (AttributeError, TypeError, IndexError, tk.TclError):
        return None


def _restaurar_rolagem(frame, posicao):
    """Depois de redesenhar os cartões, volta para onde a nutricionista estava (só estética; falhar não importa)."""
    canvas = _canvas_rolagem(frame)
    if canvas is None or posicao is None:
        return
    try:
        frame.update_idletasks()
        canvas.yview_moveto(posicao)
    except (AttributeError, TypeError, tk.TclError):
        pass


# --------------------------------------------------------------------------------------------- painel
class PainelCondutasAlta(ctk.CTkFrame):
    """Lembrete permanente na consulta: situação das condutas de alta do paciente e botão para abri-las."""

    def __init__(self, master, db_path, id_paciente, nome_paciente="", pasta_saida=None, janela_pai=None):
        super().__init__(master, fg_color=tema.LARANJA_CLARO, border_width=1, border_color=tema.LARANJA, corner_radius=8)
        self.db, self.id_paciente, self.nome = db_path, id_paciente, nome_paciente or ""
        self.pasta_saida, self.janela_pai = pasta_saida, janela_pai or master
        self.sessao = None
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(topo, text="Condutas de alta", font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=VERDE_ESC).pack(side="left")
        _btn(topo, "Abrir condutas de alta", self.abrir, 190, LARANJA, LARANJA_HOVER, 30).pack(side="right")
        self.lbl_doencas = ctk.CTkLabel(self, text="", anchor="w", justify="left", wraplength=760,
                                        font=ctk.CTkFont(size=13), text_color=tema.TEXTO)
        self.lbl_doencas.pack(fill="x", padx=12, pady=(2, 0))
        self.lbl_status = ctk.CTkLabel(self, text="", anchor="w", justify="left", wraplength=760,
                                       font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_status.pack(fill="x", padx=12, pady=(0, 8))
        self.atualizar()

    def atualizar(self):
        try:
            self.sessao = ca.SessaoCondutasAlta(self.db, self.id_paciente, self.nome)
        except ca.ErroCondutasAlta as erro:
            self.sessao = None
            self.lbl_doencas.configure(text="")
            self.lbl_status.configure(text=f"Condutas de alta indisponíveis: {erro}", text_color=VERMELHO)
            return
        self.lbl_doencas.configure(
            text=ca.frase_doencas_do_mapa(self.sessao.rotulos, self.sessao.sem_registro) + ".")
        texto, cor = texto_status(self.sessao)
        self.lbl_status.configure(text=texto, text_color=cor)

    def pendencias(self):
        """Quantas condutas sugeridas ainda esperam decisão (0 se o módulo estiver indisponível)."""
        self.atualizar()
        return len(self.sessao.pendentes()) if self.sessao else 0

    def abrir(self):
        return abrir_condutas_alta(self.janela_pai, self.db, self.id_paciente, self.nome, self.pasta_saida,
                                   ao_fechar=self.atualizar)


def abrir_condutas_alta(pai, db_path, id_paciente, nome_paciente="", pasta_saida=None, ao_fechar=None):
    """Abre a janela das condutas de alta. Se o módulo estiver indisponível (catálogo inválido, banco sem a migração),
    explica o motivo e não abre janela vazia."""
    try:
        sessao = ca.SessaoCondutasAlta(db_path, id_paciente, nome_paciente)
    except ca.ErroCondutasAlta as erro:
        messagebox.showerror("Condutas de alta", str(erro), parent=pai)
        return None
    return JanelaCondutasAlta(pai, sessao, pasta_saida, ao_fechar)


def lembrar_condutas_pendentes(painel, rotulo=None):
    """Depois de salvar a evolução: lembra as condutas de alta sem decisão e oferece abrir a janela.
    Devolve quantas estão pendentes (0 = nada a lembrar)."""
    n = painel.pendencias() if painel is not None else 0
    if not n:
        return 0
    aviso = f"Atenção: {n} {_plural(n, 'conduta de alta aguardando', 'condutas de alta aguardando')} confirmação."
    if rotulo is not None:
        atual = (rotulo.cget("text") or "").strip()
        rotulo.configure(text=(atual + "\n" if atual else "") + aviso, text_color=LARANJA)
    if messagebox.askyesno(
            "Condutas de alta pendentes",
            aviso + "\n\nAs condutas só vão para a folha do paciente depois de confirmadas por você.\n\n"
                    "Abrir as condutas de alta agora?", parent=painel.janela_pai):
        painel.abrir()
    return n


# --------------------------------------------------------------------------------------------- janela
class JanelaCondutasAlta(ctk.CTkFrame):
    """Conteúdo de condutas de alta hospedado em uma guia lateral, sem janela modal."""

    def __init__(self, pai, sessao, pasta_saida=None, ao_fechar=None):
        self.app = pai
        self._painel_externo = bool(pai and hasattr(pai, "abrir_painel_lateral"))
        if self._painel_externo:
            abrir = getattr(pai, "abrir_painel_modal", pai.abrir_painel_lateral)
            self._painel_frame = abrir(
                f"Condutas de alta — {sessao.nome_paciente}", lambda: None
            )
            container = self._painel_frame
        else:
            self._painel_frame = None
            container = pai
        super().__init__(container, fg_color="transparent")
        self.pack(fill="both", expand=True)
        self.sessao, self.db = sessao, sessao.db
        self.pasta_saida, self.ao_fechar = pasta_saida, ao_fechar
        self._cartoes, self._textos, self._motivos = [], {}, {}\n        self._imagens_orientacao = []
        self._edicoes, self._motivos_digitados, self._abertos = {}, {}, set()
        self._opcoes = {}\n        self._imagens_orientacao = []
        self._montar()
        self._atualizar()

    def destroy(self):
        if getattr(self, "_destroy_em_progresso", False):
            return super().destroy()
        if self._painel_externo and self._painel_frame is not None:
            try:
                if getattr(self._painel_frame, "_fechando_painel", False):
                    return super().destroy()
                self._destroy_em_progresso = True
                self.app.fechar_painel_lateral(self._painel_frame)
                return
            except (tk.TclError, AttributeError):
                pass
        return super().destroy()

    # ------------------------------------------------------------------------------- construção
    def _montar(self):
        # Rodapé e campos fixos entram primeiro (side="bottom"): numa janela baixa quem encolhe é a lista, não os botões.
        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.pack(side="bottom", fill="x", padx=10, pady=8)
        self.lbl_msg = ctk.CTkLabel(self, text="", anchor="w", justify="left", wraplength=940,
                                    font=ctk.CTkFont(size=12, weight="bold"), text_color=VERDE_ESC)
        self.lbl_msg.pack(side="bottom", fill="x", padx=16)
        cab2 = ctk.CTkFrame(self, fg_color="transparent")
        cab2.pack(side="bottom", fill="x", padx=14, pady=(4, 0))
        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.pack(side="bottom", fill="x", padx=14, pady=(8, 0))
        add = ctk.CTkFrame(self, fg_color="transparent")
        add.pack(side="bottom", fill="x", padx=14, pady=(2, 0))

        ctk.CTkLabel(self, text=f"Condutas de alta: {self.sessao.nome_paciente}",
                     font=ctk.CTkFont(size=20, weight="bold"), text_color=VERDE_ESC, anchor="w"
                     ).pack(fill="x", padx=16, pady=(10, 0))
        self.lbl_doencas = ctk.CTkLabel(self, text="", anchor="w", justify="left", wraplength=940,
                                        font=ctk.CTkFont(size=13), text_color=tema.TEXTO)
        self.lbl_doencas.pack(fill="x", padx=16, pady=(2, 0))
        self.lbl_status = ctk.CTkLabel(self, text="", anchor="w", justify="left", wraplength=940,
                                       font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_status.pack(fill="x", padx=16)
        self.lbl_paginas = ctk.CTkLabel(self, text="", anchor="w", justify="left", wraplength=940,
                                        font=ctk.CTkFont(size=12), text_color=tema.SUAVE)
        self.lbl_paginas.pack(fill="x", padx=16, pady=(0, 4))
        self.corpo = ctk.CTkScrollableFrame(self, fg_color=FUNDO)
        self.corpo.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        ctk.CTkLabel(add, text="Adicionar conduta do catálogo:").pack(side="left", padx=(0, 6))
        self.cb_catalogo = ctk.CTkComboBox(add, values=[""], width=470, state="readonly")
        self.cb_catalogo.pack(side="left", padx=(0, 6))
        self.b_add = _btn(add, "Adicionar", self._adicionar_manual, 90, VERDE, VERDE_HOVER, 28)
        self.b_add.pack(side="left")

        ctk.CTkLabel(cab, text="Nutricionista:").pack(side="left", padx=(0, 4))
        self.e_nutri = ctk.CTkEntry(cab, width=280)
        self.e_nutri.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(cab, text="CRN:").pack(side="left", padx=(0, 4))
        self.e_crn = ctk.CTkEntry(cab, width=150)
        self.e_crn.pack(side="left")

        ctk.CTkLabel(cab2, text="Recado ao paciente (opcional; sai na folha):", width=250, anchor="w").pack(side="left")
        self.t_recado = ctk.CTkTextbox(cab2, width=640, height=48, wrap="word")
        self.t_recado.pack(side="left")

        _btn(rodape, "Fechar", self._fechar, 90, CINZA_BTN, CINZA_HOVER).pack(side="right")
        self.b_entregue = _btn(rodape, "Marcar como entregue", self._entregar, 170, VERDE, VERDE_HOVER)
        self.b_entregue.pack(side="right", padx=6)
        self.b_nova = _btn(rodape, "Criar nova versão", self._nova_versao, 140, LARANJA, LARANJA_HOVER)
        _btn(rodape, "Imprimir folha do paciente", self._imprimir, 190, AZUL, AZUL_HOVER).pack(side="left", padx=(0, 6))
        _btn(rodape, "PDF do paciente", lambda: self._exportar("paciente"), 130, AZUL, AZUL_HOVER
             ).pack(side="left", padx=(0, 6))
        _btn(rodape, "PDF completo (nutricionista)", lambda: self._exportar("profissional"), 210, CINZA_BTN,
             CINZA_HOVER).pack(side="left")

    def _montar_cartao(self, c):
        cod, estado = c["codigo"], c["estado"]
        editavel = not self.sessao.entregue
        q = ctk.CTkFrame(self.corpo, fg_color=tema.BRANCO, corner_radius=8)
        q.pack(fill="x", padx=8, pady=5)
        self._cartoes.append(q)

        topo = ctk.CTkFrame(q, fg_color="transparent")
        topo.pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkLabel(topo, text=f"[{cod}] {c['titulo']}", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=VERDE_ESC).pack(side="left")
        ctk.CTkLabel(topo, text=etiqueta_estado(c), font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=COR_ESTADO[estado]).pack(side="right")

        # Imagem de apoio opcional, vinculada ao código da orientação e gerenciada nas Configurações.
        caminho_imagem = midias_usuario.resolver_imagem("orientacoes", cod)
        if caminho_imagem:
            try:
                from PIL import Image
                imagem = Image.open(caminho_imagem).convert("RGB")
                imagem.thumbnail((760, 420), Image.Resampling.LANCZOS)
                foto = ctk.CTkImage(light_image=imagem, dark_image=imagem, size=imagem.size)
                self._imagens_orientacao.append(foto)
                ctk.CTkLabel(q, text="", image=foto).pack(anchor="w", padx=12, pady=(4, 6))
            except Exception:
                ctk.CTkLabel(q, text="Imagem de orientação cadastrada, mas não foi possível abri-la.",
                             text_color=tema.LARANJA).pack(anchor="w", padx=12, pady=4)

        # Texto técnico: fechado por padrão (a folha do paciente é curta; a visão integral fica a um clique).
        det = ctk.CTkFrame(q, fg_color=tema.FUNDO)
        ctk.CTkLabel(det, text=texto_tecnico(c), anchor="w", justify="left", wraplength=860,
                     font=ctk.CTkFont(size=12)).pack(fill="x", padx=10, pady=8)
        b_det = _btn(q, "", None, 260, CINZA_BTN, CINZA_HOVER, 26)

        def alternar(cod=cod, det=det, b=b_det):
            if cod in self._abertos:
                self._abertos.discard(cod)
                det.pack_forget()
                b.configure(text="Ver texto técnico, conferência e fontes")
            else:
                self._abertos.add(cod)
                det.pack(fill="x", padx=2, pady=(2, 4), after=b)
                b.configure(text="Ocultar texto técnico")

        b_det.configure(command=alternar, text="Ocultar texto técnico" if cod in self._abertos
                        else "Ver texto técnico, conferência e fontes")
        b_det.pack(anchor="w", padx=10, pady=(0, 2))
        if cod in self._abertos:
            det.pack(fill="x", padx=2, pady=(2, 4), after=b_det)

        if c["catalogo_mudou"]:
            ctk.CTkLabel(q, text="O catálogo foi atualizado depois desta decisão. Os textos mostrados são os da época. "
                                 "Para usar os textos novos, volte para pendente e confirme de novo.",
                         anchor="w", justify="left", wraplength=860, font=ctk.CTkFont(size=12), text_color=LARANJA
                         ).pack(fill="x", padx=12, pady=(2, 0))

        if estado == "nao_se_aplica":
            ctk.CTkLabel(q, text="Motivo: " + c["justificativa"], anchor="w", justify="left", wraplength=860,
                         font=ctk.CTkFont(size=12), text_color=tema.SUAVE).pack(fill="x", padx=12, pady=(2, 2))
        else:
            self._montar_texto_paciente(q, c)
        if editavel:
            self._montar_botoes(q, c)

    def _montar_texto_paciente(self, q, c):
        cod = c["codigo"]
        ctk.CTkLabel(q, text="TEXTO PARA O PACIENTE (leigo). Você pode corrigir. Cada linha que começa com '- ' vira "
                             "um marcador.", anchor="w", justify="left", wraplength=860,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", padx=12, pady=(4, 0))
        texto = self._edicoes.get(cod, c["texto_paciente"])
        lacunas = ca.contar_lacunas(texto)
        if lacunas:
            ctk.CTkLabel(q, text=f"{lacunas} {_plural(lacunas, 'campo em branco', 'campos em branco')} (____): preencha "
                                 "aqui ou deixe para escrever à mão na folha impressa.", anchor="w", justify="left",
                         wraplength=860, font=ctk.CTkFont(size=12), text_color=tema.SUAVE
                         ).pack(fill="x", padx=12, pady=(0, 0))
        linhas = sum(max(1, -(-len(ln) // 105)) for ln in texto.split("\n")) + 1
        t = ctk.CTkTextbox(q, width=860, height=min(380, max(84, 21 * linhas)), wrap="word")
        t.insert("1.0", texto)
        if self.sessao.entregue:
            t.configure(state="disabled")
        t.pack(padx=12, pady=(2, 4))
        self._textos[cod] = t

    def _montar_botoes(self, q, c):
        cod, estado = c["codigo"], c["estado"]
        botoes = ctk.CTkFrame(q, fg_color="transparent")
        botoes.pack(fill="x", padx=10, pady=(0, 8))
        if estado == "pendente":
            _btn(botoes, "Confirmar com este texto", lambda cod=cod: self._confirmar(cod), 190, VERDE, VERDE_HOVER, 28
                 ).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(botoes, text="Motivo, se não se aplica:").pack(side="left", padx=(8, 4))
            e = ctk.CTkEntry(botoes, width=250)
            _set_entry(e, self._motivos_digitados.get(cod, ""))
            e.pack(side="left", padx=(0, 6))
            self._motivos[cod] = e
            _btn(botoes, "Não se aplica", lambda cod=cod: self._nao_se_aplica(cod), 120, CINZA_BTN, CINZA_HOVER, 28
                 ).pack(side="left")
        elif estado == "confirmada":
            _btn(botoes, "Salvar correção do texto", lambda cod=cod: self._salvar_correcao(cod), 190, VERDE,
                 VERDE_HOVER, 28).pack(side="left", padx=(0, 8))
            _btn(botoes, "Voltar para pendente", lambda cod=cod: self._desfazer(cod), 160, CINZA_BTN, CINZA_HOVER, 28
                 ).pack(side="left")
        else:
            _btn(botoes, "Voltar para pendente", lambda cod=cod: self._desfazer(cod), 160, CINZA_BTN, CINZA_HOVER, 28
                 ).pack(side="left")

    # ------------------------------------------------------------------------------ atualização
    @staticmethod
    def _igual(a, b):
        return ca.normalizar_texto(a) == ca.normalizar_texto(b)

    def _guardar_edicoes(self):
        """Antes de redesenhar, guarda o que foi digitado e ainda não foi confirmado (nada se perde)."""
        for cod, t in self._textos.items():
            self._edicoes[cod] = t.get("1.0", "end-1c")
        for cod, e in self._motivos.items():
            self._motivos_digitados[cod] = e.get()

    def _atualizar(self):
        self._guardar_edicoes()
        posicao = _posicao_rolagem(self.corpo)
        for w in self._cartoes:
            w.destroy()
        self._cartoes, self._textos, self._motivos = [], {}, {}
        cartoes = self.sessao.cartoes()
        por_codigo = {c["codigo"]: c for c in cartoes}
        for cod in list(self._edicoes):          # texto digitado igual ao salvo não é "edição pendente"
            c = por_codigo.get(cod)
            if c is None or c["estado"] == "nao_se_aplica" or self._igual(self._edicoes[cod], c["texto_paciente"]):
                del self._edicoes[cod]
        for c in cartoes:
            self._montar_cartao(c)
        s = self.sessao
        self.lbl_doencas.configure(
            text=ca.frase_doencas_do_mapa(s.rotulos, s.sem_registro)
                 + ". Cada conduta abaixo é uma sugestão: só vale depois de confirmada por você.")
        texto, cor = texto_status(s)
        self.lbl_status.configure(text=texto, text_color=cor)
        cab = s.cabecalho()
        for entrada, valor in ((self.e_nutri, cab["nutricionista"]), (self.e_crn, cab["crn"])):
            entrada.configure(state="normal")
            _set_entry(entrada, valor)
        self.t_recado.configure(state="normal")
        self.t_recado.delete("1.0", "end")
        self.t_recado.insert("1.0", cab["recado"])
        presentes = {c["codigo"] for c in cartoes}
        self._opcoes = {f"{c.codigo}  {c.titulo}": c.codigo for c in s.catalogo.condutas.values()
                        if c.codigo not in presentes}
        self.cb_catalogo.configure(values=list(self._opcoes) or [""])
        self.cb_catalogo.set("")
        if s.entregue:
            self.b_entregue.pack_forget()
            self.b_nova.pack(side="right", padx=6)
            self.b_add.configure(state="disabled")
            for campo in (self.e_nutri, self.e_crn, self.t_recado):
                campo.configure(state="disabled")
        else:
            self.b_nova.pack_forget()
            self.b_entregue.pack(side="right", padx=6)
            self.b_add.configure(state="normal")
        self._atualizar_paginas()
        _restaurar_rolagem(self.corpo, posicao)

    def _atualizar_paginas(self):
        try:
            n = ex.contar_paginas(self.sessao.modelo_exportacao(), "paciente")
        except ca.ErroCondutasAlta:
            self.lbl_paginas.configure(text="Folha do paciente: nenhuma conduta confirmada ainda.")
        except ImportError:
            self.lbl_paginas.configure(text="Para gerar PDF, instale a biblioteca fpdf2 (pip install fpdf2).")
        else:
            conf = sum(1 for c in self.sessao.cartoes() if c["estado"] == "confirmada")
            self.lbl_paginas.configure(
                text=f"Folha do paciente: {n} {_plural(n, 'página', 'páginas')}, com {conf} "
                     f"{_plural(conf, 'conduta confirmada', 'condutas confirmadas')}. Só o que está confirmado entra "
                     "na folha.")

    def _msg(self, texto, cor=VERDE_ESC):
        self.lbl_msg.configure(text=texto, text_color=cor)

    # ----------------------------------------------------------------------------------- ações
    def _tentar(self, funcao, *args, **kw):
        try:
            funcao(*args, **kw)
            return True
        except ca.ErroCondutasAlta as erro:
            messagebox.showwarning("Condutas de alta", str(erro), parent=self)
            return False

    def _concluir(self, cod, mensagem, cor=VERDE_ESC):
        self._edicoes.pop(cod, None)
        self._motivos_digitados.pop(cod, None)
        self._textos.pop(cod, None)
        self._msg(mensagem, cor)
        self._atualizar()

    def _confirmar(self, cod):
        texto = self._textos[cod].get("1.0", "end-1c")
        if self._tentar(self.sessao.confirmar, cod, texto_paciente=texto):
            self._concluir(cod, f"{cod} confirmada.")

    def _salvar_correcao(self, cod):
        texto = self._textos[cod].get("1.0", "end-1c")
        if self._tentar(self.sessao.corrigir_texto, cod, texto):
            self._concluir(cod, f"Correção do texto de {cod} salva.")

    def _nao_se_aplica(self, cod):
        motivo = self._motivos[cod].get().strip()
        if self._tentar(self.sessao.nao_se_aplica, cod, motivo):
            self._concluir(cod, f"{cod} marcada como \"não se aplica\".")

    def _desfazer(self, cod):
        if self._tentar(self.sessao.desfazer, cod):
            self._concluir(cod, f"{cod} voltou para pendente.", LARANJA)

    def _adicionar_manual(self):
        cod = self._opcoes.get(self.cb_catalogo.get())
        if not cod:
            messagebox.showinfo("Condutas de alta", "Escolha uma conduta do catálogo na lista.", parent=self)
            return
        if self._tentar(self.sessao.adicionar_manual, cod):
            self._msg(f"{cod} adicionada como pendente: confirme ou marque \"não se aplica\".", LARANJA)
            self._atualizar()

    def _cabecalho_digitado(self):
        return self.e_nutri.get().strip(), self.e_crn.get().strip(), self.t_recado.get("1.0", "end-1c")

    def _salvar_cabecalho(self):
        nome, crn, recado = self._cabecalho_digitado()
        return self._tentar(self.sessao.salvar_cabecalho, nome, crn, recado)

    def _tem_edicoes_nao_salvas(self):
        """Códigos cujo texto do paciente foi alterado na tela e ainda não foi confirmado/salvo."""
        self._guardar_edicoes()
        por_codigo = {c["codigo"]: c for c in self.sessao.cartoes()}
        return [cod for cod, texto in self._edicoes.items()
                if cod in por_codigo and por_codigo[cod]["estado"] != "nao_se_aplica"
                and not self._igual(texto, por_codigo[cod]["texto_paciente"])]

    def _preparar_saida(self, perfil):
        """Salva o cabeçalho, avisa o que ficará de fora do papel e devolve o modelo de exportação (None = cancelado)."""
        if not self.sessao.entregue and not self._salvar_cabecalho():
            return None
        if perfil == "paciente":
            if not any(c["estado"] == "confirmada" for c in self.sessao.cartoes()):
                messagebox.showinfo("Folha do paciente", "Confirme pelo menos uma conduta antes de gerar a folha.",
                                    parent=self)
                return None
            avisos = []
            nao_salvas = self._tem_edicoes_nao_salvas()
            if nao_salvas:
                avisos.append("Há textos corrigidos que ainda NÃO foram confirmados e não entram na folha: "
                              + ", ".join(nao_salvas) + ".")
            pend = self.sessao.pendentes()
            if pend:
                avisos.append(f"Há {len(pend)} {_plural(len(pend), 'conduta pendente', 'condutas pendentes')} que NÃO "
                              "entram na folha: " + ", ".join(pend) + ".")
            if avisos and not messagebox.askyesno("Gerar a folha assim mesmo?",
                                                  "\n\n".join(avisos) + "\n\nGerar a folha mesmo assim?", parent=self):
                return None
        return self.sessao.modelo_exportacao()

    def _gerar(self, funcao, caminho, modelo):
        """Grava o PDF e devolve o número de páginas; em falha mostra a causa e devolve None."""
        try:
            return funcao(caminho, modelo)
        except ImportError as erro:
            messagebox.showerror("Biblioteca ausente", f"{erro}\n\nInstale com:  pip install fpdf2", parent=self)
        except OSError as erro:
            messagebox.showerror("Exportar", f"Não foi possível gravar o arquivo:\n{erro}", parent=self)
        except ca.ErroCondutasAlta as erro:
            messagebox.showwarning("Condutas de alta", str(erro), parent=self)
        except Exception as erro:  # erro inesperado de biblioteca: mostra em vez de falhar em silêncio
            messagebox.showerror("Exportar", f"Erro ao gerar o PDF:\n{type(erro).__name__}: {erro}", parent=self)
        return None

    def _exportar(self, perfil):
        modelo = self._preparar_saida(perfil)
        if modelo is None:
            return
        caminho = filedialog.asksaveasfilename(parent=self, defaultextension=".pdf",
                                               initialfile=ex.nome_sugerido(modelo, perfil),
                                               filetypes=[("PDF", "*.pdf")])
        if not caminho:
            return
        funcao = ex.exportar_pdf_paciente if perfil == "paciente" else ex.exportar_pdf_profissional
        n = self._gerar(funcao, caminho, modelo)
        if n is None:
            return
        self._msg(f"PDF salvo ({n} {_plural(n, 'página', 'páginas')}): {caminho}")
        if messagebox.askyesno("Exportar", "Arquivo gerado. Deseja abri-lo agora?", parent=self) \
                and hasattr(os, "startfile"):
            os.startfile(caminho)  # Windows

    def _imprimir(self):
        modelo = self._preparar_saida("paciente")
        if modelo is None:
            return
        pasta = self.pasta_saida or os.path.join(tempfile.gettempdir(), "NutriLab_impressao")
        try:
            os.makedirs(pasta, exist_ok=True)
        except OSError as erro:
            messagebox.showerror("Imprimir", f"Não foi possível preparar a pasta do PDF:\n{erro}", parent=self)
            return
        caminho = os.path.join(pasta, ex.nome_sugerido(modelo, "paciente"))
        n = self._gerar(ex.exportar_pdf_paciente, caminho, modelo)
        if n is None:
            return
        estado, msg = ex.imprimir_pdf(caminho)
        cor = {"impresso": VERDE_ESC, "aberto": LARANJA}.get(estado, VERMELHO)
        self._msg(f"{msg} ({n} {_plural(n, 'página', 'páginas')}). Cópia em PDF: {caminho}", cor)

    def _entregar(self):
        if not self._salvar_cabecalho():
            return
        nao_salvas = self._tem_edicoes_nao_salvas()
        if nao_salvas:
            messagebox.showwarning(
                "Condutas de alta", "Há textos corrigidos que ainda não foram confirmados: " + ", ".join(nao_salvas)
                + ".\nConfirme cada um (botão verde) antes de marcar como entregue.", parent=self)
            return
        if not messagebox.askyesno(
                "Marcar como entregue",
                "Depois de marcar como entregue, este documento não poderá mais ser alterado: correções viram uma nova "
                "versão e a anterior fica guardada.\n\nA folha do paciente já foi conferida e entregue?", parent=self):
            return
        if self._tentar(self.sessao.marcar_entregue):
            self._msg("Documento marcado como entregue.")
            self._atualizar()

    def _nova_versao(self):
        if self._tentar(self.sessao.nova_versao):
            self._msg("Nova versão criada a partir da entregue. A versão anterior continua guardada.", LARANJA)
            self._atualizar()

    def _salvar_cabecalho_se_mudou(self):
        """Ao fechar, guarda nome, CRN e recado se foram alterados (sem criar documento à toa)."""
        nome, crn, recado = self._cabecalho_digitado()
        atual = self.sessao.cabecalho()
        if (nome, crn, ca.normalizar_texto(recado)) != (atual["nutricionista"], atual["crn"], atual["recado"]):
            self.sessao.salvar_cabecalho(nome, crn, recado)

    def _fechar(self):
        if not self.sessao.entregue:
            nao_salvas = self._tem_edicoes_nao_salvas()
            if nao_salvas and not messagebox.askyesno(
                    "Fechar", "Há textos corrigidos que não foram confirmados (" + ", ".join(nao_salvas)
                    + "). Se fechar agora, essas correções se perdem.\n\nFechar mesmo assim?", parent=self):
                return
            self._tentar(self._salvar_cabecalho_se_mudou)
        if self.ao_fechar:
            self.ao_fechar()
        self.destroy()
