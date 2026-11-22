"""Snapshots automáticos do banco local do NutriLab.

A cópia usa a API de backup do SQLite implementada em db_service. O agendamento
periódico cobre encerramentos do sistema que não passam pelo protocolo normal
da janela; o backup no fechamento é uma última cópia verificada.
"""
from __future__ import annotations

import atexit
from pathlib import Path
from typing import Callable

import db_service


class BackupManager:
    """Coordena snapshots sem bloquear o loop gráfico por intervalos longos.

    O SQLite confirma transações nas rotinas de gravação existentes. Este
    componente cria cópias consistentes do banco em uso, sem copiar o .db
    diretamente. O intervalo padrão de 15 minutos limita a janela entre
    snapshots em desligamentos abruptos.
    """

    def __init__(
        self,
        root,
        caminho_banco,
        *,
        intervalo_ms: int = 15 * 60 * 1000,
        on_error: Callable[[Exception], None] | None = None,
    ):
        if intervalo_ms < 60_000:
            raise ValueError("o intervalo mínimo de backup é de 60 segundos")
        self.root = root
        self.caminho_banco = Path(caminho_banco)
        self.intervalo_ms = intervalo_ms
        self.on_error = on_error or (lambda erro: None)
        self._after_id = None
        self._iniciado = False
        self._encerrado = False

    def iniciar(self):
        """Cria snapshot de abertura e agenda cópias periódicas."""
        if self._iniciado or self._encerrado:
            return
        self._iniciado = True
        atexit.register(self._backup_ao_sair)
        self._tentar_backup("inicio-sessao")
        self._agendar()

    def _agendar(self):
        if not self._encerrado:
            self._after_id = self.root.after(self.intervalo_ms, self._backup_periodico)

    def _tentar_backup(self, motivo):
        try:
            return db_service.criar_backup(self.caminho_banco, motivo=motivo)
        except Exception as erro:
            self.on_error(erro)
            return None

    def _backup_periodico(self):
        self._after_id = None
        if self._encerrado:
            return
        self._tentar_backup("periodico")
        self._agendar()

    def _backup_ao_sair(self):
        """Última tentativa best-effort para encerramentos normais do interpretador."""
        if not self._encerrado and self.caminho_banco.is_file():
            try:
                db_service.criar_backup(self.caminho_banco, motivo="encerramento-sistema")
            except Exception:
                # atexit não deve impedir o encerramento do processo; snapshots
                # periódicos continuam sendo a proteção contra desligamento abrupto.
                pass

    def fechar(self, *, ao_concluir: Callable[[], None]):
        """Cria backup final; se falhar, mantém a aplicação aberta para nova tentativa."""
        if self._encerrado:
            return True
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

        backup = self._tentar_backup("fechamento")
        if backup is None:
            self._agendar()
            return False

        self._encerrado = True
        try:
            atexit.unregister(self._backup_ao_sair)
        except Exception:
            pass
        ao_concluir()
        return True
