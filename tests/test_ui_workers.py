import unittest

import ui_workers


class JanelaFalsa:
    def __init__(self):
        self.callbacks = []
        self.viva = True

    def after(self, _ms, callback):
        self.callbacks.append(callback)

    def winfo_exists(self):
        return self.viva


class TesteTarefasUI(unittest.TestCase):
    def _executar_e_entregar(self, trabalho, **callbacks):
        janela = JanelaFalsa()
        thread = ui_workers.executar_em_segundo_plano(janela, trabalho, **callbacks)
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive(), "A tarefa de teste não terminou")
        self.assertEqual(len(janela.callbacks), 1)
        janela.callbacks.pop(0)()
        return janela

    def test_entrega_resultado_no_callback(self):
        resultados = []
        finalizou = []
        self._executar_e_entregar(lambda: 42, ao_sucesso=resultados.append,
                                  ao_finalizar=lambda: finalizou.append(True))
        self.assertEqual(resultados, [42])
        self.assertEqual(finalizou, [True])

    def test_entrega_excecao_sem_perder_finalizacao(self):
        erros = []
        finalizou = []
        def falhar():
            raise ValueError("falha simulada")
        self._executar_e_entregar(falhar, ao_erro=erros.append,
                                  ao_finalizar=lambda: finalizou.append(True))
        self.assertEqual(len(erros), 1)
        self.assertIsInstance(erros[0], ValueError)
        self.assertEqual(finalizou, [True])

    def test_janela_fechada_descarta_callback(self):
        janela = JanelaFalsa()
        chamados = []
        thread = ui_workers.executar_em_segundo_plano(
            janela, lambda: "resultado", ao_sucesso=chamados.append)
        thread.join(timeout=2)
        janela.viva = False
        janela.callbacks.pop(0)()
        self.assertEqual(chamados, [])
