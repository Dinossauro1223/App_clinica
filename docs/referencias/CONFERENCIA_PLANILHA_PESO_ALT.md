# Conferência da planilha do setor (aba `Peso-Alt`) × catálogo de referência do projeto

- **Data:** 2026-11-11 (America/Recife) · **Fase 2** (pré-trabalho independente do código) · **Branch:** `feat/fase-2-conferencia-equacoes-planilha`
- **Planilha conferida:** `CÁLCULOS ESTIMATIVA DE PESO E ESTATURA.xlsx`, aba `Peso-Alt`. É um arquivo operacional do setor e **não é versionado** (o `.gitignore` e a auditoria o bloqueiam).
- **Método:** `tools/conferir_equacoes_planilha.py` lê somente rótulos e **fórmulas** da aba e compara os coeficientes com as tabelas do relatório do projeto (`RELATORIO_FORMULAS_E_ESTIMATIVAS.txt`, seções 4 e 5). Nenhum valor de entrada e nenhuma outra aba foram lidos.
- **Resultado:** 25 de 26 itens iguais à referência; **1 divergente** (estatura de meninas brancas de 6 a 18 anos).

## Resultado item a item

Colunas: *na planilha* e *na referência* (peso em kg = a·AJ + b·PB − c; estatura em cm; AJ = altura do joelho, PB = perímetro do braço, em cm).

| Tipo | Grupo | Célula | Na planilha | Na referência | Estado |
|---|---|---|---|---|---|
| peso | 6-18 F branca | B10 | 0.77·AJ + 2.47·PB − 50.16 | 0.77·AJ + 2.47·PB − 50.16 | OK |
| estatura | 6-18 F branca | F10 | 43.21 + 2.14·AJ | 43.21 + 2.15·AJ | DIVERGENTE |
| peso | 6-18 F negra | B11 | 0.71·AJ + 2.59·PB − 50.43 | 0.71·AJ + 2.59·PB − 50.43 | OK |
| estatura | 6-18 F negra | F11 | 46.59 + 2.02·AJ | 46.59 + 2.02·AJ | OK |
| peso | 6-18 M branca | B13 | 0.68·AJ + 2.64·PB − 50.08 | 0.68·AJ + 2.64·PB − 50.08 | OK |
| estatura | 6-18 M branca | F13 | 40.54 + 2.22·AJ | 40.54 + 2.22·AJ | OK |
| peso | 6-18 M negra | B14 | 0.59·AJ + 2.73·PB − 48.32 | 0.59·AJ + 2.73·PB − 48.32 | OK |
| estatura | 6-18 M negra | F14 | 39.6 + 2.18·AJ | 39.6 + 2.18·AJ | OK |
| peso | 19-59 F branca | B20 | 1.01·AJ + 2.81·PB − 66.04 | 1.01·AJ + 2.81·PB − 66.04 | OK |
| estatura | 19-59 F branca | F20 | 70.25 + 1.87·AJ − 0.06·idade | 70.25 + 1.87·AJ − 0.06·idade | OK |
| peso | 19-59 F negra | B21 | 1.24·AJ + 2.97·PB − 82.48 | 1.24·AJ + 2.97·PB − 82.48 | OK |
| estatura | 19-59 F negra | F21 | 68.1 + 1.86·AJ − 0.06·idade | 68.1 + 1.86·AJ − 0.06·idade | OK |
| peso | 19-59 M branca | B23 | 1.19·AJ + 3.21·PB − 86.82 | 1.19·AJ + 3.21·PB − 86.82 | OK |
| estatura | 19-59 M branca | F23 | 71.85 + 1.88·AJ | 71.85 + 1.88·AJ | OK |
| peso | 19-59 M negra | B24 | 1.09·AJ + 3.14·PB − 83.72 | 1.09·AJ + 3.14·PB − 83.72 | OK |
| estatura | 19-59 M negra | F24 | 73.42 + 1.79·AJ | 73.42 + 1.79·AJ | OK |
| peso | 60-80 F branca | B30 | 1.09·AJ + 2.68·PB − 65.51 | 1.09·AJ + 2.68·PB − 65.51 | OK |
| estatura | 60-80 F branca | F30 | 75 + 1.91·AJ − 0.17·idade | 75 + 1.91·AJ − 0.17·idade | OK |
| peso | 60-80 F negra | B31 | 1.5·AJ + 2.58·PB − 84.22 | 1.5·AJ + 2.58·PB − 84.22 | OK |
| estatura | 60-80 F negra | F31 | 58.72 + 1.96·AJ | 58.72 + 1.96·AJ | OK |
| peso | 60-80 M branca | B33 | 1.1·AJ + 3.07·PB − 75.81 | 1.1·AJ + 3.07·PB − 75.81 | OK |
| estatura | 60-80 M branca | F33 | 59.01 + 2.08·AJ | 59.01 + 2.08·AJ | OK |
| peso | 60-80 M negra | B34 | 0.44·AJ + 2.86·PB − 39.21 | 0.44·AJ + 2.86·PB − 39.21 | OK |
| estatura | 60-80 M negra | F34 | 95.79 + 1.37·AJ | 95.79 + 1.37·AJ | OK |
| amputado | M | B45 | AJ = (Alt − 64.19 + 0.04·idade) / 2.02 | AJ = (Alt − 64.19 + 0.04·idade) / 2.02 | OK |
| amputado | F | C45 | AJ = (Alt − 84.88 + 0.24·idade) / 1.83 | AJ = (Alt − 84.88 + 0.24·idade) / 1.83 | OK |

## Divergência encontrada

Meninas brancas, 6 a 18 anos, estatura por altura do joelho (Chumlea, Guo e Steinbaugh, 1994):
a planilha (célula `F10`) usa **2,14**·AJ; o relatório do projeto e as cinco fontes secundárias consultadas usam **2,15**·AJ
(intercepto 43,21 em todas). A diferença é de 0,01 × AJ: para AJ entre 35 e 55 cm, a planilha subestima a estatura em
0,35 a 0,55 cm. Detalhes, fontes e decisão: `REF-2026-11-11-001` no diário bibliográfico.

## O que a planilha revela sobre a prática do setor

| Faixa | Estatura | Peso |
|---|---|---|
| 6 a 18 anos | Chumlea et al. (1994), AJ, sexo e cor | Chumlea (AJ + PB), sexo e cor |
| 19 a 59 anos | Chumlea et al. (1994), AJ, sexo e cor (idade só nas mulheres) | Chumlea (AJ + PB), sexo e cor |
| 60 a 80 anos | **Chumlea e Guo (1992)**, sexo e cor | Chumlea (AJ + PB), sexo e cor |
| Amputado | AJ obtida pela inversão de Chumlea, Roche e Steinbaugh (**1985**), sem cor | — |

Observações: a planilha **não cobre** menores de 6 nem maiores de 80 anos; e usa duas equações de estatura diferentes para
idosos (1992 na estimativa por cor; 1985 no bloco de amputados). O relatório (seção 4.6) sugere 1985 como padrão para
60 anos ou mais; a decisão adotada para o programa está em `REF-2026-11-11-002`.

## Como repetir a conferência

```bat
python tools\conferir_equacoes_planilha.py "C:\caminho\CÁLCULOS ESTIMATIVA DE PESO E ESTATURA.xlsx"
```

Código de saída 0 = tudo igual; 1 = divergência, fórmula em formato não previsto ou layout alterado; 2 = erro de uso.
Se alguém mudar a estrutura da aba, o conferidor acusa `LAYOUT` em vez de comparar às cegas.

## Limites desta conferência

- Compara a **planilha com o relatório**; não substitui a leitura do artigo original (ver estados no diário).
- Não conferiu `nutri_calculos.py`: o código do aplicativo não estava acessível. Pendência registrada no diário.
- Não avalia a *adequação clínica* das equações (população, idade, validação brasileira); isso está no relatório e nas entradas do diário.
