@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"

if not exist venv (
    echo [ERRO] O sistema ainda nao foi instalado neste computador.
    echo Rode primeiro o atalho "Instalar.bat".
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo ============================================================
python atualizar.py
echo ============================================================
echo.

python iniciar_producao.py

echo.
echo O sistema foi encerrado.
pause
