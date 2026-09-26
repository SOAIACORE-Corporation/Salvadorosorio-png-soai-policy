from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from normalize import normalize  # noqa: E402


def test_normalize_azure_resource_preserves_physical_authority():
    record = normalize(
        "azure-resource",
        {
            "subscription_id": "108eb4dd-25b3-4a7f-8d5e-4ec4389c3f0d",
            "resource_id": "psql-soaiacore-p0-34utxi",
            "name": "psql-soaiacore-p0-34utxi",
            "resource_type": "postgresql_flexible_server",
            "environment": "p0",
            "owner": "SOAiaCore",
            "observed_at": "2026-09-25T22:29:14Z",
            "source_id": "azure-physical-evidence-v3",
            "source_location": "COMITE/azure_physical_telemetry_v3.json",
        },
    )
    assert record["record_type"] == "asset"
    assert record["source"]["system"] == "azure"
    assert record["source"]["trust_level"] == "authoritative"
    assert record["payload"]["environment"] == "p0"


def test_normalize_unknown_cost_never_fabricates_zero():
    record = normalize(
        "cost",
        {
            "cost_id": "cost:unknown:test",
            "scope_id": "asset:test",
            "period": "2026-09",
            "amount": None,
            "currency": "USD",
            "observed_at": "2026-09-25T22:29:14Z",
        },
    )
    assert record["payload"]["amount"] is None
    assert record["payload"]["currency"] is None
    assert record["payload"]["cost_type"] == "unknown"
    assert record["payload"]["confidence"] == 0.0


def test_normalize_observed_cost_keeps_period_and_currency():
    record = normalize(
        "cost",
        {
            "cost_id": "cost:soaiacore:2026-09-01_2026-09-25",
            "scope_id": "SOAiaCore",
            "period": "2026-09-01/2026-09-25",
            "amount": 78.8227235885305,
            "currency": "USD",
            "cost_type": "observed",
            "observed_at": "2026-09-25T22:29:14Z",
        },
    )
    assert record["payload"]["amount"] == 78.8227235885305
    assert record["payload"]["currency"] == "USD"
    assert record["payload"]["period"] == "2026-09-01/2026-09-25"


def test_normalize_terraform_plan_does_not_auto_fix_drift():
    record = normalize(
        "terraform-plan-summary",
        {
            "finding_id": "R-006",
            "add": 11,
            "change": 6,
            "destroy": 1,
            "adjudication": "HOLD",
            "status": "HOLD",
            "severity": "WARNING",
            "observed_at": "2026-09-25T22:29:14Z",
        },
    )
    assert record["payload"]["adjudication"] == "HOLD"
    assert record["payload"]["status"] == "HOLD"
    assert record["payload"]["evidence_refs"] == ["terraform-plan:11-add-6-change-1-destroy"]


def test_normalizer_rejects_unsupported_source_kind():
    try:
        normalize("execute-cloud-change", {"observed_at": "2026-09-25T22:29:14Z"})
    except ValueError as exc:
        assert "unsupported kind" in str(exc)
    else:
        raise AssertionError("normalizer must reject execution-oriented kinds")
