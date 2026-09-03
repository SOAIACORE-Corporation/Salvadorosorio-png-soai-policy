[CmdletBinding()]
param(
    [ValidateSet('PlanOnly','ApplyReviewedPlan')]
    [string]$Mode = 'PlanOnly',

    [Parameter(Mandatory = $true)]
    [string]$BackendConfigPath,

    [Parameter(Mandatory = $true)]
    [string]$VarFilePath,

    [Parameter(Mandatory = $true)]
    [string]$BackendAuthorityReceiptPath,

    [string]$PlanFile,
    [string]$ExpectedPlanSha256,
    [string]$AdjudicationToken
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$ExpectedSubscriptionId = '108eb4dd-25b3-4a7f-8d5e-4ec4389c3f0d'
$ExpectedPilotResourceGroup = 'rg-soaiacore-p0-34utxi'
$ExpectedStateResourceGroup = 'rg-soaiacore-tfstate-34utxi'
$RequiredAdjudicationToken = 'APPLY_REVIEWED_P0_DESTROY_PLAN'
$TerraformDirectory = $PSScriptRoot

function Stop-Gate {
    param([string]$Code,[string]$Message)
    throw ("{0}: {1}" -f $Code,$Message)
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Stop-Gate 'STOP_TOOL_MISSING' ("Required command not found: {0}" -f $Name)
    }
}

function Resolve-ExistingFile {
    param([string]$Path,[string]$Label)
    if ([string]::IsNullOrWhiteSpace($Path)) {
        Stop-Gate 'STOP_FILE_REQUIRED' ("{0} path is required." -f $Label)
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Stop-Gate 'STOP_FILE_NOT_FOUND' ("{0} not found: {1}" -f $Label,$Path)
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Invoke-JsonCommand {
    param([string]$Command,[string[]]$Arguments,[string]$Label)
    $tmpOut = [System.IO.Path]::GetTempFileName()
    $tmpErr = [System.IO.Path]::GetTempFileName()
    try {
        & $Command @Arguments 1> $tmpOut 2> $tmpErr
        $exitCode = $LASTEXITCODE
        $stdout = [System.IO.File]::ReadAllText($tmpOut)
        $stderr = [System.IO.File]::ReadAllText($tmpErr)
        if ($exitCode -ne 0) {
            Stop-Gate 'STOP_COMMAND_FAILED' ("{0} failed ({1}): {2}" -f $Label,$exitCode,$stderr.Trim())
        }
        if ([string]::IsNullOrWhiteSpace($stdout)) { return $null }
        try { return ($stdout | ConvertFrom-Json) }
        catch { Stop-Gate 'STOP_JSON_PARSE' ("{0} did not return valid JSON." -f $Label) }
    }
    finally {
        Remove-Item $tmpOut,$tmpErr -Force -ErrorAction SilentlyContinue
    }
}

function Get-PropertyValue {
    param($Object,[string]$Name)
    if ($null -eq $Object) { return $null }
    $p = $Object.PSObject.Properties[$Name]
    if ($null -eq $p) { return $null }
    return $p.Value
}

function Assert-BackendAuthorityReceipt {
    param([string]$Path)
    $receipt = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    $remote = Get-PropertyValue $receipt 'remote_backend_initialized'
    $planSafe = Get-PropertyValue $receipt 'plan_no_destroy_verified'
    $reconciled = Get-PropertyValue $receipt 'config_state_reconciled'

    if ($remote -ne $true) {
        Stop-Gate 'STOP_BACKEND_AUTHORITY' 'Receipt does not prove remote_backend_initialized=true.'
    }
    if ($planSafe -ne $true) {
        Stop-Gate 'STOP_BACKEND_AUTHORITY' 'Receipt does not prove plan_no_destroy_verified=true.'
    }
    if ($reconciled -ne $true) {
        Stop-Gate 'STOP_BACKEND_AUTHORITY' 'Receipt does not prove config_state_reconciled=true.'
    }
    return $receipt
}

function Get-PlanActions {
    param($PlanJson)
    $rows = @()
    foreach ($rc in @($PlanJson.resource_changes)) {
        $actions = @($rc.change.actions)
        $rows += [pscustomobject]@{
            address = $rc.address
            mode = $rc.mode
            type = $rc.type
            name = $rc.name
            actions = $actions
        }
    }
    return $rows
}

function Assert-DestroyPlanShape {
    param([object[]]$ActionRows)
    $destructiveCount = 0
    foreach ($row in @($ActionRows)) {
        foreach ($action in @($row.actions)) {
            if ($action -eq 'create' -or $action -eq 'update') {
                Stop-Gate 'STOP_UNEXPECTED_PLAN_ACTION' ("Plan contains {0} for {1}." -f $action,$row.address)
            }
        }
        if (@($row.actions) -contains 'delete') { $destructiveCount++ }
    }
    if ($destructiveCount -lt 1) {
        Stop-Gate 'STOP_EMPTY_DESTROY_PLAN' 'Plan contains no delete actions.'
    }
    return $destructiveCount
}

Require-Command 'az'
Require-Command 'terraform'

$BackendConfigPath = Resolve-ExistingFile $BackendConfigPath 'BackendConfig'
$VarFilePath = Resolve-ExistingFile $VarFilePath 'VarFile'
$BackendAuthorityReceiptPath = Resolve-ExistingFile $BackendAuthorityReceiptPath 'BackendAuthorityReceipt'
$null = Assert-BackendAuthorityReceipt $BackendAuthorityReceiptPath

$account = Invoke-JsonCommand 'az' @('account','show','--only-show-errors','--output','json') 'Azure account precheck'
if ($account.id -ne $ExpectedSubscriptionId) {
    Stop-Gate 'STOP_SCOPE_MISMATCH' ("Subscription {0} != expected {1}." -f $account.id,$ExpectedSubscriptionId)
}
if ($account.state -ne 'Enabled') {
    Stop-Gate 'STOP_SUBSCRIPTION_DISABLED' ("Subscription state: {0}." -f $account.state)
}

$pilotRg = Invoke-JsonCommand 'az' @('group','show','--name',$ExpectedPilotResourceGroup,'--only-show-errors','--output','json') 'Pilot RG precheck'
if ($pilotRg.name -ne $ExpectedPilotResourceGroup) {
    Stop-Gate 'STOP_SCOPE_MISMATCH' 'Pilot resource group mismatch.'
}
$stateRg = Invoke-JsonCommand 'az' @('group','show','--name',$ExpectedStateResourceGroup,'--only-show-errors','--output','json') 'State RG precheck'
if ($stateRg.name -ne $ExpectedStateResourceGroup) {
    Stop-Gate 'STOP_SCOPE_MISMATCH' 'State resource group mismatch.'
}

Push-Location $TerraformDirectory
try {
    & terraform init -reconfigure -input=false ("-backend-config={0}" -f $BackendConfigPath)
    if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_TERRAFORM_INIT' 'terraform init failed.' }

    $stateAddresses = @(& terraform state list)
    if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_STATE_READ' 'terraform state list failed.' }
    if ($stateAddresses.Count -lt 1) { Stop-Gate 'STOP_EMPTY_STATE' 'Remote state contains no resource addresses.' }

    $azureInventory = Invoke-JsonCommand 'az' @('resource','list','--resource-group',$ExpectedPilotResourceGroup,'--only-show-errors','--output','json') 'Pilot inventory'

    if ($Mode -eq 'PlanOnly') {
        $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
        $outputDir = Join-Path ([System.IO.Path]::GetTempPath()) ("soaiacore-p0-teardown-{0}" -f $stamp)
        New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

        $resolvedOutput = (Resolve-Path -LiteralPath $outputDir).Path
        $resolvedRepo = (Resolve-Path -LiteralPath $TerraformDirectory).Path
        if ($resolvedOutput.StartsWith($resolvedRepo,[System.StringComparison]::OrdinalIgnoreCase)) {
            Stop-Gate 'STOP_OUTPUT_INSIDE_REPO' 'Destroy plan output must remain outside the Git working tree.'
        }

        $planPath = Join-Path $outputDir 'p0-destroy.tfplan'
        $planJsonPath = Join-Path $outputDir 'p0-destroy.tfplan.json'
        $receiptPath = Join-Path $outputDir 'p0-destroy-plan-receipt.sanitized.json'

        & terraform plan -destroy -input=false -out=$planPath ("-var-file={0}" -f $VarFilePath)
        if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_DESTROY_PLAN_FAILED' 'terraform plan -destroy failed. No apply attempted.' }

        & terraform show -json $planPath | Set-Content -LiteralPath $planJsonPath -Encoding UTF8
        if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_PLAN_JSON_FAILED' 'terraform show -json failed.' }

        $planJson = Get-Content -LiteralPath $planJsonPath -Raw | ConvertFrom-Json
        $actionRows = @(Get-PlanActions $planJson)
        $deleteCount = Assert-DestroyPlanShape $actionRows
        $planHash = (Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash.ToLower()

        $inventoryRows = @()
        foreach ($r in @($azureInventory)) {
            $inventoryRows += [pscustomobject]@{ name=$r.name; type=$r.type; id=$r.id; location=$r.location }
        }

        $sanitized = [ordered]@{
            schema = 'SOAIACORE_P0_DESTROY_PLAN_RECEIPT_V1'
            mode = 'PLAN_ONLY'
            created_utc = (Get-Date).ToUniversalTime().ToString('o')
            subscription_id = $ExpectedSubscriptionId
            pilot_resource_group = $ExpectedPilotResourceGroup
            preserved_state_resource_group = $ExpectedStateResourceGroup
            backend_authority_receipt = $BackendAuthorityReceiptPath
            state_address_count = $stateAddresses.Count
            state_addresses = $stateAddresses
            azure_inventory_count = @($inventoryRows).Count
            azure_inventory = $inventoryRows
            plan_file = $planPath
            plan_json_file = $planJsonPath
            plan_sha256 = $planHash
            delete_action_count = $deleteCount
            plan_actions = $actionRows
            apply_executed = $false
            state_backend_preserved = $true
            ghcr_credential_revocation_required_at_final_teardown = $true
            human_adjudication_required = $true
        }
        $sanitized | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $receiptPath -Encoding UTF8

        Write-Host '=== P0 GOVERNED TEARDOWN PLAN ==='
        Write-Host 'MODE=PLAN_ONLY'
        Write-Host ("STATE_ADDRESS_COUNT={0}" -f $stateAddresses.Count)
        Write-Host ("AZURE_INVENTORY_COUNT={0}" -f @($inventoryRows).Count)
        Write-Host ("DELETE_ACTION_COUNT={0}" -f $deleteCount)
        Write-Host ("PLAN_SHA256={0}" -f $planHash)
        Write-Host ("PLAN_FILE={0}" -f $planPath)
        Write-Host ("PLAN_JSON_FILE={0}" -f $planJsonPath)
        Write-Host ("SANITIZED_RECEIPT={0}" -f $receiptPath)
        Write-Host 'APPLY_EXECUTED=false'
        Write-Host 'HUMAN_ADJUDICATION_REQUIRED=true'
        Write-Host 'DONE=true'
        exit 0
    }

    if ($Mode -eq 'ApplyReviewedPlan') {
        $PlanFile = Resolve-ExistingFile $PlanFile 'PlanFile'
        if ([string]::IsNullOrWhiteSpace($ExpectedPlanSha256)) {
            Stop-Gate 'STOP_PLAN_HASH_REQUIRED' 'ExpectedPlanSha256 is required for ApplyReviewedPlan.'
        }
        if ($AdjudicationToken -ne $RequiredAdjudicationToken) {
            Stop-Gate 'STOP_HUMAN_ADJUDICATION' 'Exact adjudication token not supplied.'
        }

        $actualHash = (Get-FileHash -LiteralPath $PlanFile -Algorithm SHA256).Hash.ToLower()
        if ($actualHash -ne $ExpectedPlanSha256.ToLower()) {
            Stop-Gate 'STOP_PLAN_HASH_MISMATCH' ("Plan SHA256 {0} != reviewed {1}." -f $actualHash,$ExpectedPlanSha256.ToLower())
        }

        $tmpJson = Join-Path ([System.IO.Path]::GetTempPath()) ("soaiacore-reviewed-destroy-{0}.json" -f ([guid]::NewGuid().ToString('N')))
        try {
            & terraform show -json $PlanFile | Set-Content -LiteralPath $tmpJson -Encoding UTF8
            if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_PLAN_JSON_FAILED' 'Cannot inspect reviewed plan.' }
            $planJson = Get-Content -LiteralPath $tmpJson -Raw | ConvertFrom-Json
            $actionRows = @(Get-PlanActions $planJson)
            $deleteCount = Assert-DestroyPlanShape $actionRows
        }
        finally {
            Remove-Item $tmpJson -Force -ErrorAction SilentlyContinue
        }

        Write-Host '=== DESTRUCTIVE GATE ARMED ==='
        Write-Host ("SUBSCRIPTION={0}" -f $ExpectedSubscriptionId)
        Write-Host ("RESOURCE_GROUP={0}" -f $ExpectedPilotResourceGroup)
        Write-Host ("PLAN_SHA256={0}" -f $actualHash)
        Write-Host ("DELETE_ACTION_COUNT={0}" -f $deleteCount)
        Write-Host 'STATE_BACKEND_SCOPE=OUTSIDE_PILOT_RG'
        Write-Host 'APPLYING_EXACT_REVIEWED_PLAN=true'

        & terraform apply -input=false $PlanFile
        if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_APPLY_FAILED' 'Exact reviewed destroy plan did not apply successfully.' }

        $existsText = (& az group exists --name $ExpectedPilotResourceGroup --only-show-errors --output tsv).Trim()
        if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_POSTCHECK_FAILED' 'Could not verify pilot RG after apply.' }
        $rgAbsent = ($existsText -eq 'false')

        $finalReceipt = [ordered]@{
            schema = 'SOAIACORE_P0_TEARDOWN_RECEIPT_V1'
            mode = 'APPLY_REVIEWED_PLAN'
            completed_utc = (Get-Date).ToUniversalTime().ToString('o')
            subscription_id = $ExpectedSubscriptionId
            pilot_resource_group = $ExpectedPilotResourceGroup
            reviewed_plan_sha256 = $actualHash
            delete_action_count = $deleteCount
            apply_executed = $true
            pilot_resource_group_absent = $rgAbsent
            state_backend_preserved = $true
            ghcr_credential_revocation_required = $true
            ghcr_credential_revocation_verified = $false
        }
        $finalPath = Join-Path ([System.IO.Path]::GetTempPath()) ("soaiacore-p0-teardown-final-{0}.sanitized.json" -f (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))
        $finalReceipt | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $finalPath -Encoding UTF8

        if (-not $rgAbsent) {
            Stop-Gate 'STOP_RESIDUAL_RESOURCES' ("Pilot RG still exists. Receipt: {0}" -f $finalPath)
        }

        Write-Host '=== P0 GOVERNED TEARDOWN RESULT ==='
        Write-Host 'APPLY_EXECUTED=true'
        Write-Host 'PILOT_RESOURCE_GROUP_ABSENT=true'
        Write-Host 'STATE_BACKEND_PRESERVED=true'
        Write-Host 'GHCR_CREDENTIAL_REVOCATION_REQUIRED=true'
        Write-Host ("SANITIZED_RECEIPT={0}" -f $finalPath)
        Write-Host 'DONE=true'
    }
}
finally {
    Pop-Location
}
