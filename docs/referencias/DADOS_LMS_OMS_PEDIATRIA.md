# Dados LMS pediátricos OMS

## Origem e versão

O arquivo `dados/oms_lms_pediatricos.csv` contém parâmetros L, M e S extraídos das tabelas de referência distribuídas pelos pacotes R `anthro` 1.1.0 e `anthroplus` 1.1.0. Os metadados dos dois pacotes identificam a Organização Mundial da Saúde como detentora dos direitos autorais e apontam para os repositórios oficiais:

- [WHO anthro — Child Growth Standards](https://github.com/WorldHealthOrganization/anthro) — referência OMS 2006, 0–5 anos.
- [WHO anthroplus — Growth Reference 5–19 years](https://github.com/WorldHealthOrganization/anthroplus) — referência OMS 2007, 5–19 anos.
- [WHO Child Growth Standards](https://www.who.int/tools/child-growth-standards).
- [WHO Growth reference data for 5–19 years](https://www.who.int/tools/growth-reference-data-for-5to19-years).

Os arquivos de origem foram obtidos dos pacotes CRAN 1.1.0; o código-fonte declara os repositórios oficiais acima e a OMS como titular dos direitos autorais. O CSV do aplicativo é uma conversão dos parâmetros tabulados, não uma aproximação ou reconstrução estatística.

## Conteúdo incluído

| Referência | Indicador | Cobertura incluída |
|---|---|---|
| OMS 2006 | IMC/idade | 0–1826 dias, ambos os sexos |
| OMS 2006 | Peso/idade | 0–1826 dias, ambos os sexos |
| OMS 2006 | Comprimento/estatura por idade | 0–1826 dias, ambos os sexos |
| OMS 2007 | IMC/idade | 61–228 meses, ambos os sexos |
| OMS 2007 | Estatura/idade | 61–228 meses, ambos os sexos |
| OMS 2007 | Peso/idade | 61–120 meses, ambos os sexos |

Os limites são deliberados: peso/idade não é fornecido como indicador OMS 2007 depois de 10 anos. A seleção da referência no código mantém OMS 2006 até 60 meses completos e OMS 2007 a partir de 61 meses.

## Estrutura do CSV

Campos: `indicador`, `referencia`, `sexo`, `idade_dias`, `idade_meses`, `L`, `M`, `S`, `medida`.

- Sexo de origem 1 é armazenado como H (masculino); sexo 2 como M (feminino).
- OMS 2006 usa idade em dias; OMS 2007 usa idade em meses.
- Para comprimento/estatura OMS 2006, `medida` preserva L (comprimento deitado) ou H (estatura em pé) conforme a tabela de origem.
- Campos de idade da unidade não utilizada ficam vazios.

## Reprodução

O script temporário `tools/exportar_oms_lms.R` documenta a conversão feita no CI a partir dos objetos de dados dos pacotes. O aplicativo Python usa diretamente o CSV e não depende de R em tempo de execução.

Os parâmetros são usados apenas dentro da cobertura oficial. O sistema não extrapola idades, não sintetiza valores LMS e mantém resultado pendente quando faltar medida, sexo, data de nascimento necessária ou parâmetro aplicável.