#requires -Version 5.1
<#
SOAIACORE Rebuild P0 — Docker/WSL Diagnostic One-Shot v1.1
Read-only diagnostic guardrail for Docker Desktop / WSL context mismatches.
PowerShell 5.1 safe: native stderr is captured as evidence and does not become a
terminating script error. No WSL/Docker update, reinstall, reset, unregister,
reboot, backend/BIOS/PATH mutation, data deletion, Azure apply or cloud creation.
#>

[CmdletBinding()]
param(
    [string]$RepoPath = (Get-Location).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Architecture = 'v0.6 FINAL / FROZEN FOR P0'
$StateRoot = Join-Path $env:ProgramData 'SOAIACORE\RebuildP0'
$DiagRoot = Join-Path $StateRoot 'diagnostics'
$ReceiptDir = Join-Path $RepoPath 'receipts'
$WslExe = Join-Path $env:SystemRoot 'System32\wsl.exe'
$StartUtc = (Get-Date).ToUniversalTime()

foreach ($p in @($StateRoot,$DiagRoot,$ReceiptDir)) {
    if (-not (Test-Path -LiteralPath $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
}

$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Transcript = Join-Path $DiagRoot "docker-wsl-diagnostic-$Stamp.log"
Start-Transcript -Path $Transcript -Append | Out-Null

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
        # Windows PowerShell 5.1 promotes native stderr to ErrorRecord objects.
        # Keep it as evidence rather than terminating because warnings such as
        # WSL nested-virtualization capability messages can coexist with a
        # successful native process exit.
        $ErrorActionPreference = 'Continue'
        $global:LASTEXITCODE = 0
        $raw = @(& $Script 2>&1)
        $exitCode = [int]$global:LASTEXITCODE
        $output = @($raw | ForEach-Object { $_.ToString() })
    } catch {
        $exitCode = 1
        $errorText = $_.Exception.Message
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
    foreach ($item in @($Lines)) {
        $line = "$item"
        if ($line -match '(?i)WSL[^0-9]*([0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?)') { return $Matches[1] }
        if ($line -match '([0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?)') { return $Matches[1] }
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
    # Plain PowerShell arrays are intentional: Windows PowerShell 5.1 can throw
    # ArgumentException while coercing some generic List[object] collections.
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
                $hits = @(Select-String -LiteralPath $file.FullName -Pattern 'wslUpdateRequired|wsl\.exe|--version|exit status 1|backend|engine|nested virtualization' -SimpleMatch:$false -ErrorAction SilentlyContinue |
                    Select-Object -Last 20)
                foreach ($hit in $hits) {
                    $result += [pscustomobject]@{
                        file = $file.FullName
                        line = [int]$hit.LineNumber
                        text = "$($hit.Line)"
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

Write-Host 'SOAIACORE Docker/WSL diagnostic guardrail v1.1: READ-ONLY'

$diag = [ordered]@{}
$diag.diagnostic_version = '1.1'
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
    $diag.get_command_wsl.output = @(Get-Command wsl.exe -All -ErrorAction Stop | ForEach-Object { $_.Source })
} catch {
    $diag.get_command_wsl.exit_code = 1
    $diag.get_command_wsl.error = $_.Exception.Message
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

$wslVersionText = @($diag.wsl_version.output | ForEach-Object { "$_" })
$wslSemanticVersion = Get-WslSemanticVersion $wslVersionText
$diag.wsl_semantic_version = $wslSemanticVersion
$diag.wsl_minimum_for_guardrail = '2.1.5'
$diag.wsl_direct_healthy = ($diag.wsl_version.exit_code -eq 0 -and (Test-VersionAtLeast $wslSemanticVersion '2.1.5'))

$probeText = (@($diag.docker_desktop_wsl_probe.output) -join ' ')
$nestedWarningObserved = ($probeText -match '(?i)nested virtualization is not supported|no se admite la virtualizaci.n anidada')
$dockerDesktopProbePass = ($probeText -match 'SOAIACORE_WSL_BACKEND_PROBE_PASS')
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
            executable_path = "$($_.ExecutablePath)"
            command_line = "$($_.CommandLine)"
            owner = (Get-ProcessOwnerSafe -ProcessId $_.ProcessId)
        }
    })
} catch { }
$diag.docker_backend_processes = @($backendRows)

# `com.docker.diagnose check` is deprecated in current Docker Desktop. A full
# `diagnose/gather` can create a larger diagnostics bundle and is intentionally
# not launched by this narrow read-only rail; direct local logs are sufficient
# for classification and no diagnostic data is uploaded.
$diag.docker_diagnose = [pscustomobject]@{
    name = 'Docker diagnostics bundle'
    exit_code = 0
    output = @('SKIPPED_BY_GUARDRAIL: deprecated check not used; no bundle/upload generated')
    error = ''
}

$diag.relevant_docker_log_matches = @(Get-RelevantDockerLogs)

$engineReady = ($diag.docker_info.exit_code -eq 0)
$backendMismatchSignal = $false
foreach ($m in @($diag.relevant_docker_log_matches)) {
    $t = "$($m.text)"
    if ($t -match 'wslUpdateRequired' -or ($t -match 'wsl\.exe' -and $t -match '(--version|exit status 1|exit=1)')) {
        $backendMismatchSignal = $true
        break
    }
}

if ($engineReady) {
    $classification = 'DOCKER_ENGINE_READY'
    $blocker = ''
} elseif (-not $diag.wsl_direct_healthy) {
    $classification = 'HOST_WSL_FAILURE'
    $blocker = 'HOST_WSL_FAILURE: direct System32 wsl.exe version probe is not healthy'
} elseif ($dockerDesktopProbePass -and $backendMismatchSignal) {
    $classification = 'DOCKER_BACKEND_WSL_CONTEXT_MISMATCH'
    $blocker = 'DOCKER_BACKEND_WSL_CONTEXT_MISMATCH: host WSL and docker-desktop execution probe are healthy but Docker backend reports contradictory WSL version/update evidence'
} elseif ($dockerDesktopProbePass) {
    $classification = 'DOCKER_ENGINE_NOT_READY_DIAGNOSTIC_CAPTURED'
    $blocker = 'DOCKER_ENGINE_NOT_READY_DIAGNOSTIC_CAPTURED: docker-desktop execution probe succeeded but Docker Engine is unavailable; backend evidence captured'
} else {
    $classification = 'DOCKER_DESKTOP_WSL_DISTRO_FAILURE'
    $blocker = 'DOCKER_DESKTOP_WSL_DISTRO_FAILURE: host WSL is healthy but docker-desktop did not complete the execution probe'
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

- Diagnostic version: ``1.1``
- Classification: ``$classification``
- Blocker: ``$blocker``
- Architecture: ``$Architecture``
- Host: ``$env:COMPUTERNAME``
- Direct WSL version: ``$wslSemanticVersion``
- Direct WSL healthy: ``$($diag.wsl_direct_healthy)``
- WSL nested-virtualization warning observed: ``$nestedWarningObserved``
- .wslconfig nestedVirtualization: ``$($diag.wsl_config_signal.nested_virtualization)``
- docker-desktop execution probe pass: ``$dockerDesktopProbePass``
- Docker Engine ready: ``$engineReady``
- Backend mismatch signal: ``$backendMismatchSignal``
- AZURE_APPLY_EXECUTED: ``false``
- CLOUD_RESOURCES_CREATED: ``0``
- Transcript: ``$Transcript``

This diagnostic is read-only. It does not update/reset WSL or Docker, does not reboot Windows, and does not upload a Docker diagnostic bundle.
"@ | Set-Content -LiteralPath $mdPath -Encoding UTF8
} catch {
    $receiptFailure = $_.Exception.Message
    Write-Host "DIAGNOSTIC_RECEIPT_WRITE_FAILED=$receiptFailure"
    Stop-Transcript | Out-Null
    exit 3
}

Stop-Transcript | Out-Null

Write-Host "SOAIACORE_DOCKER_WSL_DIAGNOSTIC=$classification"
Write-Host "WSL_DIRECT_VERSION=$wslSemanticVersion"
Write-Host "WSL_DIRECT_HEALTHY=$($diag.wsl_direct_healthy)"
Write-Host "WSL_NESTED_VIRTUALIZATION_WARNING=$nestedWarningObserved"
Write-Host "WSLCONFIG_NESTED_VIRTUALIZATION=$($diag.wsl_config_signal.nested_virtualization)"
Write-Host "DOCKER_DESKTOP_WSL_PROBE_PASS=$dockerDesktopProbePass"
Write-Host "DOCKER_ENGINE_READY=$engineReady"
Write-Host "BACKEND_CONTEXT_MISMATCH_SIGNAL=$backendMismatchSignal"
Write-Host "AZURE_APPLY_EXECUTED=false"
Write-Host "CLOUD_RESOURCES_CREATED=0"

if ($engineReady) {
    Write-Host 'NEXT_ACTION=RESUME_CANONICAL_SOAIACORE_REBUILD_ONESHOT'
    exit 0
}

Write-Host "BLOCKER=$blocker"
exit 2
