# -*- coding: utf-8 -*-
"""Testes com dados sintéticos: peso ajustado, amputações múltiplas, AJ do amputado, DRI, evolução e PEP."""
import os
import sqlite3
from contextlib import closing
import tempfile
import unittest

import avaliacao_nutri as av
import pep_db as pep


class TestCalculos(unittest.TestCase):
    def test_aj_amputado_igual_a_planilha(self):  # 'Peso-Alt'!B45 e C45 (idade 89, altura 146 cm)
        self.assertAlmostEqual(av.aj_da_altura(146, 89, "Homem")[0], 42.26237623762376, 9)
        self.assertAlmostEqual(av.aj_da_altura(146, 89, "Mulher")[0], 45.07103825136612, 9)

    def test_planilha_mulher_branca_68_anos(self):  # 'Peso-Alt'!B30 = 34,8 kg; F30 = 1,5703 m
        r = av.calcular({"sexo": "Mulher", "cor": "Branca", "idade": "68", "aj": "49", "pb": "17,5"})
        self.assertAlmostEqual(r["peso"], 34.8, 1)
        self.assertAlmostEqual(r["altura_m"], 1.57, 2)
        self.assertEqual((r["tipo_peso"], r["tipo_alt"]), ("Estimado", "Estimada"))

    def test_peso_ajustado_com_edema_ascite_e_amputacao(self):
        pct = av.pct_amputacao({"Perna abaixo do joelho": 1, "Antebraço + mão": 1})  # dois membros: 5,9 + 2,3
        self.assertAlmostEqual(pct, 8.2)
        self.assertAlmostEqual(av.peso_ajustado(70, 5.5 + 2.2, pct), (70 - 7.7) / (1 - 0.082))

    def test_mais_de_dois_membros_do_mesmo_tipo(self):
        with self.assertRaises(ValueError):
            av.pct_amputacao({"Mão": 1, "Antebraço + mão": 1, "Braço inteiro": 1})

    def test_dri_adulto_e_dados_insuficientes(self):
        self.assertAlmostEqual(av.eer_dri("Homem", 40, 80, 1.8, 0, imc=24.7), 2524.88, 2)
        self.assertIsNone(av.eer_dri("Homem", 2, 12, 0.85))
        self.assertIsNone(av.eer_dri("Homem", 40, None, 1.8))

    def test_peso_aferido_corrigido_por_ascite_gera_dri_e_meta(self):
        r = av.calcular({"sexo": "Homem", "cor": "Branca", "idade": "50", "peso": "90", "altura": "175",
                         "ascite": "Moderada (6 kg)", "kcalkg": "25", "ptnkg": "1,2", "atividade": 0})
        self.assertAlmostEqual(r["ajustado"], 84.0)
        self.assertAlmostEqual(r["kcal"], 2100.0)
        self.assertIsNotNone(r["dri"])
        self.assertIsNotNone(r["dif_dri_pct"])


class TestSuplementos(unittest.TestCase):
    FICHA = {"nome": "Fórmula X", "emb_un": "ml", "kcal_100": 150.0, "ptn_100": 6.0}

    def test_aporte_e_percentuais(self):
        self.assertEqual(av.aporte_suplemento(self.FICHA, 400), (600.0, 24.0))
        r = av.resumo_suplementos([(self.FICHA, 400)], kcal_meta=2000, dri=2400, ptn_meta=60)
        self.assertEqual(r["kcal"], 600.0)
        self.assertIn("Fórmula X 400 ml/dia (600 kcal; 24,0 g PTN)", r["texto"])
        self.assertIn("30% da meta; 25% da DRI", r["texto"])
        self.assertIn("40% da meta de PTN", r["texto"])

    def test_ficha_pendente_nao_e_estimada(self):
        pend = {"nome": "Sem ficha", "emb_un": "g", "kcal_100": None, "ptn_100": None}
        self.assertIsNone(av.aporte_suplemento(pend, 30))
        r = av.resumo_suplementos([(pend, 30)], kcal_meta=2000)
        self.assertEqual((r["kcal"], r["texto"]), (0.0, "Sem ficha 30 g/dia (ficha pendente)."))
        self.assertEqual(av.resumo_suplementos([])["texto"], "")

    def test_rotulo_crn(self):
        self.assertEqual((av.rotulo_crn("12345"), av.rotulo_crn("CRN-6 12345")), ("CRN 12345", "CRN-6 12345"))


class TestEvolucao(unittest.TestCase):
    F = {"adm": "01/11/2026", "evo": "15/11/2026", "via": "Oral", "ct": "Mantida", "cx": ""}

    def test_novo_paciente_e_conduta_nova(self):
        r = av.calcular({"sexo": "Mulher", "cor": "Preta", "idade": "70", "peso": "60", "altura": "160", "kcalkg": "25", "ptnkg": "1"})
        t = av.montar_evolucao({**self.F, "ct": "Nova conduta", "cx": "Iniciar suplemento."}, r, None, "Ana – CRN 1")
        self.assertIn("NOVO PACIENTE", t)
        self.assertIn("Nova conduta (avaliação inicial): Iniciar suplemento.", t)
        self.assertIn("Peso (Kg): 60,0 (Aferido).", t)

    def test_cabecalho_vem_da_evolucao_anterior_e_dados_novos_vao_na_conduta(self):
        ant = {"peso": 58.0, "tp": "Aferido", "alt": 1.6, "ta": "Aferida", "kk": 25.0, "gk": 1.0, "ajustou": False}
        r = av.calcular({"sexo": "Mulher", "cor": "Preta", "idade": "70", "peso": "61", "altura": "160", "kcalkg": "30", "ptnkg": "1,2"})
        t = av.montar_evolucao(self.F, r, ant, "Ana – CRN 1")
        self.assertNotIn("NOVO PACIENTE", t)
        self.assertIn("Peso (Kg): 58,0 (Aferido).", t)
        self.assertIn("CONDUTA: Mantida.\nDados atuais para comparação: peso 61,0 kg", t)


class TestPep(unittest.TestCase):
    def test_usuario_assinatura_e_imutabilidade(self):
        with tempfile.TemporaryDirectory() as d:
            db = os.path.join(d, "t.db")
            self.assertFalse(pep.hospital_configurado(db))
            pep.definir_senha_hospital(db, "hospital1")
            self.assertTrue(pep.entrar_hospital(db, "hospital1"))
            self.assertFalse(pep.entrar_hospital(db, "errada"))
            uid = pep.criar_usuario(db, "ana", "Ana Teste", "CRN-6 0000", "segredo1", b"png")
            self.assertIsNone(pep.autenticar(db, uid, "errada"))
            self.assertEqual(pep.autenticar(db, uid, "segredo1")["nome_completo"], "Ana Teste")
            self.assertIsNone(pep.ultima_evolucao(db, "José Silva"))
            eid = pep.salvar_evolucao(db, "José  Silva", "15/11/2026", {"peso": 60.0}, "texto", uid)
            ult = pep.ultima_evolucao(db, "jose silva")
            self.assertEqual((ult["cabecalho"]["peso"], ult["assinante"]), (60.0, "Ana Teste"))
            with closing(sqlite3.connect(db)) as c:
                with self.assertRaises(sqlite3.DatabaseError):
                    c.execute("UPDATE Evolucoes_PEP SET texto='x' WHERE id=?", (eid,))
                with self.assertRaises(sqlite3.DatabaseError):
                    c.execute("DELETE FROM Evolucoes_PEP WHERE id=?", (eid,))
            pep.salvar_evolucao(db, "José Silva", "16/11/2026", {"peso": 59.0}, "adendo", uid, adendo_de=eid)
            self.assertEqual(pep.ultima_evolucao(db, "José Silva")["id"], eid)  # adendo não vira cabeçalho


if __name__ == "__main__":
    unittest.main()
