from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from normalize import normalize  # noqa: E402
from reconcile import reconcile_triple  # noqa: E402


ASSET = "azure:sub:psql"


def _azure(public_access="Disabled", sku="Standard_B1ms"):
    return normalize(
        "azure-config",
        {
            "observation_id": "obs:azure:psql",
            "asset_id": ASSET,
            "resource_type": "postgresql_flexible_server",
            "native_id": "psql",
            "public_network_access": public_access,
            "sku": sku,
            "observed_at": "2026-09-26T05:00:00Z",
        },
    )


def _tf(public_access="Disabled", sku="Standard_B1ms"):
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
                "sku": sku,
            },
            "observed_at": "2026-09-26T05:00:00Z",
        },
    )


def _git(public_access="Disabled", sku="Standard_B1ms"):
    return normalize(
        "github-iac",
        {
            "observation_id": "obs:git:psql",
            "asset_id": ASSET,
            "repo": "SOAIACORE-Corporation/Salvadorosorio-png-soai-policy",
            "commit": "fixture",
            "path": "infra/azure/p0",
            "intent": {
                "resource_type": "postgresql_flexible_server",
                "native_id": "psql",
                "public_network_access": public_access,
                "sku": sku,
            },
            "observed_at": "2026-09-26T05:00:00Z",
        },
    )


def _drift(records):
    return [f for f in reconcile_triple(records) if f["payload"]["type"] == "drift"]


def _gaps(records):
    return [f for f in reconcile_triple(records) if f["payload"]["type"] == "visibility_gap"]


def test_azure_config_normalizes_as_authoritative_config_observation():
    record = _azure()
    assert record["record_type"] == "observation"
    assert record["source"]["system"] == "azure"
    assert record["payload"]["fact_type"] == "config"
    assert record["payload"]["value"]["public_network_access"] == "Disabled"


def test_all_three_aligned_produces_no_finding():
    assert reconcile_triple([_azure(), _tf(), _git()]) == []


def test_physical_drift_when_terraform_and_github_agree_against_azure():
    findings = _drift([_azure("Enabled"), _tf("Disabled"), _git("Disabled")])
    assert len(findings) == 1
    assert findings[0]["payload"]["classification"] == "PHYSICAL_DRIFT"
    assert findings[0]["payload"]["adjudication"] == "PENDING"


def test_declarative_drift_when_azure_and_terraform_agree_against_github():
    findings = _drift([_azure("Disabled"), _tf("Disabled"), _git("Enabled")])
    assert len(findings) == 1
    assert findings[0]["payload"]["classification"] == "DECLARATIVE_DRIFT"


def test_managed_drift_when_azure_and_github_agree_against_terraform():
    findings = _drift([_azure("Disabled"), _tf("Enabled"), _git("Disabled")])
    assert len(findings) == 1
    assert findings[0]["payload"]["classification"] == "MANAGED_DRIFT"


def test_mixed_conflict_patterns_collapse_to_multi_source_divergence():
    findings = _drift([
        _azure(public_access="Enabled", sku="A"),
        _tf(public_access="Disabled", sku="B"),
        _git(public_access="Disabled", sku="A"),
    ])
    assert len(findings) == 1
    assert findings[0]["payload"]["classification"] == "MULTI_SOURCE_DIVERGENCE"


def test_missing_required_source_is_visibility_gap_not_healthy():
    gaps = _gaps([_tf(), _git()])
    assert len(gaps) == 1
    assert gaps[0]["payload"]["classification"] == "SOURCE_VISIBILITY_GAP"
    assert gaps[0]["payload"]["status"] == "VISIBILITY_GAP"


def test_one_source_only_does_not_invent_drift_or_visibility_case():
    assert reconcile_triple([_tf()]) == []


def test_missing_terraform_state_yields_visibility_gap_not_drift():
    records = [
        {
            "schema_version": "0.1",
            "record_id": "obs:azure:db",
            "record_type": "observation",
            "source": {
                "source_id": "azure-live",
                "system": "azure",
                "source_type": "api",
                "location": "arm",
                "collected_at": "2026-09-26T08:22:20Z",
                "hash": None,
                "freshness": "current",
                "trust_level": "authoritative",
            },
            "observed_at": "2026-09-26T08:22:20Z",
            "payload": {
                "observation_id": "obs:azure:db",
                "asset_id": "asset:postgresql:p0",
                "fact_type": "config",
                "value": {"sku": "B_Standard_B1ms", "public_network_access": False},
            },
        },
        {
            "schema_version": "0.1",
            "record_id": "obs:github:db",
            "record_type": "observation",
            "source": {
                "source_id": "github-iac",
                "system": "github",
                "source_type": "repository",
                "location": "infra/azure/p0/data.tf",
                "collected_at": "2026-09-26T08:22:20Z",
                "hash": None,
                "freshness": "current",
                "trust_level": "authoritative",
            },
            "observed_at": "2026-09-26T08:22:20Z",
            "payload": {
                "observation_id": "obs:github:db",
                "asset_id": "asset:postgresql:p0",
                "fact_type": "config",
                "value": {"intent": {"sku": "B_Standard_B1ms", "public_network_access": False}},
            },
        },
    ]

    findings = reconcile_triple(records)
    assert len(findings) == 1
    finding = findings[0]["payload"]
    assert finding["classification"] == "SOURCE_VISIBILITY_GAP"
    assert finding["adjudication"] == "VISIBILITY_GAP"
    assert finding["type"] == "visibility_gap"
    assert finding["severity"] == "UNKNOWN"
