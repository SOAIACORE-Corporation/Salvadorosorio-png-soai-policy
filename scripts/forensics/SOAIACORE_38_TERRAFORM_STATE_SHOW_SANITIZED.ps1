[CmdletBinding()]
param(
    [switch]$SelfTest
)

$ErrorActionPreference = 'Stop'

$Root = Join-Path $env:TEMP 'soaiacore-state-verify\infra\azure\p0'
$Stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$Out = Join-Path $HOME "SOAIACORE_38_TF_STATE_SHOW_SANITIZED_$Stamp.txt"
$Sha = "$Out.sha256"

$Addresses = @(
  'azurerm_consumption_budget_resource_group.pilot',
  'azurerm_key_vault.pilot',
  'azurerm_key_vault_secret.ghcr',
  'azurerm_key_vault_secret.internal_auth',
  'azurerm_key_vault_secret.oidc[0]',
  'azurerm_key_vault_secret.postgresql',
  'azurerm_monitor_metric_alert.core_unavailable',
  'azurerm_monitor_metric_alert.web_unavailable',
  'azurerm_monitor_metric_alert.worker_failed',
  'azurerm_private_dns_zone.blob',
  'azurerm_private_dns_zone.key_vault',
  'azurerm_private_dns_zone_virtual_network_link.blob',
  'azurerm_private_dns_zone_virtual_network_link.key_vault',
  'azurerm_private_endpoint.evidence_blob',
  'azurerm_private_endpoint.key_vault',
  'azurerm_role_assignment.operator_key_vault_secrets_officer',
  'azurerm_role_assignment.workload_key_vault_secrets_user',
  'azurerm_subnet.private_endpoints',
  'data.azurerm_client_config.current',
  'data.azurerm_monitor_action_group.operations',
  'random_password.internal_auth',

  # Existing resources known to have been updated during provider hardening.
  'azurerm_storage_account.evidence',
  'azurerm_container_app.core',
  'azurerm_container_app.web',
  'azurerm_container_app_job.worker'
)

function Sanitize-StateShow {
    param([string[]]$Lines)

    $outLines = New-Object System.Collections.Generic.List[string]

    foreach ($line in $Lines) {
        # Terraform normally renders sensitive state values as "(sensitive value)".
        # These additional rules redact secret-bearing attributes even if provider
        # rendering changes. Structural names/IDs/references remain available.
        if ($line -match '(?i)^\s*(value(?:_wo(?:_version)?)?|result|bcrypt_hash|password|[A-Za-z0-9_]+_password|token|[A-Za-z0-9_]+_token|access_key|[A-Za-z0-9_]+_access_key|connection_string|[A-Za-z0-9_]+_connection_string|client_secret|client_password)\s*=') {
            $key = ($line -replace '^\s*([^=]+)=.*$', '$1').TrimEnd()
            $indent = ([regex]::Match($line, '^\s*')).Value
            $outLines.Add("$indent$key= <REDACTED>")
            continue
        }

        # Defense in depth against common credential-like strings.
        $safe = $line
        $safe = $safe -replace '(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+', '$1<REDACTED>'
        $safe = $safe -replace '(?i)(sk-[A-Za-z0-9_-]{10,})', '<REDACTED>'
        $safe = $safe -replace '(?i)(gh[pousr]_[A-Za-z0-9_]{10,})', '<REDACTED>'
        $outLines.Add($safe)
    }

    return $outLines
}

if ($SelfTest) {
    $fixture = @(
        '    value = "do-not-expose"',
        '    result = "do-not-expose"',
        '    ghcr_token = "do-not-expose"',
        '    key_vault_secret_id = "/subscriptions/example/secrets/internal-auth-secret"',
        '    password_secret_name = "ghcr-pull-token"',
        '    name = "safe-name"'
    )

    $sanitizedFixture = @(Sanitize-StateShow $fixture)

    if ($Addresses.Count -ne 25) {
        throw "SELFTEST_ADDRESS_COUNT: expected 25, observed $($Addresses.Count)"
    }
    if ($sanitizedFixture[0] -notmatch '<REDACTED>' -or
        $sanitizedFixture[1] -notmatch '<REDACTED>' -or
        $sanitizedFixture[2] -notmatch '<REDACTED>') {
        throw 'SELFTEST_REDACTION: sensitive attributes were not redacted.'
    }
    if ($sanitizedFixture[3] -match '<REDACTED>' -or
        $sanitizedFixture[4] -match '<REDACTED>' -or
        $sanitizedFixture[5] -match '<REDACTED>') {
        throw 'SELFTEST_STRUCTURE: structural names/IDs were incorrectly redacted.'
    }

    Write-Host 'SELFTEST=PASS'
    Write-Host 'PARSER_EXECUTION_REACHED=true'
    Write-Host 'TERRAFORM_CALLED=false'
    Write-Host 'AZURE_CALLED=false'
    Write-Host 'MUTATION=false'
    exit 0
}

if (-not (Test-Path $Root)) {
    throw "Expected Terraform working directory not found: $Root"
}

if (-not (Get-Command terraform -ErrorAction SilentlyContinue)) {
    throw 'terraform executable not found in PATH.'
}

Set-Location $Root

$stateList = @(terraform state list 2>&1)
if ($LASTEXITCODE -ne 0) {
    throw "terraform state list failed. No mutation was attempted.`n$($stateList -join [Environment]::NewLine)"
}

$header = @(
    'SOAIACORE #38 · SANITIZED TERRAFORM STATE-SHOW EVIDENCE'
    "COLLECTED_UTC=$((Get-Date).ToUniversalTime().ToString('o'))"
    "WORKDIR=$Root"
    "STATE_ADDRESS_COUNT=$($stateList.Count)"
    'STATE_PULL=false'
    'STATE_JSON=false'
    'PLAN=false'
    'APPLY=false'
    'DESTROY=false'
    'STATE_RM=false'
    'IMPORT=false'
    'MUTATION=false'
    ''
)

Set-Content -LiteralPath $Out -Value $header -Encoding utf8

$missing = New-Object System.Collections.Generic.List[string]
$shown = 0

foreach ($address in $Addresses) {
    Add-Content -LiteralPath $Out -Value "===== $address =====" -Encoding utf8

    if ($stateList -notcontains $address) {
        Add-Content -LiteralPath $Out -Value 'STATUS=NOT_IN_STATE' -Encoding utf8
        Add-Content -LiteralPath $Out -Value '' -Encoding utf8
        $missing.Add($address)
        continue
    }

    $raw = @(terraform state show -no-color $address 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Add-Content -LiteralPath $Out -Value 'STATUS=READ_FAILED' -Encoding utf8
        $san = Sanitize-StateShow $raw
        Add-Content -LiteralPath $Out -Value $san -Encoding utf8
        Add-Content -LiteralPath $Out -Value '' -Encoding utf8
        continue
    }

    Add-Content -LiteralPath $Out -Value 'STATUS=PASS' -Encoding utf8
    $san = Sanitize-StateShow $raw
    Add-Content -LiteralPath $Out -Value $san -Encoding utf8
    Add-Content -LiteralPath $Out -Value '' -Encoding utf8
    $shown++
}

$hash = (Get-FileHash -LiteralPath $Out -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath $Sha -Value "$hash  $([IO.Path]::GetFileName($Out))" -Encoding ascii

Write-Host ''
Write-Host '=== SOAIACORE #38 TF STATE-SHOW RESULT ==='
Write-Host "STATE_ADDRESS_COUNT=$($stateList.Count)"
Write-Host "REQUESTED_ADDRESS_COUNT=$($Addresses.Count)"
Write-Host "STATE_SHOW_PASS_COUNT=$shown"
Write-Host "NOT_IN_STATE_COUNT=$($missing.Count)"
Write-Host 'STATE_PULL=false'
Write-Host 'STATE_JSON=false'
Write-Host 'PLAN=false'
Write-Host 'APPLY=false'
Write-Host 'MUTATION=false'
Write-Host "EVIDENCE_FILE=$Out"
Write-Host "SHA256=$hash"
Write-Host 'DONE=true'
