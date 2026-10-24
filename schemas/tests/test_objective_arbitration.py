import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from objective_arbitration import assess_objective_interference  # noqa: E402


def test_incompatible_writes_require_arbitration_and_do_not_invent_winner():
    result = assess_objective_interference([
        {
            "objective_id": "OBJ-A",
            "priority": 100,
            "actions": [{
                "action_id": "A1",
                "resource_ref": "azure:storage:state",
                "mode": "WRITE",
                "desired_state_hash": "sha256:state-A",
            }],
        },
        {
            "objective_id": "OBJ-B",
            "priority": 1,
            "actions": [{
                "action_id": "B1",
                "resource_ref": "azure:storage:state",
                "mode": "WRITE",
                "desired_state_hash": "sha256:state-B",
            }],
        },
    ])
    assert result["status"] == "ARBITRATION_REQUIRED"
    assert result["parallel_execution_allowed"] is False
    assert result["conflicts"][0]["automatic_winner"] is None


def test_identical_writes_are_coalescible_not_double_executed():
    result = assess_objective_interference([
        {
            "objective_id": "OBJ-A",
            "actions": [{
                "action_id": "A1",
                "resource_ref": "github:branch-protection:main",
                "mode": "WRITE",
                "desired_state_hash": "sha256:same-policy",
            }],
        },
        {
            "objective_id": "OBJ-B",
            "actions": [{
                "action_id": "B1",
                "resource_ref": "github:branch-protection:main",
                "mode": "WRITE",
                "desired_state_hash": "sha256:same-policy",
            }],
        },
    ])
    assert result["status"] == "COALESCE_REQUIRED"
    assert result["parallel_execution_allowed"] is False
    assert result["coalescible"][0]["classification"] == "COALESCIBLE_WRITE"


def test_read_write_same_resource_requires_serialization():
    result = assess_objective_interference([
        {
            "objective_id": "OBJ-READ",
            "actions": [{
                "action_id": "R1",
                "resource_ref": "postgres:decision-ledger",
                "mode": "READ",
            }],
        },
        {
            "objective_id": "OBJ-WRITE",
            "actions": [{
                "action_id": "W1",
                "resource_ref": "postgres:decision-ledger",
                "mode": "WRITE",
                "desired_state_hash": "sha256:new-ledger-state",
            }],
        },
    ])
    assert result["status"] == "SERIALIZE_REQUIRED"
    assert result["parallel_execution_allowed"] is False


def test_read_read_and_disjoint_resources_can_run_in_parallel():
    result = assess_objective_interference([
        {
            "objective_id": "OBJ-A",
            "actions": [
                {"action_id": "A1", "resource_ref": "github:repo", "mode": "READ"},
                {
                    "action_id": "A2",
                    "resource_ref": "azure:rg:A",
                    "mode": "WRITE",
                    "desired_state_hash": "sha256:A",
                },
            ],
        },
        {
            "objective_id": "OBJ-B",
            "actions": [
                {"action_id": "B1", "resource_ref": "github:repo", "mode": "READ"},
                {
                    "action_id": "B2",
                    "resource_ref": "azure:rg:B",
                    "mode": "WRITE",
                    "desired_state_hash": "sha256:B",
                },
            ],
        },
    ])
    assert result["status"] == "CLEAR"
    assert result["parallel_execution_allowed"] is True


def test_non_material_actions_do_not_create_false_conflict():
    result = assess_objective_interference([
        {
            "objective_id": "OBJ-A",
            "actions": [{
                "action_id": "A1",
                "resource_ref": "shared:resource",
                "mode": "WRITE",
                "desired_state_hash": "sha256:A",
                "material": False,
            }],
        },
        {
            "objective_id": "OBJ-B",
            "actions": [{
                "action_id": "B1",
                "resource_ref": "shared:resource",
                "mode": "WRITE",
                "desired_state_hash": "sha256:B",
            }],
        },
    ])
    assert result["status"] == "CLEAR"
