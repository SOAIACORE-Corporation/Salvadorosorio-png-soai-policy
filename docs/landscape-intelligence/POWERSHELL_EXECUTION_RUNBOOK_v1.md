# SOAiaCore PowerShell Execution Runbook v1

**Purpose:** Preserve the execution conventions validated during the 2026-09-26 Azure/GitHub OIDC bootstrap work and remove avoidable shell, path, quoting and version friction.

## Canonical operating rule

Commands are supplied and executed as plain text, one command at a time.

Do not append punctuation to a command copied from prose. In particular, a trailing period changes a PowerShell file name:

Incorrect:

```text
.\scripts\azure\Bootstrap-SOAIntelligenceGitHubOidc.ps1.
```

Correct:

```text
.\scripts\azure\Bootstrap-SOAIntelligenceGitHubOidc.ps1
```

## Supported PowerShell posture

The bootstrap and preflight avoid PowerShell 7-only syntax so they remain compatible with Windows PowerShell 5.1 and PowerShell 7+ where the underlying Azure CLI is available.

Avoid in bootstrap instructions unless explicitly required:
- `&&`
- ternary operators
- null-coalescing operators
- smart quotes
- copied bullets or markdown punctuation
- multi-command one-liners

## Diagnostic order

When execution fails, classify the failure before changing syntax:

1. PATH / current directory
2. SCRIPT EXISTS
3. SHELL / VERSION
4. ENCODING / LINE ENDINGS
5. AZ CLI AVAILABILITY
6. AUTHENTICATION
7. RBAC / DATA-PLANE ACCESS
8. SCRIPT LOGIC

Do not jump directly to modifying the script.

## Canonical preflight

From the repository root:

```text
.\scripts\azure\Invoke-SOAIntelligenceBootstrapPreflight.ps1
```

The preflight:
- reports PowerShell edition/version;
- resolves the repository and target script paths;
- verifies the bootstrap script exists;
- verifies Azure CLI is available;
- verifies an authenticated Azure CLI context without printing subscription identifiers;
- invokes the bootstrap with **no mutation parameters**;
- therefore runs the target in `PLAN_ONLY` mode.

For diagnostics only, without invoking the bootstrap:

```text
.\scripts\azure\Invoke-SOAIntelligenceBootstrapPreflight.ps1 -CheckOnly
```

## Expected safe boundary

A successful preflight must preserve:

```text
PREFLIGHT_MODE=READ_ONLY
MUTATION_PARAMETERS_PRESENT=false
AZURE_MUTATION=false
BOOTSTRAP_PLAN_EXECUTED=true
PREFLIGHT_RESULT=PASS
```

The underlying bootstrap should also report:

```text
MODE=PLAN_ONLY
IAM_AUTHORIZED=NO
AZURE_MUTATION=false
```

## Material execution boundary

The following command is **not part of preflight** and must remain a separate, explicit authority step:

```text
.\scripts\azure\Bootstrap-SOAIntelligenceGitHubOidc.ps1 -Apply -AuthorizeIam
```

It may reconcile the managed identity, OIDC federation and narrowly scoped read-only RBAC. Its execution must be evidenced and receipted separately.

## Context-integrity requirement

Every command sequence that matters operationally should preserve:
- exact command text,
- shell edition/version,
- working directory or resolved repository root,
- exit outcome,
- non-secret control outputs,
- associated receipt or CI evidence.

The goal is reproducibility: a future operator should not need the original chat to understand how the command was executed.
