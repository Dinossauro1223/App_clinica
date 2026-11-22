# Revisão isolada: PEP x módulo ambulatorial

Esta branch parte da `main` atual e contém somente a proposta isolada do PEP:
- persistência e autenticação de profissionais em `pep_db.py`;
- testes específicos do PEP;
- migração do PEP adicionada como versão 5.

## Por que foi isolado

A `main` já utiliza a migração v4 para evolução ambulatorial estruturada, biblioteca de recomendações, associações de exames e triagens. A versão da integração atribuía a v4 às tabelas do PEP. Como o sistema valida checksums de migrações aplicadas, substituir ou renumerar a v4 seria incompatível com bancos existentes.

## Decisão funcional pendente

O módulo ambulatorial registra consultas e dados estruturados. O PEP propõe autenticação de profissionais, autoria/assinatura e evoluções imutáveis com adendos. Não são equivalentes, mas devem compartilhar o mesmo identificador de paciente e evitar dois registros paralelos da mesma evolução.

Esta branch não integra o PEP à navegação principal e não altera `main`. É uma proposta isolada para revisão antes de eventual incorporação.
