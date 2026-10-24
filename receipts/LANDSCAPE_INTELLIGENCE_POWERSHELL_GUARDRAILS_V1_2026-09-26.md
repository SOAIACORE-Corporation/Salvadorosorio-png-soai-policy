# Landscape Intelligence · PowerShell Execution Guardrails v1 Receipt

**Date:** 2026-09-26  
**Branch:** `feat/landscape-intelligence-data-model-v1`  
**PR:** #84  
**Status:** VALIDATED / READ-ONLY PREFLIGHT / CROSS-VERSION SHELL GUARDRAILS

## Capability

Adds a canonical PowerShell entrypoint for the Azure/GitHub OIDC bootstrap workflow:

`scripts/azure/Invoke-SOAIntelligenceBootstrapPreflight.ps1`

The preflight:
- reports PowerShell edition and version;
- resolves repository and bootstrap script paths;
- validates the bootstrap script exists;
- verifies Azure CLI availability;
- verifies Azure CLI authentication without printing account identifiers;
- invokes the existing bootstrap with no mutation parameters;
- preserves PLAN_ONLY semantics by default;
- supports `-CheckOnly` for diagnostics without invoking the bootstrap.

## Shell/runbook controls

Canonical execution guidance now preserves:
- plain-text commands;
- one command per instruction;
- no punctuation appended to copied commands;
- no smart quotes;
- path validation before execution;
- shell/version classification before syntax changes;
- explicit separation between preflight and material `-Apply -AuthorizeIam` execution;
- compatibility posture for Windows PowerShell 5.1 and PowerShell 7+.

## Validation

GitHub Actions workflow: Landscape Intelligence Schema  
Run: #97  
Run ID: 36224912680  
Result: **120 passed in 6.13s**  
Conclusion: SUCCESS

## Safety boundary

No Azure mutation.
No Terraform apply.
No RBAC mutation.
No PostgreSQL write.
No production deployment.
No autonomous remediation.
No merge.

## Operational command

From repository root:

```text
.\scripts\azure\Invoke-SOAIntelligenceBootstrapPreflight.ps1
```

Diagnostic-only mode:

```text
.\scripts\azure\Invoke-SOAIntelligenceBootstrapPreflight.ps1 -CheckOnly
```

Material execution remains a separate authority step.
