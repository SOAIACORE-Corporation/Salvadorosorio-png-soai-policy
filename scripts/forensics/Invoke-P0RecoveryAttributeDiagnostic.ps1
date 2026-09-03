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

function Test-TrueMask {
    param($Value)
    return ($Value -is [bool] -and [bool]$Value)
}

function Test-ListNode {
    param($Value)
    if ($null -eq $Value -or $Value -is [string] -or $Value -is [System.Collections.IDictionary] -or $Value -is [pscustomobject]) {
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

function Test-DeepEqual {
    param($Left, $Right)
    if ($null -eq $Left -and $null -eq $Right) { return $true }
    if ($null -eq $Left -or $null -eq $Right) { return $false }
    $leftJson = ConvertTo-Json -InputObject $Left -Depth 100 -Compress
    $rightJson = ConvertTo-Json -InputObject $Right -Depth 100 -Compress
    return ($leftJson -ceq $rightJson)
}

function Join-AttributePath {
    param([string]$Base, [string]$Token)
    if ([string]::IsNullOrWhiteSpace($Base)) { return $Token }
    if ($Token.StartsWith('[')) { return ("{0}{1}" -f $Base, $Token) }
    return ("{0}.{1}" -f $Base, $Token)
}

function Get-ChangedAttributePaths {
    param(
        $Before,
        $After,
        $BeforeSensitive,
        $AfterSensitive,
        $AfterUnknown,
        [string]$Path
    )

    if (Test-TrueMask $AfterUnknown) {
        if ((Test-TrueMask $BeforeSensitive) -or (Test-TrueMask $AfterSensitive)) {
            return @((Join-AttributePath $Path '<sensitive-unknown>'))
        }
        return @((Join-AttributePath $Path '<unknown>'))
    }

    if (Test-DeepEqual $Before $After) {
        return @()
    }

    if ((Test-TrueMask $BeforeSensitive) -or (Test-TrueMask $AfterSensitive)) {
        return @((Join-AttributePath $Path '<sensitive>'))
    }

    $beforeProperties = @(Get-PropertyNames $Before)
    $afterProperties = @(Get-PropertyNames $After)
    if ($beforeProperties.Count -gt 0 -or $afterProperties.Count -gt 0) {
        $allNames = @($beforeProperties + $afterProperties | Sort-Object -Unique)
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

            $result += @(Get-ChangedAttributePaths \
                -Before $beforeChild.Value \
                -After $afterChild.Value \
                -BeforeSensitive $beforeSensitiveChild.Value \
                -AfterSensitive $afterSensitiveChild.Value \
                -AfterUnknown $afterUnknownChild.Value \
                -Path $childPath)
        }
        return @($result | Sort-Object -Unique)
    }

    if ((Test-ListNode $Before) -or (Test-ListNode $After)) {
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
            $result += @(Get-ChangedAttributePaths \
                -Before $beforeList[$i] \
                -After $afterList[$i] \
                -BeforeSensitive $(if ($i -lt $beforeSensitiveList.Count) { $beforeSensitiveList[$i] } else { $null }) \
                -AfterSensitive $(if ($i -lt $afterSensitiveList.Count) { $afterSensitiveList[$i] } else { $null }) \
                -AfterUnknown $(if ($i -lt $afterUnknownList.Count) { $afterUnknownList[$i] } else { $null }) \
                -Path $childPath)
        }
        return @($result | Sort-Object -Unique)
    }

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
    $newPlan = '& terraform ("-chdir={0}" -f $terraformDirectory) plan -refresh=false -input=false -detailed-exitcode -no-color ("-out={0}" -f $planPath) *> $planLog'
    if ([regex]::Matches($patched, [regex]::Escape($oldPlan)).Count -ne 1) {
        Stop-Gate 'STOP_BASE_SCRIPT_PLAN_MISMATCH' 'Expected exactly one Terraform plan invocation in the base diagnostic script.'
    }
    return $patched.Replace($oldPlan, $newPlan)
}

if ($SelfTest) {
    $before = [pscustomobject]@{
        safe = 'old'
        secret = [pscustomobject]@{ value = 'DO_NOT_LEAK_OLD' }
        stable = 'same'
    }
    $after = [pscustomobject]@{
        safe = 'new'
        secret = [pscustomobject]@{ value = 'DO_NOT_LEAK_NEW' }
        stable = 'same'
    }
    $sensitiveMask = [pscustomobject]@{ secret = [pscustomobject]@{ value = $true } }
    $paths = @(Get-ChangedAttributePaths -Before $before -After $after -BeforeSensitive $sensitiveMask -AfterSensitive $sensitiveMask -AfterUnknown $null -Path 'root')
    if ($paths -notcontains 'root.safe' -or $paths -notcontains 'root.secret.value.<sensitive>') {
        throw 'SELFTEST_ATTRIBUTE_PATH_CLASSIFICATION_FAILED'
    }
    $serializedPaths = $paths | ConvertTo-Json -Compress
    if ($serializedPaths -match 'DO_NOT_LEAK_OLD|DO_NOT_LEAK_NEW') {
        throw 'SELFTEST_SENSITIVE_VALUE_LEAK_FAILED'
    }

    $fixtureScript = @'
$ExpectedConfigCommit = '4b47fe25bb89c5733783920b1f8497c7dfadbb92'
& terraform ("-chdir={0}" -f $terraformDirectory) plan -input=false -detailed-exitcode -no-color ("-out={0}" -f $planPath) *> $planLog
'@
    $patchedFixture = Patch-DiagnosticScriptText $fixtureScript
    if ($patchedFixture -notmatch [regex]::Escape($TargetConfigCommit) -or $patchedFixture -notmatch 'plan -refresh=false') {
        throw 'SELFTEST_BASE_SCRIPT_PATCH_FAILED'
    }

    Write-Host 'SELFTEST=PASS'
    Write-Host 'NETWORK_CALLED=false'
    Write-Host 'AZURE_CALLED=false'
    Write-Host 'TERRAFORM_CALLED=false'
    Write-Host 'SECRET_VALUES_OUTPUT=false'
    Write-Host 'MUTATION=false'
    exit 0
}

Require-Command 'pwsh'
Require-Command 'terraform'

$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$workRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("soaiacore-p0-attribute-diagnostic-{0}" -f $stamp)
New-Item -ItemType Directory -Path $workRoot -Force | Out-Null
$baseScriptPath = Join-Path $workRoot 'Invoke-P0RecoveryDiagnosticPlan.pinned.ps1'
$attributeReceiptPath = Join-Path $HOME ("SOAIACORE_38_ATTRIBUTE_PATHS_{0}.sanitized.json" -f $stamp)

try {
    $downloadPath = Join-Path $workRoot 'base.ps1'
    Invoke-WebRequest -UseBasicParsing $BaseDiagnosticUrl -OutFile $downloadPath
    $baseText = Get-Content -LiteralPath $downloadPath -Raw
    $patchedText = Patch-DiagnosticScriptText $baseText
    Set-Content -LiteralPath $baseScriptPath -Value $patchedText -Encoding utf8

    $diagnosticOutput = @(& pwsh -NoProfile -ExecutionPolicy Bypass -File $baseScriptPath 2>&1)
    $diagnosticExitCode = $LASTEXITCODE
    if ($diagnosticExitCode -ne 0) {
        $diagnosticOutput | ForEach-Object { Write-Host ([string]$_) }
        Stop-Gate 'STOP_BASE_DIAGNOSTIC_FAILED' ("Pinned base diagnostic failed with exit code {0}." -f $diagnosticExitCode)
    }

    $outputLines = @($diagnosticOutput | ForEach-Object { [string]$_ })
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
    $planWorkRoot = Split-Path -Parent $planEvidenceDir
    $terraformDirectory = Join-Path $planWorkRoot 'repo\infra\azure\p0'
    if (-not (Test-Path -LiteralPath $terraformDirectory -PathType Container)) {
        Stop-Gate 'STOP_TERRAFORM_DIR_MISSING' 'Pinned Terraform working directory is unavailable.'
    }

    $nativePreferenceDefined = Test-Path Variable:PSNativeCommandUseErrorActionPreference
    if ($nativePreferenceDefined) {
        $savedNativePreference = $PSNativeCommandUseErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $false
    }
    try {
        $planJsonLines = @(& terraform ("-chdir={0}" -f $terraformDirectory) show -json $planPath 2>$null)
        $showExitCode = $LASTEXITCODE
    }
    finally {
        if ($nativePreferenceDefined) {
            $PSNativeCommandUseErrorActionPreference = $savedNativePreference
        }
    }
    if ($showExitCode -ne 0) {
        Stop-Gate 'STOP_PLAN_JSON_READ_FAILED' ("Terraform show -json failed with exit code {0}." -f $showExitCode)
    }

    $planJsonText = ($planJsonLines -join [Environment]::NewLine)
    try { $planJson = $planJsonText | ConvertFrom-Json -Depth 100 }
    catch { Stop-Gate 'STOP_PLAN_JSON_PARSE' 'Saved plan JSON could not be parsed in memory.' }
    $planJsonLines = $null
    $planJsonText = $null

    $resourceRows = @()
    foreach ($resourceChange in @($planJson.resource_changes)) {
        $actions = @($resourceChange.change.actions)
        if ($actions -contains 'no-op') { continue }
        $paths = @(Get-ChangedAttributePaths \
            -Before $resourceChange.change.before \
            -After $resourceChange.change.after \
            -BeforeSensitive $resourceChange.change.before_sensitive \
            -AfterSensitive $resourceChange.change.after_sensitive \
            -AfterUnknown $resourceChange.change.after_unknown \
            -Path '')
        $resourceRows += [ordered]@{
            address = [string]$resourceChange.address
            actions = $actions
            attribute_paths = @($paths | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Sort-Object -Unique)
        }
    }
    $planJson = $null

    $attributeReceipt = [ordered]@{
        schema = 'SOAIACORE_38_RECOVERY_ATTRIBUTE_PATHS_V1'
        recorded_utc = (Get-Date).ToUniversalTime().ToString('o')
        config_commit = $TargetConfigCommit
        base_diagnostic_commit = $BaseDiagnosticCommit
        terraform_refresh = $false
        state_address_count = [int]$baseReceipt.state_address_count
        plan_exit_code = [int]$baseReceipt.plan_exit_code
        plan_sha256 = [string]$baseReceipt.plan_sha256
        plan_gate = [string]$baseReceipt.plan_gate
        action_counts = $baseReceipt.action_counts
        changed_resources = $resourceRows
        attribute_values_output = $false
        secret_values_output = $false
        raw_plan_json_persisted = $false
        terraform_apply_executed = $false
        mutation = $false
        human_adjudication_required_before_any_apply = $true
    }
    $attributeReceipt | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $attributeReceiptPath -Encoding utf8
    $attributeReceiptHash = (Get-FileHash -LiteralPath $attributeReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()

    Write-Host ''
    Write-Host '=== SOAIACORE #38 ATTRIBUTE-PATH DIAGNOSTIC ==='
    Write-Host ("CONFIG_COMMIT={0}" -f $TargetConfigCommit)
    Write-Host ("STATE_ADDRESS_COUNT={0}" -f $baseReceipt.state_address_count)
    Write-Host ("PLAN_EXIT_CODE={0}" -f $baseReceipt.plan_exit_code)
    Write-Host ("CREATE_COUNT={0}" -f $baseReceipt.action_counts.create)
    Write-Host ("UPDATE_COUNT={0}" -f $baseReceipt.action_counts.update)
    Write-Host ("DELETE_COUNT={0}" -f $baseReceipt.action_counts.delete)
    Write-Host ("REPLACE_COUNT={0}" -f $baseReceipt.action_counts.replace)
    Write-Host ("PLAN_GATE={0}" -f $baseReceipt.plan_gate)
    Write-Host ("PLAN_SHA256={0}" -f $baseReceipt.plan_sha256)
    Write-Host ("BASE_SANITIZED_RECEIPT={0}" -f $baseReceiptPath)
    Write-Host ("ATTRIBUTE_PATH_RECEIPT={0}" -f $attributeReceiptPath)
    Write-Host ("ATTRIBUTE_PATH_RECEIPT_SHA256={0}" -f $attributeReceiptHash)
    Write-Host 'TERRAFORM_REFRESH=false'
    Write-Host 'ATTRIBUTE_VALUES_OUTPUT=false'
    Write-Host 'SECRET_VALUES_OUTPUT=false'
    Write-Host 'RAW_PLAN_JSON_PERSISTED=false'
    Write-Host 'APPLY_EXECUTED=false'
    Write-Host 'MUTATION=false'
    Write-Host 'DONE=true'
}
finally {
    Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue
}
