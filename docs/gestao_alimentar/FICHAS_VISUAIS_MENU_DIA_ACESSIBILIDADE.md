# Proposta de fichas visuais de preparação, Menu do dia e acessibilidade mobile

**Status:** especificação da próxima etapa; ainda não integrada ao fluxo operacional.
**Branch:** `feat/fichas-preparacao-fotos-menu-acessibilidade-mobile`

## 1. Ficha visual da preparação

A preparação cadastrada na Gestão alimentar (Ficha técnica) deve ter uma seção **Referência visual**, com duas imagens opcionais e independentes:

- **Porção individual montada:** prato pronto para mostrar a aparência, montagem e proporção de uma porção.
- **Preparação em recipiente cheio:** panela, cuba ou recipiente de distribuição com a preparação pronta, para ajudar a equipe a reconhecer o produto em lote.

As imagens não substituem a descrição textual. A ficha também terá **modo de preparo** (etapas ordenadas, editáveis), observações operacionais, e instruções de conservação/serviço se forem pertinentes. Upload deve validar tipo real de imagem, limitar tamanho, permitir trocar/remover a foto e apresentar pré-visualização. Evitar salvar caminhos de arquivos locais do computador do nutricionista, pois eles não estarão disponíveis no celular ou em outro computador.

## 2. Ingredientes, quantidades e rendimento

A lista de ingredientes já existe nas fichas técnicas, incluindo quantidade per capita, unidade e fator de correção (FC). A evolução proposta é:

- manter o FC por ingrediente;
- acrescentar **fator de cocção por ingrediente**, opcional até que o profissional o informe;
- permitir registrar unidade e quantidades sem conversões implícitas entre g, kg, ml, L e unidades;
- calcular quantidades totais para o número de porções previsto no menu, com sinalização de dados incompletos;
- apresentar na cozinha ingredientes, quantidade total a retirar do Almoxarifado, unidade e vínculo ao item de estoque quando existente.

Não atribuir FC ou fator de cocção padrão para ingredientes sem dado confirmado. Exibir “não informado” em vez de usar um valor estimado. O método de cálculo e a interpretação do fator de cocção precisam ser confirmados antes de automatizar rendimentos: o fator de correção atual e o fator de cocção têm funções diferentes e não devem ser tratados como intercambiáveis.

## 3. Menu do dia

A nutrição deve selecionar uma ficha cadastrada para a data e refeição (ex.: almoço). Essa seleção gera uma instância do menu do dia vinculada à ficha, com número de porções planejadas. O Menu do dia deve:

- mostrar apenas preparações selecionadas para a data/refeição atual;
- exibir ingredientes e quantidades planejadas, fotos (prato individual e recipiente cheio), modo de preparo e fatores informados;
- indicar claramente campos não preenchidos;
- manter um snapshot dos dados publicados para evitar que uma edição posterior na ficha altere silenciosamente a instrução que a cozinha já recebeu.

A aba **Menu do dia** na versão mobile é contextual e não deve ser criada/exibida quando não existir preparação selecionada para aquele dia. Deve ser visível para perfis de cozinha (e para os perfis autorizados de administração/nutrição, caso se deseje conferência) somente quando o menu publicado contiver itens. Não misturar esta aba com o mapa de pacientes nem com estoque.

## 4. Fluxo de dados e armazenamento

O desktop e o servidor Mobile usam bancos SQLite separados atualmente. A ficha técnica está no módulo de Gestão alimentar, enquanto o Mobile trabalha com seu próprio banco. A integração precisa, portanto, ser explícita e não assumir que o Mobile consegue ler a ficha desktop.

Fluxo proposto:
1. Nutricionista cadastra/edita ficha, ingredientes, FC, fatores de cocção, instruções e fotos.
2. Nutricionista seleciona as fichas para o dia e define porções.
3. Desktop publica um snapshot de menu para o servidor Mobile, com identificadores de preparação e imagens transferíveis (não caminhos locais).
4. Mobile persiste o snapshot recebido e disponibiliza apenas os itens daquele dia na aba contextual Menu do dia.
5. Cozinha consulta, confere os ingredientes para retirada e executa o preparo; mudanças no menu devem atualizar a publicação de modo rastreável.

Fotos devem ter identificadores próprios e armazenamento portátil/gerenciado (não caminhos absolutos do Windows). A entrega inicial pode sincronizar arquivos de imagem por endpoint autenticado com validação e tamanho máximo; não transmitir imagens grandes como base64 em cada consulta do menu.

## 5. Segurança, permissões e auditoria

- Nutricionista e administrador podem cadastrar, editar e publicar fichas/menu conforme permissões definidas.
- Equipe de cozinha pode consultar o menu publicado e, se autorizado, adicionar ou substituir fotos de referência; não editar ingredientes, fatores, porções planejadas ou instruções técnicas sem autorização.
- Validar permissões no servidor/API, não apenas ocultar botões na interface.
- Registrar autoria, data/hora, versão publicada e alterações relevantes.
- Menu vazio não deve produzir aba vazia, título órfão ou espaço no Mobile.

## 6. Critérios de aceite

- Ficha permite salvar e visualizar separadamente as duas fotos, modo de preparo e dados por ingrediente.
- Edição preserva dados e imagens não modificados; remoção de foto é explícita.
- Seleção no menu associa ficha, data, refeição e porções; o snapshot publicado fica estável.
- Mobile apresenta Menu do dia somente quando há menu publicado com preparações.
- Cozinha vê preparação, fotos, método e lista de ingredientes com quantidades totais, e consegue consultar sem internet após sincronização (quando o PWA estiver conectado e armazenar o snapshot).
- Permissões e testes garantem que cozinha não altere ficha nutricional por endpoints não autorizados.
- Testar menu vazio, seleção de uma/múltiplas preparações, alteração após publicação, foto ausente, imagem inválida, dados de fator ausentes, unidades diversas, telas estreitas e sincronização offline/retorno online.

## 7. Implementação recomendada por etapas

1. **Acessibilidade mobile:** preferência de escala de texto de 50% a 200%, incrementos de 10%, persistente por dispositivo, com controles recolhidos e layout adaptável. (Implementação iniciada nesta branch.)
2. **Modelo e editor de fichas:** campos de modo de preparo, fator de cocção por ingrediente e duas fotos; testes de migração e preservação de fichas antigas.
3. **Menu diário desktop:** seleção de fichas por data/refeição/porções, snapshot versionado e publicação explícita.
4. **API e Mobile:** sincronização autenticada, aba Menu do dia condicional, visualização de fotos, instruções e quantidades de ingredientes; cache offline.
5. **Testes de fluxo e validação visual:** desktop, celular, diferentes escalas de fonte, perfis, dados antigos, imagens e sincronização.

