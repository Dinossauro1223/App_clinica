# NutriLab (app_clinica)

Sistema desktop **offline** de apoio à decisão clínica para a prática nutricional. Interpreta exames laboratoriais, apoia a avaliação nutricional (anamnese, composição corporal) e gera PDFs de conduta e de exames solicitados.

> **Aviso:** ferramenta de apoio. Não substitui o julgamento clínico do profissional.

## Motivação

- **Soberania e privacidade dos dados:** execução 100% local, sem dependência de rede ou de serviços de terceiros.
- **Regras customizáveis:** pontos de corte e alvos terapêuticos atualizáveis conforme as diretrizes vigentes (SBD, SBC, BRASPEN, entre outras), sem depender de plataformas comerciais fechadas.

## Funcionalidades

- Cadastro de pacientes e registro de consultas
- Catálogo de exames e registro de resultados
- Regras de exames complementares (exame-gatilho → exame sugerido), carregadas de `regras_exames_complementares.json`
- Biblioteca de condutas, prescrições e sintomas em JSON (`condutas_internas/`, `prescricoes_internas/`, `sintomas_internos/`, `exames_internos/`)
- Geração de PDF de conduta e de exames solicitados
- Anexos por paciente (`arquivos_pacientes/`)
- **Mapa Nutricional**: registro diário por leito (anamnese estruturada num só lugar), histórico por paciente, estimativa de altura e peso (Chumlea), IMC classificado por faixa etária, impressão em PDF e Excel, gráficos mensais e catálogo de suplementos com ficha técnica (ver seção abaixo)

## Stack

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3 |
| Interface | CustomTkinter |
| Banco de dados | SQLite (`clinica.db`) |
| PDF | FPDF |
| Imagens | Pillow |
| Planilhas (mapa em Excel) | openpyxl |
| Gráficos do mapa | matplotlib (backend Agg) |
| Distribuição | PyInstaller |

## Estrutura do projeto

```
.
├── main.py                           # Aplicação (classe AppClinica, GUI + lógica)
├── setup_db.py                       # Criação do schema e importação inicial dos JSONs
├── nutri_calculos.py                 # Cálculos antropométricos e classificação do IMC (sem GUI)
├── mapa_db.py                        # Banco do Mapa: leitos, registros diários, suplementos
├── mapa_export.py                    # Exportação do mapa para Excel e PDF
├── mapa_graficos.py                  # Agregação mensal e gráficos
├── mapa_ui.py                        # Telas do Mapa, Gráficos e Suplementos
├── tests/                            # Testes automatizados (unittest)
├── app_clinica.spec                  # Configuração do PyInstaller
├── regras_exames_complementares.json # Regras de exames complementares
├── exames_internos/                  # Definições de exames (JSON)
├── condutas_internas/                # Condutas (JSON)
├── prescricoes_internas/             # Prescrições (JSON)
├── sintomas_internos/                # Sintomas (JSON)
└── arquivos_pacientes/               # Anexos e PDFs por paciente (não versionar)
```

## Modelo de dados (SQLite)

Tabelas principais: `Pacientes`, `Consultas`, `Exames_Catalogo`, `Regras_Complementares`, `Exames_Solicitados`, `Resultados_Exames`, `Arquivos_Paciente`.

O banco é a **fonte da verdade** para dados salvos e relatórios (referência por `id_consulta`), e não apenas o estado da interface. A consulta de exames solicitados para o PDF usa `LEFT JOIN` + `COALESCE`, para que itens cujo catálogo foi alterado continuem listados.

## Instalação e execução (desenvolvimento)

```bash
git clone https://github.com/neisbila32-cpu/app_clinica.git
cd app_clinica

python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install customtkinter fpdf pillow openpyxl matplotlib pyinstaller

python setup_db.py   # cria/inicializa o clinica.db
python main.py
```

No modo de desenvolvimento, ferramentas de apoio (ex.: "Importar Padrão", "Importar Referências") ficam visíveis.

## Build do executável

```bash
pyinstaller app_clinica.spec
```

O executável é gerado em `dist/`. No `.exe`, os botões de desenvolvimento são ocultados com:

```python
if not getattr(sys, 'frozen', False):
    ...  # ferramentas visíveis apenas fora do executável
```

## Mapa Nutricional

Menu lateral: **Mapa Nutricional**, **Gráficos do Mês** e **Suplementos**.

- **Leitos:** cadastre setores e leitos em *Mapa Nutricional > Leitos* (há gerador de sequência, ex.: L01 a L20).
- **Registro do dia:** duplo clique no leito. Campos: acompanhante, nome, idade, sexo, cor, AJ, PP, PB, altura e peso (estimado/real, com botões de estimativa), IMC automático com a classificação, reavaliação prevista, via da dieta, características, consistência, suplementos (lista suspensa por módulo), observações (Sim/Não) e função intestinal.
- **Dias anteriores:** navegue pela data (◀ ▶ ou digite). *Copiar último mapa* traz os pacientes do dia anterior; *Remover do mapa* serve para alta/transferência. *Histórico* lista todos os registros do paciente.
- **Impressão:** botões *PDF* (A4 paisagem, títulos abreviados e legenda) e *Excel* (uma linha por leito; célula do paciente em 4 linhas, nome em Arial 10 negrito, demais em Arial 8, classificação do IMC em vermelho entre parênteses).
- **Gráficos:** pacientes atendidos por dia, perfil por dia (pastosa, acompanhante, suplemento), consistência, via/acompanhante/suplemento, suplementos mais usados e uso por módulo. Cada registro (um leito num dia) conta como um atendimento.
- **Suplementos:** ficha técnica por 100 mL/g (kcal, proteína, lipídio, carboidrato, sódio), embalagem, preço e módulo. A classificação inicial dos seis itens é sugerida: confirme com a ficha técnica.
- **Configurações:** critério de IMC do idoso (Lipschitz ou OPAS) e equação de altura a partir dos 60 anos (Chumlea 1985 ou 1998).

Tabelas criadas no `clinica.db` (mesmo banco da tela Pacientes): `Mapa_Setores`, `Mapa_Leitos`, `Mapa_Modulos`, `Mapa_Suplementos`, `Mapa_Registros`, `Mapa_Registro_Suplementos`, `Mapa_Config`. Os registros guardam o nome e o módulo do suplemento no momento do uso, então trocar o catálogo não altera o histórico. Pacientes novos são criados em `Pacientes`; o vínculo com um cadastro existente é sempre confirmado pelo usuário.

**IMC de crianças e adolescentes (< 19 anos)** exige as tabelas LMS da OMS. Coloque em `dados/oms_imc_idade_lms.csv` (ao lado do `clinica.db`) um CSV com cabeçalho `sexo;idade_meses;L;M;S`, com `sexo` = `masculino` ou `feminino` e linhas de 0 a 228 meses (OMS 2006 para 0 a 60 meses; OMS 2007 para 61 a 228). Sem o arquivo, o mapa mostra "tabela OMS pendente" no lugar da classificação.

**Testes:** `python -m unittest discover -s tests -v` (os testes de interface usam widgets simulados; os de PDF usam um FPDF simulado quando a biblioteca real não está instalada).

## Convenções

- `snake_case` para variáveis e funções (ex.: `gerar_pdf_evolucao`); `PascalCase` para classes (ex.: `AppClinica`).
- Banco de dados como fonte da verdade (`id_consulta`).
- Referências bibliográficas no formato "Carvalho; Souza, 2024".
- Código preparado para rodar puramente local (offline).

## Privacidade

Este projeto lida com dados de saúde. **Não versione** `clinica.db`, backups `.db*` nem `arquivos_pacientes/` com dados reais. Mantenha-os no `.gitignore`.

## Status e roadmap

- [x] Exames solicitados corretos no PDF
- [x] Botões de dev ocultos no executável
- [x] Mapa Nutricional (fase 1): registro diário, histórico, PDF/Excel, gráficos e catálogo de suplementos
- [ ] Mapa: ficha técnica completa dos suplementos, cálculo de oferta (kcal/proteína) e custo
- [ ] Calculadoras: necessidades energéticas, composição corporal e índices de risco
- [ ] Revisão científica de valores de referência e alvos terapêuticos
- [ ] Importação das novas diretrizes via planilha padronizada para o `clinica.db`
- [ ] Refletir regras condicionais (população, sexo, idade, condição clínica) na lógica do app

## Fontes clínicas

SBD, SBC, BRASPEN e demais diretrizes citadas por exame (campos `fonte`, `link` e `ano_diretriz` na planilha de referência).