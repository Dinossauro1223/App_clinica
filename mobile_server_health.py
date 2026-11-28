"""Health-check HTTP estrito para confirmar que a API NutriLab Mobile está pronta."""
import hashlib
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def database_identity(path):
    """Identificador não reversível para validar que servidor e desktop apontam ao mesmo DB."""
    resolved = str(Path(path).resolve()).casefold()
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()


def check_server_health(url, timeout=0.5, expected_db=None):
    """Retorna True somente se endpoint responder 200 com status/schema esperado."""
    req = Request(url, headers={"Accept": "application/json", "Cache-Control": "no-cache"})
    try:
        with urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                return False
            data = json.loads(response.read().decode("utf-8"))
            return (
                data.get("status") == "ok"
                and data.get("database") == "ready"
                and (expected_db is None or data.get("database_id") == database_identity(expected_db))
            )
    except (URLError, HTTPError, OSError, ValueError, json.JSONDecodeError):
        return False


def wait_for_server_health(url, timeout=3.0, interval=0.15, expected_db=None):
    """Aguarda a API ficar saudável, sem exceder o prazo total aproximado."""
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        if check_server_health(
            url, timeout=min(0.5, max(0.05, deadline - time.monotonic())), expected_db=expected_db
        ):
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(interval, remaining))
