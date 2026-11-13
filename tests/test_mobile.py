"""Testes do NutriLab Mobile (criado em 12/11/2026). Dados 100% sintéticos; servidor em 127.0.0.1, porta livre."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

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
        cls.chamar(cls.adm, "POST", "/api/admin/setores", {"nome": "Clinica A", "prefixo": "A", "inicio": 1, "fim": 3})
        cls.chamar(cls.adm, "POST", "/api/admin/setores", {"nome": "Clinica B", "codigos": ["B1"]})
        cls.chamar(cls.adm, "POST", "/api/admin/itens", {"nome": "Arroz", "unidade": "kg"})
        for login, perfil, setor in [("sa", "setor", 1), ("copa", "estoque_copa", None),
                                     ("coz", "estoque_cozinha", None), ("alm", "estoque_almox", None)]:
            cod, j = cls.chamar(cls.adm, "POST", "/api/admin/usuarios",
                                {"login": login, "nome": login, "perfil": perfil, "id_setor": setor, "senha": "senha123"})
            assert cod == 200, j
        cls.t = {k: cls.entrar(k, "senha123") for k in ("sa", "copa", "coz", "alm")}

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def leito(self, tok, lid, dia=None):
        cod, j = self.chamar(tok, "GET", "/api/mapa?setor=1" + ("&data=" + dia if dia else ""))
        self.assertEqual(cod, 200, j)
        return next(l for l in j["linhas"] if l["id_leito"] == lid)

    def qtd(self, est):
        cod, j = self.chamar(self.adm, "GET", "/api/estoque?estoque=" + est)
        return j["linhas"][0]["qtd"]

    def test_login_invalido(self):
        cod, _ = self.chamar(None, "POST", "/api/login", {"login": "admin", "senha": "errada"})
        self.assertEqual(cod, 401)

    def test_permissoes_por_perfil(self):
        self.assertEqual(self.chamar(self.t["sa"], "GET", "/api/estoque")[0], 403)
        self.assertEqual(self.chamar(self.t["coz"], "GET", "/api/mapa")[0], 403)
        self.assertEqual(self.chamar(self.t["sa"], "GET", "/api/admin/painel")[0], 403)
        cod, j = self.chamar(self.t["sa"], "GET", "/api/mapa?setor=2")  # pede outro setor: recebe só o seu
        self.assertEqual(j["setor"]["id"], 1)
        cod, j = self.chamar(self.t["copa"], "GET", "/api/estoque?estoque=almox")  # pede outro estoque: recebe só o seu
        self.assertEqual(j["estoque"], "copa")

    def test_usuario_comum_so_grava_no_proprio_dia(self):
        hoje = sv.hoje()
        ontem = (date.fromisoformat(hoje) - timedelta(days=1)).isoformat()
        corpo = {"data": ontem, "linhas": [{"id_leito": 1, "ocupado": True, "acompanhante": False, "dieta": "Geral"}]}
        self.assertEqual(self.chamar(self.t["sa"], "POST", "/api/mapa", corpo)[0], 200)
        self.assertIsNone(self.leito(self.adm, 1, ontem)["data_base"])  # nada gravado em "ontem"
        self.assertEqual(self.leito(self.t["sa"], 1)["data_base"], hoje)

    def test_comeca_pela_base_do_dia_anterior(self):
        ontem = (date.fromisoformat(sv.hoje()) - timedelta(days=1)).isoformat()
        self.chamar(self.adm, "POST", "/api/mapa", {"setor": 1, "data": ontem,
                    "linhas": [{"id_leito": 2, "ocupado": True, "acompanhante": True, "dieta": "Branda"}]})
        l = self.leito(self.t["sa"], 2)
        self.assertEqual((l["ocupado"], l["acompanhante"], l["dieta"], l["herdado"]), (1, 1, "Branda", True))

    def test_correcao_do_usuario_precisa_de_autorizacao_do_admin(self):
        self.chamar(self.adm, "POST", "/api/mapa", {"setor": 1, "linhas": [{"id_leito": 3, "ocupado": True, "dieta": "Geral"}]})
        cod, r = self.chamar(self.t["sa"], "POST", "/api/mapa", {"linhas": [{"id_leito": 3, "ocupado": False}]})
        self.assertEqual(r["pendente"], 1)
        self.assertEqual(self.leito(self.t["sa"], 3)["ocupado"], 1)  # nada foi sobrescrito
        cod, j = self.chamar(self.adm, "GET", "/api/admin/correcoes")
        k = next(x for x in j["correcoes"] if "A03" in x["rotulo"])
        self.assertEqual(k["valor_atual"]["ocupado"], 1)
        self.assertEqual(self.chamar(self.adm, "POST", "/api/admin/correcoes/%d" % k["id"], {"acao": "aprovar"})[0], 200)
        self.assertEqual(self.leito(self.t["sa"], 3)["ocupado"], 0)

    def test_hierarquia_almox_cozinha_copa(self):
        rep = lambda t, est, org, q: self.chamar(self.t[t], "POST", "/api/estoque/reposicao", {"id_item": 1, "qtd": q, "origem": org})[0]
        self.chamar(self.adm, "POST", "/api/estoque", {"estoque": "almox", "linhas": [{"id_item": 1, "qtd": 10}]})
        self.assertEqual(rep("coz", "cozinha", "cozinha", 1), 400)  # cozinha só recebe do almoxarifado
        self.assertEqual(rep("coz", "cozinha", "almox", 4), 200)
        self.assertEqual((self.qtd("almox"), self.qtd("cozinha")), (6, 4))
        self.assertEqual(rep("copa", "copa", "almox", 1), 400)  # cozinha ainda tem: pegar primeiro lá
        self.assertEqual(rep("copa", "copa", "cozinha", 4), 200)
        self.assertEqual(rep("copa", "copa", "almox", 2), 200)  # cozinha zerou: pode ir ao almoxarifado
        self.assertEqual((self.qtd("almox"), self.qtd("cozinha"), self.qtd("copa")), (4, 0, 6))
        self.assertEqual(rep("alm", "almox", "cozinha", 1), 400)  # almoxarifado só recebe de fora
        self.assertEqual(rep("alm", "almox", "externo", 5), 200)
        self.assertEqual(self.qtd("almox"), 9)


if __name__ == "__main__":
    unittest.main()
