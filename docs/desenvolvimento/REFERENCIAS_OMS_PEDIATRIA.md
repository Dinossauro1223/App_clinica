# Referências antropométricas pediátricas — OMS

## Indicadores implementados

- IMC por idade: OMS 2006 e OMS 2007, até 228 meses completos.
- Peso por idade: OMS 2006 e OMS 2007, até 120 meses completos (10 anos). Não usar peso/idade para classificar excesso de peso.
- Comprimento/estatura por idade: OMS 2006 e OMS 2007, até 228 meses completos.

## Referências e fronteiras

- OMS 2006: WHO Child Growth Standards, tabelas diárias de 0 a 1826 dias.
- OMS 2007: WHO Growth Reference 5–19 years, tabelas mensais. A seleção do algoritmo AnthroPlus começa em 60 meses completos; os limites clínicos superiores são 228 meses para IMC/estatura e 120 meses para peso.
- Os registros de 229 meses (IMC/estatura) e 121 meses (peso) são âncoras técnicas para interpolar idades decimais abaixo do limite superior exclusivo; não autorizam classificar pacientes nessas idades.

Fontes:
- [WHO Child Growth Standards](https://www.who.int/tools/child-growth-standards)
- [WHO Growth Reference 5–19 years](https://www.who.int/toolkits/growth-reference-data-for-5to19-years)
- [WHO anthro](https://github.com/WorldHealthOrganization/anthro)
- [WHO anthroplus](https://github.com/WorldHealthOrganization/anthroplus)

## Dados e classificação

- Os parâmetros L, M e S estão em dados/oms_lms_pediatricos.csv, derivados dos pacotes WHO anthro 1.1.0 e anthroplus 1.1.0.
- Os pontos de corte e rótulos de classificação estão em dados/oms_classificacoes_pediatricas.json. O módulo carrega esse arquivo para selecionar as faixas e aplicar as regras por referência.
- O CSV guarda sexo, referência, indicador, idade em dias ou meses, L, M, S e, para comprimento/estatura, o tipo de medida da tabela original.
- OMS 2006 usa idade exata em dias. OMS 2007 usa idade decimal em meses e interpolação linear de L, M e S. A referência e a classe são selecionadas com meses completos.
- Nenhum valor LMS é estimado. Ausência de data de nascimento para menores de 5 anos, sexo, medida ou parâmetro aplicável resulta em avaliação pendente.

## Interpretação clínica

- IMC/idade é o indicador para classificação de magreza, eutrofia, risco de sobrepeso, sobrepeso e obesidade, com pontos de corte diferentes entre OMS 2006 e OMS 2007.
- Peso/idade avalia baixo peso; não diagnostica sobrepeso ou obesidade e não tem referência OMS depois de 10 anos.
- Estatura/idade avalia crescimento linear; valores muito elevados exigem interpretação no contexto clínico.
- Para menores de 24 meses, medir comprimento deitado. A partir de 24 meses, medir estatura em pé. A medida deve seguir o protocolo da referência.
- Valores extremos além de ±3 DP seguem o método OMS específico; não se deve extrapolar a fórmula LMS convencional.

## Integração no prontuário

A avaliação pediátrica está incorporada ao formulário de registro do leito, junto aos demais dados antropométricos. Usa data de nascimento do cadastro do paciente, sexo, peso e comprimento/estatura, calcula IMC e apresenta escores-z e classificações. Os resultados são persistidos em pediatria_oms_json, aparecem no histórico e alimentam a classificação exibida no mapa. O botão Curvas OMS abre os gráficos por sexo com a medida do paciente sobreposta.

Cada registro guarda um snapshot com data de avaliação, data de nascimento, idade em dias/meses, sexo, medidas, IMC, resultados por indicador e versão/fonte das referências. A aferição anterior não é sobrescrita por um novo registro.

## Limitações e segurança

- Sem data de nascimento, o cálculo OMS 2006 de menores de 5 anos fica pendente; idade aproximada em anos/meses não substitui idade exata em dias.
- Fora da cobertura de cada indicador, o sistema informa que não é aplicável e não extrapola.
- Testes com valores sintéticos validam apenas a matemática e a integração; não são dados clínicos nem validação de curvas.
- A triagem nutricional pediátrica deve ser interpretada por profissional habilitado e não substitui avaliação clínica.