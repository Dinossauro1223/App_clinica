# ADR-0002 — Ambiente reproduzível: Python de referência e dependências fixadas

- **Estado:** Aceita, com validação pendente no Windows e contra o código do aplicativo.
- **Data:** 10/11/2026 (America/Recife)
- **Fase do ROADMAP:** 0 — atividade 2 (ambiente reproduzível)
- **Branch:** `feat/fase-0-fundacao-seguranca-banco`

## Contexto

- O pacote analisado não tinha `requirements.txt`; a instalação era `pip install customtkinter fpdf2 pillow openpyxl
  matplotlib`, sem versões (README, seção 9). Cada máquina podia acabar com versões diferentes.
- O ROADMAP exige validação no Windows. A sessão que produziu esta ADR dispôs apenas de Linux x86_64 com Python 3.12.3,
  **sem acesso ao código do aplicativo** e sem `tkinter` (a interface gráfica não foi aberta).

## Decisão

1. **Python de referência: 3.12.x (64 bits).** Mínimo exigido pelos pacotes fixados: 3.10. `tools/verificar_ambiente.py`
   falha abaixo de 3.10 e avisa fora de 3.12.
2. `requirements.txt` com versões exatas (`==`) das seis dependências diretas; `requirements.lock.txt` com o congelamento
   completo (diretas e transitivas) gerado num venv limpo; `requirements-build.txt` acrescenta o PyInstaller.
3. **Critério de escolha das versões:** (a) instalam juntas sem conflito (`pip check`) em Python 3.12; (b) somente
   versões publicadas há mais de 14 dias (reduz o risco de versão recém-publicada com defeito ou comprometida);
   (c) majors novos sem teste do aplicativo não entram (customtkinter permanece na linha 5.x; Pillow na 12.x).
4. **`fpdf2`, nunca `fpdf`/`pyfpdf`:** todos fornecem o módulo `fpdf` e se sobrepõem; o verificador falha se encontrar a
   combinação (ou só o pacote legado).
5. **`tzdata`** entra nas dependências: o Windows não traz o banco de fusos IANA e `zoneinfo` precisa dele para
   `America/Recife` (nomes de backup, janelas de refeição).
6. **CI** (`.github/workflows/ci.yml`): Windows e Ubuntu, Python 3.12; instala `requirements.txt`, roda
   `verificar_ambiente --estrito`, `auditar_repositorio --ci` e `unittest discover`. Actions por tag de major
   (`actions/checkout@v6`, `actions/setup-python@v6`; ambas existem segundo as notas de lançamento consultadas).

## Versões fixadas (consulta ao PyPI em 09/11/2026)

| Pacote | Fixada | Publicada em | Exige Python | Mais nova na consulta | Por que não a mais nova |
|---|---|---|---|---|---|
| customtkinter | 5.2.2 | 2024-01-10 | ≥ 3.7 | 6.0.0 (2026-06-24) | major novo; sem teste de interface real |
| fpdf2 | 2.8.9 | 2026-09-29 | ≥ 3.10 | 2.9.0 (2026-10-29) | tinha 11 dias (regra de 14) |
| pillow | 12.3.0 | 2026-07-01 | ≥ 3.10 | 13.0.0 (2026-10-16) | major novo; app não validado |
| openpyxl | 3.1.5 | 2024-06-28 | ≥ 3.8 | 3.1.5 | — |
| matplotlib | 3.10.9 | 2026-04-24 | ≥ 3.10 | 3.11.2 (2026-09-11) | 3.11 exige Python ≥ 3.11 |
| tzdata | 2026.5 | 2026-10-03 | — | 2026.6 (2026-10-28) | tinha 12 dias |
| pyinstaller (build) | 6.22.3 | 2026-09-12 | < 3.16, ≥ 3.8 | 6.22.3 | — |

## Alternativas consideradas

- Faixas de versão (`~=`, `>=`): rejeitadas; o objetivo é reprodutibilidade.
- Instalar sempre a versão mais recente: rejeitada; majors novos podem remover APIs usadas pela interface ou pelos PDFs.
- `pip-tools`, `uv` ou Poetry: não adotados para manter o fluxo simples; reavaliar quando o projeto crescer.

## Consequências

- Quem já tem um ambiente funcionando com versões diferentes verá avisos do verificador (erro com `--estrito`). Nesse
  caso: comparar, testar o aplicativo e atualizar `requirements.txt` conscientemente — não "silenciar" o aviso.
- O lock foi gerado no Linux; antes de usá-lo como referência no Windows, regenerá-lo lá.

## Como atualizar versões

1. Criar um venv novo e instalar a nova versão.
2. Rodar `python -m unittest discover -s tests -v`, `python -m pip check` e abrir o aplicativo (inclui PDF e gráficos).
3. Atualizar `requirements.txt`, regenerar o lock (mantendo o cabeçalho), atualizar a tabela acima e registrar o motivo.

## Pendências

- Validar no Windows: `python tools\verificar_ambiente.py` e a suíte de testes.
- Confirmar qual versão de customtkinter está em uso real (se for a 6.x, ajustar o pin e testar a interface).
- Fixar as actions por SHA de commit (Fase 9).
- Conferir se `tzdata` é incluído no executável PyInstaller.

## Referências (consultadas em 09–10/11/2026)

- PyPI (API JSON `https://pypi.org/pypi/<pacote>/json`): datas de publicação e `Requires-Python`.
- `actions/checkout` v6.0.0/v6.0.1 e `actions/setup-python` v6.0.0 (Node 24; exigem runner ≥ 2.327.1): notas de lançamento
  em https://github.com/actions/checkout/releases e https://github.com/actions/setup-python/releases.
