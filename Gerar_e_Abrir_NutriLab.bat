@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title NutriLab

set "EXE="
if exist "%~dp0NutriLab.exe" set "EXE=%~dp0NutriLab.exe"
if not defined EXE if exist "%~dp0dist\NutriLab\NutriLab.exe" set "EXE=%~dp0dist\NutriLab\NutriLab.exe"
if not defined EXE if exist "%~dp0dist\app_clinica\app_clinica.exe" set "EXE=%~dp0dist\app_clinica\app_clinica.exe"

if not defined EXE (
    echo ============================================================
    echo NutriLab - executavel nao encontrado
    echo ============================================================
    echo.
    echo Este inicializador nao cria mais ambiente virtual nem compila
    echo o programa localmente.
    echo.
    echo Baixe o pacote Windows mais recente na secao Releases do GitHub
    echo e extraia todos os arquivos mantendo a estrutura das pastas.
    echo.
    echo Para compilar a partir do codigo-fonte, use o workflow Build Windows
    echo do repositorio ou execute o processo de desenvolvimento documentado.
    pause
    exit /b 1
)

echo Iniciando NutriLab...
start "" "%EXE%"
exit /b 0
