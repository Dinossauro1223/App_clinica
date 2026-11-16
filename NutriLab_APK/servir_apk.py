"""Serve a pasta 'saida' pela rede local para o celular baixar o APK (criado em 12/11/2026, revisado em 14/11/2026).
Ctrl+C encerra. A pagina inicial explica a instalacao e mostra o endereco do servidor NutriLab (porta 8765)."""
import http.server
import os
import socket

PORTA = 8000
PORTA_NUTRILAB = 8765
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saida")
PAGINA = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NutriLab - instalar</title>
<style>body{font:18px/1.5 sans-serif;margin:0;padding:24px;background:#f3f6f2;color:#1d2a2a}h1{color:#0f4c5c;margin:0 0 4px}
a.b{display:block;text-align:center;background:#0f4c5c;color:#fff;font-weight:bold;text-decoration:none;padding:18px;border-radius:10px;margin:18px 0}
.c{background:#fff;border:1px solid #cfd8d3;border-radius:10px;padding:14px;margin:12px 0}code{font-size:1.4em;font-weight:bold;color:#0f4c5c}</style></head><body>
<h1>NutriLab</h1><p>Aplicativo do Serviço de Nutrição</p>
<a class="b" href="/NutriLab-Mobile.apk">Baixar o aplicativo (APK)</a>
<div class="c"><b>1.</b> Toque em <b>Baixar</b>, abra o arquivo e, se o Android pedir, permita instalar de fontes desconhecidas.<br>
<b>2.</b> Abra o <b>NutriLab</b>.<br><b>3.</b> Quando ele pedir o endereço do servidor, use:<br><code>{IP}:{PORTA}</code><br>
<small>Essa é a porta do servidor NutriLab. Esta página (porta {P8000}) serve só para baixar o aplicativo.</small></div></body></html>"""


def ip_lan():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Manipulador(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PASTA, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html"):
            corpo = (PAGINA.replace("{IP}", ip_lan()).replace("{PORTA}", str(PORTA_NUTRILAB))
                     .replace("{P8000}", str(PORTA)).encode("utf-8"))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
        else:
            super().do_GET()


if not os.path.isdir(PASTA):
    raise SystemExit("Pasta 'saida' nao encontrada. Gere o APK primeiro (Gerar_APK.bat).")
print("No navegador do celular (mesmo Wi-Fi), abra:")
print("    http://%s:%d" % (ip_lan(), PORTA))
print("Depois de instalar, no app digite o endereco do servidor NutriLab:")
print("    %s:%d      (porta %d: so o servidor do NutriLab; a porta %d e so do download)" % (ip_lan(), PORTA_NUTRILAB, PORTA_NUTRILAB, PORTA))
print("Se o Windows perguntar sobre o Firewall, permita o Python na rede privada.")
print("Feche esta janela (ou Ctrl+C) quando terminar.")
try:
    http.server.ThreadingHTTPServer(("0.0.0.0", PORTA), Manipulador).serve_forever()
except KeyboardInterrupt:
    pass
