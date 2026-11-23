# -*- coding: utf-8 -*-
"""Execução segura de tarefas demoradas sem bloquear o loop gráfico do Tk.

A função de trabalho roda em uma thread daemon e não deve acessar widgets.
Os callbacks são entregues pelo loop principal via after().
"""
from __future__ import annotations

import threading
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


def executar_em_segundo_plano(
    janela,
    trabalho: Callable[[], T],
    ao_sucesso: Optional[Callable[[T], None]] = None,
    ao_erro: Optional[Callable[[Exception], None]] = None,
    ao_finalizar: Optional[Callable[[], None]] = None,
    nome: str = "nutrilab-tarefa",
) -> threading.Thread:
    """Executa I/O/cálculo fora da GUI e entrega o resultado no thread do Tk."""
    def executar():
        resultado = None
        erro = None
        try:
            resultado = trabalho()
        except Exception as exc:
            erro = exc

        def entregar():
            try:
                if hasattr(janela, "winfo_exists") and not janela.winfo_exists():
                    return
                if erro is not None:
                    if ao_erro:
                        ao_erro(erro)
                elif ao_sucesso:
                    ao_sucesso(resultado)
            finally:
                if ao_finalizar:
                    ao_finalizar()

        try:
            janela.after(0, entregar)
        except Exception:
            # A janela pode ter sido encerrada enquanto a tarefa terminava.
            pass

    thread = threading.Thread(target=executar, name=nome, daemon=True)
    thread.start()
    return thread
