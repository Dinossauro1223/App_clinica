# -*- coding: utf-8 -*-
"""Testes sintéticos para horários, autorização social e histórico de refeições."""
import tempfile
import unittest
from pathlib import Path

import refeicoes_db as rd


class TestRefeicoesPorPublico(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "refeicoes.db")
        rd.inicializar(self.db)

    def test_janelas_sao_independentes_por_publico_e_refeicao(self):
        self.assertEqual(rd.listar_janelas(self.db), [])
        rd.salvar_janela(self.db, "paciente", "almoco", "11:00", "13:00")
        rd.salvar_janela(self.db, "funcionario", "almoco", "12:00", "14:00")
        self.assertEqual(rd.listar_janelas(self.db, "paciente")[0]["inicio"], "11:00")
        self.assertEqual(rd.listar_janelas(self.db, "funcionario")[0]["inicio"], "12:00")
        with self.assertRaises(ValueError):
            rd.salvar_janela(self.db, "acompanhante", "almoco", "11:00", "13:00")

    def test_nao_aceita_janela_invalida_ou_sem_duracao(self):
        with self.assertRaises(ValueError):
            rd.salvar_janela(self.db, "paciente", "almoco", "11h", "13:00")
        with self.assertRaises(ValueError):
            rd.salvar_janela(self.db, "paciente", "almoco", "11:00", "11:00")

    def test_horario_fora_da_janela_nao_registra_refeicao(self):
        rd.salvar_janela(self.db, "paciente", "almoco", "11:00", "13:00")
        with self.assertRaisesRegex(ValueError, "fora da janela"):
            rd.registrar_refeicao_servida(
                self.db, servido_em="2026-11-25T13:30:00", refeicao="almoco",
                publico="paciente", destinatario_nome="Maria", id_paciente="internacao-1",
                nome_paciente="Maria", leito="12", valor_unitario=8.5
            )
        self.assertEqual(rd.listar_refeicoes_servidas(self.db, "2026-11-25", "2026-11-25"), [])

    def test_historico_preserva_paciente_e_leito_apos_troca_de_ocupante(self):
        rd.salvar_janela(self.db, "paciente", "almoco", "11:00", "14:00")
        rd.salvar_janela(self.db, "paciente", "lanche", "14:00", "16:00")
        rd.registrar_refeicao_servida(
            self.db, servido_em="2026-11-25T11:30:00", refeicao="almoco",
            publico="paciente", destinatario_nome="Maria", id_paciente="internacao-M",
            nome_paciente="Maria de Souza", leito="12", valor_unitario=8.0
        )
        # O leito agora tem outro paciente; o evento antigo não depende do mapa atual.
        rd.registrar_refeicao_servida(
            self.db, servido_em="2026-11-25T15:00:00", refeicao="lanche",
            publico="paciente", destinatario_nome="João", id_paciente="internacao-J",
            nome_paciente="João de Souza", leito="12", valor_unitario=3.0
        )
        eventos = rd.listar_refeicoes_servidas(self.db, "2026-11-25", "2026-11-25")
        self.assertEqual([(e["nome_paciente_snapshot"], e["leito_snapshot"]) for e in eventos],
                         [("Maria de Souza", "12"), ("João de Souza", "12")])
        self.assertEqual([e["custo_total_snapshot"] for e in eventos], [8.0, 3.0])

    def test_custo_separado_em_pacientes_funcionarios_e_acompanhantes(self):
        rd.salvar_janela(self.db, "paciente", "almoco", "11:00", "14:00")
        rd.salvar_janela(self.db, "funcionario", "almoco", "12:00", "14:00")
        comum = dict(servido_em="2026-11-25T12:30:00", refeicao="almoco",
                     quantidade=2, valor_unitario=5.0)
        rd.registrar_refeicao_servida(
            self.db, **comum, publico="paciente", destinatario_nome="Paciente",
            id_paciente="P1", nome_paciente="Paciente", leito="1"
        )
        rd.registrar_refeicao_servida(
            self.db, **comum, publico="funcionario", destinatario_nome="Funcionário"
        )
        auth = rd.salvar_autorizacao_acompanhante(
            self.db, id_paciente="P1", nome_paciente="Paciente", leito="1",
            quantidade=2, refeicoes=["almoco"], justificativa="Acompanhante com necessidade autorizada",
            autorizado_por="Assistência social", inicio_vigencia="2026-11-25T08:00:00",
            fim_vigencia="2026-11-25T18:00:00"
        )
        rd.registrar_refeicao_servida(
            self.db, **comum, publico="acompanhante", destinatario_nome="Acompanhantes",
            id_paciente="P1", id_autorizacao_acompanhante=auth
        )
        resumo = rd.resumo_custos(self.db, "2026-11-25", "2026-11-25")
        self.assertEqual(set(resumo), {"pacientes", "funcionarios", "acompanhantes"})
        self.assertEqual({k: v["custo"] for k, v in resumo.items()},
                         {"pacientes": 10.0, "funcionarios": 10.0, "acompanhantes": 10.0})

    def test_acompanhante_precisa_de_autorizacao_vigente_do_mesmo_paciente(self):
        auth = rd.salvar_autorizacao_acompanhante(
            self.db, id_paciente="P1", nome_paciente="Paciente 1", leito="8",
            quantidade=1, refeicoes=["almoco"], justificativa="Indicação social",
            autorizado_por="Assistente social", inicio_vigencia="2026-11-25T08:00:00"
        )
        base = dict(servido_em="2026-11-25T12:00:00", refeicao="almoco",
                    publico="acompanhante", destinatario_nome="Acompanhante",
                    id_autorizacao_acompanhante=auth)
        with self.assertRaisesRegex(ValueError, "outro paciente"):
            rd.registrar_refeicao_servida(
                self.db, **base, id_paciente="P2"
            )
        with self.assertRaisesRegex(ValueError, "não está coberto"):
            rd.registrar_refeicao_servida(
                self.db, **{**base, "refeicao": "colacao"}, id_paciente="P1"
            )
        with self.assertRaisesRegex(ValueError, "excede"):
            rd.registrar_refeicao_servida(
                self.db, **base, id_paciente="P1", quantidade=2
            )
        self.assertEqual(rd.listar_refeicoes_servidas(self.db, "2026-11-25", "2026-11-25"), [])

    def test_encerrar_autorizacao_impede_novos_registros(self):
        auth = rd.salvar_autorizacao_acompanhante(
            self.db, id_paciente="P1", nome_paciente="Paciente", leito="2",
            quantidade=1, refeicoes=["almoco"], justificativa="Exceção",
            autorizado_por="Assistência social", inicio_vigencia="2026-11-25T08:00:00"
        )
        self.assertTrue(rd.encerrar_autorizacao_acompanhante(self.db, auth))
        self.assertFalse(rd.encerrar_autorizacao_acompanhante(self.db, auth))
        with self.assertRaisesRegex(ValueError, "inexistente ou inativa"):
            rd.registrar_refeicao_servida(
                self.db, servido_em="2026-11-25T12:00:00", refeicao="almoco",
                publico="acompanhante", destinatario_nome="Acompanhante",
                id_paciente="P1", id_autorizacao_acompanhante=auth
            )


if __name__ == "__main__":
    unittest.main()
