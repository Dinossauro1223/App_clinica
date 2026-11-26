# -*- coding: utf-8 -*-
"""Testes sintéticos para conciliação de retiradas e consumo da cozinha."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

import gestao_alimentar_db as ga
import integracao_mobile as im
from mobile import servidor as sv


class TestConsumoCozinha(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.db = str(root / "desktop.db")
        self.mobile_db = str(root / "mobile.db")
        ga.inicializar(self.db)
        sv.preparar_banco(self.mobile_db)
        self._criar_mobile_sintetico()
        self.importacao = im.importar_movimentos_cozinha(
            self.db, self.mobile_db, "2026-11-20", "2026-11-22"
        )

    def test_le_catalogo_com_preco_embalagem_e_saldo_mais_recente_do_almox(self):
        c = sv.conectar(self.mobile_db)
        try:
            c.executemany("INSERT INTO estoque_dia(data,estoque,id_item,qtd,por_usuario,por_perfil,atualizado_em) "
                          "VALUES(?,?,?,?,?,?,?)", [
                ("2026-11-20","almox",1,12,1,"admin",sv.agora()),
                ("2026-11-21","almox",1,8,1,"admin",sv.agora()),
                ("2026-11-22","cozinha",1,3,1,"estoque_cozinha",sv.agora()),
            ])
            c.commit()
        finally:
            c.close()
        feijao = next(x for x in im.ler_produtos_almox(self.mobile_db) if x["id_item"] == 1)
        self.assertEqual(feijao["preco_unitario"], 8.0)
        self.assertEqual((feijao["embalagem_qtd"], feijao["embalagem_un"]), (1000.0, "g"))
        self.assertEqual((feijao["qtd"], feijao["data_base"]), (8.0, "2026-11-21"))

    def test_devolucao_cozinha_almox_reduz_retirada_e_custo_liquidos(self):
        c = sv.conectar(self.mobile_db)
        try:
            c.execute("""INSERT INTO movimentos
                (id,data,hora,origem,destino,id_item,qtd,por_usuario,divergente,preco_unitario_snapshot,custo_snapshot,observacao)
                VALUES(105,'2026-11-20','12:00','cozinha','almox',1,2,1,0,7.2,14.4,'Devolução de sobra')""")
            c.commit()
        finally:
            c.close()
        im.importar_movimentos_cozinha(self.db,self.mobile_db,"2026-11-20","2026-11-22")
        movimentos = ga.listar_movimentos_cozinha(self.db,"2026-11-20","2026-11-22")
        feijao = next(x for x in movimentos if x["id_mobile"]==105)
        original = next(x for x in movimentos if x["id_mobile"]==101)
        self.assertEqual(feijao["qtd"],-2)
        self.assertEqual(original["qtd_devolvida"],2)
        self.assertEqual(original["qtd_disponivel_para_alocar"],3)
        with self.assertRaises(ValueError):
            ga.salvar_alocacoes_retirada(self.db,"2026-11-20",101,[{"tipo_destino":"uso_geral","quantidade":5}])
        ga.salvar_alocacoes_retirada(self.db,"2026-11-20",101,[{"tipo_destino":"uso_geral","quantidade":3}])
        with sqlite3.connect(self.db) as c:
            observacao = c.execute("SELECT observacao FROM Mobile_Movimentos WHERE data='2026-11-20' AND id_mobile=105").fetchone()[0]
        self.assertEqual(observacao, "Devolução de sobra")
        original=next(x for x in ga.listar_movimentos_cozinha(self.db,"2026-11-20","2026-11-22") if x["id_mobile"]==101)
        self.assertEqual(original["qtd_devolvida_alocada"],2)
        self.assertEqual(original["qtd_devolvida_preparacao"],2)
        resumo=ga.resumo_consumo_observado(self.db,"2026-11-20","2026-11-22")
        item=next(x for x in resumo["itens"] if x["item"]=="Feijão")
        self.assertEqual(item["total_retirado"],6.0)  # 5 + 3 - 2 devolvidos
        self.assertAlmostEqual(item["custo_total"],45.6)  # 36 + 24 - 14.4

    def test_devolucao_reduz_alocacao_ja_lancada_na_ficha(self):
        ga.salvar_preparacoes_dia(self.db,"2026-11-20","almoco",[
            {"nome":"Feijão cozido","porcoes_previstas":100}
        ])
        prep = ga.listar_preparacoes_dia(self.db,"2026-11-20","almoco")[0]["id_preparacao_dia"]
        ga.salvar_alocacoes_retirada(self.db,"2026-11-20",101,[{
            "tipo_destino":"preparacao","id_preparacao_dia":prep,"quantidade":5
        }])
        c=sv.conectar(self.mobile_db)
        try:
            c.execute("""INSERT INTO movimentos
                (id,data,hora,origem,destino,id_item,qtd,por_usuario,divergente,preco_unitario_snapshot,custo_snapshot,observacao)
                VALUES(105,'2026-11-20','12:00','cozinha','almox',1,2,1,0,7.2,14.4,'Devolução parcial')""")
            c.commit()
        finally:
            c.close()
        im.importar_movimentos_cozinha(self.db,self.mobile_db,"2026-11-20","2026-11-22")
        resumo=ga.resumo_consumo_observado(self.db,"2026-11-20","2026-11-22")
        item=next(x for x in resumo["itens"] if x["item"]=="Feijão")
        ficha=next(x for x in resumo["por_preparacao"] if x["preparacao"]=="Feijão cozido")
        self.assertEqual(item["total_retirado"],6.0)
        self.assertEqual(item["total_alocado"],3.0)
        self.assertAlmostEqual(item["custo_alocado"],21.6)
        self.assertEqual(ficha["quantidade_total"],3.0)
        self.assertAlmostEqual(ficha["custo_total"],21.6)

    def test_custo_alocado_fica_indefinido_quando_preco_nao_existe(self):
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE Mobile_Movimentos SET valor_unitario_snapshot=NULL,custo_snapshot=NULL "
                      "WHERE data='2026-11-20' AND id_mobile=102")
        ga.salvar_alocacoes_retirada(self.db,"2026-11-20",102,[
            {"tipo_destino":"uso_geral","quantidade":0.5}
        ],usuario="teste")
        oleo = next(x for x in ga.listar_movimentos_cozinha(self.db,"2026-11-20","2026-11-20")
                    if x["id_mobile"] == 102)
        self.assertIsNone(oleo["custo_alocado"])
        resumo = ga.resumo_consumo_observado(self.db,"2026-11-20","2026-11-22")
        item = next(x for x in resumo["itens"] if x["item"] == "Óleo")
        self.assertIsNone(item["custo_alocado"])

    def test_transferencia_mobile_guarda_preco_historico(self):
        db = str(Path(self.tmp.name) / "snapshot.db")
        sv.preparar_banco(db)
        c = sv.conectar(db)
        try:
            c.execute("""INSERT INTO itens(id,nome,unidade,preco_unitario,embalagem_qtd,embalagem_un)
                         VALUES(1,'Óleo','un',7.25,900,'ml')""")
            d=sv.hoje()
            c.execute("""INSERT INTO estoque_dia(data,estoque,id_item,qtd,por_usuario,por_perfil,atualizado_em)
                         VALUES(?,?,?,?,?,?,?)""",(d,"almox",1,10,1,"admin",sv.agora()))
            sv.post_reposicao(c,{"id":1,"perfil":"estoque_cozinha"},"cozinha",{"id_item":1,"qtd":5,"origem":"almox"})
            mov=c.execute("SELECT * FROM movimentos").fetchone()
            self.assertEqual(mov["preco_unitario_snapshot"],7.25)
            self.assertAlmostEqual(mov["custo_snapshot"],36.25)
        finally:
            c.close()

    def _criar_mobile_sintetico(self):
        c = sv.conectar(self.mobile_db)
        try:
            c.execute("""INSERT INTO itens
                (id,nome,unidade,preco_unitario,embalagem_qtd,embalagem_un)
                VALUES(1,'Feijão','kg',8.0,1,'kg')""")
            c.execute("""INSERT INTO itens
                (id,nome,unidade,preco_unitario,embalagem_qtd,embalagem_un)
                VALUES(2,'Óleo','un',7.5,900,'ml')""")
            c.execute("""INSERT INTO movimentos
                (id,data,hora,origem,destino,id_item,qtd,por_usuario,divergente,
                 preco_unitario_snapshot,custo_snapshot)
                VALUES(101,'2026-11-20','06:20','almox','cozinha',1,5,1,0,7.2,36.0)""")
            c.execute("""INSERT INTO movimentos
                (id,data,hora,origem,destino,id_item,qtd,por_usuario,divergente,
                 preco_unitario_snapshot,custo_snapshot)
                VALUES(102,'2026-11-20','06:25','almox','cozinha',2,1,1,0,7.5,7.5)""")
            c.execute("""INSERT INTO movimentos
                (id,data,hora,origem,destino,id_item,qtd,por_usuario,divergente,
                 preco_unitario_snapshot,custo_snapshot)
                VALUES(103,'2026-11-20','11:10','cozinha','copa',1,2,2,0,7.2,14.4)""")
            c.execute("""INSERT INTO movimentos
                (id,data,hora,origem,destino,id_item,qtd,por_usuario,divergente,
                 preco_unitario_snapshot,custo_snapshot)
                VALUES(104,'2026-11-22','06:15','almox','cozinha',1,3,1,0,8.0,24.0)""")
            c.commit()
        finally:
            c.close()

    def test_importacao_por_intervalo_e_idempotencia(self):
        self.assertEqual(self.importacao["importados"], 4)
        self.assertEqual(self.importacao["retiradas_cozinha"], 3)
        segunda = im.importar_movimentos_cozinha(
            self.db, self.mobile_db, "2026-11-20", "2026-11-22"
        )
        self.assertEqual(segunda["importados"], 4)
        with sqlite3.connect(self.db) as c:
            total = c.execute("SELECT COUNT(*) FROM Mobile_Movimentos").fetchone()[0]
        self.assertEqual(total, 4)

    def test_lista_so_conta_almox_para_cozinha_e_preserva_preco(self):
        rows = ga.listar_movimentos_cozinha(self.db, "2026-11-20", "2026-11-22")
        self.assertEqual(len(rows), 3)
        feijao = [x for x in rows if x["item"] == "Feijão"]
        self.assertEqual([x["id_mobile"] for x in feijao], [104, 101])
        self.assertEqual(feijao[0]["preco_unitario_snapshot"], 8.0)
        self.assertEqual(feijao[1]["preco_unitario_snapshot"], 7.2)
        self.assertEqual(feijao[1]["origem_preco"], "historico")

    def test_preparacoes_esperadas_e_vinculo_opcional_a_ficha(self):
        qtd = ga.salvar_preparacoes_dia(self.db, "2026-11-20", "almoco", [
            {"nome": "Feijão cozido", "porcoes_previstas": 100},
            {"nome": "Arroz branco", "porcoes_previstas": 100},
        ])
        self.assertEqual(qtd, 2)
        preparacoes = ga.listar_preparacoes_dia(self.db, "2026-11-20", "almoco")
        self.assertEqual({x["nome"] for x in preparacoes}, {"Feijão cozido", "Arroz branco"})
        with self.assertRaises(ValueError):
            ga.salvar_preparacoes_dia(self.db, "2026-11-20", "refeicao-invalida", ["Teste"])

    def test_alocacao_parcial_revisao_e_pendencia(self):
        ga.sincronizar_produtos_almox(self.db, [
            {"id":1,"nome":"Feijão","unidade":"kg","preco_unitario":8.0,"qtd":10},
        ])
        ga.salvar_preparacoes_dia(self.db, "2026-11-20", "almoco", [
            {"nome":"Feijão cozido","porcoes_previstas":100},
            {"nome":"Caldo de feijão","porcoes_previstas":50},
        ])
        preps = ga.listar_preparacoes_dia(self.db, "2026-11-20", "almoco")
        prep = next(x for x in preps if x["nome"] == "Feijão cozido")
        mov = next(x for x in ga.listar_movimentos_cozinha(self.db,"2026-11-20","2026-11-20")
                   if x["id_mobile"] == 101)
        self.assertAlmostEqual(mov["qtd_disponivel_para_alocar"], 5.0)
        r = ga.salvar_alocacoes_retirada(self.db,"2026-11-20",101,[
            {"tipo_destino":"preparacao","id_preparacao_dia":prep["id_preparacao_dia"],"quantidade":3},
            {"tipo_destino":"uso_geral","quantidade":1},
        ],usuario="teste")
        self.assertAlmostEqual(r["alocada"],4.0)
        self.assertAlmostEqual(r["pendente"],1.0)
        ativas=ga.listar_alocacoes_retirada(self.db,"2026-11-20",101)
        self.assertEqual(len(ativas),2)
        self.assertAlmostEqual(sum(x["quantidade"] for x in ativas),4.0)
        revisoes=ga.listar_alocacoes_retirada(self.db,"2026-11-20",101,incluir_revisoes=True)
        self.assertEqual(len(revisoes),2)
        r2=ga.salvar_alocacoes_retirada(self.db,"2026-11-20",101,[
            {"tipo_destino":"preparacao","id_preparacao_dia":prep["id_preparacao_dia"],"quantidade":2},
        ],usuario="teste")
        self.assertEqual(r2["revisao"],2)
        atual=ga.listar_alocacoes_retirada(self.db,"2026-11-20",101)
        todas=ga.listar_alocacoes_retirada(self.db,"2026-11-20",101,incluir_revisoes=True)
        self.assertEqual(len(atual),1)
        self.assertEqual(len(todas),3)
        self.assertEqual(sum(x["ativa"] for x in todas),1)

    def test_nao_permite_alocar_mais_que_a_retirada(self):
        ga.salvar_preparacoes_dia(self.db,"2026-11-20","almoco",["Feijão"])
        prep=ga.listar_preparacoes_dia(self.db,"2026-11-20","almoco")[0]
        with self.assertRaisesRegex(ValueError,"excede"):
            ga.salvar_alocacoes_retirada(self.db,"2026-11-20",101,[
                {"tipo_destino":"preparacao","id_preparacao_dia":prep["id_preparacao_dia"],"quantidade":5.1}
            ])

    def test_media_por_item_e_por_preparacao(self):
        ga.sincronizar_produtos_almox(self.db,[
            {"id":1,"nome":"Feijão","unidade":"kg","preco_unitario":8.0,"qtd":10}
        ])
        ga.salvar_preparacoes_dia(self.db,"2026-11-20","almoco",[
            {"nome":"Feijão cozido","porcoes_previstas":100}
        ])
        prep=ga.listar_preparacoes_dia(self.db,"2026-11-20","almoco")[0]
        ga.salvar_alocacoes_retirada(self.db,"2026-11-20",101,[
            {"tipo_destino":"preparacao","id_preparacao_dia":prep["id_preparacao_dia"],"quantidade":4}
        ])
        resumo=ga.resumo_consumo_observado(self.db,"2026-11-20","2026-11-22")
        feijao=next(x for x in resumo["itens"] if x["item"]=="Feijão")
        self.assertAlmostEqual(feijao["total_retirado"],8.0)
        self.assertAlmostEqual(feijao["media_diaria_periodo"],8/3)
        self.assertAlmostEqual(feijao["custo_total"],60.0)
        receita=next(x for x in resumo["por_preparacao"] if x["preparacao"]=="Feijão cozido")
        self.assertAlmostEqual(receita["media_por_execucao"],4.0)
        self.assertAlmostEqual(receita["media_por_porcao_prevista"],0.04)
        self.assertAlmostEqual(receita["custo_total"],28.8)


if __name__ == "__main__":
    unittest.main()
