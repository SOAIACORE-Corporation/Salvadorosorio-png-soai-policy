#requires -Version 5.1
<#
SOAIACORE Rebuild P0 — Windows One-Shot v1.0
Architecture authority: v0.6 FINAL / FROZEN FOR P0
Purpose: bootstrap local Docker/WSL if required, reconcile AR package, execute real PostgreSQL+pgvector gate,
write receipts, and tear down disposable runtime. Safe to rerun.

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
        version = 1
        stage = 'INIT'
        repo_path = $RepoPath
        ar_zip = $ArZip
        started_at_utc = $StartUtc.ToString('o')
        last_updated_utc = $StartUtc.ToString('o')
        reboot_count = 0
        attempts = 0
    }
}

function Save-State([object]$State, [string]$Stage) {
    $State.stage = $Stage
    $State.last_updated_utc = (Get-Date).ToUniversalTime().ToString('o')
    $State | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $StateFile -Encoding UTF8
}

$State = Load-State
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
    Write-Step 'Administrative rights required for conditional Docker/WSL bootstrap. Relaunching elevated.'
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
        $v = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -Name PendingFileRenameOperations -ErrorAction SilentlyContinue).PendingFileRenameOperations
        if ($v) { return $true }
    } catch { }
    return $false
}

function Register-Resume {
    $cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -RepoPath `"$RepoPath`""
    if (-not [string]::IsNullOrWhiteSpace($ArZip)) { $cmd += " -ArZip `"$ArZip`"" }
    if (-not [string]::IsNullOrWhiteSpace($GitExe)) { $cmd += " -GitExe `"$GitExe`"" }
    if ($AutoReboot) { $cmd += ' -AutoReboot' }
    if ($KeepFailedRuntime) { $cmd += ' -KeepFailedRuntime' }
    New-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce' -Name $ResumeName -PropertyType String -Value $cmd -Force | Out-Null
}

function Clear-Resume {
    Remove-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce' -Name $ResumeName -ErrorAction SilentlyContinue
}

function Request-Reboot([string]$Reason) {
    $State.reboot_count = [int]$State.reboot_count + 1
    Save-State $State 'REBOOT_REQUIRED'
    Register-Resume
    Write-Step "REBOOT_REQUIRED: $Reason"
    if ($AutoReboot) {
        Write-Step 'Automatic reboot authorized. Rebooting in 30 seconds; RunOnce will resume the same one-shot.'
        shutdown.exe /r /t 30 /c "SOAIACORE Rebuild P0 one-shot resume" | Out-Null
    } else {
        Write-Step 'Resume has been registered. Restart Windows once; the same one-shot will continue automatically after sign-in.'
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
                $path = $_.Substring(3).Replace('\\','/')
                -not ($allowedPrefixes | Where-Object { $path.StartsWith($_, [StringComparison]::OrdinalIgnoreCase) })
            })
            if ($unexpected) { throw "REPO_NOT_CLEAN: unrelated changes: $($unexpected -join '; ')" }
            Write-Step 'PRECHECK: resuming with workflow-owned generated changes only.'
        }
        return (& $GitExe rev-parse HEAD).Trim()
    } finally { Pop-Location }
}

function Ensure-WslPrereqs {
    Write-Step 'Checking WSL2/VirtualMachinePlatform prerequisites.'
    $needsReboot = $false
    $features = @('Microsoft-Windows-Subsystem-Linux','VirtualMachinePlatform')
    foreach ($f in $features) {
        $state = (Get-WindowsOptionalFeature -Online -FeatureName $f).State
        if ($state -ne 'Enabled') {
            Write-Step "Enabling Windows feature $f"
            Enable-WindowsOptionalFeature -Online -FeatureName $f -All -NoRestart | Out-Null
            $needsReboot = $true
        }
    }
    if ($needsReboot -or (Test-PendingReboot)) { Request-Reboot 'WSL2/VirtualMachinePlatform feature activation' }
    try { wsl.exe --set-default-version 2 | Out-Null } catch { }
}

function Ensure-Winget {
    if (-not (Get-CommandPath 'winget.exe')) { throw 'WINGET_UNAVAILABLE: install Microsoft App Installer, then rerun same one-shot' }
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

function Ensure-DockerDesktop {
    $docker = Resolve-DockerCli
    if (-not $docker) {
        Write-Step 'Docker CLI/Desktop missing. Installing Docker Desktop idempotently via winget.'
        Ensure-Winget
        winget.exe install --exact --id Docker.DockerDesktop --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
        if ($LASTEXITCODE -ne 0) { throw "DOCKER_INSTALL_FAILED exit=$LASTEXITCODE" }
        if (Test-PendingReboot) { Request-Reboot 'Docker Desktop installation requested a reboot' }
        $docker = Resolve-DockerCli
        if (-not $docker) { throw 'DOCKER_CLI_MISSING_AFTER_INSTALL' }
    } else {
        Write-Step "Docker CLI already present: $docker"
    }

    $desktop = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
    if (Test-Path -LiteralPath $desktop) {
        $running = Get-Process 'Docker Desktop' -ErrorAction SilentlyContinue
        if (-not $running) {
            Write-Step 'Starting Docker Desktop.'
            Start-Process -FilePath $desktop | Out-Null
        }
    }

    $deadline = (Get-Date).AddMinutes(5)
    do {
        Start-Sleep -Seconds 5
        & $docker info *> $null
        if ($LASTEXITCODE -eq 0) { break }
    } while ((Get-Date) -lt $deadline)

    & $docker info *> $null
    if ($LASTEXITCODE -ne 0) { throw 'DOCKER_ENGINE_NOT_READY_AFTER_5_MIN' }
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
    $rootCandidates = Get-ChildItem -LiteralPath $dest -Directory
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
            if (Test-Path -LiteralPath $compose) { docker compose -f $compose down -v --remove-orphans *> $null }
        } catch { }
    }
    Stop-Transcript | Out-Null
    exit 1
}
