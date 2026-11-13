# Guia de desenvolvimento e execução no Windows

Atualizado em 10/11/2026 (Fase 0). Os comandos abaixo usam o Prompt de Comando (`cmd`). No PowerShell, troque
`.venv\Scripts\activate` por `.venv\Scripts\Activate.ps1`.

> **Estado de validação:** estes passos foram escritos e conferidos em Linux (Python 3.12). **Ainda não foram executados
> no Windows nem contra o código do aplicativo.** Se algum passo falhar, anote a mensagem exata: ela é o dado mais útil
> para corrigir o guia.

## 1. Pré-requisitos

- Windows 10 ou 11, 64 bits.
- **Python 3.12 (64 bits)** de python.org. No instalador, marque *Add python.exe to PATH* e mantenha *tcl/tk and IDLE*
  (necessário para a interface). Confira: `py -3.12 --version`.
- **Git for Windows.** Confira: `git --version`.

## 2. Criar o ambiente

Na pasta do repositório:

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python tools\verificar_ambiente.py
```

`verificar_ambiente.py` confere versão do Python, versões fixadas, conflito `fpdf`/`fpdf2`, fuso `America/Recife` e
`tkinter`. Como ler a saída:

| Mensagem | O que fazer |
|---|---|
| `Conflito de PDF` | `python -m pip uninstall fpdf pyfpdf` e depois `python -m pip install -r requirements.txt`. |
| `fuso America/Recife indisponível` | `python -m pip install tzdata`. |
| `<pacote>: instalado X, fixado Y` (aviso) | Seu ambiente difere do fixado. Se o programa funciona, **não force**: avise para decidir se o `requirements.txt` deve mudar (ADR-0002). |
| `tkinter indisponível` | Reinstale o Python marcando *tcl/tk and IDLE*. |

## 3. Executar o programa

```bat
.venv\Scripts\activate
python main.py
```

Em desenvolvimento use **banco sintético/descartável**, nunca uma cópia do banco real. O serviço `db_service.py` aceita
`NUTRILAB_DATA_DIR` (pasta) ou `NUTRILAB_DB_PATH` (arquivo) para apontar para um banco de teste — **o `main.py`, o `setup_db.py` e o mapa já usam o serviço** (ADR-0004): com `NUTRILAB_DB_PATH` ou `NUTRILAB_DATA_DIR`
definidas, o programa abre esse banco em vez do `clinica.db` da pasta do projeto.

## 4. Testes

```bat
.venv\Scripts\activate
python -m unittest discover -s tests -v
```

Registre sempre o resultado real (quantos testes, quantas falhas). Teste de interface ou PDF feito com simulador não
comprova impressão nem interação com a biblioteca real.

## 5. Auditoria antes de qualquer push

```bat
python tools\auditar_repositorio.py
```

Verifica arquivos rastreados, arquivos novos ainda não ignorados, **histórico** (arquivo sensível já commitado mesmo que
apagado depois) e se o `.gitignore` ignora de fato os padrões obrigatórios. **Nunca imprime conteúdo de arquivos**: só
caminho, número de linha e categoria.

- `BLOQUEIO` (banco `.db`, backup, anexos de pacientes, chaves/`.env`, planilhas originais do hospital, CPF válido no
  texto): **não faça push.** Retire do próximo commit com `git rm --cached -- <caminho>` (o arquivo local permanece) e
  confira o `.gitignore`.
- Achado de origem `historico`, ou algo que já foi enviado ao GitHub: **pare de enviar** e avise o responsável; o
  `.gitignore` não remove o que já foi versionado e a limpeza do histórico precisa ser planejada.
- `REVISAR` (PDF/XLSX/ZIP, e-mail, telefone, possível credencial): confirme que são genéricos. Se forem modelos
  sintéticos legítimos, liste-os em `tools\auditoria_permitidos.txt` (um padrão por linha, com `#` para comentar).
  Achados de `BLOQUEIO` **nunca** podem ser liberados por essa lista.

## 6. Banco de dados: diagnóstico, backup e restauração

Diagnóstico **somente leitura** (mostra tamanho, versão do esquema, integridade e número de linhas por tabela; não mostra
conteúdo):

```bat
python tools\diagnostico_banco.py "C:\caminho\da\pasta\do\aplicativo"
```

Se aparecer `DIVISÃO DE BANCO` (o mesmo `clinica.db` em duas pastas, por exemplo ao lado do `.exe` e em `_internal`),
**não apague nem copie um sobre o outro**: gere backup de todos e combine com o responsável qual é o oficial.

Backup manual verificado (funciona com o banco aberto):

```bat
python -c "import db_service as s; print(s.criar_backup(r'C:\caminho\clinica.db', motivo='manual'))"
```

O backup vai para a pasta `backups\` ao lado do banco. Restauração (**feche o programa antes**; o banco atual é salvo
como `pre-restauracao`):

```bat
python -c "import db_service as s; print(s.restaurar_backup(r'C:\caminho\backups\clinica.backup_AAAAMMDD-HHMMSS_manual.db', r'C:\caminho\clinica.db'))"
```

Treine primeiro com um banco sintético.

## 7. Gerar o executável (PyInstaller)

```bat
python -m pip install -r requirements-build.txt
pyinstaller app_clinica.spec
```

Depois de gerar, rode `python tools\diagnostico_banco.py dist` e abra o programa uma vez em uma pasta de teste: o
`clinica.db` deve nascer **ao lado do `.exe`**, nunca dentro de `_internal`. Este passo **ainda não foi validado**
(ADR-0001, pendência 2).

## 8. Integração contínua

`.github/workflows/ci.yml` roda em Windows e Linux (Python 3.12): instala `requirements.txt`, verifica o ambiente,
audita o repositório e executa os testes. Ainda não foi executado no GitHub.

## 9. Branches e commits (regra do projeto)

- Trabalhe em branch pequena: `feat/fase-N-assunto`, `fix/...`, `docs/...`.
- **Todo commit deve trazer o dia do commit e dizer no que se está trabalhando naquele branch** (facilita a limpeza e a
  integração com as demais frentes). Modelo:

```text
[10/11/2026] feat/fase-0-fundacao-seguranca-banco: serviço único de banco e migrações

<o que mudou, em poucas linhas>

Data-do-commit: 2026-11-10 (America/Recife)
Branch: feat/fase-0-fundacao-seguranca-banco
Trabalhando-em: Fase 0 — banco em caminho único
```

- Antes do push: `python tools\auditar_repositorio.py` e `python -m unittest discover -s tests -v`.
- Nunca inclua `.db`, backups, anexos de pacientes, planilhas/PDFs reais do hospital, `.env` ou chaves.
