"""Validates the distributable Windows ZIP before publishing it.

The only database allowed in the archive is the clean PyInstaller template at
_internal/modelo_banco/clinica.db. The writable clinica.db created when smoke-testing NutriLab.exe
must never be shipped, because extracting an update could overwrite user data.
"""
from __future__ import annotations

import sys
import zipfile
from collections import Counter
from pathlib import Path


def verificar_pacote(caminho: str | Path) -> None:
    with zipfile.ZipFile(caminho) as arquivo:
        nomes = [nome for nome in arquivo.namelist() if not nome.endswith("/")]
    duplicados = [nome for nome, quantidade in Counter(nomes).items() if quantidade > 1]
    if duplicados:
        raise ValueError("Caminhos duplicados no ZIP: " + ", ".join(duplicados))

    bancos = [nome for nome in nomes if Path(nome).name.casefold() == "clinica.db"]
    if bancos != ["_internal/clinica.db"]:
        raise ValueError(
            "O ZIP deve conter somente o modelo _internal/clinica.db; "
            f"encontrados: {bancos!r}"
        )
    sobras_sqlite = [
        nome for nome in nomes
        if Path(nome).name.casefold() in {"clinica.db-wal", "clinica.db-shm", "clinica.db-journal"}
        and "/" not in nome
    ]
    if sobras_sqlite:
        raise ValueError("Arquivos SQLite graváveis na raiz do pacote: " + ", ".join(sobras_sqlite))

    htmls = [nome for nome in nomes if Path(nome).name.casefold() == "index.html"]
    if htmls != ["_internal/mobile/static/index.html"]:
        raise ValueError(
            "O ZIP deve conter uma única fonte HTML mobile _internal/mobile/static/index.html; "
            f"encontrados: {htmls!r}"
        )


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        raise SystemExit("Uso: python tools/verificar_pacote_windows.py arquivo.zip")
    try:
        verificar_pacote(args[0])
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    print("OK: ZIP sem banco de usuário, sem caminhos duplicados e com uma única fonte HTML mobile.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
