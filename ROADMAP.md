# ROADMAP — NutriLab

> **Plano executável por agentes autônomos.** Atualizado em 09/11/2026 a partir do código e dos materiais operacionais fornecidos. Cada fase descreve objetivo, agentes, atividades, entregáveis, proibições e critérios verificáveis de conclusão.

## Como o roadmap deve ser executado

1. O agente principal lê `CLAUDE.md`, `README.md`, `AGENTS.md`, este roadmap e o inventário de planilhas antes de alterar código.
2. Compara a branch atual com o pacote-fonte analisado e marca os itens já concluídos por evidência real (código, teste ou execução), não por comentário antigo.
3. Delega tarefas independentes aos especialistas de `.claude/agents/`. Um agente integrador mantém contrato de dados e revisa os resultados.
4. Trabalha por branch pequena (`feat/fase-N-assunto`, `fix/...`, `docs/...`) e abre PR/commit local conforme o fluxo do repositório. Não envia para produção nem faz push de dados reais.
5. Quando aparecer uma dúvida bibliográfica, pesquisa e registra a decisão no `docs/desenvolvimento/DIARIO_DUVIDAS_BIBLIOGRAFICAS.md`. Não pede ao usuário para escolher a fonte.
6. Ao concluir uma fase, atualiza este arquivo, executa os testes e começa a próxima fase não bloqueada automaticamente. Não aguarda uma mensagem “pode continuar?”.
7. Se um dado, arquivo ou aprovação institucional não estiver disponível, desenvolve o que for independente e registra o item específico como pendente. Não paralisa todo o projeto.

## Visão geral das fases

| Fase | Objetivo | Agente líder | Dependência | Estado no pacote analisado |
|---|---|---|---|---|
| 0 | Fundação, segurança, ambiente e banco único | Backend + QA | Nenhuma | Em andamento: ferramentas, serviço de banco, migrações, CI e ADRs prontos e testados (Linux e Windows do usuário); integração ao código, auditoria do repositório real e validação do executável pendentes |
| 1 | Mapa Nutricional confiável | Interface clínica + Backend | Fase 0 | Parcialmente implementada |
| 2 | Antropometria, cálculos e curvas de crescimento | Pesquisa clínica + Cálculos | Contratos da Fase 1 | Parcialmente implementada; curvas incompletas |
| 3 | Identidade, permissões, auditoria e backend multiusuário | Backend + Segurança | Fase 0 | Não implementada |
| 4 | Anamnese e PEP estruturado | Interface clínica + Backend | Fases 1 e 3 | Em andamento: condutas de alta na consulta implementadas e testadas com simuladores (branch `feat/condutas-de-alta`, [ADR-0006](docs/decisoes/ADR-0006-condutas-de-alta-na-consulta.md)); anamnese estruturada, PEP, assinatura e histórico longitudinal não implementados |
| 5 | Catálogo de suplementos e cálculo de aporte | Especialista em suplementos + Backend | Fases 1, 2 e 3 | Catálogo inicial parcial |
| 6 | Estoque e controle da Nutrição | Estoque + Backend | Fases 0 e 3 | Não implementada |
| 7 | Refeições de pacientes e servidores; acesso móvel | Mobile + Backend | Fase 3; integrações com 4–6 | Não implementada |
| 8 | Indicadores, relatórios e auditoria operacional | Dados/relatórios + QA | Fases 1–7 | Gráficos do mapa parciais |
| 9 | Homologação e implantação hospitalar | QA + Segurança + Integrador | Fases 0–8 | Não iniciada |

## Melhorias de uso fora das fases

Ajustes de usabilidade pedidos pelo usuário que não pertencem a uma fase. Cada linha diz o que foi verificado de verdade.

### 20/11/2026: atalhos, gráficos e tela de boas-vindas (branch `feat/atalhos-graficos-boas-vindas-2026-11-20`)

| Entrega | Estado |
|---|---|
| Atalhos de edição no estilo do Google Planilhas (Ctrl+C/X/V, Ctrl+Z, Ctrl+Y, Ctrl+Shift+Z, F4, Ctrl+A, colar de planilha, Ctrl+C e Ctrl+A nas tabelas, F1) | Implementado em `atalhos_edicao.py` e ligado no `main.py`; 59 testes novos com widgets simulados e lógica pura. O comportamento no Tk real depende do CI (Windows e Linux) e de uso na máquina; lista em [`ATALHOS_DE_TECLADO.md`](docs/desenvolvimento/ATALHOS_DE_TECLADO.md) |
| Gráficos agrupados por assunto, cada grupo numa faixa que se arrasta para o lado, com opção "de cima para baixo" nas Configurações do Mapa | Implementado em `graficos_layout.py`, `graficos_ui.py`, `mapa_graficos.py` e `mapa_ui.py`; DM, HAS e DRC ganharam grupo e gráfico próprios (8 gráficos). Testes com widgets simulados e, no CI, `tools/verificar_interface_tk.py` com Tk real; ver [`GRAFICOS_AGRUPADOS.md`](docs/desenvolvimento/GRAFICOS_AGRUPADOS.md). Aparência e sensação do arraste só se confirmam abrindo o programa |

---

# Fase 0 — Fundação técnica, segurança e reprodutibilidade

**Objetivo:** fazer o projeto voltar a ser previsível, testável e seguro antes de ampliar funcionalidades.

**Agentes:** `database-backend-engineer` (líder), `qa-security-reviewer`, `legacy-workbook-analyst`, agente principal integrador.

### Atividades obrigatórias

1. **Auditoria do repositório**
   - Executar `git status`, conferir branch, histórico e arquivos rastreados.
   - Identificar `clinica.db`, backups, WAL, diretório `arquivos_pacientes`, PDFs, exportações e planilhas reais.
   - Remover do próximo commit qualquer dado pessoal/sensível; se já foi enviado, orientar contenção do histórico antes de push adicional.
   - Revisar `.gitignore` sem bloquear catálogos JSON genéricos necessários ao aplicativo.
   - Fazer varredura de segredos e dados identificáveis em arquivos versionados.

2. **Ambiente reproduzível**
   - Definir versão Python suportada e validar no Windows.
   - Criar `requirements.txt` com versões fixadas e documentar a diferença entre `fpdf` e `fpdf2`.
   - Criar instruções de ambiente virtual, instalação, execução, testes e build.
   - Configurar CI para executar testes automatizados e verificações básicas.

3. **Banco em caminho único**
   - Mapear todas as chamadas SQLite em `main.py`, `mapa_db.py` e `setup_db.py`.
   - Substituir conexões diretas espalhadas por um serviço centralizado de configuração/conexão.
   - Resolver a divergência entre `get_writable_path()` e `get_base_path()` no executável PyInstaller.
   - Definir local de dados graváveis, backup, restauração, migrações numeradas e rollback.
   - Fazer migração transacional do esquema existente sem destruir `Pacientes`, `Consultas`, exames e histórico.
   - Criar banco de teste sintético; nunca testar migrações diretamente no banco real.

4. **Arquitetura e contratos**
   - Desenhar relação entre paciente, internação/episódio, leito, mapa diário, consulta/PEP, profissional e funcionário.
   - Identificar o que permanece local e o que futuramente vai para API central.
   - Registrar decisões arquiteturais relevantes em ADRs (`docs/decisoes/`).

### Entregáveis

- `requirements.txt` e, se necessário, arquivo de lock.
- Serviço único de banco e migrações versionadas.
- `.gitignore` revisado e evidência de varredura do repositório.
- Guia de desenvolvimento/execução no Windows.
- Pipeline de testes automatizados.
- ADR de caminho de dados e ADR preliminar da arquitetura multiusuário.

### Não pode ser feito

- Não apagar nem substituir bancos, anexos ou histórico real.
- Não incluir os arquivos XLSX/PDF reais do hospital no Git.
- Não usar SQLite em pasta de rede, OneDrive ou serviço sincronizado como mecanismo multiusuário.
- Não apagar `condutas_internas/`, `prescricoes_internas/`, `exames_internos/` ou `sintomas_internos/` em massa.
- Não tratar execução de teste simulado como prova de execução real.

### Critérios de aceite

- Uma única função/fábrica determina o caminho do banco em desenvolvimento e no executável.
- Migração de banco sintético funciona do zero e de uma versão anterior; rollback/backups são testados.
- `python -m unittest discover -s tests -v` passa no ambiente documentado, ou falhas restantes são explicitamente listadas e justificadas.
- Nenhum dado clínico real, segredo ou planilha operacional está no diff.
- Um novo desenvolvedor consegue instalar e iniciar o programa seguindo o README.

### Andamento (atualizado em 10/11/2026 — branch `feat/fase-0-fundacao-seguranca-banco`)

Evidência detalhada em [`docs/desenvolvimento/NOTAS_DE_ENTREGA_FASE0.md`](docs/desenvolvimento/NOTAS_DE_ENTREGA_FASE0.md).
Nesta sessão o repositório privado e o código do aplicativo não estavam acessíveis; o que depende deles está marcado como **bloqueado**.

| Atividade | Estado | Evidência / o que falta |
|---|---|---|
| 1. Auditoria do repositório | **Parcial** | Ferramenta pronta e testada (`tools/auditar_repositorio.py`, 20 testes; não imprime conteúdo). **Bloqueado:** rodar no repositório real (`git status`, arquivos rastreados, histórico). |
| 2. Ambiente reproduzível | **Parcial** | `requirements.txt`, `requirements.lock.txt` e `requirements-build.txt` instalados em venv limpo (`pip check` OK, Python 3.12/Linux); `tools/verificar_ambiente.py` (14 testes); guia do Windows; CI configurado. Os testes do branch passaram no Windows do usuário (relato de 11/11/2026). **Falta:** validar contra o código do aplicativo e o executável. O CI roda no GitHub (Windows e Linux, Python 3.12): estava vermelho em `f79eabe` (15/11/2026) e nos envios seguintes por testes não portáteis, e está verde na `main` desde o pull request #6 (execução 44661288651); ver a [ADR-0006](docs/decisoes/ADR-0006-condutas-de-alta-na-consulta.md), seção "CI do GitHub". |
| 3. Banco em caminho único | **Parcial** | `db_service.py`, `db_migracoes.py` e `tools/diagnostico_banco.py` com 50 testes sintéticos (do zero, de versão anterior, falha no meio, backup/restauração, rollback). **Bloqueado:** substituir as chamadas SQLite de `main.py`, `mapa_db.py` e `setup_db.py` e validar o executável. |
| 4. Arquitetura e contratos | **Parcial** | ADR-0001, ADR-0002 e ADR-0003 (proposta, com modelo de domínio preliminar). **Falta:** decisão final multiusuário (depende do hospital) e conferência do modelo com o DDL real. |

Critérios de aceite:

- [ ] Uma única função/fábrica determina o caminho do banco em desenvolvimento e no executável — função pronta e testada (`db_service.caminho_banco`); **falta adotá-la no aplicativo**.
- [x] Migração de banco sintético funciona do zero e de uma versão anterior; rollback/backups são testados.
- [ ] `python -m unittest discover -s tests -v` passa no ambiente documentado — os 84 testes desta fase passam em Linux (Python 3.12) e no computador do usuário (Windows; relato de 11/11/2026: `Ran 84 tests in 19.016s — OK`, executado pelo aplicador do pacote; versão do Python não informada); a suíte do próprio aplicativo ainda não foi executada.
- [x] Nenhum dado clínico real, segredo ou planilha operacional está no diff deste branch (auditado: 0 BLOQUEIO, 0 REVISAR).
- [ ] Um novo desenvolvedor consegue instalar e iniciar o programa seguindo o README — não verificável sem o código.

**A Fase 0 não deve ser marcada como concluída** até que os itens bloqueados sejam resolvidos.

---

# Fase 1 — Mapa Nutricional por setor, leito e data

**Objetivo:** consolidar o mapa diário como fonte estruturada da situação nutricional por leito, preservando o fluxo existente e o leiaute de impressão do setor.

**Agentes:** `desktop-clinical-ui-engineer` (líder), `database-backend-engineer`, `legacy-workbook-analyst`, `qa-security-reviewer`.

### Atividades obrigatórias

1. **Comparar código e modelo real**
   - Mapear a planilha `Mapa_externo_novo_layout`: cabeçalhos Leito, AC, Nome, Idade, AV/REAV., Tipo de dieta, Característica, Suplemento, Observações e Diagnóstico.
   - Manter categorias LV, BR, PAS, L-P e LÍQ; características DM, HAS, LAX, CON e DRC.
   - Mapear os campos já existentes em `Mapa_Registros`; acrescentar os ausentes por migração, sem quebrar dados existentes.
   - Deixar setores e leitos configuráveis. Não codificar a quantidade de leitos observada na planilha.

2. **Fluxo diário**
   - Criar/editar registro por data + setor + leito.
   - Permitir paciente sem vínculo prévio, e vincular a um paciente existente por identificador estável após confirmação da correspondência.
   - Suportar acompanhante, sexo, cor, idade, AJ, PB, PP, peso/altura com origem, IMC, via, características, consistência, suplemento, observações e FI.
   - Registrar diagnóstico como campo controlado/restrito se fizer parte do modelo final do mapa; não expor a usuários operacionais.
   - Navegar datas, copiar mapa do dia anterior, registrar alta/transferência e manter histórico.
   - Não sobrescrever um registro histórico silenciosamente; alterações devem deixar trilha de auditoria.

3. **Impressão e exportação**
   - Reproduzir o leiaute compacto de Excel/PDF: uma linha por leito, paciente em blocos/linhas legíveis, títulos abreviados e compatibilidade A4.
   - Nome em Arial 10 negrito e detalhes em Arial 8, conforme especificação original, se o modelo continuar adotado.
   - Classificação IMC em vermelho entre parênteses, diferenciando aferido/estimado.
   - Testar PDF com FPDF real e Excel aberto/renderizado com ferramenta compatível; não aceitar somente mocks.

4. **Indicadores básicos**
   - Manter atendimento por paciente-dia, consistência, acompanhante, suplemento e módulo.
   - Definir denominadores e evitar contar o mesmo registro duas vezes.

### Entregáveis

- Mapa funcional por data/setor/leito.
- Migrações e data dictionary do mapa.
- PDF e Excel conferidos com dados sintéticos.
- Testes de copiar mapa, histórico, alta, transferência e leito inativo.
- Guia rápido do fluxo do mapa.

### Não pode ser feito

- Não fixar o setor ou o número de leitos a partir da planilha de outubro.
- Não usar o nome do paciente como chave primária.
- Não trocar medida aferida por estimada nem ocultar a origem.
- Não publicar diagnóstico ou observações clínicas no perfil de funcionário de refeição.
- Não presumir que todos os campos da planilha já existem no código.

### Critérios de aceite

- Um dia pode ser preenchido, reaberto, corrigido e impresso sem perda de histórico.
- Cópia do dia anterior não cria dois registros no mesmo leito/data.
- Testes sintéticos cobrem paciente novo, paciente existente, movimentação e setor.
- Impressões são legíveis e conferidas com PDF/Excel reais.

---

# Fase 2 — Antropometria, equações, índices e curvas de crescimento

**Objetivo:** transformar o inventário de fórmulas previamente pesquisado em um mecanismo versionado, auditável e limitado à população de validade de cada referência.

**Agentes:** `clinical-evidence-researcher` (líder científico), `database-backend-engineer`, `desktop-clinical-ui-engineer`, `qa-security-reviewer`.

### Atividades obrigatórias

1. **Usar a pesquisa prévia como ponto de partida**
   - Começar por `docs/referencias/RELATORIO_FORMULAS_E_ESTIMATIVAS.txt`, relatório datado de 25/10/2026, e pela bibliografia da seção 13.
   - Verificar fórmulas efetivamente implementadas em `nutri_calculos.py`.
   - Reabrir artigo original, protocolo institucional ou documento oficial sempre que o coeficiente, a população ou a unidade for relevante.
   - Registrar no diário todas as dúvidas e decisões de fonte; não interromper o usuário para escolher artigos.

2. **Registro de equações**
   - Criar catálogo de fórmulas com `id`, nome, autor, ano, publicação, DOI/URL, população, sexo, faixa etária, variáveis, unidades, equação, erro/limitação, versão e estado de revisão.
   - Começar pelas equações já codificadas: Chumlea para altura/peso, IMC adulto, Lipschitz/OPAS, LMS infantil e TMB atual.
   - Incluir alternativas do relatório quando houver evidência suficiente (ex.: Rabito, ulna/MUST, meia envergadura, Chumlea para idosos), sem extrapolar faixa/população.
   - Distinguir `medido`, `estimado` e `não disponível` em todos os resultados.

3. **Indicadores e ciclos de vida**
   - Incluir IMC adulto (OMS), IMC idoso (Lipschitz/OPAS configurável) e escore-z IMC/idade conforme OMS 2006/2007.
   - Mapear tabelas oficiais por sexo/idade para peso/idade, estatura/idade, peso/estatura, IMC/idade e perímetro cefálico/idade.
   - Mostrar somente curva/indicador com referência apropriada à idade e à população. Não extrapolar perímetro cefálico para idades sem curva de referência.
   - Para menores de 6 anos, favorecer comprimento/estatura aferidos; não criar fórmula geral de AJ sem fonte apropriada.
   - Preservar alertas de validade reduzida nas estimativas em idosos, especialmente mulheres e pessoas com 70 anos ou mais, conforme o relatório fornecido.

4. **Dados LMS e curvas OMS**
   - Obter arquivos oficiais e dados por sexo/idade da OMS; registrar URL, versão, data de obtenção, licença/condições, checksum e descrição das colunas.
   - Versionar arquivos de referência limpos em `dados/referencias/`, separados de dados de pacientes.
   - Validar idade em meses, sexo, L/M/S, ausência de duplicidade, faixas, monotonicidade/consistência e valores esperados com casos oficiais.
   - Implementar percentis e escore-z (LMS) com teste contra ferramenta/tabela oficial.
   - Não preencher curvas ausentes com interpolação ou aproximação improvisada. Quando o indicador estiver indisponível, mostrar o motivo.

5. **Interface e histórico**
   - Após informar idade/data de nascimento e sexo, exibir apenas os indicadores possíveis para aquela faixa etária.
   - Gráfico deve mostrar curvas de referência, posição atual e série histórica do paciente, com legenda do padrão, sexo, idade, unidade e data.
   - Guardar equação, entradas e versão da tabela com cada medição.

### Entregáveis

- Catálogo versionado de fórmulas/referências.
- Dados OMS oficiais separados por indicador e faixa etária.
- Gráficos de crescimento aplicáveis e classificação z/percentil.
- Testes de referência e de limites de idade.
- Atualização do diário bibliográfico.

### Não pode ser feito

- Não usar a razão estatura/perímetro do punho para estimar densidade ou massa muscular: o punho está fora do escopo atual.
- Não misturar peso por idade com peso por estatura, nem curva adulta com pediátrica.
- Não aplicar equação de emergência pediátrica como diagnóstico antropométrico.
- Não usar uma equação marcada `[conferir]` como validada sem consulta da fonte original.
- Não substituir dado de referência ausente por um palpite.

### Critérios de aceite

- Casos de teste reproduzem os exemplos oficiais/documentados com tolerância definida.
- Cada resultado guarda equação, referência, versão e dados de entrada.
- Limites etários impedem extrapolações indevidas.

### Andamento (atualizado em 11/11/2026 — branch `feat/fase-2-conferencia-equacoes-planilha`)

Pré-trabalho que **não depende do código do aplicativo** (inacessível na sessão): conferência da planilha do setor contra o relatório.
Detalhes em [`docs/referencias/CONFERENCIA_PLANILHA_PESO_ALT.md`](docs/referencias/CONFERENCIA_PLANILHA_PESO_ALT.md).

| Atividade | Estado | Evidência / o que falta |
|---|---|---|
| 1. Usar a pesquisa prévia como ponto de partida | **Parcial** | Relatório confrontado com a aba `Peso-Alt` (26 equações): 25 iguais e 1 divergente (REF-2026-11-11-001); decisão de padrão para 60+ anos (REF-2026-11-11-002) e citação das equações de peso (REF-2026-11-11-003) registradas no diário. **Bloqueado:** verificar as fórmulas em `nutri_calculos.py`. |
| 2. Registro de equações (catálogo) | **Insumo pronto; catálogo não criado** | `tools/conferir_equacoes_planilha.py` guarda os coeficientes de Chumlea (6–80 anos) usados na conferência, com 12 testes (passaram também no Windows do usuário: `Ran 12 tests — OK`, relato de 11/11/2026). Falta o catálogo versionado completo (id, DOI/URL, população, versão, estado de revisão). |
| 3. Indicadores e ciclos de vida | Não iniciada | Depende do código e dos dados OMS. |
| 4. Dados LMS e curvas OMS | Não iniciada | Exige obter, registrar origem/checksum e validar arquivos oficiais. |
| 5. Interface e histórico | Não iniciada | Depende do código (Fase 1 e contratos). |

**A Fase 2 não está concluída.** Coeficiente em dúvida: meninas brancas 6–18 anos (2,14 na planilha × 2,15 nas fontes); decisão e pendências no diário.
- As curvas aparecem somente nas idades/indicadores suportados.
- O relatório de validação distingue verificação matemática, bibliográfica e validação clínica institucional.

---

# Fase 3 — Usuários, hospital, permissões, auditoria e arquitetura multiusuário

**Objetivo:** garantir autoria individual das condutas e acesso mínimo necessário para cada perfil, com base técnica para desktop e celular compartilharem o mesmo ambiente.

**Agentes:** `database-backend-engineer` (líder), `mobile-meal-engineer`, `qa-security-reviewer`, agente principal integrador.

### Atividades obrigatórias

1. **Identidade institucional e pessoal**
   - Modelar o hospital/organização e os usuários individuais.
   - Implementar login seguro, encerramento de sessão, recuperação de acesso e controle de sessão.
   - Identificar nutricionista com nome completo, CRN, perfil e assinatura/carimbo armazenados de forma protegida.
   - Evitar conta genérica compartilhada para autoria clínica. Se a instituição tiver autenticação central (SSO/LDAP/OIDC), avaliar integração e documentar decisão.

2. **Papéis e permissões**
   - Criar perfis iniciais: administrador do sistema, nutricionista, supervisor, funcionário de refeição e leitura/consulta conforme necessidade.
   - Definir permissão granular por módulo e ação (visualizar/criar/editar/assinar/exportar/administrar).
   - Permitir ao nutricionista/admin convidar funcionário e conceder somente funções específicas.
   - Aplicar autorização na API/serviço de dados, não apenas ocultando botões.
   - Funcionário de refeição não pode ler qualquer módulo clínico.

3. **Auditoria**
   - Guardar quem criou/alterou/assinou, quando, qual entidade e ação, origem (desktop/web) e resultado.
   - Registrar concessão/revogação de permissões e correções de apontamento.
   - Evitar gravar conteúdo de prontuário em logs técnicos.

4. **Backend central**
   - Avaliar FastAPI + PostgreSQL ou alternativas aprovadas pelo contexto institucional.
   - Definir API, autenticação, autorização, migrações e backups.
   - Adaptar desktop para consumir o serviço; preparar cliente web para módulos móveis.
   - Manter modo local de desenvolvimento com banco sintético.

### Entregáveis

- Login de hospital/organização e login/identificação individual.
- Cadastro de profissionais (nome, CRN e assinatura/carimbo).
- Papéis e matriz de permissões.
- API central e banco com migrações.
- Trilha de auditoria.
- Testes negativos de acesso (permissão negada).

### Não pode ser feito

- Não compartilhar usuário/senha para múltiplos nutricionistas.
- Não usar imagem da assinatura como substituto de autenticação/autoria.
- Não conceder acesso clínico por conveniência ao funcionário de refeição.
- Não expor API publicamente sem autenticação, TLS, limitação de taxa, política de sessão e autorização.
- Não migrar banco real para servidor externo sem processo institucional de TI/privacidade.

### Critérios de aceite

- Dois nutricionistas conseguem registrar atos com autoria distinta.
- Perfil funcionário consegue realizar apenas a função concedida.
- API rejeita tentativas de leitura/acesso não autorizadas, inclusive chamadas diretas.
- Toda alteração relevante fica auditada.

---

# Fase 4 — Anamnese e Prontuário de Evolução Nutricional (PEP)

**Objetivo:** substituir a dependência de evolução textual dispersa por registro estruturado, com possibilidade de texto livre, histórico e documento imprimível.

**Agentes:** `desktop-clinical-ui-engineer` (líder), `database-backend-engineer`, `clinical-evidence-researcher`, `qa-security-reviewer`.

### Atividades obrigatórias

1. **Anamnese única**
   - Consolidar perguntas atuais da Nova Consulta com os campos de mapa e PEP, evitando duplicação.
   - Incluir alergia alimentar, intolerância, mastigação e aversões alimentares.
   - Preservar observações livres e frases-modelo como sugestões editáveis, nunca como resposta automática.

2. **Registro de admissão e evolução**
   - Campos de admissão e evolução por data/hora.
   - Antropometria: peso/altura com origem estimada/aferida, IMC, método e data.
   - Metas: kcal/kg/dia, kcal/dia, proteína g/dia e g/kg.
   - DVA (sim/não) e AHGT conforme modelo de origem; não expandir a sigla sem fonte institucional.
   - Função intestinal nas últimas 24 h: presente/ausente, episódios/frequência, dias sem evacuação e fezes diarreicas.
   - Dietoterapia: via oral/enteral, aceitação VO, tolerância TNE, TNO/consistência e características.
   - TNE: fórmula, volume, vazão mL/h, período de infusão e percentual/meta de energia/proteína atingidos.
   - Suplementação vinculada ao catálogo do paciente.
   - Observações e conduta (mantida/nova conduta + descrição).

3. **Escalas visuais**
   - Incorporar escala de Bristol 1–7 à função intestinal.
   - Incorporar aceitação oral em 0%, 25%, 50%, 75% e 100% por refeição.
   - Permitir “não observado”, “não se aplica” e ausência de informação, sem transformar ausência em normalidade.

4. **Assinatura e documentos**
   - Associar assinatura ao usuário autenticado, CRN, horário e versão do documento.
   - Gerar PDF com organização semelhante ao modelo enviado: paciente, evolução e antropometria.
   - Gerar carimbo com nome/CRN/assinatura de acordo com o perfil autorizado.
   - Implementar versionamento/adendo para retificações de documento assinado.

5. **Histórico longitudinal**
   - Listar admissões, avaliações, condutas e evoluções anteriores.
   - Mostrar a linha do tempo de antropometria, aceitação, função intestinal e suplementação.
   - Vincular consulta/PEP ao paciente e ao episódio de internação.

### Entregáveis

- Formulário de anamnese estruturada.
- PEP com os campos do modelo real.
- Histórico longitudinal e impressão.
- Registro de usuário/CRN e assinatura/carimbo.
- Testes de edição, adendo, bloqueio de documento assinado e trilha de auditoria.

### Não pode ser feito

- Não sobrescrever uma evolução assinada.
- Não transformar frases-modelo em achados clínicos sem confirmação do profissional.
- Não gerar automaticamente conduta ou prescrição a partir da classificação de IMC/curva.
- Não assumir a expansão de siglas clínicas não esclarecidas pelo documento.
- Não alegar validade jurídica da assinatura sem avaliação institucional.

### Critérios de aceite

- Nutricionista consegue abrir admissão, registrar evolução e consultar o histórico.
- Documento impresso identifica profissional e versão.
- Alteração após assinatura cria adendo/retificação, preservando o original.
- Escalas Bristol e aceitação guardam data, autor e valor.

### Andamento (atualizado em 20/11/2026; entrega integrada pelo pull request #5, correção do CI pelo #6)

Entrega parcial da Fase 4, pedida em 14/11/2026: **condutas de alta na consulta**, ligadas ao Mapa. Decisão, alternativas e limites em [ADR-0006](docs/decisoes/ADR-0006-condutas-de-alta-na-consulta.md). Fontes clínicas em `REF-2026-11-17-001` a `004` do [diário bibliográfico](docs/desenvolvimento/DIARIO_DUVIDAS_BIBLIOGRAFICAS.md).

| Item | Estado | Evidência / o que falta |
|---|---|---|
| Condutas sugeridas pelo Mapa (via, DM, DRC, doença respiratória, tuberculose) | **Implementado e testado com simuladores** | Catálogo JSON com 20 condutas e fontes ABNT; coluna `condicoes` no Mapa; `tests/test_condutas_alta*.py`. |
| Confirmação pela nutricionista (confirmar, corrigir o texto do paciente, "não se aplica" com motivo) | **Implementado e testado** | Nada entra na folha sem confirmação; a decisão guarda uma cópia do texto e da versão do catálogo. |
| Folha do paciente (leiga e compacta) e relatório do nutricionista (integral) em PDF | **Implementado; PDF real gerado no CI, sem conferência visual** | Layout testado com PDF simulado. O teste com fpdf2 real (2.8.9) roda no CI do GitHub, no Windows e no Linux, e gera os dois PDFs; ele só confere o cabeçalho `%PDF`, o tamanho e o número de páginas. Falta olhar um PDF gerado de verdade (a gravação de PNG para conferência visual fica pulada). |
| Imprimir | **Implementado; não testado em impressora** | `os.startfile(..., "print")` no Windows, com plano B (abrir o PDF). Falta provar no Windows do projeto. |
| Lembrar sempre | **Implementado e testado com widgets simulados** | Painel fixo na consulta, aviso depois de salvar a evolução, coluna no Mapa e aviso ao remover do Mapa. |
| Documento entregue imutável e nova versão para corrigir | **Implementado e testado** | Migração 2 (`condutas_alta`) com gatilhos e migração 3 com as travas contra `REPLACE` e contra mover item para folha entregue; ambas com `down` e backup antes. Quem tem acesso direto ao arquivo `.db` ainda pode apagar os gatilhos (Fase 3). |
| Revisão de QA da entrega | **Feita por sondagens executadas pelo integrador, com correções** | Achados e estado de cada um na [ADR-0006](docs/decisoes/ADR-0006-condutas-de-alta-na-consulta.md), seção "Revisão de QA e correções". Não foi uma revisão independente completa (as tentativas com o agente de QA foram cortadas pelo limite de uso da conta); o que não foi verificado está listado lá. |
| CI do GitHub (Windows e Linux) | **Verde na `main`** | O pull request #5 foi integrado com o CI vermelho (execução 44616635455: Windows com 1 falha e 34 erros, Linux com 2 erros). As causas estavam nos testes: fonte do PDF simulado só do Linux, pasta fixa da máquina de desenvolvimento e banco aberto ao apagar no Windows. Corrigido no pull request #6; `main` em `43a117d` com 331 testes OK nos dois sistemas (execução 44661288651). Detalhes e limites na ADR-0006. |
| Assinatura e carimbo ligados a usuário autenticado | **Não implementado** | Depende da Fase 3. Nome e CRN são digitados; não se alega validade jurídica. |
| Anamnese estruturada, PEP, escalas (Bristol e aceitação), histórico longitudinal | **Não iniciados** | Seguem nas atividades 1 a 3 e 5 desta fase. |

**A Fase 4 não está concluída.** Testes: no CI do GitHub (Windows e Linux, Python 3.12) a `main` roda 331 testes OK e 1 pulado (PNG de conferência visual); localmente (Linux, Python 3.13, sem fpdf2 real) são 331 OK e 2 pulados. Pendências: homologação clínica do conteúdo pela nutricionista responsável; lacunas de fonte registradas no diário; validação no Windows do projeto (janelas reais, aparência do PDF e impressora); catálogo ainda restrito a enteral, respiratórias/tuberculose e renal.

---

# Fase 5 — Catálogo de suplementos, dietas e cálculo de aporte

**Objetivo:** transformar a lista inicial e as planilhas de cálculo manual em catálogo técnico confiável, vinculado ao paciente e à meta nutricional.

**Agentes:** `supplement-stock-engineer` (líder), `clinical-evidence-researcher`, `database-backend-engineer`, `desktop-clinical-ui-engineer`, `qa-security-reviewer`.

### Atividades obrigatórias

1. **Importação/normalização do catálogo**
   - Preservar os seis registros de seed do código como itens iniciais.
   - Importar a lista de a lista de denominações/variantes vistas nas planilhas de cálculo como candidatos a catálogo; não tratá-las como fichas validadas.
   - Distinguir fórmula completa, fórmula para diabetes e módulos isolados (proteína, aminoácido, carboidrato, lipídeo, fibra, probiótico, vitaminas/minerais, espessante etc.).
   - Criar produto canônico + apresentação + fabricante + alias, para não unir produtos diferentes.
   - Habilitar ativo/inativo; se houver histórico de uso, preservar o cadastro como inativo, sem apagar registros.

2. **Ficha técnica**
   - Nome comercial, fabricante, apresentação, embalagem, volume/massa, medida caseira em g/mL, unidade, preço e data de vigência.
   - kcal, proteína, lipídio, carboidrato, sódio por 100 mL/g; água livre e osmolaridade conforme fabricante quando disponíveis.
   - Fonte: imagem/PDF/rótulo/ficha oficial, data de consulta, URL e versão.
   - Nunca preencher valor nutricional, medida ou preço por inferência textual ou por produto similar.

3. **Prescrição/uso diário por paciente**
   - Adicionar um ou vários itens à conduta do paciente.
   - Quantidade diária, unidade, frequência/horário/refeição, via e observação.
   - Guardar snapshot da ficha técnica, apresentação e versão na data do uso.
   - Calcular kcal, proteína, carboidrato, lipídio e sódio por dose e por dia.
   - Calcular percentuais de meta energética/proteica e g/kg, quando houver peso e meta válidos.
   - Permitir comparar dieta enteral + módulos + suplementos e indicar o total de oferta calculado.
   - Mostrar explicitamente o que ficou sem cálculo por falta de dado.

4. **Integração com PEP**
   - A suplementação usada aparece na evolução e no resumo do paciente.
   - Uma alteração de catálogo futura não modifica cálculos/históricos anteriores.
   - Exportar conduta e aporte em PDF/relatório.

5. **Auditoria das planilhas**
   - Reproduzir resultados de casos sintéticos nas abas `Calc dieta PSL PTN`, `Calc dieta Isolate PTN`, `Calc dieta Fres. PTN` e `Oferta`.
   - Comparar unidade, arredondamento, medida e composição com fichas oficiais.
   - Separar propofol de suplementos; só incluir eventual contribuição energética em módulo próprio, com fonte e regra explícitas.

### Entregáveis

- Catálogo técnico versionado, com seis seeds preservados e produtos das planilhas normalizados.
- Ficha técnica com fonte e validade.
- Prescrição/uso diário ligado ao paciente e ao PEP.
- Motor de aporte, % de metas, custo e histórico imutável.
- Testes com produtos sintéticos e casos comparados às planilhas.

### Não pode ser feito

- Não considerar automaticamente válidos os módulos sugeridos no seed.
- Não copiar valores em branco nem preencher por memória do agente.
- Não tratar nome semelhante como a mesma apresentação.
- Não calcular aporte quando unidade ou ficha não estiver disponível.
- Não sobrescrever a composição histórica com o valor atual do catálogo.
- Não converter medida caseira sem peso/volume documentado.

### Critérios de aceite

- Para uma ficha preenchida e dose válida, kcal e nutrientes são calculados com teste independente.
- Cada resultado apresenta composição e versão de referência.
- A mudança de catálogo não altera registros históricos.
- Produtos sem fonte aparecem como “ficha pendente”, sem estimativa inventada.

---

# Fase 6 — Estoque e controle do Serviço de Nutrição

> **Entrega desktop em integração:** cadastro de itens e unidades, histórico de preços, livro de movimentos com estorno, saldo calculado, custos realizados por refeição/dia/mês e programação manual com snapshot de quantidade e preço. A migração é a v5, posterior à anamnese ambulatorial (v4). Não há importação presumida de preços ou fichas técnicas.


**Objetivo:** digitalizar o controle operacional de gêneros e insumos conforme a planilha mensal do setor.

**Agentes:** `supplement-stock-engineer` (líder), `database-backend-engineer`, `legacy-workbook-analyst`, `qa-security-reviewer`.

### Atividades obrigatórias

1. Criar cadastro de insumos com nome, unidade-padrão, custo unitário, categoria, ativo/inativo e estoque mínimo opcional.
2. Preparar importador de planilhas com pré-visualização, validação e relatório de inconsistências.
3. Registrar movimentos de entrada/saída por data, quantidade, unidade, motivo e usuário.
4. Calcular saldo por item; nunca digitar saldo final como fonte de verdade quando ele puder ser derivado dos movimentos.
5. Apresentar total diário e fechamento semanal: entrada, uso, gasto e saldo.
6. Tratar normalização de unidades: KG/Kg, PAC/PCT, UN/UND, LT/LATA etc. Converter somente quando a equivalência for conhecida e documentada; caso contrário, manter unidades distintas.
7. Distinguir estoque de gêneros alimentícios, dietas enterais, suplementos e materiais; permitir relatórios separados.
8. Auditar ajustes, perdas, devoluções, inventário e correções.

### Entregáveis

- Cadastro inicial com estrutura compatível aos 139 itens da planilha, sem importar valores reais para ambientes de teste.
- Livro de movimentos e cálculo de saldo.
- Fechamentos semanais/mensais.
- Importador com relatório de erros e duplicidades.
- Testes de saldo, estorno e mudança de unidade.

### Não pode ser feito

- Não deduzir consumo quando a célula estiver vazia.
- Não zerar estoque automaticamente ao mudar o mês.
- Não somar unidades incompatíveis.
- Não alterar retrospectivamente movimentos fechados sem auditoria.
- Não publicar preço, volume ou fornecedor interno sem autorização de acesso.

### Critérios de aceite

- Saldo reproduzido a partir dos movimentos de entrada/saída.
- Fechamento semanal e mensal auditável.
- Importação de arquivo de teste mantém totais e aponta inconsistências sem corrigir silenciosamente.

---

# Fase 7 — Refeições de pacientes/servidores e módulo móvel

**Objetivo:** criar registro por refeição e apontamento rápido por celular, com acesso restrito à tarefa e ao horário autorizado.

**Agentes:** `mobile-meal-engineer` (líder), `database-backend-engineer`, `desktop-clinical-ui-engineer`, `legacy-workbook-analyst`, `qa-security-reviewer`.

### Atividades obrigatórias

1. **Refeições de pacientes**
   - Registrar por paciente, data e seis refeições: desjejum, lanche manhã, almoço, lanche tarde, jantar e ceia.
   - Guardar oferta, presença/realização e aceitação percentual (0/25/50/75/100) quando aplicável.
   - Diferenciar paciente, acompanhante e oferta extra, se o fluxo institucional exigir.
   - Exibir histórico de aceitação e cruzar com evolução clínica sem gerar conduta automática.

2. **Refeições de servidores**
   - Funcionário autentica com a própria conta e faz apontamento do dia.
   - Registra pessoa, setor, refeição, data/hora de servidor e resultado.
   - Horários solicitados: almoço 12:00–13:00 e jantar 19:00–20:00 (`America/Recife`), configuráveis pelo administrador.
   - Fora da janela, bloquear novo apontamento. Correção de erro deve usar fluxo administrativo auditado.
   - Um funcionário só acessa o módulo/função liberada, sem qualquer acesso ao Mapa/PEP.

3. **Conciliação com as fichas**
   - Converter o controle por setor em totais equivalentes aos campos “fichas entregues”, “fichas recebidas”, “refeições sem ficha” e total por dia.
   - Diferenciar contagem individual de refeições de quantidade de fichas.
   - Criar fechamento por setor e turno.

4. **Importação da planilha de refeições**
   - Usar datas reais das células, não nomes de aba.
   - Sinalizar a anomalia da aba `15-21` com datas de setembro e as lacunas de outubro.
   - Não criar eventos para dias ausentes nem converter branco em zero.
   - Construir pré-visualização e relatório de linhas não importadas.

5. **Tecnologia móvel**
   - Implementar frontend web responsivo/PWA, acessível em celular.
   - Validar identidade, setor, dia, janela e permissão no servidor/API.
   - Reduzir a interface a poucos campos e resposta rápida; tolerar conexão intermitente com fila local segura, sem permitir duplicidade quando sincronizar.

### Entregáveis

- Registro individual de refeições de pacientes.
- Escala de aceitação vinculada à refeição.
- Portal móvel de servidor com permissões mínimas.
- Relatório agregado por setor/dia/turno e conciliação de fichas.
- Importador com tratamento de datas incompletas/anômalas.

### Não pode ser feito

- Não usar uma conta compartilhada para apontamento.
- Não permitir data passada/futura ou horário fora da janela para usuário comum.
- Não validar horário apenas pelo relógio do celular.
- Não mostrar informações clínicas ao perfil operacional.
- Não registrar “consumiu” automaticamente quando não houve confirmação.
- Não considerar que total de ficha é sempre igual ao total de pessoas/refeições.

### Critérios de aceite

- Testes demonstram bloqueio fora da janela, duplicidade, usuário sem permissão e data alterada no cliente.
- Usuário de refeição não consegue acessar qualquer rota clínica.
- Totais móveis são conciliáveis com fichas de almoço/jantar.
- Lacunas da planilha são reportadas sem dados inventados.

---

# Fase 8 — Indicadores, relatórios e painéis

**Objetivo:** unificar indicadores clínicos e operacionais, com definições explícitas e dados rastreáveis.

**Agentes:** `database-backend-engineer`, agente de interface, `qa-security-reviewer` e agente principal integrador.

### Indicadores previstos

- Pacientes atendidos por dia/mês e por setor.
- Perfil de consistência (livre, branda, pastosa, líq/past, líquida), via, acompanhante e características da dieta.
- Suplementos e módulos mais usados; aporte médio e distribuição por meta, quando houver ficha completa.
- Aceitação oral por refeição e distribuição 0–100%.
- Função intestinal e Bristol, sem transformar falta de observação em categoria.
- Evolução de peso, estatura e IMC; curvas/percentis com referência exibida.
- Metas energéticas/proteicas versus oferta calculada.
- Estoque: entradas, saídas, gasto e saldo.
- Refeições por setor/turno, servidor autenticado e conciliação de fichas.

### Regras

- Cada indicador deve definir numerador, denominador, período, filtros e exclusões.
- Distinguir paciente único, atendimento e paciente-dia.
- Não misturar registros clínicos com apontamentos de servidores.
- Agregados para gestão não devem expor nomes ou diagnósticos sem autorização.
- Relatório exportado deve registrar data, filtros, fonte e usuário.

### Entregáveis e aceite

- Painel mensal com filtros e definições dos indicadores.
- PDF/Excel de relatórios com layout consistente.
- Testes de agregação com dataset sintético conhecido.
- Exportações respeitando as permissões do usuário.

### Não pode ser feito

- Não comparar porcentagens com denominadores diferentes sem explicar.
- Não somar paciente-dia como paciente único.
- Não permitir exportação de PII por perfil sem permissão.

---

# Fase 9 — Homologação, piloto e implantação

**Objetivo:** preparar uma versão candidata para uso institucional, com testes técnicos, validação clínica e operação monitorada.

**Agentes:** `qa-security-reviewer` (líder de validação), `database-backend-engineer`, `clinical-evidence-researcher`, agente principal e responsáveis institucionais quando designados.

### Atividades obrigatórias

1. Executar suíte completa em ambiente limpo; repetir em Windows e no executável empacotado.
2. Testar impressões reais de mapa, PEP e relatórios em A4 e nas impressoras do setor, com dados fictícios.
3. Testar concorrência: dois nutricionistas, funcionário mobile e alterações simultâneas.
4. Testar autenticação, permissões, expiração de sessão, auditoria, backup, restauração, perda de conexão e reprocessamento.
5. Executar verificação de privacidade: dados de teste, exportação, logs, anexos, tokens e histórico Git.
6. Fazer homologação clínica de fórmulas, curvas, unidades, siglas, classificações e apresentação dos resultados por responsável profissional.
7. Fazer homologação operacional com equipe de Nutrição/Dietética.
8. Preparar guia, treinamento, plano de suporte, monitoramento, rollback e política de atualização.
9. Realizar piloto restrito antes da liberação geral.

### Não pode ser feito

- Não chamar sistema de produção antes da homologação técnica, clínica e institucional.
- Não migrar/usar dados reais sem backup testado e autorização do hospital.
- Não habilitar assinatura/documentos oficiais sem processo institucional definido.

### Critérios de aceite

- Testes técnicos e de segurança aprovados.
- Casos de teste clínicos conferidos e aprovados pelo responsável habilitado.
- Impressões e exportações homologadas.
- Backup e restauração comprovados.
- Plano de contingência e rollback testados.
- Pendências conhecidas publicadas na versão.

---

## Matriz de responsabilidade dos agentes

| Agente | Responsabilidade principal | Entrega esperada |
|---|---|---|
| Claude principal / integrador | Priorizar fases, definir contratos, delegar, integrar e seguir o roadmap sem esperar autorização por tarefa | PR/commit integrado, status e próximos passos objetivos |
| `clinical-evidence-researcher` | Pesquisar, comparar e documentar referências e fórmulas | Entradas no diário bibliográfico e catálogo de fórmulas |
| `legacy-workbook-analyst` | Interpretar planilhas e transformar modelos reais em requisitos/dicionário de dados | Inventário, mapeamento e importadores testáveis |
| `database-backend-engineer` | Dados, migrações, API, segurança do armazenamento e auditoria | Schema/migrações, serviços e testes de integração |
| `desktop-clinical-ui-engineer` | Interfaces desktop do mapa, anamnese, PEP e relatórios | Telas funcionais e acessíveis integradas à API/camada de dados |
| `supplement-stock-engineer` | Fichas técnicas, cálculo de aporte e estoque | Catálogo versionado, cálculos, movimentos e relatórios |
| `mobile-meal-engineer` | Portal móvel e apontamento de refeições | PWA, rotas seguras, validação de horário e relatórios |
| `qa-security-reviewer` | Testes, privacidade, permissões, regressão e homologação técnica | Evidências reproduzíveis de teste e relatório de risco |

## Regras de autonomia e resolução de dúvidas

- Os agentes podem pesquisar, escolher bibliografia adequada, criar/alterar módulos, propor arquitetura, criar migrações não destrutivas, instalar dependências no ambiente controlado, escrever testes e refatorar quando necessário.
- **Não perguntar ao usuário qual artigo, fórmula ou fonte usar.** Usar a pesquisa prévia de `docs/referencias/RELATORIO_FORMULAS_E_ESTIMATIVAS.txt` e procurar fontes primárias/autoridades quando necessário; registrar todas as decisões no diário bibliográfico.
- Diante de fontes conflitantes, comparar população, faixa etária, método, tamanho da amostra, validação externa, limitações, data e autoridade. Registrar a escolha e as alternativas.
- Se uma questão clínica não tiver solução robusta, não inventar: manter o cálculo marcado como indisponível/pendente de revisão, registrar a lacuna e continuar as partes independentes.
- Não interromper o roadmap por uma dúvida isolada. O bloqueio deve ser localizado na funcionalidade específica.
- Validação humana clínica/institucional é etapa de homologação e liberação para uso assistencial, não motivo para suspender pesquisa ou desenvolvimento técnico.
- Nunca usar autonomia como permissão para apagar dado, quebrar permissão, publicar PII ou produzir conduta automática.

## Definição geral de concluído

Uma fase só está concluída quando: (1) entregáveis estão no repositório; (2) testes relevantes foram executados e os resultados reais registrados; (3) documentação e diário foram atualizados; (4) não há regressão conhecida sem tratamento; (5) migrações têm backup/rollback; (6) nenhum dado real ou segredo entrou no diff; e (7) itens não resolvidos estão listados sem serem apresentados como prontos.
