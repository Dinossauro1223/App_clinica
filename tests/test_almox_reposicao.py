# -*- coding: utf-8 -*-
"""Testes de pedidos de reposição e prazo médio calculado com datas reais."""
import tempfile
import unittest
from pathlib import Path
import almox_db
import almox_reposicao as repo

class TestReposicaoAlmox(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "clinica.db")
        almox_db.inicializar(self.db)
        repo.inicializar(self.db)
        self.item = almox_db.salvar_item(self.db, {
            "nome": "Arroz", "unidade": "kg",
            "categoria": "Gêneros alimentícios", "valor_unitario": "5,00"
        })

    def tearDown(self):
        self.tmp.cleanup()

    def test_recebimento_registra_entrada_e_prazo_real(self):
        pedido = repo.solicitar(self.db, self.item, "10", solicitado_por="Ana",
                                fornecedor="Fornecedor A", quando="2026-11-01")
        self.assertEqual(almox_db.obter_item(self.db, self.item)["saldo"], 0)
        movimento = repo.receber(self.db, pedido, recebido_por="Bia", quando="2026-11-06")
        self.assertEqual(almox_db.obter_item(self.db, self.item)["saldo"], 10)
        registro = repo.listar(self.db)[0]
        self.assertEqual(registro["status"], "recebido")
        self.assertEqual(registro["solicitado_por"], "Ana")
        self.assertEqual(registro["recebido_por"], "Bia")
        self.assertEqual(registro["id_movimento"], movimento)
        prazo = repo.prazos_medios(self.db)[0]
        self.assertEqual(prazo["pedidos_recebidos"], 1)
        self.assertEqual(prazo["prazo_medio_dias"], 5.0)

    def test_pedido_aberto_nao_entra_na_media(self):
        repo.solicitar(self.db, self.item, 4, quando="2026-11-01")
        self.assertEqual(repo.prazos_medios(self.db)[0]["pedidos_recebidos"], 0)
        self.assertIsNone(repo.prazos_medios(self.db)[0]["prazo_medio_dias"])
        self.assertEqual(repo.prazos_medios(self.db)[0]["pedidos_pendentes"], 1)

    def test_nao_permite_recebimento_duplicado_ou_antes_da_solicitacao(self):
        pedido = repo.solicitar(self.db, self.item, 2, quando="2026-11-10")
        with self.assertRaisesRegex(ValueError, "não pode anteceder"):
            repo.receber(self.db, pedido, quando="2026-11-09")
        repo.receber(self.db, pedido, quando="2026-11-10")
        with self.assertRaisesRegex(ValueError, "já foi finalizado"):
            repo.receber(self.db, pedido, quando="2026-11-11")
        self.assertEqual(almox_db.obter_item(self.db, self.item)["saldo"], 2)

    def test_item_sem_preco_exige_preco_no_recebimento(self):
        item = almox_db.salvar_item(self.db, {
            "nome": "Feijão", "unidade": "kg",
            "categoria": "Gêneros alimentícios"
        })
        pedido = repo.solicitar(self.db, item, 3, quando="2026-11-01")
        with self.assertRaisesRegex(ValueError, "Informe o valor unitário"):
            repo.receber(self.db, pedido, quando="2026-11-02")
        repo.receber(self.db, pedido, quando="2026-11-02", valor_unitario="8,50")
        self.assertEqual(almox_db.obter_item(self.db, item)["saldo"], 3)

    def test_cancelamento_nao_afeta_media(self):
        pedido = repo.solicitar(self.db, self.item, 1, quando="2026-11-01")
        repo.cancelar(self.db, pedido)
        self.assertEqual(repo.prazos_medios(self.db), [])

if __name__ == "__main__":
    unittest.main()
