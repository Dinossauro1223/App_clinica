@echo off
setlocal EnableExtensions
set "RAIZ=%~dp0"

if /I "%~1"=="--worker" goto WORKER

set "REMOTE_SHA="
set "ROOT=%RAIZ%"
:LER_ARGS
if "%~1"=="" goto CONFIRMAR
if /I "%~1"=="--remote-sha" (
    set "REMOTE_SHA=%~2"
    shift
    shift
    goto LER_ARGS
)
if /I "%~1"=="--root" (
    set "ROOT=%~2"
    shift
    shift
    goto LER_ARGS
)
shift
goto LER_ARGS

:CONFIRMAR
if not defined REMOTE_SHA (
    echo SHA remoto ausente.
    exit /b 1
)
choice /C SN /N /M "Uma nova versao do NutriLab foi encontrada. Deseja atualizar agora? [S/N] "
if errorlevel 2 exit /b 0

set "TMP=%TEMP%\NutriLab-Updater-%RANDOM%-%RANDOM%"
mkdir "%TMP%" >nul 2>&1
copy /Y "%~f0" "%TMP%\Atualizar_NutriLab.bat" >nul
copy /Y "%RAIZ%tools\atualizar_nutrilab.ps1" "%TMP%\atualizar_nutrilab.ps1" >nul
if not exist "%TMP%\atualizar_nutrilab.ps1" (
    echo ERRO: script do atualizador ausente.
    exit /b 1
)

start "" /wait "%TMP%\Atualizar_NutriLab.bat" --worker --remote-sha "%REMOTE_SHA%" --root "%ROOT%"
set "CODIGO=%ERRORLEVEL%"
rmdir /s /q "%TMP%" >nul 2>&1
exit /b %CODIGO%

:WORKER
set "REMOTE_SHA="
set "ROOT=%~dp0"
:WORKER_ARGS
if "%~2"=="" goto WORKER_RUN
if /I "%~2"=="--remote-sha" (
    set "REMOTE_SHA=%~3"
    shift
    shift
    goto WORKER_ARGS
)
if /I "%~2"=="--root" (
    set "ROOT=%~3"
    shift
    shift
    goto WORKER_ARGS
)
shift
goto WORKER_ARGS

:WORKER_RUN
if not defined REMOTE_SHA (
    echo SHA remoto ausente.
    exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0atualizar_nutrilab.ps1" -Root "%ROOT%" -RemoteSha "%REMOTE_SHA%"
exit /b %ERRORLEVEL%
