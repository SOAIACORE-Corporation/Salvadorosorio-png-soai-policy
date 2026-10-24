from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from memory_cycle import run_memory_cycle_from_evidence  # noqa: E402
from mocatriz_execution import (  # noqa: E402
    assess_stop_decision,
    assess_strategy_adaptation,
    detect_false_completion,
    determine_final_status,
)


def _evidence(authority_available: bool):
    authority_status = "CONFIRMED" if authority_available else "UNKNOWN"
    return [
        {"evidence_id":"commit:state","requirement_id":"primary-state","available":True,"validation_status":"CONFIRMED","source_ref":"git:compound"},
        {"evidence_id":"receipt:causal","requirement_id":"causal-link","available":True,"validation_status":"CONFIRMED","source_ref":"receipt:compound"},
        {"evidence_id":"receipt:authority","requirement_id":"decision-authority","available":authority_available,"validation_status":authority_status,"source_ref":"authority:compound"},
        {"evidence_id":"ci:fresh","requirement_id":"source-freshness","available":True,"validation_status":"CONFIRMED","fresh":True,"source_ref":"ci:compound"},
        {"evidence_id":"receipt:validation","requirement_id":"validation-receipt","available":True,"validation_status":"CONFIRMED","source_ref":"receipt:validation"},
    ]


def test_compound_failure_preserves_objective_and_avoids_false_escalation_or_completion():
    # Authority is temporarily unavailable: memory must fail closed rather than invent certainty.
    blocked = run_memory_cycle_from_evidence(
        _evidence(False),
        human_interactions=[],
        recovery_events=[
            {"event_id":"route-a","recoverable":True,"resolved":False,"human_intervention_required":False},
        ],
        controls=[
            {"control_id":"authority-check","executed":True,"changed_outcome":True},
            {"control_id":"recovery-route-check","executed":True,"changed_outcome":True},
        ],
    )
    assert blocked["resolve"]["canonicalization_status"] == "BLOCKED"
    assert blocked["demonstrate"]["human_interaction"]["status"] == "NOT_EXERCISED"
    assert blocked["demonstrate"]["human_interaction"]["human_interaction_efficiency_pct"] is None

    # Route A failed, but route B is autonomous and viable even though a human is available.
    stop = assess_stop_decision([
        {"type":"recovery_attempt","result":"FAILED","evidence":["EV-A-FAILED"]},
        {"type":"alternative","alternative_id":"B","status":"VIABLE_UNTRIED","requires_human":False,"evidence":["EV-B-VIABLE"]},
        {"type":"human_dependency","required":True,"available":True,"evidence":["EV-HUMAN-AVAILABLE"]},
    ])
    assert stop["recommended_status"] == "CONTINUE"
    assert stop["reason"] == "AUTONOMOUS_ALTERNATIVE_REMAINS"

    adaptation = assess_strategy_adaptation([
        {"type":"strategy_attempt","objective_id":"OBJ-COMPOUND","strategy_id":"A","result":"FAILED","evidence":["EV-A-FAILED"]},
        {"type":"strategy_change","objective_id":"OBJ-COMPOUND","from_strategy":"A","to_strategy":"B","basis_evidence":["EV-A-FAILED"]},
    ])
    assert adaptation["adaptive_mutation_count"] == 1
    assert adaptation["drift_count"] == 0

    criteria = [{"criterion_id":"AUTHORITY-RECOVERED","applicable":True,"satisfied":False,"material":True}]
    false_close = detect_false_completion("COMPLETED", criteria)
    assert false_close["false_completion"] is True
    assert determine_final_status(criteria)["final_status"] == "PENDING"

    # Authority becomes observable; the same objective may now close on evidence.
    recovered = run_memory_cycle_from_evidence(
        _evidence(True),
        human_interactions=[],
        recovery_events=[
            {"event_id":"route-b","recoverable":True,"resolved":True,"human_intervention_required":False},
        ],
        controls=[
            {"control_id":"authority-check","executed":True,"changed_outcome":True},
            {"control_id":"recovery-route-check","executed":True,"changed_outcome":True},
        ],
    )
    assert recovered["resolve"]["canonicalization_status"] == "ELIGIBLE"
    assert recovered["understand"]["context_integrity_score_pct"] == 100

    completed = determine_final_status([
        {"criterion_id":"AUTHORITY-RECOVERED","applicable":True,"satisfied":True,"material":True}
    ])
    assert completed["final_status"] == "COMPLETED"
