# AGENTS.md — Protocolo de agentes do NutriLab

Este arquivo complementa `CLAUDE.md` e `ROADMAP.md`. O objetivo é permitir que Claude e seus agentes executem o desenvolvimento com autonomia, sem perder rastreabilidade, segurança e rigor técnico.

## 1. Mandato de autonomia

O agente principal e os agentes especialistas estão autorizados a:

- Explorar integralmente o código, os testes, o esquema de banco e os arquivos de referência disponíveis.
- Pesquisar documentação técnica, protocolos e artigos científicos quando necessário.
- Escolher e implementar soluções técnicas razoáveis, reversíveis e testáveis.
- Criar módulos, classes, serviços, migrações não destrutivas, testes, documentação, ADRs e ferramentas auxiliares.
- Corrigir defeitos encontrados mesmo que não sejam a tarefa central, desde que não ampliem riscos ou escopo clínico de forma silenciosa.
- Delegar tarefas independentes a subagentes e integrar os resultados.
- Prosseguir automaticamente para as próximas tarefas do roadmap quando os critérios de aceite forem atendidos.

**Não pedir autorização ao usuário para cada decisão técnica. Não perguntar ao usuário qual artigo ou referência deve ser utilizado.** A autonomia inclui fazer a pesquisa bibliográfica necessária e registrar o caminho da decisão.

O agente não deve encerrar uma sessão apenas dizendo o que pretende fazer. Deve produzir alterações verificáveis na sessão em andamento, executar testes e entregar um resumo objetivo dos arquivos alterados, comandos executados, resultados e pendências.

## 2. Regra obrigatória para dúvidas sobre fontes

Sempre que surgir dúvida, lacuna ou divergência sobre uma fonte, artigo, equação, tabela, classificação, unidade ou população de validade:

1. Consultar primeiro o relatório de pesquisa já fornecido em `docs/referencias/RELATORIO_FORMULAS_E_ESTIMATIVAS.txt` (25/10/2026) e a referência bibliográfica citada nele.
2. Pesquisar a fonte primária, protocolo oficial, documento OMS/Ministério da Saúde ou estudo de validação pertinente. Não confiar somente em snippet, resumo de buscador ou citação indireta quando o coeficiente for usado em cálculo.
3. Comparar população, idade, sexo, variáveis, unidades, desenho do estudo, erro, validação externa, limitações e atualidade.
4. Escolher a referência mais apropriada para o uso proposto, quando a evidência permitir. Se houver conflito, registrar as alternativas e justificar a escolha.
5. **Adicionar uma entrada ao arquivo `docs/desenvolvimento/DIARIO_DUVIDAS_BIBLIOGRAFICAS.md`**, com a data real da pesquisa e os artigos/documentos usados para resolver a dúvida.
6. Atualizar o catálogo de fórmulas, o código, os testes e/ou a documentação conforme necessário.

Toda entrada deve registrar, no mínimo:

- Data (fuso `America/Recife`) e agente responsável.
- Pergunta/dúvida original.
- Fontes efetivamente consultadas: autor, ano, título, publicação/órgão, DOI/URL e página/tabela quando disponível.
- População e faixa etária estudadas.
- O que cada fonte confirma ou contradiz.
- Decisão adotada e justificativa.
- Limitações que permanecem.
- Arquivos/funções afetados e testes executados.
- Estado: resolvida, parcialmente resolvida ou pendente.

O diário é append-only: não apagar decisões antigas; se uma nova fonte mudar a conclusão, criar nova entrada que referencie a anterior.

### Quando a dúvida não puder ser resolvida

Não inventar uma resposta e não interromper todo o projeto. Registrar como pendente, implementar a estrutura técnica que não dependa do coeficiente (ex.: campo, tabela, interface, importador ou mecanismo de referência) e manter o cálculo específico desativado/indisponível até haver fonte suficiente. Prosseguir com as demais tarefas.

Validação profissional/institucional para liberar uma fórmula em uso assistencial é diferente de pesquisa bibliográfica: os agentes podem pesquisar, comparar e implementar a solução fundamentada sem pedir ao usuário para escolher a fonte; a homologação clínica final permanece registrada como critério de liberação.

## 3. Fontes e evidência

- O relatório anterior é um inventário técnico e ponto de partida, não substitui a leitura da publicação original.
- Preservar o status `[verificada]` ou `[conferir]` atribuído no relatório até que o agente confirme a fonte e documente a conferência.
- Priorizar artigos originais, revisões sistemáticas relevantes, organizações oficiais e protocolos institucionais identificáveis.
- Não inventar DOI, link, ano, autor, unidade ou faixa etária.
- Não atribuir a uma referência um resultado que ela não apresenta.
- Para dados OMS, guardar arquivo de origem, URL, versão/data, licença/condições de uso, checksum e script de transformação.
- Não interpolar ou extrapolar uma curva para além da faixa coberta sem método publicado e documentado.

## 4. Dados de entrada e planilhas do hospital

Os XLSX e PDFs enviados pelo usuário são referências operacionais com dados do setor. Eles não devem ser adicionados ao Git quando contiverem registros, valores internos, nomes, diagnóstico, escala individual, custos ou dados de pacientes/servidores.

Os agentes podem analisar a estrutura das planilhas e criar:

- Modelos vazios/sanitizados.
- Dicionários de dados.
- Scripts de importação.
- Dados sintéticos que reproduzam formato e regras sem nomes ou valores reais.
- Testes de consistência e relatórios de anomalias.

Ao importar planilhas, não assumir que nome de aba é data, que célula vazia significa zero ou que linhas de total são registros individuais. A planilha `CONTROLE DE REFEIÇÕES - Outubro 2026` apresenta discrepância de datas na aba `15-21` e apenas três blocos visíveis por aba; a inconsistência deve ser detectada, não corrigida silenciosamente.

## 5. Limites de segurança e clínica

Autonomia não autoriza:

- Versionar `clinica.db`, backups, anexos, PDFs identificáveis, planilhas reais, tokens, senhas, certificados ou chaves.
- Usar dados de paciente/servidor em teste, log, issue ou exemplo.
- Apagar ou sobrescrever histórico, evolução assinada, movimento de estoque ou trilha de auditoria.
- Transformar dado ausente em normal, negativo, “nega” ou zero.
- Transformar estimativa em medida aferida.
- Inventar fórmula, ponto de corte, referência, valor de rótulo ou dose.
- Gerar ou alterar automaticamente conduta nutricional, prescrição ou assinatura.
- Expor prontuário, antropometria, diagnóstico ou evolução ao perfil de funcionário de refeição.
- Compartilhar SQLite local em rede como solução multiusuário.
- Habilitar implantação pública ou usar dados reais fora do ambiente aprovado pelo hospital.

Quando uma questão de segurança/privacidade exigir autorização institucional, isolar a operação que depende dela e seguir com implementação sem dados reais. Não pedir autorização por dúvidas bibliográficas.

## 6. Regras específicas do NutriLab

### Antropometria

- Priorizar peso e estatura aferidos quando viáveis.
- Identificar toda estimativa, equação, unidade, entrada, data e versão de referência.
- Não usar punho para calcular densidade/massa muscular nesta versão.
- PP pode ser armazenado como medida/indicador, mas só entra em equações que a utilizem explicitamente.
- Não estimar estatura de menores de 6 anos com equação geral de AJ sem fonte aplicável.
- Mostrar aviso quando a população/faixa etária estiver fora da validação.

### Suplementos

- O seed inicial tem seis nomes e módulos sugeridos; composição, preço e embalagem não estão preenchidos no pacote analisado.
- Ficha técnica deve ter fonte e data.
- Produto/variante/apresentação devem ser identificados sem fusão por semelhança nominal.
- Registrar snapshot nutricional no uso do paciente.
- Não converter medida em gramas ou mililitros sem fator documentado.

### PEP e autoria

- Toda evolução tem usuário individual, data/hora e versão.
- Documento assinado é imutável; correções são adendos auditáveis.
- A assinatura/carimbo deve estar vinculada à conta pessoal; não afirmar validade jurídica sem política institucional.

### Mobile e refeições

- Perfis de refeição só acessam a função autorizada.
- Almoço: 12:00–13:00; jantar: 19:00–20:00, no fuso do hospital (`America/Recife`), configuráveis pelo administrador.
- Validar tempo/permissão no servidor.
- Correção retroativa só por fluxo autorizado e auditado.

## 7. Delegação entre agentes

O agente principal deve delegar tarefas claras, pequenas e com entregável definido:

- `clinical-evidence-researcher`: fontes, equações, curvas e diário bibliográfico.
- `legacy-workbook-analyst`: dicionário das planilhas, importação e anomalias.
- `database-backend-engineer`: modelo de dados, migrações, API, usuários e auditoria.
- `desktop-clinical-ui-engineer`: mapa, anamnese, PEP, impressão e fluxo desktop.
- `supplement-stock-engineer`: fichas técnicas, aporte, dieta enteral e inventário.
- `mobile-meal-engineer`: PWA, apontamento de refeições e janela de horário.
- `qa-security-reviewer`: testes, regressões, permissões, privacidade e release.

Regras:

1. Dois agentes não devem alterar o schema central ao mesmo tempo sem contrato e migração acordados.
2. Agentes paralelos devem informar arquivos que pretendem modificar antes de começar.
3. Um agente integrador resolve conflitos e revisa compatibilidade antes do merge.
4. O agente de QA deve ter independência para apontar falhas, não apenas confirmar a implementação.
5. Se uma tarefa depender de outra, registrar a dependência e executar tudo o que for independente.

## 8. Processo de execução para cada tarefa

1. Ler os documentos de orientação e identificar a fase.
2. Examinar estado do Git e código existente antes de editar.
3. Escrever plano curto e contrato se houver alteração de banco/API.
4. Pesquisar fontes e registrar dúvidas bibliográficas sem perguntar ao usuário.
5. Implementar uma alteração pequena e verificável.
6. Criar/atualizar testes sintéticos antes ou junto da implementação.
7. Executar testes relevantes e registrar saída/limitações reais. Depois do push, conferir o resultado do CI do GitHub (Windows e Linux) da branch: teste local em Linux não prova que passa no Windows (ver ADR-0006, seção "CI do GitHub").
8. Fazer revisão de privacidade do diff e exportações.
9. Atualizar README, roadmap, diário e ADRs conforme necessário.
10. Preparar resumo de entrega com arquivos alterados, comportamento implementado, comandos/resultados, decisões, limitações e próxima tarefa.
11. Se os critérios de aceite foram atendidos, seguir para a próxima tarefa/fase não bloqueada, sem solicitar autorização para continuar.

## 9. Padrão de entrega dos agentes

Cada tarefa concluída deve informar:

- **O que foi entregue:** comportamento real e arquivos.
- **Como verificar:** passos reproduzíveis.
- **Testes:** comandos executados e resultado verdadeiro, com o número da execução do CI do GitHub e o resultado no Windows e no Linux.
- **Banco:** migração, backup e rollback, quando aplicável.
- **Fontes:** referências incorporadas e entrada no diário bibliográfico.
- **Segurança:** varredura de dados reais/segredos e permissões.
- **Pendências:** apenas o que efetivamente não foi resolvido e por quê.

Não usar frases como “está pronto” quando apenas a estrutura foi criada ou um simulador passou.

**Regra final:** autonomia total para investigar, pesquisar, escolher e executar o desenvolvimento técnico; rastreabilidade obrigatória para fontes e alterações; proteção conservadora para dados e uso assistencial.
