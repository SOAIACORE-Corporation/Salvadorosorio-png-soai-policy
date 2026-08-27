from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EVIDENCE_KEYS = {
    "secrets_credentials": (
        "managed_secret_store_bound",
        "credentials_rotated",
        "approved_idp_bound",
    ),
    "terraform_state_change_control": (
        "remote_backend_initialized",
        "plan_no_destroy_verified",
    ),
    "network_data_access": ("blob_private_path_verified",),
    "observability": ("alerts_verified", "budget_alert_verified"),
    "backup_restore_rollback": (
        "postgres_restore_verified",
        "evidence_backup_verified",
        "rollback_verified",
    ),
}


def _contains(path: Path, *needles: str) -> bool:
    content = path.read_text(encoding="utf-8")
    return all(needle in content for needle in needles)


def repository_checks(root: Path) -> dict[str, dict[str, bool]]:
    terraform = root / "infra" / "azure" / "p0"
    return {
        "secrets_credentials": {
            "secret_files_ignored": _contains(root / ".gitignore", ".env", "*.tfstate"),
            "browser_secret_boundary": _contains(
                root / "apps" / "web" / "src" / "server" / "auth.mjs",
                "SOAIACORE_OIDC_CLIENT_SECRET",
                "HttpOnly",
            ),
        },
        "terraform_state_change_control": {
            "remote_backend_declared": _contains(terraform / "versions.tf", 'backend "azurerm"'),
            "azure_ad_backend_example": _contains(
                terraform / "backend.production.hcl.example", "use_azuread_auth", "true"
            ),
            "local_state_ignored": _contains(terraform / ".gitignore", "*.tfstate", "*.tfvars"),
        },
        "network_data_access": {
            "postgres_private": _contains(
                terraform / "data.tf", "public_network_access_enabled = false"
            ),
            "blob_anonymous_disabled": _contains(
                terraform / "data.tf",
                "allow_nested_items_to_be_public = false",
                "container_access_type = \"private\"",
                "shared_access_key_enabled       = false",
            ),
            "core_internal_ingress": _contains(
                terraform / "compute.tf", "external_enabled = false"
            ),
        },
        "observability": {
            "log_analytics": _contains(terraform / "compute.tf", "azurerm_log_analytics_workspace"),
            "health_probes": _contains(
                terraform / "compute.tf", "liveness_probe", "readiness_probe"
            ),
            "correlation_ids": _contains(
                root / "apps" / "core" / "src" / "soaiacore_core" / "main.py",
                "X-Correlation-ID",
            ),
        },
        "backup_restore_rollback": {
            "postgres_backup": _contains(terraform / "data.tf", "backup_retention_days"),
            "blob_recovery": _contains(
                terraform / "data.tf",
                "versioning_enabled = true",
                "delete_retention_policy",
                "container_delete_retention_policy",
            ),
            "runbook": (root / "docs" / "production" / "CONTROLLED_PILOT_HARDENING_RUNBOOK_2026-08-26.md").is_file(),
        },
    }


def plan_has_destructive_change(plan: dict[str, Any]) -> bool:
    for change in plan.get("resource_changes", []):
        actions = change.get("change", {}).get("actions", [])
        if "delete" in actions:
            return True
    return False


def evaluate(root: Path, evidence: dict[str, bool], plan: dict[str, Any] | None = None) -> dict[str, Any]:
    checks = repository_checks(root)
    observed = dict(evidence)
    if plan is not None:
        observed["plan_no_destroy_verified"] = not plan_has_destructive_change(plan)
    families: dict[str, Any] = {}
    for family, required_evidence in EVIDENCE_KEYS.items():
        repo_pass = all(checks[family].values())
        missing = [key for key in required_evidence if not observed.get(key, False)]
        status = "BLOCKED" if not repo_pass else "PASS" if not missing else "CONDITIONAL"
        families[family] = {
            "status": status,
            "repository_checks": checks[family],
            "missing_live_evidence": missing,
        }
    overall = "PASS" if all(item["status"] == "PASS" for item in families.values()) else "BLOCKED"
    return {
        "issue": "#19",
        "status": overall,
        "families": families,
        "accepted_residual_risk": [
            "Single-region controlled pilot",
            "No database HA unless the production readiness assessment requires it",
            "Web remains limited to one replica until a shared encrypted session store exists",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the controlled-pilot production gate")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--plan-json", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    plan = json.loads(args.plan_json.read_text(encoding="utf-8")) if args.plan_json else None
    result = evaluate(root, evidence, plan)
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
