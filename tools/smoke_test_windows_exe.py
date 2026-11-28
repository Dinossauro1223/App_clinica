"""Smoke test of the packaged Windows desktop executable and its embedded mobile server."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python tools/smoke_test_windows_exe.py caminho\\NutriLab.exe")
    exe = Path(sys.argv[1]).resolve()
    if not exe.is_file():
        raise SystemExit(f"Executável ausente: {exe}")

    processo = subprocess.Popen([str(exe)], cwd=str(exe.parent))
    try:
        limite = time.monotonic() + 30
        while time.monotonic() < limite:
            if processo.poll() is not None:
                raise RuntimeError(f"NutriLab.exe encerrou durante a inicialização (código {processo.returncode}).")
            try:
                with urlopen("http://127.0.0.1:8765/api/eu", timeout=1.5) as resposta:
                    codigo, corpo = resposta.status, resposta.read()
            except HTTPError as erro:
                codigo, corpo = erro.code, erro.read()
            except URLError:
                time.sleep(.5)
                continue

            if codigo == 401 and b"Sess" in corpo and b"expirada" in corpo:
                print("OK: NutriLab.exe permaneceu aberto e iniciou o servidor mobile na porta 8765.")
                return 0
            if codigo not in (0, 404, 503):
                raise RuntimeError(f"Servidor na porta 8765 respondeu inesperadamente: HTTP {codigo}: {corpo[:300]!r}")
            time.sleep(.5)
        log = exe.parent / "logs" / "mobile_server_startup.log"
        detalhe = ""
        if log.is_file():
            try:
                detalhe = log.read_text(encoding="utf-8", errors="replace")[-5000:]
            except OSError:
                detalhe = "(não foi possível ler o log de inicialização)"
        raise RuntimeError(
            "NutriLab.exe abriu, mas o servidor mobile não respondeu em 30 segundos."
            + ("\\nDiagnóstico de inicialização:\\n" + detalhe if detalhe else "")
        )
    finally:
        if processo.poll() is None:
            processo.terminate()
            try:
                processo.wait(timeout=8)
            except subprocess.TimeoutExpired:
                processo.kill()
                processo.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
