[CmdletBinding()]
param(
    [switch]$SelfTest,
    [string]$PlanPath,
    [string]$ArtifactRoot,
    [ValidateRange(300, 1800)]
    [int]$TimeoutSeconds = 900
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
if (Test-Path Variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$ExpectedSubscriptionId = '108eb4dd-25b3-4a7f-8d5e-4ec4389c3f0d'
$ExpectedConfigCommit = '685ca1d13238949e7254d452b0f11fb23777855c'
$AuthorizedPlanSha256 = '1bf195f49410216b029d82b2af527916858cbb53479ea7b711ecddb35c8bebf8'
$AuthorizationMessageId = '1a07569ff6a72fb7'
$ExpectedStateBefore = 46
$ExpectedStateAfter = 56

$ExpectedActions = [ordered]@{
    'azurerm_container_app.core'                                      = 'update'
    'azurerm_container_app.web'                                       = 'update'
    'azurerm_container_app_job.worker'                                = 'update'
    'azurerm_monitor_metric_alert.worker_failed'                      = 'update'
    'azurerm_role_assignment.core_ghcr_secret_reader'                 = 'create'
    'azurerm_role_assignment.core_internal_auth_secret_reader'       = 'create'
    'azurerm_role_assignment.core_postgresql_secret_reader'          = 'create'
    'azurerm_role_assignment.web_ghcr_secret_reader'                  = 'create'
    'azurerm_role_assignment.web_internal_auth_secret_reader'        = 'create'
    'azurerm_role_assignment.web_oidc_secret_reader'                  = 'create'
    'azurerm_role_assignment.worker_ghcr_secret_reader'               = 'create'
    'azurerm_role_assignment.worker_postgresql_secret_reader'         = 'create'
    'azurerm_role_assignment.workload_key_vault_secrets_user'         = 'delete'
    'azurerm_user_assigned_identity.core_secrets'                     = 'create'
    'azurerm_user_assigned_identity.web_secrets'                      = 'create'
    'azurerm_user_assigned_identity.worker_secrets'                   = 'create'
}

$ExpectedPostApplyAddresses = @(
    'azurerm_role_assignment.core_ghcr_secret_reader'
    'azurerm_role_assignment.core_internal_auth_secret_reader'
    'azurerm_role_assignment.core_postgresql_secret_reader'
    'azurerm_role_assignment.web_ghcr_secret_reader'
    'azurerm_role_assignment.web_internal_auth_secret_reader'
    'azurerm_role_assignment.web_oidc_secret_reader'
    'azurerm_role_assignment.worker_ghcr_secret_reader'
    'azurerm_role_assignment.worker_postgresql_secret_reader'
    'azurerm_user_assigned_identity.core_secrets'
    'azurerm_user_assigned_identity.web_secrets'
    'azurerm_user_assigned_identity.worker_secrets'
)

function Stop-Gate {
    param([string]$Code, [string]$Message)
    throw ("{0}: {1}" -f $Code, $Message)
}

function Require-Command {
    param([string]$Name)
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        Stop-Gate 'STOP_TOOL_MISSING' ("Required command not found: {0}" -f $Name)
    }
    return $command.Source
}

function Assert-NoReparseAncestors {
    param([string]$Path)

    $cursor = [System.IO.Path]::GetFullPath($Path)
    while (-not [string]::IsNullOrWhiteSpace($cursor)) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                Stop-Gate 'STOP_REPARSE_POINT_PRESENT' ("Reparse point rejected: {0}" -f $cursor)
            }
        }
        $parent = [System.IO.Directory]::GetParent($cursor)
        if ($null -eq $parent) { break }
        $cursor = $parent.FullName
    }
}

function Assert-OperatorOnlyAcl {
    param([string]$Path)

    if (-not $IsWindows) {
        Stop-Gate 'STOP_UNSUPPORTED_PLATFORM' 'Authorized apply is restricted to Windows PowerShell 7.'
    }

    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $acl = Get-Acl -LiteralPath $Path
    $unexpectedRules = @(
        $acl.Access | Where-Object {
            $_.IsInherited -or
            [string]$_.IdentityReference -ne $identity -or
            $_.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow
        }
    )
    $fullControlRules = @(
        $acl.Access | Where-Object {
            -not $_.IsInherited -and
            [string]$_.IdentityReference -eq $identity -and
            $_.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow -and
            ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::FullControl)
        }
    )
    if ($unexpectedRules.Count -ne 0 -or $fullControlRules.Count -lt 1) {
        Stop-Gate 'STOP_ARTIFACT_ACL_VERIFY_FAILED' 'Artifact ACL is not exclusive to the current operator.'
    }
}

function Test-ExactActionSet {
    param([object[]]$ChangedResources)

    $rows = @($ChangedResources)
    if ($rows.Count -ne $ExpectedActions.Count) {
        Stop-Gate 'STOP_ACTION_SET_COUNT_MISMATCH' (
            "Expected {0} changed addresses, observed {1}." -f $ExpectedActions.Count, $rows.Count
        )
    }

    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($row in $rows) {
        $address = [string]$row.address
        $actions = @($row.change.actions)
        if (-not $ExpectedActions.Contains($address)) {
            Stop-Gate 'STOP_UNEXPECTED_PLAN_ADDRESS' ("Unexpected changed address: {0}" -f $address)
        }
        if ($actions.Count -ne 1 -or [string]$actions[0] -ne [string]$ExpectedActions[$address]) {
            Stop-Gate 'STOP_UNEXPECTED_PLAN_ACTION' (
                "Unexpected action for {0}: {1}" -f $address, ($actions -join ',')
            )
        }
        if (-not $seen.Add($address)) {
            Stop-Gate 'STOP_DUPLICATE_PLAN_ADDRESS' ("Duplicate changed address: {0}" -f $address)
        }
    }

    foreach ($address in $ExpectedActions.Keys) {
        if (-not $seen.Contains([string]$address)) {
            Stop-Gate 'STOP_MISSING_PLAN_ADDRESS' ("Expected changed address is missing: {0}" -f $address)
        }
    }
}

function Invoke-TerraformApplyWithTimeout {
    param(
        [string]$TerraformPath,
        [string]$TerraformDirectory,
        [string]$SavedPlanPath,
        [string]$ApplyLogPath,
        [int]$ProcessTimeoutSeconds
    )

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $TerraformPath
    $psi.WorkingDirectory = $TerraformDirectory
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    foreach ($argument in @('apply','-input=false','-auto-approve','-no-color',$SavedPlanPath)) {
        [void]$psi.ArgumentList.Add($argument)
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $psi
    $started = $false
    $durationNoticeEmitted = $false
    try {
        if (-not $process.Start()) {
            Stop-Gate 'STOP_APPLY_PROCESS_START' 'Terraform apply process could not start.'
        }
        $started = $true
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $timer = [System.Diagnostics.Stopwatch]::StartNew()

        while (-not $process.HasExited) {
            if ($timer.Elapsed.TotalSeconds -ge $ProcessTimeoutSeconds) {
                $slice = 30000
            }
            else {
                $remaining = [int][Math]::Max(1, (($ProcessTimeoutSeconds * 1000) - $timer.ElapsedMilliseconds))
                $slice = [int][Math]::Min(30000, $remaining)
            }
            if ($process.WaitForExit($slice)) { break }
            Write-Host (
                'PROCESS_HEARTBEAT=AUTHORIZED_APPLY|ELAPSED_SECONDS={0}|TIMEOUT_SECONDS={1}' -f
                ([int][Math]::Floor($timer.Elapsed.TotalSeconds)),
                $ProcessTimeoutSeconds
            )
            if (-not $durationNoticeEmitted -and $timer.Elapsed.TotalSeconds -ge $ProcessTimeoutSeconds) {
                $durationNoticeEmitted = $true
                Write-Host (
                    'EXPECTED_DURATION_EXCEEDED=AUTHORIZED_APPLY|ELAPSED_SECONDS={0}|ACTION=CONTINUE_WITHOUT_TERMINATION' -f
                    ([int][Math]::Floor($timer.Elapsed.TotalSeconds))
                )
            }
        }
        $timer.Stop()

        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        [System.IO.File]::WriteAllText(
            $ApplyLogPath,
            ($stdout + [Environment]::NewLine + $stderr),
            [System.Text.UTF8Encoding]::new($false)
        )
        return $process.ExitCode
    }
    finally {
        if ($started -and -not $process.HasExited) {
            try { $process.Kill($true) } catch {}
            try { [void]$process.WaitForExit(30000) } catch {}
        }
        $process.Dispose()
    }
}

if ($SelfTest) {
    $fixture = @(
        $ExpectedActions.Keys | ForEach-Object {
            [pscustomobject]@{
                address = [string]$_
                change = [pscustomobject]@{ actions = @([string]$ExpectedActions[$_]) }
            }
        }
    )
    Test-ExactActionSet -ChangedResources $fixture
    if ($ExpectedActions.Count -ne 16) { throw 'SELFTEST_ACTION_COUNT_FAILED' }
    if ($ExpectedPostApplyAddresses.Count -ne 11) { throw 'SELFTEST_POST_APPLY_COUNT_FAILED' }
    if ($AuthorizedPlanSha256 -notmatch '^[0-9a-f]{64}$') { throw 'SELFTEST_PLAN_SHA_FAILED' }
    Write-Host 'SELFTEST=PASS'
    Write-Host 'AUTHORIZED_PLAN_PIN=PASS'
    Write-Host 'EXPECTED_ACTION_SET=PASS'
    Write-Host 'AZURE_CALLED=false'
    Write-Host 'TERRAFORM_CALLED=false'
    Write-Host 'MUTATION=false'
    exit 0
}

if ([string]::IsNullOrWhiteSpace($PlanPath) -or [string]::IsNullOrWhiteSpace($ArtifactRoot)) {
    Stop-Gate 'STOP_REQUIRED_PARAMETER_MISSING' 'PlanPath and ArtifactRoot are required.'
}

$terraformPath = Require-Command 'terraform'
[void](Require-Command 'git')
[void](Require-Command 'az')

$PlanPath = [System.IO.Path]::GetFullPath($PlanPath)
$ArtifactRoot = [System.IO.Path]::GetFullPath($ArtifactRoot)
$expectedPlanPath = [System.IO.Path]::GetFullPath(
    (Join-Path $ArtifactRoot 'evidence\p0-recovery-diagnostic.tfplan')
)
$terraformDirectory = Join-Path $ArtifactRoot 'repo\infra\azure\p0'
$repositoryDirectory = Join-Path $ArtifactRoot 'repo'
$applyLog = Join-Path $ArtifactRoot 'evidence\p0-authorized-apply.log'
$receiptPath = Join-Path $env:USERPROFILE (
    'SOAIACORE_P51_AUTHORIZED_APPLY_RECEIPT_{0}.sanitized.json' -f
    [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
)

$applyStarted = $false
$applySucceeded = $false
$planJsonText = $null
$planJson = $null

try {
    if (-not $PlanPath.Equals($expectedPlanPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        Stop-Gate 'STOP_PLAN_PATH_MISMATCH' 'PlanPath is not the authorized artifact path.'
    }
    if (-not (Test-Path -LiteralPath $PlanPath -PathType Leaf)) {
        Stop-Gate 'STOP_AUTHORIZED_PLAN_MISSING' 'Authorized saved plan is unavailable.'
    }
    if (-not (Test-Path -LiteralPath $terraformDirectory -PathType Container)) {
        Stop-Gate 'STOP_TERRAFORM_DIRECTORY_MISSING' 'Pinned Terraform working directory is unavailable.'
    }

    Assert-NoReparseAncestors -Path $PlanPath
    Assert-NoReparseAncestors -Path $terraformDirectory
    Assert-OperatorOnlyAcl -Path $ArtifactRoot

    $accountText = @(& az account show --only-show-errors --output json 2>&1) -join "`n"
    if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_AZURE_AUTH' 'Azure account precheck failed.' }
    $account = $accountText | ConvertFrom-Json
    if ([string]$account.id -ne $ExpectedSubscriptionId -or [string]$account.state -ne 'Enabled') {
        Stop-Gate 'STOP_SCOPE_MISMATCH' 'Azure subscription is not the authorized enabled P0 subscription.'
    }

    $actualConfigCommit = (@(& git -C $repositoryDirectory rev-parse HEAD 2>&1) -join "`n").Trim()
    if ($LASTEXITCODE -ne 0 -or $actualConfigCommit -ne $ExpectedConfigCommit) {
        Stop-Gate 'STOP_CONFIG_COMMIT_MISMATCH' 'Artifact repository does not match the authorized configuration commit.'
    }

    $planSha = (Get-FileHash -LiteralPath $PlanPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($planSha -ne $AuthorizedPlanSha256) {
        Stop-Gate 'STOP_PLAN_HASH_MISMATCH' ("Observed unauthorized plan SHA256: {0}" -f $planSha)
    }

    $showErrorPath = Join-Path $ArtifactRoot 'evidence\terraform-show.stderr.log'
    $planJsonText = (& terraform ("-chdir={0}" -f $terraformDirectory) show -json $PlanPath 2> $showErrorPath | Out-String)
    $showExitCode = $LASTEXITCODE
    Remove-Item -LiteralPath $showErrorPath -Force -ErrorAction SilentlyContinue
    if ($showExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($planJsonText)) {
        Stop-Gate 'STOP_PLAN_SHOW_FAILED' 'Authorized saved plan could not be inspected.'
    }
    $planJson = $planJsonText | ConvertFrom-Json -Depth 100
    $changedResources = @(
        $planJson.resource_changes | Where-Object {
            @($_.change.actions) -notcontains 'no-op' -and
            @($_.change.actions) -notcontains 'read'
        }
    )
    Test-ExactActionSet -ChangedResources $changedResources
    $planJsonText = $null
    $planJson = $null

    $stateBeforeError = Join-Path $ArtifactRoot 'evidence\state-before.stderr.log'
    $stateBefore = @(& terraform ("-chdir={0}" -f $terraformDirectory) state list 2> $stateBeforeError)
    if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_PRE_APPLY_STATE_READ' 'Remote state could not be read.' }
    Remove-Item -LiteralPath $stateBeforeError -Force -ErrorAction SilentlyContinue
    $stateBefore = @($stateBefore | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($stateBefore.Count -ne $ExpectedStateBefore) {
        Stop-Gate 'STOP_PRE_APPLY_STATE_COUNT' (
            "Expected {0} state addresses, observed {1}." -f $ExpectedStateBefore, $stateBefore.Count
        )
    }

    $secondPlanSha = (Get-FileHash -LiteralPath $PlanPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($secondPlanSha -ne $AuthorizedPlanSha256) {
        Stop-Gate 'STOP_PLAN_HASH_CHANGED' 'Saved-plan hash changed after validation.'
    }

    Write-Host '=== SOAIACORE P51 · AUTHORIZED SAVED PLAN APPLY ==='
    Write-Host ("AUTHORIZATION_MESSAGE_ID={0}" -f $AuthorizationMessageId)
    Write-Host ("CONFIG_COMMIT={0}" -f $ExpectedConfigCommit)
    Write-Host ("PLAN_SHA256_VERIFIED={0}" -f $secondPlanSha)
    Write-Host 'EXACT_ACTION_SET=PASS'
    Write-Host 'CREATE=11'
    Write-Host 'UPDATE=4'
    Write-Host 'DELETE=1'
    Write-Host 'REPLACE=0'
    Write-Host 'DESTROY=false'
    Write-Host 'TEARDOWN=false'
    Write-Host 'PRODUCTION=false'
    Write-Host 'TERRAFORM_APPLY_START=true'

    $applyStarted = $true
    $applyExitCode = Invoke-TerraformApplyWithTimeout `
        -TerraformPath $terraformPath `
        -TerraformDirectory $terraformDirectory `
        -SavedPlanPath $PlanPath `
        -ApplyLogPath $applyLog `
        -ProcessTimeoutSeconds $TimeoutSeconds

    if ($applyExitCode -ne 0) {
        Stop-Gate 'STOP_TERRAFORM_APPLY_FAILED' (
            "Terraform apply exited with code {0}; protected log retained at {1}." -f $applyExitCode, $applyLog
        )
    }
    $applySucceeded = $true

    $stateAfterError = Join-Path $ArtifactRoot 'evidence\state-after.stderr.log'
    $stateAfter = @(& terraform ("-chdir={0}" -f $terraformDirectory) state list 2> $stateAfterError)
    if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_POST_APPLY_STATE_READ' 'Post-apply remote state could not be read.' }
    Remove-Item -LiteralPath $stateAfterError -Force -ErrorAction SilentlyContinue
    $stateAfter = @($stateAfter | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    $stateSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($address in $stateAfter) { [void]$stateSet.Add([string]$address) }

    if ($stateAfter.Count -ne $ExpectedStateAfter) {
        Stop-Gate 'STOP_POST_APPLY_STATE_COUNT' (
            "Expected {0} state addresses, observed {1}." -f $ExpectedStateAfter, $stateAfter.Count
        )
    }
    foreach ($address in $ExpectedPostApplyAddresses) {
        if (-not $stateSet.Contains($address)) {
            Stop-Gate 'STOP_POST_APPLY_ADDRESS_MISSING' ("Expected state address is missing: {0}" -f $address)
        }
    }
    if ($stateSet.Contains('azurerm_role_assignment.workload_key_vault_secrets_user')) {
        Stop-Gate 'STOP_BROAD_ROLE_STILL_PRESENT' 'Former vault-wide role assignment remains in Terraform state.'
    }

    $receipt = [ordered]@{
        schema                         = 'SOAIACORE_P51_AUTHORIZED_SAVED_PLAN_APPLY_V1'
        recorded_utc                   = [DateTime]::UtcNow.ToString('o')
        subscription_id                = $ExpectedSubscriptionId
        authorization_message_id       = $AuthorizationMessageId
        config_commit                  = $ExpectedConfigCommit
        plan_sha256                    = $AuthorizedPlanSha256
        exact_action_set_verified      = $true
        action_counts                  = [ordered]@{ create=11; update=4; delete=1; replace=0 }
        sole_authorized_deletion       = 'azurerm_role_assignment.workload_key_vault_secrets_user'
        pre_apply_state_count          = $ExpectedStateBefore
        post_apply_state_count         = $stateAfter.Count
        expected_post_apply_addresses  = $ExpectedPostApplyAddresses
        former_broad_role_absent       = $true
        terraform_apply_executed       = $true
        terraform_apply_succeeded      = $true
        destroy_executed               = $false
        teardown_executed              = $false
        production_authorized          = $false
        raw_apply_log_persisted         = $false
        saved_plan_consumed_and_deleted = $true
    }

    Remove-Item -LiteralPath $PlanPath -Force
    if (Test-Path -LiteralPath $PlanPath) {
        Stop-Gate 'STOP_SAVED_PLAN_CLEANUP_FAILED' 'Applied saved plan could not be deleted.'
    }
    Remove-Item -LiteralPath $applyLog -Force
    if (Test-Path -LiteralPath $applyLog) {
        Stop-Gate 'STOP_RAW_APPLY_LOG_CLEANUP_FAILED' 'Raw apply log could not be deleted.'
    }

    $receipt | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $receiptPath -Encoding utf8
    $receiptSha = (Get-FileHash -LiteralPath $receiptPath -Algorithm SHA256).Hash.ToLowerInvariant()

    Write-Host ''
    Write-Host '=== SOAIACORE P51 · FINAL AUTHORIZED APPLY RECEIPT ==='
    Write-Host ("AUTHORIZATION_MESSAGE_ID={0}" -f $AuthorizationMessageId)
    Write-Host ("CONFIG_COMMIT={0}" -f $ExpectedConfigCommit)
    Write-Host ("PLAN_SHA256={0}" -f $AuthorizedPlanSha256)
    Write-Host 'CREATE=11'
    Write-Host 'UPDATE=4'
    Write-Host 'DELETE=1'
    Write-Host 'REPLACE=0'
    Write-Host ("STATE_BEFORE={0}" -f $ExpectedStateBefore)
    Write-Host ("STATE_AFTER={0}" -f $stateAfter.Count)
    Write-Host 'POST_APPLY_STATE_GATE=PASS'
    Write-Host 'FORMER_BROAD_ROLE_ABSENT=PASS'
    Write-Host 'TERRAFORM_APPLY=PASS'
    Write-Host 'SAVED_PLAN_CONSUMED_AND_DELETED=true'
    Write-Host 'RAW_APPLY_LOG_PERSISTED=false'
    Write-Host 'DESTROY=false'
    Write-Host 'TEARDOWN=false'
    Write-Host 'PRODUCTION=false'
    Write-Host ("SANITIZED_RECEIPT={0}" -f $receiptPath)
    Write-Host ("RECEIPT_SHA256={0}" -f $receiptSha)
    Write-Host 'DONE=true'
}
catch {
    Write-Host ''
    Write-Host '=== SOAIACORE P51 · AUTHORIZED APPLY STOP ==='
    Write-Host ("STOP_REASON={0}" -f $_.Exception.Message)
    Write-Host ("APPLY_STARTED={0}" -f $applyStarted.ToString().ToLowerInvariant())
    Write-Host ("APPLY_SUCCEEDED={0}" -f $applySucceeded.ToString().ToLowerInvariant())
    Write-Host 'DESTROY=false'
    Write-Host 'TEARDOWN=false'
    Write-Host 'PRODUCTION=false'
    Write-Host 'DONE=false'
    exit 1
}
finally {
    $planJsonText = $null
    $planJson = $null
}
