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

    [string]$ArtifactRoot,
    [string]$PlanFile,
    [string]$ExpectedPlanSha256,
    [string]$AdjudicationToken,
    [string]$AdjudicationAuthority,
    [string]$AuthorizationEvidenceRef
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$ExpectedSubscriptionId = '108eb4dd-25b3-4a7f-8d5e-4ec4389c3f0d'
$ExpectedPilotResourceGroup = 'rg-soaiacore-p0-34utxi'
$ExpectedStateResourceGroup = 'rg-soaiacore-tfstate-34utxi'
$RequiredAdjudicationToken = 'APPLY_REVIEWED_P0_DESTROY_PLAN'
$RequiredAdjudicationAuthority = 'Salvador Osorio Ayala'
$TerraformDirectory = $PSScriptRoot
$RunningOnWindows = ($env:OS -eq 'Windows_NT')

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

function Test-VerifiedTrue {
    param($Value)
    if ($Value -eq $true) { return $true }
    if ($null -eq $Value) { return $false }
    $text = ([string]$Value).Trim().ToUpperInvariant()
    return ($text -eq 'TRUE' -or $text -eq 'PASS' -or $text -eq 'VERIFIED')
}

function Assert-BackendAuthorityReceipt {
    param([string]$Path)
    $receipt = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    $remote = Get-PropertyValue $receipt 'remote_backend_initialized'
    $planSafe = Get-PropertyValue $receipt 'plan_no_destroy_verified'
    $reconciled = Get-PropertyValue $receipt 'config_state_reconciled'

    if (-not (Test-VerifiedTrue $remote)) {
        Stop-Gate 'STOP_BACKEND_AUTHORITY' 'Receipt does not prove remote_backend_initialized=true/PASS.'
    }
    if (-not (Test-VerifiedTrue $planSafe)) {
        Stop-Gate 'STOP_BACKEND_AUTHORITY' 'Receipt does not prove plan_no_destroy_verified=true/PASS.'
    }
    if (-not (Test-VerifiedTrue $reconciled)) {
        Stop-Gate 'STOP_BACKEND_AUTHORITY' 'Receipt does not prove config_state_reconciled=true/PASS.'
    }
    return $receipt
}

function Protect-OperatorDirectory {
    param([string]$Path)

    if ($RunningOnWindows) {
        try {
            $sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
            $acl = New-Object System.Security.AccessControl.DirectorySecurity
            $acl.SetOwner($sid)
            $acl.SetAccessRuleProtection($true,$false)
            $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
                $sid,
                'FullControl',
                'ContainerInherit,ObjectInherit',
                'None',
                'Allow'
            )
            $acl.AddAccessRule($rule)
            Set-Acl -LiteralPath $Path -AclObject $acl
        }
        catch {
            Stop-Gate 'STOP_ARTIFACT_PERMISSIONS' ("Could not restrict artifact directory ACL: {0}" -f $_.Exception.Message)
        }
        return
    }

    Require-Command 'chmod'
    & chmod 700 $Path
    if ($LASTEXITCODE -ne 0) {
        Stop-Gate 'STOP_ARTIFACT_PERMISSIONS' 'chmod 700 failed for artifact directory.'
    }
}

function Protect-OperatorFile {
    param([string]$Path)

    if ($RunningOnWindows) {
        # Files are created only after the parent directory has an explicit,
        # inheritance-protected current-user-only ACL.
        return
    }

    Require-Command 'chmod'
    & chmod 600 $Path
    if ($LASTEXITCODE -ne 0) {
        Stop-Gate 'STOP_ARTIFACT_PERMISSIONS' ("chmod 600 failed for artifact file: {0}" -f $Path)
    }
}

function New-SecureArtifactDirectory {
    param([string]$RequestedRoot)

    if ([string]::IsNullOrWhiteSpace($RequestedRoot)) {
        if ([string]::IsNullOrWhiteSpace([string]$HOME)) {
            Stop-Gate 'STOP_ARTIFACT_ROOT' 'HOME is unavailable; provide -ArtifactRoot explicitly.'
        }
        $soaRoot = Join-Path $HOME 'SOAIACORE'
        $RequestedRoot = Join-Path $soaRoot 'p0-teardown-evidence'
    }

    if (-not (Test-Path -LiteralPath $RequestedRoot -PathType Container)) {
        New-Item -ItemType Directory -Path $RequestedRoot -Force | Out-Null
    }

    $resolvedRoot = (Resolve-Path -LiteralPath $RequestedRoot).Path
    $resolvedRepo = (Resolve-Path -LiteralPath $TerraformDirectory).Path
    if ($resolvedRoot.StartsWith($resolvedRepo,[System.StringComparison]::OrdinalIgnoreCase)) {
        Stop-Gate 'STOP_OUTPUT_INSIDE_REPO' 'ArtifactRoot must remain outside the Git working tree.'
    }

    $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    $outputDir = Join-Path $resolvedRoot ("soaiacore-p0-teardown-{0}" -f $stamp)
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    Protect-OperatorDirectory $outputDir
    return (Resolve-Path -LiteralPath $outputDir).Path
}

function Get-PlanActions {
    param($PlanJson)
    $rows = @()
    foreach ($rc in @($PlanJson.resource_changes)) {
        $actions = @($rc.change.actions)
        $before = Get-PropertyValue $rc.change 'before'
        $rows += [pscustomobject]@{
            address = [string]$rc.address
            mode = [string]$rc.mode
            type = [string]$rc.type
            name = [string]$rc.name
            provider_name = [string](Get-PropertyValue $rc 'provider_name')
            actions = $actions
            prior_id = [string](Get-PropertyValue $before 'id')
            prior_resource_group_name = [string](Get-PropertyValue $before 'resource_group_name')
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

function Assert-DestroyPlanScope {
    param($PlanJson,[object[]]$ActionRows)

    $variables = Get-PropertyValue $PlanJson 'variables'
    $subscriptionVariable = Get-PropertyValue $variables 'subscription_id'
    $planSubscriptionId = [string](Get-PropertyValue $subscriptionVariable 'value')

    if ([string]::IsNullOrWhiteSpace($planSubscriptionId)) {
        Stop-Gate 'STOP_PLAN_SCOPE_MISMATCH' 'Saved plan does not expose subscription_id for scope verification.'
    }
    if (-not $planSubscriptionId.Equals($ExpectedSubscriptionId,[System.StringComparison]::OrdinalIgnoreCase)) {
        Stop-Gate 'STOP_PLAN_SCOPE_MISMATCH' ("Plan subscription {0} != expected {1}." -f $planSubscriptionId,$ExpectedSubscriptionId)
    }

    $pilotPrefix = "/subscriptions/$ExpectedSubscriptionId/resourceGroups/$ExpectedPilotResourceGroup"
    $statePrefix = "/subscriptions/$ExpectedSubscriptionId/resourceGroups/$ExpectedStateResourceGroup"
    $azureDeleteCount = 0

    foreach ($row in @($ActionRows)) {
        if (-not (@($row.actions) -contains 'delete')) { continue }

        $provider = [string]$row.provider_name
        if (-not $provider.EndsWith('/azurerm',[System.StringComparison]::OrdinalIgnoreCase)) {
            continue
        }

        $azureDeleteCount++
        $priorId = ([string]$row.prior_id).Trim().TrimEnd('/')
        if ([string]::IsNullOrWhiteSpace($priorId)) {
            Stop-Gate 'STOP_PLAN_SCOPE_MISMATCH' ("Azure delete {0} has no prior ARM id." -f $row.address)
        }

        if ($priorId.Equals($statePrefix,[System.StringComparison]::OrdinalIgnoreCase) -or
            $priorId.StartsWith(($statePrefix + '/'),[System.StringComparison]::OrdinalIgnoreCase)) {
            Stop-Gate 'STOP_STATE_BACKEND_DELETE' ("Plan attempts to delete state-backend scope via {0}." -f $row.address)
        }

        $insidePilot = $priorId.Equals($pilotPrefix,[System.StringComparison]::OrdinalIgnoreCase) -or
            $priorId.StartsWith(($pilotPrefix + '/'),[System.StringComparison]::OrdinalIgnoreCase)
        if (-not $insidePilot) {
            Stop-Gate 'STOP_PLAN_SCOPE_MISMATCH' ("Azure delete {0} is outside pinned P0 scope." -f $row.address)
        }

        $priorRg = ([string]$row.prior_resource_group_name).Trim()
        if (-not [string]::IsNullOrWhiteSpace($priorRg) -and
            -not $priorRg.Equals($ExpectedPilotResourceGroup,[System.StringComparison]::OrdinalIgnoreCase)) {
            Stop-Gate 'STOP_PLAN_SCOPE_MISMATCH' ("Azure delete {0} declares resource_group_name={1}." -f $row.address,$priorRg)
        }
    }

    if ($azureDeleteCount -lt 1) {
        Stop-Gate 'STOP_PLAN_SCOPE_MISMATCH' 'Destroy plan contains no AzureRM delete actions inside the pinned pilot scope.'
    }

    return $azureDeleteCount
}

function Assert-AzureInventoryScope {
    param([object[]]$Inventory)
    $pilotPrefix = "/subscriptions/$ExpectedSubscriptionId/resourceGroups/$ExpectedPilotResourceGroup/"
    foreach ($resource in @($Inventory)) {
        $id = [string](Get-PropertyValue $resource 'id')
        if ([string]::IsNullOrWhiteSpace($id) -or
            -not $id.StartsWith($pilotPrefix,[System.StringComparison]::OrdinalIgnoreCase)) {
            Stop-Gate 'STOP_INVENTORY_SCOPE_MISMATCH' 'Azure inventory contains an item outside the exact pinned P0 resource group.'
        }
    }
}

function Get-SanitizedActionRows {
    param([object[]]$ActionRows)
    $safe = @()
    foreach ($row in @($ActionRows)) {
        $safe += [pscustomobject]@{
            address = $row.address
            mode = $row.mode
            type = $row.type
            name = $row.name
            provider_name = $row.provider_name
            actions = @($row.actions)
        }
    }
    return $safe
}

Require-Command 'az'
Require-Command 'terraform'

$BackendConfigPath = Resolve-ExistingFile $BackendConfigPath 'BackendConfig'
$VarFilePath = Resolve-ExistingFile $VarFilePath 'VarFile'
$BackendAuthorityReceiptPath = Resolve-ExistingFile $BackendAuthorityReceiptPath 'BackendAuthorityReceipt'
$null = Assert-BackendAuthorityReceipt $BackendAuthorityReceiptPath

$account = Invoke-JsonCommand 'az' @('account','show','--only-show-errors','--output','json') 'Azure account precheck'
if (-not ([string]$account.id).Equals($ExpectedSubscriptionId,[System.StringComparison]::OrdinalIgnoreCase)) {
    Stop-Gate 'STOP_SCOPE_MISMATCH' ("Subscription {0} != expected {1}." -f $account.id,$ExpectedSubscriptionId)
}
if ($account.state -ne 'Enabled') {
    Stop-Gate 'STOP_SUBSCRIPTION_DISABLED' ("Subscription state: {0}." -f $account.state)
}

$pilotRg = Invoke-JsonCommand 'az' @('group','show','--name',$ExpectedPilotResourceGroup,'--only-show-errors','--output','json') 'Pilot RG precheck'
if (-not ([string]$pilotRg.name).Equals($ExpectedPilotResourceGroup,[System.StringComparison]::OrdinalIgnoreCase)) {
    Stop-Gate 'STOP_SCOPE_MISMATCH' 'Pilot resource group mismatch.'
}
$stateRg = Invoke-JsonCommand 'az' @('group','show','--name',$ExpectedStateResourceGroup,'--only-show-errors','--output','json') 'State RG precheck'
if (-not ([string]$stateRg.name).Equals($ExpectedStateResourceGroup,[System.StringComparison]::OrdinalIgnoreCase)) {
    Stop-Gate 'STOP_SCOPE_MISMATCH' 'State RG precheck mismatch.'
}

Push-Location $TerraformDirectory
try {
    & terraform init -reconfigure -input=false ("-backend-config={0}" -f $BackendConfigPath)
    if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_TERRAFORM_INIT' 'terraform init failed.' }

    $stateAddresses = @(& terraform state list)
    if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_STATE_READ' 'terraform state list failed.' }
    if ($stateAddresses.Count -lt 1) { Stop-Gate 'STOP_EMPTY_STATE' 'Remote state contains no resource addresses.' }

    $azureInventory = @(Invoke-JsonCommand 'az' @('resource','list','--resource-group',$ExpectedPilotResourceGroup,'--only-show-errors','--output','json') 'Pilot inventory')
    Assert-AzureInventoryScope $azureInventory

    if ($Mode -eq 'PlanOnly') {
        $outputDir = New-SecureArtifactDirectory $ArtifactRoot

        $planPath = Join-Path $outputDir 'p0-destroy.tfplan'
        $planJsonPath = Join-Path $outputDir 'p0-destroy.tfplan.json'
        $receiptPath = Join-Path $outputDir 'p0-destroy-plan-receipt.sanitized.json'

        & terraform plan -destroy -input=false -out=$planPath ("-var-file={0}" -f $VarFilePath)
        if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_DESTROY_PLAN_FAILED' 'terraform plan -destroy failed. No apply attempted.' }
        Protect-OperatorFile $planPath

        $planJsonText = (& terraform show -json $planPath | Out-String)
        if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_PLAN_JSON_FAILED' 'terraform show -json failed.' }
        [System.IO.File]::WriteAllText($planJsonPath,$planJsonText,(New-Object System.Text.UTF8Encoding($false)))
        Protect-OperatorFile $planJsonPath

        $planJson = $planJsonText | ConvertFrom-Json
        $actionRows = @(Get-PlanActions $planJson)
        $deleteCount = Assert-DestroyPlanShape $actionRows
        $azureDeleteCount = Assert-DestroyPlanScope $planJson $actionRows
        $planHash = (Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash.ToLower()

        $inventoryRows = @()
        foreach ($r in @($azureInventory)) {
            $inventoryRows += [pscustomobject]@{ name=$r.name; type=$r.type; id=$r.id; location=$r.location }
        }

        $sanitized = [ordered]@{
            schema = 'SOAIACORE_P0_DESTROY_PLAN_RECEIPT_V2'
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
            scoped_azurerm_delete_count = $azureDeleteCount
            plan_actions = @(Get-SanitizedActionRows $actionRows)
            plan_scope_verified = $true
            artifact_directory_owner_only = $true
            apply_executed = $false
            state_backend_preserved = $true
            ghcr_credential_revocation_required_at_final_teardown = $true
            adjudication_authority_required = $RequiredAdjudicationAuthority
            adjudication_decision_required = $true
        }
        [System.IO.File]::WriteAllText($receiptPath,($sanitized | ConvertTo-Json -Depth 20),(New-Object System.Text.UTF8Encoding($false)))
        Protect-OperatorFile $receiptPath

        Write-Host '=== P0 GOVERNED TEARDOWN PLAN ==='
        Write-Host 'MODE=PLAN_ONLY'
        Write-Host ("STATE_ADDRESS_COUNT={0}" -f $stateAddresses.Count)
        Write-Host ("AZURE_INVENTORY_COUNT={0}" -f @($inventoryRows).Count)
        Write-Host ("DELETE_ACTION_COUNT={0}" -f $deleteCount)
        Write-Host ("SCOPED_AZURERM_DELETE_COUNT={0}" -f $azureDeleteCount)
        Write-Host 'PLAN_SCOPE_VERIFIED=true'
        Write-Host 'ARTIFACT_DIRECTORY_OWNER_ONLY=true'
        Write-Host ("PLAN_SHA256={0}" -f $planHash)
        Write-Host ("PLAN_FILE={0}" -f $planPath)
        Write-Host ("PLAN_JSON_FILE={0}" -f $planJsonPath)
        Write-Host ("SANITIZED_RECEIPT={0}" -f $receiptPath)
        Write-Host 'APPLY_EXECUTED=false'
        Write-Host ("ADJUDICATION_AUTHORITY_REQUIRED={0}" -f $RequiredAdjudicationAuthority)
        Write-Host 'ADJUDICATION_DECISION_REQUIRED=true'
        Write-Host 'DONE=true'
        exit 0
    }

    if ($Mode -eq 'ApplyReviewedPlan') {
        $PlanFile = Resolve-ExistingFile $PlanFile 'PlanFile'
        if ([string]::IsNullOrWhiteSpace($ExpectedPlanSha256)) {
            Stop-Gate 'STOP_PLAN_HASH_REQUIRED' 'ExpectedPlanSha256 is required for ApplyReviewedPlan.'
        }
        if ($AdjudicationToken -ne $RequiredAdjudicationToken) {
            Stop-Gate 'STOP_ADJUDICATION_AUTHORITY' 'Exact adjudication token not supplied.'
        }
        if ([string]::IsNullOrWhiteSpace($AdjudicationAuthority) -or
            -not $AdjudicationAuthority.Equals($RequiredAdjudicationAuthority,[System.StringComparison]::Ordinal)) {
            Stop-Gate 'STOP_ADJUDICATION_AUTHORITY' ("Adjudication authority must be exactly: {0}." -f $RequiredAdjudicationAuthority)
        }
        if ([string]::IsNullOrWhiteSpace($AuthorizationEvidenceRef)) {
            Stop-Gate 'STOP_ADJUDICATION_EVIDENCE' 'AuthorizationEvidenceRef is required for ApplyReviewedPlan.'
        }

        $actualHash = (Get-FileHash -LiteralPath $PlanFile -Algorithm SHA256).Hash.ToLower()
        if ($actualHash -ne $ExpectedPlanSha256.ToLower()) {
            Stop-Gate 'STOP_PLAN_HASH_MISMATCH' ("Plan SHA256 {0} != reviewed {1}." -f $actualHash,$ExpectedPlanSha256.ToLower())
        }

        $planJsonText = (& terraform show -json $PlanFile | Out-String)
        if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_PLAN_JSON_FAILED' 'Cannot inspect reviewed plan.' }
        $planJson = $planJsonText | ConvertFrom-Json
        $actionRows = @(Get-PlanActions $planJson)
        $deleteCount = Assert-DestroyPlanShape $actionRows
        $azureDeleteCount = Assert-DestroyPlanScope $planJson $actionRows

        Write-Host '=== DESTRUCTIVE GATE ARMED ==='
        Write-Host ("SUBSCRIPTION={0}" -f $ExpectedSubscriptionId)
        Write-Host ("RESOURCE_GROUP={0}" -f $ExpectedPilotResourceGroup)
        Write-Host ("PLAN_SHA256={0}" -f $actualHash)
        Write-Host ("DELETE_ACTION_COUNT={0}" -f $deleteCount)
        Write-Host ("SCOPED_AZURERM_DELETE_COUNT={0}" -f $azureDeleteCount)
        Write-Host 'PLAN_SCOPE_VERIFIED=true'
        Write-Host ("ADJUDICATION_AUTHORITY={0}" -f $AdjudicationAuthority)
        Write-Host ("AUTHORIZATION_EVIDENCE_REF={0}" -f $AuthorizationEvidenceRef)
        Write-Host 'STATE_BACKEND_SCOPE=OUTSIDE_PILOT_RG'
        Write-Host 'APPLYING_EXACT_REVIEWED_PLAN=true'

        & terraform apply -input=false $PlanFile
        if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_APPLY_FAILED' 'Exact reviewed destroy plan did not apply successfully.' }

        $existsText = (& az group exists --name $ExpectedPilotResourceGroup --only-show-errors --output tsv).Trim()
        if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_POSTCHECK_FAILED' 'Could not verify pilot RG after apply.' }
        $rgAbsent = ($existsText -eq 'false')

        $finalDir = New-SecureArtifactDirectory $ArtifactRoot
        $finalPath = Join-Path $finalDir 'p0-teardown-final.sanitized.json'
        $finalReceipt = [ordered]@{
            schema = 'SOAIACORE_P0_TEARDOWN_RECEIPT_V2'
            mode = 'APPLY_REVIEWED_PLAN'
            completed_utc = (Get-Date).ToUniversalTime().ToString('o')
            subscription_id = $ExpectedSubscriptionId
            pilot_resource_group = $ExpectedPilotResourceGroup
            reviewed_plan_sha256 = $actualHash
            delete_action_count = $deleteCount
            scoped_azurerm_delete_count = $azureDeleteCount
            plan_scope_verified = $true
            adjudication_authority = $AdjudicationAuthority
            authorization_evidence_ref = $AuthorizationEvidenceRef
            apply_executed = $true
            pilot_resource_group_absent = $rgAbsent
            state_backend_preserved = $true
            ghcr_credential_revocation_required = $true
            ghcr_credential_revocation_verified = $false
        }
        [System.IO.File]::WriteAllText($finalPath,($finalReceipt | ConvertTo-Json -Depth 10),(New-Object System.Text.UTF8Encoding($false)))
        Protect-OperatorFile $finalPath

        if (-not $rgAbsent) {
            Stop-Gate 'STOP_RESIDUAL_RESOURCES' ("Pilot RG still exists. Receipt: {0}" -f $finalPath)
        }

        Write-Host '=== P0 GOVERNED TEARDOWN RESULT ==='
        Write-Host 'APPLY_EXECUTED=true'
        Write-Host 'PILOT_RESOURCE_GROUP_ABSENT=true'
        Write-Host 'STATE_BACKEND_PRESERVED=true'
        Write-Host 'GHCR_CREDENTIAL_REVOCATION_REQUIRED=true'
        Write-Host ("ADJUDICATION_AUTHORITY={0}" -f $AdjudicationAuthority)
        Write-Host ("SANITIZED_RECEIPT={0}" -f $finalPath)
        Write-Host 'DONE=true'
    }
}
finally {
    Pop-Location
}
