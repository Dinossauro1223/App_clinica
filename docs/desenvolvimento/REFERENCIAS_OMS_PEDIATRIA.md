# Referências antropométricas pediátricas — OMS

## Escopo extraído do PDF enviado

O documento contém curvas por sexo para:
- IMC por idade: nascimento–5 anos e 5–19 anos;
- peso por idade: nascimento–5 anos e 5–10 anos;
- estatura/comprimento por idade: nascimento–5 anos e 5–19 anos.

As páginas 1–10 apresentam as curvas OMS 2006/2007 em escore-z. As páginas 11–12 apresentam IMC por idade de meninas e meninos de 0 a 5 anos.

## Referências e faixas de uso

- OMS 2006 (WHO Anthro 1.1.0): idade inferior a 60 meses, usando idade exata em dias.
- OMS 2007 (WHO AnthroPlus 1.1.0): a partir de 60 meses; IMC/idade e estatura/idade até antes de 229 meses; peso/idade até antes de 121 meses.
- IMC/idade: 0–19 anos.
- Estatura/idade: 0–19 anos.
- Peso/idade: 0–10 anos; não disponibilizar a partir de 121 meses completos.
- As linhas de 229 meses (IMC/estatura) e 121 meses (peso) são âncoras técnicas para interpolar idades decimais abaixo do limite; não são pontos clínicos nem autorizam extrapolação.

Fontes oficiais:
- https://www.who.int/tools/child-growth-standards
- https://www.who.int/toolkits/growth-reference-data-for-5to19-years
- https://www.who.int/tools/growth-reference-data-for-5to19-years/indicators/bmi-for-age
- https://www.who.int/tools/growth-reference-data-for-5to19-years/indicators/height-for-age
- https://www.who.int/tools/growth-reference-data-for-5to19-years/indicators/weight-for-age-5to10-years
- https://github.com/WorldHealthOrganization/anthro
- https://github.com/WorldHealthOrganization/anthroplus
- https://cran.r-project.org/package=anthro
- https://cran.r-project.org/package=anthroplus

## Classificação

Os pontos de corte estruturados estão em `dados/oms_classificacoes_pediatricas.json`. A classificação de IMC/idade muda entre menores de 5 anos e 5–19 anos. Peso/idade não deve ser usado para diagnosticar excesso de peso; para isso, usar IMC/idade. Estatura/idade avalia crescimento linear.

## Tabelas LMS versionadas e proveniência

Os parâmetros LMS estão versionados em `dados/oms_lms_pediatricos.csv`. O arquivo foi extraído das tabelas de referência distribuídas pelos pacotes mantidos pela Organização Mundial da Saúde:

- WHO `anthro` 1.1.0 — padrões OMS 2006; repositório [WorldHealthOrganization/anthro](https://github.com/WorldHealthOrganization/anthro).
- WHO `anthroplus` 1.1.0 — referência OMS 2007; repositório [WorldHealthOrganization/anthroplus](https://github.com/WorldHealthOrganization/anthroplus).

A licença dos pacotes de origem é GPL-3. O CSV mantém os parâmetros L, M e S originais, por sexo e idade, sem digitalizar curvas nem fabricar valores. A cobertura presente no arquivo é:

- OMS 2006: 0–1826 dias para IMC/idade, peso/idade e comprimento/estatura/idade.
- OMS 2007: 60–229 meses como faixa de dados de interpolação para IMC/idade e estatura/idade.
- OMS 2007: 60–121 meses como faixa de dados de interpolação para peso/idade.

Os limites superiores 229 e 121 são apenas âncoras técnicas: a avaliação clínica permanece limitada a menos de 229 meses para IMC/estatura e menos de 121 meses para peso. O motor não extrapola além dessas âncoras. Para OMS 2006, usa idade exata em dias e não calcula quando a data de nascimento ou o parâmetro correspondente estiver ausente.

O arquivo `dados/oms_classificacoes_pediatricas.json` contém os metadados e pontos de corte de classificação; ele não substitui as tabelas LMS. Se uma combinação de sexo, indicador ou idade não existir na tabela, o resultado deve permanecer pendente. Nunca estimar ou inventar parâmetros.

## Regras para persistência e gráficos

Cada aferição deve ser preservada como evento histórico, sem sobrescrever a anterior, contendo no mínimo:
- paciente e leito vinculados;
- data/hora da aferição;
- data de nascimento ou idade exata em meses completos na data da aferição;
- sexo utilizado para selecionar a referência;
- peso (kg), comprimento/estatura (cm), IMC (kg/m²);
- origem da medida (aferida ou estimada) e método, quando aplicável;
- indicador, escore-z, classificação, referência/versão e avisos;
- registro dos dados de entrada que produziram o resultado.

Os gráficos individuais devem usar idade em meses no eixo X, valor antropométrico no eixo Y, curva de referência apropriada por sexo/idade e pontos históricos aferidos. Distinguir visualmente medidas aferidas e estimadas.

## Integração no NutriLab

A interface de edição do leito já reúne NRS-2002 e avaliação nutricional em `mapa_ui.py`; a avaliação pediátrica deve ser incorporada nesse formulário, sem criar uma aba de consulta independente. A persistência atual de `Mapa_Registros` guarda dados do registro diário, mas a série histórica de antropometria deve ter tabela própria para permitir várias aferições no mesmo dia e preservar a evolução clínica.

A NRS-2002 não deve ser considerada substituta da avaliação pediátrica por crescimento. A escolha de uma ferramenta específica de triagem de risco nutricional pediátrico deve ser validada separadamente com protocolo institucional.

## Validação antes de ativar cálculos

- Conferir os dados oficiais com a documentação OMS/Anthro/AnthroPlus.
- Testar os limites de idade (60/61 meses, 120/121 meses e 228/229 meses).
- Testar ambos os sexos, limites de classificação e valores ausentes.
- Verificar a continuidade das referências aos 5 anos.
- Não aplicar peso/idade acima de 120 meses.
- Testar cálculos LMS e classificação com casos de referência publicados.
