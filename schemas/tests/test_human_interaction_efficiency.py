import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from human_interaction import evaluate_preflight_completeness  # noqa: E402


PRECONDITIONS = [
    {"id": "DEPENDENCIES", "machine_verifiable": True, "required_before_human_action": True},
    {"id": "PERMISSIONS", "machine_verifiable": True, "required_before_human_action": True},
    {"id": "COLLISIONS", "machine_verifiable": True, "required_before_human_action": True},
    {"id": "COMPATIBILITY", "machine_verifiable": True, "required_before_human_action": True},
    {"id": "EXISTING_STATE", "machine_verifiable": True, "required_before_human_action": True},
]


def test_incomplete_preflight_fails_and_counts_avoidable_human_iteration():
    result = evaluate_preflight_completeness(
        preconditions=PRECONDITIONS,
        validated_before_first_human_action=["DEPENDENCIES", "PERMISSIONS", "COLLISIONS"],
        human_actions=[
            {"id": "HA-1", "authority_required": True, "rework_due_to_precheck_miss": True},
            {"id": "HA-2", "authority_required": True, "rework_due_to_precheck_miss": False},
        ],
    )
    assert result["status"] == "FAIL_PRECHECK_MISS"
    assert result["precheck_complete"] is False
    assert result["missed_precondition_ids"] == ["COMPATIBILITY", "EXISTING_STATE"]
    assert result["human_actions"] == {"total": 2, "necessary": 1, "avoidable": 1}
    assert result["human_interaction_efficiency"]["result_pct"] == 50.0
    assert result["avoidable_human_interaction_rate"]["result_pct"] == 50.0


def test_complete_preflight_requests_only_the_authority_bound_action():
    result = evaluate_preflight_completeness(
        preconditions=PRECONDITIONS,
        validated_before_first_human_action=[item["id"] for item in PRECONDITIONS],
        human_actions=[
            {"id": "HA-1", "authority_required": True, "rework_due_to_precheck_miss": False}
        ],
    )
    assert result["status"] == "PASS"
    assert result["precheck_complete"] is True
    assert result["missed_precondition_ids"] == []
    assert result["human_interaction_efficiency"]["result_pct"] == 100.0
    assert result["avoidable_human_interaction_rate"]["result_pct"] == 0.0


def test_zero_human_actions_is_not_exercised_not_fake_100():
    result = evaluate_preflight_completeness(
        preconditions=PRECONDITIONS,
        validated_before_first_human_action=[item["id"] for item in PRECONDITIONS],
        human_actions=[],
    )
    assert result["status"] == "PASS"
    assert result["human_interaction_efficiency"]["status"] == "NOT_EXERCISED"
    assert result["human_interaction_efficiency"]["result_pct"] is None
    assert result["avoidable_human_interaction_rate"]["status"] == "NOT_EXERCISED"
