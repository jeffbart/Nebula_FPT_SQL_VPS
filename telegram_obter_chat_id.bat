@echo off
setlocal
cd /d "%~dp0"

echo ==================================================
echo       NEBULA FTP - LOCALIZAR CANAL TELEGRAM
echo ==================================================
echo.
echo Publique uma NOVA mensagem no canal depois de adicionar
echo o bot como administrador. O token nao sera exibido.
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\scripts\telegram_obter_chat_id.ps1" -EnvFile "%~dp0config\.env"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo [FALHA] Nao foi possivel obter o CHAT_ID.
) else (
    echo [OK] Consulta concluida.
)
echo.
pause
exit /b %EXIT_CODE%
