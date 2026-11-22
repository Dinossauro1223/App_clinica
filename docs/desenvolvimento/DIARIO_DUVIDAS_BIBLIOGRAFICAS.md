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

### REF-2026-11-15-001 — Estatura 60–80 anos: método "planilha" na tela Avaliação e evolução (referencia REF-2026-11-11-002)

- **Data/agente:** 15/11/2026 (America/Recife) — Claude (integrador).
- **Dúvida:** qual equação de estatura por AJ usar para 60+ na nova tela, já que a planilha do setor (aba `Peso-Alt`, F30:F34) difere do padrão `chumlea1985` do código.
- **Fontes consultadas:** planilha do setor e a entrada REF-2026-11-11-002. Nenhuma publicação original foi aberta nesta sessão.
- **Decisão:** incluir o método `planilha` (coeficientes idênticos aos da aba) em `nutri_calculos.METODOS_ALTURA_IDOSO`, sem mudar o padrão das demais telas; a tela Avaliação e evolução o usa por pedido do usuário (prática do setor). AJ do amputado: inverso de Chumlea (1985), como em `Peso-Alt`!B45:C45. A própria planilha mistura equações em 60+; a rotulagem na tela mostra qual foi usada.
- **Limitações:** atribuição de ano/autor da equação da planilha não confirmada (ver REF-2026-11-11-002); validação clínica institucional pendente.
- **Arquivos/testes:** `nutri_calculos.py`, `avaliacao_nutri.py`, `tests/test_avaliacao.py` (9 testes sintéticos, incluindo os valores da planilha). **Estado:** parcialmente resolvida.


### REF-2026-11-22-001 — Orientações mobile para preparo de dietas e comparação de frutas

- **Data/agente:** 22/11/2026 (America/Recife) — integração NutriLab.
- **Dúvida:** como apresentar às equipes de cozinha e copa as instruções de diluição, frutas relacionadas ao trânsito intestinal, potássio e diabetes, sem transformar comparações nutricionais em prescrição clínica automática.
- **Fontes consultadas:**
  - TBCA/USP, composição de alimentos por 100 g da parte comestível: maçã Fuji com casca (BRC0064C), melancia (BRC0027C), mamão Papaia (BRC0044C), uva Rubi (BRC0035C), melão (BRC0028C), banana-prata (BRC0011C), abacate (BRC0001C), abacaxi (BRC0002C) e laranja Pera (BRC0020C). Base: https://www.tbca.net.br/base-dados/
  - American Diabetes Association. *Standards of Care in Diabetes—2026*, seção 5 — planos alimentares individualizados, preferência por frutas inteiras, controle de bebidas açucaradas e consistência de carboidratos para doses fixas de insulina: https://doi.org/10.2337/dc26-S005
  - National Institute of Diabetes and Digestive and Kidney Diseases (NIDDK). *Eating, Diet, & Nutrition for Constipation* — fibras, hidratação e adequação individual: https://www.niddk.nih.gov/health-information/digestive-diseases/constipation/eating-diet-nutrition
- **Decisões adotadas:**
  - Não inserir proporções universais de pó/água/suco. O volume e o tipo de diluente dependem do produto, da apresentação, do rótulo, da ficha técnica e da prescrição. A tela ensina o fluxo (medir, dosar, homogeneizar e conferir volume final), sem números inventados.
  - Exibir três escalas por 100 g: fibra alimentar em ordem decrescente; potássio e carboidrato disponível em ordem crescente. O gráfico é comparativo e não define alimento proibido/livre.
  - A escala de fibra é um indicador de conteúdo, não um índice de efeito laxativo. A interface não classifica as nove frutas como constipantes, pois essa categorização universal não é sustentada apenas pela composição. A maturação da banana, casca, forma de preparo, porção e tolerância devem ser consideradas.
  - Para diabetes, reforçar fruta inteira, ausência de açúcar adicionado e respeito à porção e distribuição de carboidratos individualizadas; não classificar frutas como proibidas.
  - Para doença renal, potássio por 100 g não substitui avaliação do potássio sérico, função renal, porção, medicamentos e plano individual.
- **Limitações:** valores de TBCA são referências de alimentos/variedades selecionados, não substituem análise do lote servido. As medidas mudam com variedade, maturação, casca e preparo. Os valores publicados são apresentados apenas como comparações por 100 g com atribuição à TBCA/USP. Conteúdo e doses locais precisam ser revisados pela Nutrição e pela equipe responsável antes de uso assistencial.
- **Arquivos/testes:** `mobile/servidor.py`, `mobile/static/index.html`, `mobile/static/diluicao.svg`, `mobile/static/frutas.svg`, `tests/test_mobile.py`, documentação mobile e roadmap. A alteração cria a tabela `orientacoes`, com quatro textos iniciais; GET para perfis autenticados; escrita somente pelo administrador; serviço de estáticos sob `/static/`.
- **Estado:** implementação técnica proposta; pendente de CI completo e homologação no aparelho/servidor local.
