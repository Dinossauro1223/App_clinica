"""Testes do agendador de backup: somente banco sintético e relógio/agendador simulados."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backup_manager import BackupManager


class FakeRoot:
    def __init__(self):
        self.callbacks = {}
        self.cancelados = []
        self.proximo = 0

    def after(self, intervalo, callback):
        self.proximo += 1
        self.callbacks[self.proximo] = (intervalo, callback)
        return self.proximo

    def after_cancel(self, identificador):
        self.cancelados.append(identificador)
        self.callbacks.pop(identificador, None)

    def executar_proximo(self):
        identificador = next(iter(self.callbacks))
        _, callback = self.callbacks.pop(identificador)
        callback()


class TestBackupManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "clinica.db"
        self.db.touch()
        self.root = FakeRoot()
        self.backups = []

        def backup(caminho, *, motivo):
            destino = Path(caminho).parent / f"{motivo}.db"
            destino.touch()
            self.backups.append(motivo)
            return destino

        self.patch_backup = mock.patch("backup_manager.db_service.criar_backup", side_effect=backup)
        self.patch_backup.start()
        self.addCleanup(self.patch_backup.stop)

    def test_abertura_cria_snapshot_e_agenda_periodico(self):
        gerenciador = BackupManager(self.root, self.db, intervalo_ms=120_000)
        gerenciador.iniciar()
        self.assertEqual(self.backups, ["inicio-sessao"])
        self.assertEqual(len(self.root.callbacks), 1)
        self.assertEqual(next(iter(self.root.callbacks.values()))[0], 120_000)

    def test_iniciar_repetidamente_nao_duplica_backup_timer_ou_atexit(self):
        gerenciador = BackupManager(self.root, self.db, intervalo_ms=120_000)
        with mock.patch("backup_manager.atexit.register") as registrar:
            gerenciador.iniciar()
            gerenciador.iniciar()
        self.assertEqual(self.backups, ["inicio-sessao"])
        self.assertEqual(len(self.root.callbacks), 1)
        registrar.assert_called_once_with(gerenciador._backup_ao_sair)

    def test_periodico_cria_snapshot_e_reagenda(self):
        gerenciador = BackupManager(self.root, self.db, intervalo_ms=120_000)
        gerenciador.iniciar()
        self.root.executar_proximo()
        self.assertEqual(self.backups, ["inicio-sessao", "periodico"])
        self.assertEqual(len(self.root.callbacks), 1)

    def test_falha_periodica_notifica_e_mantem_proximo_agendamento(self):
        erros = []
        gerenciador = BackupManager(self.root, self.db, intervalo_ms=120_000, on_error=erros.append)
        gerenciador.iniciar()
        with mock.patch("backup_manager.db_service.criar_backup", side_effect=OSError("disco cheio")):
            self.root.executar_proximo()
        self.assertEqual(len(erros), 1)
        self.assertIsInstance(erros[0], OSError)
        self.assertEqual(len(self.root.callbacks), 1)

    def test_falha_no_backup_inicial_nao_impede_agendamento(self):
        erros = []
        gerenciador = BackupManager(self.root, self.db, intervalo_ms=120_000, on_error=erros.append)
        with mock.patch("backup_manager.db_service.criar_backup", side_effect=OSError("sem permissao")):
            gerenciador.iniciar()
        self.assertEqual(len(erros), 1)
        self.assertEqual(len(self.root.callbacks), 1)

    def test_erro_na_notificacao_nao_interrompe_agendamento(self):
        def notificar(_erro):
            raise RuntimeError("janela de erro indisponivel")

        gerenciador = BackupManager(self.root, self.db, intervalo_ms=120_000, on_error=notificar)
        with mock.patch("backup_manager.db_service.criar_backup", side_effect=OSError("disco cheio")):
            gerenciador.iniciar()
            self.root.executar_proximo()
        self.assertEqual(len(self.root.callbacks), 1)

    def test_fechamento_faz_backup_final_cancela_timer_e_fecha(self):
        gerenciador = BackupManager(self.root, self.db, intervalo_ms=120_000)
        gerenciador.iniciar()
        fechado = []
        with mock.patch("backup_manager.atexit.unregister") as remover:
            self.assertTrue(gerenciador.fechar(ao_concluir=lambda: fechado.append(True)))
        self.assertEqual(self.backups, ["inicio-sessao", "fechamento"])
        self.assertEqual(fechado, [True])
        self.assertEqual(len(self.root.callbacks), 0)
        self.assertTrue(self.root.cancelados)
        remover.assert_called_once_with(gerenciador._backup_ao_sair)

    def test_segundo_fechamento_nao_cria_outro_backup_nem_chama_callback(self):
        gerenciador = BackupManager(self.root, self.db, intervalo_ms=120_000)
        gerenciador.iniciar()
        fechado = []
        self.assertTrue(gerenciador.fechar(ao_concluir=lambda: fechado.append("primeiro")))
        self.assertTrue(gerenciador.fechar(ao_concluir=lambda: fechado.append("segundo")))
        self.assertEqual(self.backups, ["inicio-sessao", "fechamento"])
        self.assertEqual(fechado, ["primeiro"])

    def test_falha_no_backup_final_nao_fecha_e_reagenda(self):
        erros = []
        gerenciador = BackupManager(self.root, self.db, intervalo_ms=120_000, on_error=erros.append)
        gerenciador.iniciar()
        with mock.patch("backup_manager.db_service.criar_backup", side_effect=OSError("disco cheio")):
            fechado = []
            self.assertFalse(gerenciador.fechar(ao_concluir=lambda: fechado.append(True)))
        self.assertEqual(fechado, [])
        self.assertEqual(len(erros), 1)
        self.assertEqual(len(self.root.callbacks), 1)

    def test_atexit_nao_tenta_backup_se_banco_nao_existe(self):
        gerenciador = BackupManager(self.root, self.db)
        self.db.unlink()
        with mock.patch("backup_manager.db_service.criar_backup") as backup:
            gerenciador._backup_ao_sair()
        backup.assert_not_called()

    def test_atexit_tenta_backup_se_banco_existe(self):
        gerenciador = BackupManager(self.root, self.db)
        gerenciador._backup_ao_sair()
        self.assertEqual(self.backups, ["encerramento-sistema"])

    def test_intervalo_muito_curto_e_recusado(self):
        with self.assertRaises(ValueError):
            BackupManager(self.root, self.db, intervalo_ms=10_000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
