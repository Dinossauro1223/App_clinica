# ADR-0008 — Snapshots automáticos e encerramento protegido

- **Estado:** Proposta implementada em branch; aguarda CI e revisão.
- **Data:** 22/11/2026 (America/Recife)

## Contexto

O serviço `db_service.py` já implementa backup SQLite consistente pela API nativa, validação de integridade e restauração precedida de cópia do estado atual. Entretanto, o aplicativo desktop não possuía rotina de backup ligada ao ciclo de vida da janela.

## Decisão proposta

1. Ao abrir o aplicativo, criar snapshot de início da sessão.
2. Durante o uso, criar snapshots a cada 15 minutos. Isso protege inclusive contra desligamento forçado, queda de energia ou encerramento do processo que não acione o protocolo da janela.
3. Ao fechar normalmente pela janela, criar e validar um snapshot final antes de destruir a interface. Se falhar, informar o erro e manter o aplicativo aberto para nova tentativa.
4. Registrar tentativa best-effort via `atexit` para encerramentos normais do interpretador.
5. Manter os arquivos em `backups/` ao lado do banco, com data e hora local no nome, sem versioná-los no Git. A restauração continua usando a tela/ferramenta de restauração já existente em `db_service`.

## Limitações e garantias

- O backup de fechamento não pode ser garantido quando o sistema mata o processo sem entregar evento tratável. Os snapshots periódicos reduzem a janela de perda ao intervalo configurado.
- O banco principal permanece a fonte de verdade. As operações existentes devem continuar confirmando transações; não se deve depender de backup periódico para persistir cada gravação.
- O snapshot do SQLite é consistente mesmo com o banco aberto; não copiar diretamente o arquivo `.db` enquanto o aplicativo está em uso.
- Os backups contêm dados clínicos e devem permanecer locais, protegidos por permissões do sistema operacional e excluídos do Git.
- Não há garantia contra falha simultânea do disco que contém banco e backups. Recomenda-se cópia externa institucional criptografada, sob política de acesso aprovada.

## Validação

Testes unitários usam banco e agendador sintéticos. CI Windows/Linux deve confirmar compatibilidade. Testes de desligamento real e restauração em instalação PyInstaller permanecem validação operacional.
