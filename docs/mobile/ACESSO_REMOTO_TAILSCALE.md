# Acesso remoto seguro com Tailscale

## Como funciona

O Tailscale cria uma rede privada entre dispositivos autorizados. Cada dispositivo recebe um endereço estável da faixa `100.64.0.0/10`; o tráfego entre os dispositivos é transportado pela conexão WireGuard criptografada do Tailscale. O NutriLab continua usando a API HTTP na porta 8765, mas o acesso remoto só é aceito quando a conexão chega ao endereço Tailscale detectado no próprio computador servidor.

Não é necessário abrir portas no roteador, contratar IP público ou configurar redirecionamento de portas.

## Configuração inicial

1. No computador da clínica, instale o Tailscale pelo site oficial: https://tailscale.com/download.
2. Entre com a conta que será administradora da rede privada (tailnet) da clínica.
3. Instale o Tailscale em cada celular e computador que deverá acessar o NutriLab. Entre na mesma tailnet.
4. No computador da clínica, deixe o Tailscale conectado e confirme que o dispositivo permite conexões de entrada.
5. Inicie o NutriLab Desktop. O servidor móvel continua hospedado pelo programa desktop; portanto, o computador e o NutriLab precisam permanecer ligados e em execução.
6. No NutriLab Desktop, consulte o indicador de conexão. Quando o Tailscale estiver ativo, ele mostrará o endereço `http://100.x.y.z:8765`.
7. No celular, abra a configuração de conexão do NutriLab Mobile e informe esse endereço como servidor. Faça login com a conta individual do setor.
8. Teste primeiro conectado ao Wi-Fi da clínica e depois usando a rede móvel do celular. O indicador deve mostrar conexão e a sincronização deve ocorrer.

O endereço Tailscale permanece estável quando o computador muda de Wi-Fi para cabo ou outra rede. Se o endereço for alterado administrativamente no painel Tailscale, consulte novamente o indicador do desktop.

## Controle de acesso recomendado

- Convide apenas funcionários e dispositivos que realmente precisam acessar a clínica.
- No painel de Access controls da Tailscale, use uma política de negação por padrão e uma regra *grant* que permita somente os dispositivos/grupos autorizados a alcançar o computador da clínica na porta TCP 8765.
- Não deixe a política padrão permitindo comunicação irrestrita entre todos os dispositivos da tailnet.
- Remova ou revogue imediatamente dispositivos perdidos, antigos ou de funcionários desligados.
- Mantenha as contas NutriLab individuais e com o menor perfil de acesso necessário. A autenticação Tailscale não substitui a autenticação e as permissões do NutriLab.
- Para um computador servidor dedicado, avalie habilitar o modo *Run unattended* do Tailscale no Windows. Isso mantém a VPN conectada após logout/reinicialização, mas **não inicia o NutriLab**: o servidor do aplicativo ainda depende do programa desktop aberto.

## Limitações e segurança

- O recurso só libera conexões de origem na faixa Tailscale quando o endereço de destino da conexão é exatamente o IP Tailscale detectado no computador servidor. A faixa CGNAT inteira não é liberada para outros endereços/interfaces.
- A rede local privada continua funcionando como antes.
- O Tailscale protege o transporte entre dispositivos por WireGuard; a aplicação continua usando HTTP dentro desse túnel. Não exponha a porta 8765 à internet nem faça port forwarding no roteador.
- A descoberta UDP da rede local não atravessa a internet/tailnet. Para acesso remoto, informe manualmente o endereço Tailscale na configuração do celular.
- Se o Tailscale estiver desconectado ou não instalado, o status remoto ficará indisponível e o acesso LAN continuará disponível.
- O servidor não fica disponível quando o computador ou o NutriLab Desktop estiver desligado. Os clientes podem continuar em modo local, conforme as limitações de sincronização offline documentadas no plano principal.
- Antes de uso institucional com dados reais, ainda são necessários testes em dispositivos reais, revisão das regras de acesso, backup/restauração e homologação de segurança.

## Diagnóstico rápido

- **Não aparece endereço Tailscale no desktop:** verifique se o aplicativo Tailscale está conectado e se o comando `tailscale ip -4` retorna um IP `100.x.y.z`.
- **O celular está na mesma tailnet, mas não conecta:** confirme a política de acesso (TCP 8765), a opção de conexões de entrada e o endereço informado no NutriLab Mobile.
- **Funciona no Wi-Fi, mas não na rede móvel:** confirme que o Tailscale do celular está conectado à mesma tailnet; o endereço LAN `192.168.x.x` não funciona fora da rede local.
- **Servidor desligado:** os dados locais permanecem no dispositivo, mas a sincronização só volta quando o computador e o NutriLab Desktop estiverem ativos.

## Referências oficiais

- Instalação no Windows: https://tailscale.com/docs/install/windows
- Endereços IP Tailscale: https://tailscale.com/docs/concepts/tailscale-ip-addresses
- Controle de acesso: https://tailscale.com/docs/features/access-control
- Modo sem usuário conectado no Windows: https://tailscale.com/docs/how-to/run-unattended
