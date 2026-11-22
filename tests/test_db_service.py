"""Testes de db_service.py — bancos SQLite sintéticos em pasta temporária; nenhum dado real."""
import os
import sqlite3
import sys
import tempfile
import unittest
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import db_service as svc

AGORA = datetime(2026, 11, 9, 20, 30, 15, tzinfo=timezone(timedelta(hours=-3)))
LIXO = b"isto nao e um banco sqlite " * 200


def criar_banco_sintetico(caminho, nomes=("Paciente Sintético 001", "Paciente Sintético 002")):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(caminho))
    conn.execute("CREATE TABLE Pacientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL)")
    conn.executemany("INSERT INTO Pacientes (nome) VALUES (?)", [(n,) for n in nomes])
    conn.commit()
    conn.close()
    return caminho


def ler_nomes(caminho):
    conn = sqlite3.connect(str(caminho))
    try:
        return [r[0] for r in conn.execute("SELECT nome FROM Pacientes ORDER BY id")]
    finally:
        conn.close()


class BaseTmp(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(svc.VAR_CAMINHO_BANCO, None)
        os.environ.pop(svc.VAR_DIRETORIO_DADOS, None)


class TestCaminhoUnico(BaseTmp):
    def test_desenvolvimento_usa_a_pasta_do_projeto(self):
        self.assertEqual(svc.caminho_banco(), Path(svc.__file__).resolve().parent / "clinica.db")

    def test_empacotado_usa_a_pasta_do_exe_e_nunca_a_interna(self):
        exe = self.tmp / "NutriLab" / "NutriLab.exe"
        interna = exe.parent / "_internal"
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "executable", str(exe)), \
                mock.patch.object(sys, "_MEIPASS", str(interna), create=True):
            caminho = svc.caminho_banco()
            self.assertTrue(svc.esta_empacotado())
        self.assertEqual(caminho, exe.parent.resolve() / "clinica.db")
        self.assertNotIn("_internal", caminho.parts)

    def test_variaveis_de_ambiente_e_precedencia(self):
        os.environ[svc.VAR_DIRETORIO_DADOS] = str(self.tmp / "dados")
        self.assertEqual(svc.caminho_banco(), self.tmp / "dados" / "clinica.db")
        self.assertEqual(svc.caminho_banco("outro.db"), self.tmp / "dados" / "outro.db")
        os.environ[svc.VAR_CAMINHO_BANCO] = str(self.tmp / "exato" / "meu.db")
        self.assertEqual(svc.caminho_banco(), self.tmp / "exato" / "meu.db")


class TestAvisosLocal(unittest.TestCase):
    def test_locais_inadequados(self):
        casos = {
            "\\\\servidor\\pasta\\clinica.db": "REDE",
            "//servidor/pasta/clinica.db": "REDE",
            "C:\\Users\\Ana\\OneDrive\\NutriLab\\clinica.db": "SINCRONIZADA",
            "C:\\Users\\Ana\\Dropbox\\clinica.db": "SINCRONIZADA",
            "C:\\Program Files\\NutriLab\\clinica.db": "Program Files",
        }
        for caminho, trecho in casos.items():
            with self.subTest(caminho=caminho):
                avisos = svc.avisos_local(caminho)
                self.assertEqual(len(avisos), 1)
                self.assertIn(trecho, avisos[0])

    def test_local_comum_nao_gera_aviso(self):
        self.assertEqual(svc.avisos_local("C:\\Dados\\NutriLab\\clinica.db"), [])
        self.assertEqual(svc.avisos_local("/home/usuario/nutrilab/clinica.db"), [])


class TestConectar(BaseTmp):
    def test_cria_a_pasta_e_conecta(self):
        caminho = self.tmp / "a" / "b" / "clinica.db"
        conn = svc.conectar(caminho)
        conn.execute("CREATE TABLE t (x)")
        conn.close()
        self.assertTrue(caminho.is_file())

    def test_somente_leitura_nao_cria_arquivo_nem_permite_escrita(self):
        caminho = self.tmp / "clinica.db"
        with self.assertRaises(FileNotFoundError):
            svc.conectar(caminho, somente_leitura=True)
        self.assertFalse(caminho.exists())
        criar_banco_sintetico(caminho)
        conn = svc.conectar(caminho, somente_leitura=True)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("INSERT INTO Pacientes (nome) VALUES ('x')")
        finally:
            conn.close()
        self.assertEqual(len(ler_nomes(caminho)), 2)

    def test_memoria(self):
        conn = svc.conectar(":memory:")
        self.assertEqual(conn.execute("SELECT 1").fetchone()[0], 1)
        conn.close()

    def test_foreign_keys_so_muda_quando_pedido(self):
        for valor, esperado in ((True, 1), (False, 0)):
            conn = svc.conectar(self.tmp / "fk.db", foreign_keys=valor)
            try:
                self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], esperado)
            finally:
                conn.close()

    def test_avisa_quando_o_banco_esta_em_pasta_sincronizada(self):
        caminho = self.tmp / "OneDrive" / "clinica.db"
        with warnings.catch_warnings(record=True) as capturados:
            warnings.simplefilter("always")
            svc.conectar(caminho).close()
        self.assertTrue(any(issubclass(w.category, RuntimeWarning) and "SINCRONIZADA" in str(w.message)
                            for w in capturados))


class TestIntegridade(BaseTmp):
    def test_banco_integro(self):
        db = criar_banco_sintetico(self.tmp / "clinica.db")
        self.assertEqual(svc.verificar_integridade(db), (True, ["ok"]))
        conn = svc.conectar(db, somente_leitura=True)
        try:
            self.assertEqual(svc.verificar_integridade(conn, rapida=True), (True, ["ok"]))
        finally:
            conn.close()

    def test_arquivo_que_nao_e_sqlite_ou_inexistente_nao_lanca(self):
        ruim = self.tmp / "ruim.db"
        ruim.write_bytes(LIXO)
        ok, linhas = svc.verificar_integridade(ruim)
        self.assertFalse(ok)
        self.assertTrue(linhas[0].startswith("erro:"))
        self.assertEqual(svc.verificar_integridade(self.tmp / "nao-existe.db"), (False, ["erro: FileNotFoundError"]))


class TestBackup(BaseTmp):
    def test_backup_tem_mesmo_conteudo_nome_e_pasta_esperados(self):
        db = criar_banco_sintetico(self.tmp / "clinica.db")
        backup = svc.criar_backup(db, motivo="Pré-Migração v2!", agora=AGORA)
        self.assertEqual(backup.parent, self.tmp / "backups")
        self.assertEqual(backup.name, "clinica.backup_20261109-203015_pre-migracao-v2.db")
        self.assertEqual(ler_nomes(backup), ler_nomes(db))
        self.assertEqual(svc.verificar_integridade(backup), (True, ["ok"]))

    def test_backup_nunca_sobrescreve_outro(self):
        db = criar_banco_sintetico(self.tmp / "clinica.db")
        primeiro = svc.criar_backup(db, agora=AGORA)
        segundo = svc.criar_backup(db, agora=AGORA)
        self.assertNotEqual(primeiro, segundo)
        self.assertTrue(segundo.name.endswith("_manual-2.db"))
        self.assertEqual(svc.listar_backups(db), [primeiro, segundo])

    def test_banco_inexistente(self):
        with self.assertRaises(FileNotFoundError):
            svc.criar_backup(self.tmp / "nao-existe.db")
        self.assertFalse((self.tmp / "backups").exists())

    def test_banco_corrompido_falha_sem_deixar_arquivo_parcial(self):
        ruim = self.tmp / "clinica.db"
        ruim.write_bytes(LIXO)
        with self.assertRaises(sqlite3.DatabaseError):
            svc.criar_backup(ruim, agora=AGORA)
        self.assertEqual(svc.listar_backups(ruim), [])
        self.assertEqual(ruim.read_bytes(), LIXO)

    def test_listar_backups_sem_pasta(self):
        self.assertEqual(svc.listar_backups(self.tmp / "clinica.db"), [])


class TestRestauracao(BaseTmp):
    def test_restaura_e_guarda_copia_de_seguranca_do_estado_atual(self):
        db = criar_banco_sintetico(self.tmp / "clinica.db")
        backup = svc.criar_backup(db, agora=AGORA)
        conn = sqlite3.connect(str(db))
        conn.execute("DELETE FROM Pacientes WHERE id = 1")
        conn.execute("INSERT INTO Pacientes (nome) VALUES ('Paciente Sintético 003')")
        conn.commit()
        conn.close()
        resultado = svc.restaurar_backup(backup, db, agora=AGORA)
        self.assertEqual(resultado.destino, db)
        self.assertEqual(ler_nomes(db), ["Paciente Sintético 001", "Paciente Sintético 002"])
        self.assertEqual(ler_nomes(resultado.copia_de_seguranca), ["Paciente Sintético 002", "Paciente Sintético 003"])
        self.assertIn("pre-restauracao", resultado.copia_de_seguranca.name)
        self.assertFalse(db.with_name(db.name + ".restaurando").exists())

    def test_restaura_em_destino_inexistente(self):
        origem = criar_banco_sintetico(self.tmp / "origem.db")
        backup = svc.criar_backup(origem, agora=AGORA)
        resultado = svc.restaurar_backup(backup, self.tmp / "novo" / "clinica.db")
        self.assertIsNone(resultado.copia_de_seguranca)
        self.assertEqual(ler_nomes(resultado.destino), ler_nomes(origem))

    def test_backup_corrompido_e_recusado_e_o_banco_fica_intacto(self):
        db = criar_banco_sintetico(self.tmp / "clinica.db")
        antes = db.read_bytes()
        ruim = self.tmp / "ruim.db"
        ruim.write_bytes(LIXO)
        with self.assertRaises(svc.IntegridadeError):
            svc.restaurar_backup(ruim, db)
        self.assertEqual(db.read_bytes(), antes)
        self.assertEqual(svc.listar_backups(db), [])
        self.assertFalse(db.with_name(db.name + ".restaurando").exists())

    def test_arquivos_auxiliares_do_banco_antigo_sao_movidos_nao_apagados(self):
        db = criar_banco_sintetico(self.tmp / "clinica.db")
        backup = svc.criar_backup(db, agora=AGORA)
        wal = db.with_name(db.name + "-wal")
        wal.write_bytes(b"sobra de wal")
        svc.restaurar_backup(backup, db, agora=AGORA)
        self.assertFalse(wal.exists())
        self.assertEqual(db.with_name(db.name + "-wal.antes-da-restauracao").read_bytes(), b"sobra de wal")
        self.assertEqual(svc.verificar_integridade(db), (True, ["ok"]))

    def test_falha_na_troca_final_mantem_o_banco_atual(self):
        db = criar_banco_sintetico(self.tmp / "clinica.db")
        backup = svc.criar_backup(db, agora=AGORA)
        antes = db.read_bytes()
        with mock.patch("db_service.os.replace", side_effect=PermissionError("arquivo em uso")):
            with self.assertRaises(PermissionError):
                svc.restaurar_backup(backup, db, agora=AGORA)
        self.assertEqual(db.read_bytes(), antes)
        self.assertFalse(db.with_name(db.name + ".restaurando").exists())


    def test_falha_na_troca_recoloca_wal_no_nome_original(self):
        db = criar_banco_sintetico(self.tmp / "clinica.db")
        backup = svc.criar_backup(db, agora=AGORA)
        antes = db.read_bytes()
        wal = db.with_name(db.name + "-wal")
        wal.write_bytes(b"wal antigo preservado")

        replace_real = svc.os.replace

        def falhar_apenas_na_troca(src, dst):
            if str(src).endswith(".restaurando"):
                raise PermissionError("arquivo em uso")
            return replace_real(src, dst)

        with mock.patch("db_service.os.replace", side_effect=falhar_apenas_na_troca):
            with self.assertRaises(PermissionError):
                svc.restaurar_backup(backup, db, agora=AGORA)

        self.assertEqual(db.read_bytes(), antes)
        self.assertEqual(wal.read_bytes(), b"wal antigo preservado")
        self.assertFalse(wal.with_name(wal.name + ".antes-da-restauracao").exists())
        self.assertFalse(db.with_name(db.name + ".restaurando").exists())

    def test_falha_ao_mover_segundo_auxiliar_reverte_primeiro(self):
        db = criar_banco_sintetico(self.tmp / "clinica.db")
        backup = svc.criar_backup(db, agora=AGORA)
        wal = db.with_name(db.name + "-wal")
        shm = db.with_name(db.name + "-shm")
        wal.write_bytes(b"wal")

        replace_real = svc.os.replace
        exists_real = Path.exists

        def simular_shm_presente(caminho):
            # Simula o segundo auxiliar sem criar um arquivo que o SQLite
            # poderia interpretar como sua memória compartilhada real.
            if caminho == shm:
                return True
            return exists_real(caminho)

        def falhar_ao_mover_shm(src, dst):
            if str(src).endswith("-shm"):
                raise PermissionError("shm bloqueado")
            return replace_real(src, dst)

        with mock.patch.object(Path, "exists", simular_shm_presente):
            with mock.patch("db_service.os.replace", side_effect=falhar_ao_mover_shm):
                with self.assertRaises(PermissionError):
                    svc.restaurar_backup(backup, db, agora=AGORA)

        self.assertEqual(wal.read_bytes(), b"wal")
        self.assertFalse(wal.with_name(wal.name + ".antes-da-restauracao").exists())
        self.assertFalse(db.with_name(db.name + ".restaurando").exists())

    def test_backup_inexistente(self):
        with self.assertRaises(FileNotFoundError):
            svc.restaurar_backup(self.tmp / "nao-existe.db", self.tmp / "clinica.db")


if __name__ == "__main__":
    unittest.main()
