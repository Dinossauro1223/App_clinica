# ADR-0009: Gráficos do Mapa desenhados na tela (animados), com a imagem como opção

- **Estado:** Aceita (modo local). A aparência e a sensação do arraste e da animação no monitor do usuário ainda precisam ser conferidas abrindo o programa; os testes automáticos não provam isso.
- **Data:** 22/11/2026 (America/Recife); revisada em 23/11/2026 depois de conferir a `main`.
- **Fase do ROADMAP:** fora das fases (melhoria de uso da tela de gráficos do Mapa, pedida em 20/11/2026). Continua o trabalho dos pull requests #8 (atalhos de edição) e #9 (gráficos agrupados).
- **Branch:** `feat/graficos-animados-2026-11-23`.
- **Histórico:** uma primeira versão dos gráficos animados entrou na `main` pelo pull request #74 (branch de teste `feat/scratch-animados-2026-11-22`), no estado do primeiro commit dela. Ficaram de fora a espera do primeiro desenho (item 7 abaixo), as verificações com Tk de verdade mais completas, as fotos da tela do CI e esta documentação. Esta ADR e o pull request dela completam essa entrega.

## Contexto (observado no código real)

1. Depois do pull request #9, cada gráfico do Mapa era uma imagem PNG feita pelo matplotlib e colocada numa faixa do Tk. Imagem pronta não anima. Para animar com matplotlib seria preciso refazer a figura muitas vezes por segundo, e uma figura leva dezenas de milissegundos para ser gerada, então a animação ficaria pesada justamente em computador fraco.
2. O pedido do usuário foi: gráficos mais bonitos de ver, com animação, e uma versão de alto desempenho "sem comprometer o funcionamento visual", que funcione rápido em qualquer computador.
3. O ambiente de desenvolvimento não tem `tkinter`, nem `customtkinter`, nem acesso a instalar pacotes. Tk de verdade só existe no CI do GitHub (Windows e Linux com Xvfb). Isso pesa na escolha: a solução precisa ser testável sem janela.
4. A tela abre vários gráficos de uma vez (8 gráficos em 4 grupos), e cada um precisa se redesenhar quando a janela muda de tamanho ou a escala do Windows é 125% ou 150%.

## Decisão

1. **Separar o que desenhar de onde desenhar.** `graficos_nativos.py` (Python puro) recebe a especificação do gráfico (`mapa_graficos`), a largura, o progresso da animação de 0 a 1 e uma função que mede texto, e devolve uma **lista de formas simples** (retângulo, polígono, linha, texto, círculo, arco) com a altura do gráfico. `graficos_pintor.py` desenha essa lista num `tk.Canvas`. Como a cena não depende de Tk, quase tudo é testado sem janela.
2. **A lista de formas tem sempre a mesma estrutura**, para qualquer progresso (mesmos tipos, na mesma ordem). Só mudam coordenadas, textos e visibilidade. Por isso o `PintorCanvas` cria cada forma **uma vez** e, a cada quadro, só manda ao Tk o que mudou. Um teste confere essa regra em todos os gráficos, em quatro larguras e três momentos da animação.
3. **Animação por tempo, não por número de quadros.** A entrada dura 0,9 s (`DURACAO_ENTRADA`); em computador lento perdem-se quadros, mas a duração é a mesma. Cada gráfico começa um pouco depois do anterior (0,12 s) e só quando pelo menos 30% dele está à vista. O relógio da animação para sozinho quando tudo terminou, então a tela parada não gasta processamento por causa dos gráficos.
4. **Balão com o valor** ao passar o mouse (barra, ponto de linha, fatia). O texto vem da própria especificação, e a escolha do item é por proximidade do ponteiro.
5. **O matplotlib deixa de ser necessário para mostrar a tela.** Ele continua sendo usado para "Salvar imagens" (PNG, igual ao de antes) e para o estilo "Imagens simples", e é importado só nessa hora. Sem ele, a tela animada abre normalmente.
6. **Duas opções em Configurações do Mapa**, gravadas em `Mapa_Config`: `graficos_estilo` ("animado", padrão, ou "imagem") e `graficos_disposicao` (já existia). Valor desconhecido volta ao padrão. A tela aberta é redesenhada na hora, sem recalcular os dados.
7. **A faixa espera um instante antes do primeiro desenho** (`ESPERA_INICIAL_MS`, 50 ms) e desenha uma vez só, na última largura que o Tk avisou. Motivo, visto no Tk real (CI do Windows e do Linux): o canvas recém-criado avisa primeiro a largura provisória (378 px no Windows, 394 px no Linux) e só uns instantes depois a largura final. Sem a espera, os gráficos apareciam estreitos por cerca de 150 ms e depois pulavam. Depois de desenhada, mudanças de largura da janela continuam sendo agrupadas com 120 ms de espera.
8. **A verificação com Tk de verdade faz parte do CI.** `tools/verificar_interface_tk.py` abre CustomTkinter e Tk de verdade, com dados sintéticos, simula mouse e teclado e confere arraste, encaixe, entrada animada, balão, textos dentro dos cartões, redimensionar durante a entrada, escala de 150% e destruir a tela no meio da animação. O resultado aparece no log do CI. `tools/capturar_graficos_tk.py` tira fotos da tela (informativo: nunca falha o CI).

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Continuar com PNG do matplotlib e trocar por vários quadros ou GIF | Cada quadro custa dezenas de milissegundos para gerar e ocupa memória; fica pesado justamente no computador fraco |
| `matplotlib.animation` com `FigureCanvasTkAgg` | Redesenha a figura inteira a cada quadro; depende do backend TkAgg (que o programa não usa); não combina com a faixa que arrasta |
| Biblioteca de gráficos externa (plotly, pyqtgraph, Kivy) | Dependência nova e pesada, sem como instalar nem testar aqui, e aumenta o executável |
| Desenhar cada quadro com o Pillow (superamostragem) e trocar a imagem | Bordas mais suaves, mas o custo por quadro é maior; fica como possível melhoria da etapa de desempenho, se a medição permitir |
| Recriar todas as formas a cada quadro | É o jeito mais simples e o mais lento; o Tk gasta a maior parte do tempo criando itens |
| **Canvas do Tk com cena em Python puro (escolhida)** | Sem dependência nova; atualizar coordenadas é barato; a geometria é testável sem janela |

## Consequências

- **Bom:** animação fluida com custo baixo por quadro. Medido com Tk de verdade no CI do GitHub (máquinas virtuais sem placa de vídeo), em 56 medições (8 gráficos em 7 momentos da animação, cada medição é um gráfico em um quadro). Em duas execuções (45092882621 e 45160683633), cena e formas ficaram em média entre 0,19 e 0,37 ms no Linux e entre 0,38 e 0,52 ms no Windows (máximo de 3,11 ms); com o redesenho da tela, entre 0,33 e 0,67 ms no Linux e entre 1,02 e 1,41 ms no Windows (máximo de 5,06 ms). Um quadro a 60 por segundo tem 16,7 ms, então mesmo quatro gráficos animando juntos cabem com folga.
- **Bom:** os testes cobrem a geometria sem Tk e a interface com Tk real no CI.
- **Limite:** o `tk.Canvas` não suaviza bordas no Windows nem no X11. Diagonais de linha e as bordas da rosca ficam levemente serrilhadas. Atenuação: cantos arredondados (`smooth`), linhas mais grossas, e a opção "Imagens simples" para quem preferir o desenho suave do matplotlib.
- **Limite:** o texto usa a fonte do CustomTkinter, e as medidas vêm dessa mesma fonte; se o sistema não tiver a fonte, o Tk escolhe outra e a medida acompanha.
- **Custo:** mais código para manter (cena, pintor, animação) do que uma imagem pronta. Mitigado pela separação e pelos testes.
- **Executável:** `graficos_nativos` e `graficos_pintor` entram em `hiddenimports` do `app_clinica.spec`, e um teste confere isso.
- **Dados:** nada muda no banco. Só uma chave nova de configuração (`graficos_estilo`), que não precisa de migração.
- **Rollback:** em Configurações do Mapa, escolher "Imagens simples, sem animação" volta ao desenho do pull request #9. Para voltar de vez no código, reverter o commit desta etapa (as funções que geram o PNG não foram removidas).

## Como verificar

1. `python -m unittest discover -s tests -v` (os testes de Tk real são pulados onde não há tela).
2. No CI do GitHub, abrir o passo "Testes" e procurar `--- saída de tools/verificar_interface_tk.py ---`: cada verificação aparece como `[OK]`, `[FALHA]` ou `[PULOU]`, com o tempo, e as linhas `[INFO]` trazem o custo de um quadro e quantas vezes cada faixa se desenha ao abrir.
3. As fotos da tela ficam no artefato `capturas-graficos-<sistema>` da execução (guardadas por 7 dias).
4. No computador de uso: abrir **Mapa > Gráficos**, arrastar uma faixa, passar o mouse numa barra, trocar o estilo e a disposição em Configurações.

## Pendências

- Conferir no monitor e no computador de uso a nitidez e a fluidez (o CI roda sem placa de vídeo e sem monitor).
- Etapa seguinte do ROADMAP: desempenho em computadores mais fracos (medir, adaptar a animação ao tempo de cada quadro e deixar a escolha em Configurações).
- Suavização das bordas (anti-aliasing), só se a medição mostrar que cabe no custo.

## Referências

Não houve dúvida bibliográfica nesta etapa (é interface). A documentação de uso está em [`GRAFICOS_AGRUPADOS.md`](../desenvolvimento/GRAFICOS_AGRUPADOS.md).
