@echo off
setlocal EnableExtensions
title NutriLab - gerar o APK do celular
cd /d "%~dp0"

rem ======================================================================
rem  NutriLab - Gerar_APK.bat  (criado em 12/11/2026, revisado em 14/11/2026)
rem  Gera o aplicativo Android que abre o NutriLab Mobile no celular.
rem  Primeira vez: baixa o JDK 17 e as ferramentas do Android, cerca de 600 MB
rem  e 10 a 20 minutos. Depois: cerca de 1 minuto.
rem  Saida: saida\NutriLab-Mobile.apk
rem
rem  14/11/2026: o aapt2 do Android nao abre pastas com acento no nome, como
rem  C:\Users\fulano nutricao. Por isso as ferramentas ficam num caminho curto
rem  sem acento e a compilacao acontece numa pasta de trabalho sem acento; o
rem  APK pronto volta para a pasta saida daqui.
rem ======================================================================

set "FONTE=%~dp0app"
set "SAIDA=%~dp0saida"
set "LOG=%~dp0gerar_apk_log.txt"
set "PASSO=iniciando"
for %%I in ("%LOCALAPPDATA%") do set "LOCAL_CURTO=%%~sI"
set "FERR=%LOCAL_CURTO%\NutriLabApk"
powershell -NoProfile -Command "if ('%FERR%' -cmatch '[^\x00-\x7F]') { exit 1 }"
if errorlevel 1 call :ferr_alternativa

set "JDKDIR=%FERR%\jdk"
set "SDK=%FERR%\sdk"
set "DL=%FERR%\downloads"
set "KS=%FERR%\nutrilab.keystore"
set "W=%FERR%\work"
set "BTV=34.0.0"
set "PLAT=android-34"
set "JDKURL=https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse"
set "CMDURL=https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
set "CMDURL2=https://dl.google.com/android/repository/commandlinetools-win-9477386_latest.zip"

echo.
echo ===== NutriLab: gerando o APK =====
echo.
if not exist "%FONTE%\AndroidManifest.xml" goto :sem_app
if not exist "%FERR%" mkdir "%FERR%"
if not exist "%DL%" mkdir "%DL%"
if exist "%LOG%" del /q "%LOG%"
echo Ferramentas em: %FERR%
echo.

echo [1/4] Java JDK 17
set "PASSO=Java JDK 17"
call :achar_jdk
if defined JAVA_HOME goto :jdk_ok
echo       Baixando o JDK 17: so na primeira vez, cerca de 190 MB...
call :baixar "%JDKURL%" "%DL%\jdk17.zip"
if errorlevel 1 goto :falha_download
echo       Extraindo...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%DL%\jdk17.zip' -DestinationPath '%JDKDIR%' -Force"
if errorlevel 1 goto :falha
call :achar_jdk
if not defined JAVA_HOME goto :falha
:jdk_ok
echo       OK: %JAVA_HOME%
set "PATH=%JAVA_HOME%\bin;%PATH%"

echo [2/4] Ferramentas de linha de comando do Android
set "PASSO=ferramentas de linha de comando do Android"
set "SDKMGR=%SDK%\cmdline-tools\latest\bin\sdkmanager.bat"
if exist "%SDKMGR%" goto :cmd_ok
echo       Baixando: so na primeira vez, cerca de 150 MB...
call :baixar "%CMDURL%" "%DL%\cmdline-tools.zip"
if not errorlevel 1 goto :cmd_baixado
call :baixar "%CMDURL2%" "%DL%\cmdline-tools.zip"
if errorlevel 1 goto :falha_download
:cmd_baixado
if exist "%SDK%\cmdline-tools" rmdir /s /q "%SDK%\cmdline-tools"
mkdir "%SDK%\cmdline-tools"
echo       Extraindo...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%DL%\cmdline-tools.zip' -DestinationPath '%SDK%\cmdline-tools' -Force"
if errorlevel 1 goto :falha
move "%SDK%\cmdline-tools\cmdline-tools" "%SDK%\cmdline-tools\latest" >nul
if not exist "%SDKMGR%" goto :falha
:cmd_ok
echo       OK

echo [3/4] Plataforma Android 34 e build-tools
set "PASSO=plataforma Android 34 e build-tools"
set "BT=%SDK%\build-tools\%BTV%"
set "AJAR=%SDK%\platforms\%PLAT%\android.jar"
if exist "%BT%\aapt2.exe" if exist "%AJAR%" goto :sdk_ok
echo       Aceitando as licencas e baixando, cerca de 120 MB. Pode demorar...
(for /l %%i in (1,1,80) do @echo y) | "%SDKMGR%" --sdk_root="%SDK%" --licenses >nul 2>&1
call "%SDKMGR%" --sdk_root="%SDK%" "platforms;%PLAT%" "build-tools;%BTV%"
if errorlevel 1 goto :falha_download
if not exist "%BT%\aapt2.exe" goto :falha
if not exist "%AJAR%" goto :falha
:sdk_ok
if exist "%KS%" goto :ks_ok
echo       Criando a chave de assinatura do app, uma vez so...
"%JAVA_HOME%\bin\keytool.exe" -genkeypair -keystore "%KS%" -alias nutrilab -keyalg RSA -keysize 2048 -validity 10000 -storepass android -keypass android -dname "CN=NutriLab, OU=Nutricao, O=NutriLab, C=BR" >nul 2>&1
if not exist "%KS%" goto :falha
:ks_ok
echo       OK

echo [4/4] Compilando o aplicativo
set "APP=%W%\app"
set "OBJ=%W%\obj"
if exist "%W%" rmdir /s /q "%W%"
if exist "%~dp0obj" rmdir /s /q "%~dp0obj"
mkdir "%W%"
set "PASSO=copiar o app para a pasta de trabalho sem acento"
xcopy "%FONTE%" "%APP%\" /e /i /y /q >nul
if errorlevel 1 goto :falha_build
set "PASSO=descobrir o endereco deste computador na rede"
set "IPLAN="
where py >nul 2>nul
if errorlevel 1 goto :ip_python
for /f %%i in ('py -3 "%~dp0ip_lan.py" 2^>nul') do set "IPLAN=%%i"
goto :ip_feito
:ip_python
for /f %%i in ('python "%~dp0ip_lan.py" 2^>nul') do set "IPLAN=%%i"
:ip_feito
if defined IPLAN >"%APP%\assets\servidor.txt" echo %IPLAN%:8765
mkdir "%OBJ%\classes"
mkdir "%OBJ%\dex"
if not exist "%SAIDA%" mkdir "%SAIDA%"
set "VCODE="
for /f %%i in ('powershell -NoProfile -Command "[int]((Get-Date -UFormat %%s)/60)"') do set "VCODE=%%i"
if not defined VCODE set "VCODE=1"
echo %VCODE%| findstr /r /x "[0-9][0-9]*" >nul
if errorlevel 1 set "VCODE=1"

set "PASSO=aapt2 compile - recursos"
"%BT%\aapt2.exe" compile --dir "%APP%\res" -o "%OBJ%\res.zip" >>"%LOG%" 2>&1
if errorlevel 1 goto :falha_build
set "PASSO=aapt2 link - manifesto e paginas"
"%BT%\aapt2.exe" link -o "%OBJ%\base.apk" -I "%AJAR%" --manifest "%APP%\AndroidManifest.xml" -A "%APP%\assets" --min-sdk-version 26 --target-sdk-version 34 --version-code %VCODE% --version-name 1.0 "%OBJ%\res.zip" >>"%LOG%" 2>&1
if errorlevel 1 goto :falha_build
set "PASSO=javac - codigo Java"
"%JAVA_HOME%\bin\javac.exe" -encoding UTF-8 -source 8 -target 8 -bootclasspath "%AJAR%" -d "%OBJ%\classes" "%APP%\src\br\nutrilab\mobile\MainActivity.java" >>"%LOG%" 2>&1
if errorlevel 1 goto :falha_build
set "PASSO=jar - empacotar as classes"
"%JAVA_HOME%\bin\jar.exe" cf "%OBJ%\classes.jar" -C "%OBJ%\classes" . >>"%LOG%" 2>&1
if errorlevel 1 goto :falha_build
set "PASSO=d8 - converter para Android"
call "%BT%\d8.bat" --lib "%AJAR%" --min-api 26 --output "%OBJ%\dex" "%OBJ%\classes.jar" >>"%LOG%" 2>&1
if errorlevel 1 goto :falha_build
set "PASSO=aapt add - juntar o codigo ao APK"
pushd "%OBJ%\dex"
"%BT%\aapt.exe" add "%OBJ%\base.apk" classes.dex >>"%LOG%" 2>&1
set "ERRO_AAPT=%errorlevel%"
popd
if not "%ERRO_AAPT%"=="0" goto :falha_build
set "PASSO=zipalign - alinhar o APK"
"%BT%\zipalign.exe" -f -p 4 "%OBJ%\base.apk" "%OBJ%\alinhado.apk" >>"%LOG%" 2>&1
if errorlevel 1 goto :falha_build
set "PASSO=apksigner - assinar o APK"
call "%BT%\apksigner.bat" sign --ks "%KS%" --ks-pass pass:android --key-pass pass:android --out "%OBJ%\NutriLab-Mobile.apk" "%OBJ%\alinhado.apk" >>"%LOG%" 2>&1
if errorlevel 1 goto :falha_build
if not exist "%OBJ%\NutriLab-Mobile.apk" goto :falha_build
set "PASSO=copiar o APK para a pasta saida"
if exist "%SAIDA%\NutriLab-Mobile.apk" del /q "%SAIDA%\NutriLab-Mobile.apk"
copy /y "%OBJ%\NutriLab-Mobile.apk" "%SAIDA%\NutriLab-Mobile.apk" >nul
if errorlevel 1 goto :falha_build
if not exist "%SAIDA%\NutriLab-Mobile.apk" goto :falha_build
if exist "%W%" rmdir /s /q "%W%"

echo.
echo ===== PRONTO =====
echo O APK esta em: %SAIDA%\NutriLab-Mobile.apk
echo.
echo Para instalar no celular: copie o arquivo para ele, ou baixe pelo Wi-Fi como abaixo.
echo.
if defined IPLAN echo No app, o endereco do servidor ja vem preenchido: %IPLAN%:8765
echo ATENCAO: o servidor NutriLab usa a porta 8765. A porta 8000 serve so para baixar o APK.
echo.
start "" explorer "%SAIDA%"
choice /c SN /n /m "Servir o APK pela rede agora, para baixar no celular? [S/N] "
if errorlevel 2 goto :fim
where py >nul 2>nul
if errorlevel 1 goto :com_python
py -3 "%~dp0servir_apk.py"
goto :fim
:com_python
python "%~dp0servir_apk.py"
goto :fim

:sem_app
echo ERRO: nao encontrei a pasta app ao lado deste arquivo.
goto :falha

:falha_download
echo.
echo ERRO ao baixar. Confira a internet. Se a rede do hospital bloqueia downloads,
echo tente em outra rede, como o celular compartilhando internet.
goto :falha

:falha_build
echo.
echo ERRO ao compilar. Ultimas linhas do registro:
if exist "%LOG%" powershell -NoProfile -Command "Get-Content -LiteralPath '%LOG%' -Tail 25"
goto :falha

:falha
echo.
echo O APK NAO foi gerado. Falhou em: %PASSO%
echo Registro completo: %LOG%
echo Se precisar de ajuda, envie o arquivo gerar_apk_log.txt.
pause
exit /b 1

:fim
pause
exit /b 0

:ferr_alternativa
if not defined PUBLIC set "PUBLIC=C:\Users\Public"
set "FERR=%PUBLIC%\NutriLabApk"
echo O caminho curto do seu perfil ainda tem acento. Usando a pasta alternativa:
echo %FERR%
echo As ferramentas serao baixadas de novo, uma vez so.
exit /b 0

:achar_jdk
set "JAVA_HOME="
for /d %%D in ("%JDKDIR%\jdk-*") do if exist "%%~fD\bin\javac.exe" set "JAVA_HOME=%%~fD"
exit /b 0

:baixar
rem uso: call :baixar URL ARQUIVO
if exist "%~2" del /q "%~2"
where curl.exe >nul 2>nul
if errorlevel 1 goto :baixar_ps
curl.exe -L --fail --retry 3 --connect-timeout 30 -o "%~2" "%~1"
if errorlevel 1 exit /b 1
if not exist "%~2" exit /b 1
exit /b 0
:baixar_ps
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri '%~1' -OutFile '%~2'"
if errorlevel 1 exit /b 1
if not exist "%~2" exit /b 1
exit /b 0
