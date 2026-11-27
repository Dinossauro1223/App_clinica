# -*- coding: utf-8 -*-
"""Testes do módulo Mapa Nutricional.  Executar na pasta do projeto:

    python -m unittest discover -s tests -v
"""
import gc
import os
import time
import random
import sqlite3
import sys
import tempfile
import unittest
import shutil
import zipfile
from contextlib import contextmanager
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import nutri_calculos as nc  # noqa: E402
import mapa_db as mdb  # noqa: E402
import mapa_export as mex  # noqa: E402
import mapa_graficos as mgr  # noqa: E402


@contextmanager
def conexao(caminho):
    """Como 'with sqlite3.connect()' (commit/rollback), mas também fecha: no Windows o arquivo fica travado
    enquanto a conexão estiver aberta, o que quebrava a remoção do banco ao fim dos testes."""
    c = sqlite3.connect(caminho)
    try:
        with c:
            yield c
    finally:
        c.close()


def novo_banco():
    fd, caminho = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    mdb.inicializar(caminho)
    return caminho


def registro_base(db, id_leito, data_iso, **extra):
    r = dict(data=data_iso, id_leito=id_leito, nome_paciente="Maria de Souza Lima", acompanhante=1, sexo="M",
             cor="B", idade_anos=72, aj_cm=47.0, pp_cm=31.0, pb_cm=26.5, altura_cm=152.0, altura_origem="E",
             altura_metodo="Chumlea 1985", peso_kg=58.0, peso_origem="R", via="Oral", dm=1, has=1,
             consistencia="Pastosa", obs_sim="mamão, aveia", obs_nao="leite", fi_estado="P", fi_freq=1.0,
             data_reavaliacao="2026-10-30", suplementos=[])
    r.update(extra)
    return r


class TestCalculos(unittest.TestCase):
    def test_parse_num(self):
        self.assertEqual(nc.parse_num("12,5"), 12.5)
        self.assertEqual(nc.parse_num("1.234,5"), 1234.5)
        self.assertEqual(nc.parse_num(" 7 "), 7.0)
        self.assertIsNone(nc.parse_num(""))
        self.assertIsNone(nc.parse_num("abc"))
        self.assertIsNone(nc.parse_num(None))

    def test_normalizacao(self):
        self.assertEqual(nc.norm_sexo("Homem"), "H")
        self.assertEqual(nc.norm_sexo("Mulher"), "M")
        self.assertEqual(nc.norm_sexo("Masculino"), "H")
        self.assertEqual(nc.norm_cor("Negro"), "N")
        self.assertEqual(nc.norm_cor("Branca"), "B")

    def test_altura_chumlea(self):
        self.assertEqual(nc.estimar_altura(50.5, "Homem", "Branco", 30).valor, 166.8)
        self.assertEqual(nc.estimar_altura(48, "Mulher", "Negro", 30).valor, 155.6)
        self.assertEqual(nc.estimar_altura(40, "Homem", "Branco", 10).valor, 129.3)  # 6-18 anos
        r = nc.estimar_altura(50, "Homem", "Branco", 70)  # Chumlea 1985
        self.assertEqual(r.valor, 162.4)
        self.assertTrue(any("70 anos" in a for a in r.avisos))
        self.assertEqual(nc.estimar_altura(45, "Mulher", "Branco", 80).valor, 148.0)
        self.assertEqual(nc.estimar_altura(50, "Homem", "Negro", 65, "chumlea1998").valor, 163.1)

    def test_altura_indisponivel(self):
        for args in [(50, "Homem", "Branco", 4), (None, "Homem", "Branco", 40), (50, None, "Branco", 40),
                     (50, "Homem", None, 40), (120, "Homem", "Branco", 40), (50, "Homem", "Branco", None)]:
            with self.assertRaises(nc.EstimativaIndisponivel):
                nc.estimar_altura(*args)
        # 1985 não exige a cor
        self.assertEqual(nc.estimar_altura(50, "Homem", None, 70).valor, 162.4)

    def test_peso_chumlea(self):
        self.assertEqual(nc.estimar_peso(50, 30, "Homem", "Branco", 40).valor, 69.0)
        self.assertEqual(nc.estimar_peso(45, 28, "Mulher", "Negro", 70).valor, 55.5)
        self.assertEqual(nc.estimar_peso(42, 22, "Mulher", "Branco", 12).valor, 36.5)
        with self.assertRaises(nc.EstimativaIndisponivel):
            nc.estimar_peso(50, None, "Homem", "Branco", 40)
        with self.assertRaises(nc.EstimativaIndisponivel):
            nc.estimar_peso(50, 30, "Homem", "Branco", 5)

    def test_imc_adulto(self):
        c = lambda v: nc.classificar_imc(v, 40).rotulo
        self.assertEqual([c(15.9), c(16.0), c(17.0), c(18.5), c(24.9), c(25.0), c(30.0), c(35.0), c(40.0)],
                         ["Magreza grau III", "Magreza grau II", "Magreza grau I", "Eutrofia", "Eutrofia",
                          "Sobrepeso", "Obesidade grau I", "Obesidade grau II", "Obesidade grau III"])

    def test_imc_idoso(self):
        lip = lambda v: nc.classificar_imc(v, 70).rotulo
        self.assertEqual([lip(21.9), lip(22.0), lip(27.0), lip(27.1)],
                         ["Baixo peso", "Eutrofia", "Eutrofia", "Sobrepeso"])
        opas = lambda v: nc.classificar_imc(v, 70, criterio_idoso="opas").rotulo
        self.assertEqual([opas(22.9), opas(23.0), opas(27.9), opas(28.0), opas(30.0)],
                         ["Baixo peso", "Eutrofia", "Eutrofia", "Sobrepeso", "Obesidade"])

    def test_imc_pediatrico(self):
        c = nc.classificar_imc(17.0, 10, "Homem")
        self.assertTrue(c.pendente)
        self.assertEqual(nc.texto_classificacao(c), "tabela OMS pendente")
        lms = nc.TabelaLMS()
        for s in "HM":
            for m in range(0, 229):
                lms.dados[s][m] = (1.0, 15.0, 0.1)
        z = lambda v, anos, meses=0: nc.classificar_imc(v, anos, "Mulher", meses, lms=lms)
        # com L=1, M=15, S=0,1: IMC = 15 * (1 + 0,1 * z)
        self.assertAlmostEqual(z(16.5, 10).zscore, 1.0, places=6)
        self.assertEqual(z(15.0, 10).rotulo, "Eutrofia")
        self.assertEqual(z(13.0, 10).rotulo, "Eutrofia")  # z = -1,33
        self.assertEqual(z(17.9, 10).rotulo, "Sobrepeso")  # z = 1,93
        self.assertEqual(z(18.1, 10).rotulo, "Obesidade")  # z = 2,07
        self.assertEqual(z(19.4, 10).rotulo, "Obesidade")  # z = 2,93
        self.assertEqual(z(19.6, 10).rotulo, "Obesidade grave")  # z = 3,07
        self.assertEqual(z(11.9, 10).rotulo, "Magreza")  # z = -2,07
        self.assertEqual(z(10.4, 10).rotulo, "Magreza acentuada")  # z = -3,07
        self.assertEqual(z(16.6, 2, 0).rotulo, "Risco de sobrepeso")  # menor de 5 anos
        self.assertEqual(z(18.1, 2, 0).rotulo, "Sobrepeso")  # z = 2,07, menor de 5 anos
        self.assertEqual(z(19.6, 2, 0).rotulo, "Obesidade")  # z = 3,07, menor de 5 anos

    def test_lms_csv(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("sexo;idade_meses;L;M;S\n")
            for s in ("masculino", "feminino"):
                for m in (60, 61, 62):
                    f.write(f"{s};{m};-1,5;15,2;0,08\n")
        t = nc.TabelaLMS.de_csv(f.name)
        self.assertIn(61, t.dados["H"])
        self.assertIsNotNone(t.zscore_imc(15.2, "H", 61))
        self.assertAlmostEqual(t.zscore_imc(15.2, "H", 61), 0.0, places=6)
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as g:
            g.write("sexo;idade_meses;L;M;S\nM;60;1;15;0.1\n")
        with self.assertRaises(ValueError):
            nc.TabelaLMS.de_csv(g.name)

    def test_idade(self):
        self.assertEqual(nc.idade_em_anos("25/10/1950", date(2026, 10, 24)), 75)
        self.assertEqual(nc.idade_em_anos("25/10/1950", date(2026, 10, 25)), 76)
        self.assertIsNone(nc.idade_em_anos("", date(2026, 1, 1)))


class TestBanco(unittest.TestCase):
    def setUp(self):
        self.db = novo_banco()
        self.setor = mdb.criar_setor(self.db, "Setor de teste")
        mdb.criar_leitos_sequencia(self.db, self.setor, "L", 1, 5)
        self.leitos = mdb.listar_leitos(self.db, self.setor)

    def tearDown(self):
        os.remove(self.db)

    def test_setores_e_leitos_iniciais_na_ordem_solicitada(self):
        setores = mdb.listar_setores(self.db)
        esperados = [
            ("Internos", "Operação", "OP", list(range(1, 10))),
            ("Internos", "Clínica médica", "CM", list(range(16, 34))),
            ("Internos", "Psiquiatria", "PSI", [46, 47, 48]),
            ("Internos", "Isolamento", "ISO", [1, 2]),
            ("Externos", "Sala vermelha Adulto", "SVA", [1, 2, 3]),
            ("Externos", "Sala de observação adulto", "SAU", [4, 5, 6, 7, 8, 9]),
            ("Externos", "Sala vermelha Pediatria", "SVP", [1, 2]),
            ("Externos", "Observação da Pediatria", "PED", [1, 2, 3]),
        ]
        obtidos = []
        for grupo, nome, sigla, codigos in esperados:
            setor = next(x for x in setores if x["nome"] == nome)
            self.assertEqual((setor["grupo"], setor["sigla"]), (grupo, sigla))
            leitos = mdb.listar_leitos(self.db, setor["id_setor"])
            self.assertEqual([int(x["codigo"]) for x in leitos], codigos)
            obtidos.append((setor["grupo"], setor["nome"], setor["sigla"]))
        self.assertEqual(obtidos, [(g, n, s) for g, n, s, _ in esperados])
        mdb.inicializar(self.db)
        self.assertEqual(len([x for x in mdb.listar_setores(self.db) if x.get("sigla")]), 8)

    def test_reordenacao_persistente_dentro_do_grupo(self):
        setores = mdb.listar_setores(self.db)
        cm = next(x for x in setores if x["sigla"] == "CM")
        op = next(x for x in setores if x["sigla"] == "OP")
        self.assertEqual([x["sigla"] for x in setores if x["grupo"] == "Internos"],
                         ["OP", "CM", "PSI", "ISO"])
        self.assertTrue(mdb.alterar_ordem_setor(self.db, cm["id_setor"], -1))
        atual = mdb.listar_setores(self.db)
        self.assertEqual([x["sigla"] for x in atual if x["grupo"] == "Internos"],
                         ["CM", "OP", "PSI", "ISO"])
        self.assertFalse(mdb.alterar_ordem_setor(self.db, cm["id_setor"], -1))
        # A ordenação de um grupo não desloca setores do outro grupo.
        self.assertEqual([x["sigla"] for x in atual if x["grupo"] == "Externos"],
                         ["SVA", "SAU", "SVP", "PED"])

    def test_mapa_geral_respeita_grupos_ordem_e_identificacao(self):
        linhas = mdb.mapa_do_dia(self.db, "2026-11-24")
        setores = [x["leito"] for x in linhas]
        self.assertEqual([(x["grupo_setor"], x["sigla_setor"], x["codigo"]) for x in setores[:9]],
                         [("Internos", "OP", str(n)) for n in range(1, 10)])
        self.assertEqual([(x["grupo_setor"], x["sigla_setor"], x["codigo"]) for x in setores[9:27]],
                         [("Internos", "CM", str(n)) for n in range(16, 34)])
        self.assertEqual([(x["grupo_setor"], x["sigla_setor"], x["codigo"]) for x in setores[27:30]],
                         [("Internos", "PSI", str(n)) for n in (46, 47, 48)])
        self.assertEqual(mex.textos_linha(setores[0], None)["setor"], "Internos · Operação (OP)")

    def test_seed_e_idempotencia(self):
        mdb.inicializar(self.db)  # chamar de novo não duplica
        self.assertEqual(len(mdb.listar_suplementos(self.db)),
                         len(mdb.SUPLEMENTOS_INICIAIS) + len(mdb.SUPLEMENTOS_COMPLEMENTARES) + len(mdb.SUPLEMENTOS_ENTERAIS_COMPLEMENTARES) + len(mdb.SUPLEMENTOS_DUAS_VIAS_COMPLEMENTARES))
        self.assertEqual(len(mdb.listar_modulos(self.db)), len(mdb.MODULOS_PADRAO))
        candidatos = {s["nome"]: s for s in mdb.listar_suplementos(self.db)}
        self.assertIn("Ensure Plus Advance", candidatos)
        self.assertIn("Glucerna 1.5 kcal", candidatos)
        self.assertIn("Nutrison Energy 1.5", candidatos)
        # As quatro composições preenchidas foram transcritas das respectivas fichas oficiais por 100 mL.
        fichas = {
            "Nutrison Energy 1.5": (149, 6, 5.8, 18, 134),
            "Nutrison Protein Plus Energy": (150, 7.5, 5.8, 17, 100),
            "Nutrison advanced Diason": (102, 4.3, 4.2, 11, 100),
            "Nutrison advanced Cubison": (103, 5.5, 3.3, 13, 100),
        }
        for nome, valores in fichas.items():
            item = candidatos[nome]
            self.assertEqual((item["kcal_100"], item["ptn_100"], item["lip_100"],
                              item["carb_100"], item["sod_100"]), valores)
            self.assertIn("danonenutricia.com.br", item["observacao"])
            self.assertEqual(item["modulo"], "Fórmula enteral")
        # Os demais candidatos não recebem valores inferidos.
        self.assertIsNone(candidatos["Ensure Plus Advance"]["kcal_100"])
        self.assertIn("abbottbrasil.com.br", candidatos["Ensure Plus Advance"]["observacao"])
        self.assertIsNone(candidatos["Nutrison Energy MF 1.5"]["kcal_100"])
        self.assertEqual(candidatos["Glucerna 1.5 kcal"]["modulo"], "Fórmula para diabetes")
        self.assertEqual(candidatos["Glucerna SR"]["modulo"], "Fórmula enteral e oral")
        self.assertEqual(candidatos["Nutri R 2.0"]["modulo"], "Fórmula enteral e oral")
        self.assertEqual((candidatos["Nutri R 2.0"]["kcal_100"], candidatos["Nutri R 2.0"]["ptn_100"],
                          candidatos["Nutri R 2.0"]["lip_100"], candidatos["Nutri R 2.0"]["carb_100"],
                          candidatos["Nutri R 2.0"]["sod_100"]), (200, 3.3, 6.7, 32, 131))
        self.assertEqual((candidatos["Nutri Enteral Soya"]["kcal_100"], candidatos["Nutri Enteral Soya"]["ptn_100"],
                          candidatos["Nutri Enteral Soya"]["lip_100"], candidatos["Nutri Enteral Soya"]["carb_100"],
                          candidatos["Nutri Enteral Soya"]["sod_100"]), (120, 4.4, 4, 17, 55))
        self.assertIsNone(candidatos["NUTRI FIBER 1.5"]["kcal_100"])
        self.assertEqual(candidatos["NUTRI HWHEY X"]["modulo"], "Módulo oral/enteral")
        nomes = {s["nome"]: s["modulo"] for s in mdb.listar_suplementos(self.db)}
        self.assertEqual(nomes["Simbioflora"], "Módulo probiótico/simbiótico")
        self.assertEqual(nomes["Glutamina"], "Módulo de aminoácidos")
        # excluir tudo e reinicializar não semeia de novo
        for s in mdb.listar_suplementos(self.db):
            mdb.remover_suplemento(self.db, s["id_suplemento"])
        mdb.inicializar(self.db)
        self.assertEqual(len(mdb.listar_suplementos(self.db)), 0)

    def test_leitos(self):
        self.assertEqual([l["codigo"] for l in self.leitos], ["L01", "L02", "L03", "L04", "L05"])
        with self.assertRaises(ValueError):
            mdb.criar_leito(self.db, self.setor, "L01")
        self.assertEqual(mdb.criar_leitos_sequencia(self.db, self.setor, "L", 4, 7), 2)  # só L06 e L07

    def test_registro_completo(self):
        sup = next(s for s in mdb.listar_suplementos(self.db) if s["nome"] == "Fresubin")
        reg = registro_base(self.db, self.leitos[0]["id_leito"], "2026-10-25",
                            suplementos=[dict(id_suplemento=sup["id_suplemento"], nome=sup["nome"],
                                              modulo=sup["modulo"], qtd_dia=400.0, unidade="ml")])
        id_reg = mdb.salvar_registro(self.db, reg)
        r = mdb.obter_registro(self.db, "2026-10-25", self.leitos[0]["id_leito"])
        self.assertEqual(r["id_registro"], id_reg)
        self.assertAlmostEqual(r["imc"], 25.1, places=1)
        self.assertEqual(r["imc_class"], "Eutrofia")  # 72 anos, Lipschitz (22-27)
        self.assertEqual(r["suplementos"][0]["nome"], "Fresubin")
        self.assertTrue(r["id_paciente"])
        # nova gravação no mesmo leito/dia atualiza, não duplica
        reg["peso_kg"] = 70.0
        mdb.salvar_registro(self.db, reg)
        r2 = mdb.obter_registro(self.db, "2026-10-25", self.leitos[0]["id_leito"])
        self.assertEqual(r2["id_registro"], id_reg)
        self.assertEqual(r2["imc_class"], "Sobrepeso")
        self.assertEqual(r2["id_paciente"], r["id_paciente"])
        with conexao(self.db) as c:
            self.assertEqual(c.execute("select count(*) from Mapa_Registros").fetchone()[0], 1)
            self.assertEqual(c.execute("select count(*) from Mapa_Registro_Suplementos").fetchone()[0], 1)
            self.assertEqual(c.execute("select count(*) from Pacientes").fetchone()[0], 1)
        # critério OPAS muda a classe (25,1 -> eutrofia)
        reg["peso_kg"] = 58.0
        mdb.salvar_registro(self.db, reg, criterio_idoso="opas")
        self.assertEqual(mdb.obter_registro(self.db, "2026-10-25", self.leitos[0]["id_leito"])["imc_class"], "Eutrofia")

    def test_metas_sao_persistidas_e_enteral_nao_e_suplementacao_oral(self):
        sup = next(s for s in mdb.listar_suplementos(self.db) if s["modulo"] == "Fórmula completa")
        reg = registro_base(
            self.db, self.leitos[0]["id_leito"], "2026-10-25", via="Enteral",
            meta_kcal=1800.0, meta_proteina_g=90.0,
            suplementos=[dict(id_suplemento=sup["id_suplemento"], nome=sup["nome"],
                              modulo=sup["modulo"], qtd_dia=500.0, unidade="ml")])
        mdb.salvar_registro(self.db, reg)
        salvo = mdb.obter_registro(self.db, "2026-10-25", self.leitos[0]["id_leito"])
        self.assertEqual(salvo["via"], "Enteral")
        self.assertEqual((salvo["meta_kcal"], salvo["meta_proteina_g"]), (1800.0, 90.0))
        # A separação visual/operacional deriva da via; a fórmula permanece como dieta enteral.
        self.assertEqual("Dieta enteral" if salvo["via"] == "Enteral" else "Suplementação oral",
                         "Dieta enteral")

    def test_meta_zero_ou_negativa_e_rejeitada(self):
        for campo in ("meta_kcal", "meta_proteina_g"):
            for valor in (0, -1):
                with self.assertRaises(ValueError):
                    mdb.salvar_registro(self.db, registro_base(
                        self.db, self.leitos[0]["id_leito"], "2026-10-25", **{campo: valor}))

    def test_validacao(self):
        for extra in ({"nome_paciente": " "}, {"peso_kg": 900}, {"aj_cm": 5}, {"via": "Parenteral"},
                      {"altura_origem": "X"}):
            with self.assertRaises(ValueError):
                mdb.salvar_registro(self.db, registro_base(self.db, self.leitos[0]["id_leito"], "2026-10-25", **extra))

    def test_mapa_copia_historico(self):
        a, b = self.leitos[0]["id_leito"], self.leitos[1]["id_leito"]
        mdb.salvar_registro(self.db, registro_base(self.db, a, "2026-10-24"))
        mdb.salvar_registro(self.db, registro_base(self.db, b, "2026-10-24", nome_paciente="João Pedro", sexo="H"))
        self.assertEqual(mdb.ultima_data_com_registros(self.db, "2026-10-25"), "2026-10-24")
        self.assertEqual(mdb.copiar_mapa(self.db, "2026-10-24", "2026-10-25", self.setor), 2)
        self.assertEqual(mdb.copiar_mapa(self.db, "2026-10-24", "2026-10-25", self.setor), 0)  # idempotente
        dia = mdb.mapa_do_dia(self.db, "2026-10-25", self.setor)
        self.assertEqual(len(dia), 5)
        self.assertEqual([d["registro"] is not None for d in dia], [True, True, False, False, False])
        r24 = mdb.obter_registro(self.db, "2026-10-24", a)
        r25 = mdb.obter_registro(self.db, "2026-10-25", a)
        self.assertEqual(r24["id_paciente"], r25["id_paciente"])
        hist = mdb.historico_paciente(self.db, id_paciente=r25["id_paciente"])
        self.assertEqual([h["data"] for h in hist], ["2026-10-25", "2026-10-24"])
        mdb.remover_registro(self.db, r25["id_registro"])
        self.assertIsNone(mdb.obter_registro(self.db, "2026-10-25", a))

    def test_leito_desativado_com_registro_aparece(self):
        a = self.leitos[0]["id_leito"]
        mdb.salvar_registro(self.db, registro_base(self.db, a, "2026-10-25"))
        self.assertFalse(mdb.remover_leito(self.db, a))  # tem histórico: só desativa
        dia = mdb.mapa_do_dia(self.db, "2026-10-25", self.setor)
        self.assertEqual(len(dia), 5)  # os 4 ativos + o desativado que tem registro nesse dia
        self.assertEqual(len(mdb.mapa_do_dia(self.db, "2026-10-26", self.setor)), 4)

    def test_suplementos(self):
        novo = mdb.salvar_suplemento(self.db, dict(nome="Módulo X", modulo="Módulo de fibras", preco="12,50",
                                                    emb_qtd="200", emb_un="g", kcal_100="350", ptn_100="2,5",
                                                    osmolaridade_ref="300", unidade_osmolaridade="mOsm/L",
                                                    dose_ref="20", unidade_dose_ref="g", volume_final_ref_ml="150",
                                                    agua_recomendada_ml="130", fonte_osmolaridade="Ficha técnica 2026",
            classificacao_nutricional="oligomerica", grau_hidrolise="parcialmente_hidrolisada",
            proteinas_hidrolisadas="proteína do soro do leite", fonte_classificacao="Ficha fabricante 2026",
            tipo_formula="fechada", fibra_g_100="8,5", tipo_fibra="mista",
            descricao_fibra="inulina + fibra de soja", fonte_fibra="Ficha técnica fabricante"))
        s = [x for x in mdb.listar_suplementos(self.db) if x["id_suplemento"] == novo][0]
        self.assertEqual((s["preco"], s["emb_qtd"], s["kcal_100"], s["ptn_100"]), (12.5, 200.0, 350.0, 2.5))
        self.assertEqual((s["osmolaridade_ref"], s["unidade_osmolaridade"], s["dose_ref"],
                          s["unidade_dose_ref"], s["volume_final_ref_ml"], s["agua_recomendada_ml"]),
                         (300.0, "mOsm/L", 20.0, "g", 150.0, 130.0))
        self.assertEqual((s["classificacao_nutricional"], s["grau_hidrolise"], s["proteinas_hidrolisadas"], s["tipo_formula"]),
                         ("oligomerica", "parcialmente_hidrolisada", "proteína do soro do leite", "fechada"))
        self.assertEqual((s["fibra_g_100"], s["tipo_fibra"], s["descricao_fibra"], s["fonte_fibra"]),
                         (8.5, "mista", "inulina + fibra de soja", "Ficha técnica fabricante"))
        self.assertIn("Módulo de fibras", mdb.listar_modulos(self.db))
        mdb.salvar_suplemento(self.db, dict(id_suplemento=novo, nome="Módulo X", modulo="Novo módulo", emb_un="ml",
            osmolaridade_ref="300", unidade_osmolaridade="mOsm/L", dose_ref="20", unidade_dose_ref="ml",
            volume_final_ref_ml="150", agua_recomendada_ml="130", fonte_osmolaridade="Ficha técnica 2026"))
        self.assertIn("Novo módulo", mdb.listar_modulos(self.db))
        with self.assertRaises(ValueError):
            mdb.salvar_suplemento(self.db, dict(nome="Y", kcal_100="abc"))
        with self.assertRaises(ValueError):
            mdb.salvar_suplemento(self.db, dict(nome="Y", emb_un="L"))
        # usado em registro: só desativa; não usado: exclui
        mdb.salvar_registro(self.db, registro_base(self.db, self.leitos[0]["id_leito"], "2026-10-25",
                            suplementos=[dict(id_suplemento=novo, nome="Módulo X", modulo="Novo módulo",
                                qtd_dia=20, unidade="g", agua_ml=130,
                                preparacoes=[{"refeicao": "almoço", "dose": 10,
                                              "agua_adicionada_ml": 65, "agua_separada_ml": 100},
                                             {"refeicao": "jantar", "dose": 10,
                                              "agua_adicionada_ml": 65, "agua_separada_ml": 0}])]))
        salvo = mdb.obter_registro(self.db, "2026-10-25", self.leitos[0]["id_leito"])["suplementos"][0]
        self.assertEqual((salvo["osmolaridade_ref"], salvo["dose_ref"], salvo["volume_final_ref_ml"],
                          salvo["agua_recomendada_ml"], salvo["agua_ml"]), (300.0, 20.0, 150.0, 130.0, 130.0))
        self.assertEqual((salvo["classificacao_nutricional"], salvo["grau_hidrolise"], salvo["tipo_formula"]),
                         ("oligomerica", "parcialmente_hidrolisada", "fechada"))
        self.assertEqual((salvo["fibra_g_100"], salvo["tipo_fibra"], salvo["descricao_fibra"], salvo["fonte_fibra"]),
                         (8.5, "mista", "inulina + fibra de soja", "Ficha técnica fabricante"))
        self.assertEqual(salvo["preparacoes"], [
            {"refeicao": "almoço", "dose": 10, "agua_adicionada_ml": 65, "agua_separada_ml": 100},
            {"refeicao": "jantar", "dose": 10, "agua_adicionada_ml": 65, "agua_separada_ml": 0},
        ])
        self.assertFalse(mdb.remover_suplemento(self.db, novo))
        self.assertNotIn(novo, [x["id_suplemento"] for x in mdb.listar_suplementos(self.db)])
        outro = mdb.salvar_suplemento(self.db, dict(nome="Z"))
        self.assertTrue(mdb.remover_suplemento(self.db, outro))

    def test_migracao_adiciona_colunas_de_snapshot_em_banco_antigo(self):
        fd, legado = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            with sqlite3.connect(legado) as c:
                c.execute("""CREATE TABLE Mapa_Suplementos (
                    id_suplemento INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, modulo TEXT, preco REAL,
                    emb_qtd REAL, emb_un TEXT DEFAULT 'ml', kcal_100 REAL, ptn_100 REAL, lip_100 REAL,
                    carb_100 REAL, sod_100 REAL, observacao TEXT, ativo INTEGER DEFAULT 1)""")
                c.execute("""CREATE TABLE Mapa_Registro_Suplementos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, id_registro INTEGER NOT NULL,
                    id_suplemento INTEGER, nome TEXT NOT NULL, modulo TEXT, qtd_dia REAL,
                    unidade TEXT, ml_oferta REAL, agua_ml REAL,
                    refeicoes_json TEXT DEFAULT '[]', batido_fruta INTEGER DEFAULT 0)""")
            mdb.inicializar(legado)
            with sqlite3.connect(legado) as c:
                colunas = {r[1] for r in c.execute("PRAGMA table_info(Mapa_Registro_Suplementos)")}
                colunas_catalogo = {r[1] for r in c.execute("PRAGMA table_info(Mapa_Suplementos)")}
            self.assertTrue({"kcal_100", "ptn_100", "lip_100", "carb_100", "sod_100",
                             "ficha_observacao", "ficha_snapshot_em", "osmolaridade_ref",
                             "unidade_osmolaridade", "dose_ref", "unidade_dose_ref",
                             "volume_final_ref_ml", "agua_recomendada_ml", "fonte_osmolaridade", "classificacao_nutricional",
                             "grau_hidrolise", "proteinas_hidrolisadas", "fonte_classificacao", "tipo_formula"}.issubset(colunas))
            self.assertTrue({"osmolaridade_ref", "unidade_osmolaridade", "dose_ref", "unidade_dose_ref",
                             "volume_final_ref_ml", "agua_recomendada_ml", "fonte_osmolaridade", "classificacao_nutricional",
                             "grau_hidrolise", "proteinas_hidrolisadas", "fonte_classificacao", "tipo_formula"}.issubset(colunas_catalogo))
        finally:
            try:
                os.remove(legado)
            except PermissionError:
                # SQLite pode manter o arquivo temporariamente aberto no Windows;
                # como o banco é descartável, o runner fará a limpeza ao encerrar.
                pass

    def test_migracao_adiciona_classificacao_de_dupla_via(self):
        glucerna = next(s for s in mdb.listar_suplementos(self.db) if s["nome"] == "Glucerna SR")
        mdb.salvar_suplemento(self.db, dict(
            id_suplemento=glucerna["id_suplemento"], nome="Glucerna SR",
            modulo="Fórmula para diabetes", emb_un="ml"))
        with conexao(self.db) as c:
            c.execute("DELETE FROM Mapa_Config WHERE chave='seed_suplementos_catalogo_v4'")
            c.execute("DELETE FROM Mapa_Suplementos WHERE nome='Nutri R 2.0'")
        mdb.inicializar(self.db)
        glucerna_atual = next(s for s in mdb.listar_suplementos(self.db) if s["nome"] == "Glucerna SR")
        nutri_r = next(s for s in mdb.listar_suplementos(self.db) if s["nome"] == "Nutri R 2.0")
        self.assertEqual(glucerna_atual["modulo"], "Fórmula enteral e oral")
        self.assertEqual(nutri_r["modulo"], "Fórmula enteral e oral")
        self.assertEqual(nutri_r["kcal_100"], 200)

    def test_migracao_corrige_ficha_nutrison_antiga_conhecida(self):
        item = next(s for s in mdb.listar_suplementos(self.db) if s["nome"] == "Nutrison Energy 1.5")
        mdb.salvar_suplemento(self.db, dict(
            id_suplemento=item["id_suplemento"], nome=item["nome"], modulo="Fórmula enteral",
            emb_un="ml", kcal_100=151, ptn_100=6, lip_100=5.6, carb_100=19, sod_100=128,
            observacao="Fonte antiga"))
        with conexao(self.db) as c:
            c.execute("DELETE FROM Mapa_Config WHERE chave='seed_suplementos_catalogo_v3'")
        mdb.inicializar(self.db)
        atualizado = next(s for s in mdb.listar_suplementos(self.db) if s["nome"] == "Nutrison Energy 1.5")
        self.assertEqual((atualizado["kcal_100"], atualizado["ptn_100"], atualizado["lip_100"],
                          atualizado["carb_100"], atualizado["sod_100"]), (149.0, 6.0, 5.8, 18.0, 134.0))
        self.assertIn("danonenutricia.com.br", atualizado["observacao"])

    def test_snapshot_da_ficha_nao_muda_quando_catalogo_e_atualizado(self):
        sid = mdb.salvar_suplemento(self.db, dict(
            nome="Fórmula snapshot", modulo="Fórmula completa", emb_un="g",
            kcal_100=350, ptn_100=20, lip_100=10, carb_100=45, sod_100=120,
            observacao="Ficha técnica versão A", fibra_g_100=3,
            tipo_fibra="soluvel", descricao_fibra="psyllium"))
        reg = registro_base(
            self.db, self.leitos[0]["id_leito"], "2026-10-25",
            suplementos=[dict(id_suplemento=sid, nome="Fórmula snapshot", modulo="Fórmula completa",
                              qtd_dia=50, unidade="g")])
        mdb.salvar_registro(self.db, reg)
        antes = mdb.obter_registro(self.db, "2026-10-25", self.leitos[0]["id_leito"])["suplementos"][0]
        self.assertEqual((antes["kcal_100"], antes["ptn_100"], antes["ficha_observacao"]),
                         (350.0, 20.0, "Ficha técnica versão A"))
        self.assertTrue(antes["ficha_snapshot_em"])

        mdb.salvar_suplemento(self.db, dict(
            id_suplemento=sid, nome="Fórmula snapshot", modulo="Fórmula completa", emb_un="g",
            kcal_100=200, ptn_100=5, lip_100=3, carb_100=30, sod_100=80,
            observacao="Ficha técnica versão B", fibra_g_100=9,
            tipo_fibra="insoluvel", descricao_fibra="celulose"))
        depois = mdb.obter_registro(self.db, "2026-10-25", self.leitos[0]["id_leito"])["suplementos"][0]
        self.assertEqual((depois["kcal_100"], depois["ptn_100"], depois["ficha_observacao"]),
                         (350.0, 20.0, "Ficha técnica versão A"))
        self.assertEqual((depois["fibra_g_100"], depois["tipo_fibra"], depois["descricao_fibra"]),
                         (3.0, "soluvel", "psyllium"))

    def test_config(self):
        self.assertEqual(mdb.obter_config(self.db, "criterio", "lipschitz"), "lipschitz")
        mdb.salvar_config(self.db, "criterio", "opas")
        mdb.salvar_config(self.db, "criterio", "opas2")
        self.assertEqual(mdb.obter_config(self.db, "criterio"), "opas2")


def popular_mes(db, ano=2026, mes=10, n_leitos=10, semente=7):
    """Cria um mês de registros verossímeis (para testes e para o QA visual)."""
    rnd = random.Random(semente)
    setor = next((x["id_setor"] for x in mdb.listar_setores(db) if x["nome"] == "Setor de demonstração"), None)
    if setor is None:
        setor = mdb.criar_setor(db, "Setor de demonstração")
    mdb.criar_leitos_sequencia(db, setor, "L", 1, n_leitos)
    leitos = mdb.listar_leitos(db, setor)
    sups = mdb.listar_suplementos(db)
    nomes = ["Maria de Souza Lima", "José Carlos Pereira", "Ana Beatriz Santos", "Antônio Ferreira da Silva",
             "Francisca das Chagas Oliveira", "Raimundo Nonato Costa", "Luzia Maria Alves", "Pedro Henrique Gomes",
             "Teresinha de Jesus Barbosa", "Manoel Messias de Araújo"]
    estado = {}
    for dia in range(1, mdb.dias_do_mes(ano, mes) + 1):
        d = date(ano, mes, dia)
        for i, leito in enumerate(leitos):
            if rnd.random() < 0.18:
                estado.pop(leito["id_leito"], None)
                continue
            if leito["id_leito"] not in estado:
                sx = rnd.choice("HM")
                estado[leito["id_leito"]] = dict(
                    nome_paciente=nomes[(i + dia // 6) % len(nomes)], sexo=sx, cor=rnd.choice("BN"),
                    idade_anos=rnd.choice([34, 52, 61, 68, 74, 83]), aj_cm=round(rnd.uniform(44, 54), 1),
                    pp_cm=round(rnd.uniform(26, 36), 1), pb_cm=round(rnd.uniform(22, 32), 1),
                    altura_cm=round(rnd.uniform(150, 175), 1), altura_origem=rnd.choice("ER"),
                    peso_kg=round(rnd.uniform(48, 92), 1), peso_origem=rnd.choice("ER"))
            base = estado[leito["id_leito"]]
            enteral = rnd.random() < 0.25
            usa = [s for s in sups if rnd.random() < 0.22]
            reg = dict(base, data=d.isoformat(), id_leito=leito["id_leito"], acompanhante=int(rnd.random() < 0.5),
                       via="Enteral" if enteral else "Oral",
                       consistencia="Líquida" if enteral else rnd.choice(["Livre", "Branda", "Pastosa", "Pastosa", "Líq/Past"]),
                       dm=int(rnd.random() < 0.3), has=int(rnd.random() < 0.45), laxativa=int(rnd.random() < 0.1),
                       constipante=int(rnd.random() < 0.1), drc=int(rnd.random() < 0.12),
                       obs_sim=rnd.choice(["", "frutas, sopas", "mamão, aveia", "arroz, feijão, carne moída"]),
                       obs_nao=rnd.choice(["", "leite", "carne vermelha", "ovo"]),
                       fi_estado="P" if rnd.random() < 0.8 else "A", fi_freq=float(rnd.choice([1, 2, 1])),
                       fi_dias_ausente=rnd.choice([2, 3, 4]),
                       data_reavaliacao=(d + timedelta(days=3)).isoformat(),
                       suplementos=[dict(id_suplemento=s["id_suplemento"], nome=s["nome"], modulo=s["modulo"],
                                         qtd_dia=rnd.choice([None, 200.0, 400.0]), unidade="ml") for s in usa])
            mdb.salvar_registro(db, reg)
    return leitos


    def test_dados_estruturados_da_evolucao_acompanham_historico_e_copia_do_mapa(self):
        dados = {
            "via": "Enteral", "dva": False, "status_evolucao": "fechada", "fechada": True,
            "dieta_enteral": {"nome": "Fórmula Sintética", "volume_por_etapa_ml": 180, "etapas": 6},
            "progressao_enteral": {"autorizada": True, "incremento_por_etapa_ml": 10},
            "tne_motivos": []
        }
        preparacoes = [
            {"refeicao": "desjejum", "dose": 40, "agua_adicionada_ml": 20, "agua_separada_ml": 50},
            {"refeicao": "ceia", "dose": 60, "agua_adicionada_ml": 30, "agua_separada_ml": 0},
        ]
        reg = registro_base(self.db, self.leitos[0]["id_leito"], "2026-10-25",
                            evolucao_json=json.dumps(dados, ensure_ascii=False),
                            suplementos=[dict(nome="Fórmula teste", qtd_dia=100, unidade="ml",
                                               agua_ml=50, preparacoes=preparacoes)])
        id_reg = mdb.salvar_registro(self.db, reg)
        obtido = mdb.obter_registro(self.db, "2026-10-25", self.leitos[0]["id_leito"])
        self.assertEqual(obtido["evolucao"], dados)
        dia = mdb.mapa_do_dia(self.db, "2026-10-25")
        linha = next(x for x in dia if x["leito"]["id_leito"] == self.leitos[0]["id_leito"])
        self.assertEqual(linha["registro"]["evolucao"], dados)
        historico = mdb.historico_paciente(self.db, obtido["id_paciente"])
        self.assertEqual(historico[0]["evolucao"], dados)
        self.assertEqual(mdb.copiar_mapa(self.db, "2026-10-25", "2026-10-26"), 1)
        copia = mdb.obter_registro(self.db, "2026-10-26", self.leitos[0]["id_leito"])
        self.assertEqual(copia["evolucao"], dados)
        self.assertEqual(copia["suplementos"][0]["preparacoes"], preparacoes)
        mdb.remover_registro(self.db, copia["id_registro"])
        with conexao(self.db) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM Mapa_Evolucao_Dados WHERE id_registro=?",
                                       (copia["id_registro"],)).fetchone()[0], 0)
        self.assertIsNotNone(id_reg)


    def test_troca_de_paciente_remove_evolucao_do_registro_anterior(self):
        leito = self.leitos[0]["id_leito"]
        reg = registro_base(self.db, leito, "2026-10-25", nome_paciente="Maria de Souza")
        id_reg = mdb.salvar_registro(self.db, reg)
        mdb.salvar_dados_evolucao(self.db, id_reg, {
            "status_evolucao": "fechada", "via": "Enteral",
            "dieta_enteral": {"nome": "Fórmula da paciente anterior"}
        })

        substituto = registro_base(
            self.db, leito, "2026-10-25", nome_paciente="João de Souza"
        )
        self.assertEqual(mdb.salvar_registro(self.db, substituto), id_reg)
        obtido = mdb.obter_registro(self.db, "2026-10-25", leito)
        self.assertEqual(obtido["nome_paciente"], "João de Souza")
        self.assertEqual(obtido["evolucao"], {})

    def test_progressao_enteral_diaria_e_porcoes_orais_autorizadas_para_copa(self):
        dados = {
            "via": "Enteral", "status_evolucao": "fechada", "fechada": True,
            "dieta_enteral": {"nome": "Fórmula Clínica", "volume_por_etapa_ml": 150, "etapas": 6},
            "progressao_enteral": {"autorizada": True, "plano": {"passos": [
                {"dia": 1, "volume_total_ml": 935},
                {"dia": 2, "volume_total_ml": 970},
                {"dia": 3, "volume_total_ml": 1005},
                {"dia": 4, "volume_total_ml": 1040},
                {"dia": 5, "volume_total_ml": 1075},
            ]}}
        }
        reg = registro_base(self.db, self.leitos[0]["id_leito"], "2026-10-25",
                            via="Enteral", evolucao_json=json.dumps(dados, ensure_ascii=False))
        mdb.salvar_registro(self.db, reg)
        esperado = {"2026-10-25": 900, "2026-10-26": 935, "2026-10-29": 1040, "2026-10-30": 1075}
        for data, total in esperado.items():
            linha = next(x for x in mdb.mapa_do_dia(self.db, data)
                         if x["leito"]["id_leito"] == self.leitos[0]["id_leito"])
            self.assertEqual(linha["registro"]["dados_copa"]["volume_total_ml"], total)
            self.assertAlmostEqual(linha["registro"]["dados_copa"]["volume_por_etapa_ml"], total / 6)
        oral = dict(dados, via="Oral", porcao_oral_ml=100, porcao_oral_autorizada=False)
        reg["data"] = "2026-10-31"
        reg["via"] = "Oral"
        reg["evolucao_json"] = json.dumps(oral, ensure_ascii=False)
        mdb.salvar_registro(self.db, reg)
        linha = next(x for x in mdb.mapa_do_dia(self.db, "2026-10-31")
                     if x["leito"]["id_leito"] == self.leitos[0]["id_leito"])
        self.assertEqual(linha["registro"]["dados_copa"], {})
        oral["porcao_oral_autorizada"] = True
        reg["evolucao_json"] = json.dumps(oral, ensure_ascii=False)
        mdb.salvar_registro(self.db, reg)
        linha = next(x for x in mdb.mapa_do_dia(self.db, "2026-10-31")
                     if x["leito"]["id_leito"] == self.leitos[0]["id_leito"])
        self.assertEqual(linha["registro"]["dados_copa"]["porcao_oral_ml"], 100)


class TestExportacao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = novo_banco()
        cls.leitos = popular_mes(cls.db, n_leitos=24)
        cls.setor = next(x for x in mdb.listar_setores(cls.db) if x["id_setor"] == cls.leitos[0]["id_setor"])
        cls.dia = mdb.mapa_do_dia(cls.db, "2026-10-14", cls.setor["id_setor"])
        # um caso extremo: textos longos
        cls.longo = registro_base(cls.db, cls.leitos[0]["id_leito"], "2026-10-14",
                                  nome_paciente="Francisca Aparecida das Neves Albuquerque de Vasconcelos Filho",
                                  obs_sim="arroz, feijão, carne moída, purê de batata, mamão, banana, aveia, suco de laranja sem açúcar, "
                                          "caldo de legumes, gelatina, iogurte natural, pão francês sem casca",
                                  obs_nao="leite integral, ovo cru, frituras, refrigerante, alimentos muito condimentados e ácidos",
                                  suplementos=[dict(id_suplemento=None, nome="Thopic Soya 1,5 kcal/ml", modulo="Fórmula completa",
                                                    qtd_dia=400.0, unidade="ml"),
                                               dict(id_suplemento=None, nome="Simbioflora", modulo="x", qtd_dia=None, unidade="g")])
        mdb.salvar_registro(cls.db, cls.longo)
        cls.dia = mdb.mapa_do_dia(cls.db, "2026-10-14", cls.setor["id_setor"])
        cls.saida = tempfile.mkdtemp(prefix="nutrilab_qa_")

    @classmethod
    def tearDownClass(cls):
        os.remove(cls.db)
        shutil.rmtree(cls.saida, ignore_errors=True)

    def test_suplemento_mostra_volume_refeicoes_agua_e_fruta_no_mapa(self):
        linha = mex.textos_linha({"codigo": "A01"}, {
            "nome_paciente": "Paciente", "suplementos": [
                {"nome": "Fórmula", "ml_oferta": 120, "agua_ml": 30, "refeicoes": ["desjejum", "ceia"],
                 "qtd_dia": 240, "batido_fruta": True, "unidade": "ml"},
                {"nome": "Módulo", "ml_oferta": 20, "agua_ml": 0, "refeicoes": ["almoco"],
                 "qtd_dia": 20, "batido_fruta": False, "unidade": "ml"}
            ]})
        suplementos = linha["supl"].splitlines()
        self.assertIn("120 mL/oferta × 2 = 240 mL/d", suplementos[0])
        self.assertIn("água: 30 mL/oferta", suplementos[0])
        self.assertIn("(batido com fruta)", suplementos[0])
        self.assertNotIn("batido com fruta", suplementos[1])

    def test_exportacao_da_visao_geral_identifica_o_setor(self):
        geral = mex._colunas("Todos_os_setores")
        especifico = mex._colunas("Clínica A")
        self.assertIn("setor", [c[0] for c in geral])
        self.assertNotIn("setor", [c[0] for c in especifico])
        textos = mex.textos_linha({"codigo": "A01", "setor": "UTI"}, None)
        self.assertEqual(textos["setor"], "UTI")

    def test_textos_da_celula_do_paciente(self):
        reg = mdb.obter_registro(self.db, "2026-10-14", self.leitos[1]["id_leito"]) or self.dia[0]["registro"]
        reg = dict(reg, sexo="H", cor="N", aj_cm=48.0, pp_cm=32.5, pb_cm=27.0, altura_cm=165.0, altura_origem="E",
                   peso_kg=70.5, peso_origem="R", imc=25.9, imc_class="Sobrepeso", nome_paciente="João da Silva")
        ab = mex.linhas_paciente(reg, abreviar=True)
        self.assertEqual(ab[0], [("João da Silva", "nome")])
        self.assertEqual(ab[1][0][0], "Sx: H  Cor: N  AJ: 48  PP: 32,5  PB: 27")
        self.assertEqual(ab[2][0][0], "Alt (cm): 165 (E)   Peso (kg): 70,5 (R)")
        self.assertEqual(ab[3], [("IMC (kg/m²): 25,9", "normal"), (" (Sobrepeso)", "alerta")])
        cheio = mex.linhas_paciente(reg, abreviar=False)
        self.assertEqual(cheio[1][0][0], "Sexo: Homem  Cor: Negro  AJ: 48 cm  PP: 32,5 cm  PB: 27 cm")
        self.assertEqual(cheio[2][0][0], "Altura (cm): 165 (Estimada)   Peso (kg): 70,5 (Real)")

    def test_excel(self):
        from openpyxl import load_workbook
        caminho = os.path.join(self.saida, "mapa_teste.xlsx")
        mex.exportar_excel(caminho, self.dia, "2026-10-14", self.setor["nome"])
        wb = load_workbook(caminho, rich_text=True)
        ws = wb.active
        self.assertEqual([ws.cell(4, c).value for c in range(1, 12)],
                         ["Lt", "Ac.", "Paciente", "Id.", "Reav.", "Via", "Caract. dieta", "Consist.", "Suplementos",
                          "Obs. (Sim/Não)", "F. Int."])
        self.assertGreaterEqual(ws.max_row, 4 + len(self.dia))
        self.assertEqual(ws.page_setup.orientation, "landscape")
        self.assertEqual(ws.print_title_rows.replace("$", ""), "1:4")
        # linha do caso longo (leito L01): célula do paciente em texto rico
        celula = ws["C5"].value
        self.assertEqual(ws["A5"].value, "L01")
        self.assertIn("Francisca Aparecida", str(celula))
        self.assertIn("IMC", str(celula))
        self.assertGreaterEqual(str(celula).count("\n"), 3)
        self.assertIsNotNone(ws["C5"].font)
        # o contrato atual representa leitos sem paciente por célula vazia;
        # a exportação continua incluindo a linha correspondente.
        sem_vagos = os.path.join(self.saida, "mapa_teste_sem_vagos.xlsx")
        mex.exportar_excel(sem_vagos, self.dia, "2026-10-14", self.setor["nome"], incluir_vagos=False)
        ws2 = load_workbook(sem_vagos).active
        self.assertFalse([r for r in range(4, ws2.max_row + 1) if ws2.cell(r, 3).value == "Vago"])

    def test_pdf_simulado(self):
        from fake_fpdf import FakePDF
        guarda = {}

        def fabrica(**kw):
            guarda["pdf"] = FakePDF(**kw)
            return guarda["pdf"]

        caminho = os.path.join(self.saida, "mapa_teste.pdf")
        mex.exportar_pdf(caminho, self.dia, "2026-10-14", self.setor["nome"], pdf_factory=fabrica)
        pdf = guarda["pdf"]
        self.assertGreaterEqual(len(pdf.paginas), 2)
        textos = [t[3] for t in pdf.textos]
        for titulo in ("Lt", "Ac.", "Paciente", "Id.", "Reav.", "Via", "Caract. dieta", "Consist.", "Suplementos",
                       "Obs. (Sim/Não)", "F. Int."):
            self.assertIn(mex._l1(titulo), textos)
        self.assertTrue(any("Francisca Aparecida" in t[3] for t in pdf.textos))
        self.assertTrue(any(t[4] == mex.VERMELHO_PDF and t[3].startswith(" (")
                            for t in pdf.textos), "classificação do IMC deve permanecer em vermelho")
        # nada ultrapassa a largura da página
        for _, x, _, txt, _ in pdf.textos:
            self.assertLess(x, 297 - 8)
        pdf.salvar_pngs(os.path.join(self.saida, "mapa_pdf"))
        self.assertTrue(os.path.getsize(caminho) > 1000)

    def test_latin1(self):
        self.assertEqual(mex._l1("ação – “ok” ≥ 5…"), 'ação - "ok" >= 5...')


class TestGraficos(unittest.TestCase):
    def test_agregacao_e_png(self):
        db = novo_banco()
        try:
            popular_mes(db, n_leitos=10)
            regs = mdb.registros_do_mes(db, 2026, 10)
            agg = mgr.agregar_mes(regs, 2026, 10)
            k = agg["kpis"]
            self.assertEqual(k["atendimentos"], len(regs))
            self.assertEqual(sum(v["total"] for v in agg["dias"].values()), len(regs))
            self.assertEqual(k["pastosa"], sum(1 for r in regs if r["consistencia"] == "Pastosa"))
            self.assertEqual(k["acompanhante"], sum(1 for r in regs if r["acompanhante"]))
            self.assertEqual(k["com_suplemento"], sum(1 for r in regs if r["via"] == "Oral" and r["suplementos"]))
            self.assertEqual(sum(agg["sup_nome"].values()), sum(len(r["suplementos"]) for r in regs))
            self.assertLessEqual(k["pacientes_unicos"], k["atendimentos"])
            self.assertEqual(len(agg["dias"]), 31)
            self.assertEqual(mdb.meses_com_dados(db), [(2026, 10)])
            # doenças crônicas (DM, HAS, DRC) e características da dieta (laxativa, constipante) são contadas à parte
            for campo, _, nome in mdb.CARACTERISTICAS:
                esperado = sum(1 for r in regs if r.get(campo))
                self.assertEqual(agg["carac"][nome], esperado, nome)
                destino = agg["cronicas"] if campo in mgr.CAMPOS_CRONICOS else agg["dieta_carac"]
                outro = agg["dieta_carac"] if campo in mgr.CAMPOS_CRONICOS else agg["cronicas"]
                self.assertEqual(destino[nome], esperado, nome)
                self.assertEqual(outro[nome], 0, nome)
            pngs = mgr.gerar_todos(agg)
            self.assertEqual(len(pngs), 10)
            self.assertEqual([c for c, _, _ in pngs], mgr.ordem_de_exibicao())
            for chave, _, b in pngs:
                self.assertEqual(b[:8], b"\x89PNG\r\n\x1a\n", chave)
            vazio = mgr.agregar_mes([], 2026, 2)
            self.assertEqual(len(vazio["dias"]), 28)
            for _, _, b in mgr.gerar_todos(vazio):
                self.assertEqual(b[:4], b"\x89PNG")
            pasta_graficos = tempfile.mkdtemp(prefix="nutrilab_graf_")
            try:
                mgr.salvar_graficos(agg, os.path.join(pasta_graficos, "graficos"))
            finally:
                shutil.rmtree(pasta_graficos, ignore_errors=True)
        finally:
            os.remove(db)

    def test_classificacao_separa_oral_sem_suplemento_oral_com_suplemento_e_enteral(self):
        registros = [
            {"data": "2026-11-01", "via": "Oral", "suplementos": [], "id_paciente": 1,
             "nome_paciente": "Paciente A", "acompanhante": False},
            {"data": "2026-11-01", "via": "Oral", "suplementos": [{"nome": "Produto oral", "modulo": "Fórmula completa"}],
             "id_paciente": 2, "nome_paciente": "Paciente B", "acompanhante": False},
            {"data": "2026-11-01", "via": "Enteral", "suplementos": [{"nome": "Fórmula enteral", "modulo": "Fórmula enteral"}],
             "id_paciente": 3, "nome_paciente": "Paciente C", "acompanhante": False},
            {"data": "2026-11-01", "via": "Zero", "suplementos": [], "id_paciente": 4,
             "nome_paciente": "Paciente D", "acompanhante": False},
        ]
        agg = mgr.agregar_mes(registros, 2026, 11)
        self.assertEqual(agg["classificacao_terapia"], {
            "Via oral sem suplementação": 1, "Via oral com suplementação": 1,
            "Dieta enteral": 1, "Via zero": 1})
        self.assertEqual(agg["kpis"]["oral_sem_suplemento"], 1)
        self.assertEqual(agg["kpis"]["oral_com_suplemento"], 1)
        self.assertEqual(agg["kpis"]["com_suplemento"], 1)
        self.assertEqual(agg["kpis"]["enteral"], 1)
        self.assertEqual(agg["dias"][1]["oral_sem_suplemento"], 1)
        self.assertEqual(agg["dias"][1]["oral_com_suplemento"], 1)
        self.assertEqual(agg["dias"][1]["enteral"], 1)
        spec = mgr.spec_classificacao_terapia(agg)
        self.assertEqual([(i["nome"], i["valor"]) for i in spec["itens"]], [
            ("Via oral sem suplementação", 1), ("Via oral com suplementação", 1), ("Dieta enteral", 1), ("Via zero", 1)])
        self.assertEqual(mgr.spec_perfil_dia(agg)["series"][-1]["nome"], "Dieta enteral")
        self.assertEqual(mgr.spec_resumo(agg)["titulo"], "Via da dieta e acompanhante")

    def test_grupos_cobrem_todos_os_graficos_sem_repetir(self):
        ids = [g["id"] for g in mgr.GRUPOS]
        self.assertEqual(len(ids), len(set(ids)))
        em_grupos = [c for g in mgr.GRUPOS for c in g["graficos"]]
        self.assertEqual(len(em_grupos), len(set(em_grupos)), "gráfico em dois grupos")
        self.assertEqual(set(em_grupos), set(mgr.GRAFICOS), "gráfico sem grupo, ou grupo com gráfico que não existe")
        self.assertEqual(mgr.ordem_de_exibicao(), em_grupos)
        for g in mgr.GRUPOS:
            self.assertTrue(g["titulo"] and g["cor"].startswith("#"), g["id"])

    def test_organizar_por_grupo(self):
        falsos = [(c, mgr.GRAFICOS[c][0], b"png") for c in mgr.ordem_de_exibicao()]
        grupos = mgr.organizar_por_grupo(falsos)
        self.assertEqual([g["id"] for g in grupos], ["atendimentos", "dieta", "suplementos", "cronicas"])
        self.assertEqual([c for g in grupos for c, _, _ in g["graficos"]], mgr.ordem_de_exibicao())
        self.assertEqual([c for c, _, _ in grupos[2]["graficos"]], ["suplementos", "modulos"])
        # o que não tem grupo não some: vai para "Outros gráficos", no fim
        grupos = mgr.organizar_por_grupo(falsos + [("novo", "Gráfico novo", b"png")])
        self.assertEqual(grupos[-1]["id"], "outros")
        self.assertEqual([c for c, _, _ in grupos[-1]["graficos"]], ["novo"])
        # grupo sem nenhum gráfico não aparece
        grupos = mgr.organizar_por_grupo([g for g in falsos if g[0] != "cronicas"])
        self.assertNotIn("cronicas", [g["id"] for g in grupos])
        self.assertEqual(mgr.organizar_por_grupo([]), [])

    def test_gerar_por_grupo(self):
        db = novo_banco()
        try:
            popular_mes(db, n_leitos=6)
            agg = mgr.agregar_mes(mdb.registros_do_mes(db, 2026, 10), 2026, 10)
            grupos = mgr.gerar_por_grupo(agg)
            self.assertEqual([g["id"] for g in grupos], ["atendimentos", "dieta", "suplementos", "cronicas"])
            self.assertEqual(sum(len(g["graficos"]) for g in grupos), 10)
            for g in grupos:
                for chave, titulo, png in g["graficos"]:
                    self.assertTrue(titulo and png[:4] == b"\x89PNG", chave)
        finally:
            os.remove(db)



class TestEscalasVisita(unittest.TestCase):
    def setUp(self):
        self.db = novo_banco()
        self.setor = mdb.criar_setor(self.db, "Escalas")
        self.leito = mdb.criar_leito(self.db, self.setor, "01")

    def tearDown(self):
        os.remove(self.db)

    def test_respostas_das_escalas_persistem_no_registro(self):
        respostas = {
            "bristol": "4 — Suave e macia (ideal)",
            "urina": "2 — Clara",
            "aceitacao": "75%",
        }
        mdb.salvar_registro(self.db, registro_base(
            self.db, self.leito, "2026-11-26",
            tipo_dieta="Hipossódica",
            escalas_visita_json=__import__("json").dumps(respostas, ensure_ascii=False)))
        salvo = mdb.obter_registro(self.db, "2026-11-26", self.leito)
        self.assertEqual(__import__("json").loads(salvo["escalas_visita_json"]), respostas)
        self.assertEqual(salvo["tipo_dieta"], "Hipossódica")

    def test_migracao_aditiva_e_idempotente(self):
        mdb.inicializar(self.db)
        mdb.inicializar(self.db)
        with conexao(self.db) as c:
            colunas = {r[1] for r in c.execute("PRAGMA table_info(Mapa_Registros)")}
        self.assertIn("escalas_visita_json", colunas)


if __name__ == "__main__":
    unittest.main(verbosity=2)
