from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from correlate import correlate  # noqa: E402
from normalize import normalize  # noqa: E402


def test_unknown_cost_creates_visibility_gap_and_unknown_financial_impact():
    cost = normalize(
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
    result = correlate([cost])
    assert len(result["findings"]) == 1
    assert result["findings"][0]["payload"]["adjudication"] == "VISIBILITY_GAP"
    assert result["impacts"][0]["payload"]["domain"] == "financial"
    assert result["impacts"][0]["payload"]["score"] == "UNKNOWN"


def test_stale_source_creates_visibility_gap_not_fix():
    obs = normalize(
        "monitoring",
        {
            "observation_id": "obs:stale",
            "asset_id": "asset:test",
            "metric": "health",
            "state": "Observed",
            "freshness": "stale",
            "observed_at": "2026-09-25T22:29:14Z",
        },
    )
    result = correlate([obs])
    assert result["findings"][0]["payload"]["adjudication"] == "VISIBILITY_GAP"
    assert result["findings"][0]["payload"]["status"] == "VISIBILITY_GAP"


def test_unhealthy_monitoring_creates_pending_risk():
    obs = normalize(
        "monitoring",
        {
            "observation_id": "obs:health",
            "asset_id": "asset:test",
            "metric": "health",
            "state": "Unhealthy",
            "observed_at": "2026-09-25T22:29:14Z",
        },
    )
    result = correlate([obs])
    finding = result["findings"][0]
    assert finding["payload"]["type"] == "risk"
    assert finding["payload"]["adjudication"] == "PENDING"
    assert finding["payload"]["severity"] == "WARNING"
    assert result["impacts"][0]["payload"]["domain"] == "availability"
    assert result["impacts"][0]["payload"]["score"] == "UNKNOWN"


def test_critical_monitoring_can_be_critical_without_auto_fix():
    obs = normalize(
        "monitoring",
        {
            "observation_id": "obs:critical",
            "asset_id": "asset:test",
            "metric": "health",
            "state": "Critical",
            "observed_at": "2026-09-25T22:29:14Z",
        },
    )
    result = correlate([obs])
    finding = result["findings"][0]
    assert finding["payload"]["severity"] == "CRITICAL"
    assert finding["payload"]["adjudication"] == "PENDING"


def test_aligned_p0_bundle_remains_without_findings():
    import json
    from collect import collect_manifest

    manifest_path = ROOT / "schemas" / "examples" / "landscape" / "p0-baseline-manifest-v0.1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle = collect_manifest(manifest, base_dir=manifest_path.parent)
    result = correlate(bundle["records"])
    assert result["findings"] == []
    assert result["impacts"] == []
