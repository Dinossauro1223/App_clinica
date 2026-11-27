"""Health-check HTTP estrito para confirmar que a API NutriLab Mobile está pronta."""
import json
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def check_server_health(url, timeout=0.5):
    """Retorna True somente se endpoint responder 200 com status/schema esperado."""
    req = Request(url, headers={"Accept": "application/json", "Cache-Control": "no-cache"})
    try:
        with urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                return False
            data = json.loads(response.read().decode("utf-8"))
            return data.get("status") == "ok" and data.get("database") == "ready"
    except (URLError, HTTPError, OSError, ValueError, json.JSONDecodeError):
        return False


def wait_for_server_health(url, timeout=3.0, interval=0.15):
    """Aguarda a API ficar saudável, sem exceder o prazo total aproximado."""
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        if check_server_health(url, timeout=min(0.5, max(0.05, deadline - time.monotonic()))):
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(interval, remaining))
