"""Serve a pasta 'saida' pela rede local para o celular baixar o APK (criado em 12/11/2026). Ctrl+C encerra."""
import functools
import http.server
import os
import socket

PORTA = 8000
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saida")


def ip_lan():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


if not os.path.isdir(PASTA):
    raise SystemExit("Pasta 'saida' nao encontrada. Gere o APK primeiro (Gerar_APK.bat).")
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=PASTA)
print("No navegador do celular (mesmo Wi-Fi), abra:")
print("    http://%s:%d/NutriLab-Mobile.apk" % (ip_lan(), PORTA))
print("Se o Windows perguntar sobre o Firewall, permita o Python na rede privada.")
print("Feche esta janela (ou Ctrl+C) quando terminar.")
try:
    http.server.ThreadingHTTPServer(("0.0.0.0", PORTA), handler).serve_forever()
except KeyboardInterrupt:
    pass
