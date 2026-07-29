@echo off
REM ============================================================
REM  CRIADOR SPRITES - atalho de execucao (duplo-clique)
REM  Pede o nome do arquivo de imagem (dentro de input\) e o nome
REM  do personagem, e roda o pipeline completo (imagem -> spritesheet).
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo === CRIADOR SPRITES ===
echo.
echo Coloque a imagem do personagem dentro da pasta "input\" antes de continuar.
echo (vista de frente, pose A, maos abertas vazias, sem arma, fundo claro, estilo chibi)
echo.

set /p IMG="Nome do arquivo de imagem (ex.: guerreiro.png): "
set /p NOME="Nome do personagem (ex.: guerreiro): "

echo.
echo Qual classe?
echo   1 = Guerreiro (golpe corpo-a-corpo)
echo   2 = Mago (gesto de conjuracao)
echo   3 = Arqueiro (arco e flecha)
set /p CLASSE_OPT="Digite 1, 2 ou 3: "

if "%CLASSE_OPT%"=="1" set CLASSE=guerreiro
if "%CLASSE_OPT%"=="2" set CLASSE=mago
if "%CLASSE_OPT%"=="3" set CLASSE=arqueiro
if not defined CLASSE set CLASSE=guerreiro

if not exist "input\%IMG%" (
    echo.
    echo ERRO: nao encontrei "input\%IMG%".
    echo Verifique se o arquivo esta na pasta input\ e tente de novo.
    goto :fim
)

echo.
echo Gerando spritesheet (classe: %CLASSE%), isso pode levar alguns minutos...
echo.
venv_bpy\Scripts\python.exe criar.py "input\%IMG%" --name "%NOME%" --classe %CLASSE%

echo.
echo ============================================================
echo  Pronto! Resultado em: output\%NOME%.png / .json / _frames.tres
echo ============================================================

:fim
endlocal
pause
