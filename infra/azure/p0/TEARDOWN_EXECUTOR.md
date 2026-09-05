# Governed P0 teardown executor

`Invoke-P0GovernedTeardown.ps1` implements the cleanup control tracked by #47 without authorizing teardown by itself.

## Safety model

- Default mode is `PlanOnly`.
- Scope is pinned to subscription `108eb4dd-25b3-4a7f-8d5e-4ec4389c3f0d` and pilot resource group `rg-soaiacore-p0-34utxi`.
- The state backend resource group `rg-soaiacore-tfstate-34utxi` is verified separately and is never the teardown target.
- Execution requires a sanitized #38 authority receipt proving `remote_backend_initialized=true/PASS`, `plan_no_destroy_verified=true/PASS`, and `config_state_reconciled=true/PASS`.
- `PlanOnly` creates a saved Terraform destroy plan, raw plan JSON, SHA-256 and a sanitized action/inventory receipt outside the Git working tree.
- Artifact storage is restricted to a path inside the current operator's home directory and outside the complete Git worktree.
- Symlink, junction and filesystem reparse-point components are rejected fail-closed before artifact creation; raw Terraform artifacts cannot be redirected into the repository through an alternate pathname.
- The artifact root itself is restricted to the current operator before child allocation, so the namespace parent of a staged plan is not left writable by another principal.
- Every artifact operation receives a collision-resistant GUID-suffixed child directory. Child creation is exclusive and fails closed rather than silently reusing an existing directory.
- Windows uses explicit inheritance-protected current-user-only ACLs; non-Windows hosts require `chmod 700` on artifact directories and `chmod 600` on plan/JSON/receipt files.
- The generated destroy plan is re-inspected before PLAN_ONLY completion. The plan must expose the pinned `subscription_id`; every AzureRM delete must have a prior ARM ID inside the exact P0 resource-group prefix. Any delete in the state-backend resource group or outside the pinned P0 scope fails closed.
- There is no direct `terraform destroy` path.
- `ApplyReviewedPlan` requires the exact saved plan, its reviewed SHA-256, the literal adjudication token `APPLY_REVIEWED_P0_DESTROY_PLAN`, the named adjudication authority `Salvador Osorio Ayala`, and an external authorization evidence reference.
- TOCTOU protection is mandatory on `ApplyReviewedPlan`: the caller-supplied plan is copied exactly once into a newly created exclusive owner-only artifact directory whose artifact-root parent is also operator-only; the original plan path is not reopened after staging.
- SHA-256 verification, `terraform show -json` scope inspection, immediate pre-apply re-hash, and any eventual exact-plan apply operate only on that protected staged copy.
- Any mismatch between the reviewed SHA, staged SHA, or immediate pre-apply SHA fails closed before `terraform apply`.
- Final verification requires the pilot resource group to be absent; the state backend remains preserved.
- GHCR credential revocation remains a separate required final-cutover receipt and is never automated by this script.

## Current authorization

#47 authorizes implementation and static validation only. #46 is CLOSED with `CONTROLLED_EXTENSION` authorized through `2026-09-20T05:59:59Z` and cumulative P0 cost ceiling `USD 10.00`; no teardown or destructive apply is authorized by the current lifecycle envelope.

Do not run `ApplyReviewedPlan` unless a future explicit teardown disposition is made, a specific generated destroy plan is reviewed, and that exact plan SHA is separately adjudicated by Salvador Osorio Ayala.

`PlanOnly` is also gated by current backend/config-state authority. If the supplied #38 closure receipt does not prove all three required authority flags, the executor stops before generating a destroy plan.

## Plan-only invocation pattern

Use operator-restricted, untracked files. `-ArtifactRoot`, when supplied, must resolve inside the current operator home, outside the Git worktree, and contain no symlink/junction/reparse-point component.

```powershell
.\Invoke-P0GovernedTeardown.ps1 `
  -Mode PlanOnly `
  -BackendConfigPath <protected-backend-hcl> `
  -VarFilePath <protected-pilot-tfvars> `
  -BackendAuthorityReceiptPath <sanitized-38-closure-receipt> `
  -ArtifactRoot <operator-home/evidence-directory>
```

If `-ArtifactRoot` is omitted, the script uses `SOAIACORE/p0-teardown-evidence` under the current operator's home directory, protects that artifact root, and allocates a unique operator-only child directory.

The script prints only counts, paths, hashes, scope-verification status and gate status. It does not print Terraform state contents or secret values.

## Apply-reviewed-plan invocation pattern

This mode is intentionally not authorized by #47 or the current #46 `CONTROLLED_EXTENSION`. If a future teardown disposition is formally made and a specific saved destroy plan is reviewed and adjudicated, the apply mode requires the exact named authority and evidence reference:

```powershell
.\Invoke-P0GovernedTeardown.ps1 `
  -Mode ApplyReviewedPlan `
  -BackendConfigPath <protected-backend-hcl> `
  -VarFilePath <protected-pilot-tfvars> `
  -BackendAuthorityReceiptPath <sanitized-38-closure-receipt> `
  -PlanFile <exact-saved-plan> `
  -ExpectedPlanSha256 <reviewed-sha256> `
  -AdjudicationToken APPLY_REVIEWED_P0_DESTROY_PLAN `
  -AdjudicationAuthority 'Salvador Osorio Ayala' `
  -AuthorizationEvidenceRef <formal-email-or-receipt-reference>
```

The supplied `-PlanFile` is only a staging source. After it is copied into the unique protected review directory, the source path is discarded and is never used for validation or apply.
