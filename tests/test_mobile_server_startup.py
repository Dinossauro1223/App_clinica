"""Testes do endpoint de saúde e confirmação de inicialização do servidor Mobile."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

from mobile import servidor
import mobile_server_health


class TestHealthCheckMobile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nutrilab-health-")
        self.db = str(Path(self.tmp.name) / "mobile.db")
        servidor.preparar_banco(self.db)
        self.http = servidor.criar_servidor(self.db, 0, "127.0.0.1")
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:%s/health" % self.http.server_address[1]

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=1)
        self.tmp.cleanup()

    def test_health_endpoint_returns_database_ready(self):
        with urlopen(self.url, timeout=1) as response:
            data = json.loads(response.read().decode("utf-8"))
        self.assertEqual(response.status, 200)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["database"], "ready")
        self.assertEqual(data["database_id"], mobile_server_health.database_identity(self.db))

    def test_health_check_helper_and_wait_for_helper(self):
        self.assertTrue(mobile_server_health.check_server_health(self.url))
        self.assertTrue(mobile_server_health.wait_for_server_health(
            self.url, timeout=1.0, interval=0.05, expected_db=self.db
        ))
        self.assertFalse(mobile_server_health.check_server_health(
            self.url, expected_db=str(Path(self.tmp.name) / "other.db")
        ))

    def test_health_check_rejects_non_nutrilab_http_service(self):
        self.assertFalse(mobile_server_health.check_server_health(self.url + "/not-health"))

    def test_database_unavailable_reports_not_ready(self):
        from urllib.error import HTTPError
        self.http.db = str(Path(self.tmp.name) / "missing.db")
        # A missing SQLite file is not a valid initialized server database.
        with self.assertRaises(HTTPError) as raised:
            urlopen(self.url, timeout=1)
        response = raised.exception
        data = json.loads(response.read().decode("utf-8"))
        self.assertEqual(response.code, 503)
        self.assertEqual(data, {"status": "error", "database": "unavailable"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
