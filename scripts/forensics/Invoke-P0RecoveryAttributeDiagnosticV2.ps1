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
$TerraformShowTimeoutSeconds = 90
$DiffTimeoutSeconds = 60
$DiffMaxNodes = 200000
$DiffMaxDepth = 64

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

function Test-TrueMask {
    param($Value)
    return ($Value -is [bool] -and [bool]$Value)
}

function Test-ObjectNode {
    param($Value)
    return ($Value -is [System.Collections.IDictionary] -or $Value -is [pscustomobject])
}

function Test-ListNode {
    param($Value)
    if ($null -eq $Value -or $Value -is [string] -or (Test-ObjectNode $Value)) {
        return $false
    }
    return ($Value -is [System.Collections.IEnumerable])
}

function Get-PropertyNames {
    param($Value)
    if ($null -eq $Value) { return @() }
    if ($Value -is [System.Collections.IDictionary]) {
        return @($Value.Keys | ForEach-Object { [string]$_ })
    }
    if ($Value -is [pscustomobject]) {
        return @($Value.PSObject.Properties.Name)
    }
    return @()
}

function Get-ChildInfo {
    param($Value, [string]$Name)
    if ($null -eq $Value) {
        return [pscustomobject]@{ Exists = $false; Value = $null }
    }
    if ($Value -is [System.Collections.IDictionary]) {
        if ($Value.Contains($Name)) {
            return [pscustomobject]@{ Exists = $true; Value = $Value[$Name] }
        }
        return [pscustomobject]@{ Exists = $false; Value = $null }
    }
    if ($Value -is [pscustomobject]) {
        $property = $Value.PSObject.Properties[$Name]
        if ($null -ne $property) {
            return [pscustomobject]@{ Exists = $true; Value = $property.Value }
        }
    }
    return [pscustomobject]@{ Exists = $false; Value = $null }
}

function Join-AttributePath {
    param([string]$Base, [string]$Token)
    if ([string]::IsNullOrWhiteSpace($Base)) { return $Token }
    if ($Token.StartsWith('[')) { return ("{0}{1}" -f $Base, $Token) }
    return ("{0}.{1}" -f $Base, $Token)
}

function Test-ScalarEqual {
    param($Left, $Right)
    if ($null -eq $Left -and $null -eq $Right) { return $true }
    if ($null -eq $Left -or $null -eq $Right) { return $false }
    if ($Left -is [string] -and $Right -is [string]) {
        return ([string]$Left -ceq [string]$Right)
    }
    return ($Left -eq $Right)
}

function Assert-DiffBudget {
    param([hashtable]$Budget, [int]$Depth)
    $Budget.Nodes = [int]$Budget.Nodes + 1
    if ($Budget.Nodes -gt $Budget.MaxNodes) {
        Stop-Gate 'STOP_ATTRIBUTE_DIFF_NODE_BUDGET' ("Attribute diff exceeded node budget {0}." -f $Budget.MaxNodes)
    }
    if ($Depth -gt $Budget.MaxDepth) {
        Stop-Gate 'STOP_ATTRIBUTE_DIFF_DEPTH' ("Attribute diff exceeded depth budget {0}." -f $Budget.MaxDepth)
    }
    if ([DateTime]::UtcNow -gt $Budget.DeadlineUtc) {
        Stop-Gate 'STOP_ATTRIBUTE_DIFF_TIMEOUT' ("Attribute diff exceeded {0} seconds." -f $Budget.TimeoutSeconds)
    }
}

function Get-ChangedAttributePathsLinear {
    param(
        $Before,
        $After,
        $BeforeSensitive,
        $AfterSensitive,
        $AfterUnknown,
        [string]$Path,
        [hashtable]$Budget,
        [int]$Depth = 0
    )

    Assert-DiffBudget -Budget $Budget -Depth $Depth

    if (Test-TrueMask $AfterUnknown) {
        if ((Test-TrueMask $BeforeSensitive) -or (Test-TrueMask $AfterSensitive)) {
            return @((Join-AttributePath $Path '<sensitive-unknown>'))
        }
        return @((Join-AttributePath $Path '<unknown>'))
    }

    if ((Test-TrueMask $BeforeSensitive) -or (Test-TrueMask $AfterSensitive)) {
        return @((Join-AttributePath $Path '<sensitive>'))
    }

    $beforeIsObject = Test-ObjectNode $Before
    $afterIsObject = Test-ObjectNode $After
    if ($beforeIsObject -or $afterIsObject) {
        if (-not ($beforeIsObject -and $afterIsObject)) {
            return @($Path)
        }
        $allNames = @((Get-PropertyNames $Before) + (Get-PropertyNames $After) | Sort-Object -Unique)
        $result = @()
        foreach ($name in $allNames) {
            $beforeChild = Get-ChildInfo $Before $name
            $afterChild = Get-ChildInfo $After $name
            $beforeSensitiveChild = Get-ChildInfo $BeforeSensitive $name
            $afterSensitiveChild = Get-ChildInfo $AfterSensitive $name
            $afterUnknownChild = Get-ChildInfo $AfterUnknown $name
            $childPath = Join-AttributePath $Path $name

            if (-not $beforeChild.Exists -or -not $afterChild.Exists) {
                if ((Test-TrueMask $beforeSensitiveChild.Value) -or (Test-TrueMask $afterSensitiveChild.Value)) {
                    $result += (Join-AttributePath $childPath '<sensitive>')
                }
                elseif (Test-TrueMask $afterUnknownChild.Value) {
                    $result += (Join-AttributePath $childPath '<unknown>')
                }
                else {
                    $result += $childPath
                }
                continue
            }

            $childArgs = @{
                Before          = $beforeChild.Value
                After           = $afterChild.Value
                BeforeSensitive = $beforeSensitiveChild.Value
                AfterSensitive  = $afterSensitiveChild.Value
                AfterUnknown    = $afterUnknownChild.Value
                Path            = $childPath
                Budget          = $Budget
                Depth           = ($Depth + 1)
            }
            $result += @(Get-ChangedAttributePathsLinear @childArgs)
        }
        return @($result | Sort-Object -Unique)
    }

    $beforeIsList = Test-ListNode $Before
    $afterIsList = Test-ListNode $After
    if ($beforeIsList -or $afterIsList) {
        if (-not ($beforeIsList -and $afterIsList)) {
            return @($Path)
        }
        $beforeList = @($Before)
        $afterList = @($After)
        $beforeSensitiveList = if (Test-ListNode $BeforeSensitive) { @($BeforeSensitive) } else { @() }
        $afterSensitiveList = if (Test-ListNode $AfterSensitive) { @($AfterSensitive) } else { @() }
        $afterUnknownList = if (Test-ListNode $AfterUnknown) { @($AfterUnknown) } else { @() }
        $max = [Math]::Max($beforeList.Count, $afterList.Count)
        $result = @()
        for ($i = 0; $i -lt $max; $i++) {
            $childPath = Join-AttributePath $Path ("[{0}]" -f $i)
            if ($i -ge $beforeList.Count -or $i -ge $afterList.Count) {
                $sensitive = ($i -lt $beforeSensitiveList.Count -and (Test-TrueMask $beforeSensitiveList[$i])) -or ($i -lt $afterSensitiveList.Count -and (Test-TrueMask $afterSensitiveList[$i]))
                $unknown = ($i -lt $afterUnknownList.Count -and (Test-TrueMask $afterUnknownList[$i]))
                if ($sensitive) { $result += (Join-AttributePath $childPath '<sensitive>') }
                elseif ($unknown) { $result += (Join-AttributePath $childPath '<unknown>') }
                else { $result += $childPath }
                continue
            }

            $beforeSensitiveValue = if ($i -lt $beforeSensitiveList.Count) { $beforeSensitiveList[$i] } else { $null }
            $afterSensitiveValue = if ($i -lt $afterSensitiveList.Count) { $afterSensitiveList[$i] } else { $null }
            $afterUnknownValue = if ($i -lt $afterUnknownList.Count) { $afterUnknownList[$i] } else { $null }
            $listChildArgs = @{
                Before          = $beforeList[$i]
                After           = $afterList[$i]
                BeforeSensitive = $beforeSensitiveValue
                AfterSensitive  = $afterSensitiveValue
                AfterUnknown    = $afterUnknownValue
                Path            = $childPath
                Budget          = $Budget
                Depth           = ($Depth + 1)
            }
            $result += @(Get-ChangedAttributePathsLinear @listChildArgs)
        }
        return @($result | Sort-Object -Unique)
    }

    if (Test-ScalarEqual $Before $After) { return @() }
    return @($Path)
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
            Stop-Gate 'STOP_PROCESS_TIMEOUT' ("{0} exceeded {1} seconds and was terminated." -f $Label, $TimeoutSeconds)
        }
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        return [pscustomobject]@{
            ExitCode = $process.ExitCode
            StdOut   = $stdout
            StdErr   = $stderr
        }
    }
    finally {
        if ($null -ne $process -and -not $process.HasExited) {
            try { $process.Kill($true) } catch {}
        }
        if ($null -ne $process) { $process.Dispose() }
    }
}

if ($SelfTest) {
    $budget = @{
        Nodes          = 0
        MaxNodes       = 10000
        MaxDepth       = 32
        TimeoutSeconds = 5
        DeadlineUtc    = [DateTime]::UtcNow.AddSeconds(5)
    }
    $before = [pscustomobject]@{
        safe   = 'old'
        secret = [pscustomobject]@{ value = 'DO_NOT_LEAK_OLD' }
        stable = @('a','b','c')
    }
    $after = [pscustomobject]@{
        safe   = 'new'
        secret = [pscustomobject]@{ value = 'DO_NOT_LEAK_NEW' }
        stable = @('a','b','c')
    }
    $sensitiveMask = [pscustomobject]@{ secret = [pscustomobject]@{ value = $true } }
    $paths = @(Get-ChangedAttributePathsLinear -Before $before -After $after -BeforeSensitive $sensitiveMask -AfterSensitive $sensitiveMask -AfterUnknown $null -Path 'root' -Budget $budget)
    if ($paths -notcontains 'root.safe' -or $paths -notcontains 'root.secret.value.<sensitive>') {
        throw 'SELFTEST_ATTRIBUTE_PATH_CLASSIFICATION_FAILED'
    }
    $serializedPaths = $paths | ConvertTo-Json -Compress
    if ($serializedPaths -match 'DO_NOT_LEAK_OLD|DO_NOT_LEAK_NEW') {
        throw 'SELFTEST_SENSITIVE_VALUE_LEAK_FAILED'
    }

    $largeBeforeMap = [ordered]@{}
    $largeAfterMap = [ordered]@{}
    for ($i = 0; $i -lt 2000; $i++) {
        $name = ('p{0:D4}' -f $i)
        $largeBeforeMap[$name] = $i
        $largeAfterMap[$name] = $i
    }
    $largeAfterMap['p1999'] = 999999
    $largeBudget = @{
        Nodes          = 0
        MaxNodes       = 10000
        MaxDepth       = 32
        TimeoutSeconds = 5
        DeadlineUtc    = [DateTime]::UtcNow.AddSeconds(5)
    }
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $largePaths = @(Get-ChangedAttributePathsLinear -Before ([pscustomobject]$largeBeforeMap) -After ([pscustomobject]$largeAfterMap) -BeforeSensitive $null -AfterSensitive $null -AfterUnknown $null -Path 'root' -Budget $largeBudget)
    $stopwatch.Stop()
    if ($largePaths.Count -ne 1 -or $largePaths[0] -ne 'root.p1999' -or $stopwatch.Elapsed.TotalSeconds -gt 5) {
        throw 'SELFTEST_LINEAR_DIFF_FAILED'
    }

    $fixtureScript = @'
$ExpectedConfigCommit = '4b47fe25bb89c5733783920b1f8497c7dfadbb92'
& terraform ("-chdir={0}" -f $terraformDirectory) plan -input=false -detailed-exitcode -no-color ("-out={0}" -f $planPath) *> $planLog
'@
    $patchedFixture = Patch-DiagnosticScriptText $fixtureScript
    if ($patchedFixture -notmatch [regex]::Escape($TargetConfigCommit) -or $patchedFixture -notmatch 'plan -refresh=false -lock-timeout=15s') {
        throw 'SELFTEST_BASE_SCRIPT_PATCH_FAILED'
    }

    Write-Host 'SELFTEST=PASS'
    Write-Host 'LINEAR_DIFF=PASS'
    Write-Host 'PROCESS_TIMEOUT_GUARD=CONFIGURED'
    Write-Host 'NETWORK_CALLED=false'
    Write-Host 'AZURE_CALLED=false'
    Write-Host 'TERRAFORM_CALLED=false'
    Write-Host 'SECRET_VALUES_OUTPUT=false'
    Write-Host 'MUTATION=false'
    exit 0
}

$pwshPath = Require-Command 'pwsh'
$terraformPath = Require-Command 'terraform'

$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$workRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("soaiacore-p0-attribute-diagnostic-v2-{0}" -f $stamp)
New-Item -ItemType Directory -Path $workRoot -Force | Out-Null
$baseScriptPath = Join-Path $workRoot 'Invoke-P0RecoveryDiagnosticPlan.pinned.ps1'
$baseFailurePath = Join-Path $workRoot 'base-diagnostic.failure.log'
$attributeReceiptPath = Join-Path $HOME ("SOAIACORE_38_ATTRIBUTE_PATHS_V2_{0}.sanitized.json" -f $stamp)
$successful = $false
$basePlanWorkRoot = $null

try {
    Write-Host 'PHASE=PREPARE_BASE_DIAGNOSTIC START'
    $downloadPath = Join-Path $workRoot 'base.ps1'
    Invoke-WebRequest -UseBasicParsing $BaseDiagnosticUrl -OutFile $downloadPath
    $baseText = Get-Content -LiteralPath $downloadPath -Raw
    $patchedText = Patch-DiagnosticScriptText $baseText
    Set-Content -LiteralPath $baseScriptPath -Value $patchedText -Encoding utf8
    Write-Host 'PHASE=PREPARE_BASE_DIAGNOSTIC DONE'

    Write-Host 'PHASE=BASE_DIAGNOSTIC START'
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

    $planPath = [string]$baseReceipt.diagnostic_plan_file
    if ([string]::IsNullOrWhiteSpace($planPath) -or -not (Test-Path -LiteralPath $planPath -PathType Leaf)) {
        Stop-Gate 'STOP_PLAN_FILE_MISSING' 'Saved diagnostic plan file is unavailable for attribute-path inspection.'
    }
    $planEvidenceDir = Split-Path -Parent $planPath
    $basePlanWorkRoot = Split-Path -Parent $planEvidenceDir
    $terraformDirectory = Join-Path $basePlanWorkRoot 'repo\infra\azure\p0'
    if (-not (Test-Path -LiteralPath $terraformDirectory -PathType Container)) {
        Stop-Gate 'STOP_TERRAFORM_DIR_MISSING' 'Pinned Terraform working directory is unavailable.'
    }

    if ([int]$baseReceipt.action_counts.delete -gt 0 -or [int]$baseReceipt.action_counts.replace -gt 0) {
        Stop-Gate 'STOP_DESTRUCTIVE_PLAN' 'Base plan contains delete or replace actions; attribute review halted.'
    }

    Write-Host 'PHASE=TERRAFORM_SHOW_JSON START'
    $showProcess = Invoke-ProcessTextWithTimeout -FilePath $terraformPath -Arguments @(("-chdir={0}" -f $terraformDirectory),'show','-json',$planPath) -TimeoutSeconds $TerraformShowTimeoutSeconds -Label 'Terraform show JSON'
    if ($showProcess.ExitCode -ne 0) {
        Stop-Gate 'STOP_PLAN_JSON_READ_FAILED' ("Terraform show -json failed with exit code {0}." -f $showProcess.ExitCode)
    }
    try { $planJson = $showProcess.StdOut | ConvertFrom-Json -Depth 100 }
    catch { Stop-Gate 'STOP_PLAN_JSON_PARSE' 'Saved plan JSON could not be parsed in memory.' }
    $showProcess = $null
    Write-Host 'PHASE=TERRAFORM_SHOW_JSON DONE'

    Write-Host 'PHASE=ATTRIBUTE_DIFF START'
    $changedAddressSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($row in @($baseReceipt.changed_resources)) {
        [void]$changedAddressSet.Add([string]$row.address)
    }

    $budget = @{
        Nodes          = 0
        MaxNodes       = $DiffMaxNodes
        MaxDepth       = $DiffMaxDepth
        TimeoutSeconds = $DiffTimeoutSeconds
        DeadlineUtc    = [DateTime]::UtcNow.AddSeconds($DiffTimeoutSeconds)
    }
    $resourceRows = @()
    foreach ($resourceChange in @($planJson.resource_changes)) {
        $address = [string]$resourceChange.address
        if (-not $changedAddressSet.Contains($address)) { continue }
        $actions = @($resourceChange.change.actions)
        $pathArgs = @{
            Before          = $resourceChange.change.before
            After           = $resourceChange.change.after
            BeforeSensitive = $resourceChange.change.before_sensitive
            AfterSensitive  = $resourceChange.change.after_sensitive
            AfterUnknown    = $resourceChange.change.after_unknown
            Path            = ''
            Budget          = $budget
            Depth           = 0
        }
        $paths = @(Get-ChangedAttributePathsLinear @pathArgs)
        $resourceRows += [ordered]@{
            address         = $address
            actions         = $actions
            attribute_paths = @($paths | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Sort-Object -Unique)
        }
    }
    $planJson = $null
    Write-Host ("PHASE=ATTRIBUTE_DIFF DONE nodes={0}" -f $budget.Nodes)

    $attributeReceipt = [ordered]@{
        schema                                        = 'SOAIACORE_38_RECOVERY_ATTRIBUTE_PATHS_V2'
        recorded_utc                                  = (Get-Date).ToUniversalTime().ToString('o')
        config_commit                                 = $TargetConfigCommit
        base_diagnostic_commit                        = $BaseDiagnosticCommit
        terraform_refresh                             = $false
        terraform_lock_timeout_seconds                = 15
        state_address_count                           = [int]$baseReceipt.state_address_count
        plan_exit_code                                = [int]$baseReceipt.plan_exit_code
        plan_sha256                                   = [string]$baseReceipt.plan_sha256
        plan_gate                                     = [string]$baseReceipt.plan_gate
        action_counts                                 = $baseReceipt.action_counts
        changed_resources                             = $resourceRows
        attribute_diff_nodes_visited                  = [int]$budget.Nodes
        attribute_values_output                       = $false
        secret_values_output                          = $false
        raw_plan_json_persisted                       = $false
        terraform_apply_executed                      = $false
        mutation                                      = $false
        human_adjudication_required_before_any_apply  = $true
    }
    $attributeReceipt | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $attributeReceiptPath -Encoding utf8
    $attributeReceiptHash = (Get-FileHash -LiteralPath $attributeReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()

    Write-Host ''
    Write-Host '=== SOAIACORE #38 ATTRIBUTE-PATH DIAGNOSTIC V2 ==='
    Write-Host ("CONFIG_COMMIT={0}" -f $TargetConfigCommit)
    Write-Host ("STATE_ADDRESS_COUNT={0}" -f $baseReceipt.state_address_count)
    Write-Host ("PLAN_EXIT_CODE={0}" -f $baseReceipt.plan_exit_code)
    Write-Host ("CREATE_COUNT={0}" -f $baseReceipt.action_counts.create)
    Write-Host ("UPDATE_COUNT={0}" -f $baseReceipt.action_counts.update)
    Write-Host ("DELETE_COUNT={0}" -f $baseReceipt.action_counts.delete)
    Write-Host ("REPLACE_COUNT={0}" -f $baseReceipt.action_counts.replace)
    Write-Host ("PLAN_GATE={0}" -f $baseReceipt.plan_gate)
    Write-Host ("PLAN_SHA256={0}" -f $baseReceipt.plan_sha256)
    Write-Host ("ATTRIBUTE_DIFF_NODES={0}" -f $budget.Nodes)
    Write-Host ("BASE_SANITIZED_RECEIPT={0}" -f $baseReceiptPath)
    Write-Host ("ATTRIBUTE_PATH_RECEIPT={0}" -f $attributeReceiptPath)
    Write-Host ("ATTRIBUTE_PATH_RECEIPT_SHA256={0}" -f $attributeReceiptHash)
    Write-Host 'TERRAFORM_REFRESH=false'
    Write-Host 'LOCK_TIMEOUT_SECONDS=15'
    Write-Host 'ATTRIBUTE_VALUES_OUTPUT=false'
    Write-Host 'SECRET_VALUES_OUTPUT=false'
    Write-Host 'RAW_PLAN_JSON_PERSISTED=false'
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
