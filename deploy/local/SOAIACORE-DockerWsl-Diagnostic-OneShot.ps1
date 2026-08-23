#requires -Version 5.1
<#
SOAIACORE Rebuild P0 — Docker/WSL Diagnostic One-Shot v1.0
Read-only diagnostic guardrail for Docker Desktop / WSL context mismatches.
Does not update/reinstall/reset WSL or Docker, does not reboot Windows, and never touches Azure/cloud resources.
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
    $out = @()
    $exit = $null
    $errorText = ''
    try {
        $global:LASTEXITCODE = 0
        $out = @(& $Script 2>&1 | ForEach-Object { "$_" })
        $exit = $global:LASTEXITCODE
        if ($null -eq $exit) { $exit = 0 }
    } catch {
        $exit = 1
        $errorText = $_.Exception.Message
        $out += $errorText
    }
    return [ordered]@{
        name = $Name
        exit_code = [int]$exit
        output = @($out)
        error = $errorText
    }
}

function Get-WslSemanticVersion {
    param([string[]]$Lines)
    foreach ($line in $Lines) {
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
    $roots = @(
        (Join-Path $env:LOCALAPPDATA 'Docker\log'),
        (Join-Path $env:APPDATA 'Docker\log')
    ) | Where-Object { Test-Path -LiteralPath $_ }

    $matches = New-Object System.Collections.Generic.List[object]
    foreach ($root in $roots) {
        $files = Get-ChildItem -LiteralPath $root -File -Recurse -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 30
        foreach ($file in $files) {
            try {
                $hits = Select-String -LiteralPath $file.FullName -Pattern 'wslUpdateRequired|wsl\.exe|--version|exit status 1|backend|engine' -SimpleMatch:$false -ErrorAction SilentlyContinue |
                    Select-Object -Last 20
                foreach ($hit in $hits) {
                    $matches.Add([ordered]@{
                        file = $file.FullName
                        line = $hit.LineNumber
                        text = $hit.Line
                    })
                    if ($matches.Count -ge 120) { return @($matches) }
                }
            } catch { }
        }
    }
    return @($matches)
}

Write-Host 'SOAIACORE Docker/WSL diagnostic guardrail: READ-ONLY'

$diag = [ordered]@{}
$diag.architecture = $Architecture
$diag.started_at_utc = $StartUtc.ToString('o')
$diag.host = $env:COMPUTERNAME
$diag.azure_apply_executed = $false
$diag.cloud_resources_created = 0
$diag.wsl_expected_path = $WslExe

$diag.where_wsl = Invoke-Capture 'where.exe wsl.exe' { where.exe wsl.exe }
$diag.get_command_wsl = [ordered]@{ name='Get-Command wsl.exe -All'; exit_code=0; output=@(); error='' }
try {
    $diag.get_command_wsl.output = @(Get-Command wsl.exe -All -ErrorAction Stop | ForEach-Object { $_.Source })
} catch {
    $diag.get_command_wsl.exit_code = 1
    $diag.get_command_wsl.error = $_.Exception.Message
}

if (-not (Test-Path -LiteralPath $WslExe)) {
    $diag.wsl_version = [ordered]@{ name='System32 wsl --version'; exit_code=1; output=@('System32 wsl.exe missing'); error='WSL_EXE_MISSING' }
    $diag.wsl_status = [ordered]@{ name='System32 wsl --status'; exit_code=1; output=@(); error='WSL_EXE_MISSING' }
    $diag.wsl_list = [ordered]@{ name='System32 wsl -l -v'; exit_code=1; output=@(); error='WSL_EXE_MISSING' }
    $diag.docker_desktop_wsl_probe = [ordered]@{ name='docker-desktop probe'; exit_code=1; output=@(); error='WSL_EXE_MISSING' }
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

$docker = Find-DockerCli
$diag.docker_cli_path = $docker
if ($docker) {
    $diag.docker_version = Invoke-Capture 'docker version' { & $docker version }
    $diag.docker_info = Invoke-Capture 'docker info' { & $docker info }
    $diag.docker_compose = Invoke-Capture 'docker compose version' { & $docker compose version }
} else {
    $diag.docker_version = [ordered]@{ name='docker version'; exit_code=1; output=@('Docker CLI not found'); error='DOCKER_CLI_NOT_FOUND' }
    $diag.docker_info = [ordered]@{ name='docker info'; exit_code=1; output=@(); error='DOCKER_CLI_NOT_FOUND' }
    $diag.docker_compose = [ordered]@{ name='docker compose version'; exit_code=1; output=@(); error='DOCKER_CLI_NOT_FOUND' }
}

$desktopCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
$diag.docker_desktop_cli_version = Invoke-Capture 'docker desktop version' { docker desktop version }
$diag.docker_desktop_cli_status = Invoke-Capture 'docker desktop status' { docker desktop status }

$service = Get-Service 'com.docker.service' -ErrorAction SilentlyContinue
$diag.docker_service = if ($service) {
    [ordered]@{ exists=$true; status="$($service.Status)"; start_type="$($service.StartType)" }
} else {
    [ordered]@{ exists=$false; status=''; start_type='' }
}

$backendRows = @()
try {
    $backendRows = @(Get-CimInstance Win32_Process -Filter "Name='com.docker.backend.exe'" -ErrorAction Stop | ForEach-Object {
        [ordered]@{
            process_id = $_.ProcessId
            parent_process_id = $_.ParentProcessId
            executable_path = $_.ExecutablePath
            command_line = $_.CommandLine
            owner = (Get-ProcessOwnerSafe -ProcessId $_.ProcessId)
        }
    })
} catch { }
$diag.docker_backend_processes = $backendRows

$diagnoseCandidates = @(
    'C:\Program Files\Docker\Docker\resources\com.docker.diagnose.exe',
    'C:\Program Files\Docker\Docker\resources\bin\com.docker.diagnose.exe'
)
$diagnoseExe = $diagnoseCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$diag.docker_diagnose_path = if ($diagnoseExe) { $diagnoseExe } else { '' }
if ($diagnoseExe) {
    $diag.docker_diagnose_check = Invoke-Capture 'com.docker.diagnose.exe check' { & $diagnoseExe check }
} else {
    $diag.docker_diagnose_check = [ordered]@{ name='com.docker.diagnose.exe check'; exit_code=127; output=@('Diagnostic executable not found'); error='SKIPPED_UNAVAILABLE' }
}

$diag.relevant_docker_log_matches = Get-RelevantDockerLogs

$engineReady = ($diag.docker_info.exit_code -eq 0)
$dockerDesktopProbePass = ($diag.docker_desktop_wsl_probe.exit_code -eq 0 -and (($diag.docker_desktop_wsl_probe.output -join ' ') -match 'SOAIACORE_WSL_BACKEND_PROBE_PASS'))
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
} elseif (-not $dockerDesktopProbePass) {
    $classification = 'DOCKER_DESKTOP_WSL_DISTRO_FAILURE'
    $blocker = 'DOCKER_DESKTOP_WSL_DISTRO_FAILURE: host WSL is healthy but docker-desktop distribution probe failed'
} elseif ($backendMismatchSignal) {
    $classification = 'DOCKER_BACKEND_WSL_CONTEXT_MISMATCH'
    $blocker = 'DOCKER_BACKEND_WSL_CONTEXT_MISMATCH: host WSL and docker-desktop probe are healthy but Docker backend reports contradictory WSL version/update evidence'
} else {
    $classification = 'DOCKER_ENGINE_NOT_READY_DIAGNOSTIC_CAPTURED'
    $blocker = 'DOCKER_ENGINE_NOT_READY_DIAGNOSTIC_CAPTURED: engine unavailable; diagnostic evidence captured without destructive remediation'
}

$diag.classification = $classification
$diag.blocker = $blocker
$diag.docker_engine_ready = $engineReady
$diag.docker_desktop_wsl_probe_pass = $dockerDesktopProbePass
$diag.backend_context_mismatch_signal = $backendMismatchSignal
$diag.ended_at_utc = (Get-Date).ToUniversalTime().ToString('o')
$diag.transcript = $Transcript

$jsonPath = Join-Path $ReceiptDir 'DOCKER_WSL_DIAGNOSTIC_2026-08-23.json'
$mdPath = Join-Path $ReceiptDir 'DOCKER_WSL_DIAGNOSTIC_2026-08-23.md'
$diag | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

@"
# SOAIACORE Docker/WSL Diagnostic Receipt

- Classification: ``$classification``
- Blocker: ``$blocker``
- Architecture: ``$Architecture``
- Host: ``$env:COMPUTERNAME``
- Direct WSL version: ``$wslSemanticVersion``
- Direct WSL healthy: ``$($diag.wsl_direct_healthy)``
- docker-desktop probe pass: ``$dockerDesktopProbePass``
- Docker Engine ready: ``$engineReady``
- Backend mismatch signal: ``$backendMismatchSignal``
- AZURE_APPLY_EXECUTED: ``false``
- CLOUD_RESOURCES_CREATED: ``0``
- Transcript: ``$Transcript``

This diagnostic is read-only. It does not update/reset WSL or Docker and does not reboot Windows.
"@ | Set-Content -LiteralPath $mdPath -Encoding UTF8

Stop-Transcript | Out-Null

Write-Host "SOAIACORE_DOCKER_WSL_DIAGNOSTIC=$classification"
Write-Host "WSL_DIRECT_VERSION=$wslSemanticVersion"
Write-Host "WSL_DIRECT_HEALTHY=$($diag.wsl_direct_healthy)"
Write-Host "DOCKER_DESKTOP_WSL_PROBE_PASS=$dockerDesktopProbePass"
Write-Host "DOCKER_ENGINE_READY=$engineReady"
Write-Host "AZURE_APPLY_EXECUTED=false"
Write-Host "CLOUD_RESOURCES_CREATED=0"

if ($engineReady) {
    Write-Host 'NEXT_ACTION=RESUME_CANONICAL_SOAIACORE_REBUILD_ONESHOT'
    exit 0
}

Write-Host "BLOCKER=$blocker"
exit 2
