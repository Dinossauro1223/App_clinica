# -*- coding: utf-8 -*-
"""Roda tools/verificar_interface_tk.py: a interface (atalhos e gráficos agrupados) com Tk e CustomTkinter DE VERDADE.

Os outros testes usam widgets falsos. Este abre uma janela real, simula mouse e teclado e confere o resultado, mas
só onde existe Tk e tela: no CI do Windows e do Linux (com Xvfb). Onde não há (por exemplo um servidor sem tela),
o teste é pulado e diz por quê. O script é executado num processo à parte porque test_ui_smoke.py troca o tkinter
por um falso no processo dos testes.

    python tools/verificar_interface_tk.py     # o mesmo script, para rodar à mão e ver cada verificação
"""
import os
import subprocess
import sys
import unittest

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(RAIZ, "tools", "verificar_interface_tk.py")
SEM_TELA = 77   # código de saída do script quando não há Tk ou tela


class TestInterfaceComTkDeVerdade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ambiente = dict(os.environ, PYTHONUTF8="1")
        cls.resultado = subprocess.run([sys.executable, SCRIPT], capture_output=True, text=True, encoding="utf-8",
                                       errors="replace", timeout=480, env=ambiente, cwd=RAIZ)
        # o relatório do script (cada verificação, com o tempo que levou) vai para o log do CI, passando ou não
        print("\n--- saída de tools/verificar_interface_tk.py ---\n" + cls.resultado.stdout.strip() + "\n---", flush=True)

    def relatorio(self):
        r = self.resultado
        return f"código de saída {r.returncode}\n--- saída ---\n{r.stdout}\n--- erros ---\n{r.stderr}"

    def test_verificacoes_com_tk_real(self):
        r = self.resultado
        if r.returncode == SEM_TELA:
            self.skipTest("sem Tk ou sem tela neste ambiente: " + (r.stdout.strip().splitlines() or ["?"])[-1])
        self.assertEqual(r.returncode, 0, self.relatorio())
        linhas = [x for x in r.stdout.splitlines() if x.startswith(("[OK]", "[FALHA]", "[PULOU]"))]
        # o script realmente rodou as verificações (não saiu cedo sem fazer nada)
        self.assertGreaterEqual(sum(1 for x in linhas if x.startswith("[OK]")), 8, self.relatorio())
        self.assertFalse([x for x in linhas if x.startswith("[FALHA]")], self.relatorio())


if __name__ == "__main__":
    unittest.main(verbosity=2)
