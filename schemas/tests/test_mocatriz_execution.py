from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from mocatriz_execution import (  # noqa: E402
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


def test_waiting_human_is_normal_execution_state():
    criteria = [{"criterion_id":"C1","satisfied":False,"material":True}]
    result = determine_final_status(criteria, waiting_human=True)
    assert result["final_status"] == "WAITING_HUMAN"


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
