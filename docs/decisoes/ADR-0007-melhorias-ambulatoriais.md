# ADR-0007 — Ampliação do atendimento ambulatorial

- **Status:** Aceita para implementação inicial; homologação clínica e interface Windows pendentes.
- **Data:** 22/11/2026
- **Branch:** `feat/ambulatorial-anamnese-2026-11-22)

## Contexto

A tela de consulta já guardava anamnese, antropometria, conduta, exames solicitados e resultados em campos parcialmente livres. O perfil do paciente já aceitava anexos em vários formatos e o projeto passou a oferecer condutas de alta confirmadas pela nutricionista. Era necessário dar estrutura à anamnese ambulatorial, reutilizar documentos orientativos do profissional e aproximar exames, metas e necessidades do mesmo atendimento.

A branch principal foi usada como base para preservar as atualizações já integradas ao repositório. A branch da NRS-2002 mencionada na solicitação não estava presente na lista pública de branches consultada em 22/11/2026.

## Decisão

### 1. Anamnese e plano

- Criar campos guiados por grupos (história/objetivos, alimentação/rotina, sinais/contexto).
- Manter anotações livres existentes como complemento, não descartá-las.
- Disponibilizar recordatório de 24 horas opcional, vazio por padrão.
- Manter medicamentos em uso e metas em listas estruturadas separadas.
- Gerar texto consolidado copiável para colar no SoftSus; a cópia não depende de exportação ou integração direta com o SoftSus.
- Salvar o conteúdo estruturado em tabelas próprias associadas à consulta. O campo textual legado `Consultas.anamnese` também recebe o texto consolidado para manter compatibilidade com o histórico atual.

### 2. Antropometria e estimativas

- Peso e altura continuam opcionais. Quando informados, o IMC é calculado automaticamente.
- Exibir EER DRI 2023 e fórmula de bolso lado a lado, sem substituir o mecanismo legado de TMB/VET.
- A DRI implementada nesta fase é a equação de EER de adultos não gestantes/não lactantes (19 anos ou mais), com peso (kg), estatura (cm), idade e categoria PAL. A fórmula pediátrica, gestação e lactação não são extrapoladas.
- A fórmula de bolso permite selecionar de 25 a 35 kcal/kg/dia.
- A necessidade proteica é calculada apenas quando o profissional informa um fator g/kg. Não há dose padrão ou prescrição automática.
- Apresentar os números como estimativas de apoio à decisão e preservar o fator/método usado no registro.

**Fonte primária:** National Academies of Sciences, Engineering, and Medicine. *Dietary Reference Intakes for Energy*. Washington, DC: The National Academies Press; 2023. Capítulo 5, Tabela 5-16 (equações de EER para adultos). DOI: https://doi.org/10.17226/26818. A documentação de referência complementar da Health Canada foi usada para conferir as categorias de atividade física e os coeficientes publicados: https://www.canada.ca/en/health-canada/services/food-nutrition/healthy-eating/dietary-reference-intakes/tables/reference-values.html.

### 3. Biblioteca de recomendações DOCX

- A nutricionista pode cadastrar documentos `.docx` com título, caso clínico/situação de uso e palavras-chave.
- Antes de armazenar, validar extensão, assinatura estrutural básica do pacote DOCX e tamanho máximo de 25 MB. Calcular SHA-256 para rastreabilidade.
- Copiar o documento para a pasta de dados local do programa, sob `recomendacoes_clinicas/`, e salvar somente o caminho relativo no banco.
- A consulta permite selecionar recomendações da biblioteca, associá-las ao paciente e registrar a conduta/plano relacionado.
- O documento abre no aplicativo padrão (por exemplo, Microsoft Word) para revisão e impressão. O conteúdo não é interpretado nem modificado pelo programa.

### 4. Exames e diagnósticos

- Preservar o catálogo, regras complementares e fluxo de seleção já existentes.
- Adicionar associações configuráveis do exame para: exame complementar recomendado, diagnóstico clínico relacionado ou diagnóstico nutricional relacionado.
- Guardar justificativa e fonte como campos opcionais. Apresentar associações como lembretes para revisão profissional; não criar diagnósticos, resultados ou solicitações automaticamente.

### 5. NRS-2002

- Criar estrutura para registrar resultado de triagem (instrumento, versão, pontuação, classificação, JSON de resposta, origem).
- O serviço `registrar_resultado_triagem` recebe resultado calculado pelo módulo emissor. Esta branch não implementa nem duplica o algoritmo NRS-2002.
- A ligação funcional com a tela/módulo NRS depende de integrar a branch que contém esse trabalho, revisar seu contrato e adicionar testes de integração. Até lá, a tabela é apenas o ponto de persistência preparado.

## Banco e reversibilidade

A migração v4 adiciona:

- `Consulta_Dados_Estruturados`
- `Consulta_Medicamentos`
- `Consulta_Metas`
- `Recomendacoes_Docs`
- `Consulta_Recomendacoes`
- `Exames_Associacoes`
- `Consulta_Triagens`

A migração possui instruções `down` e não altera nem remove colunas/tabelas legadas. Os arquivos DOCX ficam fora do Git, na pasta de dados do aplicativo. O rollback da migração remove as tabelas e perde os vínculos cadastrados após a migração; por isso, deve ser precedido pelo mecanismo habitual de backup verificado (`db_migracoes`/`db_service`). O rollback da migração não apaga arquivos DOCX automaticamente: a limpeza pode ser feita depois de conferir referências e backups.

## Testes e critérios pendentes

- Testes unitários do cálculo DRI (caso de referência da publicação), IMC, fórmula de bolso, proteína, validação de faixa e geração do texto.
- Testes de persistência de anamnese, recordatório, medicamentos, metas, vínculos DOCX, recomendações de exames, diagnósticos e contrato de triagem.
- A executar após o push: CI da branch em Windows e Linux; conferir especialmente CustomTkinter, seletor de arquivos, abertura/ impressão do DOCX e navegação real das telas.
- Homologação clínica da anamnese, dos rótulos e das fórmulas deve ser feita antes do uso assistencial. A equação DRI de adultos não deve ser usada em populações fora do escopo descrito.
