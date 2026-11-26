"""Integração HTTP/API das refeições individualizadas, com dados sintéticos."""
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from mobile import servidor as sv


class TestRefeicoesAPI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "mobile.db")
        senha = sv.preparar_banco(self.db)
        conn = sv.conectar(self.db)
        try:
            sessao = sv.login(conn, "127.0.0.1", {"login": "admin", "senha": senha})
        finally:
            conn.close()
        self.token = sessao["token"]

    def api(self, metodo, caminho, corpo=None, query=None, token=None):
        return sv.rotear(self.db, "127.0.0.1", metodo, caminho, query or {}, corpo or {},
                         "Bearer " + (token or self.token))

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
        self.api("POST", "/api/refeicoes/precos", {
            "publico": "funcionario", "refeicao": "almoco", "valor_unitario": 6.0})
        self.api("POST", "/api/refeicoes/servicos", {
            "setor": sid, "data": dia, "servido_em": agora.isoformat(),
            "publico": "funcionario", "destinatario_nome": "Servidor Teste",
            "refeicao": "almoco", "quantidade": 1})

        relatorio = self.api("GET", "/api/refeicoes/relatorio",
                             query={"inicio": dia, "fim": dia})
        self.assertAlmostEqual(relatorio["custos"]["pacientes"]["custo"], 8.5)
        self.assertAlmostEqual(relatorio["custos"]["acompanhantes"]["custo"], 10.0)
        self.assertAlmostEqual(relatorio["custos"]["funcionarios"]["custo"], 6.0)
        registro = next(x for x in relatorio["servicos"] if x["publico"] == "paciente")
        self.assertEqual((registro["nome_paciente_snapshot"], registro["leito_snapshot"]),
                         ("Maria", "R1"))


    def test_copa_sincroniza_refeicao_offline_com_data_original(self):
        setor = self.api("POST", "/api/admin/setores",
                         {"nome": "Setor Teste Offline Refeicoes", "codigos": ["O1"]})
        sid = setor["id"]
        lid = self.api("GET", "/api/mapa", query={"setor": str(sid)})["linhas"][0]["id_leito"]
        hoje = sv.agora_dt().replace(second=0, microsecond=0)
        ontem = hoje.date() - timedelta(days=1)
        dia = ontem.isoformat()
        servida_em = (datetime.combine(ontem, datetime.min.time()).replace(
            hour=12, tzinfo=sv.TZ)).isoformat()
        self.api("POST", "/api/refeicoes/janelas", {
            "publico": "paciente", "refeicao": "almoco", "inicio": "00:00", "fim": "23:59"})
        self.api("POST", "/api/refeicoes/precos", {
            "publico": "paciente", "refeicao": "almoco", "valor_unitario": 7.25})
        self.api("POST", "/api/mapa", {
            "setor": sid, "data": dia, "completo": True,
            "linhas": [{"id_leito": lid, "nome": "Paciente Offline",
                        "id_ocupacao": "offline:teste-paciente",
                        "atualizado_em": datetime.fromisoformat(servida_em).replace(hour=8).isoformat()}]})

        self.api("POST", "/api/admin/usuarios", {
            "login": "copa_offline_teste", "nome": "Copa Offline",
            "perfil": "copa", "id_setor": sid, "senha": "senha123"})
        conn = sv.conectar(self.db)
        try:
            sessao = sv.login(conn, "127.0.0.1",
                              {"login": "copa_offline_teste", "senha": "senha123"})
        finally:
            conn.close()
        token_copa = sessao["token"]
        dados = self.api("GET", "/api/refeicoes/servicos",
                         query={"setor": str(sid)}, token=token_copa)
        paciente = next(x for x in dados["pacientes"] if x["id_leito"] == lid)

        # Simula sincronização no dia seguinte: a data/hora original não pode ser substituída por hoje.
        resultado = self.api("POST", "/api/refeicoes/servicos", {
            "setor": sid, "data": sv.hoje(), "id_leito": lid,
            "id_paciente": paciente["id_paciente"], "servido_em": servida_em,
            "publico": "paciente", "refeicao": "almoco", "quantidade": 1
        }, token=token_copa)
        self.assertTrue(resultado["ok"])
        relatorio = self.api("GET", "/api/refeicoes/relatorio",
                             query={"inicio": dia, "fim": dia})
        self.assertAlmostEqual(relatorio["custos"]["pacientes"]["custo"], 7.25)
        self.assertEqual(relatorio["servicos"][0]["data_refeicao"], dia)


    def test_autorizacao_acompanha_id_paciente_ao_trocar_de_leito(self):
        setor = self.api("POST", "/api/admin/setores",
                         {"nome": "Setor Teste Transferencia", "codigos": ["T1", "T2"]})
        sid = setor["id"]
        leitos = self.api("GET", "/api/mapa", query={"setor": str(sid)})["linhas"]
        l1, l2 = leitos[0]["id_leito"], leitos[1]["id_leito"]
        agora = sv.agora_dt().replace(second=0, microsecond=0)
        dia = agora.date().isoformat()
        self.api("POST", "/api/refeicoes/precos", {
            "publico": "acompanhante", "refeicao": "almoco", "valor_unitario": 4.5})
        self.api("POST", "/api/mapa", {
            "setor": sid, "data": dia, "completo": True,
            "linhas": [{"id_leito": l1, "id_paciente": 98765, "nome": "Paciente Transferido",
                        "atualizado_em": (agora - timedelta(minutes=20)).isoformat()}]})
        autorizacao = self.api("POST", "/api/refeicoes/autorizacoes", {
            "setor": sid, "data": dia, "id_leito": l1, "quantidade": 1,
            "refeicoes": ["almoco"], "justificativa": "Acompanhante autorizado",
            "inicio_vigencia": (agora - timedelta(hours=1)).isoformat()})
        self.api("POST", "/api/mapa", {
            "setor": sid, "data": dia, "completo": True,
            "linhas": [
                {"id_leito": l1, "nome": "", "ocupado": 0,
                 "atualizado_em": (agora - timedelta(minutes=5)).isoformat()},
                {"id_leito": l2, "id_paciente": 98765, "nome": "Paciente Transferido",
                 "atualizado_em": (agora - timedelta(minutes=5)).isoformat()}
            ]})
        atuais = self.api("GET", "/api/refeicoes/servicos",
                          query={"setor": str(sid), "data": dia})["pacientes"]
        paciente_novo_leito = next(x for x in atuais if x["id_leito"] == l2)
        servico = self.api("POST", "/api/refeicoes/servicos", {
            "setor": sid, "data": dia, "id_leito": l2,
            "id_paciente": paciente_novo_leito["id_paciente"],
            "servido_em": agora.isoformat(), "publico": "acompanhante",
            "refeicao": "almoco", "quantidade": 1,
            "id_autorizacao_acompanhante": autorizacao["id_autorizacao"]})
        self.assertTrue(servico["ok"])
        relatorio = self.api("GET", "/api/refeicoes/relatorio",
                             query={"inicio": dia, "fim": dia})
        self.assertEqual(relatorio["servicos"][0]["leito_snapshot"], "T2")

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
                "valor_unitario": 5.0,
                "id_autorizacao_acompanhante": auth["id_autorizacao"]})


if __name__ == "__main__":
    unittest.main()
