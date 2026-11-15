"""Testes do NutriLab Mobile (criado em 12/11/2026). Dados 100% sintéticos; servidor em 127.0.0.1, porta livre."""
import json
import tempfile
import threading
import unittest
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

    def qtd(self, est):
        return self.chamar(self.adm, "GET", "/api/estoque?estoque=" + est)[1]["linhas"][0]["qtd"]

    # ------------------------------------------------------------------ testes
    def test_login_invalido(self):
        self.assertEqual(self.chamar(None, "POST", "/api/login", {"login": "admin", "senha": "errada"})[0], 401)

    def test_permissoes_por_perfil(self):
        t = self.t
        self.assertEqual(self.chamar(t["cop"], "GET", "/api/nutri/painel")[0], 403)
        self.assertEqual(self.chamar(t["cop"], "POST", "/api/nutri/publicar", {"setor": 1})[0], 403)
        self.assertEqual(self.chamar(t["cop"], "POST", "/api/nutri/janelas", {"refeicao": "almoco", "abre": "10:00", "fecha": "11:00"})[0], 403)
        self.assertEqual(self.chamar(t["coz"], "GET", "/api/mapa")[0], 403)
        self.assertEqual(self.chamar(t["nut"], "GET", "/api/estoque")[0], 403)
        self.assertEqual(self.chamar(t["cop"], "GET", "/api/mapa?setor=2")[1]["setor"]["id"], 1)  # pede outro setor: recebe o seu
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
        self.assertEqual(self.chamar(cop2, "GET", "/api/avisos")[1]["avisos"], [])  # outro setor não recebe
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
        self.assertEqual(rep("alm", "cozinha", 1), 400)  # almoxarifado só recebe de fora
        self.assertEqual(rep("alm", "externo", 5), 200)
        self.assertEqual(self.qtd("almox"), 9)


if __name__ == "__main__":
    unittest.main()
