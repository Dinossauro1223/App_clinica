"""Consulta de versões publicadas do NutriLab Desktop (somente leitura)."""
from __future__ import annotations
import json
import re
import threading
import urllib.request

REPOSITORIO = "Dinossauro1223/App_clinica"
VERSAO_ATUAL = "1.0.0"
API_RELEASE = f"https://api.github.com/repos/{REPOSITORIO}/releases/latest"


def _partes(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:4]) or (0,)


def consultar_atualizacao():
    req = urllib.request.Request(API_RELEASE, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "NutriLab-Desktop-Updater"
    })
    with urllib.request.urlopen(req, timeout=8) as r:
        release = json.loads(r.read().decode("utf-8"))
    remota = str(release.get("tag_name", "")).lstrip("v")
    if not remota:
        raise ValueError("A release mais recente não contém uma tag de versão.")
    assets = release.get("assets", [])
    pacote = next((a for a in assets if a.get("name") == "NutriLab-Windows.zip"), None)
    return {
        "status": "atualizacao" if _partes(remota) > _partes(VERSAO_ATUAL) else "atualizado",
        "local": VERSAO_ATUAL, "remota": remota,
        "url": release.get("html_url", ""),
        "notas": release.get("body", ""),
        "pacote_windows": pacote.get("browser_download_url") if pacote else None,
    }


def iniciar_verificacao(janela, callback):
    def consultar():
        try:
            resultado = consultar_atualizacao()
        except Exception as exc:
            resultado = {"status": "erro", "erro": str(exc)}
        try:
            janela.after(0, lambda: callback(resultado))
        except Exception:
            pass
    threading.Thread(target=consultar, daemon=True, name="nutrilab-desktop-update").start()
