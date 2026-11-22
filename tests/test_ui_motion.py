import unittest

import ui_motion


class WidgetFalso:
    def __init__(self, width=100):
        self.width = width
        self.callbacks = {}
        self.proximo = 0
        self.cancelados = set()

    def configure(self, **kwargs):
        self.width = kwargs.get("width", self.width)

    def after(self, _ms, callback):
        self.proximo += 1
        self.callbacks[self.proximo] = callback
        return self.proximo

    def after_cancel(self, ident):
        self.cancelados.add(ident)
        self.callbacks.pop(ident, None)

    def executar_todos(self):
        while self.callbacks:
            ident = min(self.callbacks)
            callback = self.callbacks.pop(ident)
            callback()


class TesteAnimacoesUI(unittest.TestCase):
    def test_animacao_termina_na_largura_alvo(self):
        widget = WidgetFalso(200)
        larguras = []
        ui_motion.animar_largura(widget, 200, 58, duracao_ms=90, passos=9,
                                 ao_atualizar=larguras.append)
        widget.executar_todos()
        self.assertEqual(widget.width, 58)
        self.assertEqual(larguras[-1], 58)
        self.assertGreater(len(larguras), 2)

    def test_nova_animacao_cancela_a_anterior(self):
        widget = WidgetFalso(200)
        ui_motion.animar_largura(widget, 200, 58, passos=8)
        primeiro = next(iter(widget.callbacks))
        ui_motion.animar_largura(widget, 200, 200, passos=4)
        self.assertIn(primeiro, widget.cancelados)
        widget.executar_todos()
        self.assertEqual(widget.width, 200)
