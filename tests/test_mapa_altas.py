# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

import mapa_db as mdb
import mapa_graficos as mg


class TestAltasMapa(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(self.db) and os.remove(self.db))
        mdb.inicializar(self.db)
        sid = mdb.criar_setor(self.db, "Teste")
        mdb.criar_leitos_sequencia(self.db, sid, "A", 1, 1)
        self.leito = mdb.listar_leitos(self.db, sid)[0]["id_leito"]

    def test_paciente_permanece_no_dia_seguinte_sem_alta(self):
        mdb.salvar_registro(self.db, {"data": "2026-11-23", "id_leito": self.leito,
                                      "nome_paciente": "Maria", "idade_anos": 50})
        self.assertIsNotNone(mdb.obter_registro(self.db, "2026-11-23", self.leito))
        self.assertEqual(mdb.listar_leitos(self.db)[0]["ativo"], 1)
        self.assertIsNone(mdb.obter_registro(self.db, "2026-11-23", self.leito).get("alta_em"))
        debug_mapa = mdb.mapa_do_dia(self.db, "2026-11-24")
        r = next(x["registro"] for x in debug_mapa if x["leito"]["id_leito"] == self.leito)
        self.assertEqual(r["nome_paciente"], "Maria")
        self.assertEqual(r["data"], "2026-11-23")
        self.assertEqual(r["data_exibicao"], "2026-11-24")

    def test_alta_remove_do_mapa_mas_preserva_historico(self):
        mdb.salvar_registro(self.db, {"data": "2026-11-23", "id_leito": self.leito,
                                      "nome_paciente": "Maria", "idade_anos": 50})
        r = next(x["registro"] for x in mdb.mapa_do_dia(self.db, "2026-11-24") if x["leito"]["id_leito"] == self.leito)
        mdb.registrar_alta(self.db, r, por="teste", quando="2026-11-24 09:30:00")
        self.assertIsNone(next(x["registro"] for x in mdb.mapa_do_dia(self.db, "2026-11-24") if x["leito"]["id_leito"] == self.leito))
        hist = mdb.historico_paciente(self.db, nome="Maria")
        self.assertEqual(hist[0]["alta_em"], "2026-11-24 09:30:00")
        self.assertEqual(hist[0]["alta_por"], "teste")

    def test_grafico_conta_alta_na_data_da_alta(self):
        mdb.salvar_registro(self.db, {"data": "2026-11-23", "id_leito": self.leito,
                                      "nome_paciente": "Maria", "idade_anos": 50})
        r = mdb.obter_registro(self.db, "2026-11-23", self.leito)
        mdb.registrar_alta(self.db, r, por="teste", quando="2026-11-24 09:30:00")
        registros = mdb.registros_do_mes(self.db, 2026, 11)
        agg = mg.agregar_mes(registros, 2026, 11)
        self.assertEqual(agg["dias"][24]["altas"], 1)
        self.assertEqual(agg["kpis"]["altas"], 1)


if __name__ == "__main__":
    unittest.main()
