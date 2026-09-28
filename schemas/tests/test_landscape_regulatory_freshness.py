from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from freshness import assess_freshness, assess_regulatory_source  # noqa: E402
from regulatory import regulatory_source_record  # noqa: E402


REG_DIR = ROOT / "schemas" / "examples" / "regulatory"


def _source():
    raw = json.loads((REG_DIR / "source-us-21cfr211-v0.1.json").read_text(encoding="utf-8"))
    return regulatory_source_record(raw)


def test_current_when_within_due_window():
    result = assess_freshness(
        verified_at="2026-09-26T04:00:00Z",
        now="2026-09-26T05:00:00Z",
        due_after_hours=24,
        stale_after_hours=72,
    )
    assert result["state"] == "CURRENT"
    assert result["canonical_freshness"] == "current"
    assert result["material_execution_allowed"] is True


def test_due_for_reverify_is_visible_without_becoming_stale():
    result = assess_freshness(
        verified_at="2026-09-25T00:00:00Z",
        now="2026-09-26T06:00:00Z",
        due_after_hours=24,
        stale_after_hours=72,
    )
    assert result["state"] == "DUE_FOR_REVERIFY"
    assert result["canonical_freshness"] == "current"
    assert result["material_execution_allowed"] is True


def test_stale_blocks_material_execution_but_not_analysis():
    result = assess_freshness(
        verified_at="2026-09-20T00:00:00Z",
        now="2026-09-26T06:00:00Z",
        due_after_hours=24,
        stale_after_hours=72,
    )
    assert result["state"] == "STALE"
    assert result["canonical_freshness"] == "stale"
    assert result["analysis_allowed"] is True
    assert result["material_execution_allowed"] is False


def test_missing_timestamp_is_unknown_not_current():
    result = assess_freshness(
        verified_at=None,
        now="2026-09-26T06:00:00Z",
        due_after_hours=24,
        stale_after_hours=72,
    )
    assert result["state"] == "UNKNOWN"
    assert result["canonical_freshness"] == "unknown"
    assert result["material_execution_allowed"] is False


def test_future_verification_timestamp_is_unknown():
    result = assess_freshness(
        verified_at="2026-09-27T06:00:00Z",
        now="2026-09-26T06:00:00Z",
        due_after_hours=24,
        stale_after_hours=72,
    )
    assert result["state"] == "UNKNOWN"
    assert result["material_execution_allowed"] is False


def test_regulatory_source_assessment_preserves_source_identity_and_policy():
    result = assess_regulatory_source(
        _source(),
        now="2026-09-26T05:00:00Z",
        due_after_hours=24,
        stale_after_hours=72,
    )
    assert result["regulatory_source_id"] == "regsrc:us:21cfr:part211"
    assert result["policy"]["due_after_hours"] == 24
    assert result["policy"]["stale_after_hours"] == 72


def test_http_presence_is_not_part_of_freshness_semantics():
    result = assess_freshness(
        verified_at="2026-09-20T00:00:00Z",
        now="2026-09-26T06:00:00Z",
        due_after_hours=24,
        stale_after_hours=72,
    )
    assert "http" not in result
    assert result["state"] == "STALE"


def test_invalid_policy_windows_fail_closed():
    try:
        assess_freshness(
            verified_at="2026-09-26T04:00:00Z",
            now="2026-09-26T05:00:00Z",
            due_after_hours=72,
            stale_after_hours=24,
        )
    except ValueError as exc:
        assert "stale_after_hours" in str(exc)
    else:
        raise AssertionError("invalid freshness policy must fail")
