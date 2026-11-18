# Decisões de arquitetura (ADRs)

Cada ADR registra **contexto, decisão, alternativas, consequências, como verificar, pendências e referências**.
Uma ADR aceita não é editada: se a decisão mudar, cria-se uma nova ADR que a substitui e a referencia.

| ADR | Título | Estado | Fase |
|---|---|---|---|
| [0001](ADR-0001-banco-local-caminho-unico-backup-migracoes.md) | Banco local: caminho único, backup verificado e migrações versionadas | Aceita (modo local) | 0 |
| [0002](ADR-0002-ambiente-reproduzivel-e-dependencias.md) | Ambiente reproduzível: Python de referência e dependências fixadas | Aceita, com validação pendente no Windows | 0 |
| [0003](ADR-0003-arquitetura-multiusuario-preliminar.md) | Arquitetura multiusuário preliminar e modelo de domínio | **Proposta** (sem decisão final) | 0 → 3 |
| [0004](ADR-0004-integracao-do-servico-de-banco-no-aplicativo.md) | Integração do serviço único de banco ao aplicativo | Aceita (modo local) | 0 |
| [0005](ADR-0005-executavel-sem-banco-real-modelo-sanitizado.md) | Executável sem o banco real: banco-modelo sanitizado | Aceita (modo local) | 0 |
| [0006](ADR-0006-condutas-de-alta-na-consulta.md) | Condutas de alta na consulta: catálogo versionado, confirmação pela nutricionista e folha do paciente | Aceita (modo local); conteúdo clínico aguarda homologação | 4 |

Convenção: toda ADR cita as fontes efetivamente consultadas (com data de consulta) e separa o que foi **verificado**
do que ficou **pendente**.
