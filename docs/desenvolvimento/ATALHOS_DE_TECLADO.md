# Atalhos de teclado do NutriLab

Os atalhos seguem o jeito do Google Planilhas e valem em todas as telas do programa, sem precisar ligar nada.
Para ver esta lista dentro do programa, aperte **F1**.

## Campos de texto

| Atalho | O que faz |
|---|---|
| Ctrl+C | Copiar |
| Ctrl+X | Recortar |
| Ctrl+V | Colar. Uma célula copiada do Planilhas entra sem a quebra de linha; várias células viram um texto só, separado por espaço |
| Ctrl+Shift+V | Colar só o texto, sem formatação |
| Ctrl+Z | Desfazer |
| Ctrl+Y, Ctrl+Shift+Z ou F4 | Refazer |
| Ctrl+A | Selecionar tudo |
| Ctrl+Backspace | Apagar a palavra anterior |
| Ctrl+Delete | Apagar a próxima palavra |
| Ctrl+Seta esquerda ou direita | Pular de palavra em palavra (com Shift, seleciona) |

Digitar em sequência conta como uma etapa por palavra: um Ctrl+Z desfaz a última palavra, não uma letra só.
Uma pausa de mais de um segundo, mexer o cursor ou clicar no campo também começa uma nova etapa.

## Tabelas (Mapa, pacientes, suplementos)

| Atalho | O que faz |
|---|---|
| Ctrl+A | Selecionar todas as linhas |
| Ctrl+C | Copiar as linhas selecionadas. As colunas saem separadas por tabulação: ao colar no Planilhas, cada coluna cai numa célula |

## No Mapa Nutricional

| Atalho | O que faz |
|---|---|
| Enter ou F2 | Abrir o registro do leito selecionado para registrar/editar |
| Ctrl+H | Abrir o histórico do paciente selecionado |

Também é possível abrir o registro com duplo clique no leito. Os comandos só atuam quando a lista de leitos está em foco; os botões continuam disponíveis.

## Formulário do Mapa Nutricional

| Atalho | O que faz |
|---|---|
| Ctrl+S | Salvar o registro aberto (não funciona em consulta) |
| Esc | Fechar o formulário ou a busca de paciente |
| Ctrl+F | Voltar o foco para a pesquisa de pacientes |
| Enter na lista de pacientes | Usar o paciente selecionado |

A busca abre com o cursor no campo de pesquisa. Para evitar vínculos acidentais, Enter só escolhe um paciente quando uma linha está selecionada.
## Em qualquer tela

| Atalho | O que faz |
|---|---|
| F1 | Mostrar a lista de atalhos |

## Detalhes que valem saber

* **F4 refaz**, como no Planilhas. Alt+F4 continua fechando a janela (é do sistema e o programa não mexe nele).
* Campo que o programa preencheu sozinho (por exemplo, ao abrir um paciente) não volta para o texto antigo com
  Ctrl+Z: o desfazer só enxerga o que foi digitado naquele campo depois que ele recebeu o foco.
* Campos bloqueados (somente leitura) não mudam com colar, recortar nem desfazer.
* Os atalhos não alteram nenhum dado do banco por conta própria. Só mexem no texto do campo que está na tela.

## Para quem mantém o código

* Módulo: `atalhos_edicao.py`. A lógica (histórico de desfazer, limites de palavra, tratamento do texto colado,
  texto copiado das tabelas) é Python puro; a ligação com o Tk vem no fim do arquivo.
* Instalação: uma chamada a `atalhos_edicao.instalar(self)` em `AppClinica.__init__` (`main.py`). Os atalhos entram
  nas classes de widget do Tk (`Entry`, `Text`, `Treeview`), por isso valem para os campos de todas as janelas,
  inclusive as criadas depois, sem tocar nos campos um por um.
* O Tk não tem desfazer nos campos de uma linha. Cada campo ganha um `HistoricoEdicao`, criado quando recebe o foco
  e apagado quando é destruído. Nas caixas de várias linhas (`Text`) o programa liga o desfazer nativo do Tk.
* Testes: `python -m unittest tests.test_atalhos_edicao -v`. Usam widgets simulados e a lógica pura. O comportamento
  no Tk real (foco, teclado de cada computador) só se confirma abrindo o programa.
