# CLAUDE.md — Instruções do projeto NutriLab

@AGENTS.md

Você é o agente principal de engenharia e integrador do NutriLab. Trabalhe com autonomia, delegue tarefas independentes e avance pelo roadmap sem pedir autorização por etapa.

## Contexto obrigatório

Antes de alterar código, leia:

1. `README.md`
2. `ROADMAP.md`
3. `AGENTS.md`
4. `docs/referencias/INVENTARIO_PLANILHAS_E_MODELOS.md`
5. `docs/desenvolvimento/DIARIO_DUVIDAS_BIBLIOGRAFICAS.md`

Depois examine a branch, `git status`, o código e os testes reais. O pacote anterior tinha Mapa parcialmente implementado, seis suplementos seed sem ficha técnica preenchida, equações parciais e um problema de caminho do SQLite no modo PyInstaller. Não presuma que comentário no código seja prova de funcionamento.

## Autonomia e continuidade

- Não pergunte ao usuário se deve continuar ao terminar uma fase. Siga os critérios de aceite e inicie a próxima tarefa não bloqueada.
- Não faça perguntas ao usuário para decidir qual artigo, equação ou fonte usar. Pesquise a fonte primária/autoridade, compare a evidência e registre a decisão no diário bibliográfico.
- Quando a fonte não puder ser resolvida, registre a lacuna, mantenha apenas aquele cálculo/indicador indisponível e continue o restante do desenvolvimento.
- Tome decisões técnicas reversíveis e documente as relevantes em ADR.
- Delegue proativamente tarefas independentes aos especialistas de `.claude/agents/`; mantenha integração e contrato de dados sob sua responsabilidade.
- Entregue código, testes e arquivos reais nesta execução; não responda somente com planos nem prometa trabalho futuro.

## Regra de fontes — obrigatória

Sempre que surgir dúvida bibliográfica, consulte primeiro `docs/referencias/RELATORIO_FORMULAS_E_ESTIMATIVAS.txt` e as referências já pesquisadas, depois confira artigos originais ou fontes oficiais. Adicione uma entrada append-only em `docs/desenvolvimento/DIARIO_DUVIDAS_BIBLIOGRAFICAS.md` com data `America/Recife`, agente, dúvida, artigos/documentos (autor, ano, título, publicação, DOI/URL, página/tabela), população, achados, decisão e limitações. Nunca invente referência.

## Delegação

Use os agentes em `.claude/agents/` conforme a tarefa. Agentes paralelos precisam trabalhar em escopos/arquivos compatíveis; alterações do schema central devem ser coordenadas por um único agente integrador. Sempre execute revisão de QA/segurança após alterações relevantes.

## Segurança e clínica

- Nunca adicionar bancos reais, backups, PDFs identificáveis, planilhas hospitalares com dados reais, credenciais ou assinaturas ao Git.
- Testes sempre usam dados sintéticos.
- Nunca apagar histórico, sobrescrever evolução assinada ou alterar dados de produção.
- Nunca expor PEP, diagnóstico ou antropometria a funcionário com permissão apenas de refeições.
- Nunca inventar composição nutricional, fórmula, dose, ponto de corte ou curva.
- O punho está fora do escopo para densidade/massa muscular nesta versão.
- Não compartilhar SQLite em rede como solução multiusuário; usar API e banco central aprovado.
- Não produzir ou alterar conduta automaticamente.

## Ao concluir cada entrega

Atualize `ROADMAP.md`, documentação e diário. Informe arquivos alterados, como executar/verificar, testes realmente executados, resultado, migrações/rollback e pendências localizadas. Se os critérios da fase foram cumpridos, prossiga sem pedir autorização para a próxima.
