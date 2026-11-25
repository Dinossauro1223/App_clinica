# Plano de evolução — QR, mapas compartilhados, almoxarifado e TBCA

Data da auditoria: 24/11/2026  
Base de auditoria: commit `045c2c93219d291e51ed8b0c91d486adf59e90de` da branch `feat/testes-precisao-lms-pediatria`.

## Branches de trabalho

- Funcionalidades: `feat/qr-sync-mapas-almox-2026-11-24`
- Distribuição/compilação: `feat/build-apk-integrado-2026-11-24`

Ambas foram abertas a partir do mesmo SHA acima. Não alterar nem mesclar o PR #103 durante esta etapa.

## Diagnóstico da arquitetura atual

1. O desktop é CustomTkinter e usa SQLite local (`clinica.db`).
2. O servidor mobile (`mobile/servidor.py`) é iniciado pelo desktop e usa um banco separado (`mobile.db`). As contas mobile compartilham esse banco quando apontam para o mesmo servidor.
3. O mapa mobile é persistido em `mapa_dia`, com `por_usuario`, `por_perfil` e `atualizado_em`. Há apenas o último autor por registro; não existe uma trilha imutável de cada atualização.
4. O perfil `copa` é atualmente limitado a `id_setor`; o servidor filtra os setores e impede que uma copeira altere outro setor.
5. As configurações desktop (`configuracoes_ui.py`) mostram aparência, NRS-2002 e backups. A integração mobile está em `mobile_ui.py`.
6. O formulário de login fica em `mobile/static/index.html`; o APK é uma WebView que carrega essa página e já tem uma ponte JavaScript nativa (`Android`) para funções do aplicativo.
7. O APK é compilado por `mobile/apk/Gerar_APK.bat`, gerando `mobile/apk/saida/NutriLab-Mobile.apk`. O inicializador desktop (`Gerar_e_Abrir_NutriLab.bat`) não chama esse build.
8. O PyInstaller inclui `mobile/servidor.py` e `mobile/static` em `_internal/mobile`, mas não inclui o APK. No executável, `get_base_path()` aponta para `_internal`.
9. O mobile mantém `itens` (estoque) e `suplementos_catalogo`; o desktop tem ainda o módulo `almox_db.py`, com tabelas `Almox_Itens`, `Almox_Movimentos`, `Almox_Programacoes` e `Almox_Programacao_Itens`. Esses domínios não são hoje um único cadastro.
10. A Gestão Alimentar já importa TBCA para `GA_TBCA_Alimentos`, sincroniza produtos mobile em `GA_Produtos_Almox`, permite selecionar TBCA e produto por ingrediente, e agenda preparações em `GA_Preparacoes_Dia`. A ligação entre produto, TBCA, retirada e preparação ainda depende de preenchimento/alocação manual.

## Plano ordenado — menor para maior complexidade

### 1. Simplificar unidades e formulários de estoque (baixa)

- Na interface mobile de cadastro/edição de itens, trocar a lista extensa por opções visíveis: **g (massa)**, **mL (volume)** e **unidade (peça)**.
- Preservar compatibilidade com cadastros antigos: normalizar kg→g e L→mL apenas quando houver conversão explícita e inequívoca; nunca converter massa em volume.
- Manter separados os campos: conteúdo de uma embalagem, quantidade de embalagens/estoque e unidade-base. Não confundir “500 g por pacote” com “12 pacotes no estoque”.
- Aplicar o mesmo modelo no cadastro desktop e no mobile, com rótulos claros e controles de seleção direta.
- Testar migração de unidades antigas, edição de itens e movimentações sem alterar saldos históricos.

### 2. Cadastro de insumos pelo desktop e catálogo unificado (baixa a média)

- Permitir ao administrador cadastrar/editar produtos e suplementos no desktop, incluindo nome, conteúdo da embalagem, unidade-base, quantidade em estoque, preço, categoria e situação.
- Reutilizar o catálogo do servidor mobile como fonte compartilhada para o mobile; sincronizar o espelho desktop usado pela Gestão Alimentar.
- Exibir estado de sincronização e erros; evitar criar um segundo item quando o mesmo produto já existe.
- Manter IDs estáveis e migrações aditivas para os bancos existentes.

### 3. Prazo médio de reposição por insumo (média)

- O histórico atual registra entradas/saídas, mas não tem data de solicitação do pedido separada da data de recebimento. Não é possível calcular prazo real só com os movimentos existentes.
- Criar registro de pedido/reposição com produto, quantidade, fornecedor opcional, solicitado_em, recebido_em, status e responsável.
- Ao receber, gerar a entrada de estoque ligada ao pedido.
- Calcular média em dias corridos (e apresentar quantidade de pedidos usados na média); pedidos ainda abertos não entram no cálculo.
- Mostrar o indicador ao abrir o produto no desktop e em painel exclusivo do administrador no mobile. Registros antigos sem data de solicitação ficam fora da média, sem estimar datas.

### 4. Compartilhamento do aplicativo e do programa (média)

- Criar uma área de distribuição com APK e pacote desktop ZIP.
- No desktop, disponibilizar ações para abrir WhatsApp Web com mensagem pronta, abrir o cliente de e-mail com assunto/corpo e abrir a pasta contendo o arquivo para anexação.
- Usar compartilhamento nativo com anexos quando o sistema operacional oferecer uma API compatível.
- Não afirmar que `mailto:` ou link do WhatsApp anexou o arquivo: esses esquemas não aceitam anexos locais automaticamente. Sem API/credenciais de um provedor, o fallback seguro é abrir a conversa/compositor e o arquivo para o usuário anexar.
- Nunca embutir senha SMTP, token do WhatsApp ou credencial de serviço no executável.

### 5. Compilação conjunta desktop + APK (média; branch independente)

- Atualizar `Gerar_e_Abrir_NutriLab.bat` para executar os testes prioritários, compilar o APK e depois compilar o desktop.
- Falha na compilação/validação do APK deve interromper a distribuição conjunta e registrar claramente o passo que falhou.
- Validar existência, tamanho mínimo, assinatura e integridade do APK.
- Copiar o APK para `Executavel do programa/_internal/mobile/apk/saida/NutriLab-Mobile.apk`, onde o servidor empacotado poderá encontrá-lo.
- Criar ZIP do pacote desktop completo e manifesto com versões/SHA-256; manter logs separados e status final inequívoco.
- Não substituir uma keystore de distribuição por chave efêmera do CI. O build local mantém a chave persistente já usada pelo gerador.

### 6. Dois QR codes nas configurações e leitura no login (média a alta)

- QR 1: instalação/obtenção do APK, apontando para uma rota de download servida pelo próprio NutriLab (sem depender de um link temporário do CI).
- QR 2: endereço de conexão do servidor local, incluindo IP e porta atuais. O QR não deve conter usuário, senha ou token de sessão.
- Exibir nome da rede/endereço, estado do servidor e instrução de que o celular precisa estar na mesma rede Wi-Fi.
- Adicionar “Escanear QR code” na tela de login mobile e na versão web aberta em celular.
- Implementar leitura compatível com HTTP em rede local (não depender exclusivamente de `getUserMedia`, que costuma exigir contexto seguro); manter alternativa de leitura de imagem/código manual.
- No APK, persistir o endereço confirmado pelo usuário e manter opção de trocar servidor.
- Validar com Android físico, WebView e navegador mobile; o emulador sozinho não valida câmera nem rede Wi-Fi real.

### 7. Mapa compartilhado entre todas as copeiras e histórico de autoria (média a alta)

- Tratar o banco mobile do servidor como fonte central: contas conectadas ao mesmo servidor enxergam a mesma versão do mapa.
- Implementar escopo global para o perfil copa, permitindo selecionar setores, sem remover a identificação de setor/leito. A configuração administrativa deve deixar claro quem tem acesso global.
- Criar tabela append-only de auditoria de mapa: data do mapa, setor, leito, usuário, nome/perfil no momento da ação, timestamp, campos alterados, valores anteriores/novos e origem (mobile/desktop/publicação).
- Registrar apenas alterações efetivas; propostas pendentes de aprovação ficam identificadas separadamente até serem aprovadas.
- Mostrar no mapa quem atualizou por último, data e hora, e disponibilizar histórico por leito.
- Não substituir o controle atual de conflitos/aprovação: o histórico complementa a regra existente.

### 8. Indicadores mensais e anuais de atualização (média a alta)

- Agregar auditoria por usuário, mês e ano: número de alterações efetivamente aplicadas, dias ativos e setores atualizados.
- Exibir gráficos no desktop e painel do administrador mobile.
- Distinguir alterações aplicadas de propostas pendentes/recusadas; não contar salvamentos sem mudança como produtividade.
- Mostrar o período e o critério do ranking para evitar comparações enganosas.

### 9. Produto → TBCA → ficha técnica → refeição/horário (alta)

- Acrescentar vínculo TBCA ao cadastro do produto, sem remover o vínculo específico por ingrediente que já existe.
- Ao adicionar produto a uma ficha, sugerir o alimento TBCA associado e permitir confirmação/substituição.
- Reutilizar `GA_Fichas`, `GA_Ficha_Ingredientes` e `GA_Preparacoes_Dia`; permitir programar fichas por data, refeição e janela de horário.
- Associar movimentações de retirada da cozinha às janelas de refeição e às preparações programadas como **sugestão**, com revisão humana. Uma retirada não comprova consumo integral de um ingrediente.
- Preservar quantidade, unidade, fator de correção, densidade e NPU; conversões só quando a dimensão e os dados permitirem.
- Registrar a origem de cada sugestão, o movimento que a gerou e a confirmação/correção feita pelo responsável.

## Dependências entre as branches

- A branch de distribuição publica o APK no caminho esperado pelo servidor empacotado.
- A branch de funcionalidades implementa a rota de download, QR de instalação e QR de conexão, além das telas de compartilhamento.
- A integração final deve ser testada somente depois de ambas as branches terem builds próprios aprovados. Não fazer merge automático na `main`.

## Critérios mínimos de aceite

- Banco antigo migra sem perda de usuários, mapas, saldos, suplementos ou histórico.
- Duas contas de copeira conectadas ao mesmo servidor veem a mesma atualização após recarregar/sincronizar.
- Cada alteração efetiva identifica autor, perfil, setor, leito, data e hora.
- Gráficos contam apenas alterações efetivamente aplicadas e filtram mês/ano.
- Cadastro desktop atualiza o catálogo consumido pelo mobile e pela Gestão Alimentar sem duplicar itens.
- Prazo de reposição usa solicitação e recebimento reais, sem inferir datas ausentes.
- QR de instalação baixa o APK correspondente ao pacote instalado; QR de conexão configura apenas o endereço do servidor.
- O BAT encerra com erro se qualquer build ou validação obrigatória falhar; quando passa, deixa EXE, APK e ZIP disponíveis.
- Fichas automáticas são sugestões rastreáveis e exigem confirmação antes de virar consumo contabilizado.
