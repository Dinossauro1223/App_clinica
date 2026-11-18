# -*- coding: utf-8 -*-
"""Testes do CONTEÚDO do catálogo real de condutas de alta (enteral, respiratórias/TB e renal).

Os textos do catálogo são sugestões para a nutricionista confirmar. Estes testes guardam o que dá para
verificar por máquina (grupos, gatilhos pelo Mapa, fonte em cada número, nenhum número de dose na folha
do paciente, citações sem ambiguidade, fontes registradas no diário). Eles NÃO substituem a conferência
clínica do texto.

    python -m unittest tests.test_condutas_alta_catalogo -v
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import condutas_alta as ca  # noqa: E402

RAIZ = os.path.join(os.path.dirname(__file__), "..")
DIARIO = os.path.join(RAIZ, "docs", "desenvolvimento", "DIARIO_DUVIDAS_BIBLIOGRAFICAS.md")

ESPERADO = {
    "enteral": [f"ENT-{i:02d}" for i in range(1, 10)],
    "respiratorias_tb": [f"TB-{i:02d}" for i in range(1, 6)] + ["RES-01"],
    "renal": [f"REN-{i:02d}" for i in range(1, 6)],
}

# número seguido de unidade de dose ou de quantidade clínica (o texto do paciente deixa esses valores em branco)
DOSE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|g|kg|ml|mL|l|L|kcal|mmol|UI|%)(?![A-Za-zÀ-ÿ])")
SIGLA = re.compile(r"\b[A-ZÀ-Ý]{2,}[0-9]*\b")
EM_BRANCO = re.compile(r"_{3,}")


def texto(valor):
    return valor if isinstance(valor, str) else "\n".join(valor)


class TestCatalogoRealConteudo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = ca.carregar_catalogo()

    def codigos(self, grupo):
        return sorted(c.codigo for c in self.cat.condutas.values() if c.grupo == grupo)

    def sugeridas(self, **registro):
        return sorted(c.codigo for c in ca.condutas_aplicaveis(self.cat, ca.tokens_do_registro(registro)))

    # ---------------------------------------------------------------------------------- estrutura
    def test_tres_grupos_com_os_codigos_esperados(self):
        self.assertEqual({c.grupo for c in self.cat.condutas.values()}, set(ESPERADO))
        for grupo, codigos in ESPERADO.items():
            self.assertEqual(self.codigos(grupo), sorted(codigos), grupo)

    def test_cada_conduta_tem_texto_para_os_dois_leitores_conferencia_e_fonte(self):
        for c in self.cat.condutas.values():
            self.assertTrue(c.profissional.strip(), c.codigo)
            self.assertTrue(c.paciente.strip(), c.codigo)
            self.assertTrue(c.conferir, f"{c.codigo} sem lista de conferência")
            self.assertTrue(c.fontes, f"{c.codigo} sem fonte")
            self.assertTrue(c.titulo_paciente, f"{c.codigo} sem título para o paciente")

    def test_versao_e_data_de_revisao_em_cada_grupo(self):
        for c in self.cat.condutas.values():
            self.assertRegex(c.versao, r"^\d{4}-\d{2}-\d{2}\.\d+$", c.codigo)
            self.assertRegex(c.revisado_em, r"^\d{4}-\d{2}-\d{2}$", c.codigo)

    # ------------------------------------------------------------------- gatilhos pelo que está no Mapa
    def test_tuberculose_sugere_as_cinco_condutas_de_tb_e_nao_a_respiratoria_geral(self):
        self.assertEqual(self.sugeridas(condicoes="tb"), ESPERADO["respiratorias_tb"][:5])

    def test_doenca_respiratoria_sugere_so_a_conduta_respiratoria(self):
        self.assertEqual(self.sugeridas(condicoes="resp"), ["RES-01"])

    def test_respiratoria_com_tuberculose_sugere_as_seis(self):
        self.assertEqual(self.sugeridas(condicoes="resp,tb"), sorted(ESPERADO["respiratorias_tb"]))

    def test_doenca_renal_sugere_as_cinco_condutas_renais(self):
        self.assertEqual(self.sugeridas(drc=1), ESPERADO["renal"])
        self.assertEqual(self.sugeridas(drc=1, dm=1), ESPERADO["renal"])

    def test_via_enteral_continua_sugerindo_so_as_enterais(self):
        self.assertEqual(self.sugeridas(via="Enteral"), ESPERADO["enteral"][:8])
        self.assertEqual(self.sugeridas(via="Enteral", dm=1), ESPERADO["enteral"])

    def test_sem_doenca_relatada_nada_e_sugerido(self):
        self.assertEqual(self.sugeridas(via="Oral"), [])
        self.assertEqual(self.sugeridas(), [])
        self.assertEqual(self.sugeridas(dm=1, has=1), [])

    def test_varias_doencas_somam_as_condutas(self):
        todas = self.sugeridas(via="Enteral", dm=1, drc=1, condicoes="resp,tb")
        self.assertEqual(todas, sorted(c for lista in ESPERADO.values() for c in lista))

    # ------------------------------------------------------- folha do paciente: leiga e sem dose inventada
    def test_folha_do_paciente_nao_traz_dose_nem_quantidade_clinica(self):
        for c in self.cat.condutas.values():
            sem_brancos = EM_BRANCO.sub("", c.paciente)
            self.assertEqual(DOSE.findall(sem_brancos), [], f"{c.codigo}: dose ou quantidade fixa no texto do paciente")

    def test_valores_que_dependem_da_prescricao_ficam_em_branco(self):
        for cod in ("TB-01", "TB-02", "TB-03", "RES-01", "REN-01", "REN-02", "REN-03", "REN-04", "REN-05"):
            self.assertGreaterEqual(ca.contar_lacunas(self.cat.obter(cod).paciente), 1, cod)
        self.assertRegex(self.cat.obter("TB-03").paciente, r"piridoxina\): _{3,} mg por dia")
        self.assertRegex(self.cat.obter("REN-01").paciente, r"Proteína por dia: _{3,} g")

    def test_folha_do_paciente_sem_siglas_tecnicas(self):
        permitidas = {"CRN"}
        for c in self.cat.condutas.values():
            achadas = set(SIGLA.findall(EM_BRANCO.sub("", c.paciente))) - permitidas
            self.assertFalse(achadas, f"{c.codigo}: sigla no texto do paciente: {sorted(achadas)}")

    # ------------------------------------------------- número clínico do texto profissional tem a fonte certa
    def fontes_de(self, codigo):
        return " | ".join(self.cat.obter(codigo).fontes)

    def test_numeros_da_tuberculose_apontam_para_as_fontes_que_os_sustentam(self):
        tb02 = self.cat.obter("TB-02").profissional
        for numero in ("abaixo de 16 kg/m²", "de 16,0 a 16,99", "de 17,0 a 18,49", "acima de 19 anos"):
            self.assertIn(numero, tb02)
        self.assertIn("WHO consolidated guidelines on tuberculosis", self.fontes_de("TB-02"))
        tb03 = self.cat.obter("TB-03").profissional
        for numero in ("50 mg/dia", "200 mg/dia"):
            self.assertIn(numero, tb03)
        self.assertIn("Nota Informativa nº 16/2024", self.fontes_de("TB-03"))

    def test_numeros_renais_apontam_para_a_kdigo_2024(self):
        ren01 = self.cat.obter("REN-01").profissional
        for numero in ("0,8 g/kg", "1,3 g/kg/dia", "0,3 a 0,4 g/kg/dia"):
            self.assertIn(numero, ren01)
        self.assertIn("KDIGO 2024 Clinical Practice Guideline", self.fontes_de("REN-01"))
        ren02 = self.cat.obter("REN-02").profissional
        for numero in ("abaixo de 2 g por dia", "90 mmol", "5 g de cloreto de sódio"):
            self.assertIn(numero, ren02)
        self.assertIn("KDIGO 2024 Clinical Practice Guideline", self.fontes_de("REN-02"))

    def test_respiratoria_geral_nao_inventa_meta_numerica(self):
        res = self.cat.obter("RES-01")
        self.assertEqual(re.findall(r"\d+(?:[.,]\d+)?\s*(?:g/kg|kcal|%|mg|mL)", res.profissional), [])
        self.assertIn("Nutritional assessment and therapy in COPD", self.fontes_de("RES-01"))
        self.assertIn("lacuna", res.profissional)

    # ----------------------------------------------------------------------------------------- citações
    def test_cada_texto_profissional_cita_ao_menos_uma_fonte_no_formato_abnt(self):
        citacao = re.compile(r"\([^()]*(?:(?:19|20)\d\d|\[s\.d\.\])[^()]*\)")
        for c in self.cat.condutas.values():
            self.assertRegex(c.profissional, citacao, f"{c.codigo}: sem citação (AUTOR, ano)")

    def test_autor_e_ano_repetidos_levam_letra_na_citacao_e_na_referencia(self):
        # Há duas referências BRASIL 2024 (Anvisa e Nota Informativa 16) e duas OMS 2025 (diretriz de TB e substitutos do sal).
        for c in self.cat.condutas.values():
            lido = c.profissional + "\n" + texto(c.conferir)
            self.assertNotRegex(lido, r"\((?:BRASIL, 2024|OMS, 2025)[;)]", f"{c.codigo}: citação ambígua sem letra")
        todas = " ".join(ref for c in self.cat.condutas.values() for ref in c.fontes)
        for marca in ("7 out. 2024a.", "19 dez. 2024b.", "Genebra: OMS, 2025a.", "Genebra: OMS, 2025b."):
            self.assertIn(marca, todas)

    def test_spec_do_executavel_embute_a_pasta_do_catalogo(self):
        with open(os.path.join(RAIZ, "app_clinica.spec"), encoding="utf-8") as f:
            spec = f.read()
        self.assertIn(f"('{ca.PASTA_CATALOGO}', '{ca.PASTA_CATALOGO}')", spec)
        self.assertTrue(os.path.isdir(os.path.join(RAIZ, ca.PASTA_CATALOGO)))

    def test_toda_referencia_do_catalogo_esta_no_diario_bibliografico(self):
        with open(DIARIO, encoding="utf-8") as f:
            diario = f.read()
        faltando = []
        for ref in {r for c in self.cat.condutas.values() for r in c.fontes}:
            link = re.search(r"https?://\S+?(?=\.?\s|\)|$)", ref)
            self.assertIsNotNone(link, ref[:60])
            if link.group(0).rstrip(".") not in diario:
                faltando.append(link.group(0))
        self.assertEqual(faltando, [], "fontes do catálogo sem registro no diário bibliográfico")


if __name__ == "__main__":
    unittest.main()
