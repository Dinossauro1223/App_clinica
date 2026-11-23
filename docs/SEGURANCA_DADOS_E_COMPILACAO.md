# Distribuição pública, dados locais e compilação do NutriLab

## O que pode permanecer no GitHub

O repositório deve conter somente código-fonte, recursos visuais, dependências fixadas,
migrações, testes, documentação e catálogos clínicos genéricos revisados para publicação.
Os diretórios de catálogos usados pelo aplicativo — `exames_internos/`,
`condutas_internas/`, `prescricoes_internas/`, `sintomas_internos/` e
`condutas_alta/` — são recursos de referência do programa, não prontuários. Antes de
adicionar arquivos novos a esses diretórios, revise-os para garantir que não contenham
nomes, identificadores, contatos, datas ou narrativas de pacientes.

## O que nunca deve ser versionado

- `clinica.db`, bancos SQLite, arquivos WAL/SHM e diários de transação;
- backups do banco, cópias automáticas e diretórios `backups/`;
- `arquivos_pacientes/`, PDFs, exames, anexos e documentos exportados de pacientes;
- logs locais de execução/compilação, planilhas operacionais hospitalares e exportações;
- arquivos `.env`, tokens, senhas, certificados e chaves privadas.

O `.gitignore` cobre os padrões locais e `tools/auditar_repositorio.py` examina arquivos
rastreados, arquivos que seriam incluídos no próximo commit, padrões de exclusão e caminhos
sensíveis que já tenham aparecido no histórico Git. A auditoria não imprime conteúdo dos
arquivos. Não faça push se a auditoria apontar `BLOQUEIO`. Se um dado real já foi enviado
ao GitHub, removê-lo da árvore atual ou adicioná-lo ao `.gitignore` não apaga o histórico;
é necessário tratar a limpeza do histórico e a resposta a incidente antes de continuar.

## Como o executável é gerado sem dados de pacientes

O executável não usa nem empacota um `clinica.db` da máquina de desenvolvimento. O
arquivo `tools/gerar_banco_modelo.py` constrói `modelo_banco/clinica.db` a partir do
esquema, das migrações e da inicialização dos catálogos do aplicativo. Ele valida a
integridade SQLite e exige que as tabelas de pacientes, consultas, anexos e demais
registros clínicos estejam vazias. O SPEC empacota apenas esse banco-modelo sanitizado.

Os dados criados durante o uso ficam no banco local do usuário, ao lado do executável
(ou no diretório de dados configurado), e não devem ser enviados ao repositório.

## Compilar e abrir no Windows

1. Baixe o repositório completo (ZIP do GitHub ou clone).
2. Instale Python 3.12 de 64 bits com Tcl/Tk e adicione-o ao PATH.
3. Execute `Gerar_e_Abrir_NutriLab.bat`.
4. Para forçar uma nova compilação mesmo que já exista um executável, execute:
   `Gerar_e_Abrir_NutriLab.bat /recompilar`.

O BAT instala as dependências fixadas em `requirements-build.txt`, gera o banco-modelo
limpo e chama o PyInstaller com `app_clinica.spec`. O pacote esperado é
`dist/NutriLab/NutriLab.exe` com a pasta `_internal`.

O GitHub Actions executa a mesma auditoria de privacidade antes de compilar o pacote
Windows. A compilação local não substitui a homologação funcional e clínica do programa.
