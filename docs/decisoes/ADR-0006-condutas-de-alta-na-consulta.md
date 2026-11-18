# ADR-0006: Condutas de alta na consulta (catálogo versionado, confirmação pela nutricionista e folha do paciente)

- **Estado:** Aceita (modo local). O conteúdo clínico do catálogo ainda precisa de homologação pela nutricionista responsável antes de uso assistencial. Complementa as ADR-0001 (migrações) e ADR-0004 (serviço único de banco).
- **Data:** 17/11/2026 (America/Recife)
- **Fase do ROADMAP:** 4 (conduta e documento imprimível na consulta), apoiada no Mapa da Fase 1
- **Branch:** `feat/condutas-de-alta` (criada a partir da `main` no commit `b135c90`)

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
5. **Documento entregue é imutável, no banco.** A migração 2 (`condutas_alta`) cria `Condutas_Alta_Docs` e `Condutas_Alta_Itens`, dois índices e cinco gatilhos que abortam INSERT, UPDATE e DELETE de itens, e UPDATE e DELETE do documento, quando ele está `entregue`. Corrigir uma folha entregue é criar uma nova versão (`substitui_id_doc`), nunca alterar a antiga. Entregar exige nome da nutricionista, pelo menos uma conduta confirmada e nenhuma conduta aplicável pendente. A migração tem `down`; o executor faz backup antes de aplicar (`pre-migracao-v2`) e antes de reverter (`pre-reversao-para-v1`). Não há chave estrangeira para `Pacientes`, porque essa tabela pertence ao esquema legado.
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

- Ao abrir o programa, a migração 2 roda (com backup antes). Bancos novos e antigos recebem as duas tabelas, e o Mapa ganha a coluna `condicoes` se faltar.
- **Reverter para a versão 1 apaga as tabelas de condutas.** Folhas já entregues ficam só no backup `pre-reversao-para-v1`. A coluna `condicoes` do Mapa não é removida (é aditiva e inofensiva) e continua sendo reconhecida se a migração for aplicada de novo.
- A cópia do mapa do dia anterior leva `condicoes` junto (testado).
- Cada revisão clínica do texto muda o JSON (`versao`, `revisado_em`), o diário bibliográfico e, se preciso, os testes do catálogo. Esses testes verificam o que a máquina consegue: gatilhos, fonte em cada conduta, nenhum número de dose no texto do paciente, citações sem ambiguidade, fonte registrada no diário. Eles **não substituem** a conferência clínica.
- O PDF do paciente leva nome e data. Ele é gerado sob demanda, em `arquivos_pacientes/paciente_<id>` (pasta de dados do usuário, fora do Git). Nenhum PDF, banco ou dado real entra no repositório, e os testes usam pacientes sintéticos.
- O `.spec` passa a embutir `condutas_alta/`; sem essa pasta o executável não abre as condutas (um teste confere a linha do `.spec`).
- Testes existentes foram ajustados, sem enfraquecê-los: versão final do esquema e lista de tabelas (`test_db_migracoes`, `test_diagnostico_banco`, `test_integracao_banco`), contagem de pastas gravadas fora do bundle em `main.py` (2 para 3, por causa de `pasta_condutas_alta`) e fakes de interface (`test_ui_smoke`).
- Correção de defeito antigo encontrado no caminho: `tela_mobile` ainda abria `os.path.join(get_base_path(), 'clinica.db')`, o caminho que a ADR-0004 já trocou nos outros pontos do `main.py`. Agora usa `caminho_do_banco()`.

## Como verificar

```bat
python -m unittest tests.test_condutas_alta tests.test_condutas_alta_catalogo tests.test_condutas_alta_export tests.test_condutas_alta_ui -v
python -m unittest discover -s tests -v
python condutas_alta.py
```

`python condutas_alta.py` valida o catálogo e imprime "Catálogo ok: 20 condutas em 3 grupos".

Evidências desta sessão (Linux, Python 3.13; o alvo do projeto é 3.12):

| Módulo de teste | Testes | Resultado |
|---|---|---|
| `test_condutas_alta` (núcleo, banco, imutabilidade, sessão, Mapa) | 45 | OK |
| `test_condutas_alta_catalogo` (conteúdo, gatilhos, fontes, `.spec`) | 20 | OK |
| `test_condutas_alta_export` (PDF com simulador, impressão com chamadas simuladas) | 22 | OK, 2 pulados |
| `test_condutas_alta_ui` (janelas com widgets simulados) | 50 | OK |
| Suíte inteira (`discover -s tests`) | 312 | OK, 2 pulados |

O que **não** foi executado, e por quê:

- Os dois testes pulados são o PDF gerado pelo fpdf2 real e a gravação de PNG para conferência visual. O fpdf2 não está instalado neste ambiente e a instalação de pacotes está bloqueada. A suíte inteira rodou com um pacote `fpdf` vazio no `PYTHONPATH`, só para o import de `test_integracao_banco` (nada disso entra no Git).
- As janelas reais do CustomTkinter (os testes usam widgets simulados), a restauração da posição de rolagem, a impressão real no Windows (`os.startfile`) e o build do PyInstaller também não foram exercitados.

## Pendências

1. **Homologação clínica** do texto de cada conduta pela nutricionista responsável. Até lá, o programa só sugere e a nutricionista decide.
2. **Autoria individual:** nome e CRN são digitados na janela das condutas. Não há usuário autenticado (Fase 3), assinatura nem carimbo, e não se afirma validade jurídica.
3. **Lacunas de conteúdo registradas no diário:** doença respiratória além da DPOC; interação de alimentos com isoniazida; lista de sintomas de neuropatia; líquidos, fósforo, diálise e proteína em diabetes com doença renal; frequência de pesagem; duração da piridoxina; texto original da KDOQI 2020 (não lido); itens do Manual de Recomendações para o Controle da Tuberculose de 2019 lidos uma vez só e marcados no texto.
4. **Alcance clínico do Mapa:** só há "doença respiratória" e "tuberculose" como doenças novas, e DRC sem estágio. A nutricionista descarta o que não se aplica ("não se aplica", com motivo).
5. **Imutabilidade por gatilho** protege contra qualquer escrita pelo aplicativo, mas quem abre o arquivo `.db` com acesso direto pode remover os gatilhos. A proteção forte depende da API e do banco central (Fase 3).
6. Rodar a suíte e o fluxo completo no Windows do projeto, com fpdf2 real, e imprimir uma folha de teste em papel.
7. Revisão do `.spec`: ele ainda aponta para o caminho fixo do `customtkinter` da máquina do desenvolvedor (pendência já registrada na ADR-0005).

## Referências

- Regras do projeto: `CLAUDE.md`, `AGENTS.md` (seções 5 e 6) e `ROADMAP.md` (Fase 4).
- Fontes clínicas do catálogo: [diário bibliográfico](../desenvolvimento/DIARIO_DUVIDAS_BIBLIOGRAFICAS.md), entradas `REF-2026-11-17-001` (alimentação enteral), `-002` (tuberculose), `-003` (doença respiratória) e `-004` (doença renal), cada uma com autor, ano, título, link e data de acesso.
- Nenhuma fonte externa de engenharia de software foi consultada para esta decisão. O comportamento dos gatilhos e das migrações foi verificado pelos testes listados acima, e não por documentação externa.
