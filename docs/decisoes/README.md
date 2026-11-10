# Decisões de arquitetura (ADRs)

Cada ADR registra **contexto, decisão, alternativas, consequências, como verificar, pendências e referências**.
Uma ADR aceita não é editada: se a decisão mudar, cria-se uma nova ADR que a substitui e a referencia.

| ADR | Título | Estado | Fase |
|---|---|---|---|
| [0001](ADR-0001-banco-local-caminho-unico-backup-migracoes.md) | Banco local: caminho único, backup verificado e migrações versionadas | Aceita (modo local) | 0 |
| [0002](ADR-0002-ambiente-reproduzivel-e-dependencias.md) | Ambiente reproduzível: Python de referência e dependências fixadas | Aceita, com validação pendente no Windows | 0 |
| [0003](ADR-0003-arquitetura-multiusuario-preliminar.md) | Arquitetura multiusuário preliminar e modelo de domínio | **Proposta** (sem decisão final) | 0 → 3 |

Convenção: toda ADR cita as fontes efetivamente consultadas (com data de consulta) e separa o que foi **verificado**
do que ficou **pendente**.
