from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from memory_cycle import (  # noqa: E402
    assess_human_interaction_efficiency,
    assess_methodology_controls,
    run_memory_cycle,
)


def _manifest():
    return {
        "recovery_manifest_version": "0.1",
        "requirements": [
            {"requirement_id":"e1","dimension":"evidence_coverage","status":"CONFIRMED","required":True,"material_primary":True},
            {"requirement_id":"c1","dimension":"causal_continuity","status":"CONFIRMED","required":True},
            {"requirement_id":"a1","dimension":"authority_integrity","status":"CONFIRMED","required":True,"required_authority":True},
            {"requirement_id":"f1","dimension":"freshness","status":"CONFIRMED","required":True},
            {"requirement_id":"r1","dimension":"receipt_integrity","status":"CONFIRMED","required":True},
        ],
    }


def test_complete_cycle_is_eligible_and_reuses_context_integrity():
    result = run_memory_cycle(
        _manifest(),
        human_interactions=[{"action_id":"h1","required":True}],
        controls=[
            {"control_id":"c1","executed":True,"changed_outcome":True},
            {"control_id":"c2","executed":True,"changed_outcome":False},
        ],
    )
    assert result["methodology"] == "OBSERVE_UNDERSTAND_RESOLVE_DEMONSTRATE"
    assert result["understand"]["context_integrity_score_pct"] == 100
    assert result["resolve"]["canonicalization_status"] == "ELIGIBLE"
    assert result["resolve"]["automatic_source_mutation"] is False
    assert result["demonstrate"]["human_interaction"]["human_interaction_efficiency_pct"] == 100


def test_missing_authority_blocks_canonicalization_without_inventing_certainty():
    manifest = _manifest()
    manifest["requirements"][2]["status"] = "MISSING"
    result = run_memory_cycle(manifest)
    assert "MISSING_REQUIRED_AUTHORITY" in result["understand"]["critical_gates"]
    assert result["resolve"]["canonicalization_status"] == "BLOCKED"
    assert result["understand"]["context_integrity_score_pct"] <= 84


def test_recoverable_gap_is_partial_not_showstopper():
    manifest = _manifest()
    manifest["requirements"][1]["status"] = "PARTIAL"
    result = run_memory_cycle(manifest)
    assert result["understand"]["critical_gates"] == []
    assert result["resolve"]["canonicalization_status"] == "PARTIAL"
    assert result["resolve"]["actions"] == ["RECOVER_OR_ADJUDICATE:c1"]


def test_avoidable_human_actions_reduce_efficiency():
    result = assess_human_interaction_efficiency([
        {"action_id":"approval","required":True},
        {"action_id":"manual-discovery","required":False},
    ])
    assert result["human_interaction_efficiency_pct"] == 50
    assert result["avoidable_human_interaction_rate_pct"] == 50


def test_no_human_actions_is_not_penalized():
    result = assess_human_interaction_efficiency([])
    assert result["human_interaction_efficiency_pct"] == 100
    assert result["avoidable_human_interaction_rate_pct"] == 0


def test_control_yield_and_overhead_have_consistent_semantics():
    result = assess_methodology_controls([
        {"control_id":"inventory","executed":True,"changed_outcome":True},
        {"control_id":"authority","executed":True,"changed_outcome":True},
        {"control_id":"redundant","executed":True,"changed_outcome":False},
    ])
    assert result["control_yield_pct"] == 66.67
    assert result["methodological_overhead_pct"] == 33.33
    assert round(result["control_yield_pct"] + result["methodological_overhead_pct"], 2) == 100


def test_invalid_human_event_fails_closed():
    try:
        assess_human_interaction_efficiency([{"action_id":"x","required":"maybe"}])
    except ValueError:
        pass
    else:
        raise AssertionError("ambiguous human-action requirement must fail closed")


def test_recovery_efficiency_measures_autonomous_resolution():
    result = assess_recovery_efficiency([
        {"event_id":"path-miss","recoverable":True,"resolved":True,"human_intervention_required":False},
        {"event_id":"syntax-fix","recoverable":True,"resolved":True,"human_intervention_required":False},
        {"event_id":"approval","recoverable":False,"resolved":True,"human_intervention_required":True},
    ])
    assert result["recoverable_events"] == 2
    assert result["autonomously_resolved_events"] == 2
    assert result["recovery_efficiency_pct"] == 100


def test_unresolved_recoverable_event_reduces_recovery_efficiency():
    result = assess_recovery_efficiency([
        {"event_id":"a","recoverable":True,"resolved":True,"human_intervention_required":False},
        {"event_id":"b","recoverable":True,"resolved":False,"human_intervention_required":False},
    ])
    assert result["recovery_efficiency_pct"] == 50
    assert result["unresolved_recoverable_events"] == 1
