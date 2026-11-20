# ADR-0006: Condutas de alta na consulta (catálogo versionado, confirmação pela nutricionista e folha do paciente)

- **Estado:** Aceita (modo local). O conteúdo clínico do catálogo ainda precisa de homologação pela nutricionista responsável antes de uso assistencial. Complementa as ADR-0001 (migrações) e ADR-0004 (serviço único de banco).
- **Data:** 17/11/2026 (America/Recife). Revisão de QA, migração 3 e correções em 19/11/2026 (seção "Revisão de QA e correções"). Correção do CI do GitHub em 19/11/2026 (seção "CI do GitHub"). Documentação do CI atualizada em 20/11/2026.
- **Fase do ROADMAP:** 4 (conduta e documento imprimível na consulta), apoiada no Mapa da Fase 1
- **Branch:** `feat/condutas-de-alta` (criada a partir da `main` no commit `b135c90`), integrada à `main` pelo pull request #5 (`3c34ae1`). A correção do CI foi a branch `fix/ci-testes-portateis-2026-11-19`, integrada pelo pull request #6 (`43a117d`).

## Contexto (observado no código real)

1. A tela de consulta (`tela_consultas`, em `main.py`) guardava a conduta só como texto livre (`txt_conduta`). Não havia lista de orientações de alta, nem versão em linguagem leiga para o paciente levar para casa, nem lembrete de que algo ficou pendente antes da alta.
2. O Mapa Nutricional (`mapa_db.py`) guardava a via da dieta e as características DM, HAS, laxativa, constipante e DRC, mas não doença respiratória nem tuberculose. A marca DRC não informa estágio, diálise nem tratamento conservador.
3. O banco local tinha só a migração 1 (baseline). Nenhuma tabela guardava documentos de alta.
4. O pedido do projeto (14/11/2026) foi: levar as revisões (alimentação enteral, doenças respiratórias com ressalvas para tuberculose, doenças renais) para a parte clínica da consulta como condutas que a nutricionista confirma antes da alta; textos compactos para poupar folhas, com versão para o paciente leigo e versão integral para a nutricionista; possibilidade de corrigir o arquivo que será entregue; imprimir e exportar em PDF; lembrar sempre; condutas ligadas a cada paciente pelas doenças relatadas no Mapa.
5. As regras do projeto (`CLAUDE.md`, `AGENTS.md` e o ROADMAP, Fase 4, "Não pode ser feito") proíbem gerar ou alterar conduta automaticamente, sobrescrever documento assinado e inventar dose, ponto de corte ou composição.
6. O conteúdo vem de três revisões de literatura, registradas nas entradas `REF-2026-11-17-001` a `REF-2026-11-17-004` do [diário bibliográfico](../desenvolvimento/DIARIO_DUVIDAS_BIBLIOGRAFICAS.md). As quatro estão como **parcialmente resolvidas**, com as lacunas escritas.

## Decisão

1. **Catálogo em arquivos JSON versionados** (`condutas_alta/enteral.json`, `respiratorias_tb.json`, `renal.json`: 20 condutas). Cada conduta tem código, título, título para o paciente, gatilhos, texto técnico, lista "conferir antes de confirmar", texto para o paciente e chaves de fonte que apontam para referências ABNT com link e data de acesso. `condutas_alta.carregar_catalogo` valida tudo e lista todos os problemas de uma vez: conduta sem fonte, fonte inexistente, gatilho desconhecido, código repetido, referência sem "Disponível em:" ou "Acesso em:". Cada grupo tem `versao` e `revisado_em`. A pasta é embutida no executável (`app_clinica.spec`).
2. **As doenças vêm do Mapa.** Os gatilhos usam `via:<via>`, os campos de `CARACTERISTICAS` (dm, has, drc e outros) e `cond:<código>`. Vale o registro mais recente do paciente no Mapa. Conduta sem gatilho só entra se a nutricionista a adicionar. O Mapa ganhou a coluna `condicoes` (códigos `resp` e `tb`, em texto separado por vírgula) e as caixas "Outras doenças relatadas" no formulário do registro. A lista nova (`mapa_db.CONDICOES`) fica fora de `CARACTERISTICAS` de propósito, porque `CARACTERISTICAS` define as colunas do impresso, do Excel e dos gráficos do Mapa. A coluna é criada por `ALTER TABLE ... ADD COLUMN` em `mapa_db.inicializar` quando falta, sem tocar nos dados existentes.
3. **O catálogo só sugere.** Toda conduta sugerida nasce pendente. A nutricionista a **confirma** (podendo corrigir o texto do paciente) ou marca **"não se aplica"** com motivo obrigatório. Só as confirmadas entram na folha do paciente. O que depende da prescrição (dose, volume, meta de proteína, líquidos) fica em branco ("______") no texto do paciente, para a nutricionista preencher ou escrever à mão. Os números com fonte aparecem só no texto técnico, junto da citação.
4. **A decisão guarda uma cópia.** `Condutas_Alta_Itens` grava título, textos, lista de conferência, referências e versão do catálogo no momento da decisão. Se o catálogo mudar depois, a tela avisa "catálogo atualizado depois", em vez de trocar o texto já decidido.
5. **Documento entregue é imutável, no banco.** A migração 2 (`condutas_alta`) cria `Condutas_Alta_Docs` e `Condutas_Alta_Itens`, dois índices e cinco gatilhos que abortam INSERT, UPDATE e DELETE de itens, e UPDATE e DELETE do documento, quando ele está `entregue`. A migração 3 (`condutas_alta_travas_contra_substituicao`) soma cinco travas que a revisão de QA mostrou faltar: o SQL `REPLACE INTO` (e `UPDATE OR REPLACE`) apaga a linha em conflito sem disparar o gatilho de DELETE, e um item de rascunho podia ser movido para dentro de um documento entregue. Corrigir uma folha entregue é criar uma nova versão (`substitui_id_doc`), nunca alterar a antiga. Entregar exige nome da nutricionista, pelo menos uma conduta confirmada e nenhuma conduta aplicável pendente. As migrações têm `down`; o executor faz backup antes de aplicar (`pre-migracao-vN`, com N a versão de destino, hoje 3) e antes de reverter (`pre-reversao-para-vN`). A migração 2 não foi editada: o executor guarda o checksum de cada migração aplicada, então a correção entrou como migração nova. Não há chave estrangeira para `Pacientes`, porque essa tabela pertence ao esquema legado.
6. **Duas saídas em PDF (A4) do mesmo documento.** A folha do paciente traz só as condutas confirmadas, em linguagem leiga, fonte 10, mais o recado opcional da nutricionista. O relatório do nutricionista traz todas as condutas, com situação (confirmada, não se aplica, pendente), texto técnico, lista de conferência, texto que vai ao paciente, motivo de "não se aplica" e referências, em fonte 9, marcado como uso interno. A quebra de linha e a paginação são feitas em `condutas_alta_export.py` com as mesmas primitivas que `mapa_export.py` usa (`text`, `rect`, `line`, `get_string_width`), o que permite testar o layout com um PDF simulado. A janela mostra quantas páginas a folha do paciente terá.
7. **Imprimir.** `imprimir_pdf` usa o verbo "print" do leitor de PDF padrão no Windows (`os.startfile`) e, se ele não aceitar, abre o PDF para imprimir com Ctrl+P. No Linux usa `lp` e, se faltar, abre o arquivo. As mensagens dizem "enviado" ou "aberto", nunca "impresso com sucesso", porque o programa não consegue confirmar que a impressora imprimiu.
8. **Sempre lembrar.** (a) Painel laranja fixo na tela de consulta com as doenças relatadas e o número de condutas pendentes. (b) Depois de salvar a evolução, aviso com opção de abrir as condutas. (c) No Mapa, botão e coluna "Condutas de alta", linha em laranja e contagem acima da lista. (d) Ao remover do Mapa (alta ou transferência) um paciente com conduta pendente, o programa pergunta se a nutricionista quer abrir as condutas antes.
9. **Alcance.** Só o aplicativo desktop. O servidor e o app do celular não foram alterados e não têm rota para esse módulo (nenhuma referência a `condutas_alta` em `mobile/` nem em `integracao_mobile.py`). O controle por perfil de usuário continua dependendo da Fase 3.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Textos das condutas dentro do código Python | Revisar a bibliografia exigiria mexer em código. No JSON, o diff do Git mostra texto, versão e fonte. |
| Catálogo no banco, editável pela tela | Perde o histórico de revisão no Git e permite mudar texto clínico sem registrar a fonte. Pode ser uma evolução, com perfil de coordenação (Fase 3). |
| Gerar a conduta e entregar direto | Proibido pelo `CLAUDE.md` (não produzir nem alterar conduta automaticamente). |
| Um texto só para paciente e profissional | O paciente leigo não precisa de citações nem de números técnicos, e o profissional precisa das fontes. O pedido foi justamente separar. |
| Colocar `resp` e `tb` em `CARACTERISTICAS` | Mudaria as colunas do impresso, do Excel e dos gráficos do Mapa. |
| Tabela filha `Mapa_Registro_Condicoes` | Mais normalizada, mas exige mexer no esquema do Mapa e na cópia diária. A coluna aditiva é simples e reversível. Reavaliar se a lista de doenças crescer. |
| Imutabilidade só no código do aplicativo | Qualquer outro caminho de escrita ignoraria a regra. Os gatilhos valem para qualquer conexão ao arquivo. |
| `multi_cell` do fpdf2 para quebrar o texto | A quebra dependeria do fpdf real, que não roda no ambiente de teste. Com quebra própria o layout é testável; o custo é manter esse código. |
| Biblioteca de impressão própria | Dependência nova e específica de sistema operacional. O leitor de PDF padrão já conhece a impressora configurada. |

## Consequências

- Ao abrir o programa, as migrações 2 e 3 rodam (com backup antes). Bancos novos e antigos recebem as duas tabelas e as dez travas, e o Mapa ganha a coluna `condicoes` se faltar. Quem já estava na versão 2 recebe só a 3, sem mudar nenhum dado (testado, com folha entregue).
- **Reverter para a versão 1 apaga as tabelas de condutas.** Folhas já entregues ficam só no backup `pre-reversao-para-v1`. Reverter só a 3 (para a versão 2) tira as cinco travas e mantém tabelas e dados. A coluna `condicoes` do Mapa não é removida (é aditiva e inofensiva) e continua sendo reconhecida se a migração for aplicada de novo.
- A cópia do mapa do dia anterior leva `condicoes` junto (testado).
- Cada revisão clínica do texto muda o JSON (`versao`, `revisado_em`), o diário bibliográfico e, se preciso, os testes do catálogo. Esses testes verificam o que a máquina consegue: gatilhos, fonte em cada conduta, nenhum número de dose no texto do paciente, citações sem ambiguidade, fonte registrada no diário. Eles **não substituem** a conferência clínica.
- O PDF do paciente leva nome e data. Ele é gerado sob demanda, em `arquivos_pacientes/paciente_<id>` (pasta de dados do usuário, fora do Git). Nenhum PDF, banco ou dado real entra no repositório, e os testes usam pacientes sintéticos.
- O `.spec` passa a embutir `condutas_alta/`; sem essa pasta o executável não abre as condutas (um teste confere a linha do `.spec`).
- Testes existentes foram ajustados, sem enfraquecê-los: versão final do esquema e lista de tabelas (`test_db_migracoes`, `test_diagnostico_banco`, `test_integracao_banco`), contagem de pastas gravadas fora do bundle em `main.py` (2 para 3, por causa de `pasta_condutas_alta`) e fakes de interface (`test_ui_smoke`).
- Correção de defeito antigo encontrado no caminho: `tela_mobile` ainda abria `os.path.join(get_base_path(), 'clinica.db')`, o caminho que a ADR-0004 já trocou nos outros pontos do `main.py`. Agora usa `caminho_do_banco()`.

## Revisão de QA e correções (19/11/2026)

**Como foi feita.** As tentativas de usar um agente independente de QA foram cortadas pelo limite de uso da conta, sem relatório. Os roteiros de sondagem que esses agentes deixaram escritos foram executados pelo agente integrador (Linux, Python 3.13), que também leu o código. Portanto é uma revisão por sondagens executadas pelo integrador, **não** uma revisão completa e independente. O relatório está nos arquivos de trabalho da sessão e não entra no Git.

| Achado | O que acontecia | Estado |
|---|---|---|
| A1 | `REPLACE INTO Condutas_Alta_Docs` com o `id_doc` de uma folha entregue a trocava por um rascunho, sem erro. O SQLite não dispara o gatilho de DELETE no `REPLACE` quando `recursive_triggers` está desligado (o padrão). | **Corrigido** na migração 3: travas antes de INSERT e antes de UPDATE de `id_doc`. |
| A2 | `UPDATE Condutas_Alta_Itens SET id_doc = <folha entregue>` movia um item de rascunho para dentro dela, porque o gatilho só olhava a folha de origem. A mesma falha existia para trocar o `id_item` e para `REPLACE` pela chave do item. | **Corrigido** na migração 3, com três travas no item. |
| A3 | Paciente sem nenhum registro no Mapa aparecia como "Doenças relatadas no Mapa: nenhuma" e "Nenhuma conduta sugerida pelas doenças do Mapa". Dado ausente virava "nenhuma doença". | **Corrigido.** Tela, janela e relatório do nutricionista dizem "paciente sem registro no Mapa, o programa não sabe as doenças dele" e pedem para conferir o prontuário. Registro sem doença marcada continua dizendo "nenhuma". |
| A4 | Paciente com dois registros no mesmo dia (troca de leito): a ordem era indefinida, a janela podia usar o registro antigo e a coluna do Mapa discordar da janela. | **Corrigido.** Desempate por `id_registro` (vale o criado por último), na janela e na coluna. Limite: o Mapa não guarda a hora da transferência, então "criado por último" é o critério. |
| A5 | Reverter a migração 2 apaga as tabelas de condutas. | **Aceito, como documentado.** Há backup antes de reverter, e é o próprio objetivo do `down`. A migração 3 pode ser revertida sem perder dados. |
| A6 | Registro do Mapa sem paciente ligado mostrava ao usuário o erro técnico "NOT NULL constraint failed". | **Corrigido.** Mensagem clara no módulo e aviso na tela do Mapa. |
| Outro | `desfazer` numa folha entregue não fazia nada e não avisava. | **Corrigido.** Mostra a mesma mensagem de folha entregue. |

Efeitos a conhecer: a migração 3 só cria travas, não muda dados (testado em banco que já estava na versão 2 com folha entregue). A tela de condutas não chama mais nada que dependa do comportamento antigo de `desfazer`, porque os botões de desfazer só aparecem em rascunho.

**Exclusão de paciente (verificada depois da revisão, em 19/11/2026).** `main.py` apaga só a linha de `Pacientes`: folhas de alta, registros do Mapa e as demais tabelas continuam no banco, sem ligação (comportamento antigo do programa, que não foi alterado). Como `id_paciente` é `AUTOINCREMENT` nas duas rotinas que criam a tabela (`setup_db.py` e `mapa_db.py`), o número de um paciente excluído nunca é dado a outro, então ninguém herda a folha de outra pessoa (teste novo). Sem `AUTOINCREMENT` o SQLite reaproveitaria o número, o que foi conferido à parte. O banco real do hospital não está no repositório e não foi conferido: se ele tiver sido criado por uma versão muito antiga do programa, vale rodar `SELECT sql FROM sqlite_master WHERE name = 'Pacientes'` e ver se o texto traz `AUTOINCREMENT`.

**Não foi verificado nesta revisão:** vazamento de conteúdo entre a folha do paciente e o relatório da nutricionista além do que os testes de PDF já conferem; segurança do nome do arquivo PDF; alcance pelo servidor e pelo celular, que só foi conferido por busca de texto (nenhuma referência a `condutas_alta` fora do desktop); janelas reais, PDF real, impressora e executável.

## CI do GitHub: o que falhou no pull request #5 e como foi corrigido (19/11/2026)

**O que aconteceu.** O pull request #5 foi integrado à `main` (`3c34ae1`) com o CI do GitHub vermelho (execução 44616635455, commit `61fbbb2`). No Windows, 327 testes rodaram com 1 falha e 34 erros. No Linux, 323 rodaram com 2 erros (a classe `TestExportacao` do Mapa nem começou, por isso 4 testes a menos). Os envios anteriores da branch também estavam vermelhos, e a `main` já estava vermelha antes desta entrega (`f79eabe`, execução 43725431067, com falhas de `test_mapa` e da exportação pelas telas). O "327 testes OK" que esta ADR e o ROADMAP traziam valia só para a máquina Linux onde a suíte foi rodada: o resultado do CI nos dois sistemas não tinha sido conferido antes do pull request.

As causas estavam nos testes, não na lógica das condutas:

| # | Causa | Efeito no CI | Correção |
|---|---|---|---|
| 1 | `tests/fake_fpdf.py` (o PDF simulado) abria a fonte num caminho fixo do Linux | Windows: 34 testes (32 das condutas de alta, o PDF simulado do Mapa e `test_exportar_pelas_telas`) quebravam com `OSError: cannot open resource` ou ficavam sem o PDF gravado | Procura a Liberation Sans (Linux), a Arial (Windows) e a DejaVu; se nenhuma existir, usa a fonte padrão do Pillow |
| 2 | `tests/test_mapa.py` gravava numa pasta fixa da máquina de desenvolvimento | Linux: 2 erros (`PermissionError` ao criar a pasta; a classe `TestExportacao` não rodou) | Pasta temporária, apagada no fim |
| 3 | `tests/test_mapa.py` apagava o banco de teste com a conexão SQLite ainda aberta | Windows: 1 erro (`PermissionError`, arquivo em uso por outro processo) | A conexão é fechada ao fim do bloco |

**Correção no programa, não só nos testes.** O log do CI mostrou que o fpdf2 real emitia `DeprecationWarning: Substituting font arial by core font helvetica ... will soon be removed` nas quatro chamadas de `set_font("Arial", ...)` de `condutas_alta_export.py`. Elas passaram a usar a constante `FONTE = "Helvetica"`, que é o nome oficial da mesma fonte. O Mapa (`mapa_export.py`, anterior a esta entrega) tem o mesmo apelido e não foi alterado.

**Testes novos.** `tests/test_portabilidade_testes.py` (4 testes) impede que voltem a pasta fixa, a busca de fonte só do Linux (inclui o caso de máquina sem nenhuma fonte conhecida) e o nome "Arial" no PDF das condutas. Cada guarda foi conferida desfazendo a correção numa cópia do repositório, e o teste correspondente falhou nos 3 casos.

**Resultado.** Branch de correção, execução 44656174143 (commit `6998453`): Windows com 331 testes OK em 267,7 s e Linux com 331 OK em 26,8 s, 1 pulado em cada (conferência visual em PNG). Depois do pull request #6, a `main` em `43a117d` (execução 44661288651): Windows com 331 OK em 194,3 s e Linux com 331 OK em 22,1 s. Nos registros dos dois sistemas não há mais aviso de descontinuação vindo de `condutas_alta_export.py`.

**O que isso prova e o que não prova.** Prova que a suíte inteira passa nos runners do GitHub (Windows e Linux, Python 3.12, dependências fixadas) e que o fpdf2 real (2.8.9) gera os dois PDFs das condutas. As asserções de layout passaram com a Arial no Windows e com a Liberation Sans no Linux. Não prova a aparência do PDF (o teste com fpdf2 real só confere o cabeçalho `%PDF`, o tamanho e o número de páginas), as janelas reais do CustomTkinter (os testes usam widgets simulados), a impressão real nem o executável.

**Regra daqui para frente.** Rodar a suíte no Linux não basta: depois do push, conferir o resultado do CI nos dois sistemas antes de dizer que a entrega passou (`AGENTS.md`, seção 8).

## Como verificar

```bat
python -m unittest tests.test_condutas_alta tests.test_condutas_alta_catalogo tests.test_condutas_alta_export tests.test_condutas_alta_ui -v
python -m unittest tests.test_portabilidade_testes -v
python -m unittest discover -s tests -v
python condutas_alta.py
```

`python condutas_alta.py` valida o catálogo e imprime "Catálogo ok: 20 condutas em 3 grupos". O CI do GitHub roda a suíte inteira no Windows e no Linux a cada envio para `main`, `feat/**`, `fix/**` ou `docs/**` e a cada pull request (aba Actions do repositório).

Evidências locais (Linux, Python 3.13; o alvo do projeto é 3.12). O resultado no CI está na seção anterior.

| Módulo de teste | Testes | Resultado |
|---|---|---|
| `test_condutas_alta` (núcleo, banco, imutabilidade, travas da migração 3, sessão, Mapa) | 55 | OK |
| `test_condutas_alta_catalogo` (conteúdo, gatilhos, fontes, `.spec`) | 20 | OK |
| `test_condutas_alta_export` (PDF com simulador, impressão com chamadas simuladas) | 24 | OK, 2 pulados |
| `test_condutas_alta_ui` (janelas com widgets simulados) | 53 | OK |
| `test_portabilidade_testes` (pasta fixa, fonte do PDF simulado, nome "Arial") | 4 | OK |
| Suíte inteira (`discover -s tests`) | 331 | OK, 2 pulados |

Depois da revisão de QA (19/11/2026) a suíte passou de 312 para 327 testes, e para 331 com os testes de portabilidade. Cada teste novo da revisão de QA foi conferido de trás para a frente: desfazendo a correção numa cópia do repositório, o teste correspondente falhou nas 8 tentativas (travas da migração 3, desempate no mesmo dia, coluna do Mapa, aviso ao desfazer, paciente sem cadastro, frase "sem registro", aviso na tela do Mapa e texto de status).

O que **não** foi executado, e por quê:

- Localmente, os dois testes pulados são o PDF gerado pelo fpdf2 real e a gravação de PNG para conferência visual. O fpdf2 não está instalado neste ambiente e a instalação de pacotes está bloqueada. A suíte inteira rodou com um pacote `fpdf` vazio no `PYTHONPATH`, só para o import de `test_integracao_banco` (nada disso entra no Git). O teste com fpdf2 real roda no CI do GitHub e passa nos dois sistemas; só a conferência visual em PNG continua pulada.
- As janelas reais do CustomTkinter (os testes usam widgets simulados), a restauração da posição de rolagem, a impressão real no Windows (`os.startfile`) e o build do PyInstaller também não foram exercitados.

## Pendências

1. **Homologação clínica** do texto de cada conduta pela nutricionista responsável. Até lá, o programa só sugere e a nutricionista decide.
2. **Autoria individual:** nome e CRN são digitados na janela das condutas. Não há usuário autenticado (Fase 3), assinatura nem carimbo, e não se afirma validade jurídica.
3. **Lacunas de conteúdo registradas no diário:** doença respiratória além da DPOC; interação de alimentos com isoniazida; lista de sintomas de neuropatia; líquidos, fósforo, energia e, em diálise, tudo além da proteína (a proteína no diabetes com doença renal e em diálise veio da KDIGO 2022, `REF-2026-11-18-001`); frequência de pesagem; duração da piridoxina; texto original da KDOQI 2020 (não lido); itens do Manual de Recomendações para o Controle da Tuberculose de 2019 lidos uma vez só e marcados no texto.
4. **Alcance clínico do Mapa:** só há "doença respiratória" e "tuberculose" como doenças novas, e DRC sem estágio. A nutricionista descarta o que não se aplica ("não se aplica", com motivo).
5. **Imutabilidade por gatilho** protege contra qualquer escrita pelo aplicativo e contra os comandos de SQL direto que a revisão de QA testou (incluindo `REPLACE`), mas quem abre o arquivo `.db` com acesso direto pode remover os gatilhos (`DROP TRIGGER`). A proteção forte depende da API e do banco central (Fase 3).
6. A suíte já roda no Windows do CI, com fpdf2 real. Falta o fluxo completo no Windows do projeto, com janelas reais: olhar um PDF gerado e imprimir uma folha de teste em papel.
7. Revisão do `.spec`: ele ainda aponta para o caminho fixo do `customtkinter` da máquina do desenvolvedor (pendência já registrada na ADR-0005).

## Referências

- Regras do projeto: `CLAUDE.md`, `AGENTS.md` (seções 5 e 6) e `ROADMAP.md` (Fase 4).
- Fontes clínicas do catálogo: [diário bibliográfico](../desenvolvimento/DIARIO_DUVIDAS_BIBLIOGRAFICAS.md), entradas `REF-2026-11-17-001` (alimentação enteral), `-002` (tuberculose), `-003` (doença respiratória), `-004` (doença renal) e `REF-2026-11-18-001` (doença renal: proteína no diabetes e na diálise, KDIGO 2022), cada uma com autor, ano, título, link e data de acesso.
- Nenhuma fonte externa de engenharia de software foi consultada para esta decisão. O comportamento dos gatilhos e das migrações foi verificado pelos testes listados acima, e não por documentação externa.
