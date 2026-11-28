"""Contrato de atualização Android servida pelo servidor local do NutriLab."""
import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest import mock

from mobile import servidor


class TestAtualizacaoMobileServidor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nutrilab-update-")
        self.raiz = Path(self.tmp.name)
        (self.raiz / "apk" / "saida").mkdir(parents=True)
        (self.raiz / "version.properties").write_text(
            "\n".join(["versionName=1.2.0", "versionCode=30000002", ""]), encoding="utf-8"
        )
        self.apk = b"APK-DE-TESTE-" * 128
        (self.raiz / "apk" / "saida" / "NutriLab-Mobile.apk").write_bytes(self.apk)
        self.db = str(self.raiz / "mobile.db")
        servidor.preparar_banco(self.db)
        self.patch_raiz = mock.patch.object(servidor, "AQUI", self.raiz)
        self.patch_raiz.start()
        self.http = servidor.criar_servidor(self.db, 0, "127.0.0.1")
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:%s" % self.http.server_address[1]

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=1)
        self.patch_raiz.stop()
        self.tmp.cleanup()

    def test_metadados_informam_versao_tamanho_e_hash_do_apk(self):
        with urlopen(self.base + "/api/mobile/update", timeout=2) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
        self.assertTrue(dados["disponivel"])
        self.assertEqual(dados["version_name"], "1.2.0")
        self.assertEqual(dados["version_code"], 30000002)
        self.assertEqual(dados["size"], len(self.apk))
        self.assertEqual(dados["sha256"], hashlib.sha256(self.apk).hexdigest())
        self.assertEqual(dados["download_url"], "/download/NutriLab-Mobile.apk")

    def test_download_suporta_intervalo_e_retorna_206(self):
        req = Request(self.base + "/download/NutriLab-Mobile.apk", headers={"Range": "bytes=12-31"})
        with urlopen(req, timeout=2) as resposta:
            conteudo = resposta.read()
            self.assertEqual(resposta.status, 206)
            self.assertEqual(resposta.headers["Content-Range"], "bytes 12-31/%d" % len(self.apk))
            self.assertEqual(resposta.headers["Accept-Ranges"], "bytes")
        self.assertEqual(conteudo, self.apk[12:32])

    def test_download_suporta_intervalo_de_sufixo(self):
        req = Request(self.base + "/download/NutriLab-Mobile.apk", headers={"Range": "bytes=-9"})
        with urlopen(req, timeout=2) as resposta:
            self.assertEqual(resposta.read(), self.apk[-9:])
            self.assertEqual(resposta.status, 206)

    def test_intervalo_invalido_retorna_416(self):
        req = Request(self.base + "/download/NutriLab-Mobile.apk", headers={"Range": "bytes=999999-"})
        with self.assertRaises(HTTPError) as erro:
            urlopen(req, timeout=2)
        self.assertEqual(erro.exception.code, 416)

    def test_sem_apk_nao_anuncia_atualizacao(self):
        (self.raiz / "apk" / "saida" / "NutriLab-Mobile.apk").unlink()
        with urlopen(self.base + "/api/mobile/update", timeout=2) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
        self.assertEqual(dados, {"disponivel": False})


if __name__ == "__main__":
    unittest.main(verbosity=2)
