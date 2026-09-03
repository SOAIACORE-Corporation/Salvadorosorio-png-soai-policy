# Governed P0 teardown executor

`Invoke-P0GovernedTeardown.ps1` implements the cleanup control tracked by #47 without authorizing teardown by itself.

## Safety model

- Default mode is `PlanOnly`.
- Scope is pinned to subscription `108eb4dd-25b3-4a7f-8d5e-4ec4389c3f0d` and pilot resource group `rg-soaiacore-p0-34utxi`.
- The state backend resource group `rg-soaiacore-tfstate-34utxi` is verified separately and is never the teardown target.
- Execution requires a sanitized #38 authority receipt proving `remote_backend_initialized=true`, `plan_no_destroy_verified=true`, and `config_state_reconciled=true`.
- `PlanOnly` creates a saved Terraform destroy plan, raw plan JSON, SHA-256 and a sanitized action/inventory receipt outside the Git working tree. Raw plan/plan JSON remain operator-restricted because Terraform plan material may contain sensitive values.
- There is no direct `terraform destroy` path.
- `ApplyReviewedPlan` requires the exact saved plan, its reviewed SHA-256 and the literal human-adjudication token `APPLY_REVIEWED_P0_DESTROY_PLAN`.
- The apply path re-inspects the saved plan and rejects create/update actions before applying that exact file.
- Final verification requires the pilot resource group to be absent; the state backend remains preserved.
- GHCR credential revocation remains a separate required final-cutover receipt and is never automated by this script.

## Current authorization

#47 authorizes implementation and static validation only. Do not run `ApplyReviewedPlan` until a specific teardown decision has been made under #46 and the exact generated plan has been reviewed and explicitly adjudicated.

## Plan-only invocation pattern

Use operator-restricted, untracked files. Do not paste tokens or secret values into the command line.

```powershell
.\Invoke-P0GovernedTeardown.ps1 `
  -Mode PlanOnly `
  -BackendConfigPath <protected-backend-hcl> `
  -VarFilePath <protected-pilot-tfvars> `
  -BackendAuthorityReceiptPath <sanitized-38-closure-receipt>
```

The script prints only counts, paths, hashes and gate status. It does not print Terraform state contents or secret values.
