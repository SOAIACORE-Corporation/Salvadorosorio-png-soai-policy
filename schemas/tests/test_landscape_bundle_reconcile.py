from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from bundle import bundle_records  # noqa: E402
from normalize import normalize  # noqa: E402
from reconcile import reconcile  # noqa: E402


ASSET = "azure:sub:psql"


def _tf(public_access="Disabled"):
    return normalize(
        "terraform-state",
        {
            "observation_id": "obs:tf:psql",
            "asset_id": ASSET,
            "address": "azurerm_postgresql_flexible_server.pilot",
            "resource_type": "postgresql_flexible_server",
            "native_id": "psql",
            "attributes": {
                "public_network_access": public_access,
                "sku": "Standard_B1ms",
            },
            "observed_at": "2026-09-25T22:29:14Z",
        },
    )


def _git(public_access="Disabled"):
    return normalize(
        "github-iac",
        {
            "observation_id": "obs:git:psql",
            "asset_id": ASSET,
            "repo": "SOAIACORE-Corporation/Salvadorosorio-png-soai-policy",
            "commit": "fc60164b",
            "path": "infra/azure/p0/main.tf",
            "intent": {
                "resource_type": "postgresql_flexible_server",
                "native_id": "psql",
                "public_network_access": public_access,
                "sku": "Standard_B1ms",
            },
            "observed_at": "2026-09-25T22:29:14Z",
        },
    )


def test_bundle_is_deterministic_independent_of_input_order():
    first = bundle_records([_tf(), _git()])
    second = bundle_records([_git(), _tf()])
    assert first["sha256"] == second["sha256"]
    assert first["record_count"] == 2


def test_matching_terraform_and_github_intent_produces_no_finding():
    assert reconcile([_tf(), _git()]) == []


def test_conflict_produces_pending_not_fix():
    findings = reconcile([_tf("Disabled"), _git("Enabled")])
    assert len(findings) == 1
    finding = findings[0]
    assert finding["payload"]["adjudication"] == "PENDING"
    assert finding["payload"]["status"] == "OPEN"
    assert finding["payload"]["severity"] == "UNKNOWN"
    assert finding["source"]["trust_level"] == "derived"


def test_conflict_finding_keeps_both_evidence_refs():
    finding = reconcile([_tf("Disabled"), _git("Enabled")])[0]
    assert finding["payload"]["evidence_refs"] == ["obs:tf:psql", "obs:git:psql"]


def test_one_source_only_does_not_invent_a_contradiction():
    assert reconcile([_tf("Disabled")]) == []
