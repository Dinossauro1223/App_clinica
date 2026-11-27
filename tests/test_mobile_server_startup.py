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


class _EncerramentoControlado:
    """Evento mínimo para testar espera/cancelamento sem atrasos reais."""

    def __init__(self, cancelar=False):
        self.cancelar = cancelar
        self.encerrado = False
        self.esperas = []

    def is_set(self):
        return self.encerrado

    def wait(self, segundos):
        self.esperas.append(segundos)
        if self.cancelar:
            self.encerrado = True
        return self.cancelar


class TestRetryInicializacaoMobile(unittest.TestCase):
    def _app_minimo(self, cancelar=False):
        import ast
        import os
        import queue
        import sys
        import types
        from datetime import datetime

        # Compila somente o método-alvo: importar main.py carregaria a interface
        # e suas dependências de desktop, alheias ao contrato do worker.
        # gráfica inteira, que não faz parte do ambiente mínimo destes testes.
        fonte = Path(__file__).resolve().parents[1] / "main.py"
        arvore = ast.parse(fonte.read_text(encoding="utf-8"))
        classe = next(n for n in arvore.body if isinstance(n, ast.ClassDef) and n.name == "AppClinica")
        metodo = next(n for n in classe.body if isinstance(n, ast.FunctionDef) and n.name == "_iniciar_servidor_mobile_worker")
        modulo = ast.Module(body=[metodo], type_ignores=[])
        ast.fix_missing_locations(modulo)
        namespace = {
            "im": types.SimpleNamespace(caminho_mobile_db=lambda *_: "clinica.db"),
            "caminho_do_banco": lambda: "clinica.db",
            "get_base_path": lambda: ".",
            "os": os,
            "sys": sys,
            "datetime": datetime,
            "threading": threading,
            "socket": types.SimpleNamespace(),
            "importlib": __import__("importlib"),
            "mobile_server_health": types.SimpleNamespace(),
            "__file__": str(fonte),
        }
        exec(compile(modulo, str(fonte), "exec"), namespace)
        app = types.SimpleNamespace()
        app._mobile_encerrando = _EncerramentoControlado(cancelar=cancelar)
        app._mobile_lock = threading.Lock()
        app._mobile_resultados = queue.Queue()
        app._servidor_mobile = None
        app._thread_servidor_mobile = None
        app._iniciar_servidor_mobile_worker = types.MethodType(
            namespace["_iniciar_servidor_mobile_worker"], app
        )
        return app

    def _executar_com_falha_no_banco(self, app, mensagem):
        from unittest import mock

        preparar = mock.Mock(side_effect=OSError(mensagem))
        app._iniciar_servidor_mobile_worker.__globals__["im"].caminho_mobile_db = preparar
        with mock.patch("os.makedirs"), mock.patch("builtins.open", mock.mock_open()), mock.patch("builtins.print"):
            app._iniciar_servidor_mobile_worker()
        return preparar

    def test_falha_persistente_faz_tres_tentativas_e_publica_um_erro(self):
        app = self._app_minimo()
        preparar = self._executar_com_falha_no_banco(app, "banco indisponível")

        self.assertEqual(preparar.call_count, 3)
        self.assertEqual(app._mobile_encerrando.esperas, [1.5, 3.0])
        resultado = app._mobile_resultados.get_nowait()
        self.assertEqual(resultado[0], "erro")
        self.assertIn("banco indisponível", resultado[1])
        self.assertTrue(app._mobile_resultados.empty())

    def test_fechamento_cancela_nova_tentativa(self):
        app = self._app_minimo(cancelar=True)
        preparar = self._executar_com_falha_no_banco(app, "falha transitória")

        self.assertEqual(preparar.call_count, 1)
        self.assertEqual(app._mobile_encerrando.esperas, [1.5])
        self.assertTrue(app._mobile_resultados.empty())


class TestThreadInicializacaoMobile(unittest.TestCase):
    def test_worker_de_inicio_e_referenciado_e_aguardado_no_fechamento(self):
        fonte = Path(__file__).resolve().parents[1] / "main.py"
        texto = fonte.read_text(encoding="utf-8")
        self.assertIn('self._thread_inicializacao_mobile = worker', texto)
        self.assertIn('worker_startup.join(timeout=2.0)', texto)
        self.assertIn('self._mobile_encerrando.set()', texto)
        self.assertIn('worker_startup.is_alive()', texto)


if __name__ == "__main__":
    unittest.main(verbosity=2)
