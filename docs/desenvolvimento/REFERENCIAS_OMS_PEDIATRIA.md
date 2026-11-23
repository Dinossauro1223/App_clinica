# Referências antropométricas pediátricas — OMS

## Escopo extraído do PDF enviado

O documento contém curvas por sexo para:
- IMC por idade: nascimento–5 anos e 5–19 anos;
- peso por idade: nascimento–5 anos e 5–10 anos;
- estatura/comprimento por idade: nascimento–5 anos e 5–19 anos.

As páginas 1–10 apresentam as curvas OMS 2006/2007 em escore-z. As páginas 11–12 apresentam IMC por idade de meninas e meninos de 0 a 5 anos.

## Referências e faixas de uso

- OMS 2006: padrões de crescimento de 0 a 60 meses.
- OMS 2007: referência de 61 a 228 meses.
- IMC/idade: 0–19 anos.
- Estatura/idade: 0–19 anos.
- Peso/idade: 0–10 anos; não disponibilizar após 10 anos.

Fontes oficiais:
- https://www.who.int/tools/child-growth-standards
- https://www.who.int/toolkits/growth-reference-data-for-5to19-years
- https://www.who.int/tools/growth-reference-data-for-5to19-years/indicators/bmi-for-age
- https://www.who.int/tools/growth-reference-data-for-5to19-years/indicators/height-for-age
- https://www.who.int/tools/growth-reference-data-for-5to19-years/indicators/weight-for-age-5to10-years

## Classificação

Os pontos de corte estruturados estão em `dados/oms_classificacoes_pediatricas.json`. A classificação de IMC/idade muda entre menores de 5 anos e 5–19 anos. Peso/idade não deve ser usado para diagnosticar excesso de peso; para isso, usar IMC/idade. Estatura/idade avalia crescimento linear.

## Pendência crítica: tabelas numéricas

O PDF contém gráficos, não as tabelas LMS completas. Não digitalizar visualmente os traçados como se fossem valores exatos. Para cálculo reproduzível dos escores-z e desenho correto das curvas, obter e versionar as tabelas numéricas oficiais por indicador, sexo e idade, incluindo os parâmetros L, M e S (ou as tabelas oficiais de valores por escore-z quando a referência não disponibilizar LMS).

O arquivo JSON atual contém metadados, cobertura e regras de classificação; **não contém valores antropométricos LMS**. O módulo deve manter a classificação como indisponível/pendente enquanto faltar a tabela aplicável. Nunca estimar ou inventar parâmetros.

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
