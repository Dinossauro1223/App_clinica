# -*- coding: utf-8 -*-
"""Testes das telas das condutas de alta (condutas_alta_ui) e da ligação com o Mapa, com widgets simulados.

Não abre janelas: usa os widgets falsos de tests/test_ui_smoke.py. Percorre os fluxos (confirmar, corrigir o texto,
"não se aplica", exportar, imprimir, entregar, nova versão, aviso depois da evolução, Mapa). NÃO valida a aparência
real, a impressora nem o PDF real (o layout do PDF é testado em test_condutas_alta_export.py). Dados sintéticos.

    python -m unittest tests.test_condutas_alta_ui -v
"""
import os
import re
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))


def _modulo_base():
    """Reaproveita o test_ui_smoke já importado (qualquer nome) para haver uma só instalação de widgets falsos."""
    for nome in ("test_ui_smoke", "tests.test_ui_smoke"):
        if nome in sys.modules:
            return sys.modules[nome]
    import test_ui_smoke
    return test_ui_smoke


BASE = _modulo_base()
AppFalso, Frame = BASE.AppFalso, BASE.Frame

import condutas_alta as ca  # noqa: E402
import condutas_alta_export as ex  # noqa: E402
import condutas_alta_ui as cui  # noqa: E402
import mapa_db as mdb  # noqa: E402
import mapa_ui  # noqa: E402
from fake_fpdf import FakePDF  # noqa: E402
from test_condutas_alta import grupo_teste, novo_banco, pasta_catalogo_teste, registrar  # noqa: E402

AGORA = datetime(2026, 11, 15, 10, 0, 0)
DATA = date(2026, 11, 15)
CARREGAR_CATALOGO_REAL = ca.carregar_catalogo           # guardado antes de qualquer patch
NOVA_PDF_REAL = ex._nova_pdf


# ------------------------------------------------------------------------------------------ ajudantes
def todos(raiz):
    """Todos os widgets abaixo de `raiz` que não foram destruídos."""
    for w in raiz.winfo_children():
        yield w
        yield from todos(w)


def textos(raiz):
    return [w.opts["text"] for w in todos(raiz) if w.opts.get("text")]


def achar(raiz, texto):
    for w in todos(raiz):
        if w.opts.get("text") == texto:
            return w
    raise AssertionError(f"widget com o texto {texto!r} não encontrado")


def clicar(raiz, texto):
    achar(raiz, texto).opts["command"]()


def cartao(janela, cod):
    for q in janela.corpo.winfo_children():
        if any(t.startswith(f"[{cod}]") for t in textos(q)):
            return q
    raise AssertionError(f"cartão {cod} não encontrado")


def digitar(textbox, texto):
    textbox.delete("1.0", "end")
    textbox.insert("1.0", texto)


class Base(unittest.TestCase):
    """Paciente sintético enteral + diabetes + doença renal + tuberculose: o catálogo de teste sugere TST-01..03."""

    def setUp(self):
        self.db = novo_banco()
        self.pasta_cat = pasta_catalogo_teste(grupo_teste())
        self.cat = ca.carregar_catalogo(self.pasta_cat)
        for patcher in (mock.patch.object(ca, "carregar_catalogo", return_value=self.cat),
                        mock.patch.object(ex, "_nova_pdf", lambda fabrica=None: NOVA_PDF_REAL(FakePDF)),
                        mock.patch.object(os, "startfile", create=True)):     # nunca abre programa de verdade
            patcher.start()
            self.addCleanup(patcher.stop)
        self.reg = registrar(self.db, nome="Paciente Sintético", via="Enteral", dm=1, drc=1, condicoes="tb")
        self.saida = tempfile.mkdtemp(prefix="nutrilab_ui_")
        self.app = AppFalso()
        self.caixas = list({id(c): c for c in (mapa_ui.messagebox, cui.messagebox)}.values())
        for c in self.caixas:
            c.chamadas.clear()
            c.resposta = True
        cui.filedialog.destino = ""
        self.addCleanup(self._limpar)

    def _limpar(self):
        for c in self.caixas:
            c.resposta = True
        cui.filedialog.destino = ""
        os.remove(self.db)
        shutil.rmtree(self.pasta_cat, ignore_errors=True)
        shutil.rmtree(self.saida, ignore_errors=True)

    def sessao(self, **kw):
        return ca.SessaoCondutasAlta(self.db, self.reg["id_paciente"], catalogo=self.cat, agora=AGORA, **kw)

    def janela(self, pasta_saida=None, ao_fechar=None):
        return cui.JanelaCondutasAlta(self.app, self.sessao(), pasta_saida, ao_fechar)

    def painel(self):
        return cui.PainelCondutasAlta(Frame(), self.db, self.reg["id_paciente"], "Paciente Sintético",
                                      janela_pai=self.app)

    def chamadas(self, nome, caixa=None):
        return [c for c in (caixa or cui.messagebox).chamadas if c[0] == nome]

    def decidir_tudo(self, j):
        clicar(cartao(j, "TST-01"), "Confirmar com este texto")
        clicar(cartao(j, "TST-02"), "Confirmar com este texto")
        j._motivos["TST-03"].insert(0, "Sem doença respiratória ativa")
        clicar(cartao(j, "TST-03"), "Não se aplica")


# ----------------------------------------------------------------------------------------------- textos
class TestTextos(Base):
    def test_status_pendente_decidido_e_entregue(self):
        s = self.sessao()
        msg, cor = cui.texto_status(s)
        self.assertIn("3 condutas de alta pendentes", msg)
        self.assertEqual(cor, cui.LARANJA)
        s.nao_se_aplica("TST-01", "teste")
        s.nao_se_aplica("TST-02", "teste")
        self.assertIn("1 conduta de alta pendente:", cui.texto_status(s)[0])
        s.confirmar("TST-03")
        self.assertIn("Todas as condutas de alta já foram decididas", cui.texto_status(s)[0])
        s.salvar_cabecalho("Nutri Teste", "", "")
        s.marcar_entregue()
        self.assertIn("entregue em 15/11/2026", cui.texto_status(s)[0])

    def test_sem_nenhuma_sugestao(self):
        outro = registrar(self.db, nome="Sem Doença", leito="L02", via="Oral")
        s = ca.SessaoCondutasAlta(self.db, outro["id_paciente"], catalogo=self.cat, agora=AGORA)
        self.assertIn("Nenhuma conduta sugerida", cui.texto_status(s)[0])

    def test_etiqueta_e_texto_tecnico(self):
        s = self.sessao()
        s.confirmar("TST-01", texto_paciente="- Dieta corrigida.")
        c = {x["codigo"]: x for x in s.cartoes()}
        self.assertEqual(cui.etiqueta_estado(c["TST-01"]), "CONFIRMADA  |  texto editado")
        self.assertEqual(cui.etiqueta_estado(c["TST-02"]), "PENDENTE")
        tec = cui.texto_tecnico(c["TST-01"])
        for trecho in ("TEXTO TÉCNICO (nutricionista)", "Texto profissional 1.", "CONFERIR ANTES DE CONFIRMAR",
                       "- Conferir 1", "REFERÊNCIAS", "AUTOR, A."):
            self.assertIn(trecho, tec)
        self.assertNotIn("CONFERIR", cui.texto_tecnico(c["TST-02"]))


# ------------------------------------------------------------------------------------------------ painel
class TestPainel(Base):
    def test_mostra_doencas_e_pendencias(self):
        p = self.painel()
        self.assertIn("Via enteral, Diabetes mellitus, Doença renal, Tuberculose", p.lbl_doencas.opts["text"])
        self.assertIn("3 condutas de alta pendentes", p.lbl_status.opts["text"])
        self.assertEqual(p.pendencias(), 3)

    def test_depois_de_decidir_tudo(self):
        s = self.sessao()
        for cod in ("TST-01", "TST-02", "TST-03"):
            s.nao_se_aplica(cod, "teste")
        p = self.painel()
        self.assertEqual(p.pendencias(), 0)
        self.assertIn("já foram decididas", p.lbl_status.opts["text"])

    def test_paciente_sem_registro_no_mapa(self):
        p = cui.PainelCondutasAlta(Frame(), self.db, 999, "Ninguém", janela_pai=self.app)
        self.assertIn("nenhuma", p.lbl_doencas.opts["text"])
        self.assertEqual(p.pendencias(), 0)

    def test_modulo_indisponivel_nao_quebra_a_consulta(self):
        fd, sem_migracao = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            mdb.inicializar(sem_migracao)
            p = cui.PainelCondutasAlta(Frame(), sem_migracao, 1, "X", janela_pai=self.app)
            self.assertIn("indisponíveis", p.lbl_status.opts["text"])
            self.assertEqual(p.lbl_status.opts["text_color"], cui.VERMELHO)
            self.assertEqual(p.pendencias(), 0)
        finally:
            os.remove(sem_migracao)

    def test_botao_abre_a_janela_e_o_painel_se_atualiza_ao_fechar(self):
        p = self.painel()
        j = achar(p, "Abrir condutas de alta").opts["command"]()
        self.assertIsInstance(j, cui.JanelaCondutasAlta)
        clicar(cartao(j, "TST-01"), "Confirmar com este texto")
        j._fechar()
        self.assertIn("2 condutas de alta pendentes", p.lbl_status.opts["text"])

    def test_abrir_sem_migracao_explica_e_nao_abre_janela(self):
        fd, sem_migracao = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            mdb.inicializar(sem_migracao)
            self.assertIsNone(cui.abrir_condutas_alta(self.app, sem_migracao, 1, "X"))
        finally:
            os.remove(sem_migracao)
        self.assertTrue(any("migração 2" in c[2] for c in self.chamadas("showerror")))


# ------------------------------------------------------------------------------------------------ janela
class TestJanela(Base):
    def test_um_cartao_por_conduta_sugerida(self):
        j = self.janela()
        titulos = [t for q in j.corpo.winfo_children() for t in textos(q) if t.startswith("[")]
        self.assertEqual(titulos, ["[TST-01] Enteral", "[TST-02] Renal com diabetes", "[TST-03] Respiratória ou TB"])
        self.assertIn("3 condutas de alta pendentes", j.lbl_status.opts["text"])
        self.assertIn("Cada conduta abaixo é uma sugestão", j.lbl_doencas.opts["text"])
        self.assertEqual(j._textos["TST-01"].get("1.0", "end-1c"), "- Dieta: ______\n- Lave as mãos.")
        self.assertTrue(any(t.startswith("1 campo em branco (____)") for t in textos(cartao(j, "TST-01"))))
        self.assertIn("nenhuma conduta confirmada", j.lbl_paginas.opts["text"])

    def test_texto_tecnico_abre_e_fecha_e_continua_aberto_depois_de_redesenhar(self):
        j = self.janela()
        q = cartao(j, "TST-02")
        det = next(w for w in todos(q) if "TEXTO TÉCNICO" in (w.opts.get("text") or "")).master
        self.assertFalse(det.packed)
        clicar(q, "Ver texto técnico, conferência e fontes")
        self.assertTrue(det.packed)
        self.assertIn("TST-02", j._abertos)
        clicar(cartao(j, "TST-01"), "Confirmar com este texto")          # redesenha tudo
        q = cartao(j, "TST-02")
        det = next(w for w in todos(q) if "TEXTO TÉCNICO" in (w.opts.get("text") or "")).master
        self.assertTrue(det.packed)
        clicar(q, "Ocultar texto técnico")
        self.assertFalse(det.packed)

    def test_confirmar_com_texto_corrigido(self):
        j = self.janela()
        digitar(j._textos["TST-01"], "- Dieta: 1500 mL em 6 horários.\n- Lave as mãos.")
        clicar(cartao(j, "TST-01"), "Confirmar com este texto")
        item = self.sessao().itens["TST-01"]
        self.assertEqual((item["decisao"], item["editado"]), ("confirmada", 1))
        self.assertEqual(item["texto_paciente"], "- Dieta: 1500 mL em 6 horários.\n- Lave as mãos.")
        self.assertIn("CONFIRMADA  |  texto editado", textos(cartao(j, "TST-01")))
        self.assertEqual(j.lbl_msg.opts["text"], "TST-01 confirmada.")
        self.assertIn("2 condutas de alta pendentes", j.lbl_status.opts["text"])
        self.assertIn("1 página", j.lbl_paginas.opts["text"])

    def test_nao_se_aplica_pede_motivo(self):
        j = self.janela()
        clicar(cartao(j, "TST-03"), "Não se aplica")                         # sem motivo
        self.assertEqual(len(self.chamadas("showwarning")), 1)
        self.assertEqual(self.sessao().itens, {})
        j._motivos["TST-03"].insert(0, "Sem doença respiratória ativa")
        clicar(cartao(j, "TST-03"), "Não se aplica")
        self.assertEqual(self.sessao().itens["TST-03"]["decisao"], "nao_se_aplica")
        self.assertIn("Motivo: Sem doença respiratória ativa", textos(cartao(j, "TST-03")))
        self.assertNotIn("TST-03", j._textos)                                # "não se aplica" não tem texto do paciente

    def test_corrigir_depois_de_confirmar_mantem_o_texto_tecnico(self):
        j = self.janela()
        clicar(cartao(j, "TST-01"), "Confirmar com este texto")
        digitar(j._textos["TST-01"], "- Texto corrigido depois.")
        clicar(cartao(j, "TST-01"), "Salvar correção do texto")
        item = self.sessao().itens["TST-01"]
        self.assertEqual((item["texto_paciente"], item["editado"]), ("- Texto corrigido depois.", 1))
        self.assertEqual(item["texto_profissional"], "Texto profissional 1.")
        self.assertEqual(j.lbl_msg.opts["text"], "Correção do texto de TST-01 salva.")

    def test_voltar_para_pendente(self):
        j = self.janela()
        clicar(cartao(j, "TST-01"), "Confirmar com este texto")
        clicar(cartao(j, "TST-01"), "Voltar para pendente")
        self.assertEqual(self.sessao().itens, {})
        self.assertIn("PENDENTE", textos(cartao(j, "TST-01")))

    def test_texto_digitado_nao_se_perde_ao_redesenhar(self):
        j = self.janela()
        digitar(j._textos["TST-02"], "- Rascunho da nutricionista.")
        clicar(cartao(j, "TST-01"), "Confirmar com este texto")
        self.assertEqual(j._textos["TST-02"].get("1.0", "end-1c"), "- Rascunho da nutricionista.")
        self.assertEqual(j._tem_edicoes_nao_salvas(), ["TST-02"])
        self.assertEqual(self.sessao().itens["TST-01"]["decisao"], "confirmada")     # e nada foi gravado sem confirmar
        self.assertNotIn("TST-02", self.sessao().itens)

    def test_adicionar_conduta_do_catalogo(self):
        j = self.janela()
        self.assertIn("TST-04  Só manual", j._opcoes)
        j.cb_catalogo.set("TST-04  Só manual")
        j._adicionar_manual()
        self.assertIn("PENDENTE  |  adicionada por você", textos(cartao(j, "TST-04")))
        self.assertNotIn("TST-04  Só manual", j._opcoes)
        j.cb_catalogo.set("")
        j._adicionar_manual()
        self.assertEqual(len(self.chamadas("showinfo")), 1)

    def test_catalogo_real_abre_com_um_cartao_por_pendencia(self):
        real = ca.SessaoCondutasAlta(self.db, self.reg["id_paciente"], catalogo=CARREGAR_CATALOGO_REAL(), agora=AGORA)
        j = cui.JanelaCondutasAlta(self.app, real)
        codigos = [t[1:t.index("]")] for q in j.corpo.winfo_children() for t in textos(q) if t.startswith("[")]
        self.assertEqual(codigos, [c["codigo"] for c in real.cartoes()])
        self.assertGreaterEqual(len(codigos), 9)
        self.assertEqual(set(j._textos), set(codigos))
        for texto in j._textos.values():
            self.assertTrue(texto.get("1.0", "end-1c").strip())


class TestSaida(Base):
    def setUp(self):
        super().setUp()
        self.destino = os.path.join(self.saida, "folha.pdf")

    def test_pdf_do_paciente_leva_so_o_confirmado_e_avisa_do_que_ficou_de_fora(self):
        j = self.janela()
        clicar(cartao(j, "TST-01"), "Confirmar com este texto")
        cui.filedialog.destino = self.destino
        j._exportar("paciente")
        self.assertGreater(os.path.getsize(self.destino), 0)
        aviso = [c for c in self.chamadas("askyesno") if c[1] == "Gerar a folha assim mesmo?"]
        self.assertEqual(len(aviso), 1)
        self.assertIn("TST-02", aviso[0][2])
        self.assertIn("TST-03", aviso[0][2])
        self.assertIn("PDF salvo (1 página)", j.lbl_msg.opts["text"])
        os.startfile.assert_called_once_with(self.destino)

    def test_aviso_cancelado_nao_gera_arquivo(self):
        j = self.janela()
        clicar(cartao(j, "TST-01"), "Confirmar com este texto")
        cui.filedialog.destino = self.destino
        cui.messagebox.resposta = False
        j._exportar("paciente")
        self.assertFalse(os.path.exists(self.destino))

    def test_texto_corrigido_e_nao_confirmado_tambem_e_avisado(self):
        j = self.janela()
        self.decidir_tudo(j)
        digitar(j._textos["TST-01"], "- Mudança que ninguém confirmou.")
        cui.filedialog.destino = self.destino
        j._exportar("paciente")
        aviso = [c for c in self.chamadas("askyesno") if c[1] == "Gerar a folha assim mesmo?"]
        self.assertEqual(len(aviso), 1)
        self.assertIn("NÃO foram confirmados", aviso[0][2])
        self.assertIn("TST-01", aviso[0][2])

    def test_sem_conduta_confirmada_nao_gera_folha(self):
        j = self.janela()
        cui.filedialog.destino = self.destino
        j._exportar("paciente")
        self.assertEqual(len(self.chamadas("showinfo")), 1)
        self.assertFalse(os.path.exists(self.destino))

    def test_pdf_completo_do_nutricionista_nao_exige_confirmacao(self):
        j = self.janela()
        cui.filedialog.destino = self.destino
        j._exportar("profissional")
        self.assertGreater(os.path.getsize(self.destino), 0)

    def test_escolha_de_arquivo_cancelada(self):
        j = self.janela()
        clicar(cartao(j, "TST-01"), "Confirmar com este texto")
        cui.filedialog.destino = ""
        j._exportar("profissional")
        self.assertEqual(os.listdir(self.saida), [])

    def test_biblioteca_pdf_ausente_avisa_como_instalar(self):
        j = self.janela()
        clicar(cartao(j, "TST-01"), "Confirmar com este texto")
        cui.filedialog.destino = self.destino
        with mock.patch.object(ex, "_nova_pdf", side_effect=ImportError("No module named 'fpdf'")):
            j._exportar("paciente")
        self.assertTrue(any("pip install fpdf2" in c[2] for c in self.chamadas("showerror")))
        self.assertFalse(os.path.exists(self.destino))

    def test_imprimir_grava_o_pdf_na_pasta_e_manda_para_a_impressora(self):
        j = self.janela(pasta_saida=os.path.join(self.saida, "paciente_1"))
        clicar(cartao(j, "TST-01"), "Confirmar com este texto")
        with mock.patch.object(ex, "imprimir_pdf",
                               return_value=("impresso", "Enviado para a impressora padrão do computador.")) as imp:
            j._imprimir()
        caminho = imp.call_args[0][0]
        self.assertTrue(os.path.exists(caminho))
        self.assertEqual(os.path.dirname(caminho), os.path.join(self.saida, "paciente_1"))
        self.assertEqual(os.path.basename(caminho), "Orientacoes_de_alta_Paciente_Sintetico_2026-11-15.pdf")
        self.assertIn("Enviado para a impressora", j.lbl_msg.opts["text"])
        self.assertEqual(j.lbl_msg.opts["text_color"], cui.VERDE_ESC)

    def test_falha_de_impressao_aparece_em_vermelho_e_o_pdf_fica_salvo(self):
        j = self.janela(pasta_saida=self.saida)
        clicar(cartao(j, "TST-01"), "Confirmar com este texto")
        with mock.patch.object(ex, "imprimir_pdf", return_value=("erro", "Nenhum programa de impressão foi encontrado.")):
            j._imprimir()
        self.assertEqual(j.lbl_msg.opts["text_color"], cui.VERMELHO)
        self.assertIn("Cópia em PDF", j.lbl_msg.opts["text"])
        self.assertTrue(any(n.endswith(".pdf") for n in os.listdir(self.saida)))

    def test_imprimir_sem_confirmada_nao_imprime(self):
        j = self.janela(pasta_saida=self.saida)
        with mock.patch.object(ex, "imprimir_pdf") as imp:
            j._imprimir()
        imp.assert_not_called()


class TestEntrega(Base):
    def test_entregar_exige_o_nome_da_nutricionista(self):
        j = self.janela()
        self.decidir_tudo(j)
        j._entregar()
        self.assertTrue(any("nome da nutricionista" in c[2] for c in self.chamadas("showwarning")))
        self.assertFalse(j.sessao.entregue)

    def test_entrega_cancelada_na_pergunta(self):
        j = self.janela()
        self.decidir_tudo(j)
        j.e_nutri.insert(0, "Nutri Teste")
        cui.messagebox.resposta = False
        j._entregar()
        self.assertFalse(j.sessao.entregue)

    def test_texto_corrigido_e_nao_confirmado_bloqueia_a_entrega(self):
        j = self.janela()
        self.decidir_tudo(j)
        j.e_nutri.insert(0, "Nutri Teste")
        digitar(j._textos["TST-01"], "- Mudança não confirmada.")
        j._entregar()
        self.assertTrue(any("ainda não foram confirmados" in c[2] for c in self.chamadas("showwarning")))
        self.assertFalse(j.sessao.entregue)

    def test_fluxo_de_entrega_trava_a_tela_e_nova_versao_destrava(self):
        j = self.janela()
        self.decidir_tudo(j)
        j.e_nutri.insert(0, "Nutri Teste")
        j.e_crn.insert(0, "CRN-6 0000")
        j._entregar()
        self.assertTrue(j.sessao.entregue)
        self.assertIn("entregue em 15/11/2026", j.lbl_status.opts["text"])
        self.assertFalse(j.b_entregue.packed)
        self.assertTrue(j.b_nova.packed)
        self.assertEqual(j.b_add.opts["state"], "disabled")
        self.assertEqual(j._textos["TST-01"].opts["state"], "disabled")
        self.assertEqual(j.e_nutri.opts["state"], "disabled")
        for rotulo in ("Confirmar com este texto", "Salvar correção do texto", "Voltar para pendente", "Não se aplica"):
            for cod in ("TST-01", "TST-02", "TST-03"):
                self.assertNotIn(rotulo, textos(cartao(j, cod)))
        j._nova_versao()
        self.assertFalse(j.sessao.entregue)
        self.assertTrue(j.b_entregue.packed)
        self.assertFalse(j.b_nova.packed)
        self.assertEqual(j.b_add.opts["state"], "normal")
        self.assertIn("Salvar correção do texto", textos(cartao(j, "TST-01")))
        self.assertEqual([d["status"] for d in ca.listar_documentos(self.db, self.reg["id_paciente"])],
                         ["rascunho", "entregue"])

    def test_fechar_com_texto_nao_confirmado_pergunta_e_nao_grava(self):
        fechou = []
        j = self.janela(ao_fechar=lambda: fechou.append(1))
        digitar(j._textos["TST-01"], "- mudei")
        cui.messagebox.resposta = False
        j._fechar()
        self.assertEqual(fechou, [])
        self.assertFalse(j.destroyed)
        cui.messagebox.resposta = True
        j._fechar()
        self.assertEqual(fechou, [1])
        self.assertTrue(j.destroyed)
        self.assertEqual(self.sessao().itens, {})

    def test_fechar_guarda_nome_e_crn_como_padrao_da_proxima_folha(self):
        j = self.janela()
        j.e_nutri.insert(0, "Nutri Teste")
        j.e_crn.insert(0, "CRN-6 0000")
        j._fechar()
        outro = registrar(self.db, nome="Outra Pessoa", leito="L02", via="Enteral")
        s = ca.SessaoCondutasAlta(self.db, outro["id_paciente"], catalogo=self.cat, agora=AGORA)
        self.assertEqual((s.cabecalho()["nutricionista"], s.cabecalho()["crn"]), ("Nutri Teste", "CRN-6 0000"))

    def test_fechar_sem_mudar_nada_nao_cria_documento(self):
        j = self.janela()
        j._fechar()
        self.assertIsNone(ca.documento_atual(self.db, self.reg["id_paciente"]))


class TestLembrete(Base):
    def test_depois_de_salvar_a_evolucao_lembra_e_oferece_abrir(self):
        p = self.painel()
        rotulo = cui.ctk.CTkLabel(Frame(), text="Evolução salva com sucesso!")
        with mock.patch.object(p, "abrir") as abrir:
            n = cui.lembrar_condutas_pendentes(p, rotulo)
        self.assertEqual(n, 3)
        self.assertIn("Evolução salva com sucesso!", rotulo.opts["text"])
        self.assertIn("3 condutas de alta aguardando confirmação", rotulo.opts["text"])
        self.assertEqual(rotulo.opts["text_color"], cui.LARANJA)
        self.assertEqual(len(self.chamadas("askyesno")), 1)
        abrir.assert_called_once_with()

    def test_se_a_nutricionista_recusar_nao_abre(self):
        p = self.painel()
        cui.messagebox.resposta = False
        with mock.patch.object(p, "abrir") as abrir:
            self.assertEqual(cui.lembrar_condutas_pendentes(p), 3)
        abrir.assert_not_called()

    def test_sem_pendencias_fica_quieto(self):
        s = self.sessao()
        for cod in ("TST-01", "TST-02", "TST-03"):
            s.nao_se_aplica(cod, "teste")
        p = self.painel()
        rotulo = cui.ctk.CTkLabel(Frame(), text="Evolução salva com sucesso!")
        self.assertEqual(cui.lembrar_condutas_pendentes(p, rotulo), 0)
        self.assertEqual(rotulo.opts["text"], "Evolução salva com sucesso!")
        self.assertEqual(self.chamadas("askyesno"), [])

    def test_sem_painel(self):
        self.assertEqual(cui.lembrar_condutas_pendentes(None), 0)


# ------------------------------------------------------------------------------------------------- Mapa
class TestMapa(Base):
    def setUp(self):
        super().setUp()
        self.ui = mapa_ui.MapaUI(self.app, self.db, os.path.dirname(self.db))
        self.ui.data = DATA
        self.iid = str(self.reg["id_leito"])

    def caixa_mapa(self, nome):
        return self.chamadas(nome, mapa_ui.messagebox)

    def test_coluna_e_aviso_de_pendencias(self):
        self.ui.mostrar_mapa()
        self.assertEqual(self.ui.tree.items[self.iid][-1], "3 pendentes")
        self.assertEqual(self.ui.tree.tags[self.iid], ("condpend",))
        self.assertIn("1 paciente com condutas de alta pendentes", self.ui.lbl_condutas.opts["text"])
        self.assertEqual(self.ui.lbl_condutas.opts["text_color"], mapa_ui.LARANJA)
        s = self.sessao()
        for cod in ("TST-01", "TST-02", "TST-03"):
            s.nao_se_aplica(cod, "teste")
        self.ui._recarregar()
        self.assertEqual(self.ui.tree.items[self.iid][-1], "Decididas")
        self.assertEqual(self.ui.tree.tags[self.iid], ())
        self.assertEqual(self.ui.lbl_condutas.opts["text"], "")

    def test_catalogo_invalido_nao_derruba_o_mapa(self):
        with mock.patch.object(ca, "carregar_catalogo", side_effect=ca.ErroCatalogo(["g.json: erro de teste"])):
            self.ui.mostrar_mapa()
        self.assertEqual(len(self.ui.tree.items), 1)
        self.assertEqual(self.ui.tree.items[self.iid][-1], "")
        self.assertIn("Condutas de alta indisponíveis", self.ui.lbl_condutas.opts["text"])
        self.assertIn("erro de teste", self.ui.lbl_condutas.opts["text"])
        self.assertEqual(self.ui.lbl_condutas.opts["text_color"], mapa_ui.VERMELHO)

    def test_banco_sem_a_migracao_nao_derruba_o_mapa(self):
        fd, sem_migracao = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            mdb.inicializar(sem_migracao)
            registrar(sem_migracao, nome="Sem Migração", via="Enteral")
            ui = mapa_ui.MapaUI(self.app, sem_migracao, os.path.dirname(sem_migracao))
            ui.data = DATA
            ui.mostrar_mapa()
            self.assertEqual(len(ui.tree.items), 1)
            self.assertIn("migração 2", ui.lbl_condutas.opts["text"])
            self.assertEqual(ui.lbl_condutas.opts["text_color"], mapa_ui.VERMELHO)
        finally:
            os.remove(sem_migracao)

    def test_botao_abre_as_condutas_do_paciente_selecionado(self):
        self.ui.mostrar_mapa()
        self.ui._condutas_alta()                                              # nada selecionado
        self.assertEqual(len(self.caixa_mapa("showinfo")), 1)
        self.ui.tree.selection_set(self.iid)
        self.app.pasta_condutas_alta = lambda id_paciente: f"/pasta/paciente_{id_paciente}"
        with mock.patch.object(cui, "abrir_condutas_alta") as abrir:
            self.ui._condutas_alta()
        args, kw = abrir.call_args
        self.assertEqual(args, (self.app, self.db, self.reg["id_paciente"], "Paciente Sintético",
                                f"/pasta/paciente_{self.reg['id_paciente']}"))
        self.assertEqual(kw["ao_fechar"], self.ui._recarregar)

    def test_remover_do_mapa_com_condutas_pendentes_pergunta_antes(self):
        self.ui.mostrar_mapa()
        self.ui.tree.selection_set(self.iid)
        caixa = mapa_ui.messagebox
        with mock.patch.object(caixa, "askyesnocancel", return_value=None) as pergunta:
            self.ui._remover()                                                # Cancelar
        pergunta.assert_called_once()
        self.assertIn("3 condutas de alta", pergunta.call_args[0][1])
        self.assertTrue(mdb.obter_registro(self.db, DATA.isoformat(), self.reg["id_leito"]))
        with mock.patch.object(caixa, "askyesnocancel", return_value=True), \
                mock.patch.object(self.ui, "_abrir_condutas") as abrir:
            self.ui._remover()                                                # Sim: abre as condutas
        abrir.assert_called_once()
        self.assertTrue(mdb.obter_registro(self.db, DATA.isoformat(), self.reg["id_leito"]))
        with mock.patch.object(caixa, "askyesnocancel", return_value=False):
            self.ui._remover()                                                # Não: remove mesmo assim
        self.assertFalse(mdb.obter_registro(self.db, DATA.isoformat(), self.reg["id_leito"]))

    def test_remover_sem_pendencia_nao_pergunta_das_condutas(self):
        outro = registrar(self.db, nome="Sem Doença", leito="L02", via="Oral")
        self.ui.mostrar_mapa()
        self.ui.tree.selection_set(str(outro["id_leito"]))
        self.ui._remover()
        self.assertEqual(self.caixa_mapa("askyesnocancel"), [])
        self.assertFalse(mdb.obter_registro(self.db, DATA.isoformat(), outro["id_leito"]))

    def test_formulario_grava_e_reabre_as_doencas_relatadas(self):
        id_setor = mdb.listar_setores(self.db)[0]["id_setor"]
        id_leito = mdb.criar_leito(self.db, id_setor, "L05")
        self.ui.mostrar_mapa()
        item = next(l for l in self.ui.linhas if l["leito"]["id_leito"] == id_leito)
        form = mapa_ui.FormRegistro(self.ui, item)
        self.assertEqual({c: v.get() for c, v in form.var_cond.items()}, {"resp": 0, "tb": 0})
        form.e_nome.insert(0, "Fulana Sintética")
        form.seg_acomp.set("Não")
        form.e_idade.insert(0, "70")
        form.seg_sexo.set("Mulher")
        form.var_cond["resp"].set(1)
        form.var_cond["tb"].set(1)
        form._salvar()
        self.assertEqual(mdb.obter_registro(self.db, DATA.isoformat(), id_leito)["condicoes"], "resp,tb")
        self.ui._recarregar()
        item = next(l for l in self.ui.linhas if l["leito"]["id_leito"] == id_leito)
        form2 = mapa_ui.FormRegistro(self.ui, item)
        self.assertEqual({c: v.get() for c, v in form2.var_cond.items()}, {"resp": 1, "tb": 1})
        form2.var_cond["tb"].set(0)
        form2._salvar()
        self.assertEqual(mdb.obter_registro(self.db, DATA.isoformat(), id_leito)["condicoes"], "resp")
        self.assertEqual(self.ui.tree.items[str(id_leito)][-1], "1 pendente")        # a doença relatada já gera a sugestão


# --------------------------------------------------------------------------------------- ligação no main.py
RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class TestLigacaoNoMain(unittest.TestCase):
    """main.py não pode ser importado sem as bibliotecas gráficas: a ligação é conferida pelo código-fonte."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RAIZ, "main.py"), encoding="utf-8") as f:
            cls.texto = f.read()

    def corpo(self, metodo):
        """Texto do método `metodo` (até o próximo método da classe)."""
        ini = self.texto.index(f"    def {metodo}(")
        fim = re.search(r"\n    def \w+\(", self.texto[ini + 10:])
        return self.texto[ini: ini + 10 + fim.start()] if fim else self.texto[ini:]

    def test_painel_fica_na_parte_clinica_da_consulta_logo_depois_da_conduta(self):
        corpo = self.corpo("tela_consultas")
        a = corpo.index("self.txt_conduta = ")
        b = corpo.index("PainelCondutasAlta(")
        c = corpo.index('text="Solicitação de Exames"')
        self.assertLess(a, b)
        self.assertLess(b, c)
        self.assertIn("caminho_do_banco()", corpo[b:c])
        self.assertIn("self.paciente_atual_id", corpo[b:c])
        self.assertIn("self.pasta_condutas_alta()", corpo[b:c])

    def test_salvar_evolucao_lembra_as_condutas_depois_de_gravar(self):
        corpo = self.corpo("salvar_consulta")
        self.assertLess(corpo.index("conexao.commit()"), corpo.index("lembrar_condutas_pendentes("))
        self.assertIn("self.lbl_msg_consulta", corpo[corpo.index("lembrar_condutas_pendentes("):])

    def test_pasta_da_folha_fica_com_os_arquivos_do_paciente_fora_do_bundle(self):
        corpo = self.corpo("pasta_condutas_alta")
        self.assertIn('get_writable_path("arquivos_pacientes")', corpo)
        self.assertIn('f"paciente_{id_paciente}"', corpo)

    def test_importa_o_que_usa(self):
        self.assertIn("from condutas_alta_ui import PainelCondutasAlta, lembrar_condutas_pendentes", self.texto)


if __name__ == "__main__":
    unittest.main()
