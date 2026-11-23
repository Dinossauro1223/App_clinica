# Gráficos agrupados do Mapa

Tela **Mapa > Gráficos**. Os gráficos do mês ficam agrupados por assunto. Cada grupo mostra seus gráficos lado a lado,
numa faixa que se arrasta para o lado, ou de cima para baixo, como a tela era antes (a escolha fica em Configurações).
Os gráficos são desenhados direto na tela, com uma animação de entrada, e mostram o valor ao passar o mouse. Quem
preferir pode voltar às imagens simples, sem animação.

## Grupos

| Grupo | Gráficos | De onde vêm os números |
|---|---|---|
| Atendimentos | atendimentos por dia, perfil por dia, resumo do mês | registros do Mapa no mês |
| Dieta | consistência da dieta, características (laxativa e constipante) | `Mapa_Registros` |
| Suplementos | suplementos mais usados, módulos | `Mapa_Registros` e catálogo |
| Doenças crônicas | diabetes mellitus, hipertensão arterial, doença renal | campos `dm`, `has` e `drc` do registro |

Antes, DM, HAS e DRC apareciam misturadas com laxativa e constipante no gráfico de "características". Agora as doenças
crônicas têm grupo e gráfico próprios, e "características" fica só com o que é da dieta. Os números não mudam: só a
separação (a contagem de cada campo é a mesma, e há teste conferindo isso).

Gráfico que não estiver em nenhum grupo não some: cai em "Outros gráficos", no fim da tela.

## Como usar

- **Arrastar**: segure o botão esquerdo sobre a faixa e arraste para o lado. Ao soltar, a faixa encaixa no gráfico mais
  próximo. Um arremesso rápido passa para o gráfico seguinte.
- **Setas e pontos** no cabeçalho de cada grupo: `‹` e `›` andam um gráfico por vez; os pontos mostram onde você está.
  As setas só aparecem quando há para onde ir (em janela larga os gráficos podem caber juntos).
- **Teclado**: clique na faixa e use as setas esquerda e direita.
- **Shift + roda do mouse** (ou rolagem horizontal do touchpad): anda uma posição por vez.
- **Balão com o valor**: passe o mouse sobre uma barra, um ponto de linha ou uma fatia da rosca. Aparece, por exemplo,
  "Dia 9: 9 pacientes" ou "Oral: 56 (80%)". O balão não sai da faixa, some ao arrastar e ao sair do gráfico.
- **Animação de entrada** (estilo "Animados"): cada gráfico se desenha quando aparece. As barras crescem uma depois da
  outra e os números sobem até o valor; as linhas são traçadas da esquerda para a direita; a rosca gira a partir do topo,
  no sentido horário. Dura 0,9 segundo, acontece uma vez por gráfico e começa quando pelo menos 30% dele está à vista.
  Um gráfico que ainda não apareceu na faixa espera sem gastar processamento. Voltar a um gráfico que já apareceu não
  repete a animação.
- **Configurações**: Mapa > Gráficos > **Configurações** (ou Mapa > Configurações) > "Gráficos do mês". A tela aberta é
  redesenhada na hora, sem calcular os dados de novo.

| Opção | Valores | Chave (`Mapa_Config`) | Padrão |
|---|---|---|---|
| Disposição | "Agrupados, arrastar para o lado" / "Agrupados, de cima para baixo" | `graficos_disposicao` | lado a lado |
| Estilo | "Animados (desenhados na tela)" / "Imagens simples, sem animação" | `graficos_estilo` | animados |

Valor desconhecido ou vazio em qualquer uma das duas chaves volta para o padrão. No modo "de cima para baixo" com o
estilo animado, cada gráfico fica no meio da tela, na largura de sempre (no máximo 840 px lógicos), e a entrada de cada
um começa um pouco depois da anterior.

### Os dois estilos

| Estilo | O que é | Quando usar |
|---|---|---|
| **Animados** (padrão) | Desenhados no `tk.Canvas` com formas simples (retângulos, linhas, arcos, textos). Animação de entrada, balão com o valor, mesma letra do resto do programa. Não usam matplotlib para aparecer na tela. | Uso normal |
| **Imagens simples** | PNG feito pelo matplotlib, como na versão anterior, redimensionado para a faixa. Sem animação e sem balão. | Se o estilo animado ficar estranho ou pesado no seu computador. Precisa do matplotlib instalado |

"Salvar imagens" (exportar PNG) continua usando o matplotlib nos dois estilos, e o resultado dos arquivos não mudou. Sem
o matplotlib, a tela animada abre normalmente e o programa avisa só quando se pede imagem simples ou "Salvar imagens".

## Como o código está dividido

| Arquivo | O que tem |
|---|---|
| `mapa_graficos.py` | `GRUPOS` (assunto, cor, descrição e quais gráficos), `GRAFICOS`, `especificar_por_grupo(agg)` (só dados, sem desenho), `renderizar_grupos(grupos)` (PNG), `gerar_por_grupo(agg)`, `organizar_por_grupo(...)` |
| `graficos_nativos.py` | Python puro, sem Tk: `construir(spec, largura, progresso, medir, escala, altura_minima)` devolve a lista de formas do gráfico e a altura. Barras, linhas, rosca, barras horizontais e "sem dados" |
| `graficos_pintor.py` | `Fontes` (fonte do Tk que mede e desenha, com as medidas guardadas) e `PintorCanvas` (cria cada forma uma vez e, a cada quadro, só atualiza o que mudou) |
| `graficos_layout.py` | Contas da faixa, em Python puro: largura de cada gráfico, posições de encaixe, efeito de desaceleração, constantes da animação e dos estilos |
| `graficos_ui.py` | Widgets: `CardNativo` e `CardImagem` (os dois tipos de gráfico), `FaixaHorizontal` (tk.Canvas que se arrasta, anima a entrada e mostra o balão), `PainelGraficos` (seções, setas, pontos, modo vertical) |
| `mapa_ui.py` | Liga tudo: botão Configurações da tela, opções no diálogo, `_montar_painel`, `aplicar_config_graficos` |
| `tools/prever_graficos.py` | Desenha a cena com o Pillow (sem Tk) para conferir layout e textos com dados sintéticos |
| `tools/verificar_interface_tk.py` | Verifica a interface com Tk e CustomTkinter de verdade (atalhos e gráficos) |
| `tools/capturar_graficos_tk.py` | Tira fotos da tela dos gráficos com Tk de verdade, só com dados sintéticos (informativo, nunca falha o CI) |

Para **adicionar um gráfico**: crie a função em `mapa_graficos.py` (ela devolve a especificação, e o desenho em PNG sai
dela por `renderizar_grupos`), inclua-a em `GRAFICOS` e na lista `graficos` do grupo certo em `GRUPOS`. O teste
`test_grupos_cobrem_todos_os_graficos_sem_repetir` falha se um gráfico ficar sem grupo ou em dois. Se o gráfico for de um
tipo novo, acrescente o construtor em `graficos_nativos._CONSTRUTORES`; o teste `test_todos_os_graficos_do_mapa` passa por
todos os gráficos, em quatro larguras e três momentos da animação.

### Regras da cena (o pintor depende delas)

- A lista de formas tem **sempre a mesma estrutura** (mesmos tipos, na mesma ordem) para qualquer progresso da animação.
  Só mudam coordenadas, textos e visibilidade. Por isso o pintor cria as formas uma vez e depois só atualiza. Um teste
  confere isso em todos os gráficos e larguras.
- Todas as medidas saem em pixels da tela, já multiplicadas pela escala do Windows (125%, 150%...).
- O texto é medido com a mesma fonte que o desenha. O que a cena calculou como "cabe" é o que aparece (verificado no Tk
  real: nenhum texto passa da borda do cartão).
- Dados vazios, zeros e valores gigantes não dividem por zero: um bloco da rosca sem dados mostra "Sem dados".

### Detalhes que valem lembrar

- A faixa é um único `tk.Canvas` por grupo, rolado com `xview_moveto`. Os gráficos animados são redesenhados só quando a
  janela muda de largura (com espera de 120 ms, para não redesenhar a cada pixel); as imagens são redimensionadas
  (Pillow, LANCZOS) na mesma ocasião.
- A escala de tela do Windows (125%, 150%) é lida do CustomTkinter; o limite de 840 px por gráfico vale em pixels lógicos,
  como antes.
- O encaixe e a entrada são por tempo, não por número de quadros: em computador lento a animação perde quadros, mas dura
  o mesmo.
- Eventos de uma faixa já destruída são ignorados (o Tk pode entregar um `after` depois de a tela fechar).
- O relógio da animação para sozinho quando todos os gráficos visíveis terminaram: com a tela parada o programa não gasta
  processamento por causa dos gráficos.

## Quanto custa um quadro

O `tools/verificar_interface_tk.py` mede, com Tk de verdade, o tempo de montar a cena e atualizar as formas (campo
"cena e formas") e o de redesenhar a tela (campo "com redesenho da tela"). São 56 medições: cada um dos 8 gráficos em 7
momentos da animação. Cada medição é **um gráfico em um quadro**; um quadro em que vários gráficos animam juntos (por
exemplo os quatro primeiros ao abrir a tela) custa a soma deles. Medido no CI do GitHub em 22 e 23/11/2026 (máquinas
virtuais sem placa de vídeo, Python 3.12). Os números mudam de uma execução para outra, então vão as duas:

| Sistema | Execução | Cena e formas (média / máximo) | Com redesenho da tela (média / máximo) |
|---|---|---|---|
| Linux (Xvfb) | 45092882621 (22/11) | 0,19 ms / 1,13 ms | 0,33 ms / 1,51 ms |
| Linux (Xvfb) | 45160683633 (23/11) | 0,37 ms / 1,54 ms | 0,67 ms / 4,45 ms |
| Windows | 45092882621 (22/11) | 0,38 ms / 2,16 ms | 1,02 ms / 3,73 ms |
| Windows | 45160683633 (23/11) | 0,52 ms / 3,11 ms | 1,41 ms / 5,06 ms |

Um quadro a 60 por segundo tem 16,7 ms, então sobra muita folga mesmo com quatro gráficos animando juntos. Esses números
são de máquinas do CI e podem ser maiores em computadores mais fracos; o que a verificação garante é um limite de
segurança (nenhuma medição acima de 400 ms). A otimização para computadores lentos é a etapa seguinte (veja o ROADMAP).

Também é medido o primeiro desenho: cada uma das 4 faixas se desenha **uma vez só**, já na largura final (966 px na janela
de 1024 px do Windows e 1182 px na de 1240 px do Linux). O último desenho acontece de 135 a 147 ms (Linux) e de 200 a 265 ms
(Windows) depois de a tela abrir.

## Como foi verificado

- `tests/test_graficos_layout.py`: contas de posição, sem janela.
- `tests/test_graficos_nativos.py`: a cena de cada gráfico, sem janela (limites, estrutura igual em todo progresso, animação
  que começa vazia e termina completa, zeros e dados vazios, textos que cabem, balões, `.spec` do executável).
- `tests/test_graficos_ui.py`: a faixa e o painel com widgets e relógio simulados (arraste, encaixe, arremesso, setas,
  teclado, roda, redimensionar, entrada animada, balão, destruir durante a animação). Foi conferido também quebrando o
  código de propósito: cada defeito inserido foi pego por algum teste.
- `tests/test_ui_smoke.py`: tela de gráficos e diálogo de Configurações do Mapa, nos dois estilos e com matplotlib ausente.
- `tools/verificar_interface_tk.py` (rodado pelo `tests/test_interface_tk_real.py`): abre **Tk e CustomTkinter de verdade**,
  com dados sintéticos, simula mouse e teclado e confere onde a faixa para, se a entrada anima até o fim, se o balão
  aparece e se os textos cabem com a fonte real. Roda no CI do Windows e do Linux (Xvfb). Em máquina sem tela ele é
  pulado e diz por quê. Para ver cada verificação, rode `python tools/verificar_interface_tk.py`.
- `tools/capturar_graficos_tk.py PASTA`: fotos da tela (entrada no meio, entrada pronta, balão, segundo gráfico, de cima
  para baixo, imagem simples, escala de 150%). No CI as fotos ficam como arquivo (artefato `capturas-graficos-<sistema>`).

O que **não** é provado por teste automático: a sensação do arraste e da animação no seu monitor e a nitidez em cada
tela. Isso só se confere abrindo o programa.

## Limites conhecidos

- O `tk.Canvas` não suaviza as bordas (sem anti-aliasing no Windows nem no X11). Diagonais de linha e as bordas da rosca
  podem ter serrilhado leve, mais visível em monitor de baixa resolução. As barras e os cartões têm cantos arredondados
  (`smooth`) para suavizar o visual, e quem prefere o desenho suave do matplotlib pode usar "Imagens simples".
- Quando dois itens se sobrepõem sob o ponteiro (um ponto da linha em cima de outro, por exemplo), o balão é o do item
  cujo centro está mais perto do ponteiro.
- O balão e a animação não são mostrados no estilo "Imagens simples".
