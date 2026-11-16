@echo off
setlocal EnableDelayedExpansion
rem NutriLab - publica as alteracoes desta pasta em um branch NOVO no GitHub.
rem Nunca altera a main, nunca usa --force e nunca envia banco, planilhas, PDFs ou fichas de pacientes.
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo === NutriLab: publicar alteracoes em um novo branch ===
echo.
where git >nul 2>nul
if errorlevel 1 goto sem_git
git rev-parse --is-inside-work-tree >nul 2>nul
if errorlevel 1 goto sem_repo

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd-HHmm"') do set "STAMP=%%i"
set "RAMO=feat/atualizacao-%STAMP%"
set "NOME="
set /p "NOME=Nome do branch [Enter = %RAMO%]: "
if not "%NOME%"=="" set "RAMO=%NOME%"
set "MSG=Atualizacao NutriLab %STAMP%"
set "TXT="
set /p "TXT=Mensagem do commit [Enter = %MSG%]: "
if not "%TXT%"=="" set "MSG=%TXT%"

git show-ref --verify --quiet "refs/heads/%RAMO%"
if not errorlevel 1 goto ramo_existe
git fetch origin --quiet
if errorlevel 1 goto erro_rede

for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set "ORIGEM=%%b"
git checkout -b "%RAMO%"
if errorlevel 1 goto erro
git -c core.safecrlf=false add -A

rem --- protecao: nada de banco, backups, planilhas, PDFs, fichas de pacientes ou preferencias locais
git diff --cached --name-only > "%TEMP%\nutrilab_staged.txt"
findstr /i /r /c:"\.db$" /c:"\.db-" /c:"\.sqlite" /c:"\.xlsx$" /c:"\.xls$" /c:"\.pdf$" /c:"backups/" /c:"arquivos_pacientes/" /c:"preferencias_ui\.json" "%TEMP%\nutrilab_staged.txt" > "%TEMP%\nutrilab_proibidos.txt"
if not errorlevel 1 goto proibidos

git diff --cached --quiet
if not errorlevel 1 goto nada

where python >nul 2>nul
if errorlevel 1 goto publicar
echo Rodando os testes (pode levar cerca de um minuto)...
python -m unittest discover -s tests > "%TEMP%\nutrilab_testes.txt" 2>&1
if not errorlevel 1 goto publicar
echo.
findstr /b /c:"ERROR:" /c:"FAIL:" /c:"Ran " /c:"FAILED" "%TEMP%\nutrilab_testes.txt"
echo.
echo O registro completo dos testes ficou em: %TEMP%\nutrilab_testes.txt
echo.
choice /c SN /m "Os testes falharam. Publicar mesmo assim"
if errorlevel 2 goto desfazer

:publicar
git -c core.safecrlf=false commit -q -m "%MSG%"
if errorlevel 1 goto desfazer
git push -u origin "%RAMO%"
if errorlevel 1 goto erro_push
for /f "delims=" %%u in ('git remote get-url origin') do set "URL=%%u"
set "URL=!URL:.git=!"
echo.
echo Pronto! Branch publicado: %RAMO%
echo Abra o Pull Request para revisar e mesclar: !URL!/pull/new/%RAMO%
start "" "!URL!/pull/new/%RAMO%"
goto fim

:proibidos
echo.
echo ATENCAO: estes arquivos NAO podem ir para o GitHub. Nada foi publicado:
type "%TEMP%\nutrilab_proibidos.txt"
echo Tire-os da pasta (ou do .gitignore) e rode de novo.
goto desfazer

:nada
echo Nenhuma alteracao para publicar.

:desfazer
git reset -q
git checkout -q "%ORIGEM%"
git branch -D "%RAMO%" >nul 2>nul
goto fim

:ramo_existe
echo O branch %RAMO% ja existe. Rode de novo e escolha outro nome.
goto fim

:erro_rede
echo Sem conexao com o GitHub: o git fetch falhou. Nada foi alterado.
goto fim

:erro_push
echo O envio falhou. O commit continua salvo no branch local %RAMO%.
echo Quando a conexao voltar, rode: git push -u origin %RAMO%
goto fim

:erro
echo Nao foi possivel criar o branch. Nada foi publicado.
goto fim

:sem_git
echo Git nao encontrado. Instale em https://git-scm.com/download/win e rode de novo.
goto fim

:sem_repo
echo Esta pasta nao e um repositorio Git. Coloque este arquivo na pasta do projeto App_clinica.

:fim
echo.
pause
endlocal
