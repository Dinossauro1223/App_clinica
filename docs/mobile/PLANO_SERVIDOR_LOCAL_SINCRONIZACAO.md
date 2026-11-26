# Plano — servidor local e sincronização entre dispositivos

**Branch:** `feat/servidor-local-sincronizacao-offline-2026-11-26`  
**Data:** 26/11/2026  
**Escopo:** servidor executado no computador da clínica, armazenamento local independente e sincronização dos setores quando o servidor estiver disponível.

## Decisão de arquitetura

- O computador da clínica hospeda o servidor e o banco central operacional. O servidor só fica disponível enquanto esse computador estiver ligado.
- Desktop e cada instalação mobile mantêm seu próprio armazenamento local. A indisponibilidade do servidor não deve bloquear consultas nem gravações locais.
- A sincronização é retomada automaticamente quando a conexão é restabelecida; não deve exigir que o funcionário entenda endereços IP ou inicie procedimentos técnicos.
- O SQLite central é acessado somente pelo processo do servidor. Não compartilhar o arquivo SQLite diretamente pela rede.
- O servidor não deve ficar exposto diretamente à internet. Acesso remoto deverá ocorrer por VPN/túnel autenticado, com TLS e identidade de dispositivo; a allowlist de IP é apenas uma camada auxiliar.
- O endereço IP é um dado de localização mutável, não uma identidade de segurança. A autorização deve continuar baseada em conta, perfil e credencial de dispositivo.

## Regras de sincronização

1. Cada operação local recebe identificador idempotente, usuário, dispositivo, instante local, tipo de entidade e versão-base.
2. O servidor confirma cada operação e devolve a revisão central e as alterações posteriores à última revisão conhecida.
3. Retentativas não podem duplicar movimentações, refeições, cadastros ou eventos.
4. Movimentações de almoxarifado/cozinha/copa são eventos imutáveis; o saldo é recalculado pela soma dos movimentos aceitos.
5. Alterações concorrentes em prontuário, mapa ou evolução não podem sobrescrever silenciosamente dados. Campos sem conflito podem ser mesclados; conflitos clínicos devem ser apresentados para revisão autorizada.
6. A fila local só remove uma operação depois da confirmação individual do servidor. Falha parcial mantém somente os itens não confirmados.
7. Uma sincronização completa também distribui atualizações do servidor para todos os setores e dispositivos autorizados.
8. Dados locais, filas e credenciais devem permanecer protegidos; sessões e dispositivos podem ser revogados.

## Descoberta e endereço da rede

- O aplicativo deve consultar o estado do servidor e mostrar o IP atual detectado.
- Um administrador pode registrar o IP detectado pelo servidor.
- Reiniciar o roteador ou receber outro IP não pode ser interpretado como uma nova identidade de servidor.
- Próxima etapa: implementar descoberta automática (por nome local/mDNS ou mecanismo autenticado de descoberta), para recuperar o endereço quando o IP salvo deixar de responder.
- A troca manual de endereço/QR deve continuar disponível como contingência.

## Indicador de conexão

O topo de desktop e mobile deve mostrar estados distintos:
- **Conectado:** servidor respondeu a uma verificação recente.
- **Desconectado — modo local:** servidor não respondeu; gravações ficam na fila local.
- **Sincronizando:** há operações sendo enviadas ou atualizações sendo recebidas.
- **Atenção:** existem conflitos ou operações que precisam de revisão.

O indicador não deve confundir conectividade à internet com disponibilidade do servidor da clínica.

## Segurança e privacidade

- A API atual limita clientes a endereços privados. Isso impede acesso direto a partir da internet, mas não substitui HTTPS.
- Para uso remoto, configurar VPN/túnel de saída no computador da clínica; não abrir a porta HTTP do servidor diretamente no roteador.
- Autenticação individual, autorização por perfil no servidor, proteção contra tentativas repetidas, revogação de sessões/dispositivos e trilha de auditoria.
- Não registrar dados de pacientes em logs técnicos ou testes.
- Backups consistentes e restauração testada antes de migração do banco central.
- Funcionários da copa/estoque continuam limitados às funções e aos dados autorizados para seus perfis.

## Estado desta branch

### Implementado nesta primeira fatia
- `GET /api/status`: informa disponibilidade, IP local detectado e último IP registrado.
- `POST /api/admin/rede/registrar`: registra o IP atual, somente para perfil administrador.
- Indicador de conexão no topo do mobile, com verificação periódica.
- Configuração mobile para consultar e registrar o IP detectado.
- Testes de status, registro e bloqueio para perfis não administradores.

### Ainda pendente — não considerar pronto para produção
- Indicador equivalente no cabeçalho do desktop.
- Descoberta automática após mudança de IP, sem depender do endereço antigo.
- Sincronização automática sem modal/confirmação manual, com protocolo de confirmação por operação.
- Fila local durável e idempotente para todos os setores e operações do desktop e mobile.
- Distribuição incremental das alterações centrais para todos os dispositivos.
- Política completa de conflitos para prontuário, mapa, refeições e estoque.
- Identidade e revogação de dispositivos; criptografia de transporte e acesso remoto via VPN/túnel.
- Backups, migração segura e testes de recuperação.
- Execução dos testes locais e validação do CI em Windows e Linux.

## Critérios de aceite

- Desligar o computador central deixa os clientes em modo local, sem perda de gravações.
- Ligar o computador central faz os clientes reconectarem e sincronizarem automaticamente.
- Reiniciar o roteador e alterar IP local não exige novo cadastro de dispositivo nem reduz segurança.
- Operações repetidas durante reconexão não duplicam movimentos nem registros.
- Conflitos são resolvidos por regras explícitas e auditáveis.
- Todos os setores recebem as alterações autorizadas após a sincronização.
- Nenhum cliente não autorizado acessa dados clínicos ou operacionais.
- O processo funciona em desktop Windows e APK Android.

