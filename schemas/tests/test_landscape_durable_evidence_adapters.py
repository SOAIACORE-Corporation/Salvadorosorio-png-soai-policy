from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from durable_evidence_adapters import adapt_source, adapt_sources  # noqa: E402
from recovery_manifest_builder import build_recovery_manifest  # noqa: E402


def test_failed_completed_ci_is_valid_evidence_not_success():
    evidence = adapt_source({
        "source_kind":"ci_run",
        "source_id":"ci:111",
        "requirement_id":"validation-receipt",
        "run_id":111,
        "status":"completed",
        "outcome":"failure",
        "retrieved":True,
    })
    assert evidence["validation_status"] == "CONFIRMED"
    assert evidence["source_outcome"] == "failure"


def test_in_progress_ci_is_partial_evidence():
    evidence = adapt_source({
        "source_kind":"ci_run",
        "source_id":"ci:112",
        "requirement_id":"validation-receipt",
        "run_id":112,
        "status":"in_progress",
        "retrieved":True,
    })
    assert evidence["validation_status"] == "PARTIAL"


def test_stale_source_is_computed_from_time_not_outcome():
    evidence = adapt_source({
        "source_kind":"ci_run",
        "source_id":"ci:freshness",
        "requirement_id":"source-freshness",
        "run_id":116,
        "status":"completed",
        "outcome":"success",
        "retrieved":True,
        "observed_at":"2026-09-25T00:00:00Z",
        "freshness_max_age_seconds":3600,
    }, as_of="2026-09-26T00:00:00Z")
    assert evidence["validation_status"] == "CONFIRMED"
    assert evidence["fresh"] is False


def test_decision_without_authority_is_partial():
    evidence = adapt_source({
        "source_kind":"decision",
        "source_id":"decision:r006",
        "requirement_id":"decision-authority",
        "decision_id":"R-006",
        "retrieved":True,
    })
    assert evidence["validation_status"] == "PARTIAL"


def test_source_cannot_self_assign_requirement_implicitly():
    try:
        adapt_source({
            "source_kind":"git_commit",
            "source_id":"git:abc",
            "sha":"abc",
            "retrieved":True,
        })
    except ValueError:
        pass
    else:
        raise AssertionError("source must not infer its own requirement binding")


def test_adapted_sources_feed_manifest_without_semantic_promotion():
    evidence = adapt_sources([
        {"source_kind":"git_commit","source_id":"git:abc","requirement_id":"primary-state","sha":"abc","retrieved":True},
        {"source_kind":"receipt","source_id":"receipt:causal","requirement_id":"causal-link","path":"receipt.md","retrieved":True},
        {"source_kind":"decision","source_id":"decision:r006","requirement_id":"decision-authority","decision_id":"R-006","authority":"SOA","retrieved":True},
        {"source_kind":"ci_run","source_id":"ci:fresh","requirement_id":"source-freshness","run_id":116,"status":"completed","outcome":"success","retrieved":True,"observed_at":"2026-09-26T00:00:00Z","freshness_max_age_seconds":86400},
        {"source_kind":"receipt","source_id":"receipt:validation","requirement_id":"validation-receipt","receipt_id":"VAL-1","retrieved":True},
    ], as_of="2026-09-26T01:00:00Z")
    manifest = build_recovery_manifest(evidence)
    assert all(item["status"] == "CONFIRMED" for item in manifest["requirements"])
