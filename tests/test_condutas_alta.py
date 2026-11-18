# -*- coding: utf-8 -*-
"""Testes do núcleo das condutas de alta (catálogo, regras pelo Mapa, banco, sessão). Dados 100% sintéticos.

    python -m unittest tests.test_condutas_alta -v
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import condutas_alta as ca  # noqa: E402
import db_migracoes  # noqa: E402
import mapa_db as mdb  # noqa: E402

AGORA = datetime(2026, 11, 15, 10, 0, 0)
REF = "AUTOR, A. Título de teste. Editora, 2026. Disponível em: https://exemplo.org/a. Acesso em: 15 nov. 2026."


def grupo_teste(**mudar):
    base = {
        "grupo": "teste", "titulo": "Grupo de teste", "versao": "t.1", "revisado_em": "2026-11-15",
        "referencias": {"R1": REF},
        "condutas": [
            {"codigo": "TST-01", "titulo": "Enteral", "titulo_paciente": "Sua dieta",
             "gatilhos": {"qualquer": ["via:Enteral"]}, "profissional": ["Texto profissional 1."],
             "conferir": ["Conferir 1"], "paciente": ["- Dieta: ______", "- Lave as mãos."], "fontes": ["R1"]},
            {"codigo": "TST-02", "titulo": "Renal com diabetes", "gatilhos": {"todas": ["drc", "dm"]},
             "profissional": ["Texto profissional 2."], "paciente": ["- Item renal."], "fontes": ["R1"]},
            {"codigo": "TST-03", "titulo": "Respiratória ou TB",
             "gatilhos": {"qualquer": ["cond:resp", "cond:tb"]}, "profissional": "Texto 3.",
             "paciente": "- Item respiratório.", "fontes": ["R1"]},
            {"codigo": "TST-04", "titulo": "Só manual", "profissional": ["Texto 4."],
             "paciente": ["- Item manual."], "fontes": ["R1"]},
        ]}
    base.update(mudar)
    return base


def pasta_catalogo_teste(*grupos):
    pasta = tempfile.mkdtemp(prefix="nutrilab_cat_")
    for i, g in enumerate(grupos):
        with open(os.path.join(pasta, f"g{i}.json"), "w", encoding="utf-8") as f:
            json.dump(g, f, ensure_ascii=False)
    return pasta


def novo_banco():
    fd, caminho = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    mdb.inicializar(caminho)                                   # Pacientes e Mapa_*
    db_migracoes.aplicar_migracoes(caminho, backup=False)      # baseline adotada + v2 (condutas de alta)
    return caminho


def registrar(db, nome="Paciente Sintético", leito="L01", data="2026-11-15", **extra):
    id_leito = next((l["id_leito"] for l in mdb.listar_leitos(db) if l["codigo"] == leito), None)
    if id_leito is None:
        id_leito = mdb.criar_leito(db, mdb.listar_setores(db)[0]["id_setor"], leito)
    reg = dict(data=data, id_leito=id_leito, nome_paciente=nome, sexo="M", idade_anos=70, via="Oral",
               peso_kg=50.0, altura_cm=155.0, suplementos=[])
    reg.update(extra)
    mdb.salvar_registro(db, reg)
    return mdb.obter_registro(db, data, id_leito)


class Base(unittest.TestCase):
    def setUp(self):
        self.db = novo_banco()
        self.pasta = pasta_catalogo_teste(grupo_teste())
        self.cat = ca.carregar_catalogo(self.pasta)

    def tearDown(self):
        os.remove(self.db)
        shutil.rmtree(self.pasta, ignore_errors=True)

    def sessao(self, reg, **kw):
        return ca.SessaoCondutasAlta(self.db, reg["id_paciente"], catalogo=self.cat, agora=AGORA, **kw)


class TestCatalogo(unittest.TestCase):
    def test_catalogo_real_e_valido(self):
        cat = ca.carregar_catalogo()
        self.assertGreaterEqual(len(cat.condutas), 9)
        for c in cat.condutas.values():
            self.assertTrue(c.fontes, f"{c.codigo} sem fonte")
            self.assertTrue(c.paciente.strip() and c.profissional.strip(), c.codigo)

    def test_catalogo_real_sem_travessoes_e_com_referencia_abnt(self):
        pasta = ca.pasta_catalogo()
        for nome in sorted(os.listdir(pasta)):
            if not nome.endswith(".json"):
                continue
            with open(os.path.join(pasta, nome), encoding="utf-8") as f:
                bruto = f.read()
            self.assertNotIn("\u2014", bruto, f"travessão (em dash) em {nome}")
            self.assertNotIn("\u2013", bruto, f"travessão (en dash) em {nome}")
        for c in ca.carregar_catalogo().condutas.values():
            for ref in c.fontes:
                self.assertIn("Disponível em:", ref)
                self.assertIn("Acesso em:", ref)

    def test_texto_do_paciente_e_compacto(self):
        for c in ca.carregar_catalogo().condutas.values():
            linhas = ca.linhas_do_texto(c.paciente)
            self.assertLessEqual(len(linhas), 8, f"{c.codigo}: texto do paciente longo demais")
            for _tipo, txt in linhas:
                self.assertLessEqual(len(txt), 190, f"{c.codigo}: linha longa demais")

    def test_gatilhos_do_catalogo_real_sao_validos(self):
        validos = ca.tokens_validos()
        for c in ca.carregar_catalogo().condutas.values():
            for t in c.gatilhos_qualquer + c.gatilhos_todas:
                self.assertIn(t, validos)

    def test_problemas_sao_listados_todos_de_uma_vez(self):
        ruim = grupo_teste(referencias={"R1": "Sem link nem data"})
        ruim["condutas"][0]["fontes"] = ["NAOEXISTE"]
        ruim["condutas"][1]["gatilhos"] = {"todas": ["drc", "token_inventado"]}
        ruim["condutas"][2]["fontes"] = []
        ruim["condutas"][3]["codigo"] = "x1"
        pasta = pasta_catalogo_teste(ruim)
        try:
            with self.assertRaises(ca.ErroCatalogo) as cm:
                ca.carregar_catalogo(pasta)
        finally:
            shutil.rmtree(pasta, ignore_errors=True)
        msg = str(cm.exception)
        for trecho in ("Disponível em", "NAOEXISTE", "token_inventado", "ao menos uma fonte", "padrão AAA-01"):
            self.assertIn(trecho, msg)
        self.assertGreaterEqual(len(cm.exception.problemas), 5)

    def test_codigo_repetido_entre_arquivos(self):
        pasta = pasta_catalogo_teste(grupo_teste(), grupo_teste(grupo="outro"))
        try:
            with self.assertRaises(ca.ErroCatalogo) as cm:
                ca.carregar_catalogo(pasta)
        finally:
            shutil.rmtree(pasta, ignore_errors=True)
        self.assertIn("já existe em outro arquivo", str(cm.exception))

    def test_pasta_vazia_ou_json_quebrado(self):
        vazia = tempfile.mkdtemp()
        try:
            with self.assertRaises(ca.ErroCatalogo):
                ca.carregar_catalogo(vazia)
            with open(os.path.join(vazia, "x.json"), "w", encoding="utf-8") as f:
                f.write("{isto nao e json")
            with self.assertRaises(ca.ErroCatalogo) as cm:
                ca.carregar_catalogo(vazia)
            self.assertIn("não foi possível ler", str(cm.exception))
        finally:
            shutil.rmtree(vazia, ignore_errors=True)


class TestRegras(Base):
    def test_tokens_do_registro(self):
        reg = {"via": "Enteral", "dm": 1, "has": 0, "drc": 1, "condicoes": "resp,tb"}
        self.assertEqual(ca.tokens_do_registro(reg), {"via:Enteral", "dm", "drc", "cond:resp", "cond:tb"})
        self.assertEqual(ca.tokens_do_registro(None), set())
        self.assertEqual(ca.tokens_do_registro({"via": "Oral"}), {"via:Oral"})

    def test_condutas_aplicaveis(self):
        cods = lambda toks: [c.codigo for c in ca.condutas_aplicaveis(self.cat, toks)]
        self.assertEqual(cods({"via:Enteral"}), ["TST-01"])
        self.assertEqual(cods({"via:Oral"}), [])
        self.assertEqual(cods({"drc"}), [])                      # 'todas' exige drc E dm
        self.assertEqual(cods({"drc", "dm"}), ["TST-02"])
        self.assertEqual(cods({"cond:tb"}), ["TST-03"])
        self.assertEqual(cods({"cond:resp"}), ["TST-03"])
        self.assertEqual(cods({"via:Enteral", "drc", "dm", "cond:tb"}), ["TST-01", "TST-02", "TST-03"])

    def test_conduta_sem_gatilho_nunca_e_sugerida(self):
        todos = {"via:Enteral", "via:Oral", "dm", "has", "drc", "laxativa", "constipante", "cond:resp", "cond:tb"}
        self.assertNotIn("TST-04", [c.codigo for c in ca.condutas_aplicaveis(self.cat, todos)])

    def test_rotulos(self):
        reg = {"via": "Enteral", "dm": 1, "drc": 1, "laxativa": 1, "condicoes": "tb"}
        self.assertEqual(ca.rotulos_do_registro(reg), ["Via enteral", "Diabetes mellitus", "Doença renal", "Tuberculose"])

    def test_usa_o_registro_mais_recente_do_paciente(self):
        r1 = registrar(self.db, data="2026-11-10", via="Enteral", drc=1)
        registrar(self.db, data="2026-11-14", id_paciente=r1["id_paciente"], via="Oral", drc=0)
        s = self.sessao(r1)
        self.assertEqual(s.tokens, {"via:Oral"})
        self.assertEqual(s.pendentes(), [])


class TestMapaCondicoes(Base):
    def test_gravar_e_ler_condicoes_em_ordem_canonica(self):
        r = registrar(self.db, condicoes=["tb", "resp"])
        self.assertEqual(r["condicoes"], "resp,tb")
        self.assertEqual(mdb.nomes_condicoes(r["condicoes"]), ["Doença respiratória", "Tuberculose"])

    def test_condicao_desconhecida_e_recusada(self):
        id_leito = mdb.criar_leito(self.db, 1, "L09")
        with self.assertRaises(ValueError) as cm:
            mdb.salvar_registro(self.db, dict(data="2026-11-15", id_leito=id_leito, nome_paciente="X", condicoes="asma"))
        self.assertIn("asma", str(cm.exception))

    def test_banco_antigo_ganha_a_coluna(self):
        fd, antigo = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            with closing(sqlite3.connect(antigo)) as c:   # esquema do Mapa SEM a coluna nova
                c.executescript(mdb._SCHEMA.replace("drc INTEGER DEFAULT 0, condicoes TEXT,", "drc INTEGER DEFAULT 0,"))
                self.assertNotIn("condicoes", [r[1] for r in c.execute("PRAGMA table_info(Mapa_Registros)")])
            mdb.inicializar(antigo)
            mdb.inicializar(antigo)               # idempotente
            with closing(sqlite3.connect(antigo)) as c:
                self.assertIn("condicoes", [r[1] for r in c.execute("PRAGMA table_info(Mapa_Registros)")])
            r = registrar(antigo, condicoes="tb")
            self.assertEqual(r["condicoes"], "tb")
        finally:
            os.remove(antigo)

    def test_copiar_mapa_mantem_condicoes(self):
        registrar(self.db, data="2026-11-14", condicoes="resp")
        self.assertEqual(mdb.copiar_mapa(self.db, "2026-11-14", "2026-11-15"), 1)
        copia = mdb.mapa_do_dia(self.db, "2026-11-15")[0]["registro"]
        self.assertEqual(copia["condicoes"], "resp")


class TestTexto(unittest.TestCase):
    def test_normalizar(self):
        self.assertEqual(ca.normalizar_texto("a  \r\n\r\n\r\nb\n\n"), "a\n\nb")
        self.assertEqual(ca.normalizar_texto(None), "")

    def test_linhas_do_texto(self):
        self.assertEqual(ca.linhas_do_texto("- um\n\n* dois\nlivre\n• tres"),
                         [("item", "um"), ("item", "dois"), ("texto", "livre"), ("item", "tres")])

    def test_lacunas(self):
        self.assertEqual(ca.contar_lacunas("a ____ b ______ c __"), 2)


class TestSessao(Base):
    def setUp(self):
        super().setUp()
        self.reg = registrar(self.db, via="Enteral", dm=1, drc=1, condicoes="tb")
        self.s = self.sessao(self.reg)

    def test_comeca_tudo_pendente_e_nao_cria_documento(self):
        self.assertEqual([c["codigo"] for c in self.s.cartoes()], ["TST-01", "TST-02", "TST-03"])
        self.assertTrue(all(c["estado"] == "pendente" for c in self.s.cartoes()))
        self.assertEqual(self.s.pendentes(), ["TST-01", "TST-02", "TST-03"])
        self.assertIsNone(ca.documento_atual(self.db, self.reg["id_paciente"]))

    def test_confirmar_grava_copia_e_marca_edicao(self):
        self.s.confirmar("TST-01")
        item = self.s.itens["TST-01"]
        self.assertEqual(item["decisao"], "confirmada")
        self.assertEqual(item["editado"], 0)
        self.assertEqual(item["versao_catalogo"], "t.1")
        self.assertIn("Disponível em", item["referencias"])
        self.s.confirmar("TST-02", texto_paciente="- Item renal corrigido pela nutricionista.")
        self.assertEqual(self.s.itens["TST-02"]["editado"], 1)
        card = {c["codigo"]: c for c in self.s.cartoes()}["TST-02"]
        self.assertEqual((card["estado"], card["editado"]), ("confirmada", True))
        self.assertEqual(card["texto_paciente"], "- Item renal corrigido pela nutricionista.")
        self.assertEqual(self.s.pendentes(), ["TST-03"])

    def test_editar_so_espacos_nao_conta_como_edicao(self):
        self.s.confirmar("TST-01", texto_paciente="- Dieta: ______  \r\n- Lave as mãos.\n\n")
        self.assertEqual(self.s.itens["TST-01"]["editado"], 0)

    def test_texto_vazio_nao_pode_ser_confirmado(self):
        with self.assertRaises(ca.ErroCondutasAlta):
            self.s.confirmar("TST-01", texto_paciente="   \n ")
        self.assertEqual(self.s.pendentes()[0], "TST-01")

    def test_nao_se_aplica_exige_motivo(self):
        with self.assertRaises(ca.ErroCondutasAlta):
            self.s.nao_se_aplica("TST-03", " ")
        self.s.nao_se_aplica("TST-03", "Paciente sem doença respiratória ativa")
        card = {c["codigo"]: c for c in self.s.cartoes()}["TST-03"]
        self.assertEqual(card["estado"], "nao_se_aplica")
        self.assertIsNone(self.s.itens["TST-03"]["texto_paciente"])
        self.assertNotIn("TST-03", self.s.pendentes())

    def test_desfazer_volta_para_pendente(self):
        self.s.confirmar("TST-01")
        self.s.desfazer("TST-01")
        self.assertIn("TST-01", self.s.pendentes())

    def test_decidir_de_novo_substitui_sem_duplicar(self):
        self.s.nao_se_aplica("TST-01", "motivo qualquer")
        self.s.confirmar("TST-01")
        self.assertEqual(len(ca.listar_itens(self.db, self.s.doc["id_doc"])), 1)
        self.assertEqual(self.s.itens["TST-01"]["decisao"], "confirmada")

    def test_corrigir_texto_so_muda_o_texto_do_paciente(self):
        with self.assertRaises(ca.ErroCondutasAlta):               # ainda pendente: não há o que corrigir
            self.s.corrigir_texto("TST-01", "- x")
        self.assertIsNone(self.s.doc)                              # e a tentativa não criou documento
        self.s.confirmar("TST-01")
        antes = dict(self.s.itens["TST-01"])
        self.s.corrigir_texto("TST-01", "- Dieta: 6 vezes por dia.\n- Lave as mãos.")
        item = self.s.itens["TST-01"]
        self.assertEqual(item["texto_paciente"], "- Dieta: 6 vezes por dia.\n- Lave as mãos.")
        self.assertEqual(item["editado"], 1)
        for campo in ("texto_profissional", "conferir", "referencias", "versao_catalogo", "titulo"):
            self.assertEqual(item[campo], antes[campo], campo)
        self.s.corrigir_texto("TST-01", "- Dieta: ______\n- Lave as mãos.")     # voltou ao texto do catálogo
        self.assertEqual(self.s.itens["TST-01"]["editado"], 0)
        with self.assertRaises(ca.ErroCondutasAlta):
            self.s.corrigir_texto("TST-01", " \n ")
        self.s.nao_se_aplica("TST-03", "não tem TB")
        with self.assertRaises(ca.ErroCondutasAlta):               # "não se aplica" não tem texto do paciente
            self.s.corrigir_texto("TST-03", "- x")

    def test_corrigir_texto_com_catalogo_novo_preserva_o_instantaneo(self):
        self.s.confirmar("TST-01")
        g = grupo_teste(versao="t.2")
        g["condutas"][0]["profissional"] = ["Texto profissional NOVO."]
        g["condutas"][0]["paciente"] = ["- Texto novo do catálogo."]
        pasta = pasta_catalogo_teste(g)
        try:
            novo_cat = ca.carregar_catalogo(pasta)
        finally:
            shutil.rmtree(pasta, ignore_errors=True)
        s2 = ca.SessaoCondutasAlta(self.db, self.reg["id_paciente"], catalogo=novo_cat, agora=AGORA)
        s2.corrigir_texto("TST-01", "- Dieta: ______\n- Lave bem as mãos.")
        item = s2.itens["TST-01"]
        self.assertEqual(item["texto_profissional"], "Texto profissional 1.")     # texto técnico da época
        self.assertEqual(item["versao_catalogo"], "t.1")
        self.assertEqual(item["editado"], 1)

    def test_adicionar_manual(self):
        self.s.adicionar_manual("TST-04")
        card = {c["codigo"]: c for c in self.s.cartoes()}["TST-04"]
        self.assertEqual((card["estado"], card["origem"]), ("pendente", "manual"))
        self.assertNotIn("TST-04", self.s.pendentes())          # manual não é pendência obrigatória
        self.s.confirmar("TST-04")
        self.assertEqual(self.s.itens["TST-04"]["origem"], "manual")
        with self.assertRaises(ca.ErroCondutasAlta):
            self.s.adicionar_manual("XXX-99")

    def test_conduta_decidida_continua_visivel_se_a_doenca_sair_do_mapa(self):
        self.s.confirmar("TST-03")
        registrar(self.db, id_paciente=self.reg["id_paciente"], data="2026-11-16", via="Enteral", dm=1, drc=1,
                  condicoes=None)
        s2 = self.sessao(self.reg)
        self.assertIn("TST-03", [c["codigo"] for c in s2.cartoes()])

    def test_entrega_exige_tudo_decidido_nome_e_uma_confirmada(self):
        with self.assertRaises(ca.ErroCondutasAlta) as cm:
            self.s.marcar_entregue()
        self.assertIn("documento", str(cm.exception))
        self.s.confirmar("TST-01")
        with self.assertRaises(ca.ErroCondutasAlta) as cm:
            self.s.marcar_entregue()
        self.assertIn("pendentes", str(cm.exception))
        self.s.nao_se_aplica("TST-02", "não tem DRC")
        self.s.nao_se_aplica("TST-03", "não tem TB")
        with self.assertRaises(ca.ErroCondutasAlta) as cm:
            self.s.marcar_entregue()
        self.assertIn("nome da nutricionista", str(cm.exception))
        self.s.salvar_cabecalho("Nutri Teste", "CRN-6 0000", "Volte em 30 dias.")
        self.s.marcar_entregue()
        self.assertTrue(self.s.entregue)
        self.assertEqual(self.s.doc["entregue_em"], "2026-11-15 10:00:00")

    def test_entrega_sem_nenhuma_confirmada_e_recusada(self):
        for cod in ("TST-01", "TST-02", "TST-03"):
            self.s.nao_se_aplica(cod, "não se aplica")
        self.s.salvar_cabecalho("Nutri Teste", "", "")
        with self.assertRaises(ca.ErroCondutasAlta) as cm:
            self.s.marcar_entregue()
        self.assertIn("pelo menos uma conduta", str(cm.exception))

    def entregar(self):
        for cod in ("TST-01", "TST-02", "TST-03"):
            self.s.confirmar(cod)
        self.s.salvar_cabecalho("Nutri Teste", "CRN-6 0000", "Recado.")
        self.s.marcar_entregue()

    def test_documento_entregue_e_imutavel_na_sessao_e_no_banco(self):
        self.entregar()
        with self.assertRaises(ca.ErroCondutasAlta):
            self.s.confirmar("TST-01", texto_paciente="- mudei")
        with self.assertRaises(ca.ErroCondutasAlta):
            self.s.salvar_cabecalho("Outro", "", "")
        id_doc = self.s.doc["id_doc"]
        for sql in ("UPDATE Condutas_Alta_Itens SET texto_paciente='x' WHERE id_doc=?",
                    "DELETE FROM Condutas_Alta_Itens WHERE id_doc=?",
                    "UPDATE Condutas_Alta_Docs SET recado='x' WHERE id_doc=?",
                    "DELETE FROM Condutas_Alta_Docs WHERE id_doc=?"):
            with closing(sqlite3.connect(self.db)) as c, self.assertRaises(sqlite3.IntegrityError, msg=sql):
                c.execute(sql, (id_doc,))
        with self.assertRaises(ca.ErroCondutasAlta):
            ca.desfazer_decisao(self.db, id_doc, "TST-01")

    def test_corrigir_texto_em_documento_entregue_e_recusado(self):
        self.entregar()
        with self.assertRaises(ca.ErroCondutasAlta):
            self.s.corrigir_texto("TST-01", "- mudei")
        with self.assertRaises(ca.ErroCondutasAlta):               # direto no módulo: o gatilho do banco também recusa
            ca.corrigir_texto_paciente(self.db, self.s.doc["id_doc"], "TST-01", "- mudei")

    def test_nova_versao_copia_decisoes_e_preserva_o_entregue(self):
        self.entregar()
        antigo = self.s.doc["id_doc"]
        self.s.nova_versao()
        self.assertFalse(self.s.entregue)
        self.assertEqual(self.s.doc["substitui_id_doc"], antigo)
        self.assertEqual(self.s.doc["nutricionista"], "Nutri Teste")
        self.assertEqual(sorted(self.s.itens), ["TST-01", "TST-02", "TST-03"])
        self.s.confirmar("TST-01", texto_paciente="- Texto corrigido na nova versão.")
        ant = {i["codigo"]: i for i in ca.listar_itens(self.db, antigo)}
        self.assertEqual(ant["TST-01"]["editado"], 0)             # o entregue segue como foi
        self.assertEqual([d["status"] for d in ca.listar_documentos(self.db, self.reg["id_paciente"])],
                         ["rascunho", "entregue"])
        with self.assertRaises(ca.ErroCondutasAlta):
            self.s.nova_versao()                                 # já é rascunho

    def test_cabecalho_padrao_vem_da_ultima_assinatura(self):
        self.s.salvar_cabecalho("Nutri Teste", "CRN-6 0000", "")
        outro = registrar(self.db, nome="Outra Pessoa Sintética", leito="L02", via="Enteral")
        s2 = self.sessao(outro)
        self.assertEqual((s2.cabecalho()["nutricionista"], s2.cabecalho()["crn"]), ("Nutri Teste", "CRN-6 0000"))

    def test_catalogo_novo_nao_altera_o_que_foi_confirmado(self):
        self.s.confirmar("TST-01")
        g = grupo_teste(versao="t.2")
        g["condutas"][0]["paciente"] = ["- Texto novo do catálogo."]
        pasta = pasta_catalogo_teste(g)
        try:
            novo_cat = ca.carregar_catalogo(pasta)
        finally:
            shutil.rmtree(pasta, ignore_errors=True)
        s2 = ca.SessaoCondutasAlta(self.db, self.reg["id_paciente"], catalogo=novo_cat, agora=AGORA)
        card = {c["codigo"]: c for c in s2.cartoes()}["TST-01"]
        self.assertIn("Lave as mãos", card["texto_paciente"])      # texto gravado, não o do catálogo novo
        self.assertTrue(card["catalogo_mudou"])

    def test_modelo_de_exportacao(self):
        self.s.confirmar("TST-01")
        self.s.salvar_cabecalho("Nutri Teste", "CRN-6 0000", "Recado ao paciente.")
        m = self.s.modelo_exportacao()
        self.assertEqual(m["paciente"], "Paciente Sintético")
        self.assertEqual(m["data"], "15/11/2026")
        self.assertEqual(m["condicoes"], ["Via enteral", "Diabetes mellitus", "Doença renal", "Tuberculose"])
        self.assertEqual((m["nutricionista"], m["crn"], m["recado"]), ("Nutri Teste", "CRN-6 0000", "Recado ao paciente."))
        self.assertEqual(m["status"], "rascunho")
        self.assertEqual(len(m["itens"]), 3)


class TestResumoDoMapa(Base):
    def test_estados_por_paciente(self):
        sem = registrar(self.db, nome="Sem Condutas", leito="L01", via="Oral")
        pend = registrar(self.db, nome="Com Pendência", leito="L02", via="Enteral", condicoes="tb")
        fei = registrar(self.db, nome="Tudo Decidido", leito="L03", via="Enteral")
        ent = registrar(self.db, nome="Já Entregue", leito="L04", via="Enteral")
        s = self.sessao(fei)
        s.nao_se_aplica("TST-01", "teste")
        s = self.sessao(ent)
        s.confirmar("TST-01")
        s.salvar_cabecalho("Nutri Teste", "", "")
        s.marcar_entregue()
        r = ca.resumo_por_registro(self.db, [sem, pend, fei, ent], self.cat)
        self.assertEqual(r[sem["id_paciente"]]["estado"], "sem")
        self.assertEqual(r[sem["id_paciente"]]["texto"], "")
        self.assertEqual((r[pend["id_paciente"]]["estado"], r[pend["id_paciente"]]["pendentes"]), ("pendente", 2))
        self.assertEqual(r[pend["id_paciente"]]["texto"], "2 pendentes")
        self.assertEqual((r[fei["id_paciente"]]["estado"], r[fei["id_paciente"]]["texto"]), ("decidido", "Decididas"))
        self.assertEqual((r[ent["id_paciente"]]["estado"], r[ent["id_paciente"]]["texto"]), ("entregue", "Entregue"))

    def test_cabecalho_sem_decisao_e_sem_sugestao_continua_sem_estado(self):
        reg = registrar(self.db, nome="Só Cabeçalho", leito="L05", via="Oral")
        self.sessao(reg).salvar_cabecalho("Nutri Teste", "", "")       # cria o rascunho, mas nada foi decidido
        r = ca.resumo_por_registro(self.db, [reg], self.cat)[reg["id_paciente"]]
        self.assertEqual((r["estado"], r["texto"]), ("sem", ""))

    def test_nova_doenca_depois_da_entrega_vira_pendencia_de_nova_versao(self):
        reg = registrar(self.db, via="Enteral")
        s = self.sessao(reg)
        s.confirmar("TST-01")
        s.salvar_cabecalho("Nutri Teste", "", "")
        s.marcar_entregue()
        novo = registrar(self.db, id_paciente=reg["id_paciente"], data="2026-11-16", via="Enteral", condicoes="resp")
        r = ca.resumo_por_registro(self.db, [novo], self.cat)[reg["id_paciente"]]
        self.assertEqual((r["estado"], r["pendentes"]), ("pendente", 1))
        self.assertEqual(r["texto"], "1 pendente (nova versão)")

    def test_lista_vazia_e_registro_sem_paciente(self):
        self.assertEqual(ca.resumo_por_registro(self.db, [], self.cat), {})
        self.assertEqual(ca.resumo_por_registro(self.db, [None, {"id_paciente": None}], self.cat), {})

    def test_banco_sem_a_migracao_da_erro_claro(self):
        fd, sem_migracao = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            mdb.inicializar(sem_migracao)
            with self.assertRaises(ca.ErroCondutasAlta) as cm:
                ca.documento_atual(sem_migracao, 1)
            self.assertIn("migração 2", str(cm.exception))
        finally:
            os.remove(sem_migracao)


class TestMigracao(unittest.TestCase):
    def test_aplicar_e_reverter_a_migracao_2(self):
        fd, caminho = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            mdb.inicializar(caminho)
            r = db_migracoes.aplicar_migracoes(caminho, backup=False)
            self.assertEqual((r.versao_final, r.aplicadas), (2, [1, 2]))
            def tabelas():
                with closing(sqlite3.connect(caminho)) as c:
                    return {x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertLessEqual({"Condutas_Alta_Docs", "Condutas_Alta_Itens"}, tabelas())
            rev = db_migracoes.reverter_migracoes(caminho, 1, backup=False)
            self.assertEqual((rev.versao_final, rev.revertidas), (1, [2]))
            self.assertFalse({"Condutas_Alta_Docs", "Condutas_Alta_Itens"} & tabelas())
            self.assertIn("Mapa_Registros", tabelas())            # o resto do banco não é tocado
            self.assertEqual(db_migracoes.aplicar_migracoes(caminho, backup=False).versao_final, 2)  # reaplica
        finally:
            os.remove(caminho)

    def test_banco_com_dados_gera_backup_antes_de_migrar(self):
        pasta = tempfile.mkdtemp()
        try:
            caminho = os.path.join(pasta, "clinica.db")
            mdb.inicializar(caminho)
            db_migracoes.aplicar_migracoes(caminho, migracoes=db_migracoes.MIGRACOES[:1])   # banco na v1
            r = db_migracoes.aplicar_migracoes(caminho)
            self.assertEqual(r.aplicadas, [2])
            self.assertIsNotNone(r.backup)
            self.assertTrue(os.path.exists(r.backup))
        finally:
            shutil.rmtree(pasta, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
