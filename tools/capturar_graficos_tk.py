# -*- coding: utf-8 -*-
"""Tira fotos da tela dos gráficos com Tk de VERDADE, para conferir a aparência sem abrir o programa.

Os testes automáticos provam o comportamento (arraste, animação, balão), mas não como o desenho fica no Windows ou
no Linux: serrilhado das curvas, fonte, espaçamentos. Este script abre a janela, monta os gráficos com dados
SINTÉTICOS e salva PNGs da tela. É informativo: nunca falha o CI (sai com 0 mesmo se não conseguir capturar).

    python tools/capturar_graficos_tk.py PASTA [--base64]

`--base64` também escreve cada imagem no log, em linhas [IMG nome] ..., para quando não dá para baixar o arquivo:
    grep '^\\[IMG nome.png\\]' log.txt | sed 's/^\\[IMG nome.png\\] //' | base64 -d > nome.png
"""
import base64
import io
import os
import sys
import traceback

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for pasta in (RAIZ, os.path.dirname(os.path.abspath(__file__))):
    if pasta not in sys.path:
        sys.path.insert(0, pasta)

import verificar_interface_tk as v  # noqa: E402


def capturar(raiz, pasta, nome, mostrar_base64):
    """Salva o que está na tela dentro da janela. Devolve True se conseguiu."""
    from PIL import ImageGrab
    raiz.update()
    x, y, w, h = raiz.winfo_rootx(), raiz.winfo_rooty(), raiz.winfo_width(), raiz.winfo_height()
    try:
        imagem = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    except Exception as e:  # noqa: BLE001  (sem área de trabalho, sem xcb...)
        print(f"[INFO] captura {nome} falhou: {e}", flush=True)
        return False
    caminho = os.path.join(pasta, nome)
    imagem.save(caminho, optimize=True)
    cores = len(imagem.convert("RGB").getcolors(1 << 20) or [])
    print(f"[INFO] captura {nome}: {imagem.size[0]}x{imagem.size[1]} px, {cores} cores, {os.path.getsize(caminho)} bytes",
          flush=True)
    if mostrar_base64:
        buf = io.BytesIO()
        imagem.save(buf, format="PNG", optimize=True)
        texto = base64.b64encode(buf.getvalue()).decode("ascii")
        print(f"[IMG {nome}] BEGIN {len(texto)}", flush=True)
        for i in range(0, len(texto), 2000):
            print(f"[IMG {nome}] {texto[i:i + 2000]}", flush=True)
        print(f"[IMG {nome}] END", flush=True)
    return True


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 0
    pasta, mostrar_base64 = argv[1], "--base64" in argv
    os.makedirs(pasta, exist_ok=True)
    try:
        import tkinter as tk
        import customtkinter as ctk
    except Exception as e:  # noqa: BLE001
        print(f"[INFO] sem tkinter/customtkinter, nada capturado ({e})")
        return 0
    try:
        raiz = ctk.CTk()
    except tk.TclError as e:
        print(f"[INFO] sem tela para abrir a janela, nada capturado ({e})")
        return 0
    erros = []
    raiz.report_callback_exception = lambda *info: erros.append("".join(traceback.format_exception(*info)))
    largura, altura = min(1240, raiz.winfo_screenwidth() - 20), min(820, raiz.winfo_screenheight() - 80)
    raiz.geometry(f"{largura}x{altura}+0+0")
    for opcao in (("-topmost", True),):                            # na frente de tudo, senão a captura sai com outra janela
        try:
            raiz.attributes(*opcao)
        except Exception:  # noqa: BLE001
            pass
    raiz.lift()
    v.bombear(raiz, 0.6)
    print(f"[INFO] tela {raiz.winfo_screenwidth()}x{raiz.winfo_screenheight()}, janela {largura}x{altura}, "
          f"escala {ctk.ScalingTracker.get_window_scaling(raiz) if hasattr(ctk, 'ScalingTracker') else '?'}", flush=True)

    g = v.Graficos(raiz, ctk, erros)
    lado = g.gl.DISPOSICAO_LADO_A_LADO
    try:
        g.montar(lado, "animado", espera=0.0)
        v.bombear(raiz, 0.25)
        capturar(raiz, pasta, "01_entrada_no_meio.png", mostrar_base64)       # barras e linhas ainda crescendo
        v.bombear(raiz, 2.4)
        capturar(raiz, pasta, "02_entrada_pronta.png", mostrar_base64)
        # balão com o valor: passa o mouse numa barra do primeiro gráfico
        faixa = g.painel.faixas[0]
        c = faixa.canvas
        for item, texto in faixa.dicas.items():
            if c.itemcget(item, "state") == "hidden":
                continue
            x0, y0, x1, y1 = c.bbox(item)
            wx, wy = (x0 + x1) / 2 - c.canvasx(0), y0 + 6 - c.canvasy(0)
            if 40 < wx < c.winfo_width() - 160 and 40 < wy < c.winfo_height() - 40:
                c.event_generate("<Motion>", x=int(wx), y=int(wy))
                break
        v.bombear(raiz, 0.2)
        capturar(raiz, pasta, "03_balao.png", mostrar_base64)
        c.event_generate("<Leave>")
        # arrasta a primeira faixa para o segundo gráfico
        rolavel = next((f for f in g.painel.faixas if f.n_posicoes > 1), None)
        if rolavel:
            rolavel.ir_para(1)
            v.bombear(raiz, 2.0)
            capturar(raiz, pasta, "04_segundo_grafico.png", mostrar_base64)
        g.montar(g.gl.DISPOSICAO_VERTICAL, "animado", espera=2.2)
        capturar(raiz, pasta, "05_de_cima_para_baixo.png", mostrar_base64)
        g.montar(lado, "imagem", espera=0.9)
        capturar(raiz, pasta, "06_imagem_simples.png", mostrar_base64)
        ctk.set_widget_scaling(1.5)                                  # como um monitor com escala de 150% no Windows
        v.bombear(raiz, 0.4)
        g.montar(lado, "animado", espera=2.4)
        capturar(raiz, pasta, "07_escala_150.png", mostrar_base64)
        ctk.set_widget_scaling(1.0)
    except Exception:  # noqa: BLE001
        print("[INFO] a captura parou por um erro: " + traceback.format_exc(limit=4).strip().replace("\n", " | "))
    if erros:
        print(f"[INFO] erros escondidos em callbacks do Tk: {len(erros)}: {erros[0].strip().splitlines()[-1]}")
    try:
        raiz.destroy()
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
