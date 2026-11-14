# ADR-0004 — Integração do serviço único de banco ao aplicativo

- **Estado:** Aceita (modo local). Complementa a ADR-0001; a remoção do banco real do executável está na ADR-0005.
- **Data:** 13/11/2026 (America/Recife)
- **Fase do ROADMAP:** 0 — atividade 3 (banco em caminho único), parte de integração
- **Branch:** `feat/fase-0-banco-1-integracao` (depende de `feat/fase-0-fundacao-seguranca-banco`)

## Contexto (observado no código real, `main.py`/`setup_db.py` do zip enviado em 12/11/2026)

1. `configurar_banco_dados()` usava `get_writable_path('clinica.db')` (pasta do `.exe`), mas **17 outros pontos** de `main.py`
   (telas de pacientes, consultas, exames, regras, mapa) usavam `os.path.join(get_base_path(), 'clinica.db')`. No executável,
   `get_base_path()` devolve `sys._MEIPASS`, que no modo de uma pasta é `_internal` e no modo de um arquivo é uma pasta
   temporária (PyInstaller, *Run-time Information*, ver ADR-0001). Resultado: o programa gravava pacientes em
   `_internal/clinica.db` e criava tabelas em outro arquivo — a "divisão de banco" descrita no README.
2. `setup_db.py` abria `sqlite3.connect('clinica.db')` com caminho **relativo**: o banco dependia da pasta de onde o script
   era executado.
3. O upload de anexos de pacientes gravava em `get_base_path()/arquivos_pacientes` (em `_internal`), enquanto outro ponto do
   mesmo arquivo lia/gravava em `get_writable_path("arquivos_pacientes")`.
4. O `.gitignore` tinha 6 linhas (`venv/`, `__pycache__/`, `*.pyc`, `build/`, `dist/`, `*.pdf`): **nada protegia**
   `clinica.db`, os backups, `.env` nem `arquivos_pacientes/` (a auditoria da Fase 0 listava 13 caminhos sensíveis sem proteção).
5. A suíte original tinha 1 falha pré-existente (`test_excel`): comparava o texto `<rFont val="Arial"/>`, mas o serializador XML
   do openpyxl pode escrever `<rFont val="Arial" />` (com espaço), conforme o ambiente.

## Decisão

1. **`caminho_do_banco()` em `main.py`** é a única porta de entrada do caminho: delega a `db_service.caminho_banco()` (pasta do
   `.exe` quando empacotado; pasta do projeto em desenvolvimento) e, na **primeira** execução do executável, copia o
   banco-modelo embutido (se houver) para o local gravável — comportamento que `get_writable_path` já tinha. Nunca sobrescreve.
   Os 17 pontos de `get_base_path()` e o de `get_writable_path()` passam a chamar essa função. `get_base_path()` continua
   existindo, apenas para **recursos** (imagens, catálogos JSON).
2. **`garantir_esquema_legado(conexao)`**: o DDL legado de `configurar_banco_dados` foi extraído, sem alteração de conteúdo, para uma
   função idempotente que **não faz commit nem fecha a conexão**. Ela serve de `inicializador_legado` da migração baseline
   (banco novo) e roda de novo numa conexão comum (como antes) para banco existente.
3. **Migrações na abertura:** `db_migracoes.aplicar_migracoes()` roda antes do DDL. Em banco novo, a baseline cria o esquema
   numa transação (`banco-novo`, sem backup). Em banco legado, apenas **adota** a baseline (`adotada-legado`) depois de um
   **backup verificado** em `backups/` (`clinica.backup_AAAAMMDD-HHMMSS_pre-migracao-v1.db`). Se isso falhar, o programa avisa
   e segue (a única migração existente não altera tabelas).
4. **Divisão de banco (proteção de dados):** no executável, se `_internal/clinica.db` tiver pacientes, o programa mostra um aviso
   e **não copia, não move e não apaga nada**; a decisão de qual banco é o oficial é humana (GUIA, seção 6).
5. `setup_db.py` usa o caminho único (deixa de depender da pasta atual).
6. Anexos de pacientes passam a ser gravados em `get_writable_path("arquivos_pacientes")`, como o outro ponto já fazia.
7. `.gitignore`: **união** das regras anteriores com as protetoras (bancos, backups, anexos, planilhas originais do hospital,
   segredos) e `modelo_banco/` (ADR-0005).
8. `test_excel` passa a aceitar espaço opcional antes de `/>`.

## Alternativas consideradas

| Alternativa | Por que não agora |
|---|---|
| Trocar cada `sqlite3.connect(...)` por `db_service.conectar(...)` | Mais alterações em um `main.py` de ~100 KB sem teste de interface; ganho (avisos de pasta de rede/nuvem) pode vir depois. |
| Copiar/mesclar automaticamente `_internal/clinica.db` para a pasta do `.exe` | Pode misturar ou sobrescrever dados clínicos; decisão humana. |
| Mover o banco para `%LOCALAPPDATA%` | Mudaria o local dos dados existentes (ADR-0001). |
| Exibir aviso de OneDrive/rede a cada abertura | Muitos usuários mantêm o projeto em pasta sincronizada; o aviso seria constante. |

## Consequências

- Um único arquivo de banco por instalação; o do executável fica ao lado do `.exe`.
- **Quem já usa o executável antigo:** os pacientes gravados em `_internal` **não somem** — o aviso aponta onde estão.
- Cada banco legado existente ganha **uma** cópia de segurança (`backups/`), que contém dados de pacientes: tratar como sensível
  (o novo `.gitignore` a ignora).
- O DDL legado agora existe uma só vez, numa função testável.

## Como verificar

```bat
python -m unittest discover -s tests -v
```

Evidências desta sessão (Linux, Python 3.12): **131 testes OK** (32 originais + 84 da Fase 0 + 15 de integração).
Além disso, o `configurar_banco_dados` novo foi comparado ao original: em banco novo, mesmo esquema e mesmas 16 linhas-semente;
em **cópia do banco real do usuário**, esquema e conteúdo idênticos por hash em 7 tabelas, com a baseline registrada como
`adotada-legado` e o backup criado. Não foram executados: interface gráfica real, Windows e o executável PyInstaller.

## Pendências

1. Abrir o programa de verdade (desenvolvimento) e, depois, um executável gerado, em pasta de teste.
2. Avisos de pasta de rede/nuvem na interface (`db_service.avisos_local`).
3. Demais scripts soltos na raiz (`_check_status.py`, `_smoke_*.py`, `_fix_*.py`) abrem `clinica.db` por caminho relativo; não fazem parte do app.
4. O `.spec` ainda embute o banco do desenvolvedor: ver ADR-0005.
