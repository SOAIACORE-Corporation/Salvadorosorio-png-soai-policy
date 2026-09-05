[CmdletBinding()]
param(
    [switch]$SelfTest
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$TargetConfigCommit = '6743dbeb97709476ad9f482eb86bc7ac9af15100'
$BaseDiagnosticCommit = 'a62bdb0a28c78610eeecaa0b4005bdbd2b83c7e9'
$BaseDiagnosticUrl = "https://raw.githubusercontent.com/SOAIACORE-Corporation/Salvadorosorio-png-soai-policy/$BaseDiagnosticCommit/scripts/forensics/Invoke-P0RecoveryDiagnosticPlan.ps1"
$OriginalConfigCommit = '4b47fe25bb89c5733783920b1f8497c7dfadbb92'
$BaseTimeoutSeconds = 300

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

function Patch-DiagnosticScriptText {
    param([string]$ScriptText)

    $oldPin = '$ExpectedConfigCommit = ''' + $OriginalConfigCommit + ''''
    $newPin = '$ExpectedConfigCommit = ''' + $TargetConfigCommit + ''''
    if ([regex]::Matches($ScriptText, [regex]::Escape($oldPin)).Count -ne 1) {
        Stop-Gate 'STOP_BASE_SCRIPT_PIN_MISMATCH' 'Expected exactly one configuration pin in the base diagnostic script.'
    }
    $patched = $ScriptText.Replace($oldPin, $newPin)

    $oldPlan = '& terraform ("-chdir={0}" -f $terraformDirectory) plan -input=false -detailed-exitcode -no-color ("-out={0}" -f $planPath) *> $planLog'
    $newPlan = '& terraform ("-chdir={0}" -f $terraformDirectory) plan -refresh=false -lock-timeout=15s -input=false -detailed-exitcode -no-color ("-out={0}" -f $planPath) *> $planLog'
    if ([regex]::Matches($patched, [regex]::Escape($oldPlan)).Count -ne 1) {
        Stop-Gate 'STOP_BASE_SCRIPT_PLAN_MISMATCH' 'Expected exactly one Terraform plan invocation in the base diagnostic script.'
    }
    return $patched.Replace($oldPlan, $newPlan)
}

function Invoke-ProcessTextWithTimeout {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [int]$TimeoutSeconds,
        [string]$Label
    )

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $FilePath
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    foreach ($argument in $Arguments) {
        [void]$psi.ArgumentList.Add($argument)
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $psi
    try {
        if (-not $process.Start()) {
            Stop-Gate 'STOP_PROCESS_START_FAILED' ("{0} could not start." -f $Label)
        }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            try { $process.Kill($true) } catch {}
            Stop-Gate 'STOP_PROCESS_TIMEOUT' ("{0} exceeded {1} seconds and its process tree was terminated." -f $Label, $TimeoutSeconds)
        }
        return [pscustomobject]@{
            ExitCode = $process.ExitCode
            StdOut   = $stdoutTask.GetAwaiter().GetResult()
            StdErr   = $stderrTask.GetAwaiter().GetResult()
        }
    }
    finally {
        if ($null -ne $process -and -not $process.HasExited) {
            try { $process.Kill($true) } catch {}
        }
        if ($null -ne $process) { $process.Dispose() }
    }
}

function Get-PlanTextKeys {
    param(
        [string[]]$Lines,
        [System.Collections.Generic.HashSet[string]]$AllowedAddresses
    )

    $map = [ordered]@{}
    $currentAddress = $null

    foreach ($line in $Lines) {
        $header = [regex]::Match($line, '^\s*#\s+(\S+)\s+will be updated in-place\s*$')
        if ($header.Success) {
            $candidate = $header.Groups[1].Value
            if ($AllowedAddresses.Contains($candidate)) {
                $currentAddress = $candidate
                if (-not $map.Contains($candidate)) {
                    $map[$candidate] = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
                }
            }
            else {
                $currentAddress = $null
            }
            continue
        }

        if ([string]::IsNullOrWhiteSpace($currentAddress)) { continue }

        $changed = [regex]::Match($line, '^\s*[~+\-]\s+([A-Za-z0-9_]+)\s*(?:=|\{)')
        if ($changed.Success) {
            [void]$map[$currentAddress].Add($changed.Groups[1].Value)
        }
    }

    $rows = @()
    foreach ($address in $map.Keys) {
        $keys = @($map[$address] | Sort-Object)
        if ($keys.Count -eq 0) { $keys = @('<provider-redacted-or-computed>') }
        $rows += [ordered]@{
            address      = $address
            changed_keys = $keys
        }
    }
    return $rows
}

function Test-ResidualRecoveryProcesses {
    if (-not $IsWindows) { return @() }
    if (-not (Get-Command Get-CimInstance -ErrorAction SilentlyContinue)) { return @() }

    $patterns = @(
        'Invoke-P0RecoveryAttributeDiagnostic.ps1',
        'Invoke-P0RecoveryAttributeDiagnosticV2.ps1',
        'Invoke-P0RecoveryDiagnosticPlan.pinned.ps1'
    )
    $rows = @()
    foreach ($process in @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)) {
        if ([int]$process.ProcessId -eq $PID) { continue }
        $commandLine = [string]$process.CommandLine
        if ([string]::IsNullOrWhiteSpace($commandLine)) { continue }
        foreach ($pattern in $patterns) {
            if ($commandLine -like ("*{0}*" -f $pattern)) {
                $rows += [pscustomobject]@{
                    ProcessId       = [int]$process.ProcessId
                    ParentProcessId = [int]$process.ParentProcessId
                    Name            = [string]$process.Name
                    Pattern         = $pattern
                }
                break
            }
        }
    }
    return @($rows)
}

if ($SelfTest) {
    $allowed = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    [void]$allowed.Add('azurerm_container_app.core')
    [void]$allowed.Add('azurerm_storage_account.evidence')
    $fixture = @(
        '  # azurerm_container_app.core will be updated in-place',
        '  ~ resource "azurerm_container_app" "core" {',
        '      ~ revision_suffix = "DO_NOT_LEAK_OLD" -> "DO_NOT_LEAK_NEW"',
        '      ~ secret { # contents sensitive and deliberately hidden',
        '        }',
        '    }',
        '  # azurerm_storage_account.evidence will be updated in-place',
        '  ~ resource "azurerm_storage_account" "evidence" {',
        '      ~ share_properties {',
        '        }',
        '    }'
    )
    $rows = @(Get-PlanTextKeys -Lines $fixture -AllowedAddresses $allowed)
    $serialized = $rows | ConvertTo-Json -Depth 10 -Compress
    if ($rows.Count -ne 2) { throw 'SELFTEST_PLAN_TEXT_RESOURCE_COUNT_FAILED' }
    if ($serialized -notmatch 'revision_suffix' -or $serialized -notmatch 'secret' -or $serialized -notmatch 'share_properties') {
        throw 'SELFTEST_PLAN_TEXT_KEYS_FAILED'
    }
    if ($serialized -match 'DO_NOT_LEAK_OLD|DO_NOT_LEAK_NEW') {
        throw 'SELFTEST_PLAN_TEXT_VALUE_LEAK_FAILED'
    }

    $fixtureScript = @'
$ExpectedConfigCommit = '4b47fe25bb89c5733783920b1f8497c7dfadbb92'
& terraform ("-chdir={0}" -f $terraformDirectory) plan -input=false -detailed-exitcode -no-color ("-out={0}" -f $planPath) *> $planLog
'@
    $patched = Patch-DiagnosticScriptText $fixtureScript
    if ($patched -notmatch [regex]::Escape($TargetConfigCommit) -or $patched -notmatch 'plan -refresh=false -lock-timeout=15s') {
        throw 'SELFTEST_PLAN_PATCH_FAILED'
    }

    Write-Host 'SELFTEST=PASS'
    Write-Host 'PLAN_TEXT_PARSER=PASS'
    Write-Host 'VALUE_LEAK_TEST=PASS'
    Write-Host 'PROCESS_TIMEOUT_GUARD=CONFIGURED'
    Write-Host 'NETWORK_CALLED=false'
    Write-Host 'AZURE_CALLED=false'
    Write-Host 'TERRAFORM_CALLED=false'
    Write-Host 'MUTATION=false'
    exit 0
}

$pwshPath = Require-Command 'pwsh'
[void](Require-Command 'terraform')

$residual = @(Test-ResidualRecoveryProcesses)
if ($residual.Count -gt 0) {
    $ids = ($residual | ForEach-Object { [string]$_.ProcessId }) -join ','
    Stop-Gate 'STOP_RESIDUAL_RECOVERY_PROCESS' ("Residual recovery process detected. PIDs={0}. No new plan was started." -f $ids)
}

$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$workRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("soaiacore-p0-plan-text-diagnostic-{0}" -f $stamp)
New-Item -ItemType Directory -Path $workRoot -Force | Out-Null
$baseScriptPath = Join-Path $workRoot 'Invoke-P0RecoveryDiagnosticPlan.pinned.ps1'
$baseFailurePath = Join-Path $workRoot 'base-diagnostic.failure.log'
$receiptPath = Join-Path $HOME ("SOAIACORE_38_PLAN_TEXT_KEYS_{0}.sanitized.json" -f $stamp)
$successful = $false
$basePlanWorkRoot = $null

try {
    Write-Host 'PHASE=LOCAL_PROCESS_CHECK DONE residual=0'
    Write-Host 'PHASE=PREPARE_BASE_DIAGNOSTIC START'
    $downloadPath = Join-Path $workRoot 'base.ps1'
    Invoke-WebRequest -UseBasicParsing $BaseDiagnosticUrl -OutFile $downloadPath
    $baseText = Get-Content -LiteralPath $downloadPath -Raw
    $patchedText = Patch-DiagnosticScriptText $baseText
    Set-Content -LiteralPath $baseScriptPath -Value $patchedText -Encoding utf8
    Write-Host 'PHASE=PREPARE_BASE_DIAGNOSTIC DONE'

    Write-Host 'PHASE=BASE_DIAGNOSTIC START timeout_seconds=300 lock_timeout_seconds=15'
    $baseProcess = Invoke-ProcessTextWithTimeout -FilePath $pwshPath -Arguments @('-NoProfile','-ExecutionPolicy','Bypass','-File',$baseScriptPath) -TimeoutSeconds $BaseTimeoutSeconds -Label 'Pinned base diagnostic'
    if ($baseProcess.ExitCode -ne 0) {
        @($baseProcess.StdOut, $baseProcess.StdErr) | Set-Content -LiteralPath $baseFailurePath -Encoding utf8
        Stop-Gate 'STOP_BASE_DIAGNOSTIC_FAILED' ("Pinned base diagnostic failed with exit code {0}. Failure log retained at {1}." -f $baseProcess.ExitCode, $baseFailurePath)
    }
    Write-Host 'PHASE=BASE_DIAGNOSTIC DONE'

    $outputLines = @(($baseProcess.StdOut -split "`r?`n") | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $receiptLines = @($outputLines | Where-Object { $_ -like 'SANITIZED_RECEIPT=*' })
    if ($receiptLines.Count -ne 1) {
        Stop-Gate 'STOP_BASE_RECEIPT_MISSING' 'Could not resolve exactly one sanitized receipt from the base diagnostic.'
    }
    $baseReceiptPath = $receiptLines[0].Substring('SANITIZED_RECEIPT='.Length)
    if (-not (Test-Path -LiteralPath $baseReceiptPath -PathType Leaf)) {
        Stop-Gate 'STOP_BASE_RECEIPT_NOT_FOUND' 'Base sanitized receipt file was not found.'
    }

    $baseReceipt = Get-Content -LiteralPath $baseReceiptPath -Raw | ConvertFrom-Json -Depth 100
    if ([string]$baseReceipt.config_commit -ne $TargetConfigCommit) {
        Stop-Gate 'STOP_CONFIG_COMMIT_MISMATCH' 'Base receipt does not reference the expected recovery configuration commit.'
    }
    if ([bool]$baseReceipt.terraform_apply_executed -or [bool]$baseReceipt.mutation) {
        Stop-Gate 'STOP_MUTATION_BOUNDARY' 'Base receipt indicates an unexpected mutation boundary violation.'
    }
    if ([int]$baseReceipt.action_counts.delete -gt 0 -or [int]$baseReceipt.action_counts.replace -gt 0) {
        Stop-Gate 'STOP_DESTRUCTIVE_PLAN' 'Base plan contains delete or replace actions; parsing halted.'
    }

    $planLog = [string]$baseReceipt.diagnostic_plan_log
    if ([string]::IsNullOrWhiteSpace($planLog) -or -not (Test-Path -LiteralPath $planLog -PathType Leaf)) {
        Stop-Gate 'STOP_PLAN_LOG_MISSING' 'Base diagnostic plan log is unavailable.'
    }
    $planEvidenceDir = Split-Path -Parent $planLog
    $basePlanWorkRoot = Split-Path -Parent $planEvidenceDir

    $allowed = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($changed in @($baseReceipt.changed_resources)) {
        [void]$allowed.Add([string]$changed.address)
    }

    Write-Host 'PHASE=PLAN_TEXT_SANITIZE START'
    $planLines = @(Get-Content -LiteralPath $planLog)
    $rows = @(Get-PlanTextKeys -Lines $planLines -AllowedAddresses $allowed)
    $planLines = $null
    Write-Host ("PHASE=PLAN_TEXT_SANITIZE DONE resources={0}" -f $rows.Count)

    $receipt = [ordered]@{
        schema                                       = 'SOAIACORE_38_PLAN_TEXT_KEYS_V1'
        recorded_utc                                 = (Get-Date).ToUniversalTime().ToString('o')
        config_commit                                = $TargetConfigCommit
        base_diagnostic_commit                       = $BaseDiagnosticCommit
        terraform_refresh                            = $false
        terraform_lock_timeout_seconds               = 15
        state_address_count                          = [int]$baseReceipt.state_address_count
        plan_exit_code                               = [int]$baseReceipt.plan_exit_code
        plan_sha256                                  = [string]$baseReceipt.plan_sha256
        plan_gate                                    = [string]$baseReceipt.plan_gate
        action_counts                                = $baseReceipt.action_counts
        changed_resources                            = $rows
        attribute_values_output                      = $false
        secret_values_output                         = $false
        raw_plan_json_created                        = $false
        terraform_show_json_executed                 = $false
        terraform_apply_executed                     = $false
        mutation                                     = $false
        human_adjudication_required_before_any_apply = $true
    }
    $receipt | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $receiptPath -Encoding utf8
    $receiptHash = (Get-FileHash -LiteralPath $receiptPath -Algorithm SHA256).Hash.ToLowerInvariant()

    Write-Host ''
    Write-Host '=== SOAIACORE #38 PLAN-TEXT ATTRIBUTE DIAGNOSTIC ==='
    Write-Host ("CONFIG_COMMIT={0}" -f $TargetConfigCommit)
    Write-Host ("STATE_ADDRESS_COUNT={0}" -f $baseReceipt.state_address_count)
    Write-Host ("PLAN_EXIT_CODE={0}" -f $baseReceipt.plan_exit_code)
    Write-Host ("CREATE_COUNT={0}" -f $baseReceipt.action_counts.create)
    Write-Host ("UPDATE_COUNT={0}" -f $baseReceipt.action_counts.update)
    Write-Host ("DELETE_COUNT={0}" -f $baseReceipt.action_counts.delete)
    Write-Host ("REPLACE_COUNT={0}" -f $baseReceipt.action_counts.replace)
    Write-Host ("PLAN_GATE={0}" -f $baseReceipt.plan_gate)
    Write-Host ("PLAN_SHA256={0}" -f $baseReceipt.plan_sha256)
    Write-Host ("SANITIZED_RECEIPT={0}" -f $receiptPath)
    Write-Host ("RECEIPT_SHA256={0}" -f $receiptHash)
    Write-Host 'TERRAFORM_REFRESH=false'
    Write-Host 'LOCK_TIMEOUT_SECONDS=15'
    Write-Host 'ATTRIBUTE_VALUES_OUTPUT=false'
    Write-Host 'SECRET_VALUES_OUTPUT=false'
    Write-Host 'TERRAFORM_SHOW_JSON_EXECUTED=false'
    Write-Host 'APPLY_EXECUTED=false'
    Write-Host 'MUTATION=false'
    Write-Host 'DONE=true'
    $successful = $true
}
finally {
    Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue
    if ($successful -and -not [string]::IsNullOrWhiteSpace([string]$basePlanWorkRoot)) {
        Remove-Item -LiteralPath $basePlanWorkRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
