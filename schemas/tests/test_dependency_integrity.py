import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from dependency_integrity import evaluate_dependency_integrity  # noqa: E402


def test_superseded_evidence_transitively_requires_revalidation():
    result = evaluate_dependency_integrity(
        nodes=[
            {"id": "EV-1", "kind": "evidence", "state": "SUPERSEDED"},
            {"id": "CL-1", "kind": "claim", "state": "CURRENT"},
            {"id": "MEM-1", "kind": "memory", "state": "CURRENT"},
            {"id": "DEC-1", "kind": "decision", "state": "CURRENT"},
        ],
        edges=[
            {"dependency_id": "EV-1", "dependent_id": "CL-1", "material": True},
            {"dependency_id": "CL-1", "dependent_id": "MEM-1", "material": True},
            {"dependency_id": "MEM-1", "dependent_id": "DEC-1", "material": True},
        ],
    )
    assert result["status"] == "REVALIDATION_REQUIRED"
    assert result["effective_states"] == {
        "CL-1": "REVALIDATION_REQUIRED",
        "DEC-1": "REVALIDATION_REQUIRED",
        "EV-1": "REVALIDATION_REQUIRED",
        "MEM-1": "REVALIDATION_REQUIRED",
    }


def test_rejected_evidence_invalidates_material_descendants():
    result = evaluate_dependency_integrity(
        nodes=[
            {"id": "EV-BAD", "kind": "evidence", "state": "REJECTED"},
            {"id": "CLAIM", "kind": "claim", "state": "CURRENT"},
            {"id": "DECISION", "kind": "decision", "state": "CURRENT"},
        ],
        edges=[
            {"dependency_id": "EV-BAD", "dependent_id": "CLAIM", "material": True},
            {"dependency_id": "CLAIM", "dependent_id": "DECISION", "material": True},
        ],
    )
    assert result["invalid_ids"] == ["CLAIM", "DECISION", "EV-BAD"]
    assert result["effective_states"]["DECISION"] == "INVALID"


def test_non_material_historical_lineage_does_not_invalidate_current_decision():
    result = evaluate_dependency_integrity(
        nodes=[
            {"id": "EV-OLD", "kind": "evidence", "state": "SUPERSEDED"},
            {"id": "EV-NEW", "kind": "evidence", "state": "ADMISSIBLE"},
            {"id": "DEC-NEW", "kind": "decision", "state": "CURRENT"},
        ],
        edges=[
            {"dependency_id": "EV-OLD", "dependent_id": "DEC-NEW", "material": False},
            {"dependency_id": "EV-NEW", "dependent_id": "DEC-NEW", "material": True},
        ],
    )
    assert result["effective_states"]["DEC-NEW"] == "CURRENT"
    assert "DEC-NEW" not in result["revalidation_required_ids"]


def test_unknown_evidence_fails_closed_instead_of_becoming_current():
    result = evaluate_dependency_integrity(
        nodes=[
            {"id": "EV-UNKNOWN", "kind": "evidence", "state": "UNKNOWN"},
            {"id": "MEMORY", "kind": "memory", "state": "CURRENT"},
        ],
        edges=[
            {"dependency_id": "EV-UNKNOWN", "dependent_id": "MEMORY", "material": True},
        ],
    )
    assert result["effective_states"]["MEMORY"] == "REVALIDATION_REQUIRED"


def test_dependency_cycle_is_rejected_fail_closed():
    with pytest.raises(ValueError, match="dependency cycle"):
        evaluate_dependency_integrity(
            nodes=[
                {"id": "A", "state": "CURRENT"},
                {"id": "B", "state": "CURRENT"},
            ],
            edges=[
                {"dependency_id": "A", "dependent_id": "B", "material": True},
                {"dependency_id": "B", "dependent_id": "A", "material": True},
            ],
        )
