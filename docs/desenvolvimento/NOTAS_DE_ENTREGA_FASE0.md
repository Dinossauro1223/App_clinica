# Notas de entrega — Fase 0 (fundação técnica, segurança e reprodutibilidade)

- **Data:** 10/11/2026 (America/Recife)
- **Branch:** `feat/fase-0-fundacao-seguranca-banco`
- **Situação:** entrega **parcial e honesta**: tudo o que não dependia do código do aplicativo foi feito e testado; o que
  depende dele está listado em "Pendências".

## Contexto da sessão

- O repositório `Dinossauro1223/App_clinica` não é público (clone sem credenciais falhou) e **o código do aplicativo não foi
  enviado**: só o pacote de documentação. Portanto **não foi possível** comparar o código com o README/ROADMAP; a "primeira
  fase incompleta" foi identificada pela própria tabela do ROADMAP (Fase 0: "Necessária; incompleta").
- A delegação paralela a subagentes não estava disponível: os papéis `database-backend-engineer`, `qa-security-reviewer`
  e `documentation-roadmap-writer` foram executados em sequência pelo agente integrador, seguindo seus perfis.

## O que foi entregue

| Item | Arquivos |
|---|---|
| Auditoria de dados sensíveis/segredos (sem imprimir conteúdo) | `tools/auditar_repositorio.py` |
| Verificação de ambiente (versões, fpdf×fpdf2, fuso, tkinter) | `tools/verificar_ambiente.py` |
| Serviço único de banco (caminho, conexão, backup, restauração) | `db_service.py` |
| Migrações versionadas e reversíveis | `db_migracoes.py` |
| Diagnóstico somente-leitura / "divisão de banco" | `tools/diagnostico_banco.py` |
| Dependências fixadas e lock | `requirements.txt`, `requirements.lock.txt`, `requirements-build.txt` |
| CI (Windows + Linux) | `.github/workflows/ci.yml` |
| ADRs 0001–0003 e índice | `docs/decisoes/` |
| Guia de desenvolvimento no Windows | `docs/desenvolvimento/GUIA_DESENVOLVIMENTO_WINDOWS.md` |
| Testes (84) | `tests/test_*.py` (5 arquivos) |
| Atualização de status | `ROADMAP.md` (Fase 0), `README.md` (seções 2.3, 9, 10 e 12) |

## Como verificar

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python tools\verificar_ambiente.py
python -m unittest discover -s tests -v
python tools\auditar_repositorio.py
```

## Testes (resultado real)

- `python -m unittest discover -s tests` → **Ran 84 tests … OK** em Linux x86_64, Python 3.12.3, num venv criado a partir de
  `requirements.txt` e também com o Python do sistema (os testes só usam a biblioteca padrão).
  Por arquivo: verificar_ambiente 14, auditar_repositorio 20, db_service 23, db_migracoes 18, diagnostico_banco 9.
- `pip check` sem conflitos; `verificar_ambiente.py` → OK (único aviso: `tkinter` ausente no ambiente de teste).
- `auditar_repositorio.py` no próprio branch → 0 BLOQUEIO, 0 REVISAR.
- **Não executado:** Windows; PyInstaller; interface gráfica; suíte de testes do aplicativo; o workflow de CI no GitHub.

## Banco

- Migração sintética **do zero** e **de versão anterior** testadas; falha no meio de uma migração desfaz só a migração
  com erro; **rollback** testado pelos dois caminhos (scripts `down` e restauração do backup `pre-migracao-vN`);
  checksum alterado e banco mais novo que o programa são recusados; backup corrompido não substitui o banco atual.
- O esquema legado dos testes é **sintético e mínimo** (Pacientes/Consultas); não é o DDL real.
- Nenhum banco real foi tocado (nenhum estava disponível).

## Fontes

Registradas nas ADRs (PyInstaller, SQLite, PostgreSQL, PyPI, GitHub Actions). Nenhuma dúvida **clínica/bibliográfica**
surgiu nesta fase; por isso o `DIARIO_DUVIDAS_BIBLIOGRAFICAS.md` não recebeu entrada.

## Segurança

- Varredura do próprio diff: 0 BLOQUEIO, 0 REVISAR. Nenhum dado real, segredo ou planilha foi incluído.
- Os testes montam valores com aparência de CPF/e-mail/token em tempo de execução, para o repositório não se auto-sinalizar.
- As ferramentas nunca imprimem conteúdo de arquivos ou de linhas de banco.

## Pendências (e por quê)

1. **Auditoria do repositório real** (`git status`, arquivos rastreados, histórico): precisa rodar onde o repositório está.
2. **Integração do serviço de banco** em `main.py`, `mapa_db.py` e `setup_db.py` (mapear chamadas SQLite): código inacessível.
3. **Validação no Windows** e do executável PyInstaller (local do `clinica.db`, `tzdata` no `.spec`).
4. **Suíte de testes do aplicativo** contra as versões fixadas (em especial customtkinter 5.2.2 × 6.x).
5. **CI** ainda não executado no GitHub.
6. **ADR-0003** é proposta: depende de decisões do hospital (hospedagem, autenticação, LGPD).

## Próxima tarefa

Assim que o código estiver acessível: itens 1–4 acima, nessa ordem. Em paralelo, e sem depender do código: Fase 2
(conferência das equações de estimativa contra as fontes, com registro no diário bibliográfico).
