"""Verifica atualizacoes antes da inicializacao do NutriLab empacotado."""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

REPO = "Dinossauro1223/App_clinica"
API_URL = f"https://api.github.com/repos/{REPO}/commits/main"
TIMEOUT = 8


def _raiz_instalacao() -> Path | None:
    exe = Path(sys.executable).resolve()
    if exe.parent.name.lower() != "executavel do programa":
        return None
    return exe.parent.parent


def _consultar_sha() -> str | None:
    req = urllib.request.Request(
        API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "NutriLab-Updater",
            "X-GitHub-Api-Version": "2026-03-10",
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resposta:
        dados = json.load(resposta)
    sha = dados.get("sha")
    return sha if isinstance(sha, str) and len(sha) == 40 else None


def _confirmar(remote_sha: str, local_sha: str) -> bool:
    mensagem = (
        "Existe uma nova versão do NutriLab disponível.\n\n"
        f"Versão instalada: {local_sha[:12]}\n"
        f"Nova versão: {remote_sha[:12]}\n\n"
        "Deseja fechar o programa e atualizar agora?"
    )
    resultado = ctypes.windll.user32.MessageBoxW(
        0, mensagem, "Atualização do NutriLab", 0x00000004 | 0x00000040
    )
    return resultado == 6


def verificar_e_atualizar() -> None:
    if os.environ.get("NUTRILAB_SKIP_UPDATE") == "1" or os.environ.get("CI") == "true":
        return
    raiz = _raiz_instalacao()
    if raiz is None:
        return
    atualizador = raiz / "Atualizar_NutriLab.bat"
    arquivo_versao = raiz / ".nutrilab-version"
    if not atualizador.is_file() or not arquivo_versao.is_file():
        return

    try:
        local_sha = arquivo_versao.read_text(encoding="utf-8").strip()
        if len(local_sha) != 40:
            return
        remote_sha = _consultar_sha()
        if not remote_sha or remote_sha == local_sha:
            return
        if not _confirmar(remote_sha, local_sha):
            return
        subprocess.Popen(
            [
                os.environ.get("COMSPEC", "cmd.exe"),
                "/c",
                str(atualizador),
                "--remote-sha",
                remote_sha,
                "--root",
                str(raiz),
                "--confirmed",
            ],
            cwd=str(raiz),
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0),
            close_fds=True,
        )
        os._exit(0)
    except Exception:
        return


verificar_e_atualizar()
