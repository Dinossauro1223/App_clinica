@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title NutriLab - inicializador e compilador

set "RAIZ=%~dp0"
set "SAIDA=%~dp0Executavel do programa"
set "EXE=%SAIDA%\NutriLab.exe"
set "APK=%RAIZ%mobile\apk\saida\NutriLab-Mobile.apk"
set "DISTDIR=%RAIZ%Distribuicao"
set "ZIP=%DISTDIR%\NutriLab-Desktop.zip"
set "COMPARTILHAR=%SAIDA%\_internal\compartilhamento"
set "LOGDIR=%~dp0logs"
set "LOG=%LOGDIR%\compilacao_local.log"
set "PY_CMD="

rem Atualizacao automatica ocorre dentro do executavel por runtime hook.
rem Este launcher e usado para primeira instalacao, recompilacao e pos-atualizacao.
if /I "%~1"=="/apos-atualizacao" goto COMPILAR
if /I "%~1"=="/recompilar" goto COMPILAR
if /I "%~1"=="/recompilar-sem-abrir" goto COMPILAR
if defined NUTRILAB_SKIP_UPDATE goto VERIFICAR_EXE
if exist "%EXE%" goto VERIFICAR_EXE

:COMPILAR
echo.
echo ============================================================
echo NutriLab - preparacao e compilacao
echo ============================================================
echo Pasta do programa: "%SAIDA%"
echo Nenhum ambiente virtual sera criado.
echo.

if not exist "app_clinica.spec" goto ERRO_FONTE
if not exist "requirements-build.txt" goto ERRO_FONTE
if not exist "tools\gerar_banco_modelo.py" goto ERRO_FONTE
if not exist "assets\identidade\renderizados\folhas.json" goto ERRO_IDENTIDADE

call :LOCALIZAR_PYTHON
if not defined PY_CMD call :INSTALAR_PYTHON
if not defined PY_CMD goto ERRO_PYTHON

if not exist "%LOGDIR%" mkdir "%LOGDIR%"
echo ============================================================ > "%LOG%"
echo Compilacao local do NutriLab - %DATE% %TIME% >> "%LOG%"
echo Diretorio: %CD% >> "%LOG%"
echo ============================================================ >> "%LOG%"

echo [1/8] Verificando/instalando dependencias...
call %PY_CMD% -m pip --version >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_PIP
call %PY_CMD% -m pip install -r requirements-build.txt >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_DEPENDENCIAS

echo.
echo [2/8] Executando testes prioritarios e contrato de distribuicao...
call %PY_CMD% -m unittest discover -s tests -p "test_svg_pipeline.py" -v >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_TESTES
call %PY_CMD% -m unittest discover -s tests -p "test_launcher_bootstrap.py" -v >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_TESTES

echo.
echo [3/8] Gerando banco inicial limpo...
call %PY_CMD% tools\gerar_banco_modelo.py --sobrescrever >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_BANCO
if not exist "modelo_banco\clinica.db" goto ERRO_BANCO_AUSENTE

echo.
echo [4/8] Compilando e validando o aplicativo Android...
if not exist "%RAIZ%mobile\apk\Gerar_APK.bat" goto ERRO_APK_FONTE
call "%RAIZ%mobile\apk\Gerar_APK.bat" /integrado
if errorlevel 1 goto ERRO_APK
if not exist "%APK%" goto ERRO_APK_AUSENTE
for %%F in ("%APK%") do if %%~zF LSS 10000 goto ERRO_APK_INVALIDO

echo.
echo [5/8] Compilando NutriLab.exe...
if exist "dist" rmdir /s /q "dist"
call %PY_CMD% -m PyInstaller --clean --noconfirm app_clinica.spec >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_COMPILACAO
if not exist "dist\NutriLab\NutriLab.exe" goto ERRO_EXE_AUSENTE
if not exist "dist\NutriLab\_internal\python312.dll" goto ERRO_DLL_AUSENTE

echo.
echo [6/8] Instalando o pacote em "Executavel do programa"...
if exist "%SAIDA%" rmdir /s /q "%SAIDA%"
move /Y "dist\NutriLab" "%SAIDA%" >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_SAIDA
if not exist "%EXE%" goto ERRO_SAIDA
if not exist "%EXE%\..\_internal\python312.dll" goto ERRO_DLL_AUSENTE

echo.
echo [7/8] Incorporando o APK ao servidor mobile empacotado...
if not exist "%SAIDA%\_internal\mobile" goto ERRO_APK_DESTINO
if not exist "%SAIDA%\_internal\mobile\apk\saida" mkdir "%SAIDA%\_internal\mobile\apk\saida"
copy /y "%APK%" "%SAIDA%\_internal\mobile\apk\saida\NutriLab-Mobile.apk" >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_APK_COPIA
if not exist "%SAIDA%\_internal\mobile\apk\saida\NutriLab-Mobile.apk" goto ERRO_APK_COPIA

echo.
echo [8/8] Preparando arquivos para compartilhamento...
if not exist "%DISTDIR%" mkdir "%DISTDIR%"
copy /y "%APK%" "%DISTDIR%\NutriLab-Mobile.apk" >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_PACOTE
if exist "%ZIP%" del /q "%ZIP%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Compress-Archive -Path (Join-Path $env:SAIDA '*') -DestinationPath $env:ZIP -CompressionLevel Optimal -Force" >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_PACOTE
if not exist "%ZIP%" goto ERRO_PACOTE
if not exist "%COMPARTILHAR%" mkdir "%COMPARTILHAR%"
copy /y "%ZIP%" "%COMPARTILHAR%\NutriLab-Desktop.zip" >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_PACOTE
copy /y "%APK%" "%COMPARTILHAR%\NutriLab-Mobile.apk" >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_PACOTE
powershell -NoProfile -ExecutionPolicy Bypass -Command "$a=(Get-FileHash -LiteralPath $env:APK -Algorithm SHA256).Hash; $d=(Get-FileHash -LiteralPath $env:ZIP -Algorithm SHA256).Hash; @('NutriLab Mobile APK SHA-256: '+$a,'NutriLab Desktop ZIP SHA-256: '+$d) | Set-Content -LiteralPath (Join-Path $env:DISTDIR 'manifesto-sha256.txt') -Encoding UTF8" >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_PACOTE
copy /y "%DISTDIR%\manifesto-sha256.txt" "%COMPARTILHAR%\manifesto-sha256.txt" >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_PACOTE

call :REGISTRAR_VERSAO
echo Compilacao conjunta concluida.
echo Executavel: "%EXE%"
echo APK: "%COMPARTILHAR%\NutriLab-Mobile.apk"
echo Pacote desktop: "%COMPARTILHAR%\NutriLab-Desktop.zip"
echo Distribuicao externa: "%DISTDIR%"
echo Registro: "%LOG%"
goto INICIAR

:VERIFICAR_EXE
if exist "%EXE%" goto INICIAR
goto COMPILAR

:LOCALIZAR_PYTHON
where py >nul 2>&1
if not errorlevel 1 (
    py -3.12 --version >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=py -3.12"
        exit /b 0
    )
    py -3 --version >nul 2>&1
    if not errorlevel 1 (
        py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,12) and sys.version_info < (3,15) else 1)" >nul 2>&1
        if not errorlevel 1 (
            set "PY_CMD=py -3"
            exit /b 0
        )
    )
)
where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,12) and sys.version_info < (3,15) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)
exit /b 0

:INSTALAR_PYTHON
echo.
echo Python compativel nao encontrado. Baixando Python 3.12.10 oficial...
echo A versao 3.12.10 e a ultima 3.12 com instalador Windows oficial.
set "PYTHON_VERSION=3.12.10"
set "PYTHON_INSTALLER=%TEMP%\python-%PYTHON_VERSION%-amd64.exe"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-amd64.exe"
set "PYTHON_SHA256=67B5635E80EA51072B87941312D00EC8927C4DB9BA18938F7AD2D27B328B95FB"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest -UseBasicParsing -Uri '%PYTHON_URL%' -OutFile '%PYTHON_INSTALLER%'" >> "%LOG%" 2>&1
if errorlevel 1 goto ERRO_PYTHON_DOWNLOAD
for /f "tokens=1" %%H in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-FileHash -LiteralPath '%PYTHON_INSTALLER%' -Algorithm SHA256).Hash"') do set "PYTHON_HASH=%%H"
if /I not "%PYTHON_HASH%"=="%PYTHON_SHA256%" goto ERRO_PYTHON_HASH
echo Instalando Python 3.12.10 somente para o usuario atual...
start /wait "" "%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1
if errorlevel 1 goto ERRO_PYTHON_INSTALL
del /q "%PYTHON_INSTALLER%" >nul 2>&1
call :LOCALIZAR_PYTHON
exit /b 0

:REGISTRAR_VERSAO
set "SHA="
where git >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%S in ('git -C "%RAIZ%" rev-parse HEAD 2^>nul') do set "SHA=%%S"
)
if not defined SHA (
    for /f "delims=" %%S in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "try { (Invoke-RestMethod -UseBasicParsing -TimeoutSec 8 -Uri ''https://api.github.com/repos/Dinossauro1223/App_clinica/commits/main'').sha } catch {}" 2^>nul') do set "SHA=%%S"
)
if defined SHA echo %SHA%>"%RAIZ%.nutrilab-version"
exit /b 0

:INICIAR
if not exist "%EXE%" goto ERRO_EXE_AUSENTE
if /I "%~1"=="/recompilar-sem-abrir" exit /b 0
echo.
echo Iniciando NutriLab...
start "" "%EXE%"
exit /b 0

:ERRO_FONTE
echo ERRO: arquivos de compilacao ausentes. Use o pacote completo do repositorio.
pause
exit /b 1
:ERRO_PIP
echo ERRO: pip nao esta disponivel no Python encontrado.
pause
exit /b 1
:ERRO_PYTHON
echo ERRO: nao foi possivel instalar/encontrar Python compativel.
pause
exit /b 1
:ERRO_PYTHON_DOWNLOAD
echo ERRO: falha ao baixar Python de python.org.
pause
exit /b 1
:ERRO_PYTHON_HASH
echo ERRO: o instalador Python baixado nao passou na verificacao SHA-256.
del /q "%PYTHON_INSTALLER%" >nul 2>&1
pause
exit /b 1
:ERRO_PYTHON_INSTALL
echo ERRO: a instalacao do Python falhou.
pause
exit /b 1
:ERRO_DEPENDENCIAS
echo ERRO ao instalar/verificar dependencias. Consulte "%LOG%".
type "%LOG%"
pause
exit /b 1
:ERRO_IDENTIDADE
echo ERRO: identidade visual gerada ausente.
pause
exit /b 1
:ERRO_TESTES
echo ERRO: testes prioritarios falharam. A compilacao foi interrompida.
type "%LOG%"
pause
exit /b 1
:ERRO_BANCO
echo ERRO ao gerar banco-modelo.
type "%LOG%"
pause
exit /b 1
:ERRO_BANCO_AUSENTE
echo ERRO: modelo_banco\clinica.db nao foi criado.
pause
exit /b 1
:ERRO_COMPILACAO
echo ERRO durante a compilacao pelo PyInstaller.
type "%LOG%"
pause
exit /b 1
:ERRO_EXE_AUSENTE
echo ERRO: NutriLab.exe nao foi encontrado.
pause
exit /b 1
:ERRO_DLL_AUSENTE
echo ERRO: pacote incompleto; python312.dll nao foi encontrado.
pause
exit /b 1
:ERRO_SAIDA
echo ERRO: nao foi possivel gerar a pasta "Executavel do programa".
pause
exit /b 1
:ERRO_APK_FONTE
echo ERRO: mobile\apk\Gerar_APK.bat nao foi encontrado.
pause
exit /b 1
:ERRO_APK
echo ERRO: a compilacao do APK falhou. Consulte mobile\apk\gerar_apk_log.txt.
pause
exit /b 1
:ERRO_APK_AUSENTE
echo ERRO: o gerador terminou sem criar o APK esperado.
pause
exit /b 1
:ERRO_APK_INVALIDO
echo ERRO: o APK gerado esta vazio ou pequeno demais para ser valido.
pause
exit /b 1
:ERRO_APK_DESTINO
echo ERRO: a pasta mobile nao foi incluida no pacote PyInstaller.
pause
exit /b 1
:ERRO_APK_COPIA
echo ERRO: nao foi possivel incorporar o APK ao servidor mobile empacotado.
pause
exit /b 1
:ERRO_PACOTE
echo ERRO: nao foi possivel preparar os arquivos de distribuicao/compartilhamento.
type "%LOG%"
pause
exit /b 1
