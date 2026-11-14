# ADR-0005 — Executável sem o banco real: banco-modelo sanitizado

- **Estado:** Aceita (modo local). Complementa as ADR-0001 e ADR-0004.
- **Data:** 13/11/2026 (America/Recife)
- **Fase do ROADMAP:** 0 — atividade 3 (banco único) e segurança de distribuição
- **Branch:** `feat/fase-0-banco-2-executavel-sem-banco-real` (depende de `feat/fase-0-fundacao-seguranca-banco`)

## Contexto (observado no código real)

1. O `app_clinica.spec` listava `('clinica.db', '.')` em `datas`: **cada build embutia o `clinica.db` do desenvolvedor** em `_internal/`,
   e na primeira execução o programa o copiava para a pasta do usuário (`get_writable_path`, hoje `caminho_do_banco()`).
   Esse banco tem pacientes, consultas, resultados e anexos (a cópia examinada tinha 3 pacientes, 17 consultas, 35 resultados e
   1 anexo; contagens apenas — nenhum conteúdo foi lido). Qualquer pasta `dist/` distribuída carregava esses registros.
2. O mesmo banco tem um **catálogo curado pela interface** (72 exames e 425 regras complementares), que não vem de arquivo. Tirar o
   banco embutido sem substituto reduziria a primeira execução a 15 exames e 1 regra (semente de `garantir_esquema_legado`).
3. `regras_exames_complementares.json` (57 KB) também é embutido, mas nenhum código Python o lê (a confirmar).

## Decisão

1. O executável embute um **banco-modelo sanitizado**: a estrutura completa (tabelas, índices, views, gatilhos) e as **linhas apenas das
   tabelas de catálogo** (`Exames_Catalogo`, `Regras_Complementares`). Pacientes, consultas, exames solicitados, resultados e anexos
   ficam **vazios**.
2. O modelo é **construído do zero** por `tools/gerar_banco_modelo.py` (nunca por cópia de bytes), portanto não carrega páginas livres nem
   resíduos de linhas apagadas. O gerador verifica integridade, que as tabelas fora do catálogo estão vazias e que as contagens do catálogo
   batem com a origem; imprime só contagens.
3. O arquivo fica em `modelo_banco/clinica.db`, **ignorado pelo Git** (ADR-0004): é gerado antes do build, não versionado.
4. O `.spec` embute `modelo_banco/clinica.db` como `clinica.db` e **falha cedo, com mensagem clara**, se o modelo não existir —
   falhar é melhor do que voltar a embutir um banco real por esquecimento.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Só remover o banco embutido | Perderia o catálogo curado (72 exames, 425 regras) na primeira execução. |
| Versionar o banco-modelo no Git | Binário; `*.db` é ignorado de propósito; e o risco de commitar um banco real por engano é exatamente o que se quer evitar. |
| Gerar o catálogo a partir de JSON na primeira execução | Exigiria código novo e uma exportação dos 72 exames/425 regras; pode ser uma evolução futura. |
| Manter como está | Distribui dados de pacientes a cada build. |

## Consequências

- O procedimento de build ganha um passo (`python tools\gerar_banco_modelo.py`), descrito em `docs/desenvolvimento/GUIA_EXECUTAVEL_SEM_BANCO_REAL.md`.
- Instalações novas começam com o catálogo curado e **sem pacientes**; instalações existentes não são afetadas pela mudança do `.spec`.
- **Builds antigos** (`dist/` feitos antes desta mudança) contêm o banco real: não devem ser distribuídos.

## Como verificar

```bat
python -m unittest tests.test_gerar_banco_modelo -v
python tools\gerar_banco_modelo.py
```

Evidências desta sessão (Linux, Python 3.12): 11 testes (estrutura idêntica; catálogo copiado; pacientes zerados; **nenhum dado nem resíduo de
paciente no arquivo gerado**; gatilho não dispara; IDs recomeçam em 1; recusa de sobrescrita/origem inválida; `.spec` sem o banco real).
Sobre uma **cópia do banco real**: 72 exames e 425 regras copiados, 0 linhas nas demais tabelas, integridade ok e **nenhum dos 3 nomes de
pacientes** presente no modelo (61 440 bytes). Não executado: o build PyInstaller real e o Windows.

## Pendências

1. Rodar o build real no Windows e abrir o executável em pasta de teste (GUIA, seção 4).
2. O `.spec` ainda aponta para `D:/app_clinica/venv/Lib/site-packages/customtkinter` (caminho fixo da máquina do desenvolvedor).
3. Revisão clínica do catálogo embutido por quem o curou; confirmar se `regras_exames_complementares.json` é usado.
