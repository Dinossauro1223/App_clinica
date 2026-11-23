# -*- coding: utf-8 -*-
"""Fluxo HTTP real do celular até o banco clínico do desktop, só com dados sintéticos."""
import json
import tempfile
import threading
import urllib.error
import urllib.request
import unittest
from contextlib import closing
from pathlib import Path

from mobile import servidor as sv
import integracao_mobile as im
import mapa_db as mdb


class TestMobileHttpAteDesktop(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nutrilab-mobile-e2e-")
        self.addCleanup(self.tmp.cleanup)
        self.mobile_db = str(Path(self.tmp.name) / "mobile.db")
        self.desktop_db = str(Path(self.tmp.name) / "clinica.db")
        senha = sv.preparar_banco(self.mobile_db)
        self.server = sv.criar_servidor(self.mobile_db, 0, "127.0.0.1")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._parar_servidor)
        self.base = "http://127.0.0.1:%d" % self.server.server_address[1]
        self.admin = self._post("/api/login", {"login": "admin", "senha": senha})["token"]
        setor = self._post("/api/admin/setores", {
            "nome": "Clinica E2E", "prefixo": "E", "inicio": 1, "fim": 2
        }, self.admin)
        self.id_setor = setor["id"]
        self._post("/api/admin/usuarios", {
            "login": "copa_e2e", "nome": "Copa de teste", "perfil": "copa",
            "id_setor": self.id_setor, "senha": "senha123"
        }, self.admin)
        self.copa = self._post("/api/login", {
            "login": "copa_e2e", "senha": "senha123"
        })["token"]

        with closing(sv.conectar(self.mobile_db)) as conexao:
            conexao.execute(
                "INSERT OR REPLACE INTO suplementos_catalogo"
                "(id_suplemento,nome,modulo,emb_qtd,emb_un,ativo) "
                "VALUES(9901,'Suplemento E2E','Fórmula completa',200,'ml',1)"
            )
            conexao.commit()

        mdb.inicializar(self.desktop_db)
        mdb.criar_setor(self.desktop_db, "Clinica E2E")
        setor_desktop = next(
            s for s in mdb.listar_setores(self.desktop_db) if s["nome"] == "Clinica E2E"
        )
        mdb.criar_leitos_sequencia(self.desktop_db, setor_desktop["id_setor"], "E", 1, 2)
        mdb.salvar_config(self.desktop_db, "mobile_db", self.mobile_db)

    def _parar_servidor(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def _chamar(self, metodo, caminho, corpo=None, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8") if corpo is not None else None
        req = urllib.request.Request(self.base + caminho, data=dados, method=metodo, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resposta:
                return resposta.status, json.loads(resposta.read().decode("utf-8"))
        except urllib.error.HTTPError as erro:
            return erro.code, json.loads(erro.read().decode("utf-8"))

    def _post(self, caminho, corpo, token=None):
        codigo, dados = self._chamar("POST", caminho, corpo, token)
        self.assertEqual(codigo, 200, dados)
        return dados

    def test_apk_http_envia_mapa_e_desktop_importa_no_banco_clinico(self):
        dia = sv.hoje()
        codigo, catalogo = self._chamar("GET", "/api/suplementos", token=self.copa)
        self.assertEqual(codigo, 200, catalogo)
        self.assertTrue(any(x["id_suplemento"] == 9901 for x in catalogo["suplementos"]))

        codigo, mapa = self._chamar(
            "GET", "/api/mapa?setor=%d&data=%s" % (self.id_setor, dia), token=self.copa
        )
        self.assertEqual(codigo, 200, mapa)
        leito = next(x for x in mapa["linhas"] if x["codigo"] == "E01")
        corpo = {
            "setor": self.id_setor,
            "data": dia,
            "linhas": [{
                "id_leito": leito["id_leito"],
                "nome": "Paciente Sintético E2E",
                "idade_anos": 42,
                "idade_meses": 3,
                "cor": "B",
                "via": "Oral",
                "consistencia": "Pastosa",
                "dm": True,
                "has": False,
                "laxativa": False,
                "constipante": True,
                "drc": False,
                "suplementos": [{
                    "id_suplemento": 9901,
                    "nome": "Suplemento E2E",
                    "modulo": "Fórmula completa",
                    "ml_oferta": 150,
                    "agua_ml": 25,
                    "refeicoes": ["desjejum", "ceia"],
                    "batido_fruta": True
                }]
            }]
        }
        codigo, recebido = self._chamar("POST", "/api/mapa", corpo, self.copa)
        self.assertEqual(codigo, 200, recebido)

        # É o mesmo arquivo mobile.db que o servidor local grava e o painel desktop consulta.
        self.assertEqual(im.caminho_mobile_db(self.desktop_db, str(Path(__file__).resolve().parents[1])),
                         self.mobile_db)
        exportado = im.ler_mobile(self.mobile_db, dia)
        propostas = im.propostas_mapa(self.desktop_db, exportado)
        self.assertEqual(len(propostas), 1)
        resultado = im.aplicar_mapa(self.desktop_db, propostas)
        self.assertEqual((resultado["aplicados"], resultado["erros"]), (1, []))

        registro = mdb.obter_registro(
            self.desktop_db, dia,
            next(l["id_leito"] for l in mdb.listar_leitos(
                self.desktop_db,
                next(s["id_setor"] for s in mdb.listar_setores(self.desktop_db)
                     if s["nome"] == "Clinica E2E")
            ) if l["codigo"] == "E01")
        )
        self.assertEqual(
            (registro["nome_paciente"], registro["idade_anos"], registro["idade_meses"],
             registro["cor"], registro["via"], registro["consistencia"], registro["dm"],
             registro["constipante"]),
            ("Paciente Sintético E2E", 42, 3, "B", "Oral", "Pastosa", 1, 1)
        )
        suplemento = registro["suplementos"][0]
        self.assertEqual(
            (suplemento["nome"], suplemento["ml_oferta"], suplemento["agua_ml"],
             suplemento["refeicoes"], suplemento["batido_fruta"]),
            ("Suplemento E2E", 150.0, 25.0, ["desjejum", "ceia"], 1)
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
