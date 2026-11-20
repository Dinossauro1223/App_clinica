# NutriLab — Sistema integrado de Nutrição Clínica e Dietética

> **Documentação de retomada e especificação funcional.** Revisada em 09/11/2026 a partir do pacote-fonte `App_clinica-main`, das planilhas operacionais de outubro de 2026, do relatório de fórmulas antropométricas, do modelo de Evolução Nutricional e das referências visuais fornecidas.
>
> Este documento diferencia o que foi encontrado no código, o que aparece nos materiais reais do setor e o que ainda será desenvolvido. Não certifica a validade clínica de cálculos, não substitui validação institucional e não autoriza usar o sistema em produção com dados reais.

O **NutriLab** (`app_clinica`) é um projeto de software para organizar o trabalho do Serviço de Nutrição Clínica e Dietética hospitalar. A proposta é reunir, em um único ambiente, o mapa diário por leito, antropometria, cálculos, anamnese, condutas, evolução nutricional, suplementação, indicadores, controle de refeições e estoque, com autoria individual e permissões específicas para nutricionistas e demais funcionários.

O desenvolvimento deve ser conduzido de forma **autônoma por Claude e seus agentes especializados**. Os agentes devem investigar o código, estudar os materiais do setor, pesquisar fontes primárias quando necessário, implementar, testar, documentar e avançar pelas fases do roadmap sem pedir autorização a cada decisão técnica ou dúvida bibliográfica. Toda dúvida sobre fontes deve ser resolvida por pesquisa documentada no [Diário de dúvidas bibliográficas](docs/desenvolvimento/DIARIO_DUVIDAS_BIBLIOGRAFICAS.md). As regras completas estão em [`CLAUDE.md`](CLAUDE.md) e [`AGENTS.md`](AGENTS.md).

## 1. Objetivo do produto

Construir uma plataforma hospitalar que mantenha continuidade entre:

1. **Paciente e internação:** identificação, unidade, setor, leito, acompanhante e histórico.
2. **Mapa Nutricional:** situação diária de cada leito, dieta, consistência, características, antropometria, função intestinal, observações e reavaliação.
3. **Avaliação antropométrica:** peso/estatura aferidos ou estimados, IMC, equações documentadas e curvas de crescimento aplicáveis à idade.
4. **Anamnese e PEP:** admissão, avaliação, evolução, metas, dietoterapia, suplementação, conduta e assinatura individual.
5. **Catálogo e cálculo de suplementos:** fichas técnicas atualizáveis, aporte de energia e nutrientes, dose administrada e participação nas metas do paciente.
6. **Operação de Dietética:** aceitação das refeições, controle de fichas, apontamento de refeições de pacientes/acompanhantes/servidores e estoque de gêneros.
7. **Gestão:** indicadores por dia, mês, setor, dieta, produto, módulo e perfil de atendimento.
8. **Acesso por função:** nutricionistas com acesso clínico; funcionários com permissões mínimas, como apenas registrar refeições em uma janela de horário.

O sistema é uma ferramenta de registro, organização e apoio à decisão. Ele não deve gerar ou alterar automaticamente uma conduta nutricional, nem substituir a responsabilidade do profissional habilitado.

## 2. Estado real do código analisado

A análise considera o ZIP `App_clinica-main` enviado para esta conversa. O estado atual do repositório GitHub deve ser comparado com esse pacote antes de cada implementação, pois podem existir commits posteriores.

### 2.1 Funcionalidades encontradas no código

| Área | Evidência no código | Situação observada |
|---|---|---|
| Aplicação desktop | `main.py`, `CustomTkinter` | Implementada no pacote analisado |
| Pacientes e consultas | `Pacientes`, `Consultas`, telas em `main.py` | Implementado, com dados clínicos em texto livre e campos de consulta |
| Condutas de alta | `condutas_alta.py`, `condutas_alta_ui.py`, `condutas_alta_export.py`, `condutas_alta/` | Implementada na branch `feat/condutas-de-alta` ([ADR-0006](docs/decisoes/ADR-0006-condutas-de-alta-na-consulta.md), seção 2.4); testada com simuladores, falta validar no Windows e homologar o conteúdo clínico |
| TMB/VET | `main.py` | Há seleção de Harris-Benedict (1919), Mifflin-St Jeor (1990) e Cunningham (1980), com NAF para VET |
| Mapa por leito | `mapa_ui.py`, `mapa_db.py` | Implementado parcialmente; precisa de validação integrada com o banco principal |
| Histórico/cópia diária | `mapa_db.py`, `mapa_ui.py` | Há histórico por paciente, navegação de datas e cópia do mapa anterior |
| PDF/Excel do mapa | `mapa_export.py` | Exportação implementada; precisa de conferência com o modelo institucional real |
| Gráficos do mapa | `mapa_graficos.py` | Agregação mensal e gráficos implementados |
| Catálogo inicial de suplementos | `mapa_db.py`, `mapa_ui.py` | Cadastro e manutenção do catálogo implementados; composição técnica inicial está incompleta |
| Estimativas antropométricas | `nutri_calculos.py` | Estatura e peso por equações de Chumlea e IMC por faixa etária parcialmente implementados |
| IMC infantil/adolescente | `TabelaLMS` em `nutri_calculos.py` | Leitura de CSV LMS implementada; arquivo oficial não veio no pacote |
| Testes | `tests/test_mapa.py`, `tests/test_ui_smoke.py` | Há testes automatizados, mas parte da interface e do PDF usa simuladores |

### 2.2 Mapa Nutricional: campos já modelados

O código do mapa contempla:

- Data, setor e leito; um registro diário por leito (`UNIQUE(data, id_leito)`).
- Paciente e eventual vínculo com `Pacientes`.
- Acompanhante, sexo, cor, idade em anos/meses.
- AJ (altura do joelho), PB (perímetro do braço) e PP (perímetro da panturrilha).
- Altura e peso, origem aferida/estimada e método utilizado.
- IMC e classificação, data de reavaliação.
- Via oral/enteral, características DM/HAS/laxativa/constipante/DRC e consistência livre/branda/pastosa/líq-past/líquida.
- Doenças relatadas que alimentam as condutas de alta (doença respiratória e tuberculose), na coluna `condicoes` de `Mapa_Registros`. Ficam fora das características do impresso, do Excel e dos gráficos.
- Observações “Sim” e “Não”, estado/frequência da função intestinal.
- Suplementos associados ao registro diário, com quantidade por dia e unidade.

A planilha externa do mapa acrescenta campos/agrupamentos que devem ser considerados na evolução do modelo: `AV/REAV.`, tipo de dieta (LV, BR, PAS, L-P, LÍQ), características (DM, HAS, LAX, CON, DRC), suplemento, observações e diagnóstico. O diagnóstico não deve ser exposto a perfis operacionais de refeição.

**Limite atual:** o código armazena função intestinal como presente/ausente, frequência e dias ausentes; não foi encontrada integração completa da escala de Bristol. Também não foi encontrada a escala visual de aceitação oral (0%, 25%, 50%, 75%, 100%) como campo estruturado.

### 2.3 Banco e inicialização: ponto técnico prioritário

`mapa_db.py` define as tabelas `Mapa_Config`, `Mapa_Setores`, `Mapa_Leitos`, `Mapa_Modulos`, `Mapa_Suplementos`, `Mapa_Registros` e `Mapa_Registro_Suplementos`, criadas pela função `inicializar()`.

O `clinica.db` presente no ZIP-fonte analisado não continha a tabela `Mapa_Suplementos` no momento da inspeção. O módulo cria o esquema e semeia os seis registros iniciais na primeira inicialização adequada.

Há uma inconsistência de caminho que deve ser resolvida antes de empacotar ou compartilhar o programa: `configurar_banco_dados()` usa `get_writable_path('clinica.db')`, enquanto a inicialização do mapa e diversas operações de pacientes/consultas usam `get_base_path()`. No executável PyInstaller, `get_base_path()` pode apontar para `_internal` e `get_writable_path()` para a pasta do `.exe`. A Fase 0 deve unificar a conexão e o caminho gravável, com migração e backup.

**Status (10/11/2026):** o serviço único (`db_service.py`), as migrações versionadas (`db_migracoes.py`) e o diagnóstico somente-leitura (`tools/diagnostico_banco.py`) foram criados e testados com bancos sintéticos ([ADR-0001](docs/decisoes/ADR-0001-banco-local-caminho-unico-backup-migracoes.md)). A substituição das chamadas em `main.py`, `mapa_db.py` e `setup_db.py` **continua pendente** (código inacessível na sessão que criou o serviço).

### 2.4 Condutas de alta na consulta (branch `feat/condutas-de-alta`)

**O que faz.** Na tela de consulta, o painel **Condutas de alta** sugere orientações de acordo com o que foi relatado no Mapa Nutricional do paciente (via enteral, DM, DRC, doença respiratória, tuberculose). A nutricionista confirma cada conduta, pode corrigir o texto que vai para o paciente ou marca "não se aplica" com motivo. Depois gera dois documentos:

- **Folha do paciente:** só as condutas confirmadas, em linguagem leiga e compacta, para poupar papel. O que depende da prescrição (dose, volume, meta de proteína, líquidos) fica em branco ("______") para preencher.
- **Relatório do nutricionista:** todas as condutas, com situação, texto técnico, lista de conferência, texto do paciente, motivo e referências.

Os dois saem em PDF (A4), e a folha do paciente também pode ser enviada à impressora. O programa lembra das condutas pendentes no painel da consulta, depois de salvar a evolução e no Mapa (coluna "Condutas de alta" e aviso ao remover o paciente). Folha entregue não muda mais: a correção cria uma nova versão.

**Regras de segurança.** O catálogo apenas **sugere**: nada vai para o paciente sem a confirmação da nutricionista. Os textos vêm de fontes registradas no [diário bibliográfico](docs/desenvolvimento/DIARIO_DUVIDAS_BIBLIOGRAFICAS.md). O conteúdo clínico ainda precisa de homologação pela nutricionista responsável. Nome e CRN são digitados (não há usuário autenticado antes da Fase 3), e a folha não afirma validade jurídica.

| Arquivo | Função |
|---|---|
| `condutas_alta/*.json` | Catálogo versionado: `enteral`, `respiratorias_tb`, `renal` (20 condutas) |
| `condutas_alta.py` | Regras pelo Mapa, banco, decisões e documento |
| `condutas_alta_ui.py` | Painel da consulta e janela das condutas |
| `condutas_alta_export.py` | PDF do paciente e do nutricionista, impressão |
| `db_migracoes.py` | Migração 2 (`condutas_alta`), com reversão e backup |

**Como acrescentar ou corrigir uma conduta.** Edite o JSON do grupo e preencha `codigo`, `titulo`, `titulo_paciente`, `gatilhos`, `profissional`, `conferir`, `paciente` e `fontes` (toda conduta precisa de fonte com link e "Acesso em:"). Aumente `versao` e `revisado_em`, registre a pesquisa em `docs/desenvolvimento/DIARIO_DUVIDAS_BIBLIOGRAFICAS.md` e confira:

```bat
python condutas_alta.py
python -m unittest tests.test_condutas_alta_catalogo -v
```

**Banco.** As migrações 2 (tabelas) e 3 (travas contra trocar ou mover itens de uma folha já entregue) rodam ao abrir o programa, com backup antes (`pre-migracao-v3`: o número é o da versão de destino). Reverter só a 3 tira as travas e mantém os dados. Reverter para a versão 1 apaga as tabelas de condutas: folhas já entregues ficam só no backup (`pre-reversao-para-v1`). Decisão, alternativas e limites: [ADR-0006](docs/decisoes/ADR-0006-condutas-de-alta-na-consulta.md).

## 3. Catálogo de suplementos: dados existentes e lacunas

### 3.1 Seis itens semeados no código

`mapa_db.py` contém a lista `SUPLEMENTOS_INICIAIS`. Quando o catálogo está vazio e a inicialização é executada, são inseridos os itens abaixo:

| Nome no código | Módulo inicial sugerido | Situação da classificação |
|---|---|---|
| Fresubin | Fórmula completa | Sugestão inicial; confirmar produto/apresentação |
| Thopic Soya 1,5 kcal/ml | Fórmula completa | Sugestão inicial; confirmar grafia, produto e ficha técnica |
| Glutamina | Módulo de aminoácidos | Sugestão inicial; confirmar apresentação e composição |
| Nutrison Energy | Fórmula completa | Sugestão inicial; confirmar apresentação comercial |
| Simbioflora | Módulo probiótico/simbiótico | Sugestão inicial; confirmar rótulo e unidade |
| Diamax IG | Fórmula para diabetes | Sugestão inicial; confirmar apresentação e ficha técnica |

O próprio código grava a observação **“Classificação inicial sugerida; confirmar com a ficha técnica.”**. Essas categorias não devem ser tratadas como classificação clínica definitiva.

### 3.2 Campos previstos para cada ficha técnica

A tabela `Mapa_Suplementos` e o formulário `DialogSuplemento` já preveem:

- Nome e módulo.
- Preço da embalagem (`preco`).
- Conteúdo da embalagem (`emb_qtd`) e unidade (`emb_un`: `ml` ou `g`).
- kcal por 100 mL/g (`kcal_100`).
- Proteína por 100 mL/g (`ptn_100`).
- Lipídios (`lip_100`), carboidratos (`carb_100`) e sódio (`sod_100`) por 100 mL/g.
- Observação e estado ativo/inativo.

**No pacote analisado, esses campos existem no modelo, mas os seis itens iniciais são criados sem preços, volumes de embalagem ou valores nutricionais.** Não há base para afirmar que a ficha técnica esteja preenchida ou validada.

### 3.3 Módulos disponíveis no código

`MODULOS_PADRAO` contém:

1. Fórmula completa
2. Fórmula para diabetes
3. Módulo de proteínas
4. Módulo de aminoácidos
5. Módulo de carboidratos
6. Módulo de lipídeos
7. Módulo de fibras
8. Módulo probiótico/simbiótico
9. Módulo de vitaminas e minerais
10. Espessante
11. Outro

Os módulos são editáveis/ampliáveis por `garantir_modulo()`. A classificação deve ser feita pela finalidade e composição declaradas na ficha técnica, não apenas pelo nome comercial.

### 3.4 Produtos presentes nas planilhas de cálculo, mas não semeados no catálogo

As abas `Calc dieta PSL PTN`, `Calc dieta Isolate PTN` e `Calc dieta Fres. PTN` da planilha `CÁLCULOS ESTIMATIVA DE PESO E ESTATURA` contêm matrizes de cálculo de kcal/proteína por medida para diferentes fórmulas. Além dos seis nomes semeados no código, aparecem as seguintes denominações/variantes:

- Diason 1.0; Diason E. HP; Diason Energy HP.
- Diben 1.5 (SF); Diben 1,5 (SF).
- Fresubin HP Energy; Fresubin 2 kcal HP; Fresubin Original Fb; Fresubin Original Fibre.
- Isosource 1.5; Isosource Soya.
- Novasource GC; Novasource HP; Nov. Proline (SF); Novasource Proline (SF); Nov. Senior (SA); Nov. Senior (SF); Novasource Senior.
- Nutri Enteral 1.2; Nutri Enteral Soya; Nutri R 2.0; Nutro Premium PF 1.5.
- Nutrison 1.0; Nutrison PP Energy; Nutrison Protein Plus Energy.
- Peptamen HN; Peptamen Intense; Peptisorb; Survimed; Trophic Basic.

Essas grafias foram mantidas como aparecem nas planilhas. Não unificar variantes, abreviações ou apresentações por semelhança textual. O agente do catálogo deve identificar produto, fabricante, apresentação, concentração, medida caseira e unidade usando rótulo/ficha técnica; depois, pode criar aliases ligados a um produto canônico.

### 3.5 Como o uso do suplemento é salvo atualmente

`Mapa_Registro_Suplementos` grava `id_registro`, `id_suplemento`, nome, módulo, quantidade diária e unidade. O nome e módulo são copiados para preservar parte do histórico quando o catálogo muda.

Ainda falta um snapshot da composição nutricional, da apresentação/embalagem e da versão da ficha técnica utilizada no cálculo. Sem esse snapshot, não é seguro recalcular a contribuição histórica com a ficha atualizada. A Fase 5 deve resolver isso.

### 3.6 Cálculos de aporte previstos

O relatório de fórmulas fornecido define a base matemática para integração da ficha técnica:

- Nutriente fornecido = (quantidade administrada ÷ 100) × valor do nutriente por 100 mL/g.
- Densidade calórica = kcal por 100 ÷ 100.
- Volume para atingir alvo energético = kcal alvo ÷ densidade calórica.
- Embalagens necessárias = volume/massa total ÷ conteúdo da embalagem.
- Custo estimado = número de embalagens × preço da embalagem.
- Percentual do VET = kcal do suplemento ÷ VET × 100.
- Proteína por kg = proteína fornecida ÷ peso usado no cálculo.
- Velocidade de infusão = volume ÷ horas.
- Água da fórmula depende do percentual de água declarado pelo fabricante; osmolaridade deve ser lida da ficha/rótulo, não inferida por fórmula caseira.

O cálculo deve aceitar dose em mL, g, medida ou sachê somente quando a conversão estiver documentada. Nunca converter “medida” em gramas sem o peso da medida no rótulo/ficha.

## 4. Planilhas reais e modelos operacionais fornecidos

Os arquivos reais foram analisados como **referência de fluxo e estrutura**, não como dados a serem incorporados ao Git. O inventário completo está em [`docs/referencias/INVENTARIO_PLANILHAS_E_MODELOS.md`](docs/referencias/INVENTARIO_PLANILHAS_E_MODELOS.md).

### 4.1 `Mapa_externo_novo_layout.xlsx`

A pasta de trabalho contém 16 abas com datas do mês de outubro (`0410`, `0510`, `0610`, `0710`, `0810`, `1010`, `11.10`, `1310`, `1410`, `1710`, `1810`, `1910`, `2310`, `2410`, `2710`, `2810`) e uma aba `IMC`.

O cabeçalho organiza: leito, acompanhante (`AC`), nome, idade, avaliação/reavaliação, tipo de dieta, características, suplemento, observações e diagnóstico. O tipo de dieta é representado por opções abreviadas (LV, BR, PAS, L-P, LÍQ); as características incluem DM, HAS, laxativa, constipante e DRC. A estrutura deve ser configurável por setor/leitos, sem fixar no código a quantidade de linhas do arquivo.

A aba `IMC` é uma referência de classificação e não substitui as tabelas oficiais OMS necessárias às curvas de crescimento.

### 4.2 `CONTROLE DE REFEIÇÕES - Outubro 2026.xlsx`

A pasta de trabalho possui abas identificadas como `01-07`, `08-14`, `15-21`, `Sheet 1` e `29-31`. O cabeçalho usa seis momentos de refeição: **Desjejum, Lanche manhã, Almoço, Lanche tarde, Jantar e Ceia**.

A leitura das datas reais das células identificou divergência: a aba `15-21` contém datas de 15 a 17/09/2026, embora o arquivo seja de outubro; as abas mostram três blocos de datas visíveis, não sete dias completos. Existem, portanto, lacunas e uma divergência entre nome de aba e datas. Importadores não podem assumir que o nome da aba define a data nem transformar células vazias/dias ausentes em zero consumo.

### 4.3 `CONTROLE DE FICHAS ALMOÇO E JANTAR - OUTBRO 2026.xlsx`

Possui duas abas (`ALMOÇO` e `JANTAR`) e colunas para os dias 1 a 31. As linhas agrupam serviços/setores, como Agência Transfusional, Ambulatório, Assistência Social, Clínicas, Esterilização, Farmácia, Laboratório, Lavanderia, Manutenção, Maqueiros, Médicos, Motorista, NIR, Pediatria, Porteiro, Raio-X, Recepção, Registro, SAMU, SAU, Servente/Limpeza, Nutrição, UPA e CAPS.

O modelo registra totais como **fichas entregues**, **fichas recebidas** e **refeições sem ficha**. Isso é um controle agregado por setor/refeição; não equivale ao registro individual de qual servidor realizou a refeição. O módulo móvel precisa registrar a pessoa autenticada e o setor, e depois permitir a consolidação com esses totais.

### 4.4 `Controle da Nutrição - Outubro 2026.xlsx`

A planilha contém um catálogo operacional com **139 itens**. Para cada item há unidade e valor, além de colunas diárias pareadas de **Entrada** e **Saída** ao longo de outubro. Ao fim de cada bloco semanal aparecem totais de **Entrada semanal, Uso semanal, Gasto semanal e Saldo semanal**.

Esse modelo deve orientar um módulo de estoque com cadastro de insumos, unidade padronizada, movimentos de entrada/saída, custo, saldo calculado e fechamento por período. A planilha não deve ser importada diretamente como cadastro de produção sem limpeza de unidades duplicadas (por exemplo, KG/Kg, PAC/PCT, UND/UN) e sem tratar os valores como históricos do mês de referência.

### 4.5 `CÁLCULOS ESTIMATIVA DE PESO E ESTATURA.xlsx`

A estrutura observada inclui:

- `Peso-Alt`: estimativas de peso e estatura por grupos de idade (6–18, 19–59 e 60–80 anos), sexo e cor, com base em equações de Chumlea; também há um bloco de cálculo para amputados.
- `Calc dieta PSL PTN`: fórmulas enterais e valores de kcal/proteína em uma matriz de 1 a 21 medidas.
- `Calc dieta Isolate PTN`: matriz de produtos com cálculo de kcal/proteína por medida.
- `Calc dieta Fres. PTN`: matriz de produtos para uso de Fresubin Protein e comparação de fórmulas.
- `Oferta`: consolidação de vazão, tempo de infusão, volume, densidade calórica, módulos e total de kcal/proteína; há também um campo separado para contribuição de propofol. Esse campo não deve ser incorporado como suplemento e exige tratamento específico, caso venha a fazer parte de algum cálculo assistencial.
- `Nora`: contém cálculos de noradrenalina e não pertence ao escopo nutricional do NutriLab; não migrar para o módulo de nutrição.

As planilhas são úteis para descobrir produtos, medidas e resultados esperados, mas não substituem as fichas oficiais dos fabricantes nem a auditoria das fórmulas e unidades.

### 4.6 `Evolucao_nutricional_pacientes.pdf`

O documento apresenta um modelo real de evolução em três colunas: **Paciente, Evolução e Antropometria**. A antropometria registra data, AJ, PB, PP, altura e peso, com indicação de estimado/aferido, e IMC com classificação. A evolução registra via, consistência e características da dieta, função intestinal, suplementação, aceitação, tolerância, observações e conduta.

Nas páginas 5 e 6 há listas de perguntas e frases-modelo para anamnese/observações, além de exemplos textuais de oferta de suplementos. O sistema deve transformar esse conteúdo em campos e modelos selecionáveis, preservando a possibilidade de texto livre. Frases de exemplo e doses presentes no PDF são exemplos de registro, nunca uma prescrição automática.

### 4.7 Referências visuais enviadas

- **Escala de Bristol:** escala ilustrada de 1 a 7, de fezes muito endurecidas a totalmente líquidas. Deve ser um campo estruturado da função intestinal, com imagem/legenda acessível e opção “não observado/não informado”.
- **Aceitação da dieta oral:** escala ilustrada de 0%, 25%, 50%, 75% e 100% de consumo do prato. Deve ser registrável por refeição e data, sem confundir percentual de aceitação com quantidade prescrita.

## 5. PEP — estrutura funcional desejada

O formulário de evolução deve contemplar, ao menos, os campos abaixo, de acordo com o modelo fornecido:

| Grupo | Campos |
|---|---|
| Identificação | Paciente, unidade/setor/leito, data/hora, profissional responsável |
| Admissão e evolução | Texto de admissão; texto de evolução; histórico de registros anteriores |
| Antropometria | Peso (estimado/aferido), altura (estimada/aferida), IMC, data e método |
| Metas | Necessidade energética (kcal/kg/dia), energia total (kcal/dia), proteína (g/dia) e proteína (g/kg) |
| Monitoramento | DVA (sim/não), AHGT conforme modelo do setor, função intestinal nas últimas 24 h, frequência/episódios, dias sem evacuação, fezes diarreicas |
| Dietoterapia | Via oral/enteral; aceitação VO; tolerância TNE; TNO/consistência e características |
| Terapia enteral | Fórmula, volume, vazão (mL/h), horas, meta calórica, meta proteica e quanto foi atingido |
| Suplementação | Produto, apresentação, dose, unidade, horários/refeições, via e aporte calculado |
| Observações | Texto livre e modelos reutilizáveis |
| Conduta | “Mantida” ou “Nova conduta”; campo de descrição; histórico de alterações |
| Autoria | Usuário autenticado, nome completo, CRN, carimbo/assinatura, data/hora e trilha de auditoria |

A sigla AHGT deve permanecer como no modelo de origem até que seu significado institucional esteja documentado; não inventar uma expansão. O PEP deve permitir registrar alergias, intolerâncias, capacidade de mastigar e aversões alimentares, perguntas listadas no PDF.

A assinatura eletrônica deve identificar a conta individual que realizou o ato. A existência de uma imagem de assinatura/carimbo não deve ser apresentada como certificação de validade jurídica ou institucional sem a política do hospital. Documento assinado deve ser imutável; correção ocorre por adendo/retificação auditável.

## 6. Antropometria, fórmulas e curvas

O arquivo `docs/referencias/RELATORIO_FORMULAS_E_ESTIMATIVAS.txt` é o inventário de pesquisa previamente produzido, com fórmulas, autores, anos, populações e limitações. Deve ser o ponto de partida do agente de pesquisa, sem repetir todo o levantamento do zero; fontes primárias devem ser reabertas quando um coeficiente for implementado ou houver dúvida relevante.

### 6.1 Implementado no código atual

- Estatura por AJ com equações de Chumlea (1994) em crianças/adolescentes e adultos, e Chumlea (1985) ou Chumlea (1998) em idosos.
- Peso estimado por AJ + PB com equações de Chumlea por sexo, cor e faixa etária.
- IMC = peso ÷ estatura².
- Classificação de adultos por OMS; idosos por Lipschitz ou OPAS, com Lipschitz como padrão do código.
- Classe de IMC por escore-z/LMS para menores de 19 anos quando um CSV válido estiver disponível.
- TMB por Harris-Benedict (1919), Mifflin-St Jeor (1990) e Cunningham (1980), com VET calculado por NAF no formulário de consulta.

### 6.2 Pendências de referência/dados

- O arquivo `dados/oms_imc_idade_lms.csv` não veio no pacote. O código sabe ler LMS para IMC/idade, mas não contém a tabela de referência completa.
- Não foi encontrada implementação de todas as curvas pedidas (peso/estatura, peso/idade, estatura/idade, perímetro cefálico/idade etc.).
- A aba `IMC` da planilha externa não substitui arquivos de referência OMS por sexo e idade.
- A pesquisa fornecida cita OMS 2006 (0–5 anos) e OMS 2007 (5–19 anos) para IMC/idade, mas os dados oficiais de cada indicador devem ser localizados, versionados e testados separadamente. Exibir apenas indicadores para os quais exista tabela oficial e faixa etária apropriada.
- Para menores de 6 anos, o relatório orienta priorizar comprimento/estatura medidos; não inventar uma equação geral de AJ.
- Para idosos, o relatório registra limitações de aplicabilidade de estimativas de estatura, especialmente em mulheres idosas e pessoas com 70 anos ou mais. O aviso deve ser preservado e visível.

### 6.3 Escopo de medidas

O perímetro do punho foi explicitamente deixado fora do escopo atual para estimar densidade/massa muscular. Não criar esse cálculo nesta versão. A PP (panturrilha) pode ser mantida como indicador antropométrico, mas não deve ser apresentada como variável das equações de estatura/peso em que não participa.

### 6.4 Regras de auditoria clínica

Todo resultado calculado deve guardar as entradas, unidades, equação, autor/ano, versão da referência, data/hora, origem aferida/estimada e avisos de aplicabilidade. A ausência de dado de referência deve produzir “pendente/não disponível”, nunca um valor inventado ou extrapolado.

## 7. Controle de refeições e acesso por celular

O projeto tem dois fluxos diferentes, que não devem ser confundidos:

1. **Refeições de pacientes/acompanhantes:** registro por paciente, data e cada uma das seis refeições do dia (desjejum, lanche da manhã, almoço, lanche da tarde, jantar e ceia), com aceitação oral em percentuais quando aplicável.
2. **Refeição de servidores por setor:** apontamento individual pelo funcionário autenticado, com vínculo ao setor, refeição e horário. A regra solicitada é almoço de 12:00 a 13:00 e jantar de 19:00 a 20:00, no fuso `America/Recife`, configurável pelo administrador do hospital.

O funcionário com permissão de apontamento não pode visualizar o Mapa Nutricional, prontuário, antropometria, diagnóstico, suplementação ou evolução de pacientes. A validação de data e horário deve ocorrer no servidor/API, não somente no navegador.

A planilha de fichas registra totais agregados por setor e dia; o aplicativo deve manter a trilha por servidor e gerar os totais equivalentes, sem confundir “ficha entregue”, “ficha recebida” e “refeição realizada”.

## 8. Arquitetura-alvo

A interface desktop existente pode continuar como cliente de NutriLab, mas o uso simultâneo em computadores e celulares exige uma arquitetura centralizada:

- **Clientes:** desktop CustomTkinter e aplicação web responsiva/PWA para funções móveis.
- **API:** serviço autenticado com regras de negócio e autorização por módulo/ação.
- **Banco central:** banco relacional gerido pelo hospital, com migrações e backups. PostgreSQL e FastAPI são opções para avaliar, não decisões impostas antes de registrar uma ADR (Architecture Decision Record).
- **Dados locais:** SQLite pode permanecer para desenvolvimento, testes ou modo individual, mas não deve ser compartilhado em pasta de rede/sincronização como substituto de um backend multiusuário.
- **Auditoria:** usuário, ação, entidade, data/hora, origem e resultado, sem duplicar desnecessariamente informações sensíveis em logs.

## 9. Tecnologias observadas e execução local

| Componente | Tecnologia encontrada |
|---|---|
| Linguagem | Python 3 |
| Interface desktop | CustomTkinter / Tkinter |
| Banco atual | SQLite |
| PDF | FPDF (a dependência instalada deve ser `fpdf2`, que fornece o módulo `fpdf`; não instalar `fpdf` e `fpdf2` em conjunto) |
| Imagens | Pillow |
| Excel | openpyxl |
| Gráficos | matplotlib (backend Agg no módulo de gráficos) |
| Empacotamento | PyInstaller (`app_clinica.spec`) |
| Testes | `unittest` |

A Fase 0 adicionou `requirements.txt` (versões fixadas), `requirements.lock.txt` (congelamento completo) e `requirements-build.txt` (PyInstaller). Eles foram verificados quanto à instalação conjunta (`pip check`) em Python 3.12/Linux, e os testes do pacote passaram também no Windows do usuário (relato de 11/11/2026); a compatibilidade com o código do aplicativo **ainda precisa ser validada** ([ADR-0002](docs/decisoes/ADR-0002-ambiente-reproduzivel-e-dependencias.md)). Comandos de referência para o Windows (guia completo em [`docs/desenvolvimento/GUIA_DESENVOLVIMENTO_WINDOWS.md`](docs/desenvolvimento/GUIA_DESENVOLVIMENTO_WINDOWS.md)):

```bat
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python tools\verificar_ambiente.py
python main.py
```

**Não execute `setup_db.py` de maneira improvisada nem copie um banco real por cima do banco de desenvolvimento.** Primeiro unificar o caminho do banco e definir migrações. Em desenvolvimento, use banco sintético/descartável.

Testes atuais:

```bat
.venv\Scripts\activate
python -m unittest discover -s tests -v
```

Os agentes devem registrar o resultado real. Testes de interface/PDF com simuladores não comprovam impressão ou interação com bibliotecas reais. Teste local em Linux também não prova que passa no Windows: depois do push, confira o resultado do CI do GitHub (aba Actions, Windows e Linux) da branch ou do pull request antes de integrar.

Antes de qualquer push, audite o repositório (nunca imprime conteúdo de arquivos; falha se houver banco, backup, anexo de paciente, segredo ou planilha original do hospital):

```bat
python tools\auditar_repositorio.py
```

## 10. Organização principal do código

```text
.
├── main.py                           # Aplicação desktop, pacientes, consultas e TMB/VET
├── setup_db.py                       # Inicialização legada do banco; revisar na Fase 0
├── nutri_calculos.py                 # Estimativas antropométricas e IMC/LMS
├── mapa_db.py                        # Persistência do mapa, setores, leitos e suplementos
├── mapa_ui.py                        # Telas de mapa, gráficos e catálogo de suplementos
├── mapa_export.py                    # Exportação PDF/Excel do mapa
├── mapa_graficos.py                  # Agregações e gráficos mensais
├── condutas_alta.py                  # Condutas de alta: catálogo, regras pelo Mapa, decisões e documento (Fase 4)
├── condutas_alta_ui.py               # Painel da consulta e janela das condutas de alta
├── condutas_alta_export.py           # PDF do paciente e do nutricionista, impressão
├── db_service.py                     # Serviço único de banco: caminho, conexão, backup e restauração (Fase 0)
├── db_migracoes.py                   # Migrações versionadas e reversíveis do SQLite local (Fase 0)
├── tools/                            # Auditoria de dados sensíveis, verificação de ambiente e diagnóstico de banco
├── requirements.txt                  # Dependências fixadas (+ requirements.lock.txt e requirements-build.txt)
├── docs/decisoes/                    # ADRs (decisões de arquitetura)
├── .github/workflows/ci.yml          # CI: Windows e Linux
├── exames_internos/                  # Catálogo de exames em JSON
├── condutas_alta/                    # Catálogo de condutas de alta em JSON (enteral, respiratórias/TB, renal)
├── condutas_internas/                # Biblioteca interna de condutas em JSON
├── prescricoes_internas/             # Biblioteca interna de prescrições em JSON
├── sintomas_internos/                # Biblioteca interna de sintomas em JSON
├── regras_exames_complementares.json # Regras de exames complementares
├── tests/                            # Testes automatizados
├── app_clinica.spec                  # Configuração PyInstaller
└── arquivos_pacientes/               # PDFs/anexos; não versionar se houver dado real
```

As pastas JSON podem ser necessárias ao programa. Não as apagar em massa. Antes de versionar, revisar se contêm apenas conteúdo genérico ou se incluem nomes, diagnósticos, datas de atendimento ou outro dado identificável.

## 11. Segurança, privacidade e dados reais

O projeto pode tratar dados pessoais sensíveis de saúde. Portanto:

- Nunca versionar `clinica.db`, backups, WAL/journal, anexos de pacientes, PDFs de conduta, planilhas operacionais com dados reais ou exportações identificáveis.
- Não usar dados reais nos testes, fixtures, screenshots, issues ou logs. Criar dados sintéticos.
- A exclusão pelo `.gitignore` não remove arquivos já rastreados nem limpa o histórico Git. Conferir `git ls-files` e o histórico antes de publicar.
- Não armazenar senhas, tokens, certificados ou assinaturas reais em texto puro ou no repositório.
- Não compartilhar SQLite local entre computadores e celulares. Multiusuário deve usar API e banco central autorizados pelo hospital.
- Perfis de funcionário devem negar por padrão qualquer acesso clínico.
- Preservar histórico e autoria; não sobrescrever evolução assinada.

Comandos de verificação antes de push:

```bat
git status --short
git ls-files | findstr /i "clinica.db arquivos_pacientes backup .env CONTROLE DE REFEIÇÕES CONTROLE DE FICHAS Controle da Nutrição Mapa_externo"
```

## 12. Documentos que orientam Claude e os agentes

- [`CLAUDE.md`](CLAUDE.md): instruções carregadas no início das sessões do Claude Code.
- [`AGENTS.md`](AGENTS.md): autonomia, limites, delegação e critérios de conclusão.
- [`ROADMAP.md`](ROADMAP.md): fases, responsáveis, entregas e critérios de aceite.
- [`docs/referencias/INVENTARIO_PLANILHAS_E_MODELOS.md`](docs/referencias/INVENTARIO_PLANILHAS_E_MODELOS.md): leitura detalhada dos arquivos reais de referência.
- [`docs/desenvolvimento/DIARIO_DUVIDAS_BIBLIOGRAFICAS.md`](docs/desenvolvimento/DIARIO_DUVIDAS_BIBLIOGRAFICAS.md): registro obrigatório de dúvidas e decisões sobre fontes.
- [`.claude/agents/`](.claude/agents/): agentes especialistas para pesquisa, planilhas, banco, interface, suplementos/estoque, mobile e QA.
- [`docs/decisoes/`](docs/decisoes/): ADRs (banco local, ambiente reproduzível, arquitetura multiusuário preliminar).
- [`docs/desenvolvimento/GUIA_DESENVOLVIMENTO_WINDOWS.md`](docs/desenvolvimento/GUIA_DESENVOLVIMENTO_WINDOWS.md): instalação, testes, auditoria, banco e build no Windows.
- [`docs/desenvolvimento/NOTAS_DE_ENTREGA_FASE0.md`](docs/desenvolvimento/NOTAS_DE_ENTREGA_FASE0.md): o que a Fase 0 entregou e o que falta.

## 13. Regra de continuidade

O agente principal deve iniciar pela primeira fase incompleta do roadmap, conferir o estado atual do Git, implementar os itens que não dependem de decisão externa e avançar automaticamente para a próxima fase quando os critérios forem atendidos. **Não parar para perguntar se deve continuar.** Dúvidas sobre referências são pesquisadas e registradas no diário. Dúvidas clínicas que não possam ser resolvidas por evidência devem ser isoladas como pendência de validação, enquanto o restante do desenvolvimento prossegue.
