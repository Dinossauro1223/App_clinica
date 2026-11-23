# Identidade visual NutriLab

A identidade é mantida em SVGs editáveis e componentes independentes. A tela inicial não deve usar a composição achatada como cenário: ela é montada no Canvas a partir de PNGs RGBA renderizados individualmente, preservando a transparência e a ordem de profundidade.

## Fontes vetoriais

- `nutrilab_identidade.svg`: referência da composição geral.
- `nutrilab_icone.svg`: símbolo do ícone do executável.
- `componentes/`: arco, assinatura, DNA, FACISA/UFRN, folhas, haste, frasco, maçã, wordmark, título e decoração inferior.
- `folhas.svg`: contém cinco folhas com IDs próprios (`folha-1` a `folha-5`) para extração e animação independentes.

## Renderização e execução

Execute `python tools/gerar_identidade_visual.py` antes de compilar. O gerador cria:

- `nutrilab.ico` e PNGs de identidade legados;
- `renderizados/*.png`: camadas transparentes independentes;
- `renderizados/folhas.json` e `folha_1.png` a `folha_5.png`: folhas recortadas com alpha e limites originais para animação.

O fluxo de compilação Linux do GitHub gera os vetores rasterizados e transfere o artefato ao job Windows. A compilação local requer as dependências de `requirements-build.txt`.

A tela inicial usa um Canvas: cenário e ilustrações ficam atrás; wordmark e assinaturas ficam em primeiro plano; opções e créditos não usam painéis sólidos. A janela abre maximizada, sem fullscreen exclusivo.

A composição é uma reconstrução aproximada da referência visual. Textos dependem de Arial/Helvetica ou Segoe UI; a assinatura institucional é aproximada e deve ser substituída por ativo oficial quando disponível. O PNG original `welcome_nutrilab.png` permanece preservado para compatibilidade, mas não é usado como cenário da nova tela.
