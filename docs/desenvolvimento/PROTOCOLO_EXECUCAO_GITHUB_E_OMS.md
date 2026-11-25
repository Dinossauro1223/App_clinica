# Protocolo de trabalho no GitHub — Projeto Clínica

Este documento registra o procedimento obrigatório para alterações no repositório. Deve ser seguido em qualquer branch, PR ou continuação de trabalho.

## 1. Inspeção antes de alterar

1. Confirmar repositório, branch, base (main) e SHA atual.
2. Comparar a branch com a main e revisar todos os commits e arquivos alterados.
3. Identificar se há PR existente para a mesma funcionalidade; não criar PR duplicado nem confundir branches com nomes semelhantes.
4. Antes de integrar branch antiga, preservar suas alterações úteis e reconciliá-las com a versão atual da main. Não fazer merge cego de branch muito defasada.

## 2. Ciclo obrigatório de correção e testes

1. Corrigir a causa do problema, não apenas o sintoma.
2. Executar testes específicos da alteração e a suíte integral aplicável.
3. Acompanhar os workflows do GitHub até todos os jobs terminarem. Estado queued ou in_progress não é aprovação.
4. Se qualquer teste, build, auditoria ou smoke test falhar:
   - ler o log completo e identificar a causa;
   - corrigir o código ou a configuração;
   - criar commit corretivo;
   - aguardar uma nova execução integral;
   - repetir o ciclo até a aprovação.
5. Não desabilitar testes, remover asserts ou reduzir cobertura apenas para obter CI verde. Um teste só pode ser atualizado quando estiver comprovadamente obsoleto em relação ao comportamento vigente; documentar a razão e manter uma asserção equivalente ou mais adequada.
6. Não declarar sucesso com base em testes locais, em apenas um sistema operacional ou em jobs ainda em execução.

## 3. Critérios antes do merge

O merge só pode ser feito quando:
- todos os checks obrigatórios do PR estiverem concluídos e aprovados;
- testes Windows e Linux estiverem verdes;
- compilação e smoke tests das plataformas aplicáveis estiverem verdes;
- auditoria de segurança/privacidade estiver aprovada;
- alterações e conflitos com a main estiverem revisados;
- o diff não contiver arquivos temporários, dados reais de pacientes, segredos ou artefatos de teste.

Depois do merge, confirmar o SHA resultante na main e verificar se o estado final do repositório está correto. Não afirmar que houve merge sem confirmação da API do GitHub.

## 4. Registro e comunicação

Manter registro de PR, branch, commits e SHAs corretivos, testes executados, identificadores dos workflows e conclusões dos jobs, falhas e correções, confirmação de merge ou motivo objetivo da pendência.

Se o trabalho não puder ser concluído na sessão, informar claramente o estado real e o próximo passo. Nunca sugerir que existe monitoramento em segundo plano após o fim da sessão.

## 5. Requisitos de dados clínicos e curvas OMS pediátricas

- Utilizar exclusivamente parâmetros LMS oficiais e versionados para cada referência, sexo, indicador e faixa etária.
- Não gerar, inferir ou preencher valores LMS ausentes com números sintéticos.
- Distinguir OMS 2006 (padrões de 0–5 anos) da referência OMS 2007 (5–19 anos), respeitando limites e transições de cada indicador.
- Calcular idade com a precisão exigida pela referência (dias quando aplicável; meses completos/decimais quando aplicável), sem extrapolar fora da cobertura.
- Aplicar o método OMS específico para caudas além de ±3 DP quando pertinente.
- Restringir peso/idade à faixa etária reconhecida pela OMS (até 10 anos na referência 5–19); não exibir esse indicador como avaliação válida de adolescentes mais velhos.
- A classificação clínica deve derivar do escore-z calculado com a tabela oficial e dos pontos de corte da referência, nunca apenas do IMC adulto.
- Exibir no prontuário escore-z, classificação, indicador, referência, sexo, idade/data de avaliação e estado de validade; quando faltar dado obrigatório, mostrar pendência explícita em vez de um resultado presumido.
- Os gráficos devem usar as curvas oficiais e mostrar a medida individual no eixo correspondente; não confundir tabelas de pontos de corte com tabelas LMS ou curvas.
- Testes com dados sintéticos servem somente para validar matemática e integração; nunca devem ser apresentados como validação clínica das curvas OMS.