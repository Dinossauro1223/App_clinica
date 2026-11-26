# Consumo observado da cozinha e construção de fichas

## Objetivo

Organizar as retiradas de ingredientes do almoxarifado para a cozinha, permitir sua associação às preparações esperadas e produzir médias e custos observacionais que possam orientar a construção/revisão das fichas técnicas já cadastradas na Gestão alimentar.

## Fluxo de dados

1. **Cadastro do produto:** nome, unidade de estoque, categoria, validade, preço por unidade e conteúdo da embalagem podem ser mantidos no desktop e publicados no catálogo mobile. Categorias não padrão e validades preenchidas no mobile podem ser importadas pelo botão **Importar categoria/validade do mobile**; campos vazios não apagam dados do desktop. O desktop mantém espelho do produto na tabela `GA_Produtos_Almox`.
2. **Movimentação:** cada transferência ou devolução mobile guarda data/hora, origem/destino, ID do item, quantidade, usuário, observação opcional e preço/custo snapshot.
3. **Importação:** o desktop importa um intervalo da base mobile para `Mobile_Movimentos`, mantendo `(data,id_mobile)` como chave única. A importação é idempotente.
4. **Preparações esperadas:** a aba Consumo observado permite cadastrar o que a cozinha espera preparar para cada dia/refeição, número previsto de porções e vínculo opcional a uma ficha técnica existente.
5. **Destinação:** uma retirada Almoxarifado → Cozinha pode ser repartida entre uma ou mais preparações, uso geral/não identificado e perda. A soma das destinações não pode exceder a retirada. Cada substituição cria uma revisão; versões anteriores são inativadas, mas preservadas.
6. **Análise:** o relatório apresenta totais, média por dia corrido, média por dia com retirada, intervalo médio entre dias de retirada, itens sem destinação, custos e médias por preparação/execução/porção prevista.

## Regras para não contar duas vezes

- Transferências `almox` → `cozinha` entram como retirada original de ingredientes.
- Devoluções `cozinha` → `almox` entram com quantidade e custo negativos na apuração líquida. Exemplo: retirada de 100 g e devolução de 20 g = 80 g líquidos.
- A devolução reduz primeiro o saldo ainda não destinado da retirada original. Se a quantidade já tiver sido alocada a uma preparação, o sistema reduz a alocação mais recente e o custo correspondente; se a ficha já estava preenchida, o histórico sinaliza a necessidade de revisão.
- Transferências `cozinha` → `copa` continuam no histórico geral, mas não entram novamente no total retirado do almoxarifado.
- A chave de movimento é `(data,id_mobile)`; reimportar um período não cria nova retirada.
- Os IDs de item e movimento não são descartados na integração.
- Unidades diferentes permanecem distintas. Não há conversão automática entre pacote, unidade, kg, g, litro ou ml sem equivalência cadastrada/confirmada.

## Custos e preços

O mobile grava preço unitário/custo snapshot quando o item tem preço cadastrado no momento da transferência. Cada alocação guarda o preço/custo utilizado na sua revisão. A alteração do preço atual não deve reescrever snapshots históricos.

Movimentos antigos sem preço snapshot:
- continuam sem preço histórico na origem;
- a visualização pode mostrar preço atual como estimativa, com o rótulo **Atual***;
- o custo estimado não é apresentado como custo histórico comprovado.

## Retirada versus consumo efetivo

A análise calcula **retirada líquida após devoluções** e permite associar retiradas positivas às preparações, mas não declara que tudo o que saiu do almoxarifado foi consumido. Uma parte pode permanecer no estoque da cozinha, ser transferida para a copa ou se perder.

Para apurar consumo efetivo em uma etapa posterior, ainda será necessário conferir estoque físico inicial/final por ingrediente e período, registrando entradas, transferências, devoluções e perdas. Sem essas informações o programa mantém a quantidade como retirada observada/alocada, não como consumo confirmado.

## Fichas observacionais

A média por preparação será calculada com base nas quantidades destinadas a ela em diferentes execuções. Quando as porções previstas forem informadas, o sistema apresenta quantidade por porção prevista. Esse resultado é uma **estimativa observacional**: não substitui pesagem, rendimento final, fator de correção, per capita líquido/bruto nem validação pela Nutrição.

A ficha técnica oficial continua sendo mantida no editor existente (`GA_Fichas` / `GA_Ficha_Ingredientes`). Esta etapa não cria uma segunda base de fichas e não aprova automaticamente uma ficha a partir da média.

## Arquivos e funções

- `gestao_alimentar_db.py`: `salvar_preparacoes_dia`, `listar_preparacoes_dia`, `listar_movimentos_cozinha`, `salvar_alocacoes_retirada`, `listar_alocacoes_retirada`, `resumo_consumo_observado`.
- `integracao_mobile.py`: `importar_movimentos_cozinha`; o importador existente de estoque também preserva IDs e snapshots.
- `mobile/servidor.py`: categoria, validade, observação e snapshot de preço nas movimentações; devoluções da cozinha para o almoxarifado.
- `gestao_alimentar_ui.py`: aba **Consumo observado**, editor de preparações diárias e janela de destinação.
- `main.py`: menu desktop abre a Gestão alimentar.

## Limites e próxima etapa

O cadastro do cardápio esperado é manual nesta fase; não foi localizado no main atual um calendário estruturado de preparações que possa ser importado automaticamente. A próxima etapa é integrar essa tela à origem institucional do cardápio e acrescentar inventário/conciliação de estoque físico inicial/final, retornos e perdas. Só então serão disponibilizadas médias de consumo efetivo separadas das médias de retirada.
