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
- O servidor anuncia sua presença por broadcast UDP local na porta 8766. O APK Android procura o computador na rede e só aceita automaticamente a identidade estável do servidor que já foi vinculada no primeiro acesso por QR/endereço.
- A identidade do servidor é persistida no banco e devolvida também por `/api/status`. Ela serve para evitar a troca acidental para outro servidor, mas não é segredo nem prova criptográfica contra falsificação por alguém já conectado à mesma rede; não substitui TLS/VPN nem autenticação.
- A troca manual de endereço/QR continua disponível como contingência. Se o firewall bloquear UDP 8766, a descoberta automática não funcionará até liberar essa porta; o acesso por endereço/QR continua disponível.

## Indicador de conexão

O topo de desktop e mobile deve mostrar estados distintos:
- **Conectado:** servidor respondeu a uma verificação recente.
- **Desconectado — modo local:** servidor não respondeu; gravações ficam na fila local.
- **Sincronizando:** há operações sendo enviadas ou atualizações sendo recebidas.
- **Atenção:** existem conflitos ou operações que precisam de revisão.

O indicador não deve confundir conectividade à internet com disponibilidade do servidor da clínica.

## Segurança e privacidade

- A API atual limita clientes a endereços privados. Isso impede acesso direto a partir da internet, mas não substitui HTTPS.
- O aplicativo desktop inicia o servidor local e exibe seu estado; para manter o servidor acessível, o programa desktop também precisa permanecer em execução nesta versão.
- Para uso remoto, configurar VPN/túnel de saída no computador da clínica; não abrir a porta HTTP do servidor diretamente no roteador.
- Autenticação individual, autorização por perfil no servidor, proteção contra tentativas repetidas, revogação de sessões/dispositivos e trilha de auditoria.
- Não registrar dados de pacientes em logs técnicos ou testes.
- Backups consistentes e restauração testada antes de migração do banco central.
- Funcionários da copa/estoque continuam limitados às funções e aos dados autorizados para seus perfis.

## Estado desta branch

### Implementado nesta branch até o momento
- `GET /api/status`: informa disponibilidade, IP local detectado e último IP registrado.
- `POST /api/admin/rede/registrar`: registra o IP atual, somente para perfil administrador.
- Administrador mobile registra automaticamente um IP diferente assim que o aplicativo volta a alcançar o servidor; o botão manual também permanece disponível.
- Indicador de conexão no topo do mobile, inclusive na tela de login, com verificação periódica e quantidade de operações pendentes.
- Indicador persistente no topo do desktop, mostrando se o servidor local está acessível.
- Sincronização desktop ↔ mobile em segundo plano a cada 30 segundos, para o dia atual e todos os setores: publica alterações do mapa desktop e importa refeições, contagens e movimentos do mobile.
- Alterações clínicas recebidas do mobile continuam como propostas para revisão humana; a rotina automática não as aplica ao prontuário.
- Fila offline mobile: operações sem conexão ficam no armazenamento local do dispositivo.
- Ao recuperar a conexão, operações sem conflito são enviadas automaticamente; mapas com divergências continuam aguardando revisão do funcionário.
- Cada operação POST da fila recebe identificador único. O servidor guarda o resultado e devolve a mesma resposta em retentativas, evitando duplicação após queda de conexão.
- Reutilização de identificador com conteúdo diferente é recusada com HTTP 409.
- Testes de status, registro, bloqueio de perfis não administradores e idempotência.

### Ainda pendente — não considerar pronto para produção
- Validar a descoberta UDP em roteadores e versões reais de Android/Windows, incluindo a liberação da porta UDP 8766 no Firewall do Windows. Se a descoberta estiver bloqueada, permanece o fluxo manual por QR/endereço.
- Fila offline durável para operações do próprio desktop quando o computador central estiver desconectado; a sincronização periódica atual cobre o desktop conectado ao banco local do servidor.
- Sincronização do histórico de todas as datas e distribuição incremental em tempo real para todos os dispositivos; a rotina atual sincroniza o dia atual e os clientes atualizam cada setor ao consultá-lo.
- Política de conflitos completa para prontuário, mapa, refeições e estoque; propostas clínicas do mapa não são aplicadas automaticamente e as demais regras continuam no servidor.
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

