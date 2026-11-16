@echo off
setlocal
chcp 65001 >nul
rem NutriLab - abre o programa. Pode ficar em qualquer pasta: ele sempre usa a pasta onde este arquivo esta.
cd /d "%~dp0"
title NutriLab

set "PY="
python --version >nul 2>nul
if not errorlevel 1 set "PY=python"
if not defined PY (
    py -3 --version >nul 2>nul
    if not errorlevel 1 set "PY=py -3"
)
if not defined PY goto sem_python

rem Confere as bibliotecas; se faltar alguma, instala (so na primeira vez).
%PY% -c "import customtkinter, fpdf, PIL, openpyxl, matplotlib, tzdata" >nul 2>nul
if not errorlevel 1 goto abrir

echo Instalando as bibliotecas necessarias. Isso so acontece na primeira vez...
%PY% -m pip install -r requirements.txt
if not errorlevel 1 goto abrir
echo.
echo Nao foi possivel instalar as versoes fixadas. Tentando as versoes mais recentes...
%PY% -m pip install customtkinter fpdf2 pillow openpyxl matplotlib tzdata
if errorlevel 1 goto erro_pip

:abrir
%PY% main.py
if errorlevel 1 goto erro_app
exit /b 0

:sem_python
echo.
echo Python nao foi encontrado neste computador.
echo Instale o Python 3.12 em https://www.python.org/downloads/ e marque "Add python.exe to PATH".
echo.
pause
exit /b 1

:erro_pip
echo.
echo Falha ao instalar as bibliotecas. Verifique a conexao com a internet e tente novamente.
echo.
pause
exit /b 1

:erro_app
echo.
echo O programa foi encerrado com erro. Copie a mensagem acima e envie para o suporte.
echo.
pause
exit /b 1
