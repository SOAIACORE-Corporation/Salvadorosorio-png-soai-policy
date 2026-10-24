from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from mocatriz_execution import (  # noqa: E402
    assess_stop_decision,
    assess_strategy_adaptation,
    correlate_human_response,
    create_human_task,
    detect_false_completion,
    determine_final_status,
    methodology_telemetry,
)


def test_human_task_is_correlated_and_resumes_through_understand():
    task = create_human_task(
        objective_id="OBJ-001",
        execution_id="EXE-071",
        human_task_id="HT-014",
        correlation_id="CORR-8F3A",
        reason="Need distinguishing evidence",
        question="Which alternative is authoritative?",
        evidence=["EV-018", "EV-021"],
        resume_from="RESOLVE-047",
    )
    result = correlate_human_response(task, {
        "objective_id":"OBJ-001",
        "execution_id":"EXE-071",
        "human_task_id":"HT-014",
        "correlation_id":"CORR-8F3A",
        "answer":"A",
    })
    assert task["status"] == "WAITING_HUMAN"
    assert result["correlation_status"] == "MATCHED"
    assert result["recommended_phase"] == "UNDERSTAND"


def test_wrong_human_response_cannot_resume_wrong_execution():
    task = create_human_task(
        objective_id="OBJ-001",
        execution_id="EXE-071",
        human_task_id="HT-014",
        correlation_id="CORR-8F3A",
        reason="Need decision",
        question="A or B?",
        evidence=[],
        resume_from="RESOLVE-047",
    )
    try:
        correlate_human_response(task, {
            "objective_id":"OBJ-001",
            "execution_id":"EXE-072",
            "human_task_id":"HT-014",
            "correlation_id":"CORR-8F3A",
            "answer":"A",
        })
    except ValueError:
        pass
    else:
        raise AssertionError("cross-execution human response must fail closed")


def test_false_completion_detects_material_unresolved_work():
    criteria = [
        {"criterion_id":"C1","applicable":True,"satisfied":True,"material":True},
        {"criterion_id":"C2","applicable":True,"satisfied":False,"material":True},
    ]
    result = detect_false_completion("COMPLETED", criteria)
    assert result["false_completion"] is True
    assert result["objective_completion_pct"] == 50


def test_final_status_is_not_completed_with_material_gap():
    criteria = [
        {"criterion_id":"C1","satisfied":True,"material":True},
        {"criterion_id":"C2","satisfied":False,"material":True},
    ]
    result = determine_final_status(criteria)
    assert result["final_status"] == "PENDING"


def test_zero_applicable_criteria_cannot_complete_objective():
    result = determine_final_status([])
    assert result["completion_applicable"] is False
    assert result["objective_completion_pct"] is None
    assert result["final_status"] == "PENDING"


def test_claimed_completion_without_acceptance_basis_is_false_completion():
    result = detect_false_completion("COMPLETED", [])
    assert result["completion_applicable"] is False
    assert result["objective_completion_pct"] is None
    assert result["false_completion"] is True


def test_waiting_human_is_normal_execution_state():
    criteria = [{"criterion_id":"C1","satisfied":False,"material":True}]
    result = determine_final_status(criteria, waiting_human=True)
    assert result["final_status"] == "WAITING_HUMAN"


def test_three_failed_routes_can_drive_evidence_based_strategy_mutation_without_drift():
    result = assess_strategy_adaptation([
        {"type":"strategy_attempt","objective_id":"OBJ-1","strategy_id":"A","result":"FAILED","evidence":["EV-A"]},
        {"type":"strategy_change","objective_id":"OBJ-1","from_strategy":"A","to_strategy":"B","basis_evidence":["EV-A"]},
        {"type":"strategy_attempt","objective_id":"OBJ-1","strategy_id":"B","result":"FAILED","evidence":["EV-B"]},
        {"type":"strategy_change","objective_id":"OBJ-1","from_strategy":"B","to_strategy":"C","basis_evidence":["EV-B"]},
        {"type":"strategy_attempt","objective_id":"OBJ-1","strategy_id":"C","result":"FAILED","evidence":["EV-C"]},
        {"type":"strategy_change","objective_id":"OBJ-1","from_strategy":"C","to_strategy":"D","basis_evidence":["EV-C"]},
    ])
    assert result["adaptive_mutation_count"] == 3
    assert result["drift_count"] == 0


def test_revisit_without_new_evidence_is_drift():
    result = assess_strategy_adaptation([
        {"type":"strategy_attempt","objective_id":"OBJ-1","strategy_id":"A","result":"FAILED","evidence":["EV-A"]},
        {"type":"strategy_change","objective_id":"OBJ-1","from_strategy":"A","to_strategy":"B","basis_evidence":["EV-A"]},
        {"type":"strategy_attempt","objective_id":"OBJ-1","strategy_id":"B","result":"FAILED","evidence":["EV-B"]},
        {"type":"strategy_change","objective_id":"OBJ-1","from_strategy":"B","to_strategy":"A","basis_evidence":[]},
    ])
    assert result["drift_count"] == 1
    assert "NO_BASIS_EVIDENCE" in result["classifications"][-1]["reason"]


def test_strategy_change_that_departs_objective_is_drift():
    result = assess_strategy_adaptation([
        {"type":"strategy_attempt","objective_id":"OBJ-1","strategy_id":"A","result":"FAILED","evidence":["EV-A"]},
        {"type":"strategy_change","objective_id":"OBJ-2","from_strategy":"A","to_strategy":"B","basis_evidence":["EV-A"]},
    ])
    assert result["adaptive_mutation_count"] == 0
    assert result["drift_count"] == 1
    assert "OBJECTIVE_DEPARTURE" in result["classifications"][-1]["reason"]


def test_methodology_telemetry_measures_recovery_resume_and_correlation():
    result = methodology_telemetry([
        {"type":"strategy_mutation"},
        {"type":"recovery","success":True},
        {"type":"recovery","success":False},
        {"type":"human_task"},
        {"type":"correlation","success":True},
        {"type":"resume","success":True},
        {"type":"drift"},
    ])
    assert result["strategy_mutation_count"] == 1
    assert result["drift_count"] == 1
    assert result["recovery_efficiency_pct"] == 50
    assert result["resume_success_pct"] == 100
    assert result["correlation_integrity_pct"] == 100


def test_zero_denominator_telemetry_is_not_applicable():
    result = methodology_telemetry([])
    assert result["recovery_efficiency_pct"] is None
    assert result["resume_success_pct"] is None
    assert result["correlation_integrity_pct"] is None
    assert result["recovery_efficiency_applicable"] is False
    assert result["resume_success_applicable"] is False
    assert result["correlation_integrity_applicable"] is False


def test_showstopper_requires_evidence_backed_stop_assessment():
    criteria = [{"criterion_id":"C1","satisfied":False,"material":True}]
    try:
        determine_final_status(criteria, showstopper=True)
    except ValueError as exc:
        assert "evidence-backed stop assessment" in str(exc)
    else:
        raise AssertionError("SHOWSTOPPER must not be caller-declared without evidence")


def test_viable_untried_alternative_prevents_showstopper():
    assessment = assess_stop_decision([
        {"type":"recovery_attempt","result":"FAILED","evidence":["EV-FAIL-A"]},
        {"type":"alternative","alternative_id":"B","status":"VIABLE_UNTRIED","evidence":["EV-B-VIABLE"]},
        {"type":"blocker","material":True,"resolvable":False,"evidence":["EV-BLOCKER"]},
    ])
    assert assessment["recommended_status"] == "CONTINUE"
    assert assessment["showstopper_justified"] is False
    assert assessment["reason"] == "AUTONOMOUS_ALTERNATIVE_REMAINS"


def test_available_human_dependency_is_waiting_human_not_showstopper():
    assessment = assess_stop_decision([
        {"type":"recovery_attempt","result":"FAILED","evidence":["EV-FAIL-A"]},
        {"type":"alternative","alternative_id":"A","status":"BLOCKED","evidence":["EV-A-BLOCKED"]},
        {"type":"human_dependency","required":True,"available":True,"evidence":["EV-AUTHORITY-GATE"]},
        {"type":"blocker","material":True,"resolvable":False,"evidence":["EV-BLOCKER"]},
    ])
    assert assessment["recommended_status"] == "WAITING_HUMAN"
    assert assessment["showstopper_justified"] is False


def test_showstopper_requires_failed_recovery_exhausted_alternatives_and_irreducible_blocker():
    criteria = [{"criterion_id":"C1","satisfied":False,"material":True}]
    assessment = assess_stop_decision([
        {"type":"recovery_attempt","result":"FAILED","evidence":["EV-FAIL-A"]},
        {"type":"recovery_attempt","result":"PARTIAL","evidence":["EV-PARTIAL-B"]},
        {"type":"alternative","alternative_id":"A","status":"FAILED","evidence":["EV-A-FAILED"]},
        {"type":"alternative","alternative_id":"B","status":"BLOCKED","evidence":["EV-B-BLOCKED"]},
        {"type":"human_dependency","required":True,"available":False,"evidence":["EV-HUMAN-UNAVAILABLE"]},
        {"type":"blocker","material":True,"resolvable":False,"evidence":["EV-IRREDUCIBLE"]},
    ])
    assert assessment["recommended_status"] == "SHOWSTOPPER"
    assert assessment["showstopper_justified"] is True
    result = determine_final_status(
        criteria,
        showstopper=True,
        stop_assessment=assessment,
    )
    assert result["final_status"] == "SHOWSTOPPER"


def test_material_blocker_without_exhaustion_is_blocked_not_showstopper():
    assessment = assess_stop_decision([
        {"type":"blocker","material":True,"resolvable":False,"evidence":["EV-BLOCKER"]},
    ])
    assert assessment["recommended_status"] == "BLOCKED"
    assert assessment["showstopper_justified"] is False


def test_autonomous_recovery_route_precedes_available_human_escalation():
    assessment = assess_stop_decision([
        {"type":"recovery_attempt","result":"FAILED","evidence":["EV-FAIL-A"]},
        {"type":"alternative","alternative_id":"B","status":"VIABLE_UNTRIED","requires_human":False,"evidence":["EV-B-VIABLE"]},
        {"type":"human_dependency","required":True,"available":True,"evidence":["EV-HUMAN-AVAILABLE"]},
    ])
    assert assessment["recommended_status"] == "CONTINUE"
    assert assessment["showstopper_justified"] is False
    assert assessment["reason"] == "AUTONOMOUS_ALTERNATIVE_REMAINS"


def test_human_gated_recovery_route_waits_for_human_when_no_autonomous_route_remains():
    assessment = assess_stop_decision([
        {"type":"recovery_attempt","result":"FAILED","evidence":["EV-FAIL-A"]},
        {"type":"alternative","alternative_id":"B","status":"VIABLE_UNTRIED","requires_human":True,"evidence":["EV-B-NEEDS-AUTHORITY"]},
        {"type":"human_dependency","required":True,"available":True,"evidence":["EV-HUMAN-AVAILABLE"]},
    ])
    assert assessment["recommended_status"] == "WAITING_HUMAN"
    assert assessment["showstopper_justified"] is False
    assert assessment["reason"] == "VIABLE_ALTERNATIVE_REQUIRES_HUMAN"
