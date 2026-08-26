#requires -Version 5.1
<#
SOAIACORE Rebuild P0 — Docker/WSL Diagnostic One-Shot v1.2
Read-only diagnostic guardrail for Docker Desktop / WSL context mismatches.

v1.2 fixes two diagnostic defects observed on Windows PowerShell 5.1:
1) WSL native output can contain NUL/UTF-16-style text that defeats regex parsing.
2) HOST_WSL_FAILURE must never override a successful docker-desktop execution probe.

This script does not update/reinstall/reset/unregister WSL or Docker, does not
reboot Windows, does not change backend/BIOS/PATH, does not delete Docker/WSL
data, and never performs Azure apply or creates cloud resources.
#>

[CmdletBinding()]
param(
    [string]$RepoPath = (Get-Location).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Architecture = 'v0.6 FINAL / FROZEN FOR P0'
$DiagnosticVersion = '1.2'
$StateRoot = Join-Path $env:ProgramData 'SOAIACORE\RebuildP0'
$DiagRoot = Join-Path $StateRoot 'diagnostics'
$ReceiptDir = Join-Path $RepoPath 'receipts'
$WslExe = Join-Path $env:SystemRoot 'System32\wsl.exe'
$StartUtc = (Get-Date).ToUniversalTime()

foreach ($p in @($StateRoot,$DiagRoot,$ReceiptDir)) {
    if (-not (Test-Path -LiteralPath $p)) {
        New-Item -ItemType Directory -Path $p -Force | Out-Null
    }
}

$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Transcript = Join-Path $DiagRoot "docker-wsl-diagnostic-$Stamp.log"
Start-Transcript -Path $Transcript -Append | Out-Null

function Normalize-NativeText {
    param([AllowNull()][object]$Value)
    if ($null -eq $Value) { return '' }
    $text = [string]$Value
    # WSL output observed under Windows PowerShell 5.1 may contain embedded NULs.
    $text = $text.Replace([string][char]0, '')
    # Remove BOM/replacement artifacts without changing substantive text.
    $text = $text.TrimStart([char]0xFEFF)
    return $text.TrimEnd()
}

function Invoke-Capture {
    param(
        [string]$Name,
        [scriptblock]$Script
    )

    $output = @()
    $exitCode = 0
    $errorText = ''
    $previousPreference = $ErrorActionPreference

    try {
        # Native stderr is evidence, not a terminating PowerShell exception.
        $ErrorActionPreference = 'Continue'
        $global:LASTEXITCODE = 0
        $raw = @(& $Script 2>&1)
        $exitCode = [int]$global:LASTEXITCODE
        $output = @($raw | ForEach-Object { Normalize-NativeText $_ })
    } catch {
        $exitCode = 1
        $errorText = Normalize-NativeText $_.Exception.Message
        $output = @($output + $errorText)
    } finally {
        $ErrorActionPreference = $previousPreference
    }

    return [pscustomobject]@{
        name = $Name
        exit_code = $exitCode
        output = @($output)
        error = $errorText
    }
}

function Get-WslSemanticVersion {
    param([object[]]$Lines)
    $joined = (@($Lines | ForEach-Object { Normalize-NativeText $_ }) -join "`n")
    if ($joined -match '(?i)(?:WSL|versi[oó]n\s+de\s+WSL)[^0-9]*([0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?)') {
        return $Matches[1]
    }
    if ($joined -match '([0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?)') {
        return $Matches[1]
    }
    return ''
}

function Test-VersionAtLeast {
    param([string]$Actual,[string]$Minimum)
    try { return ([version]$Actual -ge [version]$Minimum) } catch { return $false }
}

function Find-DockerCli {
    $cmd = Get-Command docker.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidate = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    return ''
}

function Get-ProcessOwnerSafe {
    param([uint32]$ProcessId)
    try {
        $p = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction Stop
        $owner = Invoke-CimMethod -InputObject $p -MethodName GetOwner -ErrorAction Stop
        if ($owner.ReturnValue -eq 0) { return "$($owner.Domain)\$($owner.User)" }
    } catch { }
    return ''
}

function Get-RelevantDockerLogs {
    $result = @()
    $roots = @(
        (Join-Path $env:LOCALAPPDATA 'Docker\log'),
        (Join-Path $env:APPDATA 'Docker\log')
    ) | Where-Object { Test-Path -LiteralPath $_ }

    foreach ($root in @($roots)) {
        $files = @(Get-ChildItem -LiteralPath $root -File -Recurse -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 30)

        foreach ($file in $files) {
            try {
                $hits = @(Select-String -LiteralPath $file.FullName -Pattern 'wslUpdateRequired|wsl\.exe|--version|exit status 1|exit=1|backend|engine|nested virtualization|virtualizaci.n anidada' -SimpleMatch:$false -ErrorAction SilentlyContinue |
                    Select-Object -Last 20)
                foreach ($hit in $hits) {
                    $result += [pscustomobject]@{
                        file = $file.FullName
                        line = [int]$hit.LineNumber
                        text = (Normalize-NativeText $hit.Line)
                    }
                    if ($result.Count -ge 120) { return @($result) }
                }
            } catch { }
        }
    }
    return @($result)
}

function Get-WslConfigSignal {
    $path = Join-Path $env:USERPROFILE '.wslconfig'
    $signal = [pscustomobject]@{
        path = $path
        exists = $false
        nested_virtualization = 'UNSET'
    }
    if (-not (Test-Path -LiteralPath $path)) { return $signal }

    $signal.exists = $true
    try {
        foreach ($line in @(Get-Content -LiteralPath $path -ErrorAction Stop)) {
            if ($line -match '^\s*nestedVirtualization\s*=\s*(true|false)\s*(?:#.*)?$') {
                $signal.nested_virtualization = $Matches[1].ToLowerInvariant()
                break
            }
        }
    } catch { }
    return $signal
}

Write-Host "SOAIACORE Docker/WSL diagnostic guardrail v$DiagnosticVersion: READ-ONLY"

$diag = [ordered]@{}
$diag.diagnostic_version = $DiagnosticVersion
$diag.architecture = $Architecture
$diag.started_at_utc = $StartUtc.ToString('o')
$diag.host = $env:COMPUTERNAME
$diag.azure_apply_executed = $false
$diag.cloud_resources_created = 0
$diag.wsl_expected_path = $WslExe
$diag.wsl_config_signal = Get-WslConfigSignal

$diag.where_wsl = Invoke-Capture 'where.exe wsl.exe' { where.exe wsl.exe }
$diag.get_command_wsl = [pscustomobject]@{ name='Get-Command wsl.exe -All'; exit_code=0; output=@(); error='' }
try {
    $diag.get_command_wsl.output = @(Get-Command wsl.exe -All -ErrorAction Stop | ForEach-Object { Normalize-NativeText $_.Source })
} catch {
    $diag.get_command_wsl.exit_code = 1
    $diag.get_command_wsl.error = Normalize-NativeText $_.Exception.Message
}

if (-not (Test-Path -LiteralPath $WslExe)) {
    $diag.wsl_version = [pscustomobject]@{ name='System32 wsl --version'; exit_code=1; output=@('System32 wsl.exe missing'); error='WSL_EXE_MISSING' }
    $diag.wsl_status = [pscustomobject]@{ name='System32 wsl --status'; exit_code=1; output=@(); error='WSL_EXE_MISSING' }
    $diag.wsl_list = [pscustomobject]@{ name='System32 wsl -l -v'; exit_code=1; output=@(); error='WSL_EXE_MISSING' }
    $diag.docker_desktop_wsl_probe = [pscustomobject]@{ name='docker-desktop probe'; exit_code=1; output=@(); error='WSL_EXE_MISSING' }
} else {
    $diag.wsl_version = Invoke-Capture 'System32 wsl --version' { & $WslExe --version }
    $diag.wsl_status = Invoke-Capture 'System32 wsl --status' { & $WslExe --status }
    $diag.wsl_list = Invoke-Capture 'System32 wsl -l -v' { & $WslExe -l -v }
    $diag.docker_desktop_wsl_probe = Invoke-Capture 'docker-desktop WSL probe' { & $WslExe -d docker-desktop echo SOAIACORE_WSL_BACKEND_PROBE_PASS }
}

$wslSemanticVersion = Get-WslSemanticVersion @($diag.wsl_version.output)
$wslVersionCommandOk = ($diag.wsl_version.exit_code -eq 0)
$wslStatusCommandOk = ($diag.wsl_status.exit_code -eq 0)
$wslListCommandOk = ($diag.wsl_list.exit_code -eq 0)
$wslVersionMeetsMinimum = (-not [string]::IsNullOrWhiteSpace($wslSemanticVersion) -and (Test-VersionAtLeast $wslSemanticVersion '2.1.5'))

$probeText = (@($diag.docker_desktop_wsl_probe.output | ForEach-Object { Normalize-NativeText $_ }) -join ' ')
$dockerDesktopProbePass = ($probeText -match 'SOAIACORE_WSL_BACKEND_PROBE_PASS')
$nestedWarningObserved = ($probeText -match '(?i)nested virtualization is not supported|no se admite la virtualizaci.n anidada')

# Host WSL operational state is corroborated. A successful docker-desktop probe
# is stronger runtime evidence than a parser failure in `wsl --version`.
$wslOperational = ($dockerDesktopProbePass -or $wslVersionCommandOk -or $wslStatusCommandOk -or $wslListCommandOk)
$wslDirectHealthy = ($wslVersionMeetsMinimum -or ($dockerDesktopProbePass -and $wslVersionCommandOk))

if ($wslVersionMeetsMinimum) {
    $wslVersionParseStatus = 'PARSED_AND_MEETS_MINIMUM'
} elseif ($wslVersionCommandOk -and [string]::IsNullOrWhiteSpace($wslSemanticVersion)) {
    $wslVersionParseStatus = 'UNPARSED_BUT_COMMAND_SUCCEEDED'
} elseif (-not [string]::IsNullOrWhiteSpace($wslSemanticVersion)) {
    $wslVersionParseStatus = 'PARSED_BELOW_MINIMUM_OR_INVALID'
} else {
    $wslVersionParseStatus = 'COMMAND_FAILED_OR_NO_VERSION'
}

$diag.wsl_semantic_version = $wslSemanticVersion
$diag.wsl_minimum_for_guardrail = '2.1.5'
$diag.wsl_version_command_ok = $wslVersionCommandOk
$diag.wsl_status_command_ok = $wslStatusCommandOk
$diag.wsl_list_command_ok = $wslListCommandOk
$diag.wsl_version_meets_minimum = $wslVersionMeetsMinimum
$diag.wsl_version_parse_status = $wslVersionParseStatus
$diag.wsl_operational = $wslOperational
$diag.wsl_direct_healthy = $wslDirectHealthy
$diag.wsl_nested_virtualization_warning_observed = $nestedWarningObserved
$diag.docker_desktop_wsl_probe_pass = $dockerDesktopProbePass

$docker = Find-DockerCli
$diag.docker_cli_path = $docker
if ($docker) {
    $diag.docker_version = Invoke-Capture 'docker version' { & $docker version }
    $diag.docker_info = Invoke-Capture 'docker info' { & $docker info }
    $diag.docker_compose = Invoke-Capture 'docker compose version' { & $docker compose version }
    $diag.docker_desktop_cli_version = Invoke-Capture 'docker desktop version' { & $docker desktop version }
    $diag.docker_desktop_cli_status = Invoke-Capture 'docker desktop status' { & $docker desktop status }
} else {
    $diag.docker_version = [pscustomobject]@{ name='docker version'; exit_code=1; output=@('Docker CLI not found'); error='DOCKER_CLI_NOT_FOUND' }
    $diag.docker_info = [pscustomobject]@{ name='docker info'; exit_code=1; output=@(); error='DOCKER_CLI_NOT_FOUND' }
    $diag.docker_compose = [pscustomobject]@{ name='docker compose version'; exit_code=1; output=@(); error='DOCKER_CLI_NOT_FOUND' }
    $diag.docker_desktop_cli_version = [pscustomobject]@{ name='docker desktop version'; exit_code=1; output=@(); error='DOCKER_CLI_NOT_FOUND' }
    $diag.docker_desktop_cli_status = [pscustomobject]@{ name='docker desktop status'; exit_code=1; output=@(); error='DOCKER_CLI_NOT_FOUND' }
}

$service = Get-Service 'com.docker.service' -ErrorAction SilentlyContinue
$diag.docker_service = if ($service) {
    [pscustomobject]@{ exists=$true; status="$($service.Status)"; start_type="$($service.StartType)" }
} else {
    [pscustomobject]@{ exists=$false; status=''; start_type='' }
}

$backendRows = @()
try {
    $backendRows = @(Get-CimInstance Win32_Process -Filter "Name='com.docker.backend.exe'" -ErrorAction Stop | ForEach-Object {
        [pscustomobject]@{
            process_id = [uint32]$_.ProcessId
            parent_process_id = [uint32]$_.ParentProcessId
            executable_path = Normalize-NativeText $_.ExecutablePath
            command_line = Normalize-NativeText $_.CommandLine
            owner = (Get-ProcessOwnerSafe -ProcessId $_.ProcessId)
        }
    })
} catch { }
$diag.docker_backend_processes = @($backendRows)
$diag.relevant_docker_log_matches = @(Get-RelevantDockerLogs)

$engineReady = ($diag.docker_info.exit_code -eq 0)
$backendMismatchSignal = $false
foreach ($m in @($diag.relevant_docker_log_matches)) {
    $t = Normalize-NativeText $m.text
    if ($t -match 'wslUpdateRequired' -or ($t -match 'wsl\.exe' -and $t -match '(--version|exit status 1|exit=1)')) {
        $backendMismatchSignal = $true
        break
    }
}

# Evidence precedence: Engine > successful docker-desktop execution probe >
# corroborated host WSL commands > parser-only interpretation.
if ($engineReady) {
    $classification = 'DOCKER_ENGINE_READY'
    $blocker = ''
} elseif ($dockerDesktopProbePass -and $backendMismatchSignal) {
    $classification = 'DOCKER_BACKEND_WSL_CONTEXT_MISMATCH'
    $blocker = 'DOCKER_BACKEND_WSL_CONTEXT_MISMATCH: docker-desktop executes successfully while Docker backend reports contradictory WSL version/update evidence'
} elseif ($dockerDesktopProbePass) {
    $classification = 'DOCKER_ENGINE_NOT_READY_DIAGNOSTIC_CAPTURED'
    $blocker = 'DOCKER_ENGINE_NOT_READY_DIAGNOSTIC_CAPTURED: WSL and docker-desktop execution are operational but Docker Engine server is unavailable'
} elseif (-not $wslOperational) {
    $classification = 'HOST_WSL_FAILURE'
    $blocker = 'HOST_WSL_FAILURE: direct WSL version/status/list and docker-desktop execution probe all failed'
} else {
    $classification = 'DOCKER_DESKTOP_WSL_DISTRO_FAILURE'
    $blocker = 'DOCKER_DESKTOP_WSL_DISTRO_FAILURE: host WSL has corroborating operational evidence but docker-desktop did not complete its execution probe'
}

$diag.classification = $classification
$diag.blocker = $blocker
$diag.docker_engine_ready = $engineReady
$diag.backend_context_mismatch_signal = $backendMismatchSignal
$diag.ended_at_utc = (Get-Date).ToUniversalTime().ToString('o')
$diag.transcript = $Transcript

$jsonPath = Join-Path $ReceiptDir 'DOCKER_WSL_DIAGNOSTIC_2026-08-23.json'
$mdPath = Join-Path $ReceiptDir 'DOCKER_WSL_DIAGNOSTIC_2026-08-23.md'

try {
    $diag | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    @"
# SOAIACORE Docker/WSL Diagnostic Receipt

- Diagnostic version: ``$DiagnosticVersion``
- Classification: ``$classification``
- Blocker: ``$blocker``
- Architecture: ``$Architecture``
- Host: ``$env:COMPUTERNAME``
- WSL version exit: ``$($diag.wsl_version.exit_code)``
- WSL status exit: ``$($diag.wsl_status.exit_code)``
- WSL list exit: ``$($diag.wsl_list.exit_code)``
- Parsed WSL version: ``$wslSemanticVersion``
- WSL version parse status: ``$wslVersionParseStatus``
- WSL operational: ``$wslOperational``
- WSL direct healthy: ``$wslDirectHealthy``
- WSL nested-virtualization warning observed: ``$nestedWarningObserved``
- .wslconfig nestedVirtualization: ``$($diag.wsl_config_signal.nested_virtualization)``
- docker-desktop execution probe pass: ``$dockerDesktopProbePass``
- Docker Engine ready: ``$engineReady``
- Backend mismatch signal: ``$backendMismatchSignal``
- AZURE_APPLY_EXECUTED: ``false``
- CLOUD_RESOURCES_CREATED: ``0``
- Transcript: ``$Transcript``

This diagnostic is read-only. It does not update/reset WSL or Docker and does not reboot Windows.
"@ | Set-Content -LiteralPath $mdPath -Encoding UTF8
} catch {
    $receiptFailure = Normalize-NativeText $_.Exception.Message
    Write-Host "DIAGNOSTIC_RECEIPT_WRITE_FAILED=$receiptFailure"
    Stop-Transcript | Out-Null
    exit 3
}

Stop-Transcript | Out-Null

Write-Host "SOAIACORE_DOCKER_WSL_DIAGNOSTIC=$classification"
Write-Host "DIAGNOSTIC_VERSION=$DiagnosticVersion"
Write-Host "WSL_VERSION_EXIT=$($diag.wsl_version.exit_code)"
Write-Host "WSL_STATUS_EXIT=$($diag.wsl_status.exit_code)"
Write-Host "WSL_LIST_EXIT=$($diag.wsl_list.exit_code)"
Write-Host "WSL_DIRECT_VERSION=$wslSemanticVersion"
Write-Host "WSL_VERSION_PARSE_STATUS=$wslVersionParseStatus"
Write-Host "WSL_OPERATIONAL=$wslOperational"
Write-Host "WSL_DIRECT_HEALTHY=$wslDirectHealthy"
Write-Host "WSL_NESTED_VIRTUALIZATION_WARNING=$nestedWarningObserved"
Write-Host "WSLCONFIG_NESTED_VIRTUALIZATION=$($diag.wsl_config_signal.nested_virtualization)"
Write-Host "DOCKER_DESKTOP_WSL_PROBE_PASS=$dockerDesktopProbePass"
Write-Host "DOCKER_ENGINE_READY=$engineReady"
Write-Host "BACKEND_CONTEXT_MISMATCH_SIGNAL=$backendMismatchSignal"
Write-Host "AZURE_APPLY_EXECUTED=false"
Write-Host "CLOUD_RESOURCES_CREATED=0"

if ($engineReady) {
    Write-Host 'NEXT_ACTION=RESUME_CANONICAL_SOAIACORE_REBUILD_ONESHOT_AFTER_V12_PRECHECK_PATCH'
    exit 0
}

Write-Host "BLOCKER=$blocker"
exit 2
