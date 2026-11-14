# ADR-0001 — Banco local: caminho único, backup verificado e migrações versionadas

- **Estado:** Aceita para o modo local (desenvolvimento e uso individual). Não define o banco multiusuário (ver ADR-0003).
- **Data:** 10/11/2026 (America/Recife)
- **Fase do ROADMAP:** 0 — atividade 3 (banco em caminho único)
- **Branch:** `feat/fase-0-fundacao-seguranca-banco`
- **Papéis:** `database-backend-engineer` (líder) e `qa-security-reviewer`, executados em sequência pelo agente integrador
  (a delegação paralela a subagentes não estava disponível na sessão).

## Contexto

1. O README (seção 2.3), baseado na análise do código-fonte, registra uma inconsistência: `configurar_banco_dados()` usa
   `get_writable_path('clinica.db')`, enquanto a inicialização do mapa e várias operações de pacientes/consultas usam
   `get_base_path()`. No executável PyInstaller, `get_base_path()` pode apontar para `_internal` e `get_writable_path()`
   para a pasta do `.exe`. **O código não estava acessível quando esta ADR foi escrita; o problema vem do README e não
   foi reproduzido aqui.**
2. A documentação do PyInstaller informa que o bootloader define `sys.frozen` e guarda em `sys._MEIPASS` o caminho do
   pacote: em um pacote de **uma pasta** é o `_internal`; em um pacote de **um arquivo** é uma pasta temporária criada
   pelo bootloader. Já `sys.executable` é o executável lançado, e `os.path.dirname(sys.executable)` é o caminho indicado
   para arquivos que ficam junto do programa. Logo, `_MEIPASS` serve para recursos empacotados (somente leitura), não
   para dados gravados pelo usuário; no modo de um arquivo esses dados ficariam numa pasta temporária.
3. A documentação do SQLite diz que a API de backup é o meio mais confiável de copiar um banco; que copiar o arquivo
   durante uma transação pode produzir uma cópia com mistura de conteúdo antigo e novo (corrompida); que o journal/WAL
   deve acompanhar o arquivo; e que sobrescrever um banco sem tratar o *journal* "quente" do original é causa de
   corrupção. Sobre redes: os bloqueios de escrita do SQLite já se mostraram incorretos em alguns sistemas de arquivos de
   rede, com casos de corrupção, e a própria documentação sugere um banco cliente/servidor (cita o PostgreSQL).

## Decisão

1. **Uma única fábrica de caminho:** `db_service.caminho_banco()`. Ordem: (a) `NUTRILAB_DB_PATH` (arquivo completo;
   desenvolvimento/testes); (b) `NUTRILAB_DATA_DIR` + nome do banco; (c) pasta do `.exe` quando empacotado (`sys.frozen`)
   ou pasta do projeto em desenvolvimento. Isso **preserva a convenção atual de `get_writable_path()`**, para não "perder"
   bancos que já existem.
2. **`_MEIPASS`/`_internal` nunca são usados para dados.**
3. **Toda conexão passa por `db_service.conectar()`**: cria a pasta do banco se necessário; emite `RuntimeWarning` para
   pasta de rede, pasta sincronizada na nuvem (OneDrive, Dropbox, Google Drive...) e `Program Files`; e **não altera
   PRAGMAs** a menos que o chamador peça (`foreign_keys=None` por padrão), para não mudar o comportamento do código
   legado (ligar chaves estrangeiras de repente poderia fazer operações antigas falharem).
4. **Backup:** `criar_backup()` usa a API de backup do SQLite (consistente mesmo com o banco aberto), grava em `backups/`
   ao lado do banco com o nome `<banco>.backup_AAAAMMDD-HHMMSS_<motivo>.db` (horário de America/Recife), nunca
   sobrescreve outro backup e **verifica a integridade** da cópia; se a verificação falhar, a cópia é descartada e o
   erro é propagado.
5. **Restauração:** `restaurar_backup()` valida o backup; cria antes uma cópia de segurança do banco atual
   (`pre-restauracao`); restaura num arquivo temporário e o valida; **move (não apaga)** os auxiliares
   `-wal`/`-shm`/`-journal` do banco antigo para `*.antes-da-restauracao`; e só então troca o arquivo de forma atômica
   (`os.replace`). Se qualquer passo falhar, o banco atual permanece intacto. No Windows, o programa precisa estar fechado.
6. **Migrações versionadas em código** (`db_migracoes.MIGRACOES`), cada uma numa transação (`BEGIN IMMEDIATE`), com
   checksum registrado em `schema_migrations`. A versão 1 é a **baseline** do esquema legado: em banco existente é apenas
   *adotada* (nenhuma tabela é tocada); em banco novo executa um `inicializador_legado` fornecido pelo chamador. Antes de
   aplicar ou reverter, cria-se um backup verificado (se falhar, nada é alterado). Migração alterada depois de aplicada,
   ou banco migrado por uma versão mais nova do programa, são recusados.
7. **Rollback por dois caminhos testados:** scripts `down` (`reverter_migracoes`) e restauração do backup `pre-migracao-vN`.
8. **Diagnóstico somente-leitura** (`tools/diagnostico_banco.py`) para localizar a "divisão de banco" (o mesmo
   `clinica.db` em duas pastas), mostrando apenas contagens por tabela; nunca funde, move ou apaga.

## Alternativas consideradas

| Alternativa | Por que não agora |
|---|---|
| Manter `get_base_path()` como caminho do banco | Aponta para `_internal` ou pasta temporária: inadequado para dados graváveis (contexto, item 2). |
| Mover os dados para `%LOCALAPPDATA%\NutriLab` | É a prática comum para aplicativos instalados, mas **muda o local dos dados existentes** e exige migração assistida e decisão do responsável; o local do banco real não foi observado. Fica como evolução. |
| Arquivos `.sql` numa pasta `migrations/` | Exigiria incluí-los no `.spec` do PyInstaller; migrações em código entram no executável pelo próprio *import*. |
| Alembic/SQLAlchemy | Dependência e ORM que o projeto não usa; reavaliar na Fase 3 com o banco central. |
| Ativar o modo WAL | Altera o modo de journal de bancos existentes e cria arquivos auxiliares; sem necessidade comprovada no uso individual. |

## Consequências

- **Positivas:** um só ponto decide onde o banco fica; backups verificados e reversíveis; migrações auditáveis; avisos
  sobre locais perigosos; diagnóstico sem expor dados.
- **Custos:** o código legado precisa ser **adaptado** para chamar `db_service` (ainda não feito); o checksum impede
  "consertar" uma migração já aplicada (intencional: cria-se uma nova); no Windows o `os.replace` falha se outro
  processo estiver com o arquivo aberto.
- **Privacidade:** os módulos novos nunca registram conteúdo de linhas. Mensagens de erro de migração trazem só o tipo da
  exceção e o texto do SQLite (nomes de tabela/coluna).

## Como verificar

```bat
python -m unittest tests.test_db_service tests.test_db_migracoes tests.test_diagnostico_banco -v
python tools\diagnostico_banco.py "C:\pasta\do\aplicativo"
```

Os 50 testes desses três arquivos usam bancos **sintéticos**: do zero, de versão anterior, falha no meio de uma migração,
backup corrompido, restauração com falha na troca final, divisão de banco etc. O esquema legado usado nos testes
(Pacientes/Consultas) é **mínimo e inventado para o teste**; não é o DDL real do aplicativo.

## Pendências e riscos

1. **Integração:** substituir `get_base_path()`/`get_writable_path()` e as conexões diretas de `main.py`, `mapa_db.py` e
   `setup_db.py` por `db_service` (passando o DDL legado e `mapa_db.inicializar` como `inicializador_legado`).
   Bloqueada por falta de acesso ao código.
2. **Executável real:** rodar `tools/diagnostico_banco.py` na pasta `dist`, confirmar que o `clinica.db` nasce junto do
   `.exe` e verificar se o `app_clinica.spec` inclui o `tzdata`.
3. **Windows:** nada foi executado no Windows (somente Linux, Python 3.12).
4. **Dados já divididos:** se existirem dois `clinica.db` com dados diferentes, decidir qual é o oficial é uma decisão
   humana (ver o diagnóstico).
5. Evolução para `%LOCALAPPDATA%`: decisão separada, com migração assistida.

## Referências (consultadas em 10/11/2026)

- PyInstaller — *Run-time Information*: https://pyinstaller.org/en/stable/runtime-information.html
- SQLite — *How To Corrupt An SQLite Database File*, item "Backup or restore while a transaction is active"
  (lido em https://sqlite.org/draft/howtocorrupt.html e no espelho https://docs.w3cub.com/sqlite/howtocorrupt.html).
- SQLite — *SQLite Over a Network, Caveats and Considerations*: https://sqlite.org/useovernet.html
