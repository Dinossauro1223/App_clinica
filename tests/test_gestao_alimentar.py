# -*- coding: utf-8 -*-
"""Testes da Gestão alimentar (Fichas). Só usa bases e planilhas sintéticas."""
import os
import tempfile
import unittest
from pathlib import Path

import gestao_alimentar_db as ga

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None


@unittest.skipIf(openpyxl is None, "openpyxl não instalado")
class TestGestaoAlimentar(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.db = str(self.dir / "nutrilab.db")
        ga.inicializar(self.db)

    def planilha_tbca(self):
        caminho = self.dir / "tbca_teste.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "TBCA (2024)"
        ws.append([
            "ID", "TIPO", "NPU", "Fator de correção (FC) - Alimentos Per Capita (1997)",
            "FC - menucontrol.com", "Medida caseira (MD)", "PER CAPITA", "ALIMENTO",
            "Kcal", "Proteína", "Carboidrato", "Lipídio", "Ácidos graxos saturados",
            "Ácidos graxos polinsaturados", "Ácidos graxos monoinsaturados", "Ácidos graxos trans",
            "Colesterol", "Fibra alimentar", "Sódio", "Ferro", "Vitamina C", "Equivalente de folato",
            "Umidade g", "Selênio", "Cobre", "Potássio", "Fósforo", "Magnésio", "Vitamina D",
            "Tiamina", "Riboflavina", "Niacina", "Vitamina B6", "Alfa0tocoferol (Vitamina E)",
            "Zinco", "Cálcio", "Vitamina A (RE)", "Vitamina A (RAE)", "Vitamina B12",
        ])
        ws.append(["T001", "Alimento", 70, 1.2, 1.1, "1 colher", 100, "Alimento teste",
                   350, 7, 80, 1, 0.2, 0.3, 0.4, 0, 0, 2, 5, 1, 0, 10, 12, 2, 3, 4,
                   50, 20, 0, 0.1, 0.2, 1, 0.1, 0.3, 2, 15, 9, 8, 0])
        wb.save(caminho)
        return str(caminho)

    def test_importa_cabecalhos_da_planilha_tbca_e_nutrientes_adicionais(self):
        arquivo = self.planilha_tbca()
        self.assertEqual(ga.importar_tbca_excel(self.db, arquivo), 1)
        item = ga.listar_alimentos(self.db, "T001")[0]
        self.assertEqual(item["alimento"], "Alimento teste")
        self.assertEqual(item["fc_referencia"], 1.2)
        self.assertEqual(item["kcal"], 350)
        self.assertEqual(item["proteina"], 7)
        self.assertEqual(item["calcio"], 15)
        self.assertEqual(item["vitamina_a_re"], 9)
        self.assertEqual(item["vitamina_b12"], 0)

    def test_calcula_fc_custo_por_porcao_e_nutrientes(self):
        ga.importar_tbca_excel(self.db, self.planilha_tbca())
        ga.sincronizar_produtos_almox(self.db, [{
            "id_item": 7, "nome": "Pacote alimento", "unidade": "pacote",
            "preco_unitario": 10.0, "embalagem_qtd": 1000, "embalagem_un": "g",
            "qtd": 3, "data_base": "2026-11-22",
        }])
        ficha_id = ga.salvar_ficha(self.db, "Preparação teste", "Acompanhamento", 2, [{
            "nome": "Alimento teste", "tbca_id": "T001", "id_produto_mobile": 7,
            "unidade": "g", "qtd_per_capita": 100, "fator_correcao": 1.2,
        }])
        resultado = ga.calcular_ficha(self.db, ficha_id)
        self.assertAlmostEqual(resultado["linhas"][0]["qtd_bruta_total"], 240)
        self.assertAlmostEqual(resultado["custo_total"], 2.4)
        self.assertAlmostEqual(resultado["custo_por_porcao"], 1.2)
        self.assertAlmostEqual(resultado["nutrientes_per_capita"]["kcal"], 350)
        self.assertTrue(resultado["linhas"][0]["estoque_suficiente"])
        self.assertEqual(resultado["custos_faltantes"], 0)

    def test_nao_converte_volume_em_gramas_sem_densidade(self):
        ga.importar_tbca_excel(self.db, self.planilha_tbca())
        ficha_id = ga.salvar_ficha(self.db, "Suco", "Suco", 1, [{
            "nome": "Alimento teste", "tbca_id": "T001", "unidade": "ml", "qtd_per_capita": 100,
            "fator_correcao": 1,
        }])
        resultado = ga.calcular_ficha(self.db, ficha_id)
        self.assertIsNone(resultado["linhas"][0]["nutrientes_per_capita"]["kcal"])
        self.assertEqual(resultado["nutrientes_faltantes"]["kcal"], 1)

    def test_custo_fica_incompleto_sem_produto_vinculado(self):
        ficha_id = ga.salvar_ficha(self.db, "Salada", "Salada", 4, [{
            "nome": "Alface", "unidade": "g", "qtd_per_capita": 30, "fator_correcao": 1.1,
        }])
        resultado = ga.calcular_ficha(self.db, ficha_id)
        self.assertIsNone(resultado["custo_total"])
        self.assertEqual(resultado["custos_faltantes"], 1)

    def test_compara_estoque_mesmo_quando_preco_nao_foi_cadastrado(self):
        ga.sincronizar_produtos_almox(self.db, [{
            "id_item": 10, "nome": "Arroz", "unidade": "pacote",
            "preco_unitario": None, "embalagem_qtd": 1000, "embalagem_un": "g",
            "qtd": 1, "data_base": "2026-11-22",
        }])
        ficha_id = ga.salvar_ficha(self.db, "Arroz", "Acompanhamento", 2, [{
            "nome": "Arroz", "unidade": "g", "qtd_per_capita": 100, "id_produto_mobile": 10,
        }])
        resultado = ga.calcular_ficha(self.db, ficha_id)
        self.assertIsNone(resultado["custo_total"])
        self.assertTrue(resultado["linhas"][0]["estoque_suficiente"])
        self.assertEqual(resultado["custos_faltantes"], 1)

    def test_nao_calcula_custo_entre_dimensoes_incompativeis(self):
        ga.sincronizar_produtos_almox(self.db, [{
            "id_item": 8, "nome": "Garrafa", "unidade": "un", "preco_unitario": 5,
            "embalagem_qtd": 500, "embalagem_un": "ml", "qtd": 10,
        }])
        ficha_id = ga.salvar_ficha(self.db, "Massa", "Outra", 1, [{
            "nome": "Farinha", "unidade": "g", "qtd_per_capita": 100,
            "id_produto_mobile": 8,
        }])
        resultado = ga.calcular_ficha(self.db, ficha_id)
        self.assertIsNone(resultado["custo_total"])
        self.assertEqual(resultado["custos_faltantes"], 1)

    def test_persiste_medida_caseira_e_npu_da_ficha(self):
        ficha_id = ga.salvar_ficha(self.db, "Purê", "Guarnição", 12, [{
            "nome": "Batata", "unidade": "g", "qtd_per_capita": 80,
            "medida_caseira": "1 unidade média", "npu": 70,
        }])
        ingrediente = ga.obter_ficha(self.db, ficha_id)["ingredientes"][0]
        self.assertEqual(ingrediente["medida_caseira"], "1 unidade média")
        self.assertEqual(ingrediente["npu"], 70)

    def test_numero_rejeita_nan_e_infinito(self):
        self.assertIsNone(ga._numero(float("nan")))
        self.assertIsNone(ga._numero(float("inf")))
        self.assertIsNone(ga._numero(float("-inf")))

    def test_estoque_sem_lancamento_nao_e_tratado_como_zero_conhecido(self):
        ga.sincronizar_produtos_almox(self.db, [{
            "id_item": 9, "nome": "Farinha", "unidade": "pacote",
            "preco_unitario": 5.0, "embalagem_qtd": 1000, "embalagem_un": "g",
            "qtd": None, "data_base": None,
        }])
        ficha_id = ga.salvar_ficha(self.db, "Bolo", "Preparação", 1, [{
            "nome": "Farinha", "unidade": "g", "qtd_per_capita": 100, "id_produto_mobile": 9,
        }])
        resultado = ga.calcular_ficha(self.db, ficha_id)
        self.assertEqual(resultado["estoque_incompleto"], 1)
        self.assertIsNone(resultado["linhas"][0]["estoque_suficiente"])

    def test_edita_e_inativa_ficha_sem_apagar_historico(self):
        ficha_id = ga.salvar_ficha(self.db, "Arroz", "Acompanhamento", 10, [
            {"nome": "Arroz", "unidade": "g", "qtd_per_capita": 50}
        ])
        ga.salvar_ficha(self.db, "Arroz integral", "Acompanhamento", 8, [
            {"nome": "Arroz integral", "unidade": "g", "qtd_per_capita": 55}
        ], id_ficha=ficha_id)
        self.assertEqual(ga.obter_ficha(self.db, ficha_id)["nome"], "Arroz integral")
        self.assertTrue(ga.inativar_ficha(self.db, ficha_id))
        self.assertEqual(ga.listar_fichas(self.db), [])
        self.assertEqual(ga.listar_fichas(self.db, incluir_inativas=True)[0]["id_ficha"], ficha_id)


    def criar_movimento_mobile(self, hora="12:00", qtd=2):
        with ga._conexao(self.db) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS Mobile_Movimentos(
                data TEXT NOT NULL,id_mobile INTEGER NOT NULL,hora TEXT,origem TEXT,destino TEXT,
                item TEXT,unidade TEXT,qtd REAL,divergente INTEGER,id_item_mobile INTEGER,
                por_usuario TEXT,valor_unitario_snapshot REAL,custo_snapshot REAL,
                PRIMARY KEY(data,id_mobile))""")
            conn.execute("""INSERT INTO Mobile_Movimentos(
                data,id_mobile,hora,origem,destino,item,unidade,qtd,divergente,id_item_mobile,
                por_usuario,valor_unitario_snapshot,custo_snapshot)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ("2026-11-24", 501, hora, "almox", "cozinha", "Pacote alimento",
                 "pacote", qtd, 0, 7, "almoxarife", 10.0, qtd * 10.0))

    def test_gera_ficha_rascunho_com_base_no_horario_e_vinculo_tbca(self):
        ga.importar_tbca_excel(self.db, self.planilha_tbca())
        ga.sincronizar_produtos_almox(self.db, [{
            "id_item": 7, "nome": "Pacote alimento", "unidade": "pacote",
            "preco_unitario": 10.0, "embalagem_qtd": 500, "embalagem_un": "g",
            "tbca_id": "T001", "qtd": 4, "data_base": "2026-11-24",
        }])
        with ga._conexao(self.db) as conn:
            conn.execute("""INSERT INTO GA_Preparacoes_Dia(
                data,refeicao,nome,porcoes_previstas,id_ficha,ativa,criado_em,atualizado_em)
                VALUES(?,?,?,?,NULL,1,?,?)""",
                ("2026-11-24", "almoco", "Preparação do almoço", 10, "2026-11-24", "2026-11-24"))
        self.criar_movimento_mobile()
        movimentos = ga.listar_movimentos_cozinha(self.db, "2026-11-24", "2026-11-24")
        resultado = ga.gerar_rascunhos_por_horario(
            self.db, "2026-11-24", movimentos,
            {"almoco": {"abre": "11:00", "fecha": "14:00"}}
        )
        self.assertEqual(resultado["alocadas"], 1)
        self.assertEqual(resultado["rascunhos"], 1)
        preparacao = ga.listar_preparacoes_dia(self.db, "2026-11-24")[0]
        self.assertIsNotNone(preparacao["id_ficha"])
        ficha = ga.obter_ficha(self.db, preparacao["id_ficha"])
        ingrediente = ficha["ingredientes"][0]
        self.assertEqual(ingrediente["tbca_id"], "T001")
        self.assertEqual(ingrediente["unidade"], "g")
        self.assertAlmostEqual(ingrediente["qtd_per_capita"], 100)
        self.assertAlmostEqual(ingrediente["fator_correcao"], 1.2)
        self.assertEqual(ingrediente["npu"], 70)
        movimentos = ga.listar_movimentos_cozinha(self.db, "2026-11-24", "2026-11-24")
        segunda = ga.gerar_rascunhos_por_horario(
            self.db, "2026-11-24", movimentos,
            {"almoco": {"abre": "11:00", "fecha": "14:00"}}
        )
        self.assertEqual(segunda["rascunhos"], 0)

    def test_nao_aloca_automaticamente_quando_houver_duas_preparacoes_na_refeicao(self):
        with ga._conexao(self.db) as conn:
            conn.execute("""CREATE TABLE Mobile_Movimentos(
                data TEXT NOT NULL,id_mobile INTEGER NOT NULL,hora TEXT,origem TEXT,destino TEXT,
                item TEXT,unidade TEXT,qtd REAL,divergente INTEGER,id_item_mobile INTEGER,
                por_usuario TEXT,valor_unitario_snapshot REAL,custo_snapshot REAL,
                PRIMARY KEY(data,id_mobile))""")
            for nome in ("Preparação A", "Preparação B"):
                conn.execute("""INSERT INTO GA_Preparacoes_Dia(
                    data,refeicao,nome,porcoes_previstas,id_ficha,ativa,criado_em,atualizado_em)
                    VALUES(?,?,?,?,NULL,1,?,?)""",
                    ("2026-11-24", "almoco", nome, 10, "2026-11-24", "2026-11-24"))
            conn.execute("""INSERT INTO Mobile_Movimentos(
                data,id_mobile,hora,origem,destino,item,unidade,qtd,divergente,id_item_mobile,
                por_usuario,valor_unitario_snapshot,custo_snapshot)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ("2026-11-24", 502, "12:00", "almox", "cozinha", "Arroz",
                 "pacote", 1, 0, 99, "almoxarife", 5.0, 5.0))
        movimentos = ga.listar_movimentos_cozinha(self.db, "2026-11-24", "2026-11-24")
        resultado = ga.gerar_rascunhos_por_horario(
            self.db, "2026-11-24", movimentos,
            {"almoco": {"abre": "11:00", "fecha": "14:00"}}
        )
        self.assertEqual(resultado["varias_preparacoes"], 1)
        self.assertEqual(resultado["alocadas"], 0)



if __name__ == "__main__":
    unittest.main()
