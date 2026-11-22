# Inventário dos arquivos reais de referência — NutriLab

Este inventário descreve a estrutura dos materiais enviados para orientar a digitalização. Não reproduz registros pessoais, nomes de pacientes, valores individuais de refeições, custos específicos ou dados de estoque. Os arquivos originais devem permanecer fora do Git quando contiverem informações reais.

## 1. Mapa externo — `Mapa_externo_novo_layout.xlsx`

- 17 abas: 16 abas diárias de outubro e uma aba `IMC`.
- Abas diárias observadas: `0410`, `0510`, `0610`, `0710`, `0810`, `1010`, `11.10`, `1310`, `1410`, `1710`, `1810`, `1910`, `2310`, `2410`, `2710`, `2810`.
- Cabeçalho: `LEITO`, `AC`, `NOME`, `IDADE`, `AV/ REAV.`, `TIPO DE DIETA`, `CARACTERÍSTICA`, `SUPLEMENTO`, `OBSERVAÇÕES`, `DIAGNÓSTICO`.
- Tipos/categorias de dieta: LV, BR, PAS, L-P e LÍQ.
- Características: DM, HAS, LAX, CON e DRC.
- Cada aba diária oferece linhas por leito; a quantidade de linhas do modelo não deve ser fixada como limite técnico do software.
- A aba `IMC` é uma folha de referência do arquivo, não a fonte oficial de curvas infantis.

**Implicação de desenvolvimento:** suportar mapa por hospital/unidade/setor/leito, registro por data, cópia do dia anterior, histórico de paciente, reavaliação, exportação e dados clínicos com acesso restrito. Verificar se diagnóstico pertence ao mapa diário ou apenas ao PEP; caso presente, protegê-lo por permissão.

## 2. Controle semanal de refeições de pacientes — `CONTROLE DE REFEIÇÕES - Outubro 2026.xlsx`

- Abas encontradas: `01-07`, `08-14`, `15-21`, `Sheet 1`, `29-31`.
- Seis refeições por dia: Desjejum, Lanche manhã, Almoço, Lanche tarde, Jantar e Ceia.
- A estrutura é uma grade de paciente/linhas versus refeições e datas.
- A leitura dos cabeçalhos mostra três blocos de data visíveis por aba; não presumir que cada aba contém sete dias completos.
- A aba chamada `15-21` apresenta datas 15–17/09/2026, embora o arquivo seja de outubro de 2026.
- A aba `Sheet 1` apresenta os dias 22–24/10/2026.
- Há lacunas no conjunto fornecido; isso não significa consumo zero.

**Implicação de desenvolvimento:** usar data armazenada no registro, não nome da aba. Importador precisa detectar data fora do mês, datas duplicadas, dias ausentes e células vazias; gerar relatório e pré-visualização antes de importar.

## 3. Controle de fichas de almoço/jantar — `CONTROLE DE FICHAS ALMOÇO E JANTAR - OUTBRO 2026.xlsx`

- Abas: `ALMOÇO` e `JANTAR`.
- Cada aba apresenta colunas diárias do dia 1 ao 31.
- Linhas de especificação agregadas por setor/serviço, incluindo Agência Transfusional, Ambulatório, Assistência Social, Clínicas, Esterilização, Extra, Farmácia, Laboratório, Lavanderia, Manutenção, Maqueiros, Médicos, Motorista, NIR, Pediatria, Porteiro, Raio-X, Recepção, Registro, SAMU, SAU, Servente/Limpeza, Nutrição, UPA e CAPS.
- A planilha contém totais de fichas entregues, fichas recebidas, refeição sem ficha e total.

**Implicação de desenvolvimento:** manter contagem separada por setor, dia e tipo de refeição; não confundir ficha emitida/recebida com confirmação individual de consumo. O portal móvel solicitado deve registrar o servidor autenticado e depois agregar por setor.

## 4. Controle mensal do estoque — `Controle da Nutrição - Outubro 2026.xlsx`

- Uma aba principal, com 139 linhas de itens (cadastro de insumos/gêneros).
- Colunas iniciais: nome do item, unidade e valor.
- Para cada dia de outubro, aparecem campos de Entrada e Saída.
- O mês está organizado em cinco blocos de período, cada um com resumo: Entrada semanal, Uso semanal, Gasto semanal e Saldo semanal.
- As unidades aparecem com variações de escrita/abreviação (por exemplo, KG/Kg, PAC/PCT, UND/UN, LT/LATA).

**Implicação de desenvolvimento:** criar catálogo normalizado, movimentos de estoque, custo, saldo calculado e resumos por semana/mês. A normalização exige equivalência conhecida, não simples substituição textual. Uma célula vazia não pode ser tratada como zero sem regra de importação.

## 5. Planilha de cálculos — `CÁLCULOS ESTIMATIVA DE PESO E ESTATURA.xlsx`

### Abas relevantes

- `Peso-Alt`: estimativa de peso e estatura por idade, sexo e cor, com referências de Chumlea; há bloco para amputados.
- `Calc dieta PSL PTN`: fórmulas enterais e matriz de kcal/proteína por 1–21 medidas.
- `Calc dieta Isolate PTN`: fórmulas com matriz de kcal/proteína por medida.
- `Calc dieta Fres. PTN`: matriz de produtos para cálculo de kcal/proteína e uso de Fresubin Protein.
- `Oferta`: agrega vazão, tempo de infusão, volume, densidade calórica, módulo e total de kcal/proteína; há campo separado de contribuição do propofol.
- `Nora`: cálculos de noradrenalina; não pertence ao escopo de Nutrição Clínica e não deve ser migrada para os módulos de suplementação/terapia nutricional.

### Denominações de produtos que aparecem nas abas de dieta

- Diason 1.0; Diason E. HP; Diason Energy HP.
- Diben 1.5 (SF); Diben 1,5 (SF).
- Fresubin HP Energy; Fresubin 2 kcal HP; Fresubin Original Fb; Fresubin Original Fibre.
- Isosource 1.5; Isosource Soya.
- Novasource GC; Novasource HP; Nov. Proline (SF); Novasource Proline (SF); Nov. Senior (SA); Nov. Senior (SF); Novasource Senior.
- Nutri Enteral 1.2; Nutri Enteral Soya; Nutri R 2.0; Nutro Premium PF 1.5.
- Nutrison 1.0; Nutrison PP Energy; Nutrison Protein Plus Energy.
- Peptamen HN; Peptamen Intense; Peptisorb; Survimed; Trophic Basic.

As denominações são mantidas como estão escritas. Podem existir produtos/variantes semelhantes, mas não devem ser consolidados sem rótulo/ficha técnica correspondente. As planilhas demonstram matrizes de cálculo, mas não são, por si só, fonte suficiente de todos os valores de composição.

## 6. Relatório de fórmulas antropométricas — `docs/referencias/RELATORIO_FORMULAS_E_ESTIMATIVAS.txt`

Relatório de 25/10/2026 com 13 seções e levantamento de equações para estatura, peso, IMC, composição corporal, massa muscular, gasto energético, necessidade nutricional e índices de risco. Cada entrada procura registrar autor, ano, população e limitações, com rótulos `[verificada]` e `[conferir]`.

Pontos centrais para o software:

- Chumlea utiliza AJ + PB para estimativa de peso em faixas etárias e grupos definidos.
- Estatura por AJ tem faixas e coeficientes distintos por sexo/idade; as equações em idosos têm alertas de aplicabilidade.
- PP não entra nas equações de peso/estatura do Mapa que usam AJ + PB, embora possa ser marcador antropométrico.
- O relatório não encontrou fórmula validada de densidade/massa muscular a partir do perímetro do punho; o punho fica fora do escopo atual.
- IMC adulto, IMC idoso e LMS infantil têm classificações diferentes.
- O relatório inclui cálculos de oferta de suplementos/terapia enteral, com valores por 100 mL/g, aporte, custo, percentuais de VET e proteína/kg.

A referência completa deve ser consultada no próprio relatório; novas dúvidas devem gerar entrada no Diário Bibliográfico.

## 7. Modelo de Evolução Nutricional — `Evolucao_nutricional_pacientes.pdf`

O PDF organiza cada paciente em colunas de paciente, evolução e antropometria. A evolução registra via, consistência, características nutricionais, função intestinal, suplementação, observações e conduta. A antropometria registra data, AJ, PB, PP, altura/peso estimados ou aferidos e IMC/classificação.

Nas páginas 5 e 6 há perguntas para anamnese (alergia, intolerância, mastigação, aversões), frases-modelo de observação e exemplos de descrição de suplemento. As frases/doses são exemplos de escrita clínica, não modelos para prescrever automaticamente.

O modelo PEP mais detalhado solicitado pelo usuário acrescenta admissão/evolução, metas energéticas/proteicas, DVA, AHGT, função intestinal 24h, fezes diarreicas, aceitação VO, tolerância TNE, vazão, meta atingida, conduta mantida/nova e assinatura eletrônica.

## 8. Referências visuais

1. **Escala de Bristol:** ilustração com tipos 1 a 7, do muito endurecido ao totalmente líquido. Digitalizar como classificação estruturada da função intestinal e oferecer “não observado/não informado”.
2. **Aceitação da dieta oral:** ilustração com 0%, 25%, 50%, 75% e 100% de consumo. Usar como escala por refeição; o registro deve indicar data, refeição e responsável.

## 9. TBCA 2024 e fichas técnicas

A pasta de trabalho `TBCA 2024` contém três abas diretamente relevantes ao desenvolvimento de fichas:

- `TBCA (2024)`: base tabular de alimentos e composição nutricional, com ID, tipo, NPU, fatores de correção, medida caseira, per capita e nutrientes. Foi usada como origem do importador TBCA do módulo Gestão alimentar.
- `Construção da ficha`: folha para montar uma preparação, com porções, ingredientes, escolha do alimento TBCA, quantidades, correção, medidas caseiras, NPU/NDPcal e referências de estoque/preço. Há fórmulas especiais do Google Sheets/`DUMMYFUNCTION`, que não são executadas automaticamente pelo desktop.
- `Fichas Técnicas`: apresenta seis blocos de preparação (salada, acompanhamento, prato principal, guarnição, sobremesa e suco), com colunas de ingredientes, per capita, FC, peso bruto, medida caseira e custo. As preparações têm fórmulas e valores em cache que incluem zeros/`None`, e nem toda linha deixa explícito se a quantidade é g ou ml.

**Implicação de desenvolvimento:** importar a base TBCA por ID é seguro e repetível; as seis fichas existentes precisam de importador assistido, pré-visualização e revisão da unidade por ingrediente. Não copiar resultados de fórmulas externas sem reimplementação e teste. NPU pode ser mantido como dado de origem, mas NDPcal não deve ser calculado até que a fórmula institucional seja validada.

## 10. Regras de uso dos arquivos-fonte

- Guardar este inventário, não as planilhas originais, no repositório.
- Para testes, construir arquivos sintéticos com a mesma estrutura, sem dados pessoais ou valores internos reais.
- Para importação, sempre mostrar pré-visualização, relatório de erro e confirmação do operador autorizado.
- Não interpretar branco como zero, não ajustar datas silenciosamente e não fundir categorias sem guardar o mapeamento.
- Atualizar este inventário quando novo modelo ou planilha for fornecido.
