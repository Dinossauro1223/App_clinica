# Roteiro de homologação física — servidor local, modo offline e Tailscale

**Status:** pendente de execução em computadores e celulares reais.  
**Branch:** `feat/servidor-local-sincronizacao-offline-2026-11-26`  
**PR:** #131 — manter Draft até concluir os critérios bloqueantes.

> Execute primeiro em ambiente de teste, com banco de teste e contas fictícias. Não use dados identificáveis de pacientes durante a homologação. Registre apenas modelo do aparelho, versão do Android/Windows, horário, etapa e resultado técnico; nunca senhas, tokens ou dados clínicos.

## 1. Pré-requisitos

- [ ] Computador Windows com a versão candidata do NutriLab Desktop.
- [ ] Dois celulares Android com a mesma versão candidata do APK.
- [ ] Computador e celulares conectados ao mesmo Wi-Fi para os testes LAN.
- [ ] Tailscale instalado e autenticado no computador e nos celulares, na mesma tailnet, para os testes remotos.
- [ ] Política Tailscale permitindo TCP 8765 somente dos dispositivos/grupos de teste autorizados.
- [ ] Firewall do Windows permitindo TCP 8765 e UDP 8766 na rede local; acesso remoto TCP 8765 pela interface Tailscale conforme a política.
- [ ] Banco de teste com setores e leitos fictícios, usuários individuais de teste e dados operacionais descartáveis.
- [ ] Cópia de segurança do banco de teste antes de começar.

**Não fazer:** abrir TCP 8765 na internet, configurar port forwarding, usar conta administrativa compartilhada ou testar com prontuários reais.

## 2. Desktop e servidor local

| Etapa | Ação | Resultado esperado |
|---|---|---|
| D1 | Iniciar o NutriLab Desktop | Indicador superior muda de “Verificando” para “Servidor conectado”. |
| D2 | Consultar o status local | `http://127.0.0.1:8765/api/status` responde com status online e IP LAN. |
| D3 | Fechar o NutriLab Desktop | Servidor deixa de responder; desktop não deve afirmar que está conectado. |
| D4 | Abrir novamente o desktop | Servidor reinicia e o status volta a online sem iniciar manualmente outro processo. |
| D5 | Reiniciar o computador | Após login e abertura do NutriLab, servidor volta a atender; confirmar comportamento do Tailscale separadamente. |

## 3. Primeiro vínculo e descoberta LAN

| Etapa | Ação | Resultado esperado |
|---|---|---|
| L1 | No celular A, informar o endereço/QR do servidor pela primeira vez | Aplicativo valida que o endereço é o NutriLab e conclui o vínculo com a identidade do servidor. |
| L2 | Fechar e reabrir o APK | Mantém o servidor vinculado. |
| L3 | Com o APK em modo offline, manter o computador ligado e conectado ao mesmo Wi-Fi | Descoberta UDP encontra o servidor vinculado e recupera a conexão. |
| L4 | Alterar o IP LAN do computador (renovação DHCP ou reinício controlado do roteador) | Celular redescobre o mesmo servidor; não deve exigir novo vínculo. |
| L5 | Bloquear temporariamente UDP 8766 no firewall | Descoberta automática falha sem travar o aplicativo; endereço/QR manual continua sendo contingência. |
| L6 | Tentar vincular endereço de outro servidor de teste | O vínculo existente não deve ser substituído silenciosamente; troca deve exigir ação explícita do usuário. |

## 4. Fila offline e recuperação

Usar operações descartáveis que possam ser verificadas e revertidas no banco de teste.

| Etapa | Ação | Resultado esperado |
|---|---|---|
| O1 | Desconectar o celular A da rede e criar uma operação de teste permitida | Operação fica na fila local; indicador mostra desconexão e pendências. |
| O2 | Encerrar e reabrir o APK ainda sem rede | Operação continua na fila. |
| O3 | Reconectar à mesma LAN | Aplicativo recupera conexão e tenta sincronizar sem intervenção técnica. |
| O4 | Simular queda da conexão durante o envio (desligar Wi-Fi após iniciar uma operação) | Retentativa não cria duplicação; item só deixa a fila após confirmação. |
| O5 | Repetir a mesma operação com o mesmo identificador | Servidor devolve o resultado original, sem aplicar novamente. |
| O6 | Reutilizar um identificador com conteúdo diferente em teste controlado | Servidor rejeita com HTTP 409. |

## 5. Dois celulares e conflitos

- [ ] Celular A e B entram com contas individuais e autorizadas.
- [ ] Ambos recebem o mesmo mapa de teste atualizado.
- [ ] A altera um leito enquanto B permanece com uma cópia antiga.
- [ ] B tenta enviar a alteração concorrente: deve aparecer divergência e não deve sobrescrever silenciosamente a alteração de A.
- [ ] Repetir com inclusão de leito/registro concorrente.
- [ ] Repetir com remoção/liberação concorrente.
- [ ] Repetir com múltiplas divergências no mesmo mapa.
- [ ] Confirmar que a contagem e a mensagem descrevem alterações, inclusões e remoções.
- [ ] Confirmar que uma base local incompleta pausa o envio automático.
- [ ] Confirmar que propostas clínicas continuam aguardando revisão humana no desktop.

## 6. Acesso remoto Tailscale

A descoberta UDP é somente LAN; para acesso remoto, configurar o endereço Tailscale manualmente.

| Etapa | Ação | Resultado esperado |
|---|---|---|
| T1 | Conectar Tailscale no PC e no celular A | Ambos aparecem na mesma tailnet; desktop mostra URL remota `http://100.x.y.z:8765`. |
| T2 | No celular A, trocar Wi-Fi por rede móvel, mantendo Tailscale conectado | A URL Tailscale conecta e o indicador mobile mostra servidor conectado. |
| T3 | Sincronizar uma operação fictícia e conferir no desktop | Operação autorizada chega uma única vez. |
| T4 | Desconectar Tailscale no celular | Acesso remoto falha de forma clara; não deve cair para endereço público ou abrir conexão insegura. |
| T5 | Desconectar Tailscale no PC | URL remota deixa de ser anunciada/disponível; LAN continua funcionando. |
| T6 | De um dispositivo fora da tailnet, tentar alcançar o IP Tailscale/porta 8765 | A política Tailscale impede o acesso. |
| T7 | Confirmar no roteador que não há encaminhamento público da porta 8765 | Porta não exposta à internet. |

## 7. Backup e recuperação

- [ ] Fazer backup do banco de teste com o servidor em estado consistente.
- [ ] Restaurar o backup em ambiente isolado.
- [ ] Confirmar que usuários, setores, mapa e operações confirmadas continuam íntegros.
- [ ] Confirmar que filas ainda pendentes no celular podem ser sincronizadas sem duplicar eventos após a restauração, ou documentar claramente a limitação encontrada.
- [ ] Não executar restauração sobre o banco operacional sem plano de reversão aprovado.

## 8. Critérios para encerrar a homologação

A etapa só pode ser marcada como aprovada quando todos os itens bloqueantes abaixo forem demonstrados e registrados:

1. Conexão LAN inicial, reconexão automática e alteração de IP.
2. Persistência da fila após fechar/reabrir o APK e recuperação após queda durante envio.
3. Idempotência sem duplicação em retentativas reais.
4. Conflitos entre dois celulares sem sobrescrita silenciosa.
5. Acesso Tailscale em rede móvel com política restritiva.
6. Ausência de exposição pública da porta 8765.
7. Backup e restauração demonstrados em ambiente isolado.
8. Revisão das permissões por perfil e confirmação de que operações clínicas continuam sujeitas à revisão humana.

Se qualquer teste produzir perda de dados, duplicação, acesso indevido ou sobrescrita clínica, interrompa a homologação, preserve os bancos de teste e registre a etapa para correção antes de continuar.

## 9. Registro dos resultados

Preencher sem incluir dados de pacientes:

- Data/hora e responsável:
- Versão/commit do desktop:
- Versão/commit do APK:
- Windows (versão):
- Modelos e versões Android:
- Roteador/Wi-Fi (modelo, se relevante):
- Resultado por etapa (D, L, O, dois celulares, T e backup):
- Falhas observadas e passos para reproduzir:
- Evidência técnica sem dados pessoais:
- Decisão: aprovado / reprovado / bloqueado por infraestrutura.

**Estado atual:** roteiro preparado; nenhum teste físico é considerado executado por este documento.
