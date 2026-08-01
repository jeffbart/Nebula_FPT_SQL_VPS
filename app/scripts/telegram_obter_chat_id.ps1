param(
    [string]$EnvFile
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "telegram_common.ps1")

if (-not $EnvFile) {
    $EnvFile = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "config\.env"
}

try {
    $token = Get-NebulaEnvValue -Path $EnvFile -Name "BOT_TOKEN"
    if (-not $token) {
        $token = Read-NebulaSecret "BOT_TOKEN (entrada oculta)"
    }
    if (-not $token) {
        throw "BOT_TOKEN nao informado."
    }

    $bot = Invoke-TelegramApi -Token $token -Method "getMe"
    Write-Host "Bot validado: @$($bot.username)" -ForegroundColor Green

    $updates = Invoke-TelegramApi -Token $token -Method "getUpdates" -Body @{
        timeout         = 0
        allowed_updates = '["channel_post"]'
    }

    $channels = @(
        $updates |
            Where-Object { $_.channel_post -and $_.channel_post.chat } |
            ForEach-Object { $_.channel_post.chat } |
            Group-Object id |
            ForEach-Object { $_.Group[0] }
    )

    if ($channels.Count -eq 0) {
        Write-Host ""
        Write-Host "Nenhum canal encontrado." -ForegroundColor Yellow
        Write-Host "Confirme que o bot e administrador, publique uma NOVA mensagem no canal e execute novamente."
        exit 2
    }

    Write-Host ""
    Write-Host "Canais encontrados:" -ForegroundColor Cyan
    $channels | Select-Object id, title, type | Format-Table -AutoSize
    Write-Host "Copie o ID correto para CHAT_ID em config\.env."
}
catch {
    Write-Host "[ERRO] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    $token = $null
}
