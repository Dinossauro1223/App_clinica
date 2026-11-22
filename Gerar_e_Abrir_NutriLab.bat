@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title NutriLab - inicializador e compilador

set "EXE="
if exist "%~dp0NutriLab.exe" set "EXE=%~dp0NutriLab.exe"
if not defined EXE if exist "%~dp0dist\NutriLab\NutriLab.exe" set "EXE=%~dp0dist\NutriLab\NutriLab.exe"
if not defined EXE if exist "%~dp0dist\app_clinica\app_clinica.exe" set "EXE=%~dp0dist\app_clinica\app_clinica.exe"

rem Use /recompilar para ignorar um executavel existente e gerar uma nova versao.
if /I "%~1"=="/recompilar" goto COMPILAR
if defined EXE goto INICIAR

:COMPILAR

echo.
echo ============================================================
echo NutriLab - executavel nao encontrado
echo ============================================================
echo O inicializador vai preparar e compilar o programa agora.
echo Nenhum ambiente virtual sera criado.
echo.

if not exist "app_clinica.spec" goto ERRO_FONTE
if not exist "requirements-build.txt" goto ERRO_FONTE
if not exist "tools\gerar_banco_modelo.py" goto ERRO_FONTE

rem Prioriza Python 3.12, a versao usada nos testes e na compilacao do GitHub.
set "PY_CMD="
where py >nul 2>&1
if not errorlevel 1 (
    py -3.12 --version >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py -3.12"
)
if not defined PY_CMD (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 --version >nul 2>&1
        if not errorlevel 1 (
            py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,12) and sys.version_info < (3,15) else 1)" >nul 2>&1
            if not errorlevel 1 set "PY_CMD=py -3"
        )
    )
)
if not defined PY_CMD (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,12) and sys.version_info < (3,15) else 1)" >nul 2>&1
        if not errorlevel 1 set "PY_CMD=python"
    )
)

if not defined PY_CMD goto ERRO_PYTHON

if not exist "logs" mkdir "logs"
set "LOG=%~dp0logs\compilacao_local.log"
echo ============================================================ > "%LOG%"
echo Compilacao local do NutriLab - %DATE% %TIME% >> "%LOG%"
echo Diretorio: %CD% >> "%LOG%"
echo. >> "%LOG%"

echo [1/4] Verificando e instalando dependencias (se necessario)...
echo [1/4] Dependencias >> "%LOG%"
call %PY_CMD% -m pip install -r requirements-build.txt >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_DEPENDENCIAS

echo.
echo [2/4] Gerando banco inicial do proprio codigo...
echo [2/4] Banco inicial >> "%LOG%"
call %PY_CMD% tools\gerar_banco_modelo.py --sobrescrever >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_BANCO
if not exist "modelo_banco\clinica.db" goto ERRO_BANCO_AUSENTE

echo.
echo [3/4] Compilando NutriLab.exe...
echo [3/4] PyInstaller >> "%LOG%"
call %PY_CMD% -m PyInstaller --clean --noconfirm app_clinica.spec >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_COMPILACAO

if not exist "dist\NutriLab\NutriLab.exe" goto ERRO_EXE_AUSENTE
set "EXE=%~dp0dist\NutriLab\NutriLab.exe"

echo.
echo [4/4] Compilacao concluida.
echo Executavel: %EXE%
echo Registro: %LOG%
goto INICIAR

:INICIAR
echo.
echo Iniciando NutriLab...
start "" "%EXE%"
exit /b 0

:ERRO_FONTE
echo ERRO: arquivos de compilacao ausentes. Baixe o repositorio completo, nao apenas este .bat.
pause
exit /b 1

:ERRO_PYTHON
echo ERRO: Python 3.12 ou 3.13/3.14 nao foi encontrado.
echo Instale Python 3.12 de 64 bits e marque "Add Python to PATH".
echo O programa nao exige que voce crie um ambiente virtual.
pause
exit /b 1

:ERRO_DEPENDENCIAS
echo ERRO ao instalar/verificar as dependencias.
echo Consulte o registro: "%LOG%"
type "%LOG%"
pause
exit /b 1

:ERRO_BANCO
echo ERRO ao gerar o banco inicial a partir das migracoes do NutriLab.
echo Nao e necessario possuir clinica.db previamente.
echo Consulte o registro: "%LOG%"
type "%LOG%"
pause
exit /b 1

:ERRO_BANCO_AUSENTE
echo ERRO: o gerador terminou, mas modelo_banco\clinica.db nao foi criado.
echo Consulte o registro: "%LOG%"
type "%LOG%"
pause
exit /b 1

:ERRO_COMPILACAO
echo ERRO durante a compilacao pelo PyInstaller.
echo Consulte o registro: "%LOG%"
type "%LOG%"
pause
exit /b 1

:ERRO_EXE_AUSENTE
echo ERRO: o PyInstaller terminou, mas dist\NutriLab\NutriLab.exe nao existe.
echo Consulte o registro: "%LOG%"
type "%LOG%"
pause
exit /b 1
