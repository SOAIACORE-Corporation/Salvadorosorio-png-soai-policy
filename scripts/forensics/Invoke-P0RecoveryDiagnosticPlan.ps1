[CmdletBinding()]
param(
    [switch]$SelfTest
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$ExpectedSubscriptionId = '108eb4dd-25b3-4a7f-8d5e-4ec4389c3f0d'
$ExpectedConfigCommit = '4b47fe25bb89c5733783920b1f8497c7dfadbb92'
$RepositoryUrl = 'https://github.com/SOAIACORE-Corporation/Salvadorosorio-png-soai-policy.git'
$PilotResourceGroup = 'rg-soaiacore-p0-34utxi'
$StateResourceGroup = 'rg-soaiacore-tfstate-34utxi'
$StateStorageAccount = 'stsoaiacoretf34utxi'
$StateContainer = 'tfstate'
$StateKey = 'soaiacore/controlled-pilot/terraform.tfstate'
$EvidenceStorageAccount = 'stsoaiacorep034utxi'
$KeyVaultName = 'kv-soaiacore-p0-34utxi'
$WebAppName = 'ca-soaiacore-p0-web-34utxi'
$CoreImage = 'ghcr.io/soaiacore-corporation/soaiacore-core@sha256:e6564cad60afa7f7e1828c193c3512c7f1b0ce53aed26459e0a61b8ac33fb467'
$WebImage = 'ghcr.io/soaiacore-corporation/soaiacore-web@sha256:da26fd8bcf6cb2a4c242d380a28c682b19c6f094f0a898258a727ef558fa6c58'
$WorkerImage = 'ghcr.io/soaiacore-corporation/soaiacore-worker@sha256:971dc02fd1ba2306cd6e1d4864e8d7de0d447169256f7d89071bc5c94ccde9a1'

function Stop-Gate {
    param([string]$Code, [string]$Message)
    throw ("{0}: {1}" -f $Code, $Message)
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Stop-Gate 'STOP_TOOL_MISSING' ("Required command not found: {0}" -f $Name)
    }
}

function Invoke-NativeText {
    param(
        [string]$Command,
        [string[]]$Arguments,
        [string]$Label
    )

    $output = @(& $Command @Arguments 2>&1)
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        Stop-Gate 'STOP_COMMAND_FAILED' ("{0} failed with exit code {1}." -f $Label, $code)
    }
    return ($output -join [Environment]::NewLine).Trim()
}

function Invoke-AzJson {
    param([string[]]$Arguments, [string]$Label)
    $text = Invoke-NativeText 'az' ($Arguments + @('--only-show-errors', '--output', 'json')) $Label
    if ([string]::IsNullOrWhiteSpace($text)) {
        Stop-Gate 'STOP_EMPTY_AZURE_RESPONSE' ("{0} returned no data." -f $Label)
    }
    try { return ($text | ConvertFrom-Json -Depth 100) }
    catch { Stop-Gate 'STOP_JSON_PARSE' ("{0} did not return valid JSON." -f $Label) }
}

function Invoke-AzSecretValue {
    param([string]$SecretName)
    $value = Invoke-NativeText 'az' @(
        'keyvault', 'secret', 'show',
        '--vault-name', $KeyVaultName,
        '--name', $SecretName,
        '--query', 'value',
        '--output', 'tsv',
        '--only-show-errors'
    ) ("Key Vault secret read: {0}" -f $SecretName)
    if ([string]::IsNullOrWhiteSpace($value)) {
        Stop-Gate 'STOP_SECRET_EMPTY' ("Secret {0} returned an empty value." -f $SecretName)
    }
    return $value
}

function Get-StateShowText {
    param([string]$TerraformDirectory, [string]$Address)
    return Invoke-NativeText 'terraform' @(
        ("-chdir={0}" -f $TerraformDirectory),
        'state', 'show', '-no-color', $Address
    ) ("Terraform state show {0}" -f $Address)
}

function Get-RegexValue {
    param([string]$Text, [string]$Pattern, [string]$Label)
    $match = [regex]::Match($Text, $Pattern, [System.Text.RegularExpressions.RegexOptions]::Singleline)
    if (-not $match.Success -or $match.Groups.Count -lt 2) {
        Stop-Gate 'STOP_EVIDENCE_PARSE' ("Could not resolve {0}." -f $Label)
    }
    return $match.Groups[1].Value
}

function Get-PlanRows {
    param($PlanJson)
    $rows = @()
    foreach ($change in @($PlanJson.resource_changes)) {
        $actions = @($change.change.actions)
        $rows += [pscustomobject]@{
            address = $change.address
            mode    = $change.mode
            type    = $change.type
            name    = $change.name
            actions = $actions
        }
    }
    return $rows
}

function Get-PlanSummary {
    param([object[]]$Rows)
    $create = 0
    $update = 0
    $delete = 0
    $replace = 0
    $read = 0
    $noOp = 0

    foreach ($row in @($Rows)) {
        $actions = @($row.actions)
        if (($actions -contains 'delete') -and ($actions -contains 'create')) { $replace++ }
        elseif ($actions -contains 'delete') { $delete++ }
        elseif ($actions -contains 'create') { $create++ }
        elseif ($actions -contains 'update') { $update++ }
        elseif ($actions -contains 'read') { $read++ }
        elseif ($actions -contains 'no-op') { $noOp++ }
    }

    return [pscustomobject]@{
        create  = $create
        update  = $update
        delete  = $delete
        replace = $replace
        read    = $read
        no_op   = $noOp
    }
}

if ($SelfTest) {
    $fixture = [pscustomobject]@{
        resource_changes = @(
            [pscustomobject]@{ address='a.keep'; mode='managed'; type='x'; name='keep'; change=[pscustomobject]@{ actions=@('no-op') } },
            [pscustomobject]@{ address='a.update'; mode='managed'; type='x'; name='update'; change=[pscustomobject]@{ actions=@('update') } },
            [pscustomobject]@{ address='a.replace'; mode='managed'; type='x'; name='replace'; change=[pscustomobject]@{ actions=@('delete','create') } }
        )
    }
    $rows = @(Get-PlanRows $fixture)
    $summary = Get-PlanSummary $rows
    if ($rows.Count -ne 3 -or $summary.no_op -ne 1 -or $summary.update -ne 1 -or $summary.replace -ne 1 -or $summary.delete -ne 0) {
        throw 'SELFTEST_PLAN_CLASSIFICATION_FAILED'
    }
    $branch = Get-RegexValue 'subject = "repo:o/r:ref:refs/heads/security/p0-identity-2026-08-27"' 'subject\s*=\s*"repo:[^"]+:ref:refs/heads/([^"]+)"' 'GitHub branch fixture'
    if ($branch -ne 'security/p0-identity-2026-08-27') {
        throw 'SELFTEST_BRANCH_PARSE_FAILED'
    }
    Write-Host 'SELFTEST=PASS'
    Write-Host 'AZURE_CALLED=false'
    Write-Host 'TERRAFORM_CALLED=false'
    Write-Host 'MUTATION=false'
    exit 0
}

Require-Command 'git'
Require-Command 'az'
Require-Command 'terraform'

$account = Invoke-AzJson @('account', 'show') 'Azure account precheck'
if ($account.id -ne $ExpectedSubscriptionId) {
    Stop-Gate 'STOP_SCOPE_MISMATCH' 'Azure subscription does not match the authorized P0 subscription.'
}
if ($account.state -ne 'Enabled') {
    Stop-Gate 'STOP_SUBSCRIPTION_DISABLED' ("Subscription state is {0}." -f $account.state)
}

$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$workRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("soaiacore-p0-recovery-plan-{0}" -f $stamp)
$repoDir = Join-Path $workRoot 'repo'
$outputDir = Join-Path $workRoot 'evidence'
New-Item -ItemType Directory -Path $workRoot, $outputDir -Force | Out-Null

$planPath = Join-Path $outputDir 'p0-recovery-diagnostic.tfplan'
$planLog = Join-Path $outputDir 'p0-recovery-diagnostic.plan.log'
$receiptPath = Join-Path $HOME ("SOAIACORE_38_RECOVERY_PLAN_RECEIPT_{0}.sanitized.json" -f $stamp)
$backendPath = Join-Path $workRoot 'backend.production.hcl'

try {
    Invoke-NativeText 'git' @('clone', '--quiet', '--no-checkout', $RepositoryUrl, $repoDir) 'Git clone' | Out-Null
    Invoke-NativeText 'git' @('-C', $repoDir, 'checkout', '--quiet', '--detach', $ExpectedConfigCommit) 'Git checkout pinned recovery config' | Out-Null
    $actualCommit = Invoke-NativeText 'git' @('-C', $repoDir, 'rev-parse', 'HEAD') 'Git HEAD verification'
    if ($actualCommit -ne $ExpectedConfigCommit) {
        Stop-Gate 'STOP_COMMIT_MISMATCH' 'Recovery checkout does not match the reviewed configuration commit.'
    }

    $terraformDirectory = Join-Path $repoDir 'infra\azure\p0'
    if (-not (Test-Path -LiteralPath $terraformDirectory -PathType Container)) {
        Stop-Gate 'STOP_REPO_LAYOUT' 'Expected Terraform directory is missing from the pinned commit.'
    }

    @"
resource_group_name  = "$StateResourceGroup"
storage_account_name = "$StateStorageAccount"
container_name       = "$StateContainer"
key                  = "$StateKey"
use_azuread_auth     = true
"@ | Set-Content -LiteralPath $backendPath -Encoding utf8

    Invoke-NativeText 'terraform' @(
        ("-chdir={0}" -f $terraformDirectory),
        'init', '-reconfigure', '-input=false', '-no-color',
        ("-backend-config={0}" -f $backendPath)
    ) 'Terraform remote backend initialization' | Out-Null

    $stateAddressesText = Invoke-NativeText 'terraform' @(("-chdir={0}" -f $terraformDirectory), 'state', 'list') 'Terraform state list'
    $stateAddresses = @($stateAddressesText -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($stateAddresses.Count -ne 46) {
        Stop-Gate 'STOP_STATE_COUNT_MISMATCH' ("Expected 46 state addresses, observed {0}." -f $stateAddresses.Count)
    }

    $ficText = Get-StateShowText $terraformDirectory 'azurerm_federated_identity_credential.github_branch'
    $githubBranch = Get-RegexValue $ficText 'subject\s*=\s*"repo:[^"]+:ref:refs/heads/([^"]+)"' 'current federated GitHub branch'

    $rg = Invoke-AzJson @('group', 'show', '--name', $PilotResourceGroup) 'Pilot resource group read'
    $expiresAt = [string]$rg.tags.expires_at
    if ([string]::IsNullOrWhiteSpace($expiresAt)) {
        Stop-Gate 'STOP_RUNTIME_INPUT_MISSING' 'Pilot expires_at tag is missing.'
    }

    $storage = Invoke-AzJson @('storage', 'account', 'show', '--resource-group', $PilotResourceGroup, '--name', $EvidenceStorageAccount) 'Evidence storage read'
    $allowedIps = @($storage.networkRuleSet.ipRules | Where-Object { $_.action -eq 'Allow' } | ForEach-Object { $_.ipAddressOrRange })
    if ($allowedIps.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$allowedIps[0])) {
        Stop-Gate 'STOP_RUNTIME_INPUT_AMBIGUOUS' ("Expected one allowed operator IP rule, observed {0}." -f $allowedIps.Count)
    }
    $operatorIp = [string]$allowedIps[0]

    $web = Invoke-AzJson @('containerapp', 'show', '--resource-group', $PilotResourceGroup, '--name', $WebAppName) 'Web Container App read'
    $registries = @($web.properties.configuration.registries | Where-Object { $_.server -eq 'ghcr.io' })
    if ($registries.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$registries[0].username)) {
        Stop-Gate 'STOP_RUNTIME_INPUT_AMBIGUOUS' 'Could not resolve exactly one GHCR registry username from Web.'
    }
    $ghcrUsername = [string]$registries[0].username

    $containers = @($web.properties.template.containers)
    if ($containers.Count -lt 1) {
        Stop-Gate 'STOP_RUNTIME_INPUT_MISSING' 'Web has no runtime container definition.'
    }
    $oidcRows = @($containers[0].env | Where-Object { $_.name -eq 'SOAIACORE_OIDC_CLIENT_ID' })
    if ($oidcRows.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$oidcRows[0].value)) {
        Stop-Gate 'STOP_RUNTIME_INPUT_AMBIGUOUS' 'Could not resolve exactly one OIDC client ID from Web runtime configuration.'
    }
    $oidcClientId = [string]$oidcRows[0].value

    # Sensitive values are read into process memory only, never written to the receipt or terminal.
    $ghcrToken = Invoke-AzSecretValue 'ghcr-pull-token'
    $oidcClientSecret = Invoke-AzSecretValue 'oidc-client-secret'

    $env:TF_VAR_subscription_id = $ExpectedSubscriptionId
    $env:TF_VAR_expires_at = $expiresAt
    $env:TF_VAR_core_image = $CoreImage
    $env:TF_VAR_web_image = $WebImage
    $env:TF_VAR_worker_image = $WorkerImage
    $env:TF_VAR_ghcr_username = $ghcrUsername
    $env:TF_VAR_ghcr_token = $ghcrToken
    $env:TF_VAR_operator_ip_address = $operatorIp
    $env:TF_VAR_oidc_client_id = $oidcClientId
    $env:TF_VAR_oidc_client_secret = $oidcClientSecret
    $env:TF_VAR_github_branch = $githubBranch

    $nativePreferenceDefined = Test-Path Variable:PSNativeCommandUseErrorActionPreference
    if ($nativePreferenceDefined) {
        $savedNativePreference = $PSNativeCommandUseErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $false
    }

    try {
        & terraform ("-chdir={0}" -f $terraformDirectory) plan -input=false -detailed-exitcode -no-color ("-out={0}" -f $planPath) *> $planLog
        $planExitCode = $LASTEXITCODE
    }
    finally {
        if ($nativePreferenceDefined) {
            $PSNativeCommandUseErrorActionPreference = $savedNativePreference
        }
    }

    if ($planExitCode -eq 1) {
        Stop-Gate 'STOP_TERRAFORM_PLAN_FAILED' ("Terraform plan failed. Diagnostic log retained at {0}." -f $planLog)
    }
    if ($planExitCode -ne 0 -and $planExitCode -ne 2) {
        Stop-Gate 'STOP_TERRAFORM_PLAN_EXIT' ("Unexpected Terraform plan exit code {0}." -f $planExitCode)
    }

    $planJsonText = Invoke-NativeText 'terraform' @(("-chdir={0}" -f $terraformDirectory), 'show', '-json', $planPath) 'Terraform plan JSON read'
    try { $planJson = $planJsonText | ConvertFrom-Json -Depth 100 }
    catch { Stop-Gate 'STOP_PLAN_JSON_PARSE' 'Terraform saved plan could not be parsed.' }
    $planJsonText = $null

    $rows = @(Get-PlanRows $planJson)
    $summary = Get-PlanSummary $rows
    $changedRows = @($rows | Where-Object { @($_.actions) -notcontains 'no-op' })
    $destructiveRows = @($rows | Where-Object { @($_.actions) -contains 'delete' })

    if ($summary.delete -gt 0 -or $summary.replace -gt 0) {
        $gate = 'STOP_DELETE_OR_REPLACE'
    }
    elseif ($planExitCode -eq 0) {
        $gate = 'NO_CHANGES'
    }
    else {
        $gate = 'NON_DESTRUCTIVE_REVIEW_REQUIRED'
    }

    $planHash = (Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $receipt = [ordered]@{
        schema = 'SOAIACORE_38_RECOVERY_DIAGNOSTIC_PLAN_V1'
        recorded_utc = (Get-Date).ToUniversalTime().ToString('o')
        config_commit = $ExpectedConfigCommit
        subscription_scope_verified = $true
        remote_backend_initialized = $true
        state_address_count = $stateAddresses.Count
        runtime_inputs_resolved_without_committing_secrets = $true
        key_vault_secret_values_output = $false
        terraform_plan_executed = $true
        terraform_apply_executed = $false
        mutation = $false
        plan_exit_code = $planExitCode
        plan_sha256 = $planHash
        plan_gate = $gate
        action_counts = [ordered]@{
            create = $summary.create
            update = $summary.update
            delete = $summary.delete
            replace = $summary.replace
            read = $summary.read
            no_op = $summary.no_op
        }
        changed_resources = @($changedRows | ForEach-Object {
            [ordered]@{ address=$_.address; mode=$_.mode; type=$_.type; name=$_.name; actions=@($_.actions) }
        })
        destructive_resources = @($destructiveRows | ForEach-Object {
            [ordered]@{ address=$_.address; actions=@($_.actions) }
        })
        raw_plan_json_persisted = $false
        diagnostic_plan_file = $planPath
        diagnostic_plan_log = $planLog
        human_adjudication_required_before_any_apply = $true
    }
    $receipt | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $receiptPath -Encoding utf8
    $receiptHash = (Get-FileHash -LiteralPath $receiptPath -Algorithm SHA256).Hash.ToLowerInvariant()

    Write-Host ''
    Write-Host '=== SOAIACORE #38 RECOVERY DIAGNOSTIC PLAN ==='
    Write-Host ("CONFIG_COMMIT={0}" -f $ExpectedConfigCommit)
    Write-Host ("STATE_ADDRESS_COUNT={0}" -f $stateAddresses.Count)
    Write-Host ("PLAN_EXIT_CODE={0}" -f $planExitCode)
    Write-Host ("CREATE_COUNT={0}" -f $summary.create)
    Write-Host ("UPDATE_COUNT={0}" -f $summary.update)
    Write-Host ("DELETE_COUNT={0}" -f $summary.delete)
    Write-Host ("REPLACE_COUNT={0}" -f $summary.replace)
    Write-Host ("READ_COUNT={0}" -f $summary.read)
    Write-Host ("NO_OP_COUNT={0}" -f $summary.no_op)
    Write-Host ("PLAN_GATE={0}" -f $gate)
    Write-Host ("PLAN_SHA256={0}" -f $planHash)
    Write-Host ("SANITIZED_RECEIPT={0}" -f $receiptPath)
    Write-Host ("RECEIPT_SHA256={0}" -f $receiptHash)
    Write-Host 'SECRET_VALUES_OUTPUT=false'
    Write-Host 'RAW_PLAN_JSON_PERSISTED=false'
    Write-Host 'APPLY_EXECUTED=false'
    Write-Host 'MUTATION=false'
    Write-Host 'DONE=true'
}
finally {
    Remove-Item Env:TF_VAR_ghcr_token -ErrorAction SilentlyContinue
    Remove-Item Env:TF_VAR_oidc_client_secret -ErrorAction SilentlyContinue
    $ghcrToken = $null
    $oidcClientSecret = $null
}
