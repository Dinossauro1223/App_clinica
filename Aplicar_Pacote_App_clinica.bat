@echo off
rem NutriLab - aplica o pacote (.bundle) ao repositorio App_clinica e publica o(s) branch(es) novo(s).
rem Mantenha este arquivo, o aplicar_pacote.py e o .bundle na MESMA pasta (auditar_repositorio.py e opcional).
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo NutriLab - aplicando o pacote ao repositorio App_clinica...
echo (Se o Git pedir login do GitHub, entre normalmente. O que falhar NAO e publicado.)
echo.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 aplicar_pacote.py %*
) else (
    python aplicar_pacote.py %*
)
echo.
echo Terminou. O registro completo ficou em aplicar_pacote_log.txt (nesta pasta).
pause
