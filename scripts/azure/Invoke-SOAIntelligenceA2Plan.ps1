[CmdletBinding()]
param(
    [string]$SubscriptionId = '108eb4dd-25b3-4a7f-8d5e-4ec4389c3f0d',
    [string]$ExpectedBranch = 'feature/soa-intelligence-a2-postgres-20260906-r2',
    [string]$StateResourceGroup = 'rg-soaiacore-tfstate-34utxi',
    [string]$StateStorageAccount = 'stsoaiacoretf34utxi',
    [string]$StateContainer = 'tfstate',
    [string]$StateKey = 'soa-intelligence/dev/postgres.tfstate',
    [string]$ExpectedResourceGroup = 'rg-soa-intelligence-dev'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'This controlled A2 plan runner requires PowerShell 7 or newer (pwsh.exe).'
}
if (-not $IsWindows) {
    throw 'This controlled A2 plan runner must be executed from the authorized Windows operator workstation, not Cloud Shell or a GitHub-hosted runner.'
}

function Assert-LastExitCode {
    param([Parameter(Mandatory)][string]$Operation)
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE."
    }
}

function Write-Boundary {
    param([string]$Name, [string]$Value)
    Write-Host ("{0}={1}" -f $Name, $Value)
}

function Get-Sha256 {
    param([Parameter(Mandatory)][string]$Path)
    return (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLowerInvariant()
}

$repoRoot = (& git rev-parse --show-toplevel).Trim()
Assert-LastExitCode 'git rev-parse --show-toplevel'
Set-Location $repoRoot

$currentBranch = (& git branch --show-current).Trim()
Assert-LastExitCode 'git branch --show-current'
if ($currentBranch -ne $ExpectedBranch) {
    throw "Expected branch '$ExpectedBranch' but current branch is '$currentBranch'. Refusing to plan from a different branch."
}

$dirty = & git status --porcelain
Assert-LastExitCode 'git status --porcelain'
if (-not [string]::IsNullOrWhiteSpace(($dirty -join "`n"))) {
    throw 'Working tree is not clean. Refusing to create a governed plan.'
}

& git fetch origin $ExpectedBranch --quiet
Assert-LastExitCode 'git fetch origin feature branch'
$localHead = (& git rev-parse HEAD).Trim()
Assert-LastExitCode 'git rev-parse HEAD'
$remoteHead = (& git rev-parse "origin/$ExpectedBranch").Trim()
Assert-LastExitCode 'git rev-parse origin feature branch'
if ($localHead -ne $remoteHead) {
    throw "Local HEAD '$localHead' does not match remote branch HEAD '$remoteHead'. Pull/reclone before planning."
}
Write-Boundary 'CONFIG_COMMIT' $localHead
Write-Boundary 'BRANCH_SYNC' 'PASS'

$terraformInfoRaw = & terraform version -json
Assert-LastExitCode 'terraform version -json'
$terraformInfo = $terraformInfoRaw | ConvertFrom-Json
$terraformVersion = [version]$terraformInfo.terraform_version
if ($terraformVersion.Major -ne 1 -or $terraformVersion.Minor -ne 15) {
    throw "Terraform 1.15.x is required by the frozen A2 stack. Found $terraformVersion."
}
Write-Boundary 'TERRAFORM_VERSION_GATE' 'PASS'

$accountRaw = & az account show --only-show-errors --output json
Assert-LastExitCode 'az account show'
$account = $accountRaw | ConvertFrom-Json
if ([string]$account.id -ne $SubscriptionId) {
    throw 'Authenticated Azure subscription does not match the governed A2 subscription.'
}
$tenantId = [string]$account.tenantId
Write-Boundary 'AZURE_ACCOUNT_CONTEXT' 'PASS'
Write-Boundary 'SUBSCRIPTION_MATCH' 'PASS'

$containerExists = (& az storage container exists `
    --auth-mode login `
    --account-name $StateStorageAccount `
    --name $StateContainer `
    --query exists `
    --output tsv `
    --only-show-errors).Trim()
Assert-LastExitCode 'Azure state container probe'
if ($containerExists -ne 'true') {
    throw 'Governed Terraform state container is not reachable from this workstation/session.'
}
Write-Boundary 'STATE_CONTAINER_ACCESS' 'PASS'

$stateBlobExists = (& az storage blob exists `
    --auth-mode login `
    --account-name $StateStorageAccount `
    --container-name $StateContainer `
    --name $StateKey `
    --query exists `
    --output tsv `
    --only-show-errors).Trim()
Assert-LastExitCode 'A2 state key collision probe'
if ($stateBlobExists -eq 'true') {
    throw "A2 state key '$StateKey' already exists. Refusing first-plan semantics until reconciled."
}
Write-Boundary 'A2_STATE_KEY_ABSENT' 'PASS'

$rgExists = (& az group exists --name $ExpectedResourceGroup --only-show-errors --output tsv).Trim()
Assert-LastExitCode 'A2 resource group collision probe'
if ($rgExists -eq 'true') {
    throw "Resource group '$ExpectedResourceGroup' already exists outside the new A2 Terraform state. Refusing unmanaged collision."
}
Write-Boundary 'A2_RESOURCE_GROUP_ABSENT' 'PASS'

$timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$artifactRoot = Join-Path $HOME ("SOAIACORE\controlled-a2-plan\$timestamp")
$evidenceDir = Join-Path $artifactRoot 'evidence'
New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null

$identity = (& whoami).Trim()
& icacls $artifactRoot /inheritance:r | Out-Null
Assert-LastExitCode 'icacls disable inheritance'
& icacls $artifactRoot /grant:r "${identity}:(OI)(CI)F" | Out-Null
Assert-LastExitCode 'icacls operator-only grant'
Write-Boundary 'ARTIFACT_ACL' 'OPERATOR_ONLY'

$backendConfigPath = Join-Path $evidenceDir 'backend.hcl'
@"
resource_group_name  = "$StateResourceGroup"
storage_account_name = "$StateStorageAccount"
container_name       = "$StateContainer"
key                  = "$StateKey"
use_azuread_auth     = true
use_cli              = true
tenant_id             = "$tenantId"
subscription_id       = "$SubscriptionId"
"@ | Set-Content -Path $backendConfigPath -Encoding utf8NoBOM

$stackDir = Join-Path $repoRoot 'infra\azure\soa-intelligence-dev'
if (-not (Test-Path -LiteralPath $stackDir -PathType Container)) {
    throw "Terraform stack directory not found: $stackDir"
}
Write-Boundary 'STACK_PATH' 'PASS'

$planPath = Join-Path $evidenceDir 'soa-intelligence-a2.tfplan'
$planJsonPath = Join-Path $evidenceDir 'soa-intelligence-a2.tfplan.json'
$receiptPath = Join-Path $artifactRoot 'SOA_INTELLIGENCE_A2_PLAN_RECEIPT.sanitized.json'

$env:TF_IN_AUTOMATION = 'true'
$env:TF_INPUT = 'false'
$env:TF_VAR_subscription_id = $SubscriptionId
$env:ARM_SUBSCRIPTION_ID = $SubscriptionId
$env:ARM_TENANT_ID = $tenantId
$env:ARM_USE_AZUREAD = 'true'
$env:ARM_USE_CLI = 'true'

$chdirArg = "-chdir=$stackDir"
& terraform $chdirArg fmt -check -diff
Assert-LastExitCode 'terraform fmt -check'
& terraform $chdirArg init -reconfigure -input=false "-backend-config=$backendConfigPath"
Assert-LastExitCode 'terraform init'
& terraform $chdirArg validate -no-color
Assert-LastExitCode 'terraform validate'
Write-Boundary 'TERRAFORM_INIT' 'PASS'
Write-Boundary 'TERRAFORM_VALIDATE' 'PASS'

& terraform $chdirArg plan -input=false -no-color "-out=$planPath" -detailed-exitcode
$planExit = $LASTEXITCODE
if ($planExit -eq 0) {
    throw 'Terraform returned no changes. A first A2 plan is expected to contain the isolated DEV resources.'
}
if ($planExit -ne 2) {
    throw "terraform plan failed with exit code $planExit."
}

$planJsonRaw = & terraform $chdirArg show -json $planPath
Assert-LastExitCode 'terraform show -json'
$planJsonRaw | Set-Content -Path $planJsonPath -Encoding utf8NoBOM
$plan = $planJsonRaw | ConvertFrom-Json -Depth 100

$expectedCreateAddresses = @(
    'random_string.suffix',
    'random_password.postgresql',
    'azurerm_resource_group.soa_intelligence',
    'azurerm_virtual_network.soa_intelligence',
    'azurerm_subnet.postgresql',
    'azurerm_private_dns_zone.postgresql',
    'azurerm_private_dns_zone_virtual_network_link.postgresql',
    'azurerm_postgresql_flexible_server.soa_intelligence',
    'azurerm_postgresql_flexible_server_database.soa_intelligence',
    'azurerm_postgresql_flexible_server_configuration.extensions'
) | Sort-Object

$managedChanges = @($plan.resource_changes | Where-Object { $_.mode -eq 'managed' })
$createAddresses = @()
$updateAddresses = @()
$deleteAddresses = @()
$replaceAddresses = @()
$otherAddresses = @()

foreach ($change in $managedChanges) {
    $actions = @($change.change.actions)
    $signature = $actions -join ','
    switch ($signature) {
        'create' { $createAddresses += [string]$change.address }
        'update' { $updateAddresses += [string]$change.address }
        'delete' { $deleteAddresses += [string]$change.address }
        'delete,create' { $replaceAddresses += [string]$change.address }
        'create,delete' { $replaceAddresses += [string]$change.address }
        'no-op' { }
        'read' { }
        default { $otherAddresses += "${($change.address)}[$signature]" }
    }
}

$createAddresses = @($createAddresses | Sort-Object)
$missingCreates = @($expectedCreateAddresses | Where-Object { $_ -notin $createAddresses })
$unexpectedCreates = @($createAddresses | Where-Object { $_ -notin $expectedCreateAddresses })

$exactActionSet = (
    $createAddresses.Count -eq $expectedCreateAddresses.Count -and
    $updateAddresses.Count -eq 0 -and
    $deleteAddresses.Count -eq 0 -and
    $replaceAddresses.Count -eq 0 -and
    $otherAddresses.Count -eq 0 -and
    $missingCreates.Count -eq 0 -and
    $unexpectedCreates.Count -eq 0
)

$planSha = Get-Sha256 -Path $planPath
$planJsonSha = Get-Sha256 -Path $planJsonPath

$receipt = [ordered]@{
    receipt_type = 'SOA_INTELLIGENCE_A2_GOVERNED_LIVE_PLAN'
    generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    config_commit = $localHead
    branch = $ExpectedBranch
    state_key = $StateKey
    create_count = $createAddresses.Count
    update_count = $updateAddresses.Count
    delete_count = $deleteAddresses.Count
    replace_count = $replaceAddresses.Count
    exact_action_set = $(if ($exactActionSet) { 'PASS' } else { 'FAIL' })
    expected_create_addresses = $expectedCreateAddresses
    actual_create_addresses = $createAddresses
    missing_create_addresses = $missingCreates
    unexpected_create_addresses = $unexpectedCreates
    update_addresses = $updateAddresses
    delete_addresses = $deleteAddresses
    replace_addresses = $replaceAddresses
    other_addresses = $otherAddresses
    plan_path = $planPath
    plan_sha256 = $planSha
    plan_json_path = $planJsonPath
    plan_json_sha256 = $planJsonSha
    artifact_root = $artifactRoot
    artifact_acl = 'OPERATOR_ONLY'
    terraform_apply = $false
    azure_resource_mutation = $false
    terraform_state_locking = 'ENABLED'
    human_authorization_required_for_apply = $true
}
$receipt | ConvertTo-Json -Depth 20 | Set-Content -Path $receiptPath -Encoding utf8NoBOM
$receiptSha = Get-Sha256 -Path $receiptPath

Write-Host ''
Write-Host '=== SOA INTELLIGENCE A2 · GOVERNED LIVE PLAN RECEIPT ==='
Write-Boundary 'CONFIG_COMMIT' $localHead
Write-Boundary 'STATE_KEY' $StateKey
Write-Boundary 'CREATE_COUNT' ([string]$createAddresses.Count)
Write-Boundary 'UPDATE_COUNT' ([string]$updateAddresses.Count)
Write-Boundary 'DELETE_COUNT' ([string]$deleteAddresses.Count)
Write-Boundary 'REPLACE_COUNT' ([string]$replaceAddresses.Count)
Write-Boundary 'EXACT_ACTION_SET' $(if ($exactActionSet) { 'PASS' } else { 'FAIL' })
Write-Boundary 'PLAN_PATH' $planPath
Write-Boundary 'PLAN_SHA256' $planSha
Write-Boundary 'PLAN_JSON_SHA256' $planJsonSha
Write-Boundary 'ARTIFACT_ROOT' $artifactRoot
Write-Boundary 'ARTIFACT_ACL' 'OPERATOR_ONLY'
Write-Boundary 'SANITIZED_RECEIPT' $receiptPath
Write-Boundary 'RECEIPT_SHA256' $receiptSha
Write-Boundary 'TERRAFORM_APPLY' 'false'
Write-Boundary 'AZURE_RESOURCE_MUTATION' 'false'
Write-Boundary 'HUMAN_AUTHORIZATION_REQUIRED' 'true'

if (-not $exactActionSet) {
    throw 'A2 live plan does not match the frozen exact action set. Apply is prohibited.'
}

Write-Boundary 'A2_LIVE_PLAN_GATE' 'PASS'
Write-Boundary 'DONE' 'true'
