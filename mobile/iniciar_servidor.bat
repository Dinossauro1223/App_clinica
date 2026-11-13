@echo off
rem NutriLab Mobile - inicia o servidor da rede local (12/11/2026). Feche a janela para desligar.
chcp 65001 >nul
cd /d "%~dp0.."
title NutriLab Mobile - servidor
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 mobile\servidor.py %*
) else (
    python mobile\servidor.py %*
)
pause
