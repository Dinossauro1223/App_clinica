"""Animações pequenas e não bloqueantes para widgets Tk/CustomTkinter."""
from __future__ import annotations


def animar_largura(widget, inicio, fim, duracao_ms=180, passos=9, ao_atualizar=None):
    """Anima a largura com easing cúbico e cancela a animação anterior do mesmo widget."""
    passos = max(1, int(passos))
    duracao_ms = max(1, int(duracao_ms))
    estado_anterior = getattr(widget, "_nutrilab_animacao_largura", None)
    if estado_anterior:
        try:
            widget.after_cancel(estado_anterior.get("after_id"))
        except Exception:
            pass

    estado = {"after_id": None}
    setattr(widget, "_nutrilab_animacao_largura", estado)
    intervalo = max(1, duracao_ms // passos)
    largura_inicial, largura_final = float(inicio), float(fim)

    def quadro(indice):
        t = min(1.0, indice / passos)
        progresso = 1.0 - (1.0 - t) ** 3
        largura = round(largura_inicial + (largura_final - largura_inicial) * progresso)
        try:
            widget.configure(width=largura)
            if ao_atualizar:
                ao_atualizar(largura)
        except Exception:
            setattr(widget, "_nutrilab_animacao_largura", None)
            return
        if indice < passos:
            estado["after_id"] = widget.after(intervalo, lambda: quadro(indice + 1))
        else:
            estado["after_id"] = None
            setattr(widget, "_nutrilab_animacao_largura", None)

    quadro(0)
