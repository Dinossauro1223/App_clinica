# Diagnóstico — persistência, sincronização e operação offline do Mapa

## Problema observado

O desktop e o mobile atualmente tratam o mapa diário como registros separados por data. No desktop, Mapa_Registros possui UNIQUE(data, id_leito), e mapa_do_dia() consulta somente registros cuja data é exatamente a data solicitada. Portanto, um paciente registrado ontem não aparece automaticamente no mapa de hoje.

No mobile existe um comportamento diferente: linhas_mapa() procura o último registro de cada leito cuja data seja menor ou igual à data consultada. Isso faz o mobile herdar o estado anterior, enquanto o desktop começa o novo dia vazio. Essa diferença de modelo explica o cenário em que os leitos da copa continuam preenchidos e os do programa aparecem vazios.

## Segundo problema: envio incremental

integracao_mobile.enviar_mapa() percorre somente os registros retornados por mapa_db.mapa_do_dia(). A função _enviar_setor() também evita enviar leitos vazios que nunca foram marcados como enviados pelo desktop.

Assim, o fluxo atual é orientado a diferenças, e não a uma fotografia completa do mapa. Isso é eficiente para notificações, mas não é adequado para reconstruir o estado de um dispositivo que perdeu dados locais, mudou de instalação ou ficou vários dias sem sincronizar.

Além disso, Mobile_Visto usa uma assinatura do conteúdo para impedir que algo já visto volte como novidade. Isso é útil para o fluxo de aprovação, mas não deve ser usado como mecanismo de sincronização de estado.

## Modelo proposto

Separar dois conceitos:

1. Estado sincronizado — cada dispositivo mantém uma cópia completa do mapa e envia o estado completo por setor/data quando houver sincronização.
2. Alterações/conflitos — cada leito possui atualizado_em, atualizado_por e origem (pc, mobile, admin, nutricionista, copa, etc.).

A sincronização compara o timestamp por leito. O estado mais novo vence automaticamente quando não houver regra clínica especial. Quando houver conflito relevante, o desktop não sobrescreve silenciosamente: apresenta lado a lado o estado atual do PC e o estado recebido do mobile.

## Interface desejada no desktop

Quadro 1 — Estado atual no programa:
- paciente;
- idade;
- dieta/via/consistência;
- preferências;
- suplementos;
- última alteração;
- usuário/origem.

Quadro 2 — Estado recebido da copa/mobile:
- mesmos campos;
- última alteração;
- usuário/origem;
- indicação clara de qual versão é mais recente.

Ações:
- Manter PC;
- Aceitar mobile;
- Mesclar campos não conflitantes;
- Ver histórico;
- Aceitar tudo mais recente.

## Envio completo

O botão de sincronização deve ter uma operação explícita de Enviar mapa completo. O payload deve conter todos os leitos do setor, inclusive vazios, e o timestamp de cada leito.

O envio de notificações pode continuar sendo incremental para não gerar avisos desnecessários. O estado, porém, deve ser completo.

## Operação sem internet

Cada instalação móvel deve possuir armazenamento local. O mapa e os dados permitidos ficam disponíveis offline. Alterações são registradas numa fila local com usuário, origem e timestamp. Quando houver conexão com o servidor, a fila é enviada e o servidor devolve os estados mais recentes.

O desktop já utiliza SQLite local. O mesmo princípio deve ser aplicado ao mobile, sem exigir conexão contínua.

Para o almoxarifado, o estoque local também deve permitir leitura e lançamentos offline. Movimentos pendentes devem ser sincronizados posteriormente sem perder usuário, horário, item, quantidade e custo.

## Regra importante

"Última alteração vence" deve ser aplicada por leito/campo, não cegamente ao mapa inteiro. Se a copa alterar somente a dieta às 10:05 e o nutricionista alterar o peso às 09:00, a sincronização não deve apagar o peso.

A versão futura deve registrar timestamps por campo ou, no mínimo, gerar um conflito quando dois lados alterarem o mesmo campo desde a última sincronização.

## Conclusão

Há dois problemas independentes:

1. Modelo de dia diferente: desktop usa somente o registro da data; mobile herda o último registro disponível.
2. Sincronização incremental: o mobile não recebe uma fotografia completa do mapa e Mobile_Visto impede que estados já conhecidos sejam reapresentados.

A correção deve tratar ambos juntos. Apenas aumentar o número de notificações não resolveria a perda de estado.