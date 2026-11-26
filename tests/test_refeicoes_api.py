"""Integração HTTP/API das refeições individualizadas, com dados sintéticos."""
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from mobile import servidor as sv


class TestRefeicoesAPI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "mobile.db")
        senha = sv.preparar_banco(self.db)
        with sv.conectar(self.db) as conn:
            sessao = sv.login(conn, "127.0.0.1", {"login": "admin", "senha": senha})
        self.token = sessao["token"]

    def api(self, metodo, caminho, corpo=None, query=None):
        return sv.rotear(self.db, "127.0.0.1", metodo, caminho, query or {}, corpo or {},
                         "Bearer " + self.token)

    def test_servico_individual_preserva_paciente_anterior_e_custos(self):
        setor = self.api("POST", "/api/admin/setores",
                         {"nome": "Setor Teste Refeicoes", "codigos": ["R1"]})
        sid = setor["id"]
        mapa = self.api("GET", "/api/mapa", query={"setor": str(sid)})
        lid = mapa["linhas"][0]["id_leito"]
        agora = sv.agora_dt().replace(second=0, microsecond=0)
        t_maria = agora - timedelta(minutes=60)
        t_joao = agora - timedelta(minutes=30)
        dia = agora.date().isoformat()

        for publico in ("paciente", "funcionario"):
            self.api("POST", "/api/refeicoes/janelas",
                     {"publico": publico, "refeicao": "almoco",
                      "inicio": "00:00", "fim": "23:59"})

        self.api("POST", "/api/mapa", {
            "setor": sid, "data": dia, "completo": True,
            "linhas": [{"id_leito": lid, "nome": "Maria",
                        "atualizado_em": t_maria.isoformat()}]})
        lista = self.api("GET", "/api/refeicoes/servicos",
                         query={"setor": str(sid), "data": dia})
        maria = next(x for x in lista["pacientes"] if x["id_leito"] == lid)

        self.api("POST", "/api/mapa", {
            "setor": sid, "data": dia, "completo": True,
            "linhas": [{"id_leito": lid, "nome": "João",
                        "atualizado_em": t_joao.isoformat()}]})
        self.api("POST", "/api/refeicoes/servicos", {
            "setor": sid, "data": dia, "id_leito": lid,
            "id_paciente": maria["id_paciente"], "nome_paciente": "Maria", "leito": "R1",
            "servido_em": (t_maria + timedelta(minutes=15)).isoformat(),
            "publico": "paciente", "refeicao": "almoco", "quantidade": 1,
            "valor_unitario": 8.5})

        atual = self.api("GET", "/api/refeicoes/servicos",
                         query={"setor": str(sid), "data": dia})
        joao = next(x for x in atual["pacientes"] if x["id_leito"] == lid)
        self.assertNotEqual(maria["id_paciente"], joao["id_paciente"])

        auth = self.api("POST", "/api/refeicoes/autorizacoes", {
            "setor": sid, "data": dia, "id_leito": lid, "quantidade": 2,
            "refeicoes": ["almoco"], "justificativa": "Exceção autorizada pela assistência social",
            "inicio_vigencia": t_joao.isoformat(),
            "fim_vigencia": (agora + timedelta(hours=1)).isoformat()})
        self.api("POST", "/api/refeicoes/servicos", {
            "setor": sid, "data": dia, "id_leito": lid,
            "id_paciente": joao["id_paciente"], "servido_em": agora.isoformat(),
            "publico": "acompanhante", "refeicao": "almoco", "quantidade": 2,
            "valor_unitario": 5.0, "id_autorizacao_acompanhante": auth["id_autorizacao"]})
        self.api("POST", "/api/refeicoes/servicos", {
            "setor": sid, "data": dia, "servido_em": agora.isoformat(),
            "publico": "funcionario", "destinatario_nome": "Servidor Teste",
            "refeicao": "almoco", "quantidade": 1, "valor_unitario": 6.0})

        relatorio = self.api("GET", "/api/refeicoes/relatorio",
                             query={"inicio": dia, "fim": dia})
        self.assertAlmostEqual(relatorio["custos"]["pacientes"]["custo"], 8.5)
        self.assertAlmostEqual(relatorio["custos"]["acompanhantes"]["custo"], 10.0)
        self.assertAlmostEqual(relatorio["custos"]["funcionarios"]["custo"], 6.0)
        registro = next(x for x in relatorio["servicos"] if x["publico"] == "paciente")
        self.assertEqual((registro["nome_paciente_snapshot"], registro["leito_snapshot"]),
                         ("Maria", "R1"))

    def test_autorizacao_nao_pode_ser_reutilizada_por_novo_ocupante(self):
        setor = self.api("POST", "/api/admin/setores",
                         {"nome": "Setor Teste Autorizacao", "codigos": ["A1"]})
        sid = setor["id"]
        lid = self.api("GET", "/api/mapa", query={"setor": str(sid)})["linhas"][0]["id_leito"]
        agora = sv.agora_dt().replace(second=0, microsecond=0)
        dia = agora.date().isoformat()
        self.api("POST", "/api/mapa", {
            "setor": sid, "data": dia, "completo": True,
            "linhas": [{"id_leito": lid, "nome": "Paciente Um",
                        "atualizado_em": (agora - timedelta(minutes=5)).isoformat()}]})
        paciente = self.api("GET", "/api/refeicoes/servicos",
                            query={"setor": str(sid), "data": dia})["pacientes"][0]
        auth = self.api("POST", "/api/refeicoes/autorizacoes", {
            "setor": sid, "data": dia, "id_leito": lid, "quantidade": 1,
            "refeicoes": ["almoco"], "justificativa": "Autorização de teste",
            "inicio_vigencia": (agora - timedelta(hours=1)).isoformat()})
        self.api("POST", "/api/mapa", {
            "setor": sid, "data": dia, "completo": True,
            "linhas": [{"id_leito": lid, "nome": "Paciente Dois",
                        "atualizado_em": (agora + timedelta(minutes=1)).isoformat()}]})
        novo = self.api("GET", "/api/refeicoes/servicos",
                        query={"setor": str(sid), "data": dia})["pacientes"][0]
        self.assertNotEqual(paciente["id_paciente"], novo["id_paciente"])
        with self.assertRaisesRegex(sv.Erro, "outro paciente"):
            self.api("POST", "/api/refeicoes/servicos", {
                "setor": sid, "data": dia, "id_leito": lid,
                "id_paciente": novo["id_paciente"],
                "servido_em": (agora + timedelta(minutes=2)).isoformat(),
                "publico": "acompanhante", "refeicao": "almoco", "quantidade": 1,
                "id_autorizacao_acompanhante": auth["id_autorizacao"]})


if __name__ == "__main__":
    unittest.main()
