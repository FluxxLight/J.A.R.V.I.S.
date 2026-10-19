@echo off
REM J.A.R.V.I.S. — execução no Windows
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (echo Python nao encontrado no PATH. & pause & exit /b 1)
python main.py %*
endlocal
