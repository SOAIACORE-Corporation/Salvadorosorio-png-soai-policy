[CmdletBinding()]
param(
    [string]$MigrationWorkerImage = 'ghcr.io/soaiacore-corporation/soaiacore-worker@sha256:85f27c3640edf98ec391feaa24fd3bd1ddb678ee1bf12220fa5a11f82bb07b2d',
    [Parameter(Mandatory)][string]$GhcrUsername,
    [SecureString]$GhcrToken,
    [string]$SubscriptionId = '108eb4dd-25b3-4a7f-8d5e-4ec4389c3f0d',
    [string]$ExpectedBranch = 'main',
    [string]$StateResourceGroup = 'rg-soaiacore-tfstate-34utxi',
    [string]$StateStorageAccount = 'stsoaiacoretf34utxi',
    [string]$StateContainer = 'tfstate',
    [string]$StateKey = 'soa-intelligence/dev/postgres.tfstate',
    [string]$ExpectedResourceGroup = 'rg-soa-intelligence-dev',
    [string]$ExpectedJobName = 'caj-soaintelligence-dev-migrate'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$CanonicalMigrationWorkerImage = 'ghcr.io/soaiacore-corporation/soaiacore-worker@sha256:85f27c3640edf98ec391feaa24fd3bd1ddb678ee1bf12220fa5a11f82bb07b2d'
$PreviousMigrationWorkerImage = 'ghcr.io/soaiacore-corporation/soaiacore-worker@sha256:0effb661f90cb59d57c152f88eb4b4ddc3a9d8958b3286ed3949a29b6af8abdc'
$PreviousCommand = @('python', '-m', 'soaiacore_worker', 'a2-bootstrap')
$ExpectedCommand = @('/app/.venv/bin/python', '-m', 'soaiacore_worker', 'a2-bootstrap')
$ExpectedUpdateAddress = 'azurerm_container_app_job.a2_migration'

if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'This governed A2 Worker Job update plan runner requires PowerShell 7 or newer.'
}
if (-not $IsWindows) {
    throw 'This governed runner must execute from the authorized Windows operator workstation.'
}
if ($MigrationWorkerImage -notmatch '@sha256:[0-9a-f]{64}$') {
    throw 'MigrationWorkerImage must be immutable and pinned by sha256 digest.'
}
if ($MigrationWorkerImage -ne $CanonicalMigrationWorkerImage) {
    throw "MigrationWorkerImage differs from the canonical security-gated Worker published from main. Expected '$CanonicalMigrationWorkerImage'."
}
if ($null -eq $GhcrToken) {
    $GhcrToken = Read-Host 'GHCR read-only token' -AsSecureString
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
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Assert-ExactSet {
    param(
        [Parameter(Mandatory)][string[]]$Expected,
        [Parameter(Mandatory)][string[]]$Actual,
        [Parameter(Mandatory)][string]$GateName
    )
    $reference = @($Expected | Sort-Object)
    $difference = @($Actual | Sort-Object)
    $delta = @(Compare-Object -ReferenceObject $reference -DifferenceObject $difference)
    if ($delta.Count -ne 0) {
        throw "$GateName failed: $($delta | Out-String)"
    }
}

$repoRoot = (& git rev-parse --show-toplevel).Trim()
Assert-LastExitCode 'git rev-parse --show-toplevel'
Set-Location $repoRoot

$currentBranch = (& git branch --show-current).Trim()
Assert-LastExitCode 'git branch --show-current'
if ($currentBranch -ne $ExpectedBranch) {
    throw "Expected branch '$ExpectedBranch' but current branch is '$currentBranch'."
}

$dirty = @(& git status --porcelain)
Assert-LastExitCode 'git status --porcelain'
if ($dirty.Count -ne 0) {
    throw "Working tree is dirty: $($dirty -join ' | ')"
}

& git fetch origin $ExpectedBranch --quiet
Assert-LastExitCode 'git fetch expected branch'
$localHead = (& git rev-parse HEAD).Trim()
Assert-LastExitCode 'git rev-parse HEAD'
$remoteHead = (& git rev-parse "origin/$ExpectedBranch").Trim()
Assert-LastExitCode 'git rev-parse remote branch'
if ($localHead -ne $remoteHead) {
    throw "Local HEAD '$localHead' differs from remote '$remoteHead'."
}

Write-Boundary 'CONFIG_COMMIT' $localHead
Write-Boundary 'BRANCH_SYNC' 'PASS'
Write-Boundary 'CANONICAL_SOURCE_BRANCH' $ExpectedBranch
Write-Boundary 'CANONICAL_WORKER_IMAGE' $CanonicalMigrationWorkerImage

$terraformInfo = (& terraform version -json) | ConvertFrom-Json
Assert-LastExitCode 'terraform version -json'
$terraformVersion = [version]$terraformInfo.terraform_version
if ($terraformVersion.Major -ne 1 -or $terraformVersion.Minor -ne 15) {
    throw "Terraform 1.15.x required; found $terraformVersion."
}
Write-Boundary 'TERRAFORM_VERSION_GATE' 'PASS'

$account = (& az account show --only-show-errors --output json) | ConvertFrom-Json
Assert-LastExitCode 'az account show'
if ([string]$account.id -ne $SubscriptionId) {
    throw 'Authenticated Azure subscription does not match governed A2 subscription.'
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
Assert-LastExitCode 'state container probe'
if ($containerExists -ne 'true') {
    throw 'Governed Terraform state container is not reachable.'
}

$stateBlobExists = (& az storage blob exists `
    --auth-mode login `
    --account-name $StateStorageAccount `
    --container-name $StateContainer `
    --name $StateKey `
    --query exists `
    --output tsv `
    --only-show-errors).Trim()
Assert-LastExitCode 'A2 state blob probe'
if ($stateBlobExists -ne 'true') {
    throw "Existing A2 state '$StateKey' was not found."
}
Write-Boundary 'A2_REMOTE_STATE_EXISTS' 'PASS'

$rgExists = (& az group exists --name $ExpectedResourceGroup --only-show-errors --output tsv).Trim()
Assert-LastExitCode 'A2 resource group probe'
if ($rgExists -ne 'true') {
    throw "Expected A2 resource group '$ExpectedResourceGroup' is absent."
}

$liveJobJson = & az containerapp job show `
    --name $ExpectedJobName `
    --resource-group $ExpectedResourceGroup `
    --subscription $SubscriptionId `
    --only-show-errors `
    --output json
Assert-LastExitCode 'live Container Apps Job read'
$liveJob = $liveJobJson | ConvertFrom-Json -Depth 100
$liveContainers = @($liveJob.properties.template.containers)
if ($liveContainers.Count -ne 1) {
    throw "Expected exactly one live Job container; found $($liveContainers.Count)."
}
$liveImage = [string]$liveContainers[0].image
$liveCommand = @($liveContainers[0].command | ForEach-Object { [string]$_ })
if ($liveImage -ne $PreviousMigrationWorkerImage) {
    throw "Live Job image drifted from the failed-bootstrap authority. Expected '$PreviousMigrationWorkerImage'; observed '$liveImage'."
}
if (($liveCommand -join [char]0) -ne ($PreviousCommand -join [char]0)) {
    throw "Live Job command drifted from the failed-bootstrap authority. Observed '$($liveCommand -join ' ')'."
}
Write-Boundary 'LIVE_JOB_PRE_UPDATE_IMAGE' $liveImage
Write-Boundary 'LIVE_JOB_PRE_UPDATE_COMMAND' ($liveCommand -join ' ')
Write-Boundary 'LIVE_JOB_PRECHECK' 'PASS'

$timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$artifactRoot = Join-Path $HOME ("SOAIACORE\controlled-a2-worker-job-update-plan\$timestamp")
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
"@ | Set-Content -LiteralPath $backendConfigPath -Encoding utf8NoBOM

$stackDir = Join-Path $repoRoot 'infra\azure\soa-intelligence-dev'
if (-not (Test-Path -LiteralPath $stackDir -PathType Container)) {
    throw "Terraform stack directory not found: $stackDir"
}

$planPath = Join-Path $evidenceDir 'soa-intelligence-a2-worker-job-update.tfplan'
$receiptPath = Join-Path $artifactRoot 'SOA_INTELLIGENCE_A2_WORKER_JOB_UPDATE_PLAN_RECEIPT.sanitized.json'
$tokenPlain = [System.Net.NetworkCredential]::new('', $GhcrToken).Password
$exactActionSet = $false
$planRetained = $false

try {
    $env:TF_IN_AUTOMATION = 'true'
    $env:TF_INPUT = 'false'
    $env:TF_VAR_subscription_id = $SubscriptionId
    $env:TF_VAR_migration_worker_image = $MigrationWorkerImage
    $env:TF_VAR_ghcr_username = $GhcrUsername
    $env:TF_VAR_ghcr_token = $tokenPlain
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

    $expectedState = @(
        'data.azurerm_client_config.current',
        'random_string.suffix',
        'random_password.postgresql',
        'azurerm_resource_group.soa_intelligence',
        'azurerm_virtual_network.soa_intelligence',
        'azurerm_subnet.postgresql',
        'azurerm_private_dns_zone.postgresql',
        'azurerm_private_dns_zone_virtual_network_link.postgresql',
        'azurerm_postgresql_flexible_server.soa_intelligence',
        'azurerm_postgresql_flexible_server_database.soa_intelligence',
        'azurerm_postgresql_flexible_server_configuration.extensions',
        'azurerm_subnet.container_apps',
        'azurerm_log_analytics_workspace.a2_migration',
        'azurerm_container_app_environment.a2_migration',
        'azurerm_container_app_job.a2_migration'
    )

    $stateAddresses = @(& terraform $chdirArg state list)
    Assert-LastExitCode 'terraform state list'
    Assert-ExactSet -Expected $expectedState -Actual $stateAddresses -GateName 'PRE_STATE_EXACT_SET'
    if ($stateAddresses.Count -ne 15) {
        throw "Expected exactly 15 A2 state addresses; found $($stateAddresses.Count)."
    }
    Write-Boundary 'PRE_STATE_ADDRESS_COUNT' ([string]$stateAddresses.Count)
    Write-Boundary 'PRE_STATE_EXACT_SET' 'PASS'

    & terraform $chdirArg plan -input=false -no-color "-out=$planPath" -detailed-exitcode
    $planExit = $LASTEXITCODE
    if ($planExit -eq 0) {
        throw 'Terraform returned no changes; the governed Worker Job update is expected.'
    }
    if ($planExit -ne 2) {
        throw "terraform plan failed with exit code $planExit."
    }

    # Parse only in memory. Never persist Terraform plan JSON because sensitive
    # registry credentials can appear even when marked sensitive.
    $planJsonRaw = & terraform $chdirArg show -json $planPath
    Assert-LastExitCode 'terraform show -json'
    $plan = $planJsonRaw | ConvertFrom-Json -Depth 100

    $managedChanges = @($plan.resource_changes | Where-Object { $_.mode -eq 'managed' })
    $createAddresses = @()
    $updateAddresses = @()
    $deleteAddresses = @()
    $replaceAddresses = @()
    $otherAddresses = @()

    foreach ($change in $managedChanges) {
        $signature = @($change.change.actions) -join ','
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
    $updateAddresses = @($updateAddresses | Sort-Object)
    $deleteAddresses = @($deleteAddresses | Sort-Object)
    $replaceAddresses = @($replaceAddresses | Sort-Object)

    $exactActionSet = (
        $createAddresses.Count -eq 0 -and
        $updateAddresses.Count -eq 1 -and
        $updateAddresses[0] -eq $ExpectedUpdateAddress -and
        $deleteAddresses.Count -eq 0 -and
        $replaceAddresses.Count -eq 0 -and
        $otherAddresses.Count -eq 0
    )

    if (-not $exactActionSet) {
        throw "A2 Worker Job update plan does not match exact 0-create/1-update/0-delete/0-replace action set. Creates=$($createAddresses -join ','); Updates=$($updateAddresses -join ','); Deletes=$($deleteAddresses -join ','); Replaces=$($replaceAddresses -join ','); Other=$($otherAddresses -join ',')."
    }

    $jobChange = @($managedChanges | Where-Object { [string]$_.address -eq $ExpectedUpdateAddress })
    if ($jobChange.Count -ne 1) {
        throw 'Expected exactly one Container Apps Job resource change.'
    }

    $beforeContainers = @($jobChange[0].change.before.template[0].container)
    $afterContainers = @($jobChange[0].change.after.template[0].container)
    if ($beforeContainers.Count -ne 1 -or $afterContainers.Count -ne 1) {
        throw 'Expected exactly one before/after container in the Job plan.'
    }

    $beforeImage = [string]$beforeContainers[0].image
    $afterImage = [string]$afterContainers[0].image
    $beforeCommand = @($beforeContainers[0].command | ForEach-Object { [string]$_ })
    $afterCommand = @($afterContainers[0].command | ForEach-Object { [string]$_ })

    if ($beforeImage -ne $PreviousMigrationWorkerImage) {
        throw "Plan before-image is not the failed-bootstrap Worker authority: '$beforeImage'."
    }
    if ($afterImage -ne $CanonicalMigrationWorkerImage) {
        throw "Plan after-image is not the canonical corrected Worker: '$afterImage'."
    }
    if (($beforeCommand -join [char]0) -ne ($PreviousCommand -join [char]0)) {
        throw "Plan before-command drifted: '$($beforeCommand -join ' ')'."
    }
    if (($afterCommand -join [char]0) -ne ($ExpectedCommand -join [char]0)) {
        throw "Plan after-command is not the corrected runtime command: '$($afterCommand -join ' ')'."
    }

    $planSha = Get-Sha256 -Path $planPath
    $receipt = [ordered]@{
        receipt_type = 'SOA_INTELLIGENCE_A2_WORKER_JOB_UPDATE_GOVERNED_PLAN'
        generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
        config_commit = $localHead
        branch = $ExpectedBranch
        state_key = $StateKey
        pre_state_address_count = $stateAddresses.Count
        canonical_worker_image = $CanonicalMigrationWorkerImage
        previous_worker_image = $PreviousMigrationWorkerImage
        expected_update_address = $ExpectedUpdateAddress
        create_count = $createAddresses.Count
        update_count = $updateAddresses.Count
        delete_count = $deleteAddresses.Count
        replace_count = $replaceAddresses.Count
        exact_action_set = 'PASS'
        update_addresses = $updateAddresses
        before_image = $beforeImage
        after_image = $afterImage
        before_command = $beforeCommand
        after_command = $afterCommand
        plan_path = $planPath
        plan_sha256 = $planSha
        plan_json_persisted = $false
        artifact_root = $artifactRoot
        artifact_acl = 'OPERATOR_ONLY'
        terraform_apply = $false
        azure_resource_mutation = $false
        database_mutation = $false
        job_start = $false
        iam_mutation = $false
        firewall_opened = $false
        postgresql_public = $false
        p0_mutation = $false
        human_authorization_required_for_apply = $true
        separate_human_authorization_required_for_job_start = $true
    }
    $receipt | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $receiptPath -Encoding utf8NoBOM
    $receiptSha = Get-Sha256 -Path $receiptPath
    $planRetained = $true

    Write-Host ''
    Write-Host '=== SOA INTELLIGENCE A2 · WORKER JOB UPDATE GOVERNED PLAN RECEIPT ==='
    Write-Boundary 'CONFIG_COMMIT' $localHead
    Write-Boundary 'STATE_KEY' $StateKey
    Write-Boundary 'PRE_STATE_ADDRESS_COUNT' ([string]$stateAddresses.Count)
    Write-Boundary 'PRE_STATE_EXACT_SET' 'PASS'
    Write-Boundary 'PREVIOUS_WORKER_IMAGE' $PreviousMigrationWorkerImage
    Write-Boundary 'CANONICAL_WORKER_IMAGE' $CanonicalMigrationWorkerImage
    Write-Boundary 'CREATE_COUNT' '0'
    Write-Boundary 'UPDATE_COUNT' '1'
    Write-Boundary 'DELETE_COUNT' '0'
    Write-Boundary 'REPLACE_COUNT' '0'
    Write-Boundary 'UPDATE_ADDRESS' $ExpectedUpdateAddress
    Write-Boundary 'BEFORE_COMMAND' ($beforeCommand -join ' ')
    Write-Boundary 'AFTER_COMMAND' ($afterCommand -join ' ')
    Write-Boundary 'EXACT_ACTION_SET' 'PASS'
    Write-Boundary 'PLAN_PATH' $planPath
    Write-Boundary 'PLAN_SHA256' $planSha
    Write-Boundary 'PLAN_JSON_PERSISTED' 'false'
    Write-Boundary 'ARTIFACT_ROOT' $artifactRoot
    Write-Boundary 'ARTIFACT_ACL' 'OPERATOR_ONLY'
    Write-Boundary 'SANITIZED_RECEIPT' $receiptPath
    Write-Boundary 'RECEIPT_SHA256' $receiptSha
    Write-Boundary 'TERRAFORM_APPLY' 'false'
    Write-Boundary 'AZURE_RESOURCE_MUTATION' 'false'
    Write-Boundary 'DATABASE_MUTATION' 'false'
    Write-Boundary 'JOB_START' 'false'
    Write-Boundary 'IAM_MUTATION' 'false'
    Write-Boundary 'FIREWALL_OPENED' 'false'
    Write-Boundary 'POSTGRESQL_PUBLIC' 'false'
    Write-Boundary 'P0_MUTATION' 'false'
    Write-Boundary 'HUMAN_AUTHORIZATION_REQUIRED' 'true'
    Write-Boundary 'SEPARATE_JOB_START_AUTHORIZATION_REQUIRED' 'true'
    Write-Boundary 'A2_WORKER_JOB_UPDATE_PLAN_GATE' 'PASS'
    Write-Boundary 'DONE' 'true'
}
finally {
    $tokenPlain = $null
    Remove-Item Env:TF_VAR_ghcr_token -ErrorAction SilentlyContinue
    Remove-Item Env:TF_VAR_ghcr_username -ErrorAction SilentlyContinue
    Remove-Item Env:TF_VAR_migration_worker_image -ErrorAction SilentlyContinue
    Remove-Item Env:TF_VAR_subscription_id -ErrorAction SilentlyContinue
    Remove-Item Env:ARM_SUBSCRIPTION_ID -ErrorAction SilentlyContinue
    Remove-Item Env:ARM_TENANT_ID -ErrorAction SilentlyContinue
    Remove-Item Env:ARM_USE_AZUREAD -ErrorAction SilentlyContinue
    Remove-Item Env:ARM_USE_CLI -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $backendConfigPath -Force -ErrorAction SilentlyContinue

    if (-not $planRetained -and (Test-Path -LiteralPath $planPath -PathType Leaf)) {
        Remove-Item -LiteralPath $planPath -Force -ErrorAction SilentlyContinue
    }
}
