# Auditoria visual mobile e fluxo da cozinha

**Data:** 26/11/2026  
**Base:** branch `main` no commit `75b3126f2dfc4093a28b16e9db5655e8cd67ba18`  
**Escopo:** PWA `mobile/static/index.html`, fluxo de estoque da cozinha e telas de administração.

## Problemas observados

- A aba de Cadastros/Administrador renderizava todos os formulários e painéis em sequência, aumentando rolagem e poluição visual.
- Cadastro e gerenciamento de usuários, atividade do mapa, pedidos de reposição, prazos, refeições, setores/leitos e catálogo não tinham uma hierarquia clara por assunto.
- O Mobile não apresentava uma escolha explícita de aparência (claro, escuro ou automático/sistema) acessível na entrada e durante o uso.
- Campos, cartões e botões secundários utilizavam fundos claros fixos, comprometendo contraste em tema escuro.
- A tela de estoque intitulava a área como "Estoque do almoxarifado" mesmo quando o usuário estava na cozinha ou na copa.
- Contagem de saldo e registro de movimentações estavam próximos, sem indicação de sequência operacional.

## Alterações nesta branch

1. Seletor de aparência no login e cabeçalho: **Sistema, Claro, Escuro**, preferência local persistente (sem alterar dados de conta no servidor).
2. Variáveis de tema e ajustes de cor para cartões, campos, textos, botões secundários e fundo, respeitando `prefers-color-scheme` quando a opção Sistema está ativa.
3. Blocos da tela administrativa fechados inicialmente, com títulos acionáveis, indicador de expansão e suporte a teclado/`aria-expanded`.
4. Agrupamento visual das opções em: Contas e permissões; Monitoramento e auditoria; Abastecimento e almoxarifado; Distribuição de refeições; Organização dos setores; Catálogo de insumos.
5. Nome e instruções do estoque contextualizados para almoxarifado, cozinha e copa; separação textual entre etapa 1 (conferir/atualizar saldo) e etapa 2 (registrar movimentação).
6. Teste de contrato de interface para tema, recolhimento dos grupos administrativos e identificação do fluxo de estoque.

## Acessibilidade de escala mobile (nova implementação)

- A opção **Configurações** está disponível na tela de entrada e no cabeçalho autenticado para todos os perfis.
- O controle de escala vai de 50% a 200%, com passo de 10%, e guarda a preferência local no dispositivo.
- O ajuste usa zoom de interface para aumentar/reduzir textos e controles em conjunto, favorecendo a reorganização dos ícones e componentes em vez de deixar elementos sobrepostos.
- O menu de preferências fica fechado inicialmente; pode ser expandido quando necessário.

## Roteiro de auditoria visual e validação

- [ ] Conferir login com os três temas e persistência após recarregar/abrir o app.
- [ ] Conferir legibilidade de formulários, cards, popups, chips e orientações em tema escuro e sistema.
- [ ] Testar cabeçalho e seletor de tema em telas estreitas (320–360 px) e tablets.
- [ ] Expandir/recolher cada seção administrativa; verificar foco por teclado e que conteúdo não se perde ao recolher.
- [ ] Testar cadastro/reativação/desativação de usuários, troca de senha e setor sem regressão de permissões.
- [ ] Conferir relatórios e gráficos administrativos ao abrir seus grupos.
- [ ] Conferir fluxo de cozinha: busca e categoria, atualização de saldo, recebimento do almoxarifado e registro de movimentação; validar mensagens e saldo retornado.
- [ ] Conferir papéis da copa e cozinha e garantir que os avisos de origem respeitem as regras atuais.
- [ ] Validar no Android/WebView e navegadores móveis, incluindo rolagem, safe-area, barra fixa de salvar e modal de conflito offline.

## Limitações

A inspeção do HTML/CSS e dos fluxos existentes foi feita por leitura do código. Ainda não foi possível executar o aplicativo em dispositivo real nem reproduzir localmente os testes automatizados, pois o ambiente de execução não conseguiu acessar GitHub para clonar o repositório. A validação automatizada será feita pelo CI da branch e a inspeção visual em aparelho real permanece pendente.

