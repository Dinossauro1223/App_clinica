@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

title NutriLab - Gerar e abrir

echo ============================================================
echo NutriLab - Gerar e abrir o programa
echo ============================================================
echo.

set "PYTHON=python"
where python >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao foi encontrado no PATH.
    echo Instale Python 3.12 e tente novamente.
    pause
    exit /b 1
)

if not exist "venv\Scripts\python.exe" (
    echo [1/5] Criando ambiente virtual...
    "%PYTHON%" -m venv venv
    if errorlevel 1 goto :erro
)

echo [2/5] Atualizando ferramentas de build...
"venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :erro
"venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 goto :erro

echo [3/5] Gerando o banco-modelo sanitizado...
"venv\Scripts\python.exe" tools\gerar_banco_modelo.py
if errorlevel 1 goto :erro

if not exist "modelo_banco\clinica.db" (
    echo ERRO: o banco-modelo nao foi criado.
    goto :erro
)

echo [4/5] Gerando o executavel com PyInstaller...
"venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm app_clinica.spec
if errorlevel 1 goto :erro

if not exist "dist\app_clinica\app_clinica.exe" (
    echo ERRO: o executavel nao foi encontrado em dist\app_clinica\app_clinica.exe.
    goto :erro
)

echo [5/5] Iniciando o servidor do NutriLab...
if exist "mobile\iniciar_servidor.bat" (
    start "NutriLab - Servidor" /min cmd /c call "%CD%\mobile\iniciar_servidor.bat"
) else (
    echo AVISO: mobile\iniciar_servidor.bat nao foi encontrado.
)

echo.
echo Abrindo o NutriLab...
start "" "%CD%\dist\app_clinica\app_clinica.exe"

echo.
echo Programa iniciado.
exit /b 0

:erro
echo.
echo ============================================================
echo ERRO: a geracao do NutriLab nao foi concluida.
echo ============================================================
echo Verifique a mensagem acima.
pause
exit /b 1
