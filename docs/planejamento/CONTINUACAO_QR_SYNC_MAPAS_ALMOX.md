# Continuação — validação e evolução QR, mapas e almoxarifado

Data: 25/11/2026  
Branch: `feat/qr-sync-mapas-almox-continuacao`  
Base: merge do PR #109 (`6ccdb12bc60e43338cd8a851755932293fdebf35`).

Esta branch dá continuidade ao trabalho integrado pelo PR #109. Não reimplementar o que já está na `main`; primeiro validar o comportamento entregue e então fechar os itens funcionais ainda pendentes.

## Etapa 1 — validação ponta a ponta da entrega do PR #109

- [ ] Instalar o APK gerado em dispositivo Android físico e validar leitura de QR pela câmera.
- [ ] Validar leitura de QR por imagem e entrada manual do endereço.
- [ ] Confirmar que o QR de conexão não contém credenciais nem token e que o endereço persistido pode ser alterado.
- [ ] Validar conexão entre dois celulares e o servidor desktop na mesma rede Wi-Fi, incluindo reconexão e troca de servidor.
- [ ] Confirmar que APK e pacote desktop/ZIP são gerados, encontrados e distribuídos pelo caminho previsto no executável instalado.
- [ ] Testar duas contas de copeira simultaneamente: atualização compartilhada do mapa, recarga, sincronização offline/online e conflitos.
- [ ] Verificar histórico por leito: autor, perfil, data/hora, origem, campos alterados e valores anterior/novo.
- [ ] Confirmar que propostas pendentes/recusadas não aparecem como alterações aplicadas nem entram nos indicadores.
- [ ] Testar permissões globais da Copa e permissões administrativas, inclusive tentativas de acesso não autorizado.
- [ ] Registrar evidências reproduzíveis e corrigir qualquer falha encontrada.

## Etapa 2 — completar o que falta no escopo do plano original

- [ ] Unificar o cadastro de insumos desktop/mobile com IDs estáveis, migrações aditivas e prevenção de duplicidade.
- [ ] Integrar cadastro de produtos, catálogo do almoxarifado e espelho usado pela Gestão Alimentar.
- [ ] Completar prazo médio de reposição com solicitação e recebimento reais, responsável, quantidade e média em dias; excluir pedidos abertos e registros legados sem data de solicitação.
- [ ] Completar distribuição do APK e pacote desktop, com instruções de compartilhamento que não aleguem anexos automáticos quando não houver suporte.
- [ ] Completar indicadores mensais/anuais de atividade com critérios transparentes e apenas alterações efetivamente aplicadas.
- [ ] Concluir vínculo Produto → TBCA → ficha técnica → preparação/refeição, mantendo sugestões rastreáveis e confirmação humana antes de contabilizar consumo.

## Etapa 3 — qualidade e integração

- [ ] Criar testes unitários e de integração para cada correção.
- [ ] Testar migração a partir de bancos reais/legados preservando usuários, mapas, estoque e histórico.
- [ ] Executar CI Linux, Windows e Android, build Windows, APK e build integrado.
- [ ] Revisar permissões, autenticação, integridade e concorrência.
- [ ] Atualizar documentação e critérios de aceite.
- [ ] Só abrir PR para `main` quando os testes automatizados e os cenários manuais críticos estiverem aprovados.

## Critério de conclusão

A branch só estará pronta para merge quando os cenários ponta a ponta forem reproduzidos, as etapas funcionais acordadas estiverem implementadas e todos os workflows relevantes estiverem verdes. Não fazer merge automático.
