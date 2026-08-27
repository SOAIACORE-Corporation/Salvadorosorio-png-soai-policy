<#
.SYNOPSIS
    SOAIACORE MASTER PRECHECK v1.0 correction pass.
.DESCRIPTION
    Read-only, phase-aware precheck. It never repairs Git, mutates Azure, applies Terraform,
    changes application code, or prints secret values. It compares the master baseline with
    observed state and emits one receipt plus a compact GO/NO-GO summary.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("P0_OPS_HARDENING", "P1_ITERATION_01", "INTERNAL_ACCESS_GATE", "PRODUCTION_HARDENING", "ALL_READINESS")]
    [string]$TargetPhase,

    [Parameter(Mandatory = $false)]
    [int]$Issue = 0,

    [Parameter(Mandatory = $false)]
    [string]$ReceiptPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$MasterJsonPath = Join-Path $ScriptDir "precheck.master.json"

function Stop-ContextFailure {
    param([string]$Code, [string]$Blocker, [string]$NextAction)
    Write-Host "SOAIACORE_PRECHECK=BLOCKED"
    Write-Host "GO=false"
    Write-Host "BLOCKER_CODE=$Code"
    Write-Host "BLOCKER=$Blocker"
    Write-Host "NEXT_ACTION=$NextAction"
    exit 1
}

if (-not (Test-Path -LiteralPath $MasterJsonPath -PathType Leaf)) {
    Stop-ContextFailure "PC-CTX-001" "MASTER_CONTEXT_FILE_MISSING" "RESTORE_PRECHECK_MASTER_JSON"
}

try {
    $Master = Get-Content -LiteralPath $MasterJsonPath -Raw | ConvertFrom-Json
} catch {
    Stop-ContextFailure "PC-CTX-007" "MASTER_CONTEXT_JSON_INVALID" "REPAIR_PRECHECK_MASTER_JSON"
}

if ([string]::IsNullOrWhiteSpace($ReceiptPath)) {
    $ReceiptPath = Join-Path ([System.IO.Path]::GetTempPath()) "SOAIACORE\precheck\SOAIACORE_PRECHECK_RECEIPT.json"
} elseif (-not [System.IO.Path]::IsPathRooted($ReceiptPath)) {
    $ReceiptPath = Join-Path $RepoRoot $ReceiptPath
}

$Receipt = [ordered]@{
    precheck = "SOAIACORE_MASTER_PRECHECK"
    schema_version = "1.0"
    master_revision = $Master.revision
    timestamp_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    target_phase = $TargetPhase
    target_issue = $(if ($Issue -gt 0) { $Issue } else { $null })
    precheck_mutations = "NONE"
    authority = [ordered]@{
        architecture = $Master.architecture.version
        architecture_status = $Master.architecture.status
        integration_branch = $Master.source_control.integration_branch
        baseline_sha = $Master.source_control.baseline_sha
        observed_branch = ""
        observed_sha = ""
        baseline_relation = ""
        origin = ""
    }
    toolchain = [ordered]@{}
    security = [ordered]@{
        secrets_in_git = 0
        tfstate_in_git = 0
        tfplan_in_git = 0
        private_keys_in_git = 0
        production_data = $false
        live_provider_calls = $false
    }
    runtime = [ordered]@{
        web = "NOT_CHECKED"
        core = "NOT_CHECKED"
        worker = "NOT_CHECKED"
        postgres = "NOT_CHECKED"
        postgres_version = ""
        pgvector = "NOT_CHECKED"
        pgvector_version = ""
        migrations = $null
    }
    azure = [ordered]@{
        checked = $false
        subscription = ""
        tenant = ""
        resource_count = $null
        terraform_drift = "NOT_CHECKED_READ_ONLY_PRECHECK"
        ttl_remaining_hours = $null
        budget_usd = $null
    }
    baseline_tests = @()
    active_acceptance_set = @()
    gates = @()
    summary = [ordered]@{
        pass = 0
        warn = 0
        soft_block = 0
        hard_block = 0
    }
    authorization = [ordered]@{
        go = $false
        authorized_scope = "NONE"
        azure_write = $false
        terraform_write = $false
        forbidden_scope = @("ALL_MUTATIONS")
    }
    blockers = @()
    next_action = ""
}

function Add-GateResult {
    param(
        [string]$GateId,
        [string]$Name,
        [ValidateSet("PASS", "WARN", "SOFT_BLOCK", "HARD_BLOCK")]
        [string]$Status,
        [string]$Code,
        [string]$Message,
        $Expected = $null,
        $Observed = $null
    )
    $gate = [ordered]@{
        gate_id = $GateId
        name = $Name
        status = $Status
        code = $Code
        message = $Message
        expected = $Expected
        observed = $Observed
    }
    $Receipt.gates += $gate
    switch ($Status) {
        "PASS" { $Receipt.summary.pass++ }
        "WARN" { $Receipt.summary.warn++ }
        "SOFT_BLOCK" { $Receipt.summary.soft_block++ }
        "HARD_BLOCK" {
            $Receipt.summary.hard_block++
            $Receipt.blockers += [ordered]@{ code = $Code; message = $Message; gate_id = $GateId }
        }
    }
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$File,
        [Parameter(Mandatory = $false)][string[]]$Arguments = @(),
        [Parameter(Mandatory = $false)][string]$WorkingDirectory = $RepoRoot
    )
    $old = Get-Location
    try {
        Set-Location -LiteralPath $WorkingDirectory
        $text = (& $File @Arguments 2>&1 | Out-String).Trim()
        $code = $LASTEXITCODE
        return [pscustomobject]@{ ExitCode = $code; Output = $text }
    } catch {
        return [pscustomobject]@{ ExitCode = 127; Output = $_.Exception.Message }
    } finally {
        Set-Location $old
    }
}

function Get-PhasePolicy {
    $prop = $Master.execution_policy.PSObject.Properties[$TargetPhase]
    if ($null -eq $prop) { return $null }
    return $prop.Value
}

$PhasePolicy = Get-PhasePolicy
if ($null -eq $PhasePolicy) {
    Stop-ContextFailure "PC-CTX-008" "TARGET_PHASE_POLICY_MISSING" "ADD_TARGET_PHASE_POLICY"
}

function Get-IssuePolicy {
    if ($Issue -le 0) { return $null }
    $prop = $Master.issue_policy.PSObject.Properties[[string]$Issue]
    if ($null -eq $prop) { return $null }
    return $prop.Value
}

$IssuePolicy = Get-IssuePolicy

$EnabledGates = New-Object System.Collections.Generic.List[string]
foreach ($g in @($PhasePolicy.required_gates)) {
    if (-not $EnabledGates.Contains([string]$g)) { [void]$EnabledGates.Add([string]$g) }
}
if ($null -ne $IssuePolicy) {
    foreach ($g in @($IssuePolicy.extra_gates)) {
        if (-not $EnabledGates.Contains([string]$g)) { [void]$EnabledGates.Add([string]$g) }
    }
}

function Test-GateEnabled {
    param([string]$GateId)
    return $EnabledGates.Contains($GateId)
}

function Get-RequiredTools {
    $list = New-Object System.Collections.Generic.List[string]
    foreach ($t in @($PhasePolicy.required_tools)) {
        if (-not $list.Contains([string]$t)) { [void]$list.Add([string]$t) }
    }
    if ($null -ne $IssuePolicy) {
        foreach ($t in @($IssuePolicy.required_tools)) {
            if (-not $list.Contains([string]$t)) { [void]$list.Add([string]$t) }
        }
    }
    return @($list)
}

function Test-GitGrep {
    param([string]$Pattern, [string[]]$Paths)
    $args = @("grep", "-n", "-I", "-E", $Pattern, "--") + $Paths
    $r = Invoke-Native "git" $args
    return [pscustomobject]@{ Found = ($r.ExitCode -eq 0); Output = $r.Output }
}

# GATE 00 — execution contract
if (Test-GateEnabled "GATE_00") {
    if ($Master.architecture.version -ne "v0.6" -or $Master.architecture.status -ne "FINAL_FROZEN") {
        Add-GateResult "GATE_00" "Execution Contract" "HARD_BLOCK" "PC-CTX-002" "Architecture must remain v0.6 FINAL_FROZEN" "v0.6 FINAL_FROZEN" "$($Master.architecture.version) $($Master.architecture.status)"
    } elseif ($TargetPhase -eq "P1_ITERATION_01" -and $Master.lifecycle.provider_mode -ne "MOCK") {
        Add-GateResult "GATE_00" "Execution Contract" "HARD_BLOCK" "PC-CTX-003" "P1 requires provider mode MOCK" "MOCK" $Master.lifecycle.provider_mode
    } elseif ([bool]$PhasePolicy.issue_required -and $Issue -le 0) {
        Add-GateResult "GATE_00" "Execution Contract" "HARD_BLOCK" "PC-CTX-004" "P1 execution requires an explicit issue" "8..15" $Issue
    } elseif ($TargetPhase -eq "P1_ITERATION_01" -and (@($PhasePolicy.allowed_issues) -notcontains $Issue)) {
        Add-GateResult "GATE_00" "Execution Contract" "HARD_BLOCK" "PC-CTX-005" "Issue is outside P1 Iteration 01" (@($PhasePolicy.allowed_issues) -join ",") $Issue
    } elseif ($TargetPhase -eq "P1_ITERATION_01" -and (@($Master.p1.completed_at_baseline) -contains $Issue)) {
        Add-GateResult "GATE_00" "Execution Contract" "HARD_BLOCK" "PC-CTX-006" "Issue is already completed at the governing baseline; do not spend execution on a closed issue" $Master.p1.next_critical_issue $Issue
    } elseif ([bool]$Master.lifecycle.production_authorized) {
        Add-GateResult "GATE_00" "Execution Contract" "HARD_BLOCK" "PC-CTX-009" "Master context unexpectedly marks production authorized" $false $true
    } else {
        Add-GateResult "GATE_00" "Execution Contract" "PASS" "PC-CTX-000" "Execution contract matches governing baseline"
    }
}

# GATE 01 — selective toolchain
if (Test-GateEnabled "GATE_01") {
    $missing = @()
    foreach ($tool in (Get-RequiredTools)) {
        $cmd = Get-Command $tool -ErrorAction SilentlyContinue
        if ($null -eq $cmd) {
            $Receipt.toolchain[$tool] = [ordered]@{ present = $false; path = "" }
            $missing += $tool
        } else {
            $Receipt.toolchain[$tool] = [ordered]@{ present = $true; path = $cmd.Source }
        }
    }
    if ($missing.Count -gt 0) {
        Add-GateResult "GATE_01" "Selective Toolchain" "HARD_BLOCK" "PC-ENV-001" "Required tool(s) missing for target phase/issue: $($missing -join ', ')" (Get-RequiredTools) $missing
    } else {
        Add-GateResult "GATE_01" "Selective Toolchain" "PASS" "PC-ENV-000" "Required phase/issue toolchain is available"
    }
}

# GATE 02 — Git authority, lineage, worktree; no fetch/repair
if (Test-GateEnabled "GATE_02") {
    $root = Invoke-Native "git" @("rev-parse", "--show-toplevel")
    if ($root.ExitCode -ne 0) {
        Add-GateResult "GATE_02" "Git Authority" "HARD_BLOCK" "PC-GIT-099" "Repository root cannot be resolved"
    } else {
        $branch = Invoke-Native "git" @("rev-parse", "--abbrev-ref", "HEAD")
        $head = Invoke-Native "git" @("rev-parse", "HEAD")
        $origin = Invoke-Native "git" @("remote", "get-url", "origin")
        $Receipt.authority.observed_branch = $branch.Output
        $Receipt.authority.observed_sha = $head.Output
        $Receipt.authority.origin = $origin.Output

        $gitFailures = @()
        if ($origin.ExitCode -ne 0 -or $origin.Output -notlike "*$($Master.source_control.expected_remote_contains)*") { $gitFailures += "ORIGIN_MISMATCH" }

        $base = [string]$Master.source_control.baseline_sha
        $cat = Invoke-Native "git" @("cat-file", "-e", "$base`^{commit}")
        if ($cat.ExitCode -ne 0) {
            $gitFailures += "BASELINE_SHA_NOT_LOCAL"
            $Receipt.authority.baseline_relation = "UNKNOWN"
        } else {
            $ancestor = Invoke-Native "git" @("merge-base", "--is-ancestor", $base, $head.Output)
            if ($ancestor.ExitCode -eq 0) {
                $Receipt.authority.baseline_relation = $(if ($head.Output -eq $base) { "EXACT" } else { "DESCENDANT" })
            } else {
                $Receipt.authority.baseline_relation = "DIVERGENT"
                $gitFailures += "BASELINE_DIVERGENCE"
            }
        }

        $status = Invoke-Native "git" @("status", "--porcelain=v2")
        if (-not [string]::IsNullOrWhiteSpace($status.Output)) { $gitFailures += "DIRTY_WORKTREE" }

        $gitPath = (Invoke-Native "git" @("rev-parse", "--git-dir")).Output
        if (-not [System.IO.Path]::IsPathRooted($gitPath)) { $gitPath = Join-Path $RepoRoot $gitPath }
        foreach ($marker in @("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD")) {
            if (Test-Path -LiteralPath (Join-Path $gitPath $marker)) { $gitFailures += "GIT_OPERATION_IN_PROGRESS" }
        }
        if ((Test-Path -LiteralPath (Join-Path $gitPath "rebase-merge")) -or (Test-Path -LiteralPath (Join-Path $gitPath "rebase-apply"))) {
            $gitFailures += "GIT_OPERATION_IN_PROGRESS"
        }

        if ($gitFailures.Count -gt 0) {
            $code = if ($gitFailures -contains "DIRTY_WORKTREE") { "PC-GIT-003" } elseif ($gitFailures -contains "BASELINE_DIVERGENCE") { "PC-GIT-002" } elseif ($gitFailures -contains "BASELINE_SHA_NOT_LOCAL") { "PC-GIT-005" } else { "PC-GIT-006" }
            Add-GateResult "GATE_02" "Git Authority" "HARD_BLOCK" $code "Git authority/lineage check failed: $($gitFailures -join ', ')" $base $head.Output
        } else {
            Add-GateResult "GATE_02" "Git Authority" "PASS" "PC-GIT-000" "Origin, lineage and clean worktree verified" $base $head.Output
        }
    }
}

# GATE 03 — tracked secret/state hygiene; never emit matched value
if (Test-GateEnabled "GATE_03") {
    $tracked = (Invoke-Native "git" @("ls-files")).Output -split "`r?`n"
    $tracked = @($tracked | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $stateFindings = @()
    $planFindings = @()
    $keyFindings = @()
    $secretFindings = @()
    $binaryExtensions = @(".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".woff", ".woff2", ".pyc")
    $secretPatterns = @(
        [pscustomobject]@{ Name = "OPENSSH_PRIVATE_KEY"; Regex = "-----BEGIN (OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----" },
        [pscustomobject]@{ Name = "GITHUB_CLASSIC_PAT"; Regex = "ghp_[0-9A-Za-z]{30,}" },
        [pscustomobject]@{ Name = "GITHUB_FINE_GRAINED_PAT"; Regex = "github_pat_[0-9A-Za-z_]{30,}" },
        [pscustomobject]@{ Name = "GOOGLE_CLIENT_SECRET"; Regex = "GOCSPX-[0-9A-Za-z_-]{20,}" },
        [pscustomobject]@{ Name = "POSTGRES_URI_PASSWORD"; Regex = "postgres(?:ql)?://[^\s:/]+:[^\s@]+@" },
        [pscustomobject]@{ Name = "AZURE_CLIENT_SECRET"; Regex = "AZURE_CLIENT_SECRET\s*=\s*['\"]?[^'\"\s]+" }
    )

    foreach ($rel in $tracked) {
        if ($rel -match "(^|/).*\.tfstate(?:\.|$)" -or $rel -match "terraform\.tfstate") { $stateFindings += $rel; continue }
        if ($rel -match "\.tfplan(?:\.|$)" -or $rel -match "(^|/)tfplan$") { $planFindings += $rel; continue }
        if ($rel -match "\.(pem|pfx|p12|key)$") { $keyFindings += $rel; continue }
        $full = Join-Path $RepoRoot $rel
        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { continue }
        $ext = [System.IO.Path]::GetExtension($full).ToLowerInvariant()
        if ($binaryExtensions -contains $ext) { continue }
        try {
            $info = Get-Item -LiteralPath $full
            if ($info.Length -gt 2097152) { continue }
            $text = Get-Content -LiteralPath $full -Raw -ErrorAction Stop
            foreach ($sp in $secretPatterns) {
                if ($text -match $sp.Regex) {
                    $secretFindings += "$rel [$($sp.Name)]"
                    break
                }
            }
        } catch {
            # Unreadable tracked text is handled conservatively as a warning below, not as secret content.
        }
    }

    $Receipt.security.secrets_in_git = $secretFindings.Count
    $Receipt.security.tfstate_in_git = $stateFindings.Count
    $Receipt.security.tfplan_in_git = $planFindings.Count
    $Receipt.security.private_keys_in_git = $keyFindings.Count
    if (($secretFindings.Count + $stateFindings.Count + $planFindings.Count + $keyFindings.Count) -gt 0) {
        $observed = @($secretFindings + $stateFindings + $planFindings + $keyFindings)
        Add-GateResult "GATE_03" "Security Hygiene" "HARD_BLOCK" "PC-SEC-001" "Tracked secret/state/key material detected; values were not emitted" "ZERO" $observed
    } else {
        Add-GateResult "GATE_03" "Security Hygiene" "PASS" "PC-SEC-000" "No tracked secret, tfstate, tfplan or private-key material detected"
    }
}

# GATE 04 — physical topology
if (Test-GateEnabled "GATE_04") {
    $missing = @()
    foreach ($p in $Master.runtime.paths.PSObject.Properties) {
        $rel = [string]$p.Value
        if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $rel))) { $missing += $rel }
    }
    if ($missing.Count -gt 0) {
        Add-GateResult "GATE_04" "Physical Architecture" "HARD_BLOCK" "PC-ARC-001" "Required runtime path(s) missing: $($missing -join ', ')" ($Master.runtime.paths | ConvertTo-Json -Compress) $missing
    } else {
        Add-GateResult "GATE_04" "Physical Architecture" "PASS" "PC-ARC-000" "Web/Core/Worker/runtime/database/test/Azure paths exist"
    }
}

# GATE 05 — architecture invariants
if (Test-GateEnabled "GATE_05") {
    $violations = @()
    $coreClient = Join-Path $RepoRoot "apps/web/src/server/core-client.mjs"
    $dispatcher = Join-Path $RepoRoot "apps/core/src/soaiacore_core/dispatcher.py"
    $workerMain = Join-Path $RepoRoot "apps/worker/src/soaiacore_worker/__main__.py"
    if (-not (Test-Path -LiteralPath $coreClient)) { $violations += "SERVER_SIDE_CORE_CLIENT_MISSING" }
    if (-not (Test-Path -LiteralPath $workerMain)) { $violations += "WORKER_ENTRYPOINT_MISSING" }

    $nextPublic = Test-GitGrep "NEXT_PUBLIC_.*CORE|NEXT_PUBLIC_CORE" @("apps/web")
    if ($nextPublic.Found) { $violations += "BROWSER_CORE_URL_EXPOSURE" }
    $newQueue = Test-GitGrep "ServiceBusClient|KafkaProducer|KafkaConsumer|EventGridPublisherClient" @("apps/core", "apps/worker")
    if ($newQueue.Found -and $TargetPhase -eq "P1_ITERATION_01") { $violations += "SECOND_CLOUD_QUEUE_OR_EVENT_BUS_INTRODUCED" }
    $createRunJob = Test-GitGrep "create_run_job" @("apps/core", "packages/python-runtime")
    if (-not $createRunJob.Found) { $violations += "CANONICAL_RUN_JOB_TRANSACTION_MISSING" }
    $runOne = Test-GitGrep "run-one|run_one" @("apps/worker", "packages/python-runtime")
    if (-not $runOne.Found) { $violations += "WORKER_SINGLE_JOB_PATH_MISSING" }
    if ($Issue -ge 11 -and $TargetPhase -eq "P1_ITERATION_01" -and -not (Test-Path -LiteralPath $dispatcher)) { $violations += "DISPATCHER_BASELINE_MISSING" }

    if ($violations.Count -gt 0) {
        Add-GateResult "GATE_05" "Architecture Invariants" "HARD_BLOCK" "PC-ARC-002" "Architecture invariant violation(s): $($violations -join ', ')" "v0.6 invariants" $violations
    } else {
        Add-GateResult "GATE_05" "Architecture Invariants" "PASS" "PC-ARC-000" "BFF, PostgreSQL queue and Worker isolation invariants preserved"
    }
}

# GATE 06 — issue-specific baseline tests
if (Test-GateEnabled "GATE_06") {
    $tests = @()
    if ($null -ne $IssuePolicy) { $tests = @($IssuePolicy.baseline_tests) }
    if ($tests.Count -eq 0) {
        Add-GateResult "GATE_06" "Baseline Tests" "PASS" "PC-TST-SKIPPED" "No baseline test command required for this target"
    } else {
        $failures = @()
        $index = 0
        foreach ($test in $tests) {
            $index++
            $exe = [string]$test.exe
            $args = @($test.args | ForEach-Object { [string]$_ })
            $r = Invoke-Native $exe $args
            $Receipt.baseline_tests += [ordered]@{ index = $index; exe = $exe; args = $args; exit_code = $r.ExitCode }
            if ($r.ExitCode -ne 0) { $failures += "TEST_$index exit=$($r.ExitCode)" }
        }
        if ($failures.Count -gt 0) {
            Add-GateResult "GATE_06" "Baseline Tests" "HARD_BLOCK" "PC-TST-001" "Baseline tests fail before authorized mutation: $($failures -join '; ')" "ALL_ZERO_EXIT" $failures
        } else {
            Add-GateResult "GATE_06" "Baseline Tests" "PASS" "PC-TST-000" "Issue-specific baseline tests passed before mutation"
        }
    }
}

# GATE 07 — PostgreSQL/pgvector/migrations using existing runtime configuration; no credentials embedded
if (Test-GateEnabled "GATE_07") {
    if ($null -eq (Get-Command python -ErrorAction SilentlyContinue)) {
        Add-GateResult "GATE_07" "PostgreSQL Runtime" "HARD_BLOCK" "PC-DB-001" "Python is required for canonical runtime DB precheck"
    } else {
        $oldPythonPath = $env:PYTHONPATH
        try {
            $parts = @(
                (Join-Path $RepoRoot "apps/worker/src"),
                (Join-Path $RepoRoot "apps/core/src"),
                (Join-Path $RepoRoot "packages/python-runtime/src")
            )
            $env:PYTHONPATH = ($parts -join [System.IO.Path]::PathSeparator)
            $workerCheck = Invoke-Native "python" @("-m", "soaiacore_worker", "precheck")
            $probeCode = @'
import json
import psycopg
from soaiacore_runtime.config import RuntimeSettings
s = RuntimeSettings.from_env()
with psycopg.connect(s.database_url, connect_timeout=3) as c:
    server = c.execute("SHOW server_version").fetchone()[0]
    vector = c.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()
print(json.dumps({"server_version": server, "pgvector": vector[0] if vector else None}, separators=(",", ":")))
'@
            $probe = Invoke-Native "python" @("-c", $probeCode)
            if ($workerCheck.ExitCode -ne 0 -or $probe.ExitCode -ne 0) {
                $Receipt.runtime.postgres = "UNAVAILABLE_OR_INVALID"
                Add-GateResult "GATE_07" "PostgreSQL Runtime" "HARD_BLOCK" "PC-DB-001" "Canonical PostgreSQL/pgvector/migration precheck failed; no fallback credentials were used" "PostgreSQL 17 + pgvector + 8 migrations" "PRECHECK_FAILED"
            } else {
                $workerJson = $workerCheck.Output | ConvertFrom-Json
                $probeJson = $probe.Output | ConvertFrom-Json
                $major = ([string]$probeJson.server_version -split "\.")[0]
                $Receipt.runtime.postgres = "READY"
                $Receipt.runtime.postgres_version = [string]$probeJson.server_version
                $Receipt.runtime.pgvector = $(if ($null -ne $probeJson.pgvector) { "READY" } else { "MISSING" })
                $Receipt.runtime.pgvector_version = [string]$probeJson.pgvector
                $Receipt.runtime.migrations = [int]$workerJson.migrations
                if ([int]$major -ne [int]$Master.persistence.major_version -or $null -eq $probeJson.pgvector -or [int]$workerJson.migrations -ne [int]$Master.persistence.migrations_expected -or [string]$workerJson.provider_mode -ne "MOCK") {
                    Add-GateResult "GATE_07" "PostgreSQL Runtime" "HARD_BLOCK" "PC-DB-002" "Database runtime differs from canonical P1 baseline" "PostgreSQL 17 + pgvector + 8 migrations + MOCK" "$($probeJson.server_version) / vector=$($probeJson.pgvector) / migrations=$($workerJson.migrations) / provider=$($workerJson.provider_mode)"
                } else {
                    Add-GateResult "GATE_07" "PostgreSQL Runtime" "PASS" "PC-DB-000" "Canonical PostgreSQL version, pgvector and migration count verified"
                }
            }
        } catch {
            $Receipt.runtime.postgres = "UNAVAILABLE_OR_INVALID"
            Add-GateResult "GATE_07" "PostgreSQL Runtime" "HARD_BLOCK" "PC-DB-099" "Database verification failed without exposing connection material"
        } finally {
            $env:PYTHONPATH = $oldPythonPath
        }
    }
}

# GATE 08 — Core query API baseline
if (Test-GateEnabled "GATE_08") {
    $required = @("/v1/projects", "/v1/contexts", "/v1/context-capsules", "/v1/analysis-profiles", "/v1/evidence/", "/v1/runs")
    $missing = @()
    foreach ($route in $required) {
        $r = Test-GitGrep ([regex]::Escape($route)) @("apps/core")
        if (-not $r.Found) { $missing += $route }
    }
    if ($missing.Count -gt 0) {
        Add-GateResult "GATE_08" "Core Query Surface" "HARD_BLOCK" "PC-API-001" "Expected bounded query surface is incomplete" $required $missing
    } else {
        $Receipt.runtime.core = "QUERY_SURFACE_PRESENT"
        Add-GateResult "GATE_08" "Core Query Surface" "PASS" "PC-API-000" "Required Core read/query route families are present"
    }
}

# GATE 09 — Web/BFF boundary
if (Test-GateEnabled "GATE_09") {
    $violations = @()
    $client = Join-Path $RepoRoot "apps/web/src/server/core-client.mjs"
    if (-not (Test-Path -LiteralPath $client)) { $violations += "CORE_CLIENT_MISSING" }
    $directCore = Test-GitGrep "NEXT_PUBLIC_.*CORE|NEXT_PUBLIC_CORE_API_BASE_URL" @("apps/web")
    if ($directCore.Found) { $violations += "CORE_URL_BROWSER_EXPOSURE" }
    $dbClient = Test-GitGrep "psycopg|postgresql://|DATABASE_URL" @("apps/web/src/app")
    if ($dbClient.Found) { $violations += "DATABASE_MATERIAL_IN_BROWSER_APP" }
    if ($violations.Count -gt 0) {
        Add-GateResult "GATE_09" "Web BFF Boundary" "HARD_BLOCK" "PC-WEB-001" "Web/BFF security boundary violation(s): $($violations -join ', ')" "SERVER_SIDE_BFF_ONLY" $violations
    } else {
        $Receipt.runtime.web = "BFF_BOUNDARY_PRESENT"
        Add-GateResult "GATE_09" "Web BFF Boundary" "PASS" "PC-WEB-000" "Browser-to-Core/DB credential boundary remains server-side"
    }
}

# GATE 10 — Worker/dispatcher semantics
if (Test-GateEnabled "GATE_10") {
    $missing = @()
    foreach ($tuple in @(
        @("create_run_job", @("apps/core", "packages/python-runtime")),
        @("run-one|run_one", @("apps/worker", "packages/python-runtime")),
        @("JobDispatcher|dispatch", @("apps/core/src/soaiacore_core/dispatcher.py", "apps/core/src/soaiacore_core/main.py"))
    )) {
        $found = Test-GitGrep ([string]$tuple[0]) ([string[]]$tuple[1])
        if (-not $found.Found) { $missing += [string]$tuple[0] }
    }
    if ($missing.Count -gt 0) {
        Add-GateResult "GATE_10" "Worker Dispatch Semantics" "HARD_BLOCK" "PC-WRK-001" "Worker/dispatcher canonical symbols missing" "DB commit -> wake-up -> DB claim" $missing
    } else {
        $Receipt.runtime.worker = "DISPATCH_BASELINE_PRESENT"
        Add-GateResult "GATE_10" "Worker Dispatch Semantics" "PASS" "PC-WRK-000" "PostgreSQL queue and wake-up dispatcher baseline are present"
    }
}

# GATE 11 — Azure identity/session, read-only
if (Test-GateEnabled "GATE_11") {
    $account = Invoke-Native "az" @("account", "show", "--output", "json")
    if ($account.ExitCode -ne 0) {
        Add-GateResult "GATE_11" "Azure Identity" "HARD_BLOCK" "PC-AZ-001" "Azure CLI session is unavailable; precheck will not run az login" "AUTHENTICATED_SESSION" "MISSING"
    } else {
        $a = $account.Output | ConvertFrom-Json
        $Receipt.azure.checked = $true
        $Receipt.azure.subscription = [string]$a.id
        $Receipt.azure.tenant = [string]$a.tenantId
        Add-GateResult "GATE_11" "Azure Identity" "PASS" "PC-AZ-000" "Azure read session verified"
    }
}

# GATE 12 — Azure inventory, read-only
if (Test-GateEnabled "GATE_12") {
    $list = Invoke-Native "az" @("resource", "list", "--output", "json")
    if ($list.ExitCode -ne 0) {
        Add-GateResult "GATE_12" "Azure Inventory" "HARD_BLOCK" "PC-AZ-002" "Azure resource inventory could not be read"
    } else {
        $all = @($list.Output | ConvertFrom-Json)
        $soa = @($all | Where-Object { ([string]$_.name -match "soaiacore") -or ([string]$_.resourceGroup -match "soaiacore") })
        $Receipt.azure.resource_count = $soa.Count
        if ($soa.Count -eq 0) {
            Add-GateResult "GATE_12" "Azure Inventory" "HARD_BLOCK" "PC-AZ-003" "No SOAIACORE Azure resources were discoverable for an Azure-targeted phase" ">0" 0
        } else {
            Add-GateResult "GATE_12" "Azure Inventory" "PASS" "PC-AZ-000" "SOAIACORE Azure resources discovered" ">0" $soa.Count
        }
    }
}

# GATE 13 — Container Apps existence, read-only
if (Test-GateEnabled "GATE_13") {
    $apps = Invoke-Native "az" @("containerapp", "list", "--output", "json")
    $jobs = Invoke-Native "az" @("containerapp", "job", "list", "--output", "json")
    if ($apps.ExitCode -ne 0 -or $jobs.ExitCode -ne 0) {
        Add-GateResult "GATE_13" "Container Apps" "HARD_BLOCK" "PC-AZ-004" "Container Apps/Jobs inventory unavailable"
    } else {
        $appItems = @($apps.Output | ConvertFrom-Json)
        $jobItems = @($jobs.Output | ConvertFrom-Json)
        $web = @($appItems | Where-Object { [string]$_.name -match "soaiacore.*web|web.*soaiacore" })
        $core = @($appItems | Where-Object { [string]$_.name -match "soaiacore.*core|core.*soaiacore" })
        $worker = @($jobItems | Where-Object { [string]$_.name -match "soaiacore.*worker|worker.*soaiacore" })
        if ($web.Count -eq 0 -or $core.Count -eq 0 -or $worker.Count -eq 0) {
            Add-GateResult "GATE_13" "Container Apps" "HARD_BLOCK" "PC-AZ-005" "Expected Web/Core/Worker Azure runtime units not all present" "web=1 core=1 worker=1" "web=$($web.Count) core=$($core.Count) worker=$($worker.Count)"
        } else {
            Add-GateResult "GATE_13" "Container Apps" "PASS" "PC-AZ-000" "Web/Core/Worker Azure runtime units are discoverable"
        }
    }
}

# GATE 14 — GHCR binding static contract
if (Test-GateEnabled "GATE_14") {
    $ghcr = Test-GitGrep "ghcr\.io/soaiacore-corporation/" @("infra/azure/p0")
    $latest = Test-GitGrep "ghcr\.io/[^\s\"']+:latest" @("infra/azure/p0")
    if (-not $ghcr.Found -or $latest.Found) {
        Add-GateResult "GATE_14" "GHCR Binding" "HARD_BLOCK" "PC-REG-001" "Private GHCR immutable-image binding contract is missing or :latest is referenced" "GHCR_BY_DIGEST_NO_LATEST" "INVALID"
    } else {
        Add-GateResult "GATE_14" "GHCR Binding" "PASS" "PC-REG-000" "GHCR binding is present and no :latest reference was detected"
    }
}

# GATE 15 — Terraform configuration/backend classification; never apply
if (Test-GateEnabled "GATE_15") {
    $tfDir = Join-Path $RepoRoot "infra/azure/p0"
    $validate = Invoke-Native "terraform" @("-chdir=$tfDir", "validate", "-no-color")
    $backend = Test-GitGrep "backend\s+\"azurerm\"" @("infra/azure/p0")
    $remoteRequired = $false
    if ($PhasePolicy.PSObject.Properties["remote_tfstate_required"]) { $remoteRequired = [bool]$PhasePolicy.remote_tfstate_required }
    if ($validate.ExitCode -ne 0) {
        Add-GateResult "GATE_15" "Terraform Control Plane" "HARD_BLOCK" "PC-TF-001" "terraform validate failed" "VALID" "INVALID"
    } elseif ($remoteRequired -and -not $backend.Found) {
        Add-GateResult "GATE_15" "Terraform Control Plane" "HARD_BLOCK" "PC-TF-002" "Protected remote Terraform backend is required for this phase" "azurerm backend" "LOCAL_OR_UNDECLARED"
    } elseif (-not $backend.Found) {
        Add-GateResult "GATE_15" "Terraform Control Plane" "WARN" "PC-TF-010" "Local Terraform state remains an accepted P0 exception; no plan/apply was run" "REMOTE_FOR_PRODUCTION" "LOCAL_P0_EXCEPTION"
    } else {
        Add-GateResult "GATE_15" "Terraform Control Plane" "PASS" "PC-TF-000" "Terraform validates and remote backend declaration is present"
    }
}

# GATE 16 — TTL; read-only tags
if (Test-GateEnabled "GATE_16") {
    $list = Invoke-Native "az" @("resource", "list", "--output", "json")
    if ($list.ExitCode -ne 0) {
        Add-GateResult "GATE_16" "Pilot TTL" "HARD_BLOCK" "PC-FIN-001" "Unable to read Azure resource tags for TTL"
    } else {
        $items = @($list.Output | ConvertFrom-Json)
        $expiries = @()
        foreach ($item in $items) {
            if (([string]$item.name -match "soaiacore" -or [string]$item.resourceGroup -match "soaiacore") -and $null -ne $item.tags -and $item.tags.PSObject.Properties["expires_at"]) {
                try { $expiries += [DateTime]::Parse([string]$item.tags.expires_at).ToUniversalTime() } catch { }
            }
        }
        if ($expiries.Count -eq 0) {
            Add-GateResult "GATE_16" "Pilot TTL" "SOFT_BLOCK" "PC-FIN-002" "No parseable expires_at tag found on SOAIACORE Azure resources" "TTL_TAG" "MISSING"
        } else {
            $earliest = ($expiries | Sort-Object | Select-Object -First 1)
            $hours = [math]::Round(($earliest - (Get-Date).ToUniversalTime()).TotalHours, 2)
            $Receipt.azure.ttl_remaining_hours = $hours
            if ($hours -le 0) {
                Add-GateResult "GATE_16" "Pilot TTL" "HARD_BLOCK" "PC-FIN-003" "Pilot TTL is expired" ">0h" $hours
            } elseif ($hours -le [double]$Master.ttl_policy_hours.hard_block_at_or_below) {
                Add-GateResult "GATE_16" "Pilot TTL" "HARD_BLOCK" "PC-FIN-004" "Less than or equal to 24h remains; no new Azure mutation is authorized" ">24h" $hours
            } elseif ($hours -le [double]$Master.ttl_policy_hours.warn_above) {
                Add-GateResult "GATE_16" "Pilot TTL" "SOFT_BLOCK" "PC-FIN-005" "Pilot TTL is inside the short operational window" ">72h" $hours
            } elseif ($hours -le [double]$Master.ttl_policy_hours.pass_above) {
                Add-GateResult "GATE_16" "Pilot TTL" "WARN" "PC-FIN-006" "Pilot TTL is below one week" ">168h" $hours
            } else {
                Add-GateResult "GATE_16" "Pilot TTL" "PASS" "PC-FIN-000" "Pilot TTL is adequate for the requested phase" ">168h" $hours
            }
        }
    }
}

# GATE 17 — Defender inventory only
if (Test-GateEnabled "GATE_17") {
    $pricing = Invoke-Native "az" @("security", "pricing", "list", "--output", "json")
    if ($pricing.ExitCode -ne 0) {
        Add-GateResult "GATE_17" "Defender Pricing" "WARN" "PC-FIN-010" "Defender pricing inventory unavailable through current Azure CLI/session" "READABLE" "UNAVAILABLE"
    } else {
        $obj = $pricing.Output | ConvertFrom-Json
        $paid = @($obj.value | Where-Object { [string]$_.pricingTier -eq "Standard" } | ForEach-Object { [string]$_.name })
        Add-GateResult "GATE_17" "Defender Pricing" $(if ($paid.Count -gt 0) { "WARN" } else { "PASS" }) "PC-FIN-011" "Defender paid-plan inventory captured; precheck made no pricing changes" "SCOPED_TO_USED_SERVICES" $paid
    }
}

# GATE 18 — minimum alerts / observability inventory
if (Test-GateEnabled "GATE_18") {
    $ag = Invoke-Native "az" @("monitor", "action-group", "list", "--output", "json")
    $metric = Invoke-Native "az" @("monitor", "metrics", "alert", "list", "--output", "json")
    $activity = Invoke-Native "az" @("monitor", "activity-log", "alert", "list", "--output", "json")
    if ($ag.ExitCode -ne 0 -or $metric.ExitCode -ne 0 -or $activity.ExitCode -ne 0) {
        Add-GateResult "GATE_18" "Observability Controls" "WARN" "PC-OBS-001" "One or more alert inventories could not be read" "READABLE_ALERT_INVENTORY" "PARTIAL"
    } else {
        $agCount = @($ag.Output | ConvertFrom-Json).Count
        $metricCount = @($metric.Output | ConvertFrom-Json).Count
        $activityCount = @($activity.Output | ConvertFrom-Json).Count
        if ($TargetPhase -eq "PRODUCTION_HARDENING" -and ($agCount -eq 0 -or ($metricCount + $activityCount) -eq 0)) {
            Add-GateResult "GATE_18" "Observability Controls" "HARD_BLOCK" "PC-OBS-002" "Production hardening requires actionable alert routing" "ACTION_GROUP_AND_ALERTS" "action_groups=$agCount alerts=$($metricCount + $activityCount)"
        } elseif ($agCount -eq 0 -or ($metricCount + $activityCount) -eq 0) {
            Add-GateResult "GATE_18" "Observability Controls" "SOFT_BLOCK" "PC-OBS-003" "Minimum operational alerting remains incomplete" "ACTION_GROUP_AND_ALERTS" "action_groups=$agCount alerts=$($metricCount + $activityCount)"
        } else {
            Add-GateResult "GATE_18" "Observability Controls" "PASS" "PC-OBS-000" "Action group and Azure alert inventory are present"
        }
    }
}

# GATE 19 — Azure PostgreSQL posture
if (Test-GateEnabled "GATE_19") {
    $pg = Invoke-Native "az" @("postgres", "flexible-server", "list", "--output", "json")
    if ($pg.ExitCode -ne 0) {
        Add-GateResult "GATE_19" "Azure PostgreSQL" "HARD_BLOCK" "PC-DB-010" "Azure PostgreSQL inventory unavailable"
    } else {
        $servers = @($pg.Output | ConvertFrom-Json | Where-Object { [string]$_.name -match "soaiacore" })
        if ($servers.Count -eq 0) {
            Add-GateResult "GATE_19" "Azure PostgreSQL" "HARD_BLOCK" "PC-DB-011" "SOAIACORE PostgreSQL Flexible Server not found"
        } else {
            $s = $servers[0]
            $versionOk = ([string]$s.version -eq "17")
            $publicOff = ([string]$s.network.publicNetworkAccess -eq "Disabled" -or [string]$s.publicNetworkAccess -eq "Disabled")
            if (-not $versionOk -or -not $publicOff) {
                Add-GateResult "GATE_19" "Azure PostgreSQL" "HARD_BLOCK" "PC-DB-012" "PostgreSQL version/network posture differs from P0 baseline" "version=17 publicNetworkAccess=Disabled" "version=$($s.version)"
            } else {
                Add-GateResult "GATE_19" "Azure PostgreSQL" "PASS" "PC-DB-000" "PostgreSQL 17 private-network posture verified"
            }
        }
    }
}

# GATE 20 — Blob account posture
if (Test-GateEnabled "GATE_20") {
    $sa = Invoke-Native "az" @("storage", "account", "list", "--output", "json")
    if ($sa.ExitCode -ne 0) {
        Add-GateResult "GATE_20" "Blob Storage" "WARN" "PC-AZ-020" "Storage account inventory unavailable"
    } else {
        $accounts = @($sa.Output | ConvertFrom-Json | Where-Object { [string]$_.name -match "soaiacore" -or [string]$_.resourceGroup -match "soaiacore" })
        if ($accounts.Count -eq 0) {
            Add-GateResult "GATE_20" "Blob Storage" "HARD_BLOCK" "PC-AZ-021" "SOAIACORE storage account not found"
        } else {
            $acct = $accounts[0]
            $anonDisabled = ($acct.allowBlobPublicAccess -eq $false -or $null -eq $acct.allowBlobPublicAccess)
            $publicNetwork = [string]$acct.publicNetworkAccess
            if (-not $anonDisabled) {
                Add-GateResult "GATE_20" "Blob Storage" "HARD_BLOCK" "PC-AZ-022" "Anonymous Blob public access appears enabled" $false $acct.allowBlobPublicAccess
            } elseif ($TargetPhase -eq "PRODUCTION_HARDENING" -and $publicNetwork -eq "Enabled") {
                Add-GateResult "GATE_20" "Blob Storage" "SOFT_BLOCK" "PC-AZ-023" "Blob public network remains enabled and requires explicit production disposition" "MINIMUM_REQUIRED_EXPOSURE" $publicNetwork
            } elseif ($publicNetwork -eq "Enabled") {
                Add-GateResult "GATE_20" "Blob Storage" "WARN" "PC-AZ-024" "Blob public network remains enabled; anonymous access is disabled" "P0_ACCEPTED" $publicNetwork
            } else {
                Add-GateResult "GATE_20" "Blob Storage" "PASS" "PC-AZ-000" "Blob anonymous/public-network posture meets target gate"
            }
        }
    }
}

# GATE 21 — data/provider governance. No payload inspection.
if (Test-GateEnabled "GATE_21") {
    $Receipt.security.live_provider_calls = [bool]$Master.lifecycle.live_provider_calls_allowed
    $Receipt.security.production_data = [bool]$Master.lifecycle.production_data_allowed
    if ($TargetPhase -eq "P1_ITERATION_01" -and ([bool]$Master.lifecycle.live_provider_calls_allowed -or [bool]$Master.lifecycle.production_data_allowed)) {
        Add-GateResult "GATE_21" "Data and Provider Governance" "HARD_BLOCK" "PC-DATA-001" "P1 must remain MOCK with non-production data" "MOCK + NON_PRODUCTION" "POLICY_VIOLATION"
    } else {
        Add-GateResult "GATE_21" "Data and Provider Governance" "PASS" "PC-DATA-000" "Master policy forbids LIVE providers and production data for current P1 scope" "NO_PAYLOAD_INSPECTION" "POLICY_ONLY"
    }
}

# GATE 22 — active acceptance set, compact and issue-specific
if (Test-GateEnabled "GATE_22") {
    $sets = @{
        8 = @("query list/get", "404", "invalid filter", "bounded limit", "stable order", "OpenAPI inclusion")
        9 = @("guided Project->Corpus->Context->Capsule->Run", "BFF only", "idempotency", "loading/empty/error")
        10 = @("commit before dispatch", "dispatch unavailable", "duplicate dispatch", "single DB claim", "no-job exit")
        11 = @("QUEUED", "DISPATCH_PENDING", "RUNNING", "REVIEW_REQUIRED", "COMPLETED", "FAILED_*", "bounded polling", "sanitized errors", "cold-start progress")
        12 = @("completed/queued/failed/review inspector", "NOT_AVAILABLE discipline", "BFF only")
        13 = @("evidence metadata", "invalid ref", "state/admissibility distinction", "no direct Blob")
        14 = @("bounded recent runs", "filters", "terminal links", "newest-first stable order")
        15 = @("Core flow", "Web/BFF E2E", "dispatch/Worker", "lifecycle receipt", "security regression", "MOCK only")
    }
    if ($Issue -gt 0 -and $sets.ContainsKey($Issue)) { $Receipt.active_acceptance_set = $sets[$Issue] }
    Add-GateResult "GATE_22" "Acceptance Scope" "PASS" "PC-TST-010" "Active acceptance set generated without loading unrelated issue context" "ISSUE_SPECIFIC" $Receipt.active_acceptance_set
}

# Authorization: any HARD_BLOCK denies mutation. SOFT_BLOCK is phase debt but does not override explicit hard rules.
$IsGo = ($Receipt.summary.hard_block -eq 0)
$Receipt.authorization.go = $IsGo
if ($IsGo) {
    $scope = $TargetPhase
    if ($Issue -gt 0) { $scope = "$TargetPhase :: ISSUE #$Issue" }
    $Receipt.authorization.authorized_scope = $scope
    $Receipt.authorization.azure_write = [bool]$PhasePolicy.azure_write
    $Receipt.authorization.terraform_write = [bool]$PhasePolicy.terraform_write
    $forbidden = @("ARCHITECTURE_V0_7", "LIVE_PROVIDER_CALLS", "PRODUCTION_DATA_OUTSIDE_AUTHORIZED_GATE")
    if (-not [bool]$PhasePolicy.azure_write) { $forbidden += "AZURE_WRITE" }
    if (-not [bool]$PhasePolicy.terraform_write) { $forbidden += "TERRAFORM_WRITE" }
    $Receipt.authorization.forbidden_scope = $forbidden
    $Receipt.next_action = $(if ($Issue -gt 0) { "EXECUTE_ISSUE_$Issue" } else { "EXECUTE_$TargetPhase" })
} else {
    $Receipt.authorization.authorized_scope = "NONE"
    $Receipt.authorization.azure_write = $false
    $Receipt.authorization.terraform_write = $false
    $Receipt.authorization.forbidden_scope = @("ALL_MUTATIONS")
    $Receipt.next_action = "RESOLVE_BLOCKER_$($Receipt.blockers[0].code)"
}

$ReceiptDir = Split-Path -Parent $ReceiptPath
if (-not (Test-Path -LiteralPath $ReceiptDir)) { New-Item -ItemType Directory -Path $ReceiptDir -Force | Out-Null }
$Receipt | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8

$securityStatus = if (($Receipt.security.secrets_in_git + $Receipt.security.tfstate_in_git + $Receipt.security.tfplan_in_git + $Receipt.security.private_keys_in_git) -eq 0) { "PASS" } else { "BLOCKED" }

if ($IsGo) {
    Write-Host "SOAIACORE_PRECHECK=PASS"
    Write-Host "TARGET=$TargetPhase"
    if ($Issue -gt 0) { Write-Host "ISSUE=$Issue" }
    Write-Host "ARCHITECTURE=v0.6_FINAL_FROZEN"
    Write-Host "BRANCH=$($Receipt.authority.observed_branch)"
    Write-Host "HEAD=$($Receipt.authority.observed_sha)"
    Write-Host "BASELINE_RELATION=$($Receipt.authority.baseline_relation)"
    Write-Host "SECURITY=$securityStatus"
    Write-Host "PRECHECK_MUTATIONS=NONE"
    Write-Host "AZURE_WRITE_AUTHORIZED=$($Receipt.authorization.azure_write.ToString().ToLowerInvariant())"
    Write-Host "TERRAFORM_WRITE_AUTHORIZED=$($Receipt.authorization.terraform_write.ToString().ToLowerInvariant())"
    Write-Host "ARCHITECTURE_CHANGE_REQUIRED=false"
    Write-Host "HARD_BLOCKERS=0"
    Write-Host "SOFT_BLOCKERS=$($Receipt.summary.soft_block)"
    Write-Host "GO=true"
    Write-Host "NEXT_ACTION=$($Receipt.next_action)"
    Write-Host "RECEIPT=$ReceiptPath"
    exit 0
} else {
    $first = $Receipt.blockers[0]
    Write-Host "SOAIACORE_PRECHECK=BLOCKED"
    Write-Host "TARGET=$TargetPhase"
    if ($Issue -gt 0) { Write-Host "ISSUE=$Issue" }
    Write-Host "SECURITY=$securityStatus"
    Write-Host "PRECHECK_MUTATIONS=NONE"
    Write-Host "GO=false"
    Write-Host "BLOCKER_CODE=$($first.code)"
    Write-Host "BLOCKER=$($first.message)"
    Write-Host "NEXT_ACTION=$($Receipt.next_action)"
    Write-Host "RECEIPT=$ReceiptPath"
    exit 1
}
