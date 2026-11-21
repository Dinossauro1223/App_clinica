# Gráficos agrupados do Mapa

Tela **Mapa > Gráficos**. Os gráficos do mês ficam agrupados por assunto. Cada grupo mostra seus gráficos lado a lado,
numa faixa que se arrasta para o lado, ou de cima para baixo, como a tela era antes (a escolha fica em Configurações).

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
- **De cima para baixo**: Mapa > Gráficos > **Configurações** (ou Mapa > Configurações) > "Gráficos do mês".
  A tela aberta é redesenhada na hora, sem gerar os gráficos de novo.

O padrão é "Agrupados, arrastar para o lado". A escolha fica gravada na configuração `graficos_disposicao` (tabela
`Mapa_Config`). Valor desconhecido ou vazio volta para o padrão.

## Como o código está dividido

| Arquivo | O que tem |
|---|---|
| `mapa_graficos.py` | `GRUPOS` (assunto, cor, descrição e quais gráficos), `GRAFICOS`, `gerar_por_grupo(agg)`, `organizar_por_grupo(...)` |
| `graficos_layout.py` | Contas da faixa, em Python puro: largura de cada gráfico, posições de encaixe, efeito de desaceleração |
| `graficos_ui.py` | Widgets: `FaixaHorizontal` (tk.Canvas que se arrasta) e `PainelGraficos` (seções, setas, pontos, modo vertical) |
| `mapa_ui.py` | Liga tudo: botão Configurações da tela, opção no diálogo, `_montar_painel`, `aplicar_config_graficos` |

Para **adicionar um gráfico**: crie a função em `mapa_graficos.py`, inclua-a em `GRAFICOS` e na lista `graficos` do grupo
certo em `GRUPOS`. O teste `test_grupos_cobrem_todos_os_graficos_sem_repetir` falha se um gráfico ficar sem grupo ou em dois.

Detalhes que valem lembrar:

- A faixa é um único `tk.Canvas` por grupo, rolado com `xview_moveto`; as imagens são redimensionadas para a largura da
  faixa (Pillow, LANCZOS) e refeitas só quando a janela muda de largura (com espera de 120 ms, para não redesenhar a cada
  pixel).
- A escala de tela do Windows (125%, 150%) é lida do CustomTkinter; o limite de 840 px por gráfico vale em pixels lógicos,
  como antes.
- O encaixe é por tempo, não por número de quadros: em computador lento a animação perde quadros, mas dura o mesmo.
- Eventos de uma faixa já destruída são ignorados (o Tk pode entregar um `after` depois de a tela fechar).

## Como foi verificado

- `tests/test_graficos_layout.py`: contas de posição, sem janela.
- `tests/test_graficos_ui.py`: a faixa e o painel com widgets e relógio simulados (arraste, encaixe, arremesso, setas,
  teclado, roda, redimensionar, destruir). Foi conferido também quebrando o código de propósito: cada defeito inserido
  foi pego por algum teste.
- `tests/test_ui_smoke.py`: tela de gráficos e diálogo de Configurações do Mapa.
- `tools/verificar_interface_tk.py` (rodado pelo `tests/test_interface_tk_real.py`): abre **Tk e CustomTkinter de verdade**,
  com dados sintéticos, simula mouse e teclado e confere onde a faixa para e o que o Tk mostra. Roda no CI do Windows e do
  Linux (Xvfb). Em máquina sem tela ele é pulado e diz por quê. Para ver cada verificação, rode
  `python tools/verificar_interface_tk.py`.

O que **não** é provado por teste automático: a aparência (cores, proporções, nitidez) e a sensação do arraste no seu
monitor. Isso só se confere abrindo o programa.
