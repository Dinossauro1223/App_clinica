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

## 3.1 Registro diário de produção, faltas, sobras e desperdício

Cada preparação do menu terá seu próprio fechamento diário, independente das demais preparações da refeição. A cozinha e o nutricionista poderão registrar:

- quantidade de porções planejadas e produzidas;
- se a preparação não foi produzida/disponibilizada;
- quantas porções faltaram (inclusive falta parcial);
- identificação de cada cuba/panela utilizada;
- peso de sobra e peso de desperdício de cada cuba, separadamente, em kg;
- observação operacional e responsável pelo registro.

O modelo de dados foi iniciado nesta branch com as tabelas `GA_Producao_Preparacao` e `GA_Producao_Cubas`, e funções transacionais para salvar, consultar e listar os registros. O registro é único por preparação do menu e data; uma correção atualiza o registro e substitui o conjunto de cubas, evitando duplicação acidental. A implementação atual é a camada de persistência; ainda faltam os formulários desktop/mobile e os endpoints com controle de permissões.

### Como o histórico deve orientar o planejamento

O sistema deve manter indicadores por preparação e refeição, em janelas móveis e com amostra mínima, como:

- porções planejadas versus produzidas;
- porções que faltaram;
- sobra total por cuba e em relação à quantidade produzida;
- desperdício total por cuba;
- frequência de dias com falta total/parcial.

A projeção de produção pode ser ajustada a partir da procura observada, mas não deve tratar sobra e desperdício como a mesma coisa. **Sobra limpa e segura que não foi servida** é indicador de excesso de produção; **desperdício** pode incluir restos não aproveitáveis e não deve ser abatido automaticamente da demanda. O peso de sobra só pode ser convertido em porções quando houver peso médio por porção medido e cadastrado para aquela preparação. Sem esse dado, o sistema deve exibir kg e não inventar equivalência.

### Regras para ajuste de estoque

O ajuste de retirada do almoxarifado deve usar a quantidade de produção recomendada e a ficha técnica versionada (ingredientes, FC, fator de cocção quando informado, rendimento e unidade). O histórico de produção pode sugerir nova quantidade, mas a alteração da requisição/baixa de estoque precisa de conferência e confirmação humana. Nunca reduzir ingrediente por causa de desperdício sem uma regra técnica validada: desperdício de prato/cuba não informa, por si só, qual ingrediente deve ser reduzido.

O menu publicado e os registros de produção precisam preservar a versão da ficha usada naquele dia. Alterações posteriores na ficha não podem reescrever silenciosamente o histórico de produção ou os consumos já calculados.

## 3.2 Classificação das preparações por tipo de refeição

A classificação organiza a montagem do cardápio; não é uma obrigação de preencher todas as categorias nem uma nova ficha técnica.

### Almoço e jantar

Exibir as categorias em grupos recolhíveis ou seções compactas, nesta ordem:

1. Saladas (`salada`)
2. Entradas (`entrada`)
3. Prato principal (`prato_principal`)
4. Acompanhamentos (`acompanhamento`)
5. Sobremesas (`sobremesa`)
6. Suco/fruta (`suco_fruta`)

Todas são opcionais. O nutricionista pode montar um jantar apenas com prato principal e acompanhamento, por exemplo. Não criar espaços vazios para categorias sem preparações.

### Desjejum, colação, lanche da tarde e ceia

Usar uma organização simples, sem exibir as seis categorias de almoço/jantar. As preparações ficam em uma lista única de itens (`geral`), permitindo combinações livres de bebidas, frutas, pães e demais alimentos servidos pelo estabelecimento.

### Regras de dados e compatibilidade

- A categoria pertence à seleção daquela preparação no cardápio do dia, não à identidade permanente da ficha técnica. A mesma ficha pode ser classificada de modo diferente em dias/contextos distintos.
- Cada preparação continua independente e vinculada à sua ficha técnica; uma refeição é a composição das preparações selecionadas.
- Não exigir categoria para registros legados já existentes. Novas interfaces devem oferecer a categoria adequada ao tipo de refeição e impedir combinações inválidas.
- A categoria selecionada deve ser preservada no snapshot de produção para que alterações posteriores no cardápio não mudem a classificação histórica.
- A interface deve agrupar e permitir recolher categorias, mostrar apenas as que possuem itens e manter a ordem definida acima.
- Categoria não altera porções, FC, fator de cocção, consumo de estoque ou cálculos nutricionais.

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
2. **Modelo de conteúdo visual (primeira fatia):** modo de preparo, etapas ordenadas e duas imagens opcionais em BLOB SQLite, sem caminhos locais. Valida assinatura JPEG/PNG/WebP e limita cada imagem a 5 MB. Editor, fator de cocção, snapshots publicados e sincronização ainda pendentes.
3. **Editor desktop de fichas:** formulário de instruções, etapas e duas fotos; fator de cocção por ingrediente apenas como dado explícito, sem cálculo automático até validar a convenção de uso.
3. **Menu diário desktop:** seleção de fichas por data/refeição/porções, snapshot versionado e publicação explícita.
4. **API e Mobile:** sincronização autenticada, aba Menu do dia condicional, visualização de fotos, instruções e quantidades de ingredientes; cache offline.
5. **Testes de fluxo e validação visual:** desktop, celular, diferentes escalas de fonte, perfis, dados antigos, imagens e sincronização.

