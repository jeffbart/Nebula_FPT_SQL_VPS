Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-NebulaEnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }

    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $separator = $trimmed.IndexOf("=")
        if ($separator -lt 1) {
            continue
        }

        if ($trimmed.Substring(0, $separator).Trim() -ne $Name) {
            continue
        }

        $value = $trimmed.Substring($separator + 1).Trim()
        if ($value.Length -ge 2) {
            $quoted = ($value.StartsWith('"') -and $value.EndsWith('"')) -or
                      ($value.StartsWith("'") -and $value.EndsWith("'"))
            if ($quoted) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }
        return $value
    }

    return $null
}

function Read-NebulaSecret {
    param([Parameter(Mandatory = $true)][string]$Prompt)

    $secureValue = Read-Host $Prompt -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Invoke-TelegramApi {
    param(
        [Parameter(Mandatory = $true)][string]$Token,
        [Parameter(Mandatory = $true)][string]$Method,
        [hashtable]$Body
    )

    $request = @{
        Uri         = "https://api.telegram.org/bot$Token/$Method"
        Method      = "Post"
        ErrorAction = "Stop"
    }
    if ($Body) {
        $request.Body = $Body
    }

    try {
        $response = Invoke-RestMethod @request
    }
    catch {
        $detail = $_.ErrorDetails.Message
        if ($detail) {
            $description = $null
            try {
                $parsed = $detail | ConvertFrom-Json
                $description = $parsed.description
            }
            catch {
                $description = $null
            }
            if ($description) {
                throw "Telegram: $description"
            }
            throw "Falha na API do Telegram: $detail"
        }
        throw "Falha na API do Telegram: $($_.Exception.Message)"
    }

    if (-not $response.ok) {
        throw "Telegram recusou a operacao: $($response.description)"
    }
    return $response.result
}
