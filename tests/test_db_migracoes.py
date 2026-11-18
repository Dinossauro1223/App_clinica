"""Testes de db_migracoes.py.

O esquema legado usado aqui (Pacientes/Consultas) é SINTÉTICO e mínimo: serve só para exercitar o mecanismo de
migração e NÃO reproduz o DDL real do aplicativo (que não estava acessível quando estes testes foram escritos).
"""
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import db_migracoes as mig
import db_service as svc

FUSO = timezone(timedelta(hours=-3))


def tempo(minutos=0):
    return datetime(2026, 11, 9, 20, 0, 0, tzinfo=FUSO) + timedelta(minutes=minutos)


def inicializador_legado(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS Pacientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS Consultas (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                 "id_paciente INTEGER NOT NULL REFERENCES Pacientes(id), texto TEXT)")


MIG_TESTE = (
    mig.Migracao(1, "baseline", baseline=True),
    mig.Migracao(2, "cria_auditoria_teste",
                 up=("CREATE TABLE Auditoria_Teste (id INTEGER PRIMARY KEY, acao TEXT NOT NULL)",),
                 down=("DROP TABLE Auditoria_Teste",)),
    mig.Migracao(3, "coluna_observacao",
                 up=("ALTER TABLE Pacientes ADD COLUMN observacao TEXT",),
                 down=("ALTER TABLE Pacientes DROP COLUMN observacao",)),
)


def criar_legado_sintetico(caminho, n=3):
    conn = sqlite3.connect(str(caminho))
    inicializador_legado(conn)
    for i in range(1, n + 1):
        conn.execute("INSERT INTO Pacientes (nome) VALUES (?)", (f"Paciente Sintético {i:03d}",))
        conn.execute("INSERT INTO Consultas (id_paciente, texto) VALUES (?, ?)", (i, f"Consulta sintética {i:03d}"))
    conn.commit()
    conn.close()
    return Path(caminho)


def _consulta(caminho, sql):
    conn = sqlite3.connect(str(caminho))
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def dump_legado(caminho):
    return {"Pacientes": _consulta(caminho, "SELECT id, nome FROM Pacientes ORDER BY id"),
            "Consultas": _consulta(caminho, "SELECT id, id_paciente, texto FROM Consultas ORDER BY id")}


def colunas(caminho, tabela):
    return [r[1] for r in _consulta(caminho, f"PRAGMA table_info({tabela})")]


def tabelas(caminho):
    return {r[0] for r in _consulta(
        caminho, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def registro(caminho):
    return _consulta(caminho, "SELECT versao, origem FROM schema_migrations ORDER BY versao")


def versao(caminho):
    conn = sqlite3.connect(str(caminho))
    try:
        return mig.versao_atual(conn)
    finally:
        conn.close()


class BaseTmp(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.db = self.tmp / "clinica.db"


class TestDoZero(BaseTmp):
    def test_banco_novo_ate_a_ultima_versao(self):
        r = mig.aplicar_migracoes(self.db, MIG_TESTE, inicializador_legado=inicializador_legado, agora=tempo())
        self.assertEqual((r.versao_inicial, r.versao_final, r.aplicadas), (0, 3, [1, 2, 3]))
        self.assertIsNone(r.backup)
        self.assertFalse(r.baseline_adotado)
        self.assertEqual(tabelas(self.db), {"Pacientes", "Consultas", "Auditoria_Teste", "schema_migrations"})
        self.assertIn("observacao", colunas(self.db, "Pacientes"))
        self.assertEqual(registro(self.db), [(1, "banco-novo"), (2, "migracao"), (3, "migracao")])
        self.assertEqual(svc.verificar_integridade(self.db), (True, ["ok"]))

    def test_migracao_que_falha_e_desfeita_e_as_anteriores_permanecem(self):
        with self.assertRaises(mig.ErroMigracao) as ctx:     # sem inicializador não há tabela Pacientes
            mig.aplicar_migracoes(self.db, MIG_TESTE, agora=tempo())
        self.assertIn("migração 3", str(ctx.exception))
        self.assertEqual(versao(self.db), 2)
        self.assertEqual(registro(self.db), [(1, "banco-novo"), (2, "migracao")])
        self.assertIn("Auditoria_Teste", tabelas(self.db))

    def test_inicializador_que_falha_nao_deixa_tabelas_pela_metade(self):
        def inicializador_ruim(conn):
            conn.execute("CREATE TABLE Pacientes (id INTEGER PRIMARY KEY)")
            raise RuntimeError("falha simulada")
        with self.assertRaises(mig.ErroMigracao):
            mig.aplicar_migracoes(self.db, MIG_TESTE, inicializador_legado=inicializador_ruim)
        self.assertEqual(tabelas(self.db), {"schema_migrations"})
        self.assertEqual(versao(self.db), 0)

    def test_banco_em_memoria(self):
        r = mig.aplicar_migracoes(":memory:", MIG_TESTE, inicializador_legado=inicializador_legado)
        self.assertEqual(r.versao_final, 3)
        self.assertIsNone(r.backup)


class TestBancoLegadoExistente(BaseTmp):
    def test_baseline_e_adotada_sem_alterar_dados_e_com_backup(self):
        criar_legado_sintetico(self.db)
        antes = dump_legado(self.db)
        chamado = mock.Mock()
        r = mig.aplicar_migracoes(self.db, MIG_TESTE[:1], inicializador_legado=chamado, agora=tempo())
        self.assertEqual(r.aplicadas, [1])
        self.assertTrue(r.baseline_adotado)
        chamado.assert_not_called()
        self.assertEqual(dump_legado(self.db), antes)
        self.assertEqual(registro(self.db), [(1, "adotada-legado")])
        self.assertIsNotNone(r.backup)
        self.assertEqual(svc.listar_backups(self.db), [r.backup])

    def test_da_versao_anterior_para_a_atual_faz_backup_e_preserva_dados(self):
        criar_legado_sintetico(self.db)
        antes = dump_legado(self.db)
        mig.aplicar_migracoes(self.db, MIG_TESTE[:2], agora=tempo(0))
        r = mig.aplicar_migracoes(self.db, MIG_TESTE, agora=tempo(1))
        self.assertEqual((r.versao_inicial, r.versao_final, r.aplicadas), (2, 3, [3]))
        self.assertIn("pre-migracao-v3", r.backup.name)
        self.assertEqual(dump_legado(self.db), antes)
        self.assertIn("observacao", colunas(self.db, "Pacientes"))
        self.assertIn("Auditoria_Teste", tabelas(r.backup))                  # o backup é de ANTES da v3 (v2 já existia)
        self.assertNotIn("observacao", colunas(r.backup, "Pacientes"))

    def test_aplicar_de_novo_nao_faz_nada(self):
        criar_legado_sintetico(self.db)
        mig.aplicar_migracoes(self.db, MIG_TESTE, agora=tempo())
        total = len(svc.listar_backups(self.db))
        r = mig.aplicar_migracoes(self.db, MIG_TESTE, agora=tempo(1))
        self.assertEqual((r.aplicadas, r.backup, r.versao_final), ([], None, 3))
        self.assertEqual(len(svc.listar_backups(self.db)), total)

    def test_falha_desfaz_so_a_migracao_com_erro_e_o_backup_permite_voltar(self):
        criar_legado_sintetico(self.db)
        mig.aplicar_migracoes(self.db, MIG_TESTE[:2], agora=tempo(0))
        antes = dump_legado(self.db)
        ruim = MIG_TESTE[:2] + (mig.Migracao(
            3, "falha", up=("ALTER TABLE Pacientes ADD COLUMN observacao TEXT",
                            "INSERT INTO TabelaQueNaoExiste VALUES (1)")),)
        with self.assertRaises(mig.ErroMigracao) as ctx:
            mig.aplicar_migracoes(self.db, ruim, agora=tempo(1))
        self.assertIn("migração 3", str(ctx.exception))
        self.assertNotIn("observacao", colunas(self.db, "Pacientes"))     # o ALTER foi desfeito
        self.assertEqual(versao(self.db), 2)
        backup = svc.listar_backups(self.db)[-1]
        self.assertIn("pre-migracao-v3", backup.name)
        # rollback pelo backup
        mig_ok = svc.restaurar_backup(backup, self.db, agora=tempo(2))
        self.assertIsNotNone(mig_ok.copia_de_seguranca)
        self.assertEqual(dump_legado(self.db), antes)
        self.assertEqual([v for v, _ in registro(self.db)], [1, 2])


class TestSeguranca(BaseTmp):
    def test_migracao_alterada_depois_de_aplicada_e_recusada_antes_de_mudar_algo(self):
        mig.aplicar_migracoes(self.db, MIG_TESTE, inicializador_legado=inicializador_legado, agora=tempo())
        alterada = (MIG_TESTE[0],
                    mig.Migracao(2, "cria_auditoria_teste", up=("CREATE TABLE Auditoria_Teste (id INTEGER, extra TEXT)",),
                                 down=("DROP TABLE Auditoria_Teste",)),
                    MIG_TESTE[2])
        with self.assertRaises(mig.MigracaoAlteradaError):
            mig.aplicar_migracoes(self.db, alterada)
        self.assertEqual(svc.listar_backups(self.db), [])

    def test_banco_migrado_por_versao_mais_nova_e_recusado(self):
        mig.aplicar_migracoes(self.db, MIG_TESTE, inicializador_legado=inicializador_legado)
        with self.assertRaises(mig.VersaoMaisNovaError):
            mig.aplicar_migracoes(self.db, MIG_TESTE[:2])

    def test_checksum_cobre_up_mas_nao_down(self):
        a = mig.Migracao(2, "x", up=("SELECT 1",), down=("SELECT 2",))
        self.assertEqual(a.checksum, mig.Migracao(2, "x", up=("SELECT 1",), down=("SELECT 3",)).checksum)
        self.assertNotEqual(a.checksum, mig.Migracao(2, "x", up=("SELECT 9",), down=("SELECT 2",)).checksum)
        self.assertNotEqual(a.checksum, mig.Migracao(3, "x", up=("SELECT 1",)).checksum)


class TestReversao(BaseTmp):
    def test_reverter_ate_a_baseline_remove_o_que_as_migracoes_criaram(self):
        mig.aplicar_migracoes(self.db, MIG_TESTE, inicializador_legado=inicializador_legado, agora=tempo(0))
        r = mig.reverter_migracoes(self.db, 1, MIG_TESTE, agora=tempo(1))
        self.assertEqual((r.revertidas, r.versao_final), ([3, 2], 1))
        self.assertNotIn("Auditoria_Teste", tabelas(self.db))
        self.assertNotIn("observacao", colunas(self.db, "Pacientes"))
        self.assertIn("pre-reversao-para-v1", r.backup.name)
        self.assertEqual(registro(self.db), [(1, "banco-novo")])

    def test_reversao_recusada_sem_script_down_e_nada_muda(self):
        sem_down = MIG_TESTE[:2] + (mig.Migracao(3, "irreversivel", up=("ALTER TABLE Pacientes ADD COLUMN x TEXT",)),)
        mig.aplicar_migracoes(self.db, sem_down, inicializador_legado=inicializador_legado)
        antes = registro(self.db)
        with self.assertRaises(mig.MigracaoIrreversivelError):
            mig.reverter_migracoes(self.db, 1, sem_down)
        self.assertEqual(registro(self.db), antes)
        self.assertEqual(svc.listar_backups(self.db), [])

    def test_baseline_nao_pode_ser_revertida(self):
        mig.aplicar_migracoes(self.db, MIG_TESTE, inicializador_legado=inicializador_legado)
        with self.assertRaises(mig.MigracaoIrreversivelError):
            mig.reverter_migracoes(self.db, 0, MIG_TESTE)

    def test_reverter_para_versao_igual_ou_maior_nao_faz_nada(self):
        mig.aplicar_migracoes(self.db, MIG_TESTE, inicializador_legado=inicializador_legado)
        r = mig.reverter_migracoes(self.db, 3, MIG_TESTE)
        self.assertEqual((r.revertidas, r.backup, r.versao_final), ([], None, 3))


class TestListaEProducao(BaseTmp):
    def test_listas_invalidas(self):
        baseline = mig.Migracao(1, "b", baseline=True)
        casos = {
            "vazia": (),
            "com buraco": (baseline, mig.Migracao(3, "x")),
            "sem baseline": (mig.Migracao(1, "x"),),
            "duas baselines": (baseline, mig.Migracao(2, "b2", baseline=True)),
            "baseline com up": (mig.Migracao(1, "b", up=("SELECT 1",), baseline=True),),
        }
        for nome, lista in casos.items():
            with self.subTest(nome):
                with self.assertRaises(mig.ListaMigracoesInvalida):
                    mig.validar_lista(lista)

    def test_alvo_parcial_e_alvo_invalido(self):
        r = mig.aplicar_migracoes(self.db, MIG_TESTE, alvo=2, inicializador_legado=inicializador_legado)
        self.assertEqual((r.versao_final, r.aplicadas), (2, [1, 2]))
        with self.assertRaises(mig.ListaMigracoesInvalida):
            mig.aplicar_migracoes(self.db, MIG_TESTE, alvo=9)

    def test_migracoes_de_producao_em_banco_legado_e_em_banco_novo(self):
        mig.validar_lista(mig.MIGRACOES)
        criar_legado_sintetico(self.db)
        ultima = mig.MIGRACOES[-1].versao
        r = mig.aplicar_migracoes(self.db)
        self.assertEqual((r.versao_final, r.baseline_adotado), (ultima, True))
        novo = self.tmp / "novo.db"
        inicializador = mock.Mock(side_effect=inicializador_legado)
        r2 = mig.aplicar_migracoes(novo, inicializador_legado=inicializador)
        self.assertEqual((r2.versao_final, r2.baseline_adotado), (ultima, False))
        inicializador.assert_called_once()
        self.assertEqual(registro(novo), [(1, "banco-novo")] + [(m.versao, "migracao") for m in mig.MIGRACOES[1:]])


if __name__ == "__main__":
    unittest.main()
