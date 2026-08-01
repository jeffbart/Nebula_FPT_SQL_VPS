param(
    [string]$EnvFile
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "telegram_common.ps1")

if (-not $EnvFile) {
    $EnvFile = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "config\.env"
}

$testMessageId = $null
$token = $null
$chatId = $null

try {
    if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
        throw "Arquivo de configuracao nao encontrado: $EnvFile"
    }

    $token = Get-NebulaEnvValue -Path $EnvFile -Name "BOT_TOKEN"
    $chatId = Get-NebulaEnvValue -Path $EnvFile -Name "CHAT_ID"
    if (-not $token) { throw "BOT_TOKEN nao configurado em $EnvFile" }
    if (-not $chatId) { throw "CHAT_ID nao configurado em $EnvFile" }

    Write-Host "[1/4] Validando o token..."
    $bot = Invoke-TelegramApi -Token $token -Method "getMe"
    Write-Host "      Bot: @$($bot.username)" -ForegroundColor Green

    Write-Host "[2/4] Validando acesso ao canal..."
    $chat = Invoke-TelegramApi -Token $token -Method "getChat" -Body @{ chat_id = $chatId }
    Write-Host "      Canal: $($chat.title) ($($chat.id))" -ForegroundColor Green

    Write-Host "[3/4] Enviando mensagem temporaria..."
    $sent = Invoke-TelegramApi -Token $token -Method "sendMessage" -Body @{
        chat_id              = $chatId
        text                 = "Teste automatico NebulaFTP - $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))"
        disable_notification = "true"
    }
    $testMessageId = $sent.message_id
    Write-Host "      Envio confirmado (message_id=$testMessageId)." -ForegroundColor Green

    Write-Host "[4/4] Apagando mensagem temporaria..."
    $deleted = Invoke-TelegramApi -Token $token -Method "deleteMessage" -Body @{
        chat_id    = $chatId
        message_id = $testMessageId
    }
    if (-not $deleted) {
        throw "A API nao confirmou a exclusao da mensagem de teste."
    }
    $testMessageId = $null
    Write-Host "      Exclusao confirmada." -ForegroundColor Green
    Write-Host ""
    Write-Host "Telegram pronto para o NebulaFTP." -ForegroundColor Green
    Write-Host "Observacao: API_ID e API_HASH sao validados ao iniciar o NebulaFTP."
}
catch {
    Write-Host "[ERRO] $($_.Exception.Message)" -ForegroundColor Red
    if ($testMessageId) {
        Write-Host "A mensagem temporaria $testMessageId pode ter permanecido no canal." -ForegroundColor Yellow
    }
    exit 1
}
finally {
    $token = $null
    $chatId = $null
}
