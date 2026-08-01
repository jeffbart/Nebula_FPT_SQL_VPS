[CmdletBinding()]
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$VenvPython = ""
)

$ErrorActionPreference = "Stop"
$deploymentRoot = Split-Path -Parent $ProjectRoot
if (-not $VenvPython) {
    $VenvPython = Join-Path $deploymentRoot "venv\Scripts\python.exe"
}
$environmentFile = Join-Path $deploymentRoot "config\.env"
$environmentExample = Join-Path $deploymentRoot "config\.env.vps.example"
$env:NEBULA_ENV_FILE = $environmentFile

if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Python do ambiente virtual não encontrado: $VenvPython"
}
if (-not (Test-Path -LiteralPath $ProjectRoot)) {
    throw "Diretório da aplicação não encontrado: $ProjectRoot"
}
if (-not (Test-Path -LiteralPath $environmentFile)) {
    if (-not (Test-Path -LiteralPath $environmentExample)) {
        throw "Exemplo de configuração não encontrado: $environmentExample"
    }
    Copy-Item -LiteralPath $environmentExample -Destination $environmentFile
    Write-Warning "Preencha $environmentFile antes de aplicar migrations."
    return
}

Push-Location $ProjectRoot
try {
    & $VenvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependências." }

    & $VenvPython -m scripts.migrate
    if ($LASTEXITCODE -ne 0) { throw "Falha ao aplicar migrations SQL." }

    & $VenvPython -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Testes falharam." }
}
finally {
    Pop-Location
}

Write-Host "Preparação da aplicação concluída."
