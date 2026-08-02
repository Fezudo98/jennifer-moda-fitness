@echo off
chcp 65001 >nul
set PYTHONUTF8=1
setlocal

rem ============================================================
rem   ESTE E O UNICO ARQUIVO QUE PRECISA SER LEVADO MANUALMENTE
rem   para o computador da loja (pendrive, e-mail, WhatsApp...).
rem   Todo o resto do sistema e baixado automaticamente do GitHub.
rem ============================================================

rem >>> Edite a linha abaixo com a URL do repositorio + token <<<
set REPO_URL=https://SEU_TOKEN_AQUI@github.com/USUARIO/REPOSITORIO.git

set PASTA=%USERPROFILE%\Desktop\Jennifer Moda Fitness

echo ============================================================
echo   Jennifer Moda Fitness - Preparando instalacao
echo ============================================================
echo.

where git >nul 2>nul
if errorlevel 1 (
    echo [ERRO] O programa "Git" nao esta instalado neste computador.
    echo Baixe e instale em: https://git-scm.com/download/win
    echo Durante a instalacao, pode deixar todas as opcoes no padrao.
    echo Depois de instalar, rode este arquivo de novo.
    pause
    exit /b 1
)

if exist "%PASTA%" (
    echo A pasta do sistema ja existe em:
    echo   %PASTA%
    echo Pulando o download e indo direto para a instalacao.
) else (
    echo Baixando o sistema, aguarde...
    git clone "%REPO_URL%" "%PASTA%"
    if errorlevel 1 (
        echo.
        echo [ERRO] Nao foi possivel baixar o sistema. Verifique a internet
        echo e se o endereco do repositorio configurado neste arquivo esta correto.
        pause
        exit /b 1
    )
)

cd /d "%PASTA%"
call Instalar.bat
