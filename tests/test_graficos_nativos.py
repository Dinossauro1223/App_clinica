# -*- coding: utf-8 -*-
"""Cena dos gráficos animados (graficos_nativos), sem janela: geometria, animação e casos extremos."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import graficos_nativos as gn  # noqa: E402
import mapa_db as mdb  # noqa: E402
import mapa_graficos as mgr  # noqa: E402


def medir(texto, tam, negrito):
    """Medidor falso: largura proporcional ao tamanho (cada letra vale 0,55 do tamanho; negrito um pouco mais)."""
    return len(texto) * tam * (0.6 if negrito else 0.55)


PERIODO = "outubro de 2026"
DIAS = list(range(1, 32))
VALORES = [3, 5, 4, 8, 6, 0, 2, 7, 9, 4, 3, 5, 6, 8, 7, 4, 5, 6, 3, 2, 8, 9, 7, 6, 5, 4, 3, 6, 7, 8, 5]


def espec(tipo, **extra):
    return {"tipo": tipo, "titulo": "Título do gráfico", "periodo": PERIODO, **extra}


SPECS = {
    "vazio": espec("vazio", mensagem="Sem registros para exibir neste período."),
    "barras_v": espec("barras_v", x=DIAS, y=VALORES, cor="#4caf50", rotulo_x="Dia do mês", rotulo_y="Pacientes",
                      dicas=[f"Dia {d}: {v}" for d, v in zip(DIAS, VALORES)]),
    "barras_v_curto": espec("barras_v", x=[1, 2, 3], y=[2, 2, 2], cor="#4caf50", rotulo_x="Dia", rotulo_y="Pacientes",
                            dicas=["a", "b", "c"]),
    "linhas": espec("linhas", x=DIAS, rotulo_x="Dia do mês", rotulo_y="Pacientes", series=[
        {"nome": "Total atendidos", "cor": "#607d8b", "tracejado": True, "valores": VALORES},
        {"nome": "Dieta pastosa", "cor": "#ff9800", "tracejado": False, "valores": [v // 2 for v in VALORES]},
        {"nome": "Com acompanhante", "cor": "#2196f3", "tracejado": False, "valores": [v // 3 for v in VALORES]},
        {"nome": "Com suplemento", "cor": "#1b5e20", "tracejado": False, "valores": [1 + v // 4 for v in VALORES]}]),
    "roscas": espec("roscas", blocos=[
        {"nome": "Via da dieta", "itens": [{"rotulo": "Oral", "valor": 70, "cor": "#4caf50"},
                                           {"rotulo": "Enteral", "valor": 25, "cor": "#2196f3"},
                                           {"rotulo": "Não informada", "valor": 5, "cor": "#607d8b"}]},
        {"nome": "Acompanhante", "itens": [{"rotulo": "Sim", "valor": 40, "cor": "#4caf50"},
                                           {"rotulo": "Não", "valor": 60, "cor": "#607d8b"}]},
        {"nome": "Uso de suplemento", "itens": [{"rotulo": "Sim", "valor": 100, "cor": "#1b5e20"}]}]),
    "barras_h": espec("barras_h", cor="#ff9800", total=120, rotulo_x="Atendimentos (paciente-dia)", itens=[
        {"nome": "Pastosa", "valor": 60}, {"nome": "Branda", "valor": 31}, {"nome": "Livre", "valor": 12},
        {"nome": "Líquida", "valor": 9}, {"nome": "Líquida e pastosa para disfagia grave", "valor": 3}]),
}
LARGURAS, ESCALAS, PROGRESSOS = (360, 520, 840), (1.0, 1.5, 2.0), (0.0, 0.2, 0.55, 1.0)


def tipos(formas):
    return [f["t"] for f in formas]


def caixa_do_texto(f):
    """(x0, x1) que o texto ocupa, segundo a âncora."""
    x, _ = f["c"]
    w = medir(f["texto"], f["tam"], f["negrito"])
    return {"w": (x, x + w), "nw": (x, x + w), "sw": (x, x + w), "e": (x - w, x)}.get(f["ancora"], (x - w / 2, x + w / 2))


def caixa(coords):
    xs, ys = coords[0::2], coords[1::2]
    return min(xs), min(ys), max(xs), max(ys)


class TestUtilidades(unittest.TestCase):
    def test_escala_agradavel(self):
        for maximo, esperado in [(0, (1, 1)), (1, (1, 1)), (3, (3, 1)), (5, (5, 1)), (7, (8, 2)), (12, (15, 5)),
                                 (31, (40, 10)), (101, (150, 50)), (2.2, (3, 1))]:
            self.assertEqual(gn.escala_agradavel(maximo), esperado, maximo)
        for maximo in range(0, 400):
            topo, passo = gn.escala_agradavel(maximo)
            self.assertGreaterEqual(topo, maximo)
            self.assertEqual(topo % passo, 0)
            self.assertLessEqual(topo // passo, 5, maximo)

    def test_cortar_texto(self):
        self.assertEqual(gn.cortar_texto(medir, "Curto", 10, False, 500), "Curto")
        cortado = gn.cortar_texto(medir, "Um texto bem comprido que não cabe", 10, False, 100)
        self.assertTrue(cortado.endswith("…") and len(cortado) < 34)
        self.assertLessEqual(medir(cortado, 10, False), 100)
        self.assertEqual(gn.cortar_texto(medir, "Muito", 10, False, 1), "M…")   # nunca devolve vazio

    def test_pontos_arredondados(self):
        pts = gn.pontos_arredondados(10, 20, 110, 70, 8)
        self.assertEqual(len(pts) % 2, 0)
        x0, y0, x1, y1 = caixa(pts)
        self.assertEqual((x0, y0, x1, y1), (10, 20, 110, 70))
        # raio maior que a metade do lado é limitado (barra bem baixa ou bem fina)
        x0, y0, x1, y1 = caixa(gn.pontos_arredondados(0, 0, 6, 40, 30))
        self.assertEqual((x0, y0, x1, y1), (0, 0, 6, 40))
        self.assertEqual(gn.pontos_arredondados(0, 0, 10, 10, 0)[:2], [0, 0])

    def test_escurecer_e_porcentagem(self):
        self.assertEqual(gn.escurecer("#ffffff", 0.5), "#808080")
        self.assertEqual(gn.escurecer("#000000"), "#000000")
        self.assertEqual(gn.porcentagem(1, 4), 25.0)
        self.assertEqual(gn.porcentagem(1, 0), 0.0)


class TestCena(unittest.TestCase):
    def test_estrutura_e_altura_iguais_em_qualquer_progresso(self):
        """O pintor cria as formas uma vez e depois só atualiza: a lista não pode mudar de forma durante a animação."""
        for nome, spec in SPECS.items():
            for largura in LARGURAS:
                for esc in ESCALAS:
                    ref, altura = gn.construir(spec, largura * esc, 1.0, medir, esc)
                    for p in PROGRESSOS:
                        formas, h = gn.construir(spec, largura * esc, p, medir, esc)
                        self.assertEqual(tipos(formas), tipos(ref), (nome, largura, esc, p))
                        self.assertEqual(h, altura, (nome, largura, esc, p))

    def test_tudo_dentro_do_cartao(self):
        for nome, spec in SPECS.items():
            for largura in LARGURAS:
                for esc in ESCALAS:
                    w = largura * esc
                    for p in (0.0, 0.5, 1.0):
                        formas, altura = gn.construir(spec, w, p, medir, esc)
                        for f in formas:
                            if f.get("visivel") is False:
                                continue
                            ctx = (nome, largura, esc, p, f["t"], f.get("texto"))
                            if f["t"] == "texto":
                                a, b = caixa_do_texto(f)
                                self.assertGreaterEqual(a, -1, ctx)
                                self.assertLessEqual(b, w + 1, ctx)
                                self.assertTrue(0 <= f["c"][1] <= altura + 1, ctx)
                            elif f["t"] == "arco":
                                continue   # o traço do anel é grosso: conferido em test_roscas
                            else:
                                x0, y0, x1, y1 = caixa(list(f["c"]) if f["t"] != "poli" else f["c"])
                                self.assertGreaterEqual(x0, -1, ctx)
                                self.assertGreaterEqual(y0, -1, ctx)
                                self.assertLessEqual(x1, w + 1, ctx)
                                self.assertLessEqual(y1, altura + 1, ctx)

    def test_altura_minima_iguala_cartoes(self):
        for nome, spec in SPECS.items():
            natural = gn.altura_natural(spec, 600, medir)
            formas, altura = gn.construir(spec, 600, 1.0, medir, 1.0, altura_minima=natural + 120)
            self.assertEqual(altura, natural + 120, nome)
            fundo = formas[0]
            self.assertEqual(fundo["t"], "poli", nome)
            self.assertAlmostEqual(caixa(fundo["c"])[3], altura - 0.5, msg=nome)
            # com mínimo menor que o natural, vale o natural
            self.assertEqual(gn.construir(spec, 600, 1.0, medir, 1.0, altura_minima=10)[1], natural, nome)

    def test_escala_do_windows_aumenta_tudo_na_mesma_proporcao(self):
        for nome, spec in SPECS.items():
            h1 = gn.altura_natural(spec, 600, medir, 1.0)
            h15 = gn.altura_natural(spec, 600 * 1.5, medir, 1.5)
            self.assertAlmostEqual(h15 / h1, 1.5, delta=0.02, msg=nome)

    def test_titulo_comprido_e_cortado_para_caber(self):
        spec = dict(SPECS["barras_v"], titulo="Um título muito, mas muito comprido mesmo, que não cabe em cartão estreito")
        formas, _ = gn.construir(spec, 300, 1.0, medir)
        titulo = next(f for f in formas if f["t"] == "texto" and f["negrito"])
        self.assertTrue(titulo["texto"].endswith("…"))
        self.assertLessEqual(medir(titulo["texto"], titulo["tam"], True), 300 - 2 * gn.PAD + 1)

    def test_vazio(self):
        formas, altura = gn.construir(SPECS["vazio"], 500, 1.0, medir)
        textos = [f["texto"] for f in formas if f["t"] == "texto"]
        self.assertIn("Sem registros para exibir neste período.", textos)
        self.assertIn("Título do gráfico", textos)
        self.assertEqual(tipos(formas), ["poli", "texto", "texto", "texto"])
        self.assertGreater(altura, 100)


class TestBarrasVerticais(unittest.TestCase):
    def barras(self, formas):
        return [f for f in formas if f["t"] == "poli"][1:]    # a primeira é o fundo do cartão

    def test_alturas_proporcionais_aos_valores(self):
        formas, _ = gn.construir(SPECS["barras_v"], 840, 1.0, medir)
        barras = self.barras(formas)
        self.assertEqual(len(barras), len(DIAS))
        razoes = []
        for barra, v in zip(barras, VALORES):
            _, y0, _, y1 = caixa(barra["c"])
            if v:
                razoes.append((y1 - y0) / v)
                self.assertTrue(barra["visivel"])
            else:
                self.assertFalse(barra["visivel"])
                self.assertIsNone(barra["dica"])
        self.assertAlmostEqual(max(razoes), min(razoes), delta=0.01)
        self.assertEqual(barras[0]["dica"], "Dia 1: 3")

    def test_tudo_escondido_no_comeco_e_cheio_no_fim(self):
        inicio, _ = gn.construir(SPECS["barras_v"], 840, 0.0, medir)
        self.assertFalse(any(b["visivel"] for b in self.barras(inicio)))
        numeros = [f for f in inicio if f["t"] == "texto" and f["tam"] == 10 and f["texto"].isdigit()
                   and f.get("visivel") is not None]
        self.assertFalse(any(f["visivel"] for f in numeros if f["ancora"] == "s"))
        fim, _ = gn.construir(SPECS["barras_v"], 840, 1.0, medir)
        self.assertEqual(sum(1 for b in self.barras(fim) if b["visivel"]), sum(1 for v in VALORES if v))

    def test_crescem_e_a_primeira_sai_antes_da_ultima(self):
        alturas = []
        for p in (0.2, 0.4, 0.6, 0.8, 1.0):
            formas, _ = gn.construir(SPECS["barras_v"], 840, p, medir)
            alturas.append([caixa(b["c"])[3] - caixa(b["c"])[1] for b in self.barras(formas)])
        for i in range(len(DIAS)):
            serie = [a[i] for a in alturas]
            self.assertEqual(serie, sorted(serie), i)
        meio = alturas[1]
        self.assertGreater(meio[0] / VALORES[0], meio[-1] / VALORES[-1])   # escalonado: começa pela esquerda

    def test_numero_sobe_junto_com_a_barra(self):
        fim, _ = gn.construir(SPECS["barras_v"], 840, 1.0, medir)
        numeros = [f["texto"] for f in fim if f["t"] == "texto" and f["ancora"] == "s" and f.get("visivel")]
        self.assertIn("9", numeros)
        meio, _ = gn.construir(SPECS["barras_v"], 840, 0.6, medir)
        topo = [int(f["texto"]) for f in meio if f["t"] == "texto" and f["ancora"] == "s" and f.get("visivel")]
        self.assertTrue(all(v <= 9 for v in topo))

    def test_so_a_barra_mais_alta_tem_cor_mais_escura(self):
        formas, _ = gn.construir(SPECS["barras_v"], 840, 1.0, medir)
        cores = {b["fill"] for b in self.barras(formas)}
        self.assertEqual(cores, {"#4caf50", gn.escurecer("#4caf50")})
        iguais, _ = gn.construir(SPECS["barras_v_curto"], 840, 1.0, medir)
        self.assertEqual({b["fill"] for b in self.barras(iguais)}, {"#4caf50"})


class TestLinhas(unittest.TestCase):
    def linhas(self, formas, largura_min=2):
        return [f for f in formas if f["t"] == "linha" and f.get("visivel") is not None]

    def test_linha_revelada_da_esquerda_para_a_direita(self):
        pontas = []
        for p in (0.1, 0.3, 0.6, 1.0):
            formas, _ = gn.construir(SPECS["linhas"], 840, p, medir)
            ls = self.linhas(formas)
            self.assertEqual(len(ls), 4)
            self.assertTrue(all(f["visivel"] for f in ls))
            pontas.append(max(f["c"][0::2][-1] for f in ls))
        self.assertEqual(pontas, sorted(pontas))
        formas, _ = gn.construir(SPECS["linhas"], 840, 1.0, medir)
        for f in self.linhas(formas):
            self.assertEqual(len(f["c"]), 2 * len(DIAS))
        inicio, _ = gn.construir(SPECS["linhas"], 840, 0.0, medir)
        self.assertFalse(any(f["visivel"] for f in self.linhas(inicio)))

    def test_bolinhas_aparecem_conforme_a_linha_passa(self):
        def visiveis(p):
            formas, _ = gn.construir(SPECS["linhas"], 840, p, medir)
            return sum(1 for f in formas if f["t"] == "oval" and f["visivel"])
        self.assertEqual(visiveis(1.0), 4 * len(DIAS))
        self.assertLess(visiveis(0.3), visiveis(0.6))
        formas, _ = gn.construir(SPECS["linhas"], 840, 1.0, medir)
        ovais = [f for f in formas if f["t"] == "oval"]
        self.assertEqual(ovais[0]["dica"], "Total atendidos, dia 1: 3")

    def test_legenda_quebra_em_cartao_estreito(self):
        largo, h_largo = gn.construir(SPECS["linhas"], 900, 1.0, medir)
        estreito, h_estreito = gn.construir(SPECS["linhas"], 300, 1.0, medir)
        self.assertGreater(h_estreito, h_largo)
        # uma amostra de legenda por série (as 4 primeiras linhas curtas, antes dos eixos)
        self.assertEqual(len([f for f in estreito if f["t"] == "linha" and f["c"][2] - f["c"][0] == 22
                              and "visivel" not in f]), 4)

    def test_tracejado_so_na_serie_marcada(self):
        formas, _ = gn.construir(SPECS["linhas"], 840, 1.0, medir)
        dados = [f for f in formas if f["t"] == "linha" and "visivel" in f]
        self.assertEqual([bool(f["tracejado"]) for f in dados], [True, False, False, False])

    def test_um_ponto_so_nao_quebra(self):
        spec = dict(SPECS["linhas"], x=[1], series=[{"nome": "A", "cor": "#000000", "tracejado": False, "valores": [3]}])
        for p in (0.0, 0.5, 1.0):
            formas, _ = gn.construir(spec, 500, p, medir)
            self.assertTrue(formas)


class TestRoscas(unittest.TestCase):
    def arcos(self, formas):
        return [f for f in formas if f["t"] == "arco"]

    def test_fatias_somam_a_volta_inteira_no_fim(self):
        formas, _ = gn.construir(SPECS["roscas"], 840, 1.0, medir)
        arcos = self.arcos(formas)
        self.assertEqual(len(arcos), 3 + 2 + 1)
        por_bloco = [arcos[0:3], arcos[3:5], arcos[5:6]]
        for grupo in por_bloco:
            total = sum(-a["extensao"] for a in grupo)
            folgas = 0 if len(grupo) == 1 else 1.2 * len(grupo)
            self.assertAlmostEqual(total + folgas, 360.0, delta=0.05)
            self.assertTrue(all(a["visivel"] for a in grupo))
        # primeira fatia começa no topo (90 graus) e as seguintes vêm no sentido horário
        self.assertAlmostEqual(por_bloco[0][0]["inicio"], 90 - 0.6, delta=0.01)
        self.assertLess(por_bloco[0][1]["inicio"], por_bloco[0][0]["inicio"])
        # tamanho de cada fatia é proporcional ao valor
        a, b = por_bloco[0][0], por_bloco[0][1]
        self.assertAlmostEqual((-a["extensao"] + 1.2) / (-b["extensao"] + 1.2), 70 / 25, delta=0.01)

    def test_anel_vai_se_fechando_com_o_progresso(self):
        def varrido(p):
            formas, _ = gn.construir(SPECS["roscas"], 840, p, medir)
            return sum(-a["extensao"] for a in self.arcos(formas) if a["visivel"])
        valores = [varrido(p) for p in (0.1, 0.3, 0.6, 1.0)]
        self.assertEqual(valores, sorted(valores))
        self.assertEqual(sum(1 for a in self.arcos(gn.construir(SPECS["roscas"], 840, 0.0, medir)[0])
                             if a["visivel"]), 0)

    def test_porcentagem_do_centro_e_a_maior_fatia(self):
        formas, _ = gn.construir(SPECS["roscas"], 840, 1.0, medir)
        centros = [f["texto"] for f in formas if f["t"] == "texto" and f["texto"].endswith("%")]
        self.assertEqual(centros, ["70%", "60%", "100%"])

    def test_anel_cabe_no_cartao(self):
        for largura in LARGURAS:
            for esc in ESCALAS:
                w = largura * esc
                formas, altura = gn.construir(SPECS["roscas"], w, 1.0, medir, esc)
                for a in self.arcos(formas):
                    x0, y0, x1, y1 = a["c"]
                    meia = a["largura"] / 2
                    self.assertGreaterEqual(x0 - meia, -1)
                    self.assertLessEqual(x1 + meia, w + 1)
                    self.assertGreaterEqual(y0 - meia, 0)
                    self.assertLessEqual(y1 + meia, altura)

    def test_bloco_sem_dados_nao_quebra(self):
        spec = espec("roscas", blocos=[{"nome": "Vazio", "itens": []},
                                       {"nome": "Zero", "itens": [{"rotulo": "Sim", "valor": 0, "cor": "#000000"}]},
                                       {"nome": "Normal", "itens": [{"rotulo": "Sim", "valor": 4, "cor": "#4caf50"}]}])
        for p in (0.0, 0.5, 1.0):
            formas, _ = gn.construir(spec, 600, p, medir)
            self.assertEqual(sum(1 for f in formas if f["t"] == "texto" and f["texto"] == "Sem dados"), 2)


class TestBarrasHorizontais(unittest.TestCase):
    def barras(self, formas):
        return [f for f in formas if f["t"] == "poli"][1:]

    def test_larguras_proporcionais_aos_valores(self):
        formas, _ = gn.construir(SPECS["barras_h"], 840, 1.0, medir)
        larguras = [caixa(b["c"])[2] - caixa(b["c"])[0] for b in self.barras(formas)]
        valores = [60, 31, 12, 9, 3]
        razoes = [w / v for w, v in zip(larguras, valores)]
        self.assertAlmostEqual(max(razoes), min(razoes), delta=0.02)
        # de cima para baixo, na ordem recebida
        ys = [caixa(b["c"])[1] for b in self.barras(formas)]
        self.assertEqual(ys, sorted(ys))

    def test_texto_do_valor_cresce_com_a_barra(self):
        def textos(p):
            formas, _ = gn.construir(SPECS["barras_h"], 840, p, medir)
            return [f["texto"] for f in formas if f["t"] == "texto" and "%)" in f["texto"] and f.get("visivel")]
        self.assertEqual(textos(1.0), ["60  (50%)", "31  (26%)", "12  (10%)", "9  (8%)", "3  (2%)"])
        self.assertEqual(textos(0.0), [])
        self.assertLess(len(textos(0.2)), 5)

    def test_nome_comprido_e_cortado(self):
        formas, _ = gn.construir(SPECS["barras_h"], 420, 1.0, medir)
        nomes = [f["texto"] for f in formas if f["t"] == "texto" and f["ancora"] == "w" and "%)" not in f["texto"]]
        self.assertTrue(any(n.endswith("…") for n in nomes), nomes)

    def test_todos_com_valor_zero_nao_divide_por_zero(self):
        spec = dict(SPECS["barras_h"], itens=[{"nome": "A", "valor": 0}, {"nome": "B", "valor": 0}])
        for p in (0.0, 1.0):
            formas, _ = gn.construir(spec, 600, p, medir)
            self.assertTrue(formas)

    def test_dicas_com_porcentagem_do_total(self):
        formas, _ = gn.construir(SPECS["barras_h"], 840, 1.0, medir)
        self.assertEqual(self.barras(formas)[0]["dica"], "Pastosa: 60 (50%)")


class TestComDadosDoMapa(unittest.TestCase):
    """Os gráficos reais do Mapa (dados sintéticos) viram cenas válidas em qualquer largura."""

    @classmethod
    def setUpClass(cls):
        from test_mapa import novo_banco, popular_mes
        cls.db = novo_banco()
        popular_mes(cls.db, n_leitos=8)
        regs = mdb.registros_do_mes(cls.db, 2026, 10)
        cls.cheio = mgr.agregar_mes(regs, 2026, 10)
        cls.vazio = mgr.agregar_mes([], 2026, 2)

    @classmethod
    def tearDownClass(cls):
        try:
            os.remove(cls.db)
        except OSError:
            pass

    def test_todos_os_graficos_do_mapa(self):
        for agg in (self.cheio, self.vazio):
            for chave, titulo, spec in mgr.especificar_todos(agg):
                self.assertEqual(spec["titulo"] and spec["tipo"] in gn._CONSTRUTORES, True, chave)
                for largura in (320, 600, 840, 1260):
                    for p in (0.0, 0.5, 1.0):
                        formas, altura = gn.construir(spec, largura, p, medir, largura / 840)
                        self.assertTrue(formas and altura > 0, (chave, largura, p))


if __name__ == "__main__":
    unittest.main(verbosity=2)
