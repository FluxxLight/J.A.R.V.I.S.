@echo off
REM ============================================================
REM  J.A.R.V.I.S. — build do EXE (Windows)
REM  Uso: build.bat
REM ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo [1/3] Verificando Python...
where python >nul 2>nul
if errorlevel 1 (
    echo ERRO: Python nao encontrado no PATH. Instale Python 3.10+ e tente de novo.
    pause
    exit /b 1
)
python --version

echo.
echo [2/3] Instalando dependencias de build...
python -m pip install -r requirements-ui.txt -r requirements-build.txt
if errorlevel 1 (
    echo ERRO: falha ao instalar dependencias de UI/build.
    pause
    exit /b 1
)
echo.
echo Dependencias OPCIONAIS de voz local (recomendado p/ EXE com voz):
echo   pip install -r requirements-voice.txt
python -c "import vosk" >nul 2>nul
if errorlevel 1 (
    echo   (vosk NAO instalado - o EXE saira sem reconhecimento; modo texto.)
) else (
    echo   (voz local detectada - sera empacotada no EXE.)
)

echo.
echo [3/3] Executando build reproduzivel...
python build.py
set BUILD_CODE=!errorlevel!

if !BUILD_CODE! neq 0 (
    echo.
    echo BUILD FALHOU (codigo !BUILD_CODE!). Veja as mensagens acima.
    pause
    exit /b !BUILD_CODE!
)

echo.
echo ============================================================
echo  BUILD OK. Entrega em: dist\JARVIS\J.A.R.V.I.S.exe
echo ============================================================
pause
endlocal
