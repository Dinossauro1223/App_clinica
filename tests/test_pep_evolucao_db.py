import os
import sqlite3
import tempfile
import unittest
from contextlib import closing

import db_migracoes
import pep_db
import pep_evolucao_db as evdb


class TestPepEvolucaoDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "pep.db")
        db_migracoes.aplicar_migracoes(self.db, backup=False)
        with closing(sqlite3.connect(self.db)) as c:
            c.execute("CREATE TABLE Pacientes (id_paciente INTEGER PRIMARY KEY, nome TEXT NOT NULL, data_nascimento TEXT, sexo TEXT)")
            c.execute("INSERT INTO Pacientes VALUES (1, 'Paciente Sintético', '01/01/1954', 'F')")
            c.commit()
        self.uid = pep_db.criar_usuario(self.db, "nutri", "Nutricionista Teste", "CRN-6 1234", "senha-forte-123")

    def tearDown(self):
        self.tmp.cleanup()

    def _nutri(self, crn_conferido=True):
        return evdb.cadastrar_membro(
            self.db, "Nutricionista Teste", "nutricionista", crn="CRN-6 1234",
            crn_conferido=crn_conferido, id_usuario=self.uid)

    def _intern(self):
        return evdb.cadastrar_membro(self.db, "Estagiário Teste", "estagiario")

    def _dados(self):
        return {
            "antropometria": {
                "data": "25/11/2026", "idade_anos": 72, "altura_m": 1.65, "altura_origem": "A",
                "peso_kg": 62, "peso_origem": "A", "imc_class": "Eutrofia"
            },
            "via": "Oral", "dva": False, "tno": "Regular",
            "dieta_oral": {"consistencia": "Branda", "caracteristicas": ["DM", "HAS"]},
            "observacoes": "Observação sintética", "conduta": "Conduta sintética"
        }

    def test_cadastra_e_lista_equipe(self):
        nutri = self._nutri()
        est = self._intern()
        self.assertEqual(evdb.listar_equipe(self.db, "nutricionista")[0]["id_membro"], nutri)
        self.assertEqual(evdb.listar_equipe(self.db, "estagiario")[0]["id_membro"], est)

    def test_nutricionista_exige_crn_conferido_e_conta_vinculada(self):
        with self.assertRaises(ValueError):
            self._nutri(crn_conferido=False)
        with self.assertRaises(ValueError):
            evdb.cadastrar_membro(self.db, "Nutri", "nutricionista", crn="123", crn_conferido=True, id_usuario=self.uid)

    def test_estagiario_nao_pode_receber_conta_de_fechamento(self):
        with self.assertRaises(ValueError):
            evdb.cadastrar_membro(self.db, "Estagiário", "estagiario", id_usuario=self.uid)

    def test_salva_rascunho_com_historico_append_only(self):
        est = self._intern()
        rid = evdb.salvar_rascunho(self.db, 1, "25/11/2026", self._dados(), est)
        evdb.salvar_rascunho(self.db, 1, "25/11/2026", self._dados() | {"observacoes": "Atualizada"}, est, rid)
        self.assertEqual(len(evdb.historico_rascunho(self.db, rid)), 2)
        with closing(sqlite3.connect(self.db)) as c:
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("UPDATE Pep_Rascunho_Historico SET acao='alterada' WHERE id_rascunho=?", (rid,))
            c.rollback()

    def test_estagiario_nao_fecha_sem_autenticacao_nutricionista(self):
        est = self._intern()
        rid = evdb.salvar_rascunho(self.db, 1, "25/11/2026", self._dados(), est)
        with self.assertRaises(evdb.EvolucaoPEPError):
            evdb.fechar_rascunho(self.db, rid, self.uid, "senha-errada", confirmado=True)
        self.assertEqual(evdb.obter_rascunho(self.db, rid)["status"], "rascunho")

    def test_fechar_exige_confirmacao_explicita(self):
        est = self._intern()
        self._nutri()
        rid = evdb.salvar_rascunho(self.db, 1, "25/11/2026", self._dados(), est)
        with self.assertRaises(evdb.EvolucaoPEPError):
            evdb.fechar_rascunho(self.db, rid, self.uid, "senha-forte-123", confirmado=False)

    def test_fecha_e_grava_evolucao_estruturada_com_autoria(self):
        est = self._intern()
        self._nutri()
        rid = evdb.salvar_rascunho(self.db, 1, "25/11/2026", self._dados(), est)
        eid = evdb.fechar_rascunho(self.db, rid, self.uid, "senha-forte-123", confirmado=True)
        self.assertEqual(evdb.obter_rascunho(self.db, rid)["status"], "fechada")
        with closing(sqlite3.connect(self.db)) as c:
            row = c.execute(
                "SELECT paciente_nome, texto, assinante_nome, assinante_crn, elaborador_nome, fechada_em, dados_json "
                "FROM Pep_Evolucoes WHERE id_evolucao=?", (eid,)).fetchone()
            self.assertEqual(row[0], "Paciente Sintético")
            self.assertIn("TNO: Regular (75% de consumo estimado)", row[1])
            self.assertIn("Observações: Observação sintética", row[1])
            self.assertEqual(row[2:5], ("Nutricionista Teste", "CRN-6 1234", "Estagiário Teste"))
            self.assertTrue(row[5])
            self.assertIn('"via": "Oral"', row[6])

    def test_evolucao_fechada_e_inalteravel(self):
        est = self._intern()
        self._nutri()
        rid = evdb.salvar_rascunho(self.db, 1, "25/11/2026", self._dados(), est)
        evdb.fechar_rascunho(self.db, rid, self.uid, "senha-forte-123", confirmado=True)
        with self.assertRaises(evdb.EvolucaoPEPError):
            evdb.salvar_rascunho(self.db, 1, "25/11/2026", self._dados(), est, rid)
        with closing(sqlite3.connect(self.db)) as c:
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("DELETE FROM Pep_Rascunhos WHERE id_rascunho=?", (rid,))

    def test_paciente_inexistente_e_data_invalida_sao_rejeitados(self):
        est = self._intern()
        with self.assertRaises(ValueError):
            evdb.salvar_rascunho(self.db, 99, "25/11/2026", self._dados(), est)
        with self.assertRaises(ValueError):
            evdb.salvar_rascunho(self.db, 1, "31/02/2026", self._dados(), est)


if __name__ == "__main__":
    unittest.main()
