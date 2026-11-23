# Diário de dúvidas bibliográficas e decisões clínicas de referência

**Finalidade:** registro interno e append-only para Claude e seus agentes. Sempre que surgir uma dúvida sobre fonte, artigo, equação, tabela, corte, unidade, população de validade ou interpretação bibliográfica, o agente deve pesquisar e registrar a solução aqui. **Não perguntar ao usuário qual artigo/fonte escolher.**

## Regras de preenchimento

- Usar a data real da pesquisa em `America/Recife` (`AAAA-MM-DD HH:MM`).
- Registrar todos os artigos/documentos efetivamente consultados, não apenas referências encontradas em um resultado de busca.
- Para cada artigo: autor(es), ano, título, periódico/órgão, volume/páginas quando disponível, DOI ou URL, e página/tabela/figura relevante.
- Informar população/amostra, idade, sexo, variáveis e unidades estudadas.
- Explicar evidência favorável e contraditória, a decisão escolhida e sua limitação.
- Relacionar arquivos/funções e testes afetados.
- Nunca apagar uma entrada antiga. Uma nova conclusão deve criar entrada posterior e referenciar a anterior.
- Se não houver solução robusta, registrar `PENDENTE`, manter somente o cálculo/indicador afetado indisponível e continuar o restante do roadmap.

## Contexto de pesquisa já fornecido

O projeto recebeu `docs/referencias/RELATORIO_FORMULAS_E_ESTIMATIVAS.txt`, um relatório de fórmulas antropométricas datado de 25/10/2026. O relatório reúne 13 seções sobre estatura, peso, IMC, composição corporal, massa muscular, gasto energético, índices de risco e cálculos de terapia nutricional, com referências e marcações `[verificada]`/`[conferir]`. Esse documento é o ponto de partida; não é necessário perguntar ao usuário para refazer o levantamento. A leitura da fonte original continua necessária ao implementar coeficientes ou resolver conflitos.

## Modelo de entrada — copiar para cada ocorrência

### REF-AAAA-MM-DD-NNN — Título curto da dúvida

- **Data/hora (America/Recife):** AAAA-MM-DD HH:MM
- **Agente responsável:** nome do agente
- **Fase/issue/branch:** Fase N / referência da tarefa
- **Estado:** RESOLVIDA | PARCIALMENTE RESOLVIDA | PENDENTE
- **Dúvida original:** qual fórmula, tabela, unidade, faixa etária, população ou referência estava incerta?
- **Onde apareceu:** arquivo, função, tela, planilha ou requisito.

#### Fontes consultadas

1. Autor(es). Ano. *Título*. Periódico/órgão, volume, páginas. DOI/URL. Página/tabela/figura consultada.
   - População/amostra:
   - Faixa etária/sexo:
   - Variáveis/unidades:
   - Contribuição para a decisão:
2. (Adicionar as demais fontes efetivamente consultadas.)

#### Comparação e análise

- O que as fontes concordam:
- Onde divergem:
- Qual população é mais semelhante à população-alvo:
- Limitações, risco de viés e validade externa:

#### Decisão adotada

- Escolha:
- Justificativa:
- Alternativas descartadas ou mantidas como opção:
- Como o software comunica a limitação:

#### Impacto técnico e verificação

- Arquivos/tabelas/funções alterados:
- Migração ou versão de referência:
- Testes adicionados/executados:
- Resultado real dos testes:
- Pendências restantes:

---

## Histórico de entradas

_Nenhuma nova dúvida bibliográfica foi registrada neste pacote de documentação. O agente deve criar a primeira entrada no momento em que surgir a próxima dúvida efetiva; não preencher exemplos fictícios nem inventar pesquisa que não foi realizada._


### REF-2026-11-11-001 — Meninas brancas 6–18 anos: coeficiente 2,14 (planilha do setor) ou 2,15 (literatura) na estatura por AJ (Chumlea et al., 1994)

- **Data/hora (America/Recife):** 2026-11-11 22:13
- **Agente responsável:** `clinical-evidence-researcher` (papel executado em sequência pelo agente integrador)
- **Fase/issue/branch:** Fase 2 — pré-trabalho independente do código / `feat/fase-2-conferencia-equacoes-planilha`
- **Estado:** PARCIALMENTE RESOLVIDA — decisão tomada com base em fontes secundárias concordantes; o artigo original não foi acessado.
- **Dúvida original:** a equação de estatura por altura do joelho para meninas brancas de 6 a 18 anos usa 2,14 ou 2,15 como coeficiente de AJ?
- **Onde apareceu:** planilha do setor `CÁLCULOS ESTIMATIVA DE PESO E ESTATURA.xlsx`, aba `Peso-Alt`, célula `F10` (`=(43.21+2.14*B4)/100`), contra o relatório do projeto, seção 4.2 (2,15). Detectada por `tools/conferir_equacoes_planilha.py`.

#### Fontes consultadas

1. Planilha do setor (documento interno enviado pelo usuário em 2026-11-09; sem URL). Aba `Peso-Alt`, célula `F10`. Traz 2,14; os outros 25 itens conferidos coincidem com o relatório.
2. Relatório do projeto (25/10/2026), seção 4.2, status `[verificada]`: 2,15 (erro-padrão 3,90 cm); referência completa: Chumlea WC, Guo SS, Steinbaugh ML. Prediction of stature from knee height for black and white adults and children with application to mobility-impaired or handicapped persons. J Am Diet Assoc. 1994;94(12):1385-8 (como listada no relatório; **o artigo não foi aberto**).
3. Vitorino SAS. 2007. *Análise de equações para estimativa de estatura e percentual de gordura corporal em crianças de 6 a 10 anos*. Dissertação (Mestrado), Universidade Federal de Viçosa. https://posnutricao.ufv.br/wp-content/uploads/2019/08/Santuzza.pdf (resumo). Cita Chumlea et al. (1994): meninas brancas E = 43,21 + 2,15·AJ.
   - População/amostra: 404 crianças de 6 a 10 anos, rede pública. Variáveis: AJ (cm) → estatura (cm).
4. HU-UFGD/Ebserh. POP.EMTN.002 — Avaliação antropométrica e nutricional em paciente adulto/idoso, versão 02 (15/08/2024). https://www.gov.br/hubrasil/pt-br/hospitais-universitarios/regiao-centro-oeste/hu-ufgd/acesso-a-informacao/pops-protocolos-e-processos/gad/pop-emtn-002-avaliacao-antropometrica-e-nutricional-em-paciente-adulto_idoso-v-2.pdf — Quadro 2: "43,21 + 2,15 x AJ (cm)", fonte "adaptada de Chumlea, 1994".
5. Portal de Boas Práticas IFF/Fiocruz. *Desospitalização de crianças com condições crônicas complexas de saúde: o papel da nutrição* (apresentação, 2024). https://portaldeboaspraticas.iff.fiocruz.br/wp-content/uploads/2024/08/DESOSP_CCC_NUTRIC_CRIANCA.pdf — "Meninas brancas = 43,21 + (2,15 x CJ)", citando Chumlea et al., 1994 (CJ = comprimento do membro inferior a partir do joelho).
6. Medical Algorithms. *Estimating height for black and white children from knee height*. https://www.medicalalgorithms.com/estimating-height-for-black-and-white-children-from-knee-height — "(2.15 * knee height) + 43.21", Chumlea (1994), 6–18 anos.
7. Revista ALAN, artigo "Estimación de talla y peso en niños de 9 a 14 años" (título lido no cabeçalho de página; autoria e volume **não verificados**). https://www.alanrevista.org/download/article/4582 — "TE = AR x 2,15 + 43,21" para meninas. Observação: o mesmo texto imprime o peso de meninas brancas com "−50,06", enquanto a planilha, o relatório e o POP trazem −50,16 — erro de transcrição naquela publicação, sem efeito sobre a decisão.
8. Correia ER, Pinheiro RO. 2017. *Estatura real x estatura estimada pela fórmula de Chumlea em crianças e adolescentes atendidas em um hospital terciário de referência do Nordeste brasileiro*. TCC, Faculdade Pernambucana de Saúde (IMIP, Recife). https://tcc.fps.edu.br/handle/fpsrepo/368 (resumo). Relata que a fórmula de Chumlea (1994) subestimou a estatura em crianças e adolescentes hospitalizados. Evidência fraca (TCC), mas regionalmente próxima; usada apenas como limitação.

#### Comparação e análise

- **O que as fontes concordam:** relatório e cinco documentos secundários (3, 4, 5, 6, 7) trazem 2,15 com intercepto 43,21; os demais 3 grupos de 6–18 anos e todos os outros coeficientes de peso e estatura de 19–80 anos coincidem entre planilha e relatório.
- **Onde divergem:** apenas a planilha (2,14). Nenhuma fonte consultada traz 2,14.
- **Impacto numérico:** diferença de 0,01 × AJ; com AJ de 35 a 55 cm, a planilha subestima a estatura em 0,35 a 0,55 cm (e, por consequência, superestima levemente o IMC).
- **Limitações e vieses:** as fontes secundárias podem copiar-se entre si; a concordância entre elas **não** equivale a verificação independente do original. A equação foi derivada em crianças típicas dos EUA e aplicada a crianças com limitação de mobilidade (relatório, 4.2); o TCC do IMIP (item 8) sugere subestimação na população local.

#### Decisão adotada

- **Escolha:** usar **2,15** no catálogo de fórmulas e no código; registrar a divergência com a planilha; sinalizar ao responsável pela planilha a conferência da célula `F10`. A planilha não é artefato do repositório e não foi alterada.
- **Justificativa:** 6 de 6 fontes consultadas trazem 2,15; 2,14 não tem respaldo encontrado; provável erro de digitação na planilha.
- **Alternativa descartada:** manter 2,14 para reproduzir a planilha — a regra do projeto é não replicar coeficiente sem fonte.
- **Como o software comunica a limitação:** grava equação, fonte e versão com cada estimativa e rotula o valor como "estimado".
- **Condição para encerrar:** consultar o artigo original (J Am Diet Assoc 1994) e registrar o coeficiente transcrito. Até lá, marcar este coeficiente como `[conferir no original]` no catálogo.

#### Impacto técnico e verificação

- **Arquivos criados:** `tools/conferir_equacoes_planilha.py`, `tests/test_conferir_equacoes_planilha.py`, `docs/referencias/CONFERENCIA_PLANILHA_PESO_ALT.md`. Nenhum arquivo do aplicativo foi alterado (código inacessível).
- **Testes executados:** 12 testes do conferidor, todos OK (Linux, Python 3.12.3). Execução contra a planilha real: 25 de 26 itens iguais; 1 divergente (`F10`).
- **Pendências:** conferir em `nutri_calculos.py` qual coeficiente é usado (2,14 ou 2,15) e cobrir com teste de referência; consultar o artigo original.

---

### REF-2026-11-11-002 — Estatura para 60 anos ou mais: a planilha do setor usa Chumlea e Guo (1992); o relatório sugere Chumlea (1985) como padrão

- **Data/hora (America/Recife):** 2026-11-11 22:13
- **Agente responsável:** `clinical-evidence-researcher` (papel executado em sequência pelo agente integrador)
- **Fase/issue/branch:** Fase 2 — pré-trabalho independente do código / `feat/fase-2-conferencia-equacoes-planilha`
- **Estado:** PARCIALMENTE RESOLVIDA — decisão técnica tomada; homologação clínica pelo setor continua como critério de liberação.
- **Dúvida original:** qual equação de estatura por AJ o programa deve usar por padrão para 60 anos ou mais: a prática da planilha do setor ou a sugestão do relatório?
- **Onde apareceu:** planilha `Peso-Alt`, células `F30`, `F31`, `F33`, `F34` (60–80 anos, por sexo e cor) e bloco "Cálculos – Amputado" (`B45`, `C45`, inversão de 1985); relatório, seções 4.4 e 4.6.

#### Fontes consultadas

1. Planilha do setor, aba `Peso-Alt` (documento interno). As quatro fórmulas de 60–80 anos coincidem exatamente com a tabela de Chumlea e Guo (1992) do relatório: homens brancos 59,01 + 2,08·AJ; homens negros 95,79 + 1,37·AJ; mulheres brancas 75,00 + 1,91·AJ − 0,17·idade; mulheres negras 58,72 + 1,96·AJ. O bloco de amputados inverte Chumlea, Roche e Steinbaugh (1985): 64,19 − 0,04·idade + 2,02·AJ (homens) e 84,88 − 0,24·idade + 1,83·AJ (mulheres).
2. Relatório do projeto (25/10/2026), seções 4.4, 4.5 e 4.6. Equações de 1985, 1992 e 1998 marcadas `[verificada]` **no relatório**; sugestão inicial: 1985 como padrão "por ser o mais difundido no país", com opção de trocar por 1998. O relatório também cita estudos brasileiros (Lima et al., 2018; Silva et al., 2018; Demetra, 2019) que **não foram reabertos** nesta sessão.
   - Referências do relatório: Chumlea WC, Roche AF, Steinbaugh ML. Estimating stature from knee height for persons 60 to 90 years of age. J Am Geriatr Soc. 1985;33(2):116-20. Chumlea WC, Guo S. Equations for predicting stature in white and black elderly individuals. J Gerontol. 1992;47(6):M197-203. Chumlea WC, Guo SS, Wholihan K, et al. Stature prediction equations for elderly non-Hispanic white, non-Hispanic black, and Mexican-American persons developed from NHANES III data. J Am Diet Assoc. 1998;98(2):137-42.
3. HU-UFGD/Ebserh. POP.EMTN.002, versão 02 (2024), Quadro 3 (60–90 anos, Chumlea 1985). Imprime 2,04 como coeficiente de AJ para homens; o relatório já aponta provável erro de digitação (o original é 2,02, como na planilha do setor).
   - URL: https://www.gov.br/hubrasil/pt-br/hospitais-universitarios/regiao-centro-oeste/hu-ufgd/acesso-a-informacao/pops-protocolos-e-processos/gad/pop-emtn-002-avaliacao-antropometrica-e-nutricional-em-paciente-adulto_idoso-v-2.pdf

#### Comparação e análise

- **Concordam:** os coeficientes da planilha para 60–80 anos são idênticos aos de Chumlea e Guo (1992) no relatório; o bloco de amputados é idêntico a Chumlea 1985 (com 2,02, não 2,04).
- **Divergem:** a planilha usa 1992 (por sexo e cor) como estimativa corrente e 1985 só para amputados; o relatório sugere 1985 como padrão geral. A planilha cobre apenas 60–80 anos; Chumlea 1985 declara faixa de 60 a 90 anos.
- **Evidência de desempenho (conforme o relatório, não reaberta):** nenhuma equação teve bom desempenho em mulheres idosas e em pessoas de 70 anos ou mais em lares de idosos de Natal; Chumlea 1985 superestimou a estatura em cerca de 5 cm em idosos de ambulatório em Lagarto (SE).
- **População mais semelhante:** adultos e idosos hospitalizados no Nordeste; nenhuma das equações foi derivada nessa população.

#### Decisão adotada

- **Escolha:** o catálogo registra as três equações para 60 anos ou mais (1985, 1992, 1998), cada uma com população e limites. O **padrão inicial é a prática documentada do setor (Chumlea e Guo 1992, por sexo e cor, 60–80 anos)**; 1985 e 1998 ficam selecionáveis.
- **Justificativa:** manter continuidade com os números que o setor já produz e registra nas evoluções; a sugestão do relatório baseia-se na difusão da equação, e o desempenho local de todas é limitado. A escolha é reversível por configuração.
- **Alternativas mantidas como opção:** Chumlea 1985 (sem cor; 60–90 anos) e Chumlea 1998 (NHANES III, sexo e cor, 60 anos ou mais).
- **Como o software comunica a limitação:** grava nome da equação, fonte e versão junto do valor; rotula "estimado"; mostra aviso de precisão reduzida (mulheres e 70 anos ou mais); acima de 80 anos não usa a equação de 1992 sem aviso explícito.
- **Pendência de homologação:** o setor deve confirmar a equação padrão; a decisão acima é técnica e não substitui essa homologação.

#### Impacto técnico e verificação

- **Arquivos:** nenhum alterado além da documentação e do conferidor (código inacessível).
- **Testes:** `tests/test_conferir_equacoes_planilha.py` cobre a extração das fórmulas de 60–80 anos e do bloco de amputados (12 testes, OK).
- **Pendências:** verificar em `nutri_calculos.py` qual equação é usada hoje para 60 anos ou mais e como o programa a seleciona; implementar a seleção com testes de referência.

---

### REF-2026-11-11-003 — Equações de peso por AJ + PB: coeficientes coincidem, mas a citação original varia entre documentos

- **Data/hora (America/Recife):** 2026-11-11 22:13
- **Agente responsável:** `clinical-evidence-researcher` (papel executado em sequência pelo agente integrador)
- **Fase/issue/branch:** Fase 2 — pré-trabalho independente do código / `feat/fase-2-conferencia-equacoes-planilha`
- **Estado:** PARCIALMENTE RESOLVIDA — coeficientes conferidos entre documentos; publicação original a identificar.
- **Dúvida original:** a que publicação de Chumlea atribuir as equações de peso por AJ + PB para 6–18, 19–59 e 60–80 anos?
- **Onde apareceu:** planilha `Peso-Alt` (6–18 anos rotulada "Chumlea et al. 1994"; demais faixas só "Chumlea et al."); relatório, seção 5.2 (a citação varia: Chumlea, Roche e Mukherjee, 1987, Ross; Chumlea et al., 1988; Chumlea e Guo, 1994); POP.EMTN.002 do HU-UFGD ("Fonte: Chumlea et al., 1998").

#### Fontes consultadas

1. Planilha do setor, aba `Peso-Alt`: 12 equações de peso, todas iguais às do relatório.
2. Relatório do projeto, seções 5.1 e 5.2 (`[verificada]`; observação sobre a citação variável e sobre erro de digitação em uma apostila).
3. HU-UFGD/Ebserh. POP.EMTN.002, versão 02 (2024), Quadro 1 — mesmos 12 conjuntos de coeficientes (inclusive 0,44·AJ + 2,86·PB − 39,21 para homens negros de 60–80 anos). URL na REF-2026-11-11-002, item 3.
4. Revista ALAN (item 7 da REF-2026-11-11-001): imprime −50,06 em vez de −50,16 para meninas brancas — erro de transcrição.

#### Comparação e análise

- **Concordam:** planilha, relatório e POP trazem os mesmos coeficientes; o erro de transcrição observado (−50,06) aparece só em uma publicação secundária.
- **Divergem:** a atribuição (1987, 1988, 1994 ou 1998). Não foi possível identificar, sem abrir os originais, em qual deles cada conjunto foi publicado.
- **Limitações:** os três documentos podem derivar de uma mesma fonte secundária; coeficientes iguais em cópias não provam a transcrição correta do original.

#### Decisão adotada

- **Escolha:** manter os coeficientes (conferidos entre documentos) e citar a fonte como "Chumlea et al. (equações de peso por AJ + CB; publicação original a confirmar)". Não escolher um ano sem consultar a fonte.
- **Justificativa:** regra do projeto — não atribuir a uma referência o que não foi verificado nela.
- **Como o software comunica a limitação:** rótulo da equação com a citação acima e a faixa etária de validade (até 80 anos; acima disso, aviso).
- **Pendência:** identificar a publicação original de cada conjunto (1987 Ross; J Am Diet Assoc 1988;88:564-8; outras) e registrar em nova entrada que referencie esta.

#### Impacto técnico e verificação

- **Arquivos:** nenhum alterado; coeficientes cobertos por `tests/test_conferir_equacoes_planilha.py` (catálogo de referência).
- **Pendências:** conferir `nutri_calculos.py`; testes de referência do código quando acessível.


---

### REF-2026-11-17-001: Orientações de alta em nutrição enteral domiciliar, fonte de cada orientação

- **Data/hora (America/Recife):** 2026-11-17 01:55 (pesquisa feita em 2026-11-13 e 2026-11-14; registro posterior, no mesmo pacote das condutas de alta)
- **Agente responsável:** `clinical-evidence-researcher` (papel executado pelo agente integrador)
- **Fase/issue/branch:** condutas de alta na consulta / `feat/condutas-de-alta`
- **Estado:** PARCIALMENTE RESOLVIDA
- **Dúvida original:** que documentos sustentam o que a nutricionista entrega ao paciente em dieta enteral na alta (prescrição, misturas caseiras, posição, água, validade, medicamentos, sonda, sinais de alerta, acompanhamento) e que pontos ficam sem fonte?
- **Onde apareceu:** pedido do usuário de 2026-11-13 (revisão sobre alimentação enteral) e de 2026-11-14 (levar as revisões para a parte clínica da consulta). Arquivo `condutas_alta/enteral.json`.

#### Fontes consultadas

1. BISCHOFF, S. C. et al. ESPEN guideline on home enteral nutrition. Clinical Nutrition, v. 39, n. 1, p. 5-22, 2020. Versão em português. Disponível em: https://www.espen.org/files/ESPEN-Guidelines/HEN-Guideline-Portuguese.pdf. Acesso em: 13 nov. 2026.
   - Uso: ENT-01 (início em casa com paciente e cuidador treinados, informação por escrito, modo de infusão), ENT-02 (misturas caseiras desaconselhadas, boa prática), ENT-03 (água na sonda, aspiração), ENT-05 (medicamentos pela sonda), ENT-06 (gastrostomia, grau B), ENT-07 e ENT-08 (acompanhamento, peso).
   - População: pacientes em nutrição enteral domiciliar (diretriz de prática clínica). A faixa etária não foi registrada nesta leitura.
   - Como li: versão em português do site da ESPEN, por ferramenta que devolve trechos.
2. BRASIL. Ministério da Saúde. Agência Nacional de Vigilância Sanitária. Resolução RDC nº 503, de 27 de maio de 2021. Dispõe sobre os requisitos mínimos exigidos para a Terapia de Nutrição Enteral. Diário Oficial da União: seção 1, Brasília, DF, n. 136, p. 417, 21 jul. 2021. Republicada por ter saído com incorreção no original. Disponível em: https://ses.sp.bvs.br/wp-content/uploads/2021/07/U_RS-MS-ANVISA-RDC-503-REP_270521.pdf. Acesso em: 13 nov. 2026.
   - Uso: ENT-01 (arts. 25 e 26), ENT-02 (art. 3º, VIII; art. 45; arts. 25 e 172), ENT-04 (arts. 45 e 46). O art. 191 e a nota de republicação foram relidos em segunda leitura; o conteúdo do art. 191 não foi detalhado neste registro.
   - População: norma sanitária para serviços e pacientes em terapia de nutrição enteral.
3. BRASIL. Ministério da Saúde. Agência Nacional de Vigilância Sanitária. Gerência-Geral de Alimentos. Fórmulas para nutrição enteral: perguntas e respostas. 3. ed. Brasília, DF: Anvisa, 7 out. 2024a. Disponível em: https://www.gov.br/anvisa/pt-br/centraisdeconteudo/publicacoes/alimentos/perguntas-e-respostas-arquivos/formulas-para-nutricao-enteral.pdf/@@display-file/file. Acesso em: 14 nov. 2026.
   - Uso: ENT-02 (dieta artesanal líquida ou em purê pode ser dada por sonda, mas não é fórmula para nutrição enteral; cabe ao profissional avaliar).
4. DA SILVA, J. S. V. et al. ASPEN consensus recommendations for refeeding syndrome. Nutrition in Clinical Practice, v. 35, n. 2, p. 178-195, 2020. DOI: 10.1002/ncp.10474. Disponível em: https://achpccg.com/wp-content/uploads/2024/10/Nut-in-Clin-Prac-2020-da-Silva-ASPEN-Consensus-Recommendations-for-Refeeding-Syndrome.pdf. Acesso em: 13 nov. 2026.
   - Uso: item de conferência de ENT-01 (fósforo, potássio, magnésio e tiamina, se a dieta foi iniciada ou aumentada há menos de 5 dias em paciente muito desnutrido). População: não registrada nesta leitura.
   - Como li: PDF hospedado fora do site da revista, com a citação do próprio PDF.
5. GONÇALVES, T. J. M. et al. Diretriz BRASPEN de terapia nutricional no envelhecimento. BRASPEN Journal, v. 34, supl. 3, p. 2-58, 2019. Disponível em: https://www.avantenestle.com.br/sites/default/files/2020-03/Diretriz-Braspen-min.pdf. Acesso em: 14 nov. 2026.
   - Uso: ENT-03 (cabeceira de 45° a 90° durante a alimentação oral ou enteral e por 30 a 40 minutos depois, evidência moderada) e ENT-09 (fórmulas específicas para controle glicêmico, evidência baixa). População: idosos.
6. HOSPITAL DAS CLÍNICAS DA FACULDADE DE MEDICINA DE BOTUCATU (HCFMB). Núcleo de Nutrição e Dietética. POP GE 019: administração de nutrição enteral fracionada. Botucatu: Unesp, [s.d.]a. Disponível em: https://hcfmb.unesp.br/wp-content/uploads/2024/06/POP-GE-019-Administracao-de-Nutricao-Enteral-Fracionada.pdf. Acesso em: 13 nov. 2026.
   HOSPITAL DAS CLÍNICAS DA FACULDADE DE MEDICINA DE BOTUCATU (HCFMB). Núcleo de Nutrição e Dietética. POP GE 020: administração de nutrição enteral por sistema fechado. Botucatu: Unesp, [s.d.]b. Disponível em: https://hcfmb.unesp.br/wp-content/uploads/2024/06/POP-GE-020-Administracao-de-Nutricao-Enteral-por-Sistema-Fechado.pdf. Acesso em: 13 nov. 2026.
   - Uso: ENT-03, ENT-04 e ENT-07 (cabeceira de 30° a 45°, água, lavagem das mãos, validade da dieta e do equipo, intolerância). São protocolos hospitalares.
   - Limitação: os documentos não trazem o nome do hospital nem data de revisão rotulada; a atribuição ao Hospital das Clínicas de Botucatu (Unesp) vem do site que os hospeda.
7. VOLKERT, D. et al. ESPEN practical guideline: clinical nutrition and hydration in geriatrics. Clinical Nutrition, v. 41, n. 4, p. 958-989, 2022. DOI: 10.1016/j.clnu.2022.01.024. Disponível em: https://ueaeprints.uea.ac.uk/83181/7/1_s2.0_S0261561422000346_main.pdf. Acesso em: 13 nov. 2026.
   - Uso: ENT-01 (via oral junto com a sonda; textura segura definida por especialista em disfagia, boa prática). População: idosos.
   - Como li: versão aceita (pré-prova) no repositório da Universidade de East Anglia; volume e páginas conferidos em outro registro da publicação.

Também lidos e NÃO usados no catálogo: BRASIL. Anvisa. Resolução RDC nº 21, de 13 de maio de 2015, e o resumo do ASPEN safe practices for enteral nutrition therapy (Boullata et al., 2017) no portal PSNet (só o resumo).

#### Comparação e análise

- **Divergências:** cabeceira (Botucatu, 30° a 45°; BRASPEN, 45° a 90° para idosos com disfagia) e volume de água na sonda (ESPEN, 30 mL; Botucatu, 40 mL). Não há fonte brasileira domiciliar única para esses valores.
- **Releitura:** foram relidos o art. 191 e a nota de republicação da RDC 503, a recomendação 32 e os graus da ESPEN para idosos, e as frases da BRASPEN.

#### Decisão adotada

- O texto do paciente segue a BRASPEN para a cabeceira (população-alvo idosa, evidência moderada declarada) e traz espaços em branco para volumes, horários e prescrição. Os prazos de Botucatu aparecem só no texto profissional, como protocolo hospitalar.
- Sinais de aspiração e frequência de pesagem não têm fonte nas leituras feitas: o catálogo manda incluir conforme o protocolo do serviço.
- Citação: "BRASIL, 2024a" (Anvisa) e "BRASIL, 2024b" (Nota Informativa 16/2024), para não haver citação ambígua quando as duas aparecem na mesma folha.

#### Impacto técnico e verificação

- **Arquivos:** `condutas_alta/enteral.json` (versão `2026-11-16.1`); `tests/test_condutas_alta_catalogo.py`.
- **Testes executados (17/11/2026, Linux, Python 3.13):** `python -m unittest tests.test_condutas_alta_catalogo`: 20 testes, todos OK. Eles conferem estrutura, gatilhos, fonte em cada conduta, ausência de dose no texto do paciente e registro da fonte neste diário. Não conferem o conteúdo clínico.
- **Limitações que permanecem:** a Diretriz BRASPEN de Enfermagem em Terapia Nutricional (passos práticos) não abriu e não foi citada; a RDC 503 lida é a republicada em julho de 2021, sem levantamento completo de alterações posteriores; as leituras foram por ferramenta de trechos, então números levados a trabalho acadêmico merecem conferência no original; o protocolo do HMAB precisa ser confirmado.

---

### REF-2026-11-17-002: Tuberculose na alta, o que a literatura oficial permite orientar e quais números podem entrar

- **Data/hora (America/Recife):** 2026-11-17 01:58 (pesquisa feita em 2026-11-14, 2026-11-15 e 2026-11-16)
- **Agente responsável:** `clinical-evidence-researcher` (papel executado pelo agente integrador)
- **Fase/issue/branch:** condutas de alta na consulta / `feat/condutas-de-alta`
- **Estado:** PARCIALMENTE RESOLVIDA
- **Dúvida original:** o que a OMS e o Ministério da Saúde permitem orientar, na alta de paciente com tuberculose (TB), sobre avaliação nutricional, desnutrição, vitamina B6, vitamina D, álcool, apoio alimentar e contatos; e quais números (cortes de IMC, dose) podem entrar no sistema?
- **Onde apareceu:** pedido do usuário de 2026-11-13 (revisão sobre doenças respiratórias com ressalvas para TB). Arquivo `condutas_alta/respiratorias_tb.json` (TB-01 a TB-05).

#### Fontes consultadas

1. ORGANIZAÇÃO MUNDIAL DA SAÚDE (OMS). WHO consolidated guidelines on tuberculosis: module 6: tuberculosis and comorbidities. 2. ed. Genebra: OMS, 2025b. Seção Undernutrition. Disponível em: https://www.who.int/publications/i/item/9789240111967 (cópia lida: https://medbox.org/index.php/dl/6901c38f2bba0a2b691d29d2). Acesso em: 15 nov. 2026.
   - Recomendações lidas (páginas da seção Undernutrition, inferidas do layout, podem variar em uma página): Rec. 1 (p. 7), avaliação nutricional ao diagnóstico e durante o tratamento, forte, sem evidência direta; Rec. 2 (p. 7), contatos domiciliares, forte, certeza baixa; Rec. 3 (p. 13), intervenções nutricionais na desnutrição grave, moderada ou leve, forte, certeza baixa a moderada; Rec. 6 (p. 13), cestas de alimentos com suplementos de múltiplos micronutrientes em insegurança alimentar, forte, certeza moderada; Rec. 7 (p. 23), vitamina D só em pesquisa rigorosa, condicional, certeza baixa. Adesão (Rec. 4 e 5): condicionais.
   - Definições (adultos acima de 19 anos, Tabela 1, p. 11): desnutrição grave, IMC abaixo de 16 kg/m²; moderada, 16,0 a 16,99; leve, 17,0 a 18,49. Duas leituras de trechos diferentes concordaram nos três cortes. Crianças: critérios próprios (escore Z, perímetro do braço). Gestantes: remetidas ao pré-natal da OMS (pp. 11 e 25).
   - Peso: a diretriz diz apenas que o peso é acompanhado no início do tratamento e durante todo ele (p. 27) e admite não haver critérios nem limiares de variação de peso (p. 28). A OMS não fixa frequência.
   - Cesta do ensaio RATIONS (pp. 17 e 21; números conferidos em duas leituras): 1200 kcal e 52 g de proteína por dia para a pessoa com TB; 750 kcal e 23 g para o contato domiciliar, por pelo menos 6 meses. A diretriz diz que são especificações do ensaio, NÃO doses fixadas pela OMS. Por isso NÃO entram no sistema.
   - População: pessoas com TB de qualquer idade (adulto, criança), com regras próprias por faixa. Como li: texto completo em cópia hospedada na MEDBOX (terceiro), em janelas de 100.000 caracteres; o PDF oficial do IRIS não abriu (client_error). Graus lidos na Tabela A (uma leitura) e conferidos em parte no BIGG-REC (BVS) e no comunicado da OMS de 8 out. 2025 (https://www.who.int/news/item/08-10-2025-who-releases-new-guidelines-on-tuberculosis-and-undernutrition).
2. BRASIL. Ministério da Saúde. Manual de recomendações para o controle da tuberculose no Brasil. 2. ed. atual. Brasília, DF: Ministério da Saúde, 2019. Disponível em: https://portaldeboaspraticas.iff.fiocruz.br/wp-content/uploads/2021/04/manual_recomendacoes_controle_tuberculose_brasil_2_ed.pdf. Acesso em: 14 nov. 2026.
   - Trechos lidos (leitura única por trecho, via resumo de ferramenta, páginas e seções como informadas pela ferramenta): seção 5.1 (acompanhar o peso para ajustar doses), seção 4.4.4 (piridoxina 50 mg/dia na pessoa com diabetes em uso de isoniazida), quadro 32 (na intolerância digestiva, reformular o horário, por exemplo duas horas após o café da manhã), p. 260 (avaliar o uso de álcool em todas as consultas, em especial pela hepatotoxicidade), seção 7.3.2 (restaurantes comunitários, cestas básicas e outras estratégias de segurança alimentar como incentivo à adesão da população em situação de rua).
   - Só a dose de 50 mg/dia foi confirmada por outra fonte (item 3). Os demais trechos estão marcados no texto do sistema como "leitura única, conferir no texto".
3. BRASIL. Ministério da Saúde. Secretaria de Vigilância em Saúde e Ambiente. Departamento de HIV/Aids, Tuberculose, Hepatites Virais e Infecções Sexualmente Transmissíveis. Coordenação-Geral de Vigilância da Tuberculose, Micoses Endêmicas e Micobactérias não Tuberculosas. Nota Informativa nº 16/2024-CGTM/.DATHI/SVSA/MS: orientações sobre o uso do medicamento cloridrato de piridoxina 50 mg comprimido. Brasília, DF, 19 dez. 2024b. Disponível em: https://www.rj.gov.br/saude/sites/default/files/arquivo_pagina_basica/Nota_Informativa_16-2024-Piridoxina-50mg-ampliacao-de-utilizacao.pdf. Acesso em: 16 nov. 2026.
   - Lida em 2026-11-15 e relida em 2026-11-16. A cópia lida é a hospedada no site da Secretaria de Estado de Saúde do RJ, com cabeçalho e código de verificação do SEI do Ministério da Saúde; a ferramenta de leitura não autenticou o documento no SEI. Conteúdo: situações em que o Ministério distribui piridoxina 50 mg (gestantes no esquema básico; coinfecção TB-HIV; pessoas com desnutrição e pessoas com diabetes, ambos em tratamento da TB; neuropatia periférica causada pelo tratamento; parte dos esquemas de tratamento preventivo). Dose: 50 mg/dia na prevenção e em gestantes; na neuropatia, 50 mg/dia podendo chegar a 200 mg/dia conforme o quadro clínico. Duração, álcool, idosos e corte de IMC: não constam. Duas leituras concordaram nos números.
   - Correção: as anotações anteriores traziam o título "ampliação de utilização de piridoxina 50 mg", que vinha do nome do arquivo. O título impresso na página 1 é "Orientações sobre o uso do medicamento cloridrato de piridoxina 50mg comprimido".
4. Consultados e NÃO usados: OMS. Guideline: nutritional care and support for patients with tuberculosis, 2013 (https://apps.who.int/iris/handle/10665/94836), cuja regra sobre IMC foi substituída pela edição de 2025 (confirmado em fonte secundária, BIGG-REC); páginas do BIGG-REC (BVS) usadas só para conferir graus.

#### Comparação e análise

- **Concordam:** a diretriz da OMS de 2025, o comunicado da OMS e o BIGG-REC nos graus das recomendações 1 a 3; a Nota Informativa 16/2024 e o Manual de 2019 na dose de 50 mg/dia.
- **Divergem ou não se cobrem:** o Manual de 2019 é anterior à OMS 2025 e não traz as recomendações novas; a OMS 2013 usava outra regra, hoje substituída.
- **Lacunas:** nenhuma fonte oficial encontrada sobre alimentos que interfiram na isoniazida; a lista de sintomas de neuropatia não vem das fontes lidas; frequência de pesagem (a OMS não fixa; o Manual fala em acompanhar); duração da piridoxina.

#### Decisão adotada

- Entram como SUGESTÕES para a nutricionista confirmar (TB-01 a TB-05). Números confirmados em duas leituras (cortes de IMC, 50 e 200 mg/dia) aparecem só no texto profissional, com a fonte; a folha do paciente deixa em branco tudo que depende de prescrição.
- Não entram: cesta do RATIONS e doses de micronutrientes do ensaio, vitamina D de rotina, regra de 2013, orientação sobre alimento e isoniazida, e isolamento e máscaras (fora do escopo nutricional; ficam com a equipe médica e de enfermagem).

#### Impacto técnico e verificação

- **Arquivos:** `condutas_alta/respiratorias_tb.json` (versão `2026-11-16.1`); `tests/test_condutas_alta_catalogo.py`.
- **Testes executados (17/11/2026, Linux, Python 3.13):** `python -m unittest tests.test_condutas_alta_catalogo`: 20 testes, todos OK. Eles conferem estrutura, gatilhos, fonte em cada conduta, ausência de dose no texto do paciente e registro da fonte neste diário. Não conferem o conteúdo clínico.
- **Limitações que permanecem:** a diretriz da OMS foi lida em cópia de terceiro; o Manual de 2019 foi lido por trechos de leitura única; é preciso conferir tudo no documento original antes de citar em trabalho acadêmico; a homologação clínica do texto é da nutricionista responsável.

---

### REF-2026-11-17-003: Doença respiratória (fora a TB), fonte para a orientação nutricional da alta

- **Data/hora (America/Recife):** 2026-11-17 02:00 (pesquisa feita em 2026-11-16)
- **Agente responsável:** `clinical-evidence-researcher` (papel executado pelo agente integrador)
- **Fase/issue/branch:** condutas de alta na consulta / `feat/condutas-de-alta`
- **Estado:** PARCIALMENTE RESOLVIDA (uma fonte, só o resumo lido)
- **Dúvida original:** que fonte sustenta orientação nutricional para paciente com doença respiratória, e quais metas numéricas (energia, proteína, IMC, fracionamento) podem entrar?
- **Onde apareceu:** pedido do usuário de 2026-11-13 (doenças respiratórias). Arquivo `condutas_alta/respiratorias_tb.json` (RES-01).

#### Fontes consultadas

1. SCHOLS, A. M. et al. Nutritional assessment and therapy in COPD: a European Respiratory Society statement. European Respiratory Journal, v. 44, n. 6, p. 1504-1520, 2014. DOI: 10.1183/09031936.00070914. Disponível em: https://cris.maastrichtuniversity.nl/en/publications/nutritional-assessment-and-therapy-in-copd-a-european-respiratory/. Acesso em: 16 nov. 2026.
   - Resumo lido em duas fontes (a página da Universidade de Maastricht, endereço acima, e o registro do PubMed, consultado pelo endereço www.pubmed.gov/25234804; o identificador do PubMed não pôde ser reconferido depois da leitura): o estado nutricional, em especial a composição corporal alterada, é determinante independente do desfecho da DPOC; "a intervenção nutricional é provavelmente eficaz em desnutridos e provavelmente mais quando combinada com exercício"; "uma dieta bem equilibrada beneficia todos os pacientes com DPOC" (tradução nossa do resumo). Sem números de IMC, energia ou proteína no resumo.
   - Autores (lista completa, página de Maastricht): A. M. Schols, I. M. Ferreira, F. Franssen, H. R. Gosker, W. Janssens, M. Muscaritoli, C. Pison, M. P. M. H. Rutten-van Mölken, F. Slinde, M. C. Steiner, R. Tkacova e S. J. Singh.
   - População: DPOC, com foco em desnutridos. O texto completo no site da ERS não abriu (client_error): só o resumo foi lido.
2. FERREIRA, I. M. Doença pulmonar obstrutiva crônica e desnutrição: por que não estamos vencendo a batalha? Jornal Brasileiro de Pneumologia (revisão). Disponível em: https://www.jornaldepneumologia.com.br/details/579/pt-BR. Acesso em: 16 nov. 2026. Ano, volume, páginas e DOI NÃO constam na página lida. O resumo diz que ensaios com suplementação por mais de 2 semanas não tiveram efeito estatisticamente significativo e conclui que não há evidência de eficácia da suplementação nutricional na DPOC; velhice, anorexia relativa e inflamação alta se associam à ausência de resposta. NÃO foi citada no catálogo porque sem ano e volume não há referência ABNT completa, e o texto parece mais antigo que o da ERS.
3. Encontrados na busca e NÃO lidos (bloqueio ou fonte secundária): revisão Cochrane Nutritional supplementation for stable chronic obstructive pulmonary disease (Ferreira et al., 2012, CD000998.pub3; PubMed, PMC e Cochrane Library bloqueados); páginas de divulgação do Nutritotal. Nenhuma diretriz brasileira específica de DPOC (BRASPEN ou SBPT) apareceu na busca.

#### Comparação e análise

- **Divergência:** a declaração da ERS (2014) considera a intervenção nutricional provavelmente eficaz em desnutridos; a revisão brasileira lida (data não confirmada) não encontrou efeito da suplementação em ensaios longos. A diferença pode vir de data, população e desfechos; sem os textos completos não foi possível resolver.
- **Limites:** só resumos; DPOC não é toda doença respiratória; asma, pneumonia e outras não foram levantadas.

#### Decisão adotada

- RES-01 fica curta e qualitativa: alimentação equilibrada, comunicar perda de peso, apetite e falta de ar ao comer, plano individual em branco para a nutricionista, exercício orientado pela equipe com a ressalva "provavelmente". Nenhuma meta numérica entra. A conferência avisa que a fonte é de DPOC e pede confirmar o diagnóstico.
- A divergência sobre suplemento oral NÃO é resolvida pelo sistema: a decisão sobre suplemento fica com a nutricionista.

#### Impacto técnico e verificação

- **Arquivos:** `condutas_alta/respiratorias_tb.json` (RES-01); `tests/test_condutas_alta_catalogo.py` (garante que RES-01 não traz meta numérica).
- **Testes executados (17/11/2026, Linux, Python 3.13):** `python -m unittest tests.test_condutas_alta_catalogo`: 20 testes, todos OK. Eles conferem estrutura, gatilhos, fonte em cada conduta, ausência de dose no texto do paciente e registro da fonte neste diário. Não conferem o conteúdo clínico.
- **Pendências:** ler o texto completo da declaração da ERS e a revisão Cochrane; localizar ano e volume do artigo do Jornal Brasileiro de Pneumologia; buscar diretriz brasileira e fonte para asma e outras doenças respiratórias.

---

### REF-2026-11-17-004: Doença renal crônica na alta, proteína, sal, potássio, remédios e substitutos do sal

- **Data/hora (America/Recife):** 2026-11-17 02:03 (pesquisa feita em 2026-11-15 e 2026-11-16)
- **Agente responsável:** `clinical-evidence-researcher` (papel executado pelo agente integrador)
- **Fase/issue/branch:** condutas de alta na consulta / `feat/condutas-de-alta`
- **Estado:** PARCIALMENTE RESOLVIDA
- **Dúvida original:** o que a literatura permite orientar, com fonte, ao paciente com doença renal crônica (DRC) sobre proteína, sal, substitutos do sal, potássio, remédios e suplementos, líquidos; e qual diretriz adotar quando KDIGO e KDOQI divergem?
- **Onde apareceu:** pedido do usuário de 2026-11-13 (doenças renais). Arquivo `condutas_alta/renal.json` (REN-01 a REN-05). O gatilho é a marcação "Doença renal" do Mapa (campo `drc`), que não informa estágio nem diálise.

#### Fontes consultadas

1. KIDNEY DISEASE: IMPROVING GLOBAL OUTCOMES (KDIGO) CKD WORK GROUP. KDIGO 2024 Clinical Practice Guideline for the Evaluation and Management of Chronic Kidney Disease. Kidney International, v. 105, n. 4S, p. S117-S314, 2024. Disponível em: https://kdigo.org/wp-content/uploads/2024/03/KDIGO-2024-CKD-Guideline.pdf. Acesso em: 15 nov. 2026.
   - Lida pelo sumário executivo (https://kdigo.org/wp-content/uploads/2017/02/KDIGO-2024-CKD-Guideline-Executive-Summary.pdf) e pelo texto completo (páginas S205 a S229, em janelas de leitura). Itens: recomendação 3.3.1.1 (2C), proteína de 0,8 g/kg/dia em adultos com DRC G3 a G5; prática 3.3.1.1, evitar mais de 1,3 g/kg/dia em quem tem risco de progressão; prática 3.3.1.2, dieta com 0,3 a 0,4 g/kg/dia só sob supervisão rigorosa e com aminoácidos essenciais ou cetoanálogos; prática 3.3.1.3, não prescrever dieta pobre em proteína a quem está metabolicamente instável; prática 3.3.1.4, crianças, não restringir; prática 3.3.1.5, idosos com fragilidade e sarcopenia, considerar metas maiores de proteína e de calorias; sódio abaixo de 2 g/dia (90 mmol, 5 g de cloreto de sódio) (2C) e a ressalva de que a restrição geralmente não cabe na nefropatia perdedora de sal (exceções citadas: nefropatia perdedora de sal, desnutrição, clima muito quente, p. S211); práticas 3.3.2 (nutricionista renal e adaptações individuais), 3.11.5.1 e 3.11.5.2 (potássio individualizado; limitar alimentos ricos em potássio biodisponível), 4.1.3 (rever medicamentos sem prescrição e fitoterápicos), 5.2.3.2 e 5.2.3.3 (triagem de desnutrição). Trecho sobre substitutos de sal feitos com cloreto de potássio, p. S228, lido em dois fragmentos.
   - População: adultos com DRC G3 a G5 sem diálise. Números de proteína e de sódio confirmados em duas leituras (sumário e texto completo); práticas de potássio 3.11.5.1 e 3.11.5.2 também em duas leituras; os demais itens, uma leitura.
2. ORGANIZAÇÃO MUNDIAL DA SAÚDE (OMS). Launch of the WHO guideline on the use of lower-sodium salt substitutes: overview. Genebra: OMS, 2025a. Apresentação de slides. Disponível em: https://cdn.who.int/media/docs/default-source/nutrition-and-food-safety/events/2025/launch-of-lsss-guideline-presentation-1-overview.pdf?sfvrsn=73c55f08_3. Acesso em: 16 nov. 2026.
   - Lida em slides de lançamento da diretriz da OMS (leitura única): recomendação condicional, certeza baixa, de trocar o sal comum por substitutos com menos sódio e com potássio em adultos da população geral, com exclusão de pessoas com comprometimento renal e de condições que podem comprometer a excreção de potássio (slides 6 e 7; tradução nossa). O PDF da diretriz e o resumo no IRIS não abriram (client_error).
3. BRASIL. Ministério da Saúde. Secretaria de Atenção Primária à Saúde. Linhas de cuidado: doença renal crônica (DRC) em adultos: listagem de alimentos ricos e pobres em potássio. [S. l.]: Ministério da Saúde, [s.d.]. Disponível em: https://linhasdecuidado.saude.gov.br/portal/doenca-renal-cronica-(DRC)-em-adultos/listagem-alimentos/. Acesso em: 16 nov. 2026.
   - Leitura única: tabela com colunas de baixo e de alto teor de potássio, sem corte numérico por porção; "Sal dietéticos ou light" está na coluna de alto teor; legumes têm baixo teor de potássio "se cozidos em água fervente e desprezando a água da fervura"; a página cita como fonte "Adaptado de Orientações nutricionais. Sociedade Brasileira de Nefrologia. São Luís: EDUFMA, 2018". A página não traz data nem público-alvo.
4. FABRE, L. et al. Manual para pacientes com doença renal crônica: estágios 4 e 5. [S. l.]: [s. n.], [2024?]. Disponível em: https://sbn.org.br/wp-content/uploads/2024/11/ManualProntoDRC4e5_compressed.pdf. Acesso em: 16 nov. 2026.
   - Leitura única, páginas inferidas do texto extraído (podem variar em uma): público, adultos e idosos com DRC estágios 4 e 5 não dialítica (p. 5); reduzir o sal no preparo (p. 34); "o sal light é rico em potássio" e pode elevar o potássio no sangue (p. 44); a excreção de potássio cai com a perda da função renal (p. 42); ferver os vegetais reduz cerca de 50% do potássio da maioria (p. 43); evitar excesso de proteína (p. 62) e manter acompanhamento com nutricionista (p. 40); quantidade de líquido combinada com o médico, sem volume (p. 20); anti-inflamatórios como diclofenaco, ibuprofeno e naproxeno podem prejudicar o rim (p. 32); cuidado com suplementos, que podem elevar o fósforo (p. 48). Chás e fitoterápicos não constam. A página não nomeia a editora; o arquivo está hospedado em sbn.org.br; o ano foi estimado ([2024?]).
5. Lidos e NÃO usados no catálogo (secundários ou rascunho): rascunho de consulta pública "Clinical Practice Guideline for Nutrition in Chronic Kidney Disease: 2019 Update" (KDOQI, outubro de 2019; primeiros 100.000 de 542.065 caracteres; numeração do rascunho difere da versão final); LAMBERT, K. et al. Commentary on the 2020 update of the KDOQI clinical practice guideline for nutrition in chronic kidney disease. Nephrology, v. 27, n. 6, p. 537-540, 2022 (https://pmc.ncbi.nlm.nih.gov/articles/PMC9303594); MOLINA, P. et al. Optimizing Diet to Slow CKD Progression. Frontiers in Medicine, v. 8, art. 654250, 2021, DOI 10.3389/fmed.2021.654250 (https://pmc.ncbi.nlm.nih.gov/articles/PMC8267004). O texto original da KDOQI 2020 NÃO foi lido.
6. Encontrados na busca e NÃO lidos: relatório preliminar do PCDT de DRC da Conitec (consulta pública nº 56, 2026), Diretrizes clínicas para o cuidado ao paciente com doença renal crônica no SUS (Ministério da Saúde, 2014), protocolos estaduais e municipais, páginas de divulgação.

#### Comparação e análise

- **Divergem:** sódio (KDIGO 2024, abaixo de 2 g/dia; rascunho e secundários da KDOQI, abaixo de 2,3 g/dia, ou 100 mmol); proteína em DRC não dialítica (KDIGO, 0,8 g/kg/dia; secundários da KDOQI, faixas menores, com variação por diabetes); diálise (a KDIGO 2024 não cobre; as fontes secundárias da KDOQI citam 1,0 a 1,2 g/kg/dia). Esses valores da KDOQI vêm de rascunho e de comentários, não do original.
- **Concordam:** KDIGO, manual de pacientes e lista do Ministério da Saúde em que sal light e substitutos de sal levam potássio; a OMS exclui pessoas com doença renal do uso de substitutos.
- **Mais adequada à população-alvo:** KDIGO 2024 trata de idosos frágeis e sarcopênicos e pede metas MAIORES de proteína e energia, o perfil do caso de estágio com paciente idosa desnutrida; por isso o texto mantém "sem restringir" como item de conferência.

#### Decisão adotada

- KDIGO 2024 como fonte principal: texto original lido, atual e compatível com adultos e idosos com DRC sem diálise. KDOQI 2020 fica como alternativa não adotada, porque o original não foi lido.
- Nenhuma meta para diálise, para diabetes com DRC ou para fósforo entra no sistema; a conferência manda seguir o protocolo da nefrologia. Líquidos: nenhuma fonte lida traz volume, o campo fica em branco.
- Folha do paciente: nenhum número; metas de proteína, sal, potássio, líquidos e suplemento ficam em branco para a nutricionista preencher. Cuidados gerais com sal light, anti-inflamatórios, chás e suplementos entram com a ressalva de falar com a equipe.

#### Impacto técnico e verificação

- **Arquivos:** `condutas_alta/renal.json` (versão `2026-11-16.1`); `tests/test_condutas_alta_catalogo.py` (números renais apontam para a KDIGO 2024).
- **Testes executados (17/11/2026, Linux, Python 3.13):** `python -m unittest tests.test_condutas_alta_catalogo`: 20 testes, todos OK. Eles conferem estrutura, gatilhos, fonte em cada conduta, ausência de dose no texto do paciente e registro da fonte neste diário. Não conferem o conteúdo clínico.
- **Limitações que permanecem:** páginas e trechos de leitura única estão marcados no texto; KDIGO lida em janelas parciais; OMS lida em slides; o manual de pacientes não nomeia a editora; a marcação "Doença renal" do Mapa não distingue estágio nem diálise, então a conferência pede essa informação.
- **Pendências:** ler a KDOQI 2020 no original e registrar nova entrada que referencie esta; ler o PCDT de DRC e as diretrizes do Ministério da Saúde; buscar fonte para fósforo, líquidos, diabetes com DRC e diálise.

---

### REF-2026-11-18-001: Doença renal crônica, proteína no diabetes com DRC e na diálise (KDIGO 2022)

- **Data/hora (America/Recife):** 2026-11-18 08:10
- **Agente responsável:** `clinical-evidence-researcher` (papel executado pelo agente integrador)
- **Fase/issue/branch:** condutas de alta na consulta / `feat/condutas-de-alta`
- **Estado:** PARCIALMENTE RESOLVIDA. Esta entrada complementa a `REF-2026-11-17-004`, que fica como está: ela deixou "diabetes com DRC" e "diálise" sem fonte, e aqui entra fonte primária só para proteína e sódio nesses dois casos.
- **Dúvida original:** existe, em fonte primária, meta de proteína para pessoas com diabetes e DRC sem diálise e para quem faz diálise? A diretriz de diabetes na DRC traz algo sobre sódio, potássio e substitutos do sal que mude os textos de `REN-02` e `REN-03`?
- **Onde apareceu:** fechamento da revisão 3 (doenças renais) pedida pelo usuário em 2026-11-13; pendência da `REF-2026-11-17-004`. Arquivo `condutas_alta/renal.json`.

#### Fontes consultadas

1. KIDNEY DISEASE: IMPROVING GLOBAL OUTCOMES (KDIGO) DIABETES WORK GROUP. KDIGO 2022 Clinical Practice Guideline for Diabetes Management in Chronic Kidney Disease. Kidney International, v. 102, n. 5S, p. S1-S127, 2022. Disponível em: https://kdigo.org/wp-content/uploads/2023/12/KDIGO-2022-Diabetes-Guideline.pdf. Acesso em: 18 nov. 2026.
   - Lida pelo WebFetch em quatro janelas de 100.000 caracteres (o texto tem 601.577): 0 a 100.000 (resumo das recomendações, páginas S19 a S28), 100.000 a 200.000 (capítulo 1, sem nutrição), 200.000 a 300.000 (capítulo 3, seção 3.1 Nutrição, páginas S63 a S71) e 300.000 a 400.000 (seção 3.2 e capítulos 4 e 5, sem proteína). A ferramenta devolve resumo feito por modelo pequeno, não o PDF, e as páginas impressas podem variar em uma.
   - População: pessoas com diabetes e DRC (o documento trata de diabetes na DRC).
   - Confirmado em duas leituras (resumo, p. S24, e capítulo, p. S63 a S65): recomendação 3.1.1 (2C), proteína de 0,8 g/kg (peso)/dia em pessoas com diabetes e DRC sem diálise; prática 3.1.2, quem faz hemodiálise e, principalmente, diálise peritoneal deve consumir de 1,0 a 1,2 g/kg (peso)/dia; recomendação 3.1.2 (2C), sódio abaixo de 2 g/dia (90 mmol; 5 g de cloreto de sódio).
   - Leitura única: p. S63, na DRC avançada o potássio pode precisar de restrição, com frutas e verduras de menor teor; p. S67, substitutos de sal ricos em potássio podem não ser adequados na DRC avançada; p. S64 e S65, desnutrição e dieta muito baixa em proteína (0,4 a 0,6 g/kg/dia), que "could lead to malnutrition".
   - Não encontrado nas janelas lidas: meta de energia (kcal/kg), fósforo, líquidos e meta própria para idosos frágeis ou sarcopênicos.
   - Uso: `REN-01` (proteína e diálise), `REN-02` (sódio e substitutos do sal) e `REN-03` (potássio na DRC avançada).

#### Comparação e análise

- **Concorda:** com a KDIGO 2024 (proteína de 0,8 g/kg/dia e sódio abaixo de 2 g/dia, ambos 2C). Os 1,0 a 1,2 g/kg/dia em diálise coincidem com o que o comentário de Lambert et al. (2022) atribui à KDOQI 2020 (fonte secundária; original não lido).
- **Diverge:** das faixas para diabetes que fontes secundárias atribuem à KDOQI (0,6 a 0,8 g/kg de peso ideal no comentário; 0,8 a 0,9 no rascunho de 2019) e na base de peso (a KDIGO usa kg de peso corporal; as secundárias, peso ideal).
- **Divergência no próprio repositório, não alterada:** `exames_internos/EXM-TFG-ESTIMADA-EGFR.json` (conteúdo anterior a esta branch, sem fonte no arquivo) traz proteína de 0,6 g/kg/dia em G4, de 0,6 a 0,8 g/kg/dia em G3b e de 1,2 a 1,4 g/kg/dia em diálise, além de limites de potássio (2.000 mg/dia) e de fósforo (800 mg/dia). A KDIGO 2024 sugere 0,8 g/kg/dia de G3 a G5 sem diálise, a KDIGO 2022 cita 1,0 a 1,2 g/kg/dia em diálise, e nas leituras desta entrega não apareceram limites numéricos de potássio nem de fósforo. O arquivo não foi alterado: é conteúdo clínico de outra funcionalidade e a mudança depende da nutricionista responsável.

#### Decisão adotada

- A KDIGO 2022 entra como fonte de `REN-01` (proteína no diabetes com DRC sem diálise e em diálise), `REN-02` (sódio no diabetes com DRC e substitutos do sal) e `REN-03` (potássio na DRC avançada). Versão do catálogo renal: `2026-11-18.1`.
- A folha do paciente continua sem número: as metas seguem em branco para a nutricionista preencher.
- Correção de atribuição em `REN-03`: "desprezar a água do cozimento" vem da lista do Ministério da Saúde (BRASIL, [s.d.]); o manual para pacientes (FABRE et al., [2024?]) diz apenas que ferver reduz cerca de 50% do potássio (leitura única). O texto agora atribui cada parte à sua fonte.
- Continuam sem valor no sistema: energia (kcal/kg), fósforo, líquidos e, em diálise, qualquer item além da proteína. A KDOQI 2020 segue como alternativa não adotada (original não lido).

#### Impacto técnico e verificação

- **Arquivos:** `condutas_alta/renal.json` (versão `2026-11-18.1`); `tests/test_condutas_alta_catalogo.py` (proteína em diálise e fonte KDIGO 2022 em `REN-01` e `REN-02`); `docs/decisoes/ADR-0006-condutas-de-alta-na-consulta.md` (lista de lacunas e de entradas do diário).
- **Testes executados (18/11/2026, Linux, Python 3.13):** `python -m unittest tests.test_condutas_alta_catalogo`: 20 testes, todos OK (o teste dos números renais passou a conferir 1,0 a 1,2 g/kg/dia e a fonte KDIGO 2022 em `REN-01` e `REN-02`; o teste do diário confere o link da KDIGO 2022). Suíte completa (`python -m unittest discover -s tests`, com um pacote `fpdf` vazio só para permitir a importação): 312 testes, OK, 2 pulados (PDF com fpdf2 real e PNG de conferência visual). Eles conferem estrutura, fonte em cada número e registro no diário; não conferem o conteúdo clínico.
- **Limitações que permanecem:** leitura por janelas, via resumo de ferramenta; potássio, substitutos do sal e desnutrição da KDIGO 2022 em leitura única; a prática de diálise vem de uma diretriz de pessoas com diabetes e DRC; a marcação "Doença renal" do Mapa não distingue estágio, diálise nem diabetes na DRC, então a conferência pede essas informações.
- **Pendências:** ler a KDOQI 2020 no original; ler o PCDT de DRC e as diretrizes do Ministério da Saúde de 2014; buscar fonte para fósforo, líquidos e energia; a nutricionista responsável decidir o que fazer com os valores de `exames_internos/EXM-TFG-ESTIMADA-EGFR.json`.


## REF-2026-11-22-001 — Equações DRI 2023 para necessidade energética de adultos

- **Data/hora (America/Recife):** 2026-11-22
- **Agente responsável:** ChatGPT
- **Fase/issue/branch:** Atendimento ambulatorial / `feat/ambulatorial-anamnese-2026-11-22`
- **Estado:** RESOLVIDA para adultos não gestantes/não lactantes; demais populações fora do escopo desta implementação.
- **Dúvida original:** quais coeficientes aplicar para estimar a necessidade energética total por equações DRI 2023, comparando-a com uma fórmula de bolso configurável?
- **Onde apareceu:** nova tela de consulta ambulatorial; `ambulatorial.py`, `main.py`, `tests/test_ambulatorial.py`.

### Fontes consultadas

1. National Academies of Sciences, Engineering, and Medicine. 2023. *Dietary Reference Intakes for Energy*. Washington, DC: The National Academies Press. Capítulo 5, Tabela 5-16 — equações de EER para adultos (19 anos ou mais). DOI: https://doi.org/10.17226/26818.
   - População/amostra: grupos de estágio de vida descritos no relatório; a tabela utilizada nesta tarefa contém equações específicas para homens e mulheres adultos.
   - Variáveis/unidades: idade em anos, estatura em centímetros, peso em quilogramas e categoria de nível de atividade física (PAL).
   - Coeficientes implementados: H inativo (753,07; −10,83; 6,50; 14,10), pouco ativo (581,47; −10,83; 8,30; 14,94), ativo (1004,82; −10,83; 6,52; 15,91), muito ativo (−517,88; −10,83; 15,61; 19,11). M inativo (584,90; −7,01; 5,72; 11,71), pouco ativo (575,77; −7,01; 6,60; 12,14), ativo (710,25; −7,01; 6,54; 12,34), muito ativo (511,83; −7,01; 9,07; 12,56).
2. Health Canada. *Dietary Reference Intakes: Reference Values for Energy*. Tabelas/quadros de referência das equações de EER e categorias de atividade física. https://www.canada.ca/en/health-canada/services/food-nutrition/healthy-eating/dietary-reference-intakes/tables/reference-values.html.
   - Uso nesta tarefa: conferência independente das equações adultas e da descrição das categorias de atividade física.

### Decisão e limitações

- Implementar apenas a equação de EER para adultos com 19 anos ou mais. Embora o relatório DRI descreva fórmulas para outras faixas, elas não foram incorporadas nesta tarefa.
- Não extrapolar a equação adulta para crianças/adolescentes, gestantes ou lactantes. Para essas populações, a interface informa que a equação não está disponível.
- Exibir EER DRI 2023 em paralelo com fórmula de bolso selecionável entre 25 e 35 kcal/kg/dia; não tratar a fórmula de bolso como parte das DRI.
- O cálculo proteico requer fator g/kg definido pelo profissional, sem valor automático presumido.
- As estimativas são apoio à decisão, não prescrição. A homologação das fórmulas e sua adequação ao contexto clínico permanece sob responsabilidade profissional.

### Impacto técnico e verificação

- **Arquivos:** `ambulatorial.py` (equações e validação), `main.py` (interface e atualização automática), `tests/test_ambulatorial.py` (exemplo da publicação e validações), `docs/decisoes/ADR-0007-melhorias-ambulatoriais.md`.
- **Teste de referência:** mulher, 22 anos, 165 cm, 63 kg, PAL pouco ativo — EER esperado de 2275,37 kcal/dia.
- **Pendências:** validar clinicamente os rótulos PAL no serviço, revisar a população de aplicação com nutricionista responsável e conferir execução visual/CI em Windows e Linux.
