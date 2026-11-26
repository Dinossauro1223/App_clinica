# -*- coding: utf-8 -*-
"""Testes sintéticos do almoxarifado e do cálculo de custos por refeição."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

import almox_db as db
import db_migracoes


class TestAlmoxarifado(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "clinica.db")
        db.inicializar(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def item(self, preco="5,00", nome="Arroz", unidade="kg"):
        return db.salvar_item(self.path, {
            "nome": nome, "unidade": unidade, "categoria": "Gêneros alimentícios",
            "valor_unitario": preco,
        })

    def test_preco_brasileiro_e_historico(self):
        iid = self.item("1.234,56")
        self.assertEqual(db.obter_item(self.path, iid)["valor_unitario"], 1234.56)
        db.salvar_item(self.path, {"id_item": iid, "nome": "Arroz", "unidade": "kg",
                                  "categoria": "Gêneros alimentícios", "valor_unitario": "1.300,00"})
        self.assertEqual([x["valor_unitario"] for x in db.historico_precos(self.path, iid)],
                         [1300.0, 1234.56])

    def test_compra_atualiza_preco_medio_sem_alterar_preco_do_movimento(self):
        iid = self.item("10,00")
        db.registrar_movimento(self.path, "2026-11-01", iid, "entrada", 10, "10,00")
        db.registrar_movimento(self.path, "2026-11-02", iid, "entrada", 10, "14,00")
        self.assertEqual(db.obter_item(self.path, iid)["saldo"], 20)
        self.assertEqual(db.obter_item(self.path, iid)["valor_unitario"], 12)
        compras = [m for m in db.listar_movimentos(self.path) if m["motivo"] == "compra"]
        self.assertEqual(sorted(m["valor_unitario"] for m in compras), [10, 14])

    def test_gasto_real_por_refeicao_dia_e_mes(self):
        iid = self.item()
        db.registrar_movimento(self.path, "2026-11-22", iid, "entrada", 10, "5,00")
        db.registrar_movimento(self.path, "2026-11-22", iid, "consumo", 2, refeicao="almoco")
        db.registrar_movimento(self.path, "2026-11-22", iid, "consumo", 1.5, refeicao="jantar")
        r = db.resumo_periodo(self.path, "2026-11-01", "2026-11-30")
        self.assertEqual({x["refeicao"]: x["total"] for x in r["realizado_refeicao"]},
                         {"almoco": 10.0, "jantar": 7.5})
        self.assertEqual({x["data"]: x["total"] for x in r["realizado_dia"]}, {"2026-11-22": 17.5})
        self.assertEqual(r["realizado_total"], 17.5)

    def test_consumo_exige_refeicao_e_estoque(self):
        iid = self.item()
        with self.assertRaisesRegex(ValueError, "refeição"):
            db.registrar_movimento(self.path, "2026-11-22", iid, "consumo", 1)
        with self.assertRaisesRegex(ValueError, "Saldo insuficiente"):
            db.registrar_movimento(self.path, "2026-11-22", iid, "consumo", 1, refeicao="almoco")

    def test_estorno_preserva_movimento_original_e_reverte_custo(self):
        iid = self.item("4,00")
        db.registrar_movimento(self.path, "2026-11-22", iid, "entrada", 5, "4,00")
        mid = db.registrar_movimento(self.path, "2026-11-22", iid, "consumo", 2, refeicao="almoco")
        estorno = db.estornar_movimento(self.path, mid, data="2026-11-22", justificativa="Lançamento duplicado")
        self.assertEqual(db.obter_item(self.path, iid)["saldo"], 5)
        rows = {m["id_movimento"]: m for m in db.listar_movimentos(self.path)}
        self.assertEqual(rows[mid]["motivo"], "consumo")
        self.assertEqual(rows[estorno]["id_estorno_de"], mid)
        self.assertEqual(db.resumo_periodo(self.path, "2026-11-22", "2026-11-22")["realizado_total"], 0)
        with self.assertRaisesRegex(ValueError, "já foi estornado"):
            db.estornar_movimento(self.path, mid)

    def test_programacao_estima_separada_e_gera_consumo_ao_realizar(self):
        iid = self.item("8,00")
        db.registrar_movimento(self.path, "2026-11-22", iid, "entrada", 20, "8,00")
        pid = db.criar_programacao(self.path, "2026-11-23", "almoco", 10)
        db.adicionar_item_programacao(self.path, pid, iid, "0,25")
        r = db.resumo_periodo(self.path, "2026-11-23", "2026-11-23")
        self.assertEqual(r["programado_total"], 20)
        self.assertEqual(r["realizado_total"], 0)
        db.alterar_status_programacao(self.path, pid, "confirmada")
        self.assertEqual(len(db.realizar_programacao(self.path, pid)), 1)
        self.assertEqual(db.obter_item(self.path, iid)["saldo"], 17.5)
        r = db.resumo_periodo(self.path, "2026-11-23", "2026-11-23")
        self.assertEqual(r["realizado_total"], 20)
        self.assertEqual(r["programado_total"], 0)

    def test_validade_busca_categoria_e_observacao_de_movimento(self):
        cedo = db.salvar_item(self.path, {"nome":"Tempero", "unidade":"g", "categoria":"Temperos e condimentos", "validade":"2026-11-30", "valor_unitario":"0,05"})
        tarde = db.salvar_item(self.path, {"nome":"Arroz", "unidade":"kg", "categoria":"Grãos e cereais", "validade":"2026-12-15", "valor_unitario":"5,00"})
        db.salvar_item(self.path, {"nome":"Feijão", "unidade":"kg", "categoria":"Grãos e cereais", "valor_unitario":"8,00"})
        ordenados = db.listar_itens(self.path)
        self.assertEqual([x["nome"] for x in ordenados], ["Tempero", "Arroz", "Feijão"])
        self.assertEqual(db.listar_itens(self.path, termo="temp")[0]["id_item"], cedo)
        self.assertEqual(ordenados[0]["categoria"], "Temperos e condimentos")
        db.registrar_movimento(self.path, "2026-11-25", tarde, "entrada", 10, "5,00", observacao="Recebimento parcial conferido")
        mov = db.listar_movimentos(self.path, id_item=tarde)[0]
        self.assertEqual(mov["observacao"], "Recebimento parcial conferido")

    def test_unidades_nao_sao_convertidas_implicitamente(self):
        kg = self.item("4", "Farinha", "kg")
        g = self.item("0,004", "Farinha", "g")
        db.registrar_movimento(self.path, "2026-11-22", kg, "entrada", 1, "4")
        self.assertEqual(db.obter_item(self.path, kg)["saldo"], 1)
        self.assertEqual(db.obter_item(self.path, g)["saldo"], 0)


class TestMigracaoAlmox(unittest.TestCase):
    def test_v2_cria_tabelas_e_tem_reversao(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "clinica.db")
            c = sqlite3.connect(path)
            c.execute("CREATE TABLE Pacientes(id INTEGER PRIMARY KEY)")
            c.execute("CREATE TABLE Consultas(id INTEGER PRIMARY KEY)")
            c.commit()
            c.close()
            r = db_migracoes.aplicar_migracoes(path, alvo=5, backup=False)
            self.assertEqual(r.versao_final, 5)
            c = sqlite3.connect(path)
            nomes = {x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({"Almox_Itens", "Almox_Movimentos", "Almox_Programacoes"}.issubset(nomes))
            c.close()
            r = db_migracoes.reverter_migracoes(path, para_versao=4, backup=False)
            self.assertEqual(r.versao_final, 4)
            c = sqlite3.connect(path)
            nomes = {x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            c.close()
            self.assertNotIn("Almox_Itens", nomes)
            self.assertIn("Pacientes", nomes)


class TestMenuAlmox(unittest.TestCase):
    def test_menu_e_callback_desktop(self):
        raiz = Path(__file__).resolve().parents[1]
        source = (raiz / "main.py").read_text(encoding="utf-8")
        self.assertIn('("Almoxarifado", self.tela_almoxarifado)', source)
        self.assertIn("def tela_almoxarifado(self):", source)
        self.assertIn("from almox_ui import AlmoxUI", source)
        self.assertIn("AlmoxUI(self, caminho_do_banco(), get_base_path()).mostrar()", source)


if __name__ == "__main__":
    unittest.main()
