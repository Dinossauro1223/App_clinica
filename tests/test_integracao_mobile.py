# -*- coding: utf-8 -*-
"""Testes da integração desktop <-> mobile (criado em 12/11/2026). Dados sintéticos; sem interface gráfica real."""
import os
import json
import shutil
import sys
import tempfile
import types
import unittest
from contextlib import closing
from datetime import date, datetime
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import integracao_mobile as im  # noqa: E402
import mapa_db as mdb  # noqa: E402

try:
    from mobile import servidor as sv
except ImportError:  # pacote do mobile ainda não instalado: os testes que dependem do servidor são pulados
    sv = None
# servidor da versão 2 em diante (a primeira versão não tem publicar/migrar e não serve para a integração)
SERVIDOR_OK = sv is not None and all(hasattr(sv, n) for n in ("migrar", "publicar", "decidir", "linhas_mapa"))

DIA = "2026-11-12"


def exportacao(linhas, correcoes=()):
    """Monta um 'export' do mobile (esquema 2): setor Clinica A (id 1) e leitos A01..A04 (ids 1..4)."""
    base = {"nome": "", "idade_anos": None, "idade_meses": None, "acompanhante": 0, "dieta": "", "diagnostico": "",
            "pref_sim": "", "pref_nao": ""}
    mapa = [{**base, **campos, "data": DIA, "id_leito": int(cod[1:]), "por_perfil": "copa"} for cod, campos in linhas.items()]
    return {"data": DIA, "setores": [{"id": 1, "nome": "Clinica A"}],
            "leitos": [{"id": i, "id_setor": 1, "codigo": "A%02d" % i} for i in range(1, 5)],
            "itens": [{"id": 1, "nome": "Arroz", "unidade": "kg"}], "mapa": mapa, "correcoes_pendentes": list(correcoes),
            "refeicoes": [{"data": DIA, "id_setor": 1, "refeicao": "almoco", "qtd": 30.0, "atualizado_em": "2026-11-12T12:30:00-03:00"}],
            "estoque": [{"data": DIA, "estoque": "copa", "id_item": 1, "qtd": 5.0, "atualizado_em": "2026-11-12T08:00:00-03:00"}],
            "movimentos": [{"id": 1, "data": DIA, "hora": "2026-11-12T09:00:00-03:00", "origem": "cozinha", "destino": "copa",
                            "id_item": 1, "qtd": 2.0, "divergente": 1}]}


def _remover(caminho):
    try:
        os.remove(caminho)
    except OSError:  # no Windows o arquivo pode ficar preso por um instante; não vale falhar o teste por isso
        pass


class _Base(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(_remover, self.db)
        mdb.inicializar(self.db)
        mdb.criar_setor(self.db, "Clinica A")
        self.sid = next(s["id_setor"] for s in mdb.listar_setores(self.db) if s["nome"] == "Clinica A")
        mdb.criar_leitos_sequencia(self.db, self.sid, "A", 1, 4)
        self.leito = {l["codigo"]: l["id_leito"] for l in mdb.listar_leitos(self.db, self.sid)}

    def salvar(self, cod, **campos):
        mdb.salvar_registro(self.db, {"data": DIA, "id_leito": self.leito[cod], **campos})
        return self.reg(cod)

    def reg(self, cod):
        return mdb.obter_registro(self.db, DIA, self.leito[cod])


class TestMapeamento(unittest.TestCase):
    def test_dieta_e_diagnostico(self):
        self.assertEqual(im.dieta_para_desktop("Geral"), {"consistencia": "Livre"})
        self.assertEqual(im.dieta_para_desktop("pastosa"), {"consistencia": "Pastosa"})
        self.assertEqual(im.dieta_para_desktop("Enteral"), {"via": "Enteral"})
        self.assertEqual(im.dieta_para_desktop("Hipossódica"), {})
        self.assertEqual(im.dieta_para_mobile({"consistencia": "Livre"}), "Geral")
        self.assertEqual(im.dieta_para_mobile({"via": "Enteral", "consistencia": "Branda"}), "Enteral")
        self.assertEqual(im.diagnostico_para_mobile({"dm": 1, "has": 0, "drc": 1}), "DM, DRC")

    def test_servidor_antigo_da_erro_claro(self):
        antigo = types.SimpleNamespace(ESQUEMA="", conectar=lambda *_: None)  # como o servidor da 1ª versão: sem migrar/publicar
        with mock.patch.object(im, "_servidor", return_value=antigo):
            with self.assertRaises(im.ErroMobile) as erro:
                im.ler_mobile(os.path.join(tempfile.gettempdir(), "qualquer.db"), DIA)
        self.assertIn("versão antiga", str(erro.exception))


class TestTimestamps(unittest.TestCase):
    def test_comparacao_aceita_timestamp_naive_e_com_fuso(self):
        self.assertTrue(im._timestamp_maior("2026-11-12 12:00:00", "2026-11-12T11:00:00-03:00"))
        self.assertTrue(im._timestamp_maior("2026-11-12T12:00:00-03:00", "2026-11-12 11:00:00"))
        self.assertFalse(im._timestamp_maior("2026-11-12 10:00:00", "2026-11-12T11:00:00-03:00"))


class TestReceber(_Base):
    def test_mapa_recebido_de_varios_setores_fica_disponivel_na_visao_geral(self):
        ex = exportacao({"A01": {"nome": "Paciente Clínica", "dieta": "Branda"}})
        ex["setores"].append({"id": 2, "nome": "UTI"})
        ex["leitos"].append({"id": 5, "id_setor": 2, "codigo": "U01"})
        ex["mapa"].append({"data": DIA, "id_leito": 5, "nome": "Paciente UTI", "idade_anos": 60,
                           "idade_meses": None, "acompanhante": 0, "dieta": "Pastosa", "diagnostico": "",
                           "pref_sim": "", "pref_nao": "", "por_perfil": "copa"})
        propostas = im.propostas_mapa(self.db, ex)
        self.assertEqual({p["setor"] for p in propostas}, {"Clinica A", "UTI"})
        res = im.aplicar_mapa(self.db, propostas)
        self.assertEqual((res["aplicados"], res["erros"]), (2, []))
        geral = mdb.mapa_do_dia(self.db, DIA, None)
        self.assertEqual(len([x for x in geral if x["registro"]]), 2)
        self.assertEqual({x["leito"]["setor"] for x in geral if x["registro"]}, {"Clinica A", "UTI"})

    def test_novo_paciente_aplica_e_nao_repete(self):
        ex = exportacao({"A02": {"nome": "Joao Teste", "idade_anos": 8, "idade_meses": 3, "acompanhante": 1,
                                 "dieta": "Pastosa", "diagnostico": "Teste", "pref_nao": "peixe"}})
        props = im.propostas_mapa(self.db, ex)
        self.assertEqual([(p["leito"], p["tipo"], p["padrao"]) for p in props], [("A02", "novo", True)])
        res = im.aplicar_mapa(self.db, props)
        self.assertEqual((res["aplicados"], res["erros"]), (1, []))
        r = self.reg("A02")
        self.assertEqual((r["nome_paciente"], r["idade_meses"], r["acompanhante"], r["consistencia"], r["obs_nao"]),
                         ("Joao Teste", 3, 1, "Pastosa", "peixe"))
        self.assertIsNotNone(r["id_paciente"])
        self.assertEqual(im.propostas_mapa(self.db, ex), [])
        with closing(mdb.conectar(self.db)) as c:  # o diagnóstico não tem campo no desktop: fica guardado à parte
            self.assertEqual(c.execute("SELECT diagnostico FROM Mobile_Extra WHERE leito='A02'").fetchone()[0], "Teste")

    def test_alterado_preserva_dados_clinicos_e_suplementos(self):
        self.salvar("A01", nome_paciente="Maria Teste", idade_anos=70, peso_kg=60, altura_cm=160, consistencia="Branda", dm=1,
                    obs_sim="fruta", suplementos=[{"nome": "Modulo X", "qtd_dia": 2, "unidade": "un"}])
        ex = exportacao({"A01": {"nome": "Maria Teste", "idade_anos": 70, "dieta": "Branda", "pref_sim": "fruta", "pref_nao": "peixe"}})
        props = im.propostas_mapa(self.db, ex)
        self.assertEqual([(p["tipo"], p["campos"], p["padrao"]) for p in props], [("alterado", ["obs_nao"], True)])
        self.assertEqual(im.aplicar_mapa(self.db, props)["aplicados"], 1)
        r = self.reg("A01")
        self.assertEqual((r["obs_nao"], r["peso_kg"], r["altura_cm"], r["dm"], len(r["suplementos"])), ("peixe", 60, 160, 1, 1))

    def test_troca_de_paciente_comeca_limpo(self):
        antigo = self.salvar("A03", nome_paciente="Ana Teste", idade_anos=50, peso_kg=60, altura_cm=160)["id_paciente"]
        props = im.propostas_mapa(self.db, exportacao({"A03": {"nome": "Bia Teste", "idade_anos": 30}}))
        self.assertEqual([(p["tipo"], p["padrao"]) for p in props], [("troca", False)])
        self.assertEqual(im.aplicar_mapa(self.db, props)["aplicados"], 1)
        r = self.reg("A03")
        self.assertEqual((r["nome_paciente"], r["peso_kg"], r["idade_anos"]), ("Bia Teste", None, 30))
        self.assertNotEqual(r["id_paciente"], antigo)

    def test_liberar_leito(self):
        self.salvar("A04", nome_paciente="Caio Teste", idade_anos=40)
        props = im.propostas_mapa(self.db, exportacao({"A04": {}}))
        self.assertEqual([(p["tipo"], p["padrao"]) for p in props], [("liberar", False)])
        im.aplicar_mapa(self.db, props)
        self.assertIsNone(self.reg("A04"))

    def test_estado_mobile_mais_antigo_nao_substitui_pc(self):
        self.salvar("A01", nome_paciente="PC", idade_anos=70)
        with closing(mdb.conectar(self.db)) as c:
            c.execute("UPDATE Mapa_Registros SET atualizado_em=? WHERE id_leito=?",
                      ("2026-11-12 12:00:00", self.leito["A01"]))
            c.commit()
        ex = exportacao({"A01": {"nome": "Copa", "idade_anos": 71}})
        ex["mapa"][0]["atualizado_em"] = "2026-11-12T11:00:00-03:00"
        self.assertEqual(im.propostas_mapa(self.db, ex), [])

    def test_estado_mobile_mais_novo_gera_proposta(self):
        self.salvar("A01", nome_paciente="PC", idade_anos=70)
        with closing(mdb.conectar(self.db)) as c:
            c.execute("UPDATE Mapa_Registros SET atualizado_em=? WHERE id_leito=?",
                      ("2026-11-12 10:00:00", self.leito["A01"]))
            c.commit()
        ex = exportacao({"A01": {"nome": "Copa", "idade_anos": 71}})
        ex["mapa"][0]["atualizado_em"] = "2026-11-12T11:00:00-03:00"
        props = im.propostas_mapa(self.db, ex)
        self.assertEqual([(p["tipo"], p["leito"]) for p in props], [("troca", "A01")])

    def test_vazio_do_mobile_nao_apaga_e_geral_equivale_a_livre(self):
        self.salvar("A01", nome_paciente="Maria Teste", idade_anos=70, idade_meses=5, consistencia="Livre", obs_sim="fruta")
        ex = exportacao({"A01": {"nome": "Maria Teste", "idade_anos": 70, "dieta": "Geral"}})  # sem meses e sem preferências
        self.assertEqual(im.propostas_mapa(self.db, ex), [])

    def test_ignorar_nao_repete_ate_o_mobile_mudar(self):
        ex = exportacao({"A02": {"nome": "Joao Teste", "idade_anos": 8}})
        im.ignorar_mapa(self.db, im.propostas_mapa(self.db, ex))
        self.assertEqual(im.propostas_mapa(self.db, ex), [])
        ex2 = exportacao({"A02": {"nome": "Joao Teste", "idade_anos": 9}})
        self.assertEqual(len(im.propostas_mapa(self.db, ex2)), 1)

    def test_refeicoes_e_estoque_sao_idempotentes(self):
        ex = exportacao({})
        for _ in range(2):
            im.importar_refeicoes(self.db, ex)
            self.assertEqual(im.importar_estoque(self.db, ex), (1, 1))
        r = im.resumo(self.db, DIA)
        self.assertEqual(r["refeicoes"], [{"setor": "Clinica A", "refeicao": "almoco", "qtd": 30.0}])
        self.assertEqual((r["estoques"][0]["estoque"], r["estoques"][0]["itens"], r["movimentos"], r["divergentes"]), ("copa", 1, 1, 1))


@unittest.skipIf(not SERVIDOR_OK, "servidor mobile atualizado (pacote Mobile Completo) não instalado")
class TestComServidor(_Base):
    def setUp(self):
        super().setUp()
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        self.mdb = os.path.join(tmp, "mobile.db")
        sv.preparar_banco(self.mdb)
        self.salvar("A01", nome_paciente="Maria Teste", idade_anos=70, consistencia="Branda", dm=1, obs_sim="fruta")

    def mobile(self, sql, *a):
        c = sv.conectar(self.mdb)
        try:
            return [dict(r) for r in c.execute(sql, a)]
        finally:
            c.close()

    def copa_salva(self, linhas):
        c = sv.conectar(self.mdb)
        try:
            sid = c.execute("SELECT id FROM setores WHERE nome='Clinica A'").fetchone()["id"]
            ids = {l["codigo"]: l["id"] for l in c.execute("SELECT id, codigo FROM leitos WHERE id_setor=?", (sid,))}
            u = c.execute("SELECT * FROM usuarios WHERE login='copa1'").fetchone()
            if u is None:  # a correção só aparece com um usuário de verdade (o painel mostra quem pediu)
                sv.criar_usuario(c, "copa1", "Copa Teste", "copa", sid, "senha123")
                u = c.execute("SELECT * FROM usuarios WHERE login='copa1'").fetchone()
            res = sv.post_mapa(c, dict(u), {"id": sid, "nome": "Clinica A"}, DIA,
                               [{"id_leito": ids[cod], **campos} for cod, campos in linhas.items()])
            c.commit()
            return res
        finally:
            c.close()

    def test_exportacao_mobile_eh_snapshot_completo_e_herda_ate_alta(self):
        c = sv.conectar(self.mdb)
        try:
            setor = sv.criar_setor(c, {"nome": "Export", "codigos": ["E01", "E02"]})
            sid = setor["id"]
            lids = {r["codigo"]: r["id"] for r in c.execute(
                "SELECT id,codigo FROM leitos WHERE id_setor=?", (sid,)).fetchall()}
            adm = dict(c.execute("SELECT * FROM usuarios WHERE perfil='admin' ORDER BY id LIMIT 1").fetchone())
            ontem = "2026-11-11"
            sv.gravar(c, "mapa", ontem, str(lids["E01"]),
                      {"ocupado": 1, "nome": "Paciente Herdado", "idade_anos": 60,
                       "_atualizado_em": "2026-11-11T10:00:00-03:00"},
                      adm["id"], "admin")
            c.commit()

            ex = sv.exportar(c, DIA)
            linhas = {x["codigo"]: x for x in ex["mapa"] if x["id_setor"] == sid}
            self.assertEqual(len(linhas), 2)
            self.assertEqual((linhas["E01"]["nome"], linhas["E01"]["data_base"], linhas["E01"]["atualizado_em"]),
                             ("Paciente Herdado", ontem, "2026-11-11T10:00:00-03:00"))
            self.assertEqual((linhas["E02"]["nome"], linhas["E02"]["ocupado"]), ("", 0))

            # Uma alta/liberação explícita vira um novo estado vazio com timestamp mais recente.
            sv.post_mapa(c, adm, {"id": sid, "nome": "Export"}, DIA, [{
                "id_leito": lids["E01"], "nome": "", "ocupado": 0,
                "atualizado_em": "2026-11-12T10:00:00-03:00"
            }], completo=True)
            ex = sv.exportar(c, DIA)
            linha = next(x for x in ex["mapa"] if x["id_setor"] == sid and x["codigo"] == "E01")
            self.assertEqual((linha["nome"], linha["ocupado"], linha["data_base"], linha["atualizado_em"]),
                             ("", 0, DIA, "2026-11-12T10:00:00-03:00"))
            self.assertEqual(ex["esquema"], 4)
        finally:
            c.close()

    def test_snapshot_completo_respeita_o_mais_recente(self):
        c = sv.conectar(self.mdb)
        try:
            setor = sv.criar_setor(c, {"nome": "Clinica A", "codigos": ["A01"]})
            sid = setor["id"]
            lid = c.execute("SELECT id FROM leitos WHERE id_setor=? AND codigo='A01'", (sid,)).fetchone()["id"]
            u = dict(c.execute("SELECT * FROM usuarios WHERE perfil='admin' ORDER BY id LIMIT 1").fetchone())
            base = {"id_leito": lid, "nome": "Copa", "idade_anos": 70, "atualizado_em": "2026-11-12T10:00:00-03:00"}
            sv.post_mapa(c, u, {"id": sid, "nome": "Clinica A"}, DIA, [base], completo=True)
            antigo = {**base, "nome": "PC antigo", "atualizado_em": "2026-11-12T09:00:00-03:00"}
            sv.post_mapa(c, u, {"id": sid, "nome": "Clinica A"}, DIA, [antigo], completo=True)
            self.assertEqual(sv.linhas_mapa(c, sid, DIA)[0]["nome"], "Copa")
            novo = {**base, "nome": "PC novo", "atualizado_em": "2026-11-12T11:00:00-03:00"}
            sv.post_mapa(c, u, {"id": sid, "nome": "Clinica A"}, DIA, [novo], completo=True)
            self.assertEqual(sv.linhas_mapa(c, sid, DIA)[0]["nome"], "PC novo")
        finally:
            c.close()

    def test_ida_e_volta(self):
        # desktop -> mobile: publica para a copa com aviso dos leitos alterados
        res = im.enviar_mapa(self.db, self.mdb, DIA, texto="teste")
        self.assertEqual(next(r for r in res if r["setor"] == "Clinica A")["leitos"], 1)
        a01 = next(r for r in self.mobile("SELECT m.*, l.codigo FROM mapa_dia m JOIN leitos l ON l.id=m.id_leito") if r["codigo"] == "A01")
        self.assertEqual((a01["nome"], a01["dieta"], a01["diagnostico"], a01["pref_sim"], a01["por_perfil"]),
                         ("Maria Teste", "Branda", "DM", "fruta", "admin"))
        self.assertEqual(len(self.mobile("SELECT * FROM avisos")), 1)
        res = im.enviar_mapa(self.db, self.mdb, DIA)  # nada mudou: não avisa de novo
        self.assertEqual(next(r for r in res if r["setor"] == "Clinica A")["leitos"], 0)
        self.assertEqual(len(self.mobile("SELECT * FROM avisos")), 1)
        # a copeira corrige um leito que a nutrição já publicou (vira correção) e informa um paciente novo
        r = self.copa_salva({"A01": {"nome": "Maria Teste", "idade_anos": 70, "dieta": "Branda", "diagnostico": "DM",
                                     "pref_sim": "fruta", "pref_nao": "ovo"},
                             "A02": {"nome": "Joao Teste", "idade_anos": 8, "dieta": "Pastosa"}})
        self.assertEqual((r["pendente"], r["ok"]), (1, 1))
        # mobile -> desktop: as duas coisas chegam como propostas para conferir
        props = {p["leito"]: p for p in im.propostas_mapa(self.db, im.ler_mobile(self.mdb, DIA))}
        self.assertEqual((props["A01"]["tipo"], props["A01"]["campos"], bool(props["A01"]["id_correcao"])), ("alterado", ["obs_nao"], True))
        self.assertEqual((props["A02"]["tipo"], props["A02"]["id_correcao"]), ("novo", None))
        res = im.aplicar_mapa(self.db, list(props.values()), self.mdb)
        self.assertEqual((res["aplicados"], res["erros"]), (2, []))
        self.assertEqual((self.reg("A01")["obs_nao"], self.reg("A02")["nome_paciente"]), ("ovo", "Joao Teste"))
        self.assertEqual(self.mobile("SELECT status FROM correcoes")[0]["status"], "aprovada")
        self.assertEqual(im.propostas_mapa(self.db, im.ler_mobile(self.mdb, DIA)), [])
        # alta no desktop: o leito é liberado na copa (só porque foi o desktop que o preencheu)
        mdb.remover_registro(self.db, self.reg("A01")["id_registro"])
        im.enviar_mapa(self.db, self.mdb, DIA)
        a01 = next(r for r in self.mobile("SELECT m.*, l.codigo FROM mapa_dia m JOIN leitos l ON l.id=m.id_leito") if r["codigo"] == "A01")
        self.assertEqual(a01["nome"], "")

    def test_campos_estruturados_e_suplementos_fazem_ida_e_volta(self):
        catalogo = mdb.listar_suplementos(self.db, apenas_ativos=True)
        self.assertTrue(catalogo)
        s = catalogo[0]
        self.salvar("A03", nome_paciente="Paciente Completo", cor="B", via="Oral", consistencia="Pastosa",
                    dm=1, has=1, laxativa=1, constipante=0, drc=1,
                    suplementos=[{"id_suplemento": s["id_suplemento"], "nome": s["nome"], "modulo": s.get("modulo"),
                                  "ml_oferta": 120, "agua_ml": 25, "refeicoes": ["desjejum", "ceia"],
                                  "qtd_dia": 240, "unidade": "ml", "batido_fruta": True}])
        im.enviar_mapa(self.db, self.mdb, DIA)
        linha = next(r for r in self.mobile("SELECT m.*,l.codigo FROM mapa_dia m JOIN leitos l ON l.id=m.id_leito")
                     if r["codigo"] == "A03")
        self.assertEqual((linha["cor"], linha["via"], linha["consistencia"], linha["dm"], linha["has"],
                          linha["laxativa"], linha["constipante"], linha["drc"]),
                         ("B", "Oral", "Pastosa", 1, 1, 1, 0, 1))
        sup = json.loads(linha["suplementos_json"])[0]
        self.assertEqual((sup["ml_oferta"], sup["agua_ml"], sup["refeicoes"], sup["qtd_dia"], sup["batido_fruta"]),
                         (120.0, 25.0, ["desjejum", "ceia"], 240.0, True))
        with closing(sv.conectar(self.mdb)) as c:
            self.assertTrue(c.execute("SELECT 1 FROM suplementos_catalogo WHERE id_suplemento=? AND ativo=1",
                                      (s["id_suplemento"],)).fetchone())
        # A atualização feita pela Copa deve voltar com os mesmos detalhes ao desktop.
        self.copa_salva({"A03": {"nome": "Paciente Completo", "cor": "B", "via": "Oral",
                                  "consistencia": "Pastosa", "dm": 1, "has": 1, "laxativa": 1,
                                  "constipante": 0, "drc": 1,
                                  "suplementos": [{"id_suplemento": s["id_suplemento"], "nome": s["nome"],
                                                   "modulo": s.get("modulo"), "ml_oferta": 130, "agua_ml": 30,
                                                   "refeicoes": ["desjejum", "ceia"], "batido_fruta": False}]}})
        propostas = im.propostas_mapa(self.db, im.ler_mobile(self.mdb, DIA))
        proposta = next(p for p in propostas if p["leito"] == "A03")
        im.aplicar_mapa(self.db, [proposta], self.mdb)
        atualizado = self.reg("A03")["suplementos"][0]
        self.assertEqual((atualizado["ml_oferta"], atualizado["agua_ml"], atualizado["refeicoes"],
                          atualizado["batido_fruta"]), (130.0, 30.0, ["desjejum", "ceia"], 0))

    def test_correcao_recusada_no_desktop(self):
        im.enviar_mapa(self.db, self.mdb, DIA)
        self.copa_salva({"A01": {"nome": "Maria Teste", "idade_anos": 70, "pref_nao": "ovo"}})
        props = im.propostas_mapa(self.db, im.ler_mobile(self.mdb, DIA))
        self.assertEqual(len(props), 1)
        im.ignorar_mapa(self.db, props, self.mdb)
        self.assertEqual(self.mobile("SELECT status FROM correcoes")[0]["status"], "recusada")
        self.assertIsNone(self.reg("A01")["obs_nao"] or None)


def _importar_mobile_ui():
    """Importa mobile_ui com tkinter/customtkinter trocados por mocks (sem janela) e restaura o resto do processo."""
    nomes = ("customtkinter", "tkinter", "tkinter.ttk", "tkinter.messagebox", "tkinter.filedialog")
    antes = {n: sys.modules.get(n) for n in nomes}
    sys.modules.update({n: mock.MagicMock(name=n) for n in nomes})
    sys.modules.pop("mobile_ui", None)
    try:
        import mobile_ui
    finally:
        for n, m in antes.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m
    return mobile_ui


class TestTela(_Base):
    def test_tela_monta_sem_erro(self):
        ui = _importar_mobile_ui().MobileUI(mock.MagicMock(), self.db, os.path.dirname(self.db))
        ui.mostrar()
        self.assertTrue(ui.mobile_db.endswith(os.path.join("mobile", "dados", "mobile.db")))

    @unittest.skipIf(not SERVIDOR_OK, "servidor mobile atualizado (pacote Mobile Completo) não instalado")
    def test_tela_confere_e_aplica(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        mob = os.path.join(tmp, "mobile.db")
        sv.preparar_banco(mob)
        c = sv.conectar(mob)
        sid = sv.criar_setor(c, {"nome": "Clinica A", "prefixo": "A", "inicio": 1, "fim": 4})["id"]
        lid = c.execute("SELECT id FROM leitos WHERE codigo='A02'").fetchone()["id"]
        sv.post_mapa(c, {"id": 9, "perfil": "copa", "id_setor": sid}, {"id": sid, "nome": "Clinica A"}, DIA,
                     [{"id_leito": lid, "nome": "Joao Teste", "idade_anos": 8}])
        c.commit()
        c.close()
        mdb.salvar_config(self.db, "mobile_db", mob)
        app = mock.MagicMock()
        app.mapa = None  # sem a tela do Mapa: critério e tabelas LMS padrão
        mobile_ui = _importar_mobile_ui()
        ui = mobile_ui.MobileUI(app, self.db, os.path.dirname(self.db))

        # Este teste valida o fluxo da tela, não o agendamento concorrente.
        # Executa os workers de forma determinística; a thread real é coberta
        # separadamente por tests/test_ui_workers.py.
        def executar_sincrono(janela, trabalho, ao_sucesso=None, ao_erro=None,
                              ao_finalizar=None, nome="teste"):
            try:
                resultado = trabalho()
            except Exception as exc:
                if ao_erro:
                    ao_erro(exc)
            else:
                if ao_sucesso:
                    ao_sucesso(resultado)
            finally:
                if ao_finalizar:
                    ao_finalizar()

        with mock.patch.object(mobile_ui.ui_workers, "executar_em_segundo_plano",
                               side_effect=executar_sincrono):
            ui.mostrar()
            ui.data = date(2026, 11, 12)
            ui._verificar()
            self.assertEqual(len(ui.propostas), 1)
            ui.tree.selection.return_value = tuple(ui.propostas)
            ui._aplicar()
        self.assertEqual(self.reg("A02")["nome_paciente"], "Joao Teste")


class TestCatalogoPedidosAlmox(unittest.TestCase):
    def test_desktop_cadastra_item_tbca_e_calcula_prazo_de_recebimento(self):
        with tempfile.TemporaryDirectory() as pasta:
            banco = os.path.join(pasta, "mobile.db")
            sv.preparar_banco(banco)
            item_id = im.salvar_produto_almox(banco, {
                "nome": "Leite teste", "unidade": "frasco", "preco_unitario": "8,50",
                "embalagem_qtd": "1000", "embalagem_un": "ml", "tbca_id": "T001",
            }, estoque_inicial="4")
            c = sv.conectar(banco)
            try:
                item = c.execute("SELECT * FROM itens WHERE id=?", (item_id,)).fetchone()
                self.assertEqual(item["tbca_id"], "T001")
                self.assertEqual(item["embalagem_un"], "ml")
            finally:
                c.close()
            with mock.patch.object(sv, "agora_dt",
                                   lambda: datetime(2026, 11, 10, 9, 0, tzinfo=sv.TZ)):
                pedido = im.criar_pedido_almox(banco, item_id, 2, "Fornecedor teste", "Pedido teste", "Perfil desktop")
            with mock.patch.object(sv, "agora_dt",
                                   lambda: datetime(2026, 11, 12, 10, 0, tzinfo=sv.TZ)):
                im.receber_pedido_almox(banco, pedido, "Perfil desktop")
            prazo = im.prazo_medio_produto(banco, item_id)
            self.assertEqual(prazo["pedidos_recebidos"], 1)
            self.assertAlmostEqual(prazo["prazo_medio_dias"], 2.0)
            self.assertEqual(prazo["pendentes"], 0)



if __name__ == "__main__":
    unittest.main()
