# Notas de entrega — Fase 0, integração do banco ao aplicativo

- **Data:** 13/11/2026 (America/Recife) · **Branch:** `feat/fase-0-banco-1-integracao` (empilhado sobre `feat/fase-0-fundacao-seguranca-banco`)
- **Base:** código real do zip `App_clinica-main` enviado em 12/11/2026 (sem os dados de pacientes, que nunca foram copiados para o repositório).

## O que mudou

| Arquivo | Mudança |
|---|---|
| `main.py` | `caminho_do_banco()` (única porta do caminho); 17+1 pontos passam a usá-la; DDL legado extraído para `garantir_esquema_legado()`; migrações na abertura; aviso de "dois bancos"; anexos na pasta gravável |
| `setup_db.py` | usa o caminho único |
| `.gitignore` | união com as regras protetoras (bancos, backups, anexos, planilhas, segredos) |
| `tests/test_mapa.py` | `test_excel` tolera espaço antes de `/>` (falha pré-existente) |
| `tests/test_integracao_banco.py` | 15 testes novos |
| `docs/decisoes/ADR-0004-...md` | decisão, alternativas, evidências e pendências |
| `docs/desenvolvimento/GUIA_DESENVOLVIMENTO_WINDOWS.md` | seção 3 atualizada |

## Testes (resultado real)

`python -m unittest discover -s tests` → **Ran 131 tests — OK** (Linux, Python 3.12.3; venv criado de `requirements.txt`):
mapa 23, ui_smoke 9, integração 15, db_service 23, db_migracoes 18, verificar_ambiente 14, auditar_repositorio 20, diagnostico_banco 9.
Auditoria do branch: 0 BLOQUEIO, 0 REVISAR.

## Banco (evidência com dados reais, sem expor conteúdo)

O `configurar_banco_dados` novo e o original foram executados em **cópias** do `clinica.db` do usuário:
esquema (DDL) e conteúdo (hash por tabela) idênticos nas 7 tabelas; `schema_migrations` = `(1, 'adotada-legado')`;
backup `pre-migracao-v1` criado. Contagens preservadas (3 pacientes, 17 consultas, 72 exames, 425 regras, 41+35 exames/resultados).

## Segurança

- Dados de pacientes do zip (`clinica.db`, backups do banco e `arquivos_pacientes/`) **não** entraram em nenhum commit.
- O `.gitignore` anterior **não protegia** esses arquivos; agora protege.

## Pendências

Abrir a interface real e um executável de teste; Windows; avisos de pasta de rede/nuvem na interface; ADR-0005 (banco no executável).
