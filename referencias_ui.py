# -*- coding: utf-8 -*-
"""Janela de referências técnicas utilizadas pelo NutriLab."""
from __future__ import annotations

import webbrowser
import customtkinter as ctk

import tema


REFERENCIAS = [
    (
        "BRANDÃO, Andréa Araujo et al. Diretriz Brasileira de Hipertensão Arterial – 2025. Arquivos Brasileiros de Cardiologia, v. 122, n. 9, e20250624, 2025. DOI: 10.36660/abc.20250624.",
        "Referência brasileira atual para contextualizar o monitoramento pressórico e a avaliação de pacientes com hipertensão.",
        "https://doi.org/10.36660/abc.20250624",
    ),
    (
        "CEDERHOLM, Tommy et al. GLIM criteria for the diagnosis of malnutrition: a consensus report from the global clinical nutrition community. Clinical Nutrition, v. 38, n. 1, p. 1-9, 2019. DOI: 10.1016/j.clnu.2018.08.002.",
        "Critérios fenotípicos e etiológicos para avaliação de desnutrição.",
        "https://doi.org/10.1016/j.clnu.2018.08.002",
    ),
    (
        "CHUMLEA, William C.; ROCHE, Alex F.; STEINBAUGH, Marsha L. Estimating stature from knee height for persons 60 to 90 years of age. Journal of the American Geriatrics Society, v. 33, n. 2, p. 116-120, 1985.",
        "Estimativa de estatura por altura do joelho em idosos.",
        "https://pubmed.ncbi.nlm.nih.gov/?term=Estimating+stature+from+knee+height+for+persons+60+to+90+years+of+age",
    ),
    (
        "ERNSTMEYER, K.; CHRISTMAN, E. (ed.). Nursing fundamentals. 2. ed. Eau Claire: Chippewa Valley Technical College, 2024. Part XV: Fluids and Electrolytes.",
        "Variação superior a 1 kg em 24 horas como alerta para revisão do balanço hídrico, com pesagem padronizada.",
        "https://www.ncbi.nlm.nih.gov/books/NBK610839/",
    ),
    (
        "GOMES, F. et al. ESPEN practical guideline: clinical nutrition in hospitalized patients. Clinical Nutrition, v. 40, n. 12, p. 5684-5709, 2021. DOI: 10.1016/j.clnu.2021.09.012.",
        "Referência para acompanhamento da ingestão e suporte nutricional em pacientes hospitalizados.",
        "https://doi.org/10.1016/j.clnu.2021.09.012",
    ),
    (
        "IKIZLER, T. Alp et al. KDOQI clinical practice guideline for nutrition in CKD: 2020 update. American Journal of Kidney Diseases, v. 76, n. 3, supl. 1, p. S1-S107, 2020. DOI: 10.1053/j.ajkd.2020.05.006.",
        "Referência alternativa para avaliação e cuidado nutricional na doença renal crônica.",
        "https://doi.org/10.1053/j.ajkd.2020.05.006",
    ),
    (
        "JENSEN, Gordon L. et al. GLIM consensus approach to diagnosis of malnutrition: a 5-year update. JPEN Journal of Parenteral and Enteral Nutrition, v. 49, n. 4, p. 414-427, 2025. DOI: 10.1002/jpen.2756.",
        "Atualização do consenso GLIM; critérios de perda de peso, baixo IMC e ingestão/assimilação não foram modificados.",
        "https://doi.org/10.1002/jpen.2756",
    ),
    (
        "KIDNEY DISEASE: IMPROVING GLOBAL OUTCOMES (KDIGO). KDIGO 2024 clinical practice guideline for the evaluation and management of chronic kidney disease. 2024.",
        "Referência renal padrão para avaliação da DRC, TFGe e albuminúria.",
        "https://kdigo.org/wp-content/uploads/2024/03/KDIGO-2024-CKD-Guideline.pdf",
    ),
    (
        "KONDRUP, Jens et al. Nutritional risk screening (NRS 2002): a new method based on an analysis of controlled clinical trials. Clinical Nutrition, v. 22, n. 3, p. 321-336, 2003.",
        "Triagem de risco nutricional e programação da reavaliação.",
        "https://pubmed.ncbi.nlm.nih.gov/?term=Nutritional+risk+screening+NRS+2002+Kondrup",
    ),
    (
        "MIFFLIN, Mark D. et al. A new predictive equation for resting energy expenditure in healthy individuals. The American Journal of Clinical Nutrition, v. 51, n. 2, p. 241-247, 1990. DOI: 10.1093/ajcn/51.2.241.",
        "Equação preditiva de gasto energético em repouso.",
        "https://doi.org/10.1093/ajcn/51.2.241",
    ),
    (
        "UNIVERSIDADE FEDERAL DO RIO GRANDE DO NORTE. Sistema Integrado de Bibliotecas. Orientações para normalização de trabalhos acadêmicos. Natal: UFRN, [s. d.].",
        "Orientação institucional de normalização, incluindo ABNT NBR 6023:2025 e NBR 10520:2023.",
        "https://sisbi.ufrn.br/biblioteca/bczm/orientacoes",
    ),
    (
        "VALENTE, Fernando et al. Manejo do Diabetes Mellitus Tipo 2. In: SOCIEDADE BRASILEIRA DE DIABETES. Diretriz Oficial da Sociedade Brasileira de Diabetes: edição 2026. São Paulo: SBD, 2026. DOI: 10.29327/5881296.2026-2.",
        "Referência nacional para contextualizar diabetes mellitus, metas glicêmicas e recomendações nutricionais.",
        "https://diretriz.diabetes.org.br/manejo-do-diabetes-mellitus-tipo-2/",
    ),
    (
        "WHITE, Jane V. et al. Consensus statement: Academy of Nutrition and Dietetics and American Society for Parenteral and Enteral Nutrition: characteristics recommended for the identification and documentation of adult malnutrition (undernutrition). JPEN Journal of Parenteral and Enteral Nutrition, v. 36, n. 3, p. 275-283, 2012. DOI: 10.1177/0148607112440285.",
        "Faixas temporais de perda ponderal e características para documentação de desnutrição em adultos.",
        "https://doi.org/10.1177/0148607112440285",
    ),
    (
        "WORLD HEALTH ORGANIZATION. WHO Child Growth Standards: length/height-for-age, weight-for-age, weight-for-length, weight-for-height and body mass index-for-age: methods and development. Geneva: WHO, 2006.",
        "Padrões de crescimento infantil e parâmetros LMS de 0 a 5 anos.",
        "https://www.who.int/tools/child-growth-standards",
    ),
    (
        "WORLD HEALTH ORGANIZATION. Growth reference data for 5-19 years. Geneva: WHO, 2007.",
        "Referência de crescimento para crianças e adolescentes de 5 a 19 anos.",
        "https://www.who.int/tools/growth-reference-data-for-5to19-years",
    ),
]


class JanelaReferencias(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Referências utilizadas — NutriLab")
        self.geometry("900x720")
        self.minsize(620, 480)
        self.transient(master)
        self.configure(fg_color=tema.FUNDO)
        self.grab_set()

        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=18, pady=(16, 8))
        ctk.CTkLabel(
            topo, text="REFERÊNCIAS UTILIZADAS",
            font=tema.fonte(19, "bold"), text_color=tema.VERDE,
        ).pack(side="left")
        ctk.CTkButton(
            topo, text="Fechar", width=90, command=self.destroy,
            fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER,
        ).pack(side="right")

        ctk.CTkLabel(
            self,
            text=("Lista em ordem alfabética, alinhada à esquerda e com referências formatadas "
                  "conforme ABNT NBR 6023:2025 e orientações da UFRN. Selecione “Consultar fonte” "
                  "para abrir o documento original. Composição, osmolaridade e fibras de cada produto "
                  "mantêm também a fonte específica registrada em sua ficha técnica."),
            justify="left", wraplength=840, text_color=tema.SUAVE,
        ).pack(fill="x", padx=20, pady=(0, 10))

        corpo = ctk.CTkScrollableFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=12, pady=(0, 14))
        for referencia, uso, url in REFERENCIAS:
            referencia_abnt = (
                referencia.rstrip(".") + ". Disponível em: " + url +
                ". Acesso em: 27 nov. 2026."
            )
            card = ctk.CTkFrame(
                corpo, fg_color=tema.BRANCO, border_width=1,
                border_color=tema.BORDA, corner_radius=9,
            )
            card.pack(fill="x", padx=5, pady=5)
            ctk.CTkLabel(
                card, text=referencia_abnt, justify="left", anchor="w",
                wraplength=800, text_color=tema.TEXTO,
                font=tema.fonte(12),
            ).pack(fill="x", padx=12, pady=(10, 4))
            ctk.CTkLabel(
                card, text="Aplicação no NutriLab: " + uso,
                justify="left", anchor="w", wraplength=800,
                text_color=tema.SUAVE, font=tema.fonte(11),
            ).pack(fill="x", padx=12, pady=(0, 6))
            ctk.CTkButton(
                card, text="Consultar fonte", width=135, height=30,
                command=lambda destino=url: webbrowser.open(destino),
                fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER,
            ).pack(anchor="e", padx=12, pady=(0, 10))

        ctk.CTkLabel(
            self,
            text=("Nota clínica: perda de pelo menos 1 kg em até 24 horas é sinal de possível deterioração "
                  "clínica/nutricional e exige avaliação da ingestão e da tendência, além de revisão do balanço "
                  "hídrico e da técnica de pesagem. Não confirma desnutrição nem substitui GLIM/ASPEN. O diagnóstico "
                  "GLIM exige pelo menos um critério fenotípico e um etiológico; a perda ponderal deve ser não intencional."),
            justify="left", wraplength=840, text_color=tema.LARANJA_TEXTO,
        ).pack(fill="x", padx=20, pady=(0, 14))
