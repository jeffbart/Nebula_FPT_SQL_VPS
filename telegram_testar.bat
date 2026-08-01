@echo off
setlocal
cd /d "%~dp0"

echo ==================================================
echo          NEBULA FTP - TESTE DO TELEGRAM
echo ==================================================
echo.
echo Este teste enviara uma mensagem silenciosa ao canal e,
echo em seguida, tentara apaga-la para validar as permissoes.
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\scripts\telegram_testar.ps1" -EnvFile "%~dp0config\.env"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo [FALHA] O teste do Telegram nao foi concluido.
) else (
    echo [OK] Bot, canal, envio e exclusao validados.
)
echo.
pause
exit /b %EXIT_CODE%
