[CmdletBinding()]
param(
    [switch]$SelfTest,
    [ValidateRange(300, 1800)]
    [int]$TimeoutSeconds = 900
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
if (Test-Path Variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$ExpectedSubscriptionId = '108eb4dd-25b3-4a7f-8d5e-4ec4389c3f0d'
$TargetConfigCommit = '685ca1d13238949e7254d452b0f11fb23777855c'
$BaseDiagnosticCommit = 'a62bdb0a28c78610eeecaa0b4005bdbd2b83c7e9'
$BaseDiagnosticUrl = "https://raw.githubusercontent.com/SOAIACORE-Corporation/Salvadorosorio-png-soai-policy/$BaseDiagnosticCommit/scripts/forensics/Invoke-P0RecoveryDiagnosticPlan.ps1"
$OriginalConfigCommit = '4b47fe25bb89c5733783920b1f8497c7dfadbb92'

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

function Remove-DirectoryVerified {
    param(
        [string]$Path,
        [int]$CleanupTimeoutSeconds = 60
    )

    if ([string]::IsNullOrWhiteSpace($Path)) { return }
    $deadline = [DateTime]::UtcNow.AddSeconds($CleanupTimeoutSeconds)
    do {
        if (-not (Test-Path -LiteralPath $Path)) { return }
        try { Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop }
        catch {}
        if (-not (Test-Path -LiteralPath $Path)) { return }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)

    Stop-Gate 'STOP_SENSITIVE_CLEANUP_UNVERIFIED' (
        "Could not prove deletion of sensitive work root: {0}" -f $Path
    )
}

function Protect-OperatorDirectory {
    param([string]$Path)

    if (-not $IsWindows) {
        Stop-Gate 'STOP_UNSUPPORTED_PLATFORM' 'Saved-plan generation is restricted to Windows PowerShell 7.'
    }

    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    if ([string]::IsNullOrWhiteSpace($identity)) {
        Stop-Gate 'STOP_OPERATOR_IDENTITY_MISSING' 'Could not resolve the current Windows identity.'
    }

    & icacls.exe $Path /inheritance:r | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Stop-Gate 'STOP_ARTIFACT_ACL_FAILED' 'Could not remove inherited permissions from the artifact root.'
    }

    & icacls.exe $Path /grant:r ("{0}:(OI)(CI)F" -f $identity) | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Stop-Gate 'STOP_ARTIFACT_ACL_FAILED' 'Could not grant the operator exclusive control of the artifact root.'
    }

    $acl = Get-Acl -LiteralPath $Path
    $unexpectedRules = @(
        $acl.Access | Where-Object {
            $_.IsInherited -or
            [string]$_.IdentityReference -ne $identity -or
            $_.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow
        }
    )
    $operatorRules = @(
        $acl.Access | Where-Object {
            -not $_.IsInherited -and
            [string]$_.IdentityReference -eq $identity -and
            $_.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow -and
            ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::FullControl)
        }
    )
    if ($unexpectedRules.Count -ne 0 -or $operatorRules.Count -lt 1) {
        Stop-Gate 'STOP_ARTIFACT_ACL_VERIFY_FAILED' 'Artifact ACL is not exclusive to the current operator.'
    }

    Write-Host ("ARTIFACT_OPERATOR={0}" -f $identity)
    Write-Host 'ARTIFACT_ACL=OPERATOR_ONLY'
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

function Patch-BaseDiagnostic {
    param([string]$ScriptText)

    $ScriptText = $ScriptText -replace "`r`n", "`n"

    $oldPin = '$ExpectedConfigCommit = ''' + $OriginalConfigCommit + ''''
    $newPin = '$ExpectedConfigCommit = ''' + $TargetConfigCommit + ''''
    if ([regex]::Matches($ScriptText, [regex]::Escape($oldPin)).Count -ne 1) {
        Stop-Gate 'STOP_BASE_SCRIPT_PIN_MISMATCH' 'Expected exactly one configuration pin.'
    }
    $patched = $ScriptText.Replace($oldPin, $newPin)

    $oldRoot = '$workRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("soaiacore-p0-recovery-plan-{0}" -f $stamp)'
    $newRoot = '$workRoot = $env:SOAIACORE_P0_SAVED_PLAN_ROOT'
    if ([regex]::Matches($patched, [regex]::Escape($oldRoot)).Count -ne 1) {
        Stop-Gate 'STOP_BASE_SCRIPT_ROOT_MISMATCH' 'Expected exactly one work-root assignment.'
    }
    $patched = $patched.Replace($oldRoot, $newRoot)

    $oldPlan = '& terraform ("-chdir={0}" -f $terraformDirectory) plan -input=false -detailed-exitcode -no-color ("-out={0}" -f $planPath) *> $planLog'
    $newPlan = '& terraform ("-chdir={0}" -f $terraformDirectory) plan -lock-timeout=15s -input=false -detailed-exitcode -no-color ("-out={0}" -f $planPath) *> $planLog'
    if ([regex]::Matches($patched, [regex]::Escape($oldPlan)).Count -ne 1) {
        Stop-Gate 'STOP_BASE_SCRIPT_PLAN_MISMATCH' 'Expected exactly one Terraform plan invocation.'
    }
    return $patched.Replace($oldPlan, $newPlan)
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
        $actions = @($row.actions)
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

function Invoke-ProcessWithTimeout {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkRoot,
        [int]$ProcessTimeoutSeconds
    )

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $FilePath
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $psi.Environment['SOAIACORE_P0_SAVED_PLAN_ROOT'] = $WorkRoot
    foreach ($argument in $Arguments) { [void]$psi.ArgumentList.Add($argument) }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $psi
    $started = $false
    $timedOut = $false
    try {
        if (-not $process.Start()) {
            Stop-Gate 'STOP_PROCESS_START_FAILED' 'Saved-plan child process could not start.'
        }
        $started = $true
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $timer = [System.Diagnostics.Stopwatch]::StartNew()

        while (-not $process.HasExited) {
            $remaining = [int][Math]::Max(1, (($ProcessTimeoutSeconds * 1000) - $timer.ElapsedMilliseconds))
            $slice = [int][Math]::Min(30000, $remaining)
            if ($process.WaitForExit($slice)) { break }
            Write-Host (
                'PROCESS_HEARTBEAT=SAVED_PLAN|ELAPSED_SECONDS={0}|TIMEOUT_SECONDS={1}' -f
                ([int][Math]::Floor($timer.Elapsed.TotalSeconds)),
                $ProcessTimeoutSeconds
            )
            if ($timer.Elapsed.TotalSeconds -ge $ProcessTimeoutSeconds) {
                $timedOut = $true
                try { $process.Kill($true) } catch {}
                try { [void]$process.WaitForExit(30000) } catch {}
                Stop-Gate 'STOP_PROCESS_TIMEOUT' (
                    "Saved-plan generation exceeded {0} seconds." -f $ProcessTimeoutSeconds
                )
            }
        }
        $timer.Stop()

        return [pscustomobject]@{
            ExitCode = $process.ExitCode
            StdOut   = $stdoutTask.GetAwaiter().GetResult()
            StdErr   = $stderrTask.GetAwaiter().GetResult()
        }
    }
    finally {
        if ($started -and -not $process.HasExited) {
            try { $process.Kill($true) } catch {}
            try { [void]$process.WaitForExit(30000) } catch {}
        }
        if ($timedOut) {
            Remove-DirectoryVerified -Path $WorkRoot
        }
        $process.Dispose()
    }
}

if ($SelfTest) {
    $fixture = @(
        $ExpectedActions.Keys | ForEach-Object {
            [pscustomobject]@{ address = [string]$_; actions = @([string]$ExpectedActions[$_]) }
        }
    )
    Test-ExactActionSet -ChangedResources $fixture
    if ($ExpectedActions.Count -ne 16) { throw 'SELFTEST_EXPECTED_ADDRESS_COUNT_FAILED' }
    if (@($ExpectedActions.Values | Where-Object { $_ -eq 'create' }).Count -ne 11) { throw 'SELFTEST_CREATE_COUNT_FAILED' }
    if (@($ExpectedActions.Values | Where-Object { $_ -eq 'update' }).Count -ne 4) { throw 'SELFTEST_UPDATE_COUNT_FAILED' }
    if (@($ExpectedActions.Values | Where-Object { $_ -eq 'delete' }).Count -ne 1) { throw 'SELFTEST_DELETE_COUNT_FAILED' }

    $patchFixture = @'
$ExpectedConfigCommit = '4b47fe25bb89c5733783920b1f8497c7dfadbb92'
$workRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("soaiacore-p0-recovery-plan-{0}" -f $stamp)
& terraform ("-chdir={0}" -f $terraformDirectory) plan -input=false -detailed-exitcode -no-color ("-out={0}" -f $planPath) *> $planLog
'@
    $patchedFixture = Patch-BaseDiagnostic -ScriptText $patchFixture
    if (
        $patchedFixture -notmatch [regex]::Escape($TargetConfigCommit) -or
        $patchedFixture -notmatch [regex]::Escape('$workRoot = $env:SOAIACORE_P0_SAVED_PLAN_ROOT') -or
        $patchedFixture -notmatch [regex]::Escape('plan -lock-timeout=15s -input=false')
    ) {
        throw 'SELFTEST_BASE_PATCH_FAILED'
    }

    Write-Host 'SELFTEST=PASS'
    Write-Host 'EXPECTED_ACTION_SET=PASS'
    Write-Host 'PINNED_BASE_PATCH=PASS'
    Write-Host 'NETWORK_CALLED=false'
    Write-Host 'AZURE_CALLED=false'
    Write-Host 'TERRAFORM_CALLED=false'
    Write-Host 'MUTATION=false'
    exit 0
}

$pwshPath = Require-Command 'pwsh'
[void](Require-Command 'git')
[void](Require-Command 'az')
[void](Require-Command 'terraform')
[void](Require-Command 'icacls.exe')

$accountText = @(& az account show --only-show-errors --output json 2>&1) -join "`n"
if ($LASTEXITCODE -ne 0) { Stop-Gate 'STOP_AZURE_AUTH' 'Azure account precheck failed.' }
$account = $accountText | ConvertFrom-Json
if ([string]$account.id -ne $ExpectedSubscriptionId -or [string]$account.state -ne 'Enabled') {
    Stop-Gate 'STOP_SCOPE_MISMATCH' 'Azure subscription is not the expected enabled P0 subscription.'
}

$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$controlledRoot = Join-Path $env:USERPROFILE 'SOAIACORE\controlled-apply'
$workRoot = Join-Path $controlledRoot $stamp
$patchedScriptPath = Join-Path $workRoot 'Invoke-P0RecoveryDiagnosticPlan.saved.ps1'
$receiptPath = Join-Path $env:USERPROFILE ("SOAIACORE_P51_SAVED_PLAN_RECEIPT_{0}.sanitized.json" -f $stamp)
$succeeded = $false

try {
    Assert-NoReparseAncestors -Path $controlledRoot
    New-Item -ItemType Directory -Path $workRoot -Force | Out-Null
    Assert-NoReparseAncestors -Path $workRoot
    Protect-OperatorDirectory -Path $workRoot

    $downloadPath = Join-Path $workRoot 'base.ps1'
    Invoke-WebRequest -UseBasicParsing $BaseDiagnosticUrl -OutFile $downloadPath
    $baseText = Get-Content -LiteralPath $downloadPath -Raw
    $patchedText = Patch-BaseDiagnostic -ScriptText $baseText
    Set-Content -LiteralPath $patchedScriptPath -Value $patchedText -Encoding utf8
    Remove-Item -LiteralPath $downloadPath -Force

    Write-Host 'SAVED_PLAN_GENERATION_START=true'
    Write-Host ("TARGET_CONFIG_COMMIT={0}" -f $TargetConfigCommit)
    Write-Host ("TIMEOUT_SECONDS={0}" -f $TimeoutSeconds)

    $result = Invoke-ProcessWithTimeout `
        -FilePath $pwshPath `
        -Arguments @('-NoProfile','-ExecutionPolicy','Bypass','-File',$patchedScriptPath) `
        -WorkRoot $workRoot `
        -ProcessTimeoutSeconds $TimeoutSeconds

    if ($result.ExitCode -ne 0) {
        Stop-Gate 'STOP_SAVED_PLAN_CHILD_FAILED' (
            "Saved-plan child failed with exit code {0}." -f $result.ExitCode
        )
    }

    $outputLines = @(($result.StdOut -split "`r?`n") | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $receiptLines = @($outputLines | Where-Object { $_ -like 'SANITIZED_RECEIPT=*' })
    if ($receiptLines.Count -ne 1) {
        Stop-Gate 'STOP_CHILD_RECEIPT_MISSING' 'Could not resolve exactly one child receipt.'
    }
    $childReceiptPath = $receiptLines[0].Substring('SANITIZED_RECEIPT='.Length)
    $childReceipt = Get-Content -LiteralPath $childReceiptPath -Raw | ConvertFrom-Json -Depth 100

    if ([string]$childReceipt.config_commit -ne $TargetConfigCommit) {
        Stop-Gate 'STOP_CONFIG_COMMIT_MISMATCH' 'Saved plan uses an unexpected configuration commit.'
    }
    if ([int]$childReceipt.state_address_count -ne 46 -or [int]$childReceipt.plan_exit_code -ne 2) {
        Stop-Gate 'STOP_STATE_OR_PLAN_EXIT_MISMATCH' 'State count or plan exit code changed unexpectedly.'
    }
    if ([bool]$childReceipt.terraform_apply_executed -or [bool]$childReceipt.mutation) {
        Stop-Gate 'STOP_MUTATION_BOUNDARY' 'Child receipt indicates an unexpected mutation.'
    }

    Test-ExactActionSet -ChangedResources @($childReceipt.changed_resources)

    $counts = $childReceipt.action_counts
    if (
        [int]$counts.create -ne 11 -or
        [int]$counts.update -ne 4 -or
        [int]$counts.delete -ne 1 -or
        [int]$counts.replace -ne 0
    ) {
        Stop-Gate 'STOP_ACTION_COUNT_MISMATCH' 'Saved plan action counts differ from the reviewed set.'
    }

    $planPath = [System.IO.Path]::GetFullPath([string]$childReceipt.diagnostic_plan_file)
    $rootPath = (
        [System.IO.Path]::GetFullPath($workRoot).TrimEnd(
            [System.IO.Path]::DirectorySeparatorChar,
            [System.IO.Path]::AltDirectorySeparatorChar
        ) + [System.IO.Path]::DirectorySeparatorChar
    )
    if (-not $planPath.StartsWith($rootPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        Stop-Gate 'STOP_PLAN_PATH_SCOPE' 'Saved plan is outside the protected artifact root.'
    }
    if (-not (Test-Path -LiteralPath $planPath -PathType Leaf)) {
        Stop-Gate 'STOP_SAVED_PLAN_MISSING' 'Saved plan file is unavailable.'
    }

    $planSha = (Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($planSha -ne [string]$childReceipt.plan_sha256) {
        Stop-Gate 'STOP_PLAN_HASH_MISMATCH' 'Independent saved-plan hash verification failed.'
    }

    $receipt = [ordered]@{
        schema                         = 'SOAIACORE_P51_GOVERNED_SAVED_PLAN_V1'
        recorded_utc                   = [DateTime]::UtcNow.ToString('o')
        subscription_id                = $ExpectedSubscriptionId
        config_commit                  = $TargetConfigCommit
        state_address_count            = 46
        plan_path                      = $planPath
        plan_sha256                    = $planSha
        artifact_root                  = $workRoot
        artifact_acl                   = 'OPERATOR_ONLY'
        action_counts                  = [ordered]@{ create=11; update=4; delete=1; replace=0 }
        changed_resources              = @($childReceipt.changed_resources)
        allowed_destructive_addresses  = @('azurerm_role_assignment.workload_key_vault_secrets_user')
        exact_action_set_verified      = $true
        human_authorization_required   = $true
        terraform_apply_executed       = $false
        mutation                       = $false
    }
    $receipt | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $receiptPath -Encoding utf8
    $receiptSha = (Get-FileHash -LiteralPath $receiptPath -Algorithm SHA256).Hash.ToLowerInvariant()

    Remove-Item -LiteralPath $patchedScriptPath -Force -ErrorAction SilentlyContinue
    $succeeded = $true

    Write-Host ''
    Write-Host '=== SOAIACORE P51 · GOVERNED SAVED PLAN RECEIPT ==='
    Write-Host ("CONFIG_COMMIT={0}" -f $TargetConfigCommit)
    Write-Host 'STATE_ADDRESS_COUNT=46'
    Write-Host 'CREATE_COUNT=11'
    Write-Host 'UPDATE_COUNT=4'
    Write-Host 'DELETE_COUNT=1'
    Write-Host 'REPLACE_COUNT=0'
    Write-Host 'EXACT_ACTION_SET=PASS'
    Write-Host 'ALLOWED_DESTRUCTIVE_ADDRESSES=azurerm_role_assignment.workload_key_vault_secrets_user'
    Write-Host ("PLAN_PATH={0}" -f $planPath)
    Write-Host ("PLAN_SHA256={0}" -f $planSha)
    Write-Host ("ARTIFACT_ROOT={0}" -f $workRoot)
    Write-Host 'ARTIFACT_ACL=OPERATOR_ONLY'
    Write-Host ("SANITIZED_RECEIPT={0}" -f $receiptPath)
    Write-Host ("RECEIPT_SHA256={0}" -f $receiptSha)
    Write-Host 'TERRAFORM_APPLY=false'
    Write-Host 'AZURE_MUTATION=false'
    Write-Host 'HUMAN_AUTHORIZATION_REQUIRED=true'
    Write-Host 'DONE=true'
}
finally {
    if (-not $succeeded) {
        Remove-DirectoryVerified -Path $workRoot
    }
}
