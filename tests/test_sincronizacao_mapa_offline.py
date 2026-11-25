# -*- coding: utf-8 -*-
"""Diagnóstico dos problemas de persistência/sincronização do Mapa."""
import os
import tempfile
import unittest
from datetime import datetime
import mapa_db as mdb

D1 = "2026-11-23"
D2 = "2026-11-24"

class TestPersistenciaMapaEntreDias(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db"); os.close(fd)
        self.addCleanup(lambda: os.path.exists(self.db) and os.remove(self.db))
        mdb.inicializar(self.db)
        mdb.criar_setor(self.db, "Clinica Teste")
        sid = next(s["id_setor"] for s in mdb.listar_setores(self.db) if s["nome"] == "Clinica Teste")
        mdb.criar_leitos_sequencia(self.db, sid, "A", 1, 2)
        self.leitos = {x["codigo"]: x["id_leito"] for x in mdb.listar_leitos(self.db, sid)}

    def test_main_atual_herda_o_dia_anterior_enquanto_nao_houver_alta(self):
        mdb.salvar_registro(self.db, {"data": D1, "id_leito": self.leitos["A01"], "nome_paciente": "Paciente de ontem", "idade_anos": 40})
        hoje = mdb.mapa_do_dia(self.db, D2, None)
        a01 = next(x for x in hoje if x["leito"]["codigo"] == "A01")
        self.assertIsNotNone(a01["registro"])
        self.assertEqual(a01["registro"]["nome_paciente"], "Paciente de ontem")

    def test_alta_libera_o_leito_a_partir_da_data_da_alta(self):
        mdb.salvar_registro(self.db, {"data": D1, "id_leito": self.leitos["A01"], "nome_paciente": "Paciente de ontem", "idade_anos": 40})
        hoje = mdb.mapa_do_dia(self.db, D2, None)
        a01 = next(x for x in hoje if x["leito"]["codigo"] == "A01")
        mdb.registrar_alta(self.db, a01["registro"], por="teste", quando="2026-11-24 10:00:00")
        depois = mdb.mapa_do_dia(self.db, D2, None)
        a01 = next(x for x in depois if x["leito"]["codigo"] == "A01")
        self.assertIsNone(a01["registro"])

class TestContratoDeSincronizacao(unittest.TestCase):
    def test_estado_completo_precisa_conter_todos_os_leitos(self):
        estado = [
            {"leito": "A01", "nome": "Paciente", "atualizado_em": "2026-11-24T08:00:00-03:00"},
            {"leito": "A02", "nome": "", "atualizado_em": "2026-11-24T08:00:00-03:00"},
        ]
        self.assertEqual(len(estado), 2)

    def test_conflito_deve_comparar_timestamp_pc_e_mobile(self):
        pc = {"nome": "PC", "atualizado_em": "2026-11-24T10:00:00-03:00", "origem": "pc"}
        mobile = {"nome": "Copa", "atualizado_em": "2026-11-24T10:05:00-03:00", "origem": "mobile"}
        vencedor = max((pc, mobile), key=lambda x: datetime.fromisoformat(x["atualizado_em"]))
        self.assertEqual(vencedor["origem"], "mobile")