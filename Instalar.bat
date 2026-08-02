@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"

echo ============================================================
echo   Jennifer Moda Fitness - Instalacao
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao foi encontrado neste computador.
    echo Instale o Python em https://www.python.org/downloads/ e tente novamente.
    echo Durante a instalacao do Python, marque a opcao "Add Python to PATH".
    pause
    exit /b 1
)

if not exist venv (
    echo Criando ambiente do sistema...
    python -m venv venv
)

echo Instalando componentes necessarios (pode demorar alguns minutos)...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt

echo.
echo Preparando o banco de dados...
set FLASK_APP=run.py
flask db upgrade

echo.
echo ============================================================
echo   Agora vamos criar o primeiro usuario administrador.
echo ============================================================
python seed.py

echo.
echo ============================================================
echo   Instalacao concluida!
echo   Use o atalho "Iniciar Sistema.bat" sempre que for abrir o sistema.
echo ============================================================
pause
