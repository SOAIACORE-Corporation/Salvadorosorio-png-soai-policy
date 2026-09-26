[CmdletBinding()]
param(
    [switch]$CheckOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Check {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][string]$Value
    )
    Write-Host ("{0}={1}" -f $Name, $Value)
}

Write-Check 'PREFLIGHT_MODE' 'READ_ONLY'
Write-Check 'POWERSHELL_EDITION' $PSVersionTable.PSEdition
Write-Check 'POWERSHELL_VERSION' $PSVersionTable.PSVersion.ToString()
Write-Check 'CURRENT_DIRECTORY' (Get-Location).Path

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$BootstrapScript = Join-Path $PSScriptRoot 'Bootstrap-SOAIntelligenceGitHubOidc.ps1'

Write-Check 'REPO_ROOT' $RepoRoot
Write-Check 'BOOTSTRAP_SCRIPT' $BootstrapScript

if (-not (Test-Path -LiteralPath $BootstrapScript -PathType Leaf)) {
    Write-Check 'BOOTSTRAP_SCRIPT_EXISTS' 'false'
    throw 'Bootstrap script not found. Stop before attempting execution.'
}
Write-Check 'BOOTSTRAP_SCRIPT_EXISTS' 'true'

$AzCommand = Get-Command az -ErrorAction SilentlyContinue
if ($null -eq $AzCommand) {
    Write-Check 'AZ_CLI_AVAILABLE' 'false'
    throw 'Azure CLI was not found in PATH.'
}
Write-Check 'AZ_CLI_AVAILABLE' 'true'

& az account show --only-show-errors --output none
if ($LASTEXITCODE -ne 0) {
    Write-Check 'AZURE_AUTH_CONTEXT' 'FAIL'
    throw 'Azure CLI is not authenticated. Authenticate before continuing.'
}
Write-Check 'AZURE_AUTH_CONTEXT' 'PASS'

Write-Check 'COMMAND_STYLE' 'PLAIN_TEXT_SINGLE_COMMAND'
Write-Check 'TRAILING_PERIOD_FORBIDDEN' 'true'
Write-Check 'MUTATION_PARAMETERS_PRESENT' 'false'
Write-Check 'AZURE_MUTATION' 'false'

if ($CheckOnly) {
    Write-Check 'BOOTSTRAP_PLAN_EXECUTED' 'false'
    Write-Check 'PREFLIGHT_RESULT' 'PASS_CHECK_ONLY'
    exit 0
}

Write-Host ''
Write-Host 'Invoking bootstrap in PLAN_ONLY mode. No -Apply or -AuthorizeIam parameters are passed.'
Write-Host ''

& $BootstrapScript
if ($LASTEXITCODE -ne 0) {
    Write-Check 'BOOTSTRAP_PLAN_EXECUTED' 'true'
    Write-Check 'PREFLIGHT_RESULT' 'FAIL_BOOTSTRAP_PLAN'
    exit $LASTEXITCODE
}

Write-Check 'BOOTSTRAP_PLAN_EXECUTED' 'true'
Write-Check 'PREFLIGHT_RESULT' 'PASS'
