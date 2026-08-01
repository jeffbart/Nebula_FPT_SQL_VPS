@echo off
setlocal EnableExtensions

rem Este BAT fica na raiz da implantação, um nível acima da pasta app.
cd /d "%~dp0"
set "NEBULA_ROOT=%CD%"
set "NEBULA_APP=%NEBULA_ROOT%\app"
set "NEBULA_PYTHON=%NEBULA_ROOT%\venv\Scripts\python.exe"

title NebulaFTP SQL + FTPS
echo ==================================================
echo          NEBULA FTP - SQL SERVER + FTPS
echo ==================================================
echo.

if not exist "%NEBULA_APP%\main.py" (
    echo [ERRO] Nao foi encontrado: %NEBULA_APP%\main.py
    goto :falha
)
if not exist "%NEBULA_APP%\ftp\database.py" (
    echo [ERRO] A pasta app nao contem a variante SQL/FTPS.
    goto :falha
)
if not exist "%NEBULA_APP%\ftp\staging_space.py" (
    echo [ERRO] Modulo de liberacao progressiva nao encontrado:
    echo        %NEBULA_APP%\ftp\staging_space.py
    echo Sincronize toda a pasta app da versao atual para a VPS.
    goto :falha
)
if not exist "%NEBULA_PYTHON%" (
    echo [ERRO] Ambiente virtual nao encontrado:
    echo        %NEBULA_PYTHON%
    echo Execute app\scripts\deploy_vps.ps1 primeiro.
    goto :falha
)

findstr /C:"SQLServerPathIO" /C:"SQLServerUserManager" "%NEBULA_APP%\main.py" >nul 2>&1
if errorlevel 1 (
    echo [ERRO] main.py nao foi reconhecido como a variante SQL/FTPS.
    goto :falha
)

if not defined NEBULA_ENV_FILE set "NEBULA_ENV_FILE=%NEBULA_ROOT%\config\.env"
if not exist "%NEBULA_ENV_FILE%" (
    echo [ERRO] Configuracao nao encontrada: %NEBULA_ENV_FILE%
    echo Copie config\.env.vps.example para config\.env e preencha os valores.
    goto :falha
)

echo Raiz:        %NEBULA_ROOT%
echo Aplicacao:   %NEBULA_APP%
echo Configuracao:%NEBULA_ENV_FILE%
echo Python:      %NEBULA_PYTHON%
echo.

echo [1/2] Validando dependencias...
"%NEBULA_PYTHON%" -c "import pyodbc, bcrypt, cryptography, pyrogram, aiofiles, dotenv; print('Dependencias OK')"
if errorlevel 1 goto :falha

echo [2/2] Iniciando NebulaFTP...
echo Para encerrar, pressione Ctrl+C.
echo.
pushd "%NEBULA_APP%"
"%NEBULA_PYTHON%" main.py
set "NEBULA_EXIT=%ERRORLEVEL%"
popd

if not "%NEBULA_EXIT%"=="0" goto :falha
echo NebulaFTP encerrado normalmente.
exit /b 0

:falha
echo.
echo [FALHA] O NebulaFTP nao foi iniciado.
echo Consulte a mensagem acima e o log configurado no .env.
echo.
pause
exit /b 1
