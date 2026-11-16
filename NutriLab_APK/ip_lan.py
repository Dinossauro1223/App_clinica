"""Imprime o IP deste computador na rede local (nada se nao achar). Usado pelo Gerar_APK.bat (14/11/2026)."""
import socket

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(("10.255.255.255", 1))
    ip = s.getsockname()[0]
    if not ip.startswith("127."):
        print(ip)
except OSError:
    pass
finally:
    s.close()
