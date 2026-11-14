# Guia — gerar o executável sem o banco real

Atualizado em 13/11/2026 (ADR-0005). Comandos no Prompt de Comando; no PowerShell, ative o ambiente com `.venv\Scripts\Activate.ps1`.

> **Estado de validação:** escrito e conferido em Linux. O build PyInstaller e a execução do `.exe` **ainda não foram testados no Windows**.

## 1. Gerar o banco-modelo (uma vez por build)

Na raiz do projeto, com o seu `clinica.db` de desenvolvimento ao lado do `main.py`:

```bat
python tools\gerar_banco_modelo.py
```

Resultado esperado: `modelo_banco\clinica.db` com o catálogo (por exemplo, `Exames_Catalogo` e `Regras_Complementares` com linhas) e
**todas as demais tabelas com 0 linhas**. A pasta `modelo_banco\` é ignorada pelo Git. Para refazer: `--sobrescrever`.

## 2. Gerar o executável

```bat
python -m pip install -r requirements-build.txt
pyinstaller app_clinica.spec
```

Se o modelo não existir, o `.spec` para com a mensagem *"Banco-modelo ausente. Rode primeiro: python tools\gerar_banco_modelo.py"*.

## 3. Conferir antes de distribuir

```bat
python tools\diagnostico_banco.py dist
```

No `dist`, o `clinica.db` dentro de `_internal` deve ser o modelo: **0 linhas** em `Pacientes`, `Consultas`, `Resultados_Exames` e `Arquivos_Paciente`.
Se aparecer qualquer paciente, **não distribua**.

## 4. Testar numa pasta separada

Copie a pasta `dist\app_clinica` para uma pasta de teste e abra o `.exe`. Na primeira execução o programa copia o modelo para
`clinica.db` **ao lado do `.exe`**; ali ficam os dados do usuário. Rode de novo o diagnóstico nessa pasta: deve mostrar o banco ao lado do `.exe`
(com o catálogo) e o modelo em `_internal`.

## Atenção

- **Não distribua** nenhuma pasta `dist\` gerada antes desta mudança: ela embute o seu `clinica.db` real.
- Se você já entregou um executável antigo a alguém, os registros do seu banco foram junto.
