"""Testes do NutriLab Mobile (criado em 12/11/2026). Dados 100% sintéticos; servidor em 127.0.0.1, porta livre."""
import json
import tempfile
import threading
import unittest
from contextlib import closing
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

from mobile import servidor as sv


class MobileTest(unittest.TestCase):
    @classmethod
    def chamar(cls, tok, metodo, caminho, corpo=None):
        cab = {"Content-Type": "application/json"}
        if tok:
            cab["Authorization"] = "Bearer " + tok
        dados = json.dumps(corpo).encode() if corpo is not None else None
        req = urllib.request.Request(cls.base + caminho, data=dados, method=metodo, headers=cab)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    @classmethod
    def entrar(cls, login, senha):
        cod, j = cls.chamar(None, "POST", "/api/login", {"login": login, "senha": senha})
        assert cod == 200, j
        return j["token"]

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        db = str(Path(cls.tmp.name) / "teste.db")
        senha = sv.preparar_banco(db)
        cls.db = db
        cls.srv = sv.criar_servidor(db, 0)
        cls.base = "http://127.0.0.1:%d" % cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.adm = cls.entrar("admin", senha)
        cls.chamar(cls.adm, "POST", "/api/admin/setores", {"nome": "Clinica A", "prefixo": "A", "inicio": 1, "fim": 6})
        cls.chamar(cls.adm, "POST", "/api/admin/setores", {"nome": "Clinica B", "codigos": ["B1"]})
        cls.chamar(cls.adm, "POST", "/api/admin/itens", {"nome": "Arroz", "unidade": "kg"})
        for login, perfil, setor in [("cop", "copa", 1), ("cop2", "copa", 2), ("nut", "nutricionista", 1),
                                     ("nut2", "nutricionista", 2), ("coz", "estoque_cozinha", None), ("alm", "estoque_almox", None)]:
            cod, j = cls.chamar(cls.adm, "POST", "/api/admin/usuarios",
                                {"login": login, "nome": login, "perfil": perfil, "id_setor": setor, "senha": "senha123"})
            assert cod == 200, j
        cls.t = {k: cls.entrar(k, "senha123") for k in ("cop", "cop2", "nut", "nut2", "coz", "alm")}

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    # -------------------------------------------------------------- auxiliares
    def leito(self, tok, lid, dia=None):
        cod, j = self.chamar(tok, "GET", "/api/mapa?setor=1" + ("&data=" + dia if dia else ""))
        self.assertEqual(cod, 200, j)
        return next(l for l in j["linhas"] if l["id_leito"] == lid)

    def publicar(self, linhas, dia=None, texto=None):
        extra = {"data": dia} if dia else {}
        nut = self.t["nut"]
        self.assertEqual(self.chamar(nut, "POST", "/api/mapa", {"setor": 1, "linhas": linhas, **extra})[0], 200)
        return self.chamar(nut, "POST", "/api/nutri/publicar", {"setor": 1, "texto": texto, **extra})

    def ontem(self):
        return (date.fromisoformat(sv.hoje()) - timedelta(days=1)).isoformat()

    def em(self, h, m=0):
        return mock.patch.object(sv, "agora_dt", lambda: datetime(2026, 11, 12, h, m, tzinfo=sv.TZ))

    def qtd(self, est, dia=None):
        consulta = "/api/estoque?estoque=" + est
        if dia:
            consulta += "&data=" + dia
        linhas = self.chamar(self.adm, "GET", consulta)[1]["linhas"]
        return next(l["qtd"] for l in linhas if l["nome"] == "Arroz")

    def limpar_itens_almox_teste(self, ids):
        c = sv.conectar(self.db)
        try:
            marcadores = ",".join("?" for _ in ids)
            for tabela in ("movimentos", "estoque_dia"):
                c.execute(f"DELETE FROM {tabela} WHERE id_item IN ({marcadores})", tuple(ids))
            c.execute(f"DELETE FROM itens WHERE id IN ({marcadores})", tuple(ids))
            c.commit()
        finally:
            c.close()

    # ------------------------------------------------------------------ testes
    def test_admin_inicial_usa_credencial_solicitada(self):
        with tempfile.TemporaryDirectory() as pasta:
            banco = str(Path(pasta) / "mobile.db")
            senha = sv.preparar_banco(banco)
            self.assertEqual(senha, "123456789")
            c = sv.conectar(banco)
            try:
                self.assertEqual(c.execute("SELECT login FROM usuarios WHERE perfil='admin'").fetchone()["login"], "admin")
                self.assertEqual(sv.login(c, "127.0.0.1", {"login": "admin", "senha": "123456789"})["usuario"]["perfil"], "admin")
            finally:
                c.close()
            # Simula banco legado: administrador existia com senha aleatória, mas sem marcador da migração.
            c = sv.conectar(banco)
            try:
                uid = c.execute("SELECT id FROM usuarios WHERE login='admin'").fetchone()["id"]
                c.execute("DELETE FROM sistema_config WHERE chave='senha_admin_inicial_aplicada'")
                sv.definir_senha(c, uid, "senha-legada-aleatoria")
                c.commit()
            finally:
                c.close()
            self.assertEqual(sv.preparar_banco(banco), "123456789")
            c = sv.conectar(banco)
            try:
                self.assertEqual(sv.login(c, "127.0.0.1", {"login": "admin", "senha": "123456789"})["usuario"]["perfil"], "admin")
                uid = c.execute("SELECT id FROM usuarios WHERE login='admin'").fetchone()["id"]
                sv.definir_senha(c, uid, "senha-personalizada")
                c.commit()
            finally:
                c.close()
            self.assertIsNone(sv.preparar_banco(banco))
            c = sv.conectar(banco)
            try:
                self.assertEqual(sv.login(c, "127.0.0.1", {"login": "admin", "senha": "senha-personalizada"})["usuario"]["perfil"], "admin")
            finally:
                c.close()
            senha_redefinida = sv.preparar_banco(banco, redefinir=True)
            self.assertTrue(senha_redefinida)
            self.assertNotEqual(senha_redefinida, "123456789")

    def test_copa_pode_consultar_e_gravar_no_mapa_compartilhado_de_outro_setor(self):
        cod, dados = self.chamar(self.t["cop"], "GET", "/api/mapa?setor=2")
        self.assertEqual(cod, 200, dados)
        self.assertEqual(dados["setor"]["id"], 2)
        cod, resultado = self.chamar(self.t["cop"], "POST", "/api/mapa",
                                     {"setor": 2, "linhas": [{"id_leito": 7, "nome": "Paciente compartilhado"}]})
        self.assertEqual(cod, 200, resultado)
        leitura = self.chamar(self.t["cop2"], "GET", "/api/mapa?setor=2")[1]
        linha = next(x for x in leitura["linhas"] if x["id_leito"] == 7)
        self.assertEqual(linha["nome"], "Paciente compartilhado")
        self.assertEqual(linha["por_nome"], "cop")


    def test_download_apk_disponibiliza_arquivo_do_bundle_com_nome_correto(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            destino = raiz / "apk" / "saida" / "NutriLab-Mobile.apk"
            destino.parent.mkdir(parents=True)
            conteudo = b"APK-DE-TESTE-SINTETICO"
            destino.write_bytes(conteudo)
            with mock.patch.object(sv, "AQUI", raiz):
                with urllib.request.urlopen(self.base + "/download/NutriLab-Mobile.apk") as resposta:
                    self.assertEqual(resposta.status, 200)
                    self.assertEqual(resposta.headers.get_content_type(), "application/vnd.android.package-archive")
                    self.assertIn('filename="NutriLab-Mobile.apk"', resposta.headers.get("Content-Disposition", ""))
                    self.assertEqual(resposta.read(), conteudo)

    def test_login_invalido(self):
        self.assertEqual(self.chamar(None, "POST", "/api/login", {"login": "admin", "senha": "errada"})[0], 401)

    def test_orientacoes_disponiveis_para_perfis_e_editaveis_so_pelo_admin(self):
        tokens = [self.adm, *self.t.values()]
        for tok in tokens:
            cod, j = self.chamar(tok, "GET", "/api/orientacoes")
            self.assertEqual(cod, 200)
            self.assertEqual({x["slug"] for x in j["orientacoes"]} >=
                             {"diluicao", "intestino", "potassio", "diabetes"}, True)
        linhas = self.chamar(self.adm, "GET", "/api/orientacoes")[1]["orientacoes"]
        dil = next(x for x in linhas if x["slug"] == "diluicao")
        self.assertEqual(self.chamar(self.t["cop"], "POST", "/api/admin/orientacoes",
                                     {"id": dil["id"], "titulo": "Não autorizado", "texto": "x"})[0], 403)
        self.assertEqual(self.chamar(self.adm, "POST", "/api/admin/orientacoes",
                                     {"id": dil["id"], "titulo": "Preparo revisado", "texto": "Texto revisado"})[0], 200)
        self.assertEqual(self.chamar(self.adm, "POST", "/api/admin/orientacoes",
                                     {"titulo": "Aviso local", "texto": "Conteúdo adicional"})[0], 200)
        atual = self.chamar(self.t["cop"], "GET", "/api/orientacoes")[1]["orientacoes"]
        self.assertTrue(any(x["titulo"] == "Preparo revisado" for x in atual))
        self.assertTrue(any(x["titulo"] == "Aviso local" for x in atual))

    def test_arquivos_ilustrativos_e_creditos_mobile(self):
        for caminho, tipo in (("/static/diluicao.svg", "image/svg+xml"),
                              ("/static/frutas.svg", "image/svg+xml")):
            with urllib.request.urlopen(self.base + caminho) as r:
                self.assertEqual(r.status, 200)
                self.assertIn(tipo, r.headers.get("Content-Type", ""))
                self.assertIn(b"<svg", r.read(300))
        pagina = (Path(__file__).resolve().parents[1] / "mobile" / "static" / "index.html").read_text(encoding="utf-8")
        for texto in ("Orientações", "Thiago S. Santos", "Neis B. Alencar", "NutriLab 2026",
                      "https://www.tbca.net.br/base-dados/", "Reconheça as frutas"):
            self.assertIn(texto, pagina)
        for conteudo_individual in ("escalaFrutas", "Carboidrato disponível:", "Fibra alimentar: maior",
                                    "Potássio: menor", "k:173", "f:4.03"):
            self.assertNotIn(conteudo_individual, pagina)
        # O gráfico deve usar valores TBCA por 100 g, sem transformar a comparação em
        # liberação/proibição clínica. Os desenhos precisam comunicar copo, balança e mistura.
        for trecho in ("potassio:83.62", "potassio:346.00", "potassio:160.42",
                       "Potássio nas frutas", "por 100 g", "não libera nem proíbe"):
            self.assertIn(trecho, pagina)
        desenho_preparo = (Path(__file__).resolve().parents[1] / "mobile" / "static" / "diluicao.svg").read_text(encoding="utf-8")
        for termo in ("COPO DOSADOR", "BALANÇA", "VOLUME MAIOR", "mL", "gramas"):
            self.assertIn(termo, desenho_preparo)
        self.assertNotIn("fumaça", desenho_preparo.lower())
        desenho_frutas = (Path(__file__).resolve().parents[1] / "mobile" / "static" / "frutas.svg").read_text(encoding="utf-8")
        for termo in ("melancia", "uva", "mamão"):
            self.assertIn(termo, desenho_frutas.lower())


    def test_admin_cadastra_e_edita_preco_e_embalagem_do_item(self):
        codigo, dados = self.chamar(self.adm, "POST", "/api/admin/itens", {
            "nome": "Farinha Teste", "unidade": "pacote", "preco_unitario": 8.5,
            "embalagem_qtd": 500, "embalagem_un": "g"
        })
        self.assertEqual(codigo, 200, dados)
        item_id = dados.get("id")
        self.assertTrue(item_id)
        lista = self.chamar(self.adm, "GET", "/api/itens")[1]["itens"]
        item = next(x for x in lista if x["id"] == item_id)
        self.assertEqual((item["preco_unitario"], item["embalagem_qtd"], item["embalagem_un"]),
                         (8.5, 500.0, "g"))
        self.assertEqual(self.chamar(self.adm, "POST", "/api/admin/itens/%s" % item_id, {
            "nome": "Farinha Teste", "unidade": "pacote", "preco_unitario": 9.0,
            "embalagem_qtd": 1, "embalagem_un": "kg"
        })[0], 200)
        atual = next(x for x in self.chamar(self.adm, "GET", "/api/itens")[1]["itens"] if x["id"] == item_id)
        self.assertEqual((atual["preco_unitario"], atual["embalagem_qtd"], atual["embalagem_un"]),
                         (9.0, 1000.0, "g"))
        self.assertEqual(self.chamar(self.t["cop"], "POST", "/api/admin/itens/%s" % item_id, {
            "nome": "Farinha Teste", "unidade": "pacote", "preco_unitario": 9.0
        })[0], 403)

    def test_admin_rejeita_embalagem_com_unidade_invalida(self):
        codigo, _ = self.chamar(self.adm, "POST", "/api/admin/itens", {
            "nome": "Item inválido", "unidade": "pacote", "preco_unitario": 8,
            "embalagem_qtd": 500, "embalagem_un": "x"
        })
        self.assertEqual(codigo, 400)

    def test_catalogo_de_suplementos_disponivel_para_copa(self):
        with closing(sv.conectar(self.db)) as c:
            c.execute("INSERT OR REPLACE INTO suplementos_catalogo(id_suplemento,nome,modulo,emb_qtd,emb_un,ativo) "
                      "VALUES(901,'Suplemento Teste','Fórmula completa',200,'ml',1)")
            c.commit()
        cod, dados = self.chamar(self.t["cop"], "GET", "/api/suplementos")
        self.assertEqual(cod, 200)
        item = next(s for s in dados["suplementos"] if s["id_suplemento"] == 901)
        self.assertEqual((item["nome"], item["modulo"], item["emb_qtd"], item["emb_un"]),
                         ("Suplemento Teste", "Fórmula completa", 200.0, "ml"))

    def test_copa_salva_caracteristicas_e_varios_suplementos(self):
        linha = {"id_leito": 6, "nome": "Paciente Suplementação", "cor": "B", "consistencia": "Pastosa",
                 "via": "Oral", "dm": True, "has": True, "laxativa": False, "constipante": True, "drc": False,
                 "suplementos": [
                     {"id_suplemento": 901, "nome": "Suplemento Teste", "modulo": "Fórmula completa",
                      "ml_oferta": 150, "agua_ml": 30, "refeicoes": ["desjejum", "ceia"], "batido_fruta": True},
                     {"id_suplemento": 902, "nome": "Módulo Teste", "modulo": "Proteico",
                      "ml_oferta": 50, "agua_ml": 0, "refeicoes": ["almoco"], "batido_fruta": False}
                 ]}
        cod, _ = self.chamar(self.t["cop"], "POST", "/api/mapa", {"linhas": [linha]})
        self.assertEqual(cod, 200)
        salvo = self.leito(self.t["cop"], 6)
        self.assertEqual((salvo["cor"], salvo["consistencia"], salvo["via"], salvo["dm"], salvo["has"],
                          salvo["laxativa"], salvo["constipante"], salvo["drc"]),
                         ("B", "Pastosa", "Oral", 1, 1, 0, 1, 0))
        self.assertEqual(len(salvo["suplementos"]), 2)
        self.assertEqual((salvo["suplementos"][0]["qtd_dia"], salvo["suplementos"][0]["ofertas_dia"],
                          salvo["suplementos"][0]["agua_ml"], salvo["suplementos"][0]["batido_fruta"]),
                         (300.0, 2, 30.0, True))
        self.assertEqual(salvo["suplementos"][1]["qtd_dia"], 50.0)

    def test_suplemento_exige_ao_menos_uma_refeicao(self):
        linha = {"id_leito": 5, "nome": "Paciente Teste", "suplementos": [
            {"id_suplemento": 903, "nome": "Suplemento", "ml_oferta": 100, "refeicoes": []}]}
        cod, dados = self.chamar(self.t["cop"], "POST", "/api/mapa", {"linhas": [linha]})
        self.assertEqual(cod, 400)
        self.assertIn("refeição", dados["erro"])

    def test_permissoes_por_perfil(self):
        t = self.t
        self.assertEqual(self.chamar(t["cop"], "GET", "/api/nutri/painel")[0], 403)
        self.assertEqual(self.chamar(t["cop"], "POST", "/api/nutri/publicar", {"setor": 1})[0], 403)
        self.assertEqual(self.chamar(t["cop"], "POST", "/api/nutri/janelas", {"refeicao": "almoco", "abre": "10:00", "fecha": "11:00"})[0], 403)
        self.assertEqual(self.chamar(t["coz"], "GET", "/api/mapa")[0], 403)
        self.assertEqual(self.chamar(t["nut"], "GET", "/api/estoque")[0], 403)
        self.assertEqual(self.chamar(t["cop"], "GET", "/api/mapa?setor=2")[1]["setor"]["id"], 2)  # a copa pode consultar outro setor
        self.assertEqual(self.chamar(t["cop2"], "GET", "/api/mapa?setor=1")[1]["setor"]["id"], 1)
        self.assertEqual(self.chamar(t["nut"], "GET", "/api/mapa?setor=2")[1]["setor"]["id"], 1)
        self.assertEqual(self.chamar(t["cop"], "GET", "/api/estoque?estoque=almox")[1]["estoque"], "copa")

    def test_copa_so_grava_no_proprio_dia(self):
        hoje, ontem = sv.hoje(), self.ontem()
        corpo = {"data": ontem, "linhas": [{"id_leito": 1, "nome": "Paciente Teste 1", "idade_anos": 70, "dieta": "Geral",
                                            "diagnostico": "Teste", "pref_sim": "fruta", "pref_nao": "peixe"}]}
        self.assertEqual(self.chamar(self.t["cop"], "POST", "/api/mapa", corpo)[0], 200)
        self.assertIsNone(self.leito(self.adm, 1, ontem)["data_base"])  # nada gravado em "ontem"
        l = self.leito(self.t["cop"], 1)
        self.assertEqual((l["data_base"], l["nome"], l["idade_anos"], l["pref_nao"], l["ocupado"]), (hoje, "Paciente Teste 1", 70, "peixe", 1))

    def test_comeca_pela_base_do_dia_anterior(self):
        cod, _ = self.publicar([{"id_leito": 2, "nome": "Paciente Teste 2", "idade_anos": 8, "idade_meses": 3,
                                 "dieta": "Branda", "acompanhante": True}], dia=self.ontem())
        self.assertEqual(cod, 200)
        l = self.leito(self.t["cop"], 2)
        self.assertEqual((l["nome"], l["idade_meses"], l["dieta"], l["acompanhante"], l["herdado"]), ("Paciente Teste 2", 3, "Branda", 1, True))

    def test_correcao_da_copa_precisa_de_autorizacao_da_nutricao(self):
        t = self.t
        self.publicar([{"id_leito": 3, "nome": "Paciente Teste 3", "dieta": "Geral"}])
        cod, r = self.chamar(t["cop"], "POST", "/api/mapa", {"linhas": [{"id_leito": 3, "nome": "Paciente Teste 3", "dieta": "Pastosa"}]})
        self.assertEqual(r["pendente"], 1)
        self.assertEqual(self.leito(t["cop"], 3)["dieta"], "Geral")  # nada foi sobrescrito
        k = next(x for x in self.chamar(t["nut"], "GET", "/api/nutri/correcoes")[1]["correcoes"] if "A03" in x["rotulo"])
        self.assertEqual(k["valor_atual"]["dieta"], "Geral")
        self.assertFalse([x for x in self.chamar(t["nut2"], "GET", "/api/nutri/correcoes")[1]["correcoes"] if "A03" in x["rotulo"]])
        self.assertEqual(self.chamar(t["nut2"], "POST", "/api/nutri/correcoes/%d" % k["id"], {"acao": "aprovar"})[0], 403)
        self.assertEqual(self.chamar(t["nut"], "POST", "/api/nutri/correcoes/%d" % k["id"], {"acao": "aprovar"})[0], 200)
        self.assertEqual(self.leito(t["cop"], 3)["dieta"], "Pastosa")

    def test_publicacao_chega_a_copa_e_avisa_quais_leitos(self):
        cop, cop2, nut = self.t["cop"], self.t["cop2"], self.t["nut"]
        for tok in (cop, cop2):  # zera avisos deixados por outros testes
            ids = [a["id"] for a in self.chamar(tok, "GET", "/api/avisos")[1]["avisos"]]
            self.chamar(tok, "POST", "/api/avisos/lidos", {"ids": ids})
        linhas = [{"id_leito": 4, "nome": "Paciente Teste 4", "idade_anos": 55, "dieta": "Zero", "diagnostico": "Teste"},
                  {"id_leito": 5, "nome": "Paciente Teste 5", "idade_anos": 31}]
        self.chamar(nut, "POST", "/api/mapa", {"setor": 1, "linhas": linhas})
        self.assertEqual(self.leito(cop, 4)["nome"], "")  # rascunho ainda não chega à copa...
        self.assertTrue(self.leito(nut, 4)["rascunho"])  # ...mas a nutrição o enxerga
        self.assertEqual(self.chamar(cop, "GET", "/api/avisos")[1]["avisos"], [])
        cod, r = self.chamar(nut, "POST", "/api/nutri/publicar", {"setor": 1, "texto": "Conferir dietas"})
        self.assertEqual((cod, r["leitos"]), (200, 2))
        self.assertEqual(self.leito(cop, 4)["diagnostico"], "Teste")
        av = self.chamar(cop, "GET", "/api/avisos")[1]["avisos"]
        self.assertEqual(len(av), 1)
        self.assertEqual({(x["leito"], x["tipo"]) for x in av[0]["leitos"]}, {("A04", "novo"), ("A05", "novo")})
        self.assertEqual(len(self.chamar(cop2, "GET", "/api/avisos")[1]["avisos"]), 1)  # todas as copeiras recebem avisos do mapa compartilhado
        self.chamar(cop, "POST", "/api/avisos/lidos", {"ids": [av[0]["id"]]})
        self.assertEqual(self.chamar(cop, "GET", "/api/avisos")[1]["avisos"], [])
        self.chamar(nut, "POST", "/api/nutri/avisos", {"texto": "Dieta zero a partir das 20h"})  # aviso em texto
        self.assertEqual(self.chamar(cop, "GET", "/api/avisos")[1]["avisos"][0]["tipo"], "texto")
        self.chamar(nut, "POST", "/api/mapa", {"setor": 1, "linhas": [{"id_leito": 4}]})  # sem nome = leito liberado
        self.chamar(nut, "POST", "/api/nutri/publicar", {"setor": 1})
        self.assertEqual(self.leito(cop, 4)["nome"], "")
        self.assertEqual(self.chamar(self.t["nut2"], "POST", "/api/nutri/publicar", {"setor": 1})[0], 400)  # nut2 só publica o setor 2

    def test_contagem_de_refeicoes_so_no_horario(self):
        cop, nut = self.t["cop"], self.t["nut"]

        def cont(tok, ref, q=10):
            return self.chamar(tok, "POST", "/api/refeicoes", {"linhas": [{"refeicao": ref, "qtd": q}]})[0]
        with self.em(10):
            self.assertEqual(cont(cop, "almoco"), 200)
            self.assertEqual(cont(cop, "jantar"), 403)  # ainda fechado
            self.assertEqual(cont(cop, "desjejum"), 403)  # refeição não habilitada
            j = self.chamar(cop, "GET", "/api/refeicoes")[1]
            self.assertEqual([(l["refeicao"], l["aberta"]) for l in j["linhas"]], [("almoco", True), ("jantar", False)])
        with self.em(8, 59):
            self.assertEqual(cont(cop, "almoco"), 403)
        with self.em(17):
            self.assertEqual(cont(cop, "almoco"), 403)  # a janela do almoço fechou às 16:00
            self.assertEqual(cont(cop, "jantar"), 200)
            self.assertEqual(cont(nut, "almoco", 11), 200)  # nutrição conta a qualquer hora
            self.assertEqual(self.chamar(nut, "POST", "/api/nutri/janelas", {"refeicao": "almoco", "abre": "17:00", "fecha": "18:00"})[0], 200)
            self.assertEqual(cont(cop, "almoco"), 200)  # horário do setor 1 foi alterado pela nutrição dele
            self.chamar(self.t["nut2"], "POST", "/api/nutri/janelas", {"setor": 1, "refeicao": "jantar", "abre": "10:00", "fecha": "11:00"})
            self.assertEqual(cont(cop, "jantar"), 200)  # nut2 mexeu só no setor 2
        with self.em(14, 30):
            self.assertEqual(self.chamar(self.adm, "POST", "/api/admin/refeicoes",
                                         {"refeicao": "lanche", "ativa": True, "abre": "14:00", "fecha": "15:00"})[0], 200)
            self.assertEqual(cont(cop, "lanche"), 200)  # refeição acrescentada depois

    def test_almox_categorias_validade_busca_e_devolucao_com_observacao(self):
        for nome, categoria, validade in (("Tempero Validade", "Temperos e condimentos", "2026-11-30"),
                                          ("Arroz Validade", "Grãos e cereais", "2026-12-15")):
            codigo, dados = self.chamar(self.adm, "POST", "/api/admin/itens", {
                "nome": nome, "unidade": "g", "preco_unitario": 0.05,
                "categoria": categoria, "validade": validade})
            self.assertEqual(codigo, 200, dados)
        itens = self.chamar(self.adm, "GET", "/api/itens")[1]["itens"]
        self.assertLess(itens.index(next(x for x in itens if x["nome"] == "Tempero Validade")),
                        itens.index(next(x for x in itens if x["nome"] == "Arroz Validade")))
        tempero = next(x for x in itens if x["nome"] == "Tempero Validade")
        arroz_novo = next(x for x in itens if x["nome"] == "Arroz Validade")
        self.addCleanup(self.limpar_itens_almox_teste, [tempero["id"], arroz_novo["id"]])
        self.assertEqual((tempero["categoria"], tempero["validade"]), ("Temperos e condimentos", "2026-11-30"))
        iid = tempero["id"]
        self.assertEqual(self.chamar(self.t["alm"], "POST", f"/api/almox/itens/{iid}", {
            "categoria":"Temperos e condimentos", "validade":"2026-11-29"})[0], 200)
        tempero_atualizado = next(x for x in self.chamar(self.adm, "GET", "/api/itens")[1]["itens"] if x["id"] == iid)
        self.assertEqual(tempero_atualizado["validade"], "2026-11-29")
        self.assertEqual(self.chamar(self.t["alm"], "POST", "/api/estoque/reposicao", {
            "estoque":"almox", "id_item":iid, "qtd":100, "origem":"externo", "observacao":"Compra inicial"})[0], 200)
        self.assertEqual(self.chamar(self.t["coz"], "POST", "/api/estoque/reposicao", {
            "estoque":"cozinha", "id_item":iid, "qtd":100, "origem":"almox", "observacao":"Retirada para preparo"})[0], 200)
        self.assertEqual(self.chamar(self.t["alm"], "POST", "/api/estoque/reposicao", {
            "estoque":"almox", "id_item":iid, "qtd":20, "origem":"cozinha",
            "observacao":"Devolução de 20 g não utilizados"})[0], 200)
        saldo = next(x for x in self.chamar(self.adm, "GET", "/api/estoque?estoque=almox")[1]["linhas"] if x["id_item"] == iid)["qtd"]
        self.assertEqual(saldo, 20)
        with closing(sv.conectar(self.db)) as c:
            mov = c.execute("SELECT origem,destino,observacao FROM movimentos WHERE id_item=? ORDER BY id DESC LIMIT 1", (iid,)).fetchone()
            self.assertEqual((mov["origem"], mov["destino"], mov["observacao"]),
                             ("cozinha", "almox", "Devolução de 20 g não utilizados"))
        html = (Path(__file__).resolve().parents[1] / "mobile" / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn("function filtrarEstoque()", html)
        self.assertIn("id=buscaEstoque", html)
        self.assertIn("id=categoriaEstoque", html)
        self.assertIn("async function salvarClassificacao(id)", html)

    def test_hierarquia_almox_cozinha_copa(self):
        def rep(t, org, q):
            return self.chamar(self.t[t], "POST", "/api/estoque/reposicao", {"id_item": 1, "qtd": q, "origem": org})[0]
        self.chamar(self.adm, "POST", "/api/estoque", {"estoque": "almox", "linhas": [{"id_item": 1, "qtd": 10}]})
        self.assertEqual(rep("coz", "cozinha", 1), 400)  # cozinha só recebe do almoxarifado
        self.assertEqual(rep("coz", "almox", 4), 200)
        self.assertEqual((self.qtd("almox"), self.qtd("cozinha")), (6, 4))
        self.assertEqual(rep("cop", "almox", 1), 400)  # cozinha ainda tem: pegar primeiro lá
        self.assertEqual(rep("cop", "cozinha", 4), 200)
        self.assertEqual(rep("cop", "almox", 2), 200)  # cozinha zerou: pode ir ao almoxarifado
        self.assertEqual((self.qtd("almox"), self.qtd("cozinha"), self.qtd("copa")), (4, 0, 6))
        self.assertEqual(rep("coz", "almox", 1), 200)  # cozinha recebe do almoxarifado
        self.assertEqual(rep("alm", "cozinha", 1), 200)  # devolução de sobra ao almoxarifado
        self.assertEqual((self.qtd("almox"), self.qtd("cozinha"), self.qtd("copa")), (4, 0, 6))
        self.assertEqual(rep("alm", "externo", 5), 200)
        self.assertEqual(self.qtd("almox"), 9)


    def test_migracao_normaliza_unidades_antigas_sem_alterar_conteudo_fisico(self):
        with tempfile.TemporaryDirectory() as pasta:
            banco = str(Path(pasta) / "mobile.db")
            sv.preparar_banco(banco)
            c = sv.conectar(banco)
            try:
                c.executemany(
                    "INSERT INTO itens(nome,unidade,embalagem_qtd,embalagem_un) VALUES(?,?,?,?)",
                    [("Produto kg", "pacote", 0.5, "kg"),
                     ("Produto L", "frasco", 1.5, "L"),
                     ("Produto mg", "sache", 250, "mg"),
                     ("Produto g", "pacote", 500, "g")],
                )
                sv.migrar(c)
                valores = {r["nome"]: (r["embalagem_qtd"], r["embalagem_un"])
                           for r in c.execute("SELECT nome,embalagem_qtd,embalagem_un FROM itens")}
                self.assertEqual(valores["Produto kg"], (500.0, "g"))
                self.assertEqual(valores["Produto L"], (1500.0, "ml"))
                self.assertEqual(valores["Produto mg"], (0.25, "g"))
                self.assertEqual(valores["Produto g"], (500.0, "g"))
            finally:
                c.close()

    def test_cadastro_mobile_apresenta_unidades_como_opcoes_diretas(self):
        html = (Path(__file__).resolve().parents[1] / "mobile" / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn('name=ieu value="g"', html)
        self.assertIn('name=ieu value="ml"', html)
        self.assertIn('name=ieu value="un"', html)
        self.assertNotIn("select id=ieu", html)


    def test_todas_as_copeiras_compartilham_mapa_e_historico_identifica_autor(self):
        cop, cop2 = self.t["cop"], self.t["cop2"]
        mapa = self.chamar(cop, "GET", "/api/mapa?setor=2")[1]
        self.assertEqual(mapa["setor"]["id"], 2)
        leito_id = mapa["linhas"][0]["id_leito"]
        codigo, resultado = self.chamar(cop, "POST", "/api/mapa", {
            "setor": 2, "linhas": [{"id_leito": leito_id, "nome": "Paciente compartilhado"}]
        })
        self.assertEqual(codigo, 200, resultado)
        leitura = self.chamar(cop2, "GET", "/api/mapa?setor=2")[1]
        linha = next(x for x in leitura["linhas"] if x["id_leito"] == leito_id)
        self.assertEqual(linha["nome"], "Paciente compartilhado")
        self.assertEqual(linha["por_nome"], "cop")
        self.assertEqual(linha["por_perfil"], "copa")
        with closing(sv.conectar(self.db)) as c:
            historico = c.execute(
                "SELECT por_nome,por_perfil,origem,campos_alterados FROM mapa_historico "
                "WHERE id_leito=? ORDER BY id DESC LIMIT 1", (leito_id,)
            ).fetchone()
            self.assertIsNotNone(historico)
            self.assertEqual((historico["por_nome"], historico["por_perfil"], historico["origem"]),
                             ("cop", "copa", "mobile"))
            self.assertIn("nome", json.loads(historico["campos_alterados"]))
        ranking = self.chamar(self.adm, "GET", "/api/admin/mapa/atividade?periodo=ano&ano=2026")[1]
        self.assertGreaterEqual(ranking["total"], 1)
        self.assertIn("cop", [x["nome"] for x in ranking["ranking"]])
        self.assertEqual(self.chamar(cop, "GET", "/api/admin/mapa/atividade?periodo=ano&ano=2026")[0], 403)


    def test_configuracoes_exibem_dois_qrs_e_compartilhamento(self):
        cfg = (Path(__file__).resolve().parents[1] / "configuracoes_ui.py").read_text(encoding="utf-8")
        servidor = (Path(__file__).resolve().parents[1] / "mobile" / "servidor.py").read_text(encoding="utf-8")
        self.assertIn("nutrilab-server", cfg)
        self.assertIn("/download/NutriLab-Mobile.apk", cfg)
        self.assertIn("WhatsApp", cfg)
        self.assertIn("mailto:", cfg)
        self.assertIn('u.path == "/download/NutriLab-Mobile.apk"', servidor)
        import qrcode
        qr = qrcode.QRCode()
        qr.add_data("http://192.168.0.10:8765")
        qr.make(fit=True)
        self.assertIsNotNone(qr.make_image().get_image())


    def test_pedido_almox_registra_recebimento_e_prazo_medio(self):
        data_recebimento = "2026-11-12"
        saldo_anterior = self.qtd("almox", data_recebimento)
        with mock.patch.object(sv, "agora_dt",
                               lambda: datetime(2026, 11, 10, 9, 0, tzinfo=sv.TZ)):
            cod, criado = self.chamar(self.adm, "POST", "/api/admin/almox/pedidos",
                                      {"id_item": 1, "qtd": 3, "fornecedor": "Fornecedor teste"})
        self.assertEqual(cod, 200, criado)
        pedido_id = criado["id"]
        cod, lista = self.chamar(self.adm, "GET", "/api/admin/almox/pedidos")
        self.assertEqual(cod, 200)
        self.assertEqual(next(p for p in lista["pedidos"] if p["id"] == pedido_id)["status"], "pendente")
        with mock.patch.object(sv, "agora_dt",
                               lambda: datetime(2026, 11, 12, 10, 0, tzinfo=sv.TZ)):
            cod, recebido = self.chamar(self.adm, "POST",
                                        "/api/admin/almox/pedidos/%d/receber" % pedido_id, {})
        self.assertEqual(cod, 200, recebido)
        self.assertEqual(self.qtd("almox", data_recebimento), saldo_anterior + 3)
        cod, prazos = self.chamar(self.adm, "GET", "/api/admin/almox/prazos")
        self.assertEqual(cod, 200, prazos)
        arroz = next(p for p in prazos["prazos"] if p["id_item"] == 1)
        self.assertEqual(arroz["pedidos_recebidos"], 1)
        self.assertAlmostEqual(arroz["prazo_medio_dias"], 2.0)
        self.assertEqual(arroz["pendentes"], 0)
        cod, negado = self.chamar(self.t["cop"], "GET", "/api/admin/almox/prazos")
        self.assertEqual(cod, 403)


    def test_imagem_de_orientacao_e_compartilhada_e_persiste_apos_atualizacao(self):
        orientacoes = self.chamar(self.adm, "GET", "/api/orientacoes")[1]["orientacoes"]
        dil = next(o for o in orientacoes if o["slug"] == "diluicao")
        # PNG mínimo conhecido; o servidor valida a assinatura e persiste o conteúdo no SQLite.
        png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/pZ8AAAAASUVORK5CYII="
        cod, resposta = self.chamar(self.adm, "POST", "/api/admin/orientacoes/imagem",
                                    {"id": dil["id"], "tipo": "image/png", "imagem_data": png})
        self.assertEqual(cod, 200, resposta)
        self.assertEqual(self.chamar(self.t["cop"], "POST", "/api/admin/orientacoes/imagem",
                                     {"id": dil["id"], "tipo": "image/png", "imagem_data": png})[0], 403)
        salvo = next(o for o in self.chamar(self.t["cop"], "GET", "/api/orientacoes")[1]["orientacoes"]
                     if o["slug"] == "diluicao")
        self.assertEqual((salvo["imagem_tipo"], salvo["imagem_data"]), ("image/png", png))
        # Reexecutar a preparação/migração simula uma atualização do servidor sem perder a mídia.
        sv.preparar_banco(self.db)
        depois = next(o for o in self.chamar(self.adm, "GET", "/api/orientacoes")[1]["orientacoes"]
                      if o["slug"] == "diluicao")
        self.assertEqual((depois["imagem_tipo"], depois["imagem_data"]), ("image/png", png))

    def test_upload_orientacao_rejeita_formato_invalido(self):
        dil = next(o for o in self.chamar(self.adm, "GET", "/api/orientacoes")[1]["orientacoes"]
                   if o["slug"] == "diluicao")
        cod, resposta = self.chamar(self.adm, "POST", "/api/admin/orientacoes/imagem",
                                    {"id": dil["id"], "tipo": "image/png", "imagem_data": "bm90LWEtcG5n"})
        self.assertEqual(cod, 400)
        self.assertIn("formato", resposta["erro"].lower())




if __name__ == "__main__":
    unittest.main()
