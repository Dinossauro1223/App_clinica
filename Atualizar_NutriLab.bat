@echo off
setlocal EnableExtensions
set "RAIZ=%~dp0"

if /I "%~1"=="--remote-sha" goto INICIAR
if /I "%~1"=="--worker" goto INICIAR

echo O atualizador precisa ser iniciado pelo NutriLab.
exit /b 1

:INICIAR
set "REMOTE_SHA=%~2"
set "ROOT=%~dp0"
if /I "%~1"=="--remote-sha" (
    set "ROOT=%~dp0"
)
if not defined REMOTE_SHA (
    echo SHA remoto ausente.
    exit /b 1
)

set "TMP=%TEMP%\NutriLab-Updater-%RANDOM%-%RANDOM%"
mkdir "%TMP%" >nul 2>&1
copy /Y "%~f0" "%TMP%\Atualizar_NutriLab.bat" >nul
copy /Y "%RAIZ%tools\atualizar_nutrilab.ps1" "%TMP%\atualizar_nutrilab.ps1" >nul
if not exist "%TMP%\atualizar_nutrilab.ps1" (
    echo ERRO: script do atualizador ausente.
    exit /b 1
)

start "" /wait powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TMP%\atualizar_nutrilab.ps1" -Root "%ROOT%" -RemoteSha "%REMOTE_SHA%"
set "CODIGO=%ERRORLEVEL%"
rmdir /s /q "%TMP%" >nul 2>&1
exit /b %CODIGO%
