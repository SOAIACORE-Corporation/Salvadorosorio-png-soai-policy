#requires -Version 5.1
<#
SOAIACORE Rebuild P0 — Windows One-Shot v1.1
Architecture authority: v0.6 FINAL / FROZEN FOR P0
Purpose: self-heal the local Windows WSL2/Docker substrate, reconcile the AR package,
execute the real PostgreSQL+pgvector gate, write receipts, and tear down disposable runtime.
Safe to rerun. Fail-closed on non-remediable host conditions.

This script never performs Azure apply and never creates cloud resources.
#>

[CmdletBinding()]
param(
    [string]$RepoPath = (Get-Location).Path,
    [string]$ArZip = "",
    [string]$GitExe = "",
    [switch]$AutoReboot,
    [switch]$KeepFailedRuntime
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$ExpectedBranch = 'rebuild/p0-v0.6-final'
$ExpectedArchitecture = 'v0.6 FINAL / FROZEN FOR P0'
$StateRoot = Join-Path $env:ProgramData 'SOAIACORE\RebuildP0'
$StateFile = Join-Path $StateRoot 'oneshot-state.json'
$LogDir = Join-Path $StateRoot 'logs'
$ReceiptDir = Join-Path $RepoPath 'receipts'
$WorkRoot = Join-Path $env:TEMP 'SOAIACORE-RebuildP0'
$ResumeName = 'SOAIACORE_RebuildP0_Resume'
$StartUtc = (Get-Date).ToUniversalTime()
$MaxReboots = 4

function Write-Step([string]$Message) {
    $stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    Write-Host "[$stamp] $Message"
}

function Ensure-Dir([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { New-Item -ItemType Directory -Path $Path -Force | Out-Null }
}

Ensure-Dir $StateRoot
Ensure-Dir $LogDir
Ensure-Dir $ReceiptDir
Ensure-Dir $WorkRoot

$Transcript = Join-Path $LogDir ("oneshot-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
Start-Transcript -Path $Transcript -Append | Out-Null

function Load-State {
    if (Test-Path -LiteralPath $StateFile) {
        try { return (Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json) } catch { }
    }
    return [pscustomobject]@{
        version = 2
        stage = 'INIT'
        repo_path = $RepoPath
        ar_zip = $ArZip
        started_at_utc = $StartUtc.ToString('o')
        last_updated_utc = $StartUtc.ToString('o')
        reboot_count = 0
        attempts = 0
        last_reboot_reason = ''
        wsl_update_attempted = $false
        docker_recovery_attempts = 0
    }
}

function Ensure-StateProperty([object]$Object,[string]$Name,$Value) {
    if (-not ($Object.PSObject.Properties.Name -contains $Name)) {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    }
}

function Save-State([object]$State, [string]$Stage) {
    $State.stage = $Stage
    $State.last_updated_utc = (Get-Date).ToUniversalTime().ToString('o')
    $State | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $StateFile -Encoding UTF8
}

$State = Load-State
Ensure-StateProperty $State 'version' 2
Ensure-StateProperty $State 'last_reboot_reason' ''
Ensure-StateProperty $State 'wsl_update_attempted' $false
Ensure-StateProperty $State 'docker_recovery_attempts' 0
$State.version = 2
$State.attempts = [int]$State.attempts + 1
if ([string]::IsNullOrWhiteSpace($ArZip) -and -not [string]::IsNullOrWhiteSpace([string]$State.ar_zip)) { $ArZip = [string]$State.ar_zip }
if (-not [string]::IsNullOrWhiteSpace($ArZip)) { $State.ar_zip = $ArZip }
Save-State $State $State.stage

if ([string]::IsNullOrWhiteSpace($GitExe)) {
    $gitCommand = Get-Command git.exe -ErrorAction SilentlyContinue
    if ($gitCommand) { $GitExe = $gitCommand.Source }
}

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Build-ResumeCommand {
    $cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -RepoPath `"$RepoPath`""
    if (-not [string]::IsNullOrWhiteSpace($ArZip)) { $cmd += " -ArZip `"$ArZip`"" }
    if (-not [string]::IsNullOrWhiteSpace($GitExe)) { $cmd += " -GitExe `"$GitExe`"" }
    if ($AutoReboot) { $cmd += ' -AutoReboot' }
    if ($KeepFailedRuntime) { $cmd += ' -KeepFailedRuntime' }
    return $cmd
}

function Relaunch-Elevated {
    $argList = @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"{0}"' -f $PSCommandPath),'-RepoPath',('"{0}"' -f $RepoPath))
    if (-not [string]::IsNullOrWhiteSpace($ArZip)) { $argList += @('-ArZip',('"{0}"' -f $ArZip)) }
    if (-not [string]::IsNullOrWhiteSpace($GitExe)) { $argList += @('-GitExe',('"{0}"' -f $GitExe)) }
    if ($AutoReboot) { $argList += '-AutoReboot' }
    if ($KeepFailedRuntime) { $argList += '-KeepFailedRuntime' }
    Start-Process powershell.exe -Verb RunAs -ArgumentList ($argList -join ' ')
    Stop-Transcript | Out-Null
    exit 0
}

if (-not (Test-Admin)) {
    Write-Step 'Administrative rights required. Relaunching the same one-shot elevated.'
    Relaunch-Elevated
}

function Get-CommandPath([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Test-PendingReboot {
    $keys = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending',
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
    )
    foreach ($k in $keys) { if (Test-Path $k) { return $true } }
    try {
        $pending = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -Name PendingFileRenameOperations -ErrorAction SilentlyContinue).PendingFileRenameOperations
        if ($pending) { return $true }
    } catch { }
    return $false
}

function Register-Resume {
    $cmd = Build-ResumeCommand
    New-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce' -Name $ResumeName -PropertyType String -Value $cmd -Force | Out-Null
}

function Clear-Resume {
    Remove-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce' -Name $ResumeName -ErrorAction SilentlyContinue
}

function Request-Reboot([string]$Reason) {
    if ([int]$State.reboot_count -ge $MaxReboots) {
        throw "REBOOT_LOOP_GUARD: max=$MaxReboots last_reason=$Reason"
    }
    $State.reboot_count = [int]$State.reboot_count + 1
    $State.last_reboot_reason = $Reason
    Save-State $State 'REBOOT_REQUIRED'
    Register-Resume
    Write-Step "REBOOT_REQUIRED: $Reason"
    if ($AutoReboot) {
        Write-Step 'Automatic reboot authorized. Rebooting in 20 seconds; RunOnce will resume this same entrypoint.'
        shutdown.exe /r /t 20 /c "SOAIACORE Rebuild P0 one-shot resume" | Out-Null
    } else {
        Write-Step 'Resume registered. Restart Windows once and sign in; the same one-shot will resume.'
    }
    Stop-Transcript | Out-Null
    exit 3010
}

function Assert-Repo {
    Write-Step 'PRECHECK: repository and branch.'
    if (-not (Test-Path -LiteralPath (Join-Path $RepoPath '.git'))) { throw "REPO_NOT_FOUND: $RepoPath" }
    Push-Location $RepoPath
    try {
        if ([string]::IsNullOrWhiteSpace($GitExe) -or -not (Test-Path -LiteralPath $GitExe)) { throw 'GIT_UNAVAILABLE' }
        $branch = (& $GitExe branch --show-current).Trim()
        if ($branch -ne $ExpectedBranch) { throw "WRONG_BRANCH: expected=$ExpectedBranch actual=$branch" }
        & $GitExe remote -v | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'GIT_REMOTE_UNAVAILABLE' }
        $dirty = @(& $GitExe status --porcelain)
        if ($dirty) {
            $allowedPrefixes = @(
                'contracts/', 'schemas/', 'db/', 'docs/persistence/', 'docs/azure/',
                'validation/', 'deploy/local/ar/', 'receipts/'
            )
            $unexpected = @($dirty | Where-Object {
                if ($_.Length -lt 4) { return $true }
                $path = $_.Substring(3).Replace('\\','/')
                -not ($allowedPrefixes | Where-Object { $path.StartsWith($_, [StringComparison]::OrdinalIgnoreCase) })
            })
            if ($unexpected) { throw "REPO_NOT_CLEAN: unrelated changes: $($unexpected -join '; ')" }
            Write-Step 'PRECHECK: resuming with workflow-owned generated changes only.'
        }
        return (& $GitExe rev-parse HEAD).Trim()
    } finally { Pop-Location }
}

function Get-OptionalFeatureState([string]$Name) {
    try {
        $f = Get-WindowsOptionalFeature -Online -FeatureName $Name -ErrorAction Stop
        return [string]$f.State
    } catch {
        return 'Unavailable'
    }
}

function Test-FirmwareVirtualization {
    try {
        $cpus = @(Get-CimInstance Win32_Processor -ErrorAction Stop)
        if (-not $cpus) { return $true }
        $known = @($cpus | Where-Object { $null -ne $_.VirtualizationFirmwareEnabled })
        if (-not $known) { return $true }
        return -not (@($known | Where-Object { -not $_.VirtualizationFirmwareEnabled }).Count -gt 0)
    } catch {
        return $true
    }
}

function Ensure-HypervisorBoot {
    $bcd = & bcdedit.exe /enum '{current}' 2>$null
    if ($LASTEXITCODE -ne 0) { return $false }
    $text = ($bcd -join "`n")
    if ($text -match '(?im)^hypervisorlaunchtype\s+Off\s*$') {
        Write-Step 'Enabling Windows hypervisor launch at boot.'
        & bcdedit.exe /set hypervisorlaunchtype auto | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'HYPERVISOR_BOOT_ENABLE_FAILED' }
        return $true
    }
    return $false
}

function Invoke-WslUpdate {
    Write-Step 'Ensuring WSL runtime is current.'
    $State.wsl_update_attempted = $true
    Save-State $State 'WSL_UPDATE'

    & wsl.exe --update
    $exit = $LASTEXITCODE
    if ($exit -ne 0) {
        Write-Step "wsl --update returned exit=$exit. Retrying with --web-download."
        & wsl.exe --update --web-download
        $exit = $LASTEXITCODE
    }
    if ($exit -ne 0) { throw "WSL_UPDATE_FAILED exit=$exit" }

    try { & wsl.exe --set-default-version 2 | Out-Null } catch { }
    try { & wsl.exe --shutdown | Out-Null } catch { }
    Start-Sleep -Seconds 2

    $versionText = ''
    try { $versionText = ((& wsl.exe --version 2>&1) -join ' ') } catch { }
    if (-not [string]::IsNullOrWhiteSpace($versionText)) { Write-Step "WSL: $versionText" }
}

function Ensure-WslPrereqs {
    Write-Step 'Checking virtualization, WSL2, VirtualMachinePlatform, and Hyper-V availability.'
    if (-not (Test-FirmwareVirtualization)) {
        throw 'HARDWARE_VIRTUALIZATION_DISABLED_IN_FIRMWARE'
    }

    $needsReboot = $false
    foreach ($f in @('Microsoft-Windows-Subsystem-Linux','VirtualMachinePlatform')) {
        $state = Get-OptionalFeatureState $f
        if ($state -eq 'Unavailable') { throw "WINDOWS_FEATURE_UNAVAILABLE: $f" }
        if ($state -ne 'Enabled') {
            Write-Step "Enabling Windows feature $f"
            Enable-WindowsOptionalFeature -Online -FeatureName $f -All -NoRestart | Out-Null
            $needsReboot = $true
        }
    }

    # Hyper-V is optional on editions that do not expose it, but if available we enable it because
    # Docker Desktop may request it on this host. This is idempotent.
    $hyperVState = Get-OptionalFeatureState 'Microsoft-Hyper-V-All'
    if ($hyperVState -ne 'Unavailable' -and $hyperVState -ne 'Enabled') {
        Write-Step 'Enabling Microsoft-Hyper-V-All because this Windows edition exposes it.'
        Enable-WindowsOptionalFeature -Online -FeatureName 'Microsoft-Hyper-V-All' -All -NoRestart | Out-Null
        $needsReboot = $true
    }

    if (Ensure-HypervisorBoot) { $needsReboot = $true }
    if ($needsReboot) { Request-Reboot 'Windows virtualization feature activation' }
    if (Test-PendingReboot) { Request-Reboot 'Windows has a pending reboot required by virtualization/WSL components' }

    Invoke-WslUpdate

    if (Test-PendingReboot) { Request-Reboot 'WSL update requires Windows restart' }
}

function Ensure-Winget {
    if (-not (Get-CommandPath 'winget.exe')) { throw 'WINGET_UNAVAILABLE: Microsoft App Installer is required for unattended Docker installation' }
}

function Resolve-DockerCli {
    $docker = Get-CommandPath 'docker.exe'
    if ($docker) { return $docker }
    $candidate = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
    if (Test-Path -LiteralPath $candidate) {
        $env:PATH = "$(Split-Path $candidate);$env:PATH"
        return $candidate
    }
    return $null
}

function Stop-DockerDesktopBestEffort {
    foreach ($name in @('Docker Desktop','com.docker.backend','com.docker.proxy','vpnkit')) {
        Get-Process -Name $name -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

function Start-DockerDesktopBestEffort {
    $service = Get-Service 'com.docker.service' -ErrorAction SilentlyContinue
    if ($service -and $service.Status -ne 'Running') {
        try { Start-Service 'com.docker.service' -ErrorAction Stop } catch { }
    }
    $desktop = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
    if (Test-Path -LiteralPath $desktop) {
        $running = Get-Process 'Docker Desktop' -ErrorAction SilentlyContinue
        if (-not $running) {
            Write-Step 'Starting Docker Desktop.'
            Start-Process -FilePath $desktop | Out-Null
        }
    }
}

function Wait-DockerEngine([string]$Docker,[int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        & $Docker info *> $null
        if ($LASTEXITCODE -eq 0) { return $true }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Repair-DockerEngine([string]$Docker) {
    $State.docker_recovery_attempts = [int]$State.docker_recovery_attempts + 1
    Save-State $State 'DOCKER_RECOVERY'
    Write-Step "Docker recovery attempt $($State.docker_recovery_attempts): shutting down WSL and restarting Docker Desktop."
    try { & wsl.exe --shutdown | Out-Null } catch { }
    Stop-DockerDesktopBestEffort
    Start-DockerDesktopBestEffort
    return (Wait-DockerEngine $Docker 240)
}

function Ensure-DockerDesktop {
    $docker = Resolve-DockerCli
    if (-not $docker) {
        Write-Step 'Docker Desktop missing. Installing idempotently via winget.'
        Ensure-Winget
        & winget.exe install --exact --id Docker.DockerDesktop --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
        $exit = $LASTEXITCODE
        if ($exit -ne 0) { throw "DOCKER_INSTALL_FAILED exit=$exit" }
        $docker = Resolve-DockerCli
        if (-not $docker) { throw 'DOCKER_CLI_MISSING_AFTER_INSTALL' }
        if (Test-PendingReboot) { Request-Reboot 'Docker Desktop installation requested a restart' }
    } else {
        Write-Step "Docker CLI already present: $docker"
    }

    Start-DockerDesktopBestEffort
    if (-not (Wait-DockerEngine $docker 180)) {
        Write-Step 'Docker Engine not ready after initial wait. Starting self-heal sequence.'
        if (-not (Repair-DockerEngine $docker)) {
            Invoke-WslUpdate
            if (Test-PendingReboot) { Request-Reboot 'WSL repair/update requires restart before Docker Engine can start' }
            if (-not (Repair-DockerEngine $docker)) {
                if (Test-PendingReboot) { Request-Reboot 'Docker/Windows virtualization stack still has a pending restart' }
                throw 'DOCKER_ENGINE_NOT_READY_AFTER_SELF_HEAL'
            }
        }
    }

    & $docker compose version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'DOCKER_COMPOSE_UNAVAILABLE' }
    return $docker
}

function Resolve-ArZip {
    if (-not [string]::IsNullOrWhiteSpace($ArZip) -and (Test-Path -LiteralPath $ArZip)) { return (Resolve-Path $ArZip).Path }
    $patterns = @(
        (Join-Path $RepoPath 'SOAIACORE_AR_v0.8_Persistence_and_Azure_Readiness_FINAL.zip'),
        (Join-Path $env:USERPROFILE 'Downloads\SOAIACORE_AR_v0.8_Persistence_and_Azure_Readiness_FINAL.zip')
    )
    foreach ($p in $patterns) { if (Test-Path -LiteralPath $p) { return (Resolve-Path $p).Path } }
    throw 'AR_PACKAGE_ACCESS=BLOCKED: authoritative AR v0.8 ZIP not found locally. Codex must retrieve Drive file ID 1EmOJFGv-1slm9GYtXD4V849wANxOYpaw and rerun this same entrypoint with -ArZip.'
}

function Expand-ArPackage([string]$ZipPath) {
    $dest = Join-Path $WorkRoot 'ar-v0.8'
    if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }
    Ensure-Dir $dest
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $dest -Force
    $rootCandidates = @(Get-ChildItem -LiteralPath $dest -Directory)
    if ($rootCandidates.Count -eq 1 -and (Test-Path (Join-Path $rootCandidates[0].FullName 'README.md'))) { return $rootCandidates[0].FullName }
    if (Test-Path (Join-Path $dest 'README.md')) { return $dest }
    $readme = Get-ChildItem -LiteralPath $dest -Filter README.md -Recurse | Select-Object -First 1
    if (-not $readme) { throw 'AR_PACKAGE_INVALID: README.md not found' }
    return $readme.Directory.FullName
}

function Copy-IfDifferent([string]$Source, [string]$Destination) {
    Ensure-Dir (Split-Path $Destination)
    if (Test-Path -LiteralPath $Destination) {
        $a = (Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash
        $b = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash
        if ($a -eq $b) { return $false }
    }
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
    return $true
}

function Reconcile-Ar([string]$ArRoot) {
    Write-Step 'Reconciling AR package into rebuild source tree (copy-if-different).'
    $map = @{
        'contracts' = 'contracts'
        'schemas' = 'schemas'
        'sql\migrations' = 'db\migrations'
        'sql\tests' = 'db\tests'
        'docs' = 'docs\persistence'
        'azure' = 'docs\azure'
        'validation' = 'validation'
        'local' = 'deploy\local\ar'
    }
    foreach ($srcRel in $map.Keys) {
        $srcDir = Join-Path $ArRoot $srcRel
        if (-not (Test-Path -LiteralPath $srcDir)) { continue }
        $dstDir = Join-Path $RepoPath $map[$srcRel]
        Get-ChildItem -LiteralPath $srcDir -File -Recurse | ForEach-Object {
            $rel = $_.FullName.Substring($srcDir.Length).TrimStart('\')
            Copy-IfDifferent $_.FullName (Join-Path $dstDir $rel) | Out-Null
        }
    }
}

function Invoke-LocalGate([string]$ArRoot) {
    $gateCandidates = @(
        (Join-Path $RepoPath 'deploy\local\ar\run_local_gate.ps1'),
        (Join-Path $ArRoot 'local\run_local_gate.ps1')
    )
    $gate = $gateCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $gate) { throw 'LOCAL_GATE_SCRIPT_NOT_FOUND' }
    Write-Step "Executing real local PostgreSQL+pgvector gate: $gate"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $gate
    if ($LASTEXITCODE -ne 0) { throw "LOCAL_POSTGRES_GATE_FAILED exit=$LASTEXITCODE" }
}

function Write-Receipt([string]$Status,[string]$Blocker,[string]$CommitSha,[string]$DockerVersion,[string]$ComposeVersion) {
    $end = (Get-Date).ToUniversalTime()
    $base = 'LOCAL_POSTGRES_GATE_2026-08-23'
    $jsonPath = Join-Path $ReceiptDir ($base + '.json')
    $mdPath = Join-Path $ReceiptDir ($base + '.md')
    $hostSafe = $env:COMPUTERNAME
    $obj = [ordered]@{
        status = $Status
        blocker = $Blocker
        architecture = $ExpectedArchitecture
        branch = $ExpectedBranch
        commit_sha_before_receipt = $CommitSha
        host = $hostSafe
        docker_version = $DockerVersion
        docker_compose_version = $ComposeVersion
        started_at_utc = $State.started_at_utc
        ended_at_utc = $end.ToString('o')
        attempts = $State.attempts
        reboot_count = $State.reboot_count
        last_reboot_reason = $State.last_reboot_reason
        wsl_update_attempted = $State.wsl_update_attempted
        docker_recovery_attempts = $State.docker_recovery_attempts
        AZURE_APPLY_EXECUTED = $false
        CLOUD_RESOURCES_CREATED = 0
        transcript = $Transcript
    }
    $obj | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8
    @"
# SOAIACORE Local PostgreSQL Gate Receipt

- Status: ``$Status``
- Blocker: ``$Blocker``
- Architecture: ``$ExpectedArchitecture``
- Branch: ``$ExpectedBranch``
- Commit before receipt: ``$CommitSha``
- Host: ``$hostSafe``
- Docker: ``$DockerVersion``
- Docker Compose: ``$ComposeVersion``
- Started UTC: ``$($State.started_at_utc)``
- Ended UTC: ``$($end.ToString('o'))``
- Attempts: ``$($State.attempts)``
- Reboots: ``$($State.reboot_count)``
- Last reboot reason: ``$($State.last_reboot_reason)``
- WSL update attempted: ``$($State.wsl_update_attempted)``
- Docker recovery attempts: ``$($State.docker_recovery_attempts)``
- AZURE_APPLY_EXECUTED: ``false``
- CLOUD_RESOURCES_CREATED: ``0``

Final: ``SOAIACORE_LOCAL_POSTGRES_GATE=$Status``
"@ | Set-Content -LiteralPath $mdPath -Encoding UTF8
    return @($jsonPath,$mdPath)
}

$commit = ''
$dockerVersion = ''
$composeVersion = ''
try {
    Save-State $State 'PRECHECK'
    $commit = Assert-Repo

    Save-State $State 'WINDOWS_SUBSTRATE'
    Ensure-WslPrereqs

    Save-State $State 'DOCKER_BOOTSTRAP'
    $docker = Ensure-DockerDesktop
    $dockerVersion = (& $docker --version) -join ' '
    $composeVersion = (& $docker compose version) -join ' '

    Save-State $State 'AR_RESOLVE'
    $zip = Resolve-ArZip
    $State.ar_zip = $zip
    Save-State $State 'AR_EXPAND'
    $arRoot = Expand-ArPackage $zip

    Save-State $State 'RECONCILE'
    Reconcile-Ar $arRoot

    Save-State $State 'LOCAL_GATE'
    Invoke-LocalGate $arRoot

    Save-State $State 'PASS'
    $receipts = Write-Receipt 'PASS' '' $commit $dockerVersion $composeVersion
    Clear-Resume
    Write-Step 'SOAIACORE_LOCAL_POSTGRES_GATE=PASS'
    Write-Step "Receipts: $($receipts -join ', ')"
    Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
    Stop-Transcript | Out-Null
    exit 0
}
catch {
    $blocker = $_.Exception.Message
    Save-State $State 'BLOCKED'
    try { Write-Receipt 'BLOCKED' $blocker $commit $dockerVersion $composeVersion | Out-Null } catch { }
    Write-Error "SOAIACORE_LOCAL_POSTGRES_GATE=BLOCKED :: $blocker"
    if (-not $KeepFailedRuntime) {
        try {
            $compose = Join-Path $RepoPath 'deploy\local\ar\docker-compose.persistence.yml'
            $dockerCli = Resolve-DockerCli
            if ($dockerCli -and (Test-Path -LiteralPath $compose)) { & $dockerCli compose -f $compose down -v --remove-orphans *> $null }
        } catch { }
    }
    Stop-Transcript | Out-Null
    exit 1
}
