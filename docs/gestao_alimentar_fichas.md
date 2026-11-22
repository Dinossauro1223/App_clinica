# Gestão alimentar (Fichas) — guia funcional

**Primeira entrega:** 22/11/2026
**Escopo:** desktop NutriLab, com leitura do Almoxarifado do NutriLab Mobile.

## 1. Onde encontrar

A função aparece na barra lateral em **GESTÃO ALIMENTAR → Gestão alimentar (Fichas)**. Ela é separada das áreas Ambulatorial e Hospitalar e abre três abas:

- **Fichas técnicas:** cadastro, edição, inativação e cálculo das preparações.
- **Almoxarifado:** espelho dos itens e saldos lidos do banco do Mobile.
- **Base TBCA:** pesquisa e importação da aba `TBCA (2024)` da planilha de referência.

Os dados da função são armazenados em tabelas próprias (`GA_*`) no banco principal selecionado pelo `db_service`. Não alteram as tabelas clínicas existentes.

## 2. Base de composição dos alimentos

Use **Importar TBCA do Excel** e selecione a planilha fornecida. O importador lê a aba `TBCA (2024)` por cabeçalho, sem depender de posição fixa das colunas. A importação atual aceita os dados de identificação, tipo, NPU, fatores de correção, medida caseira, per capita e composição nutricional, incluindo energia, macronutrientes, minerais e vitaminas disponíveis na planilha.

O processamento é repetível: um ID TBCA já existente é atualizado, não duplicado. Na planilha entregue nesta sessão foram processadas 5.269 linhas válidas e permaneceram 5.268 IDs únicos após atualização do ID repetido presente na origem.

## 3. Cadastro de ficha técnica

Em **Nova ficha**, informe nome, categoria, número de porções e, opcionalmente, descrição/modo de preparo. Para cada ingrediente, informe:

- Nome e quantidade per capita líquida.
- Unidade: `g`, `kg`, `mg`, `ml`, `L` ou `un`.
- Fator de correção (FC), maior que zero.
- Medida caseira, quando conhecida.
- ID TBCA, para vincular composição nutricional.
- NPU, apenas como valor registrado de referência, sem cálculo automático de NDPcal.
- Densidade em g/ml, quando for necessário converter volume em massa para consultar a TBCA.
- Produto do Almoxarifado, quando houver correspondência com o item cadastrado no Mobile.

A ficha é editável. A opção **Inativar** oculta a preparação da lista principal sem apagar seus registros.

## 4. Cálculos apresentados

Para cada ingrediente:

- Quantidade líquida total = quantidade per capita × número de porções.
- Quantidade bruta total = quantidade líquida total × FC.
- Custo = quantidade bruta total em unidade-base ÷ conteúdo da embalagem em unidade-base × preço da unidade de estoque.
- Nutrientes por porção = quantidade líquida per capita em gramas ÷ 100 × composição TBCA por 100 g.

A conversão entre g/kg/mg e ml/L respeita dimensões. Um ingrediente em volume só contribui para os nutrientes da TBCA quando a densidade g/ml foi informada; o sistema não presume que 1 ml = 1 g. O custo só é calculado quando a dimensão do ingrediente é compatível com a dimensão do conteúdo da embalagem.

O custo total só aparece como completo quando todos os ingredientes possuem produto associado, preço e conteúdo de embalagem compatíveis. Caso contrário, a tela apresenta custo parcial e quantidade de pendências. O saldo é confrontado com a quantidade bruta necessária; saldo insuficiente e estoque sem lançamento são sinalizados.

## 5. Integração com Almoxarifado Mobile

A tela consulta `mobile/dados/mobile.db` usando as funções do servidor Mobile, no mesmo computador em que o servidor desktop/mobile está instalado. A leitura usa os itens do Almoxarifado, o saldo mais recente disponível até a data atual e os metadados comerciais do cadastro:

- nome do produto;
- preço unitário da unidade de estoque;
- conteúdo de cada unidade (quantidade + unidade em g/kg/mg/ml/L/un);
- quantidade em estoque.

A ficha mantém um espelho de consulta local e a data de sincronização. Ela **não grava nem altera saldos** no banco Mobile. Use **Sincronizar Almoxarifado** para atualizar o espelho. Um saldo sem lançamento é tratado como desconhecido, não como zero confirmado.

Na versão do Mobile incluída no ZIP original, o cadastro de itens ainda não tinha preço e conteúdo de embalagem. Esta branch acrescenta esses campos e migra bancos existentes de modo aditivo. No Mobile, o administrador pode cadastrar esses metadados ao adicionar um item ou usar **Editar preço/embalagem** nos itens existentes. Os campos ficam vazios nos itens antigos até serem preenchidos; nenhum preço ou conteúdo é inventado.

## 6. O que não é importado automaticamente ainda

A aba `Fichas Técnicas` da planilha contém seis blocos de preparação, mas alguns valores dependem de fórmulas específicas do Google Sheets, há valores armazenados como zero/`None` e o modelo não apresenta uma unidade inequívoca por linha para todos os ingredientes (há preparações com medidas em massa e volume). Por isso, esta primeira entrega **não importa essas seis preparações em lote**. Elas devem ser cadastradas/revisadas na tela antes de serem usadas para custos ou composição nutricional. A próxima etapa recomendada é um importador com pré-visualização, validação de unidade por ingrediente e relatório dos campos que exigem conferência.

A aba `Construção da ficha` também contém fórmulas externas/`DUMMYFUNCTION`; essas fórmulas não são executadas pelo aplicativo. A função reimplementa os cálculos básicos descritos acima. NPU é armazenado quando informado, mas NDPcal não é calculado automaticamente porque a regra/fórmula da origem não foi considerada segura para migração direta.

## 7. Testes e limites desta entrega

Os testes automatizados usam bancos e planilhas sintéticas. Cobrem importação TBCA, conversão de unidades, FC, custos, composição nutricional, cadastro Mobile, migração aditiva, leitura do Almoxarifado, sincronização e preservação de estoque desconhecido.

Antes do uso operacional, validar a correspondência dos produtos, unidades, densidades, fatores de correção, porções, resultados e preços com a equipe responsável. Os resultados são estimativas de apoio e não substituem a conferência da ficha institucional nem a validação profissional.
