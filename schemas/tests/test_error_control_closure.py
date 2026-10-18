from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from error_control_audit import audit_error_controls  # noqa: E402


def test_all_known_errors_are_accounted_for_and_unresolved_are_explicit():
    result = audit_error_controls(ROOT)
    assert result["total_errors"] >= 21
    assert result["all_errors_accounted_for"] is True

    rows = {row["error_id"]: row for row in result["rows"]}
    for error_id in result["unresolved_error_ids"]:
        assert error_id in rows
        assert rows[error_id]["effective_status"] in {"OPEN", "MITIGATED", "WAITING_HUMAN"}

    assert "ERR-20261017-031" in result["unresolved_error_ids"]
    assert rows["ERR-20261017-031"]["effective_status"] == "OPEN"


def test_security_gate_error_is_effectively_controlled():
    result = audit_error_controls(ROOT)
    rows = {row["error_id"]: row for row in result["rows"]}
    assert rows["ERR-20260926-015"]["effective_status"] == "CONTROLLED"


def test_required_acceptance_gate_not_starved_by_commit_churn():
    result = audit_error_controls(ROOT)
    rows = {row["error_id"]: row for row in result["rows"]}
    assert rows["ERR-20260926-021"]["class"] == "CI_STARVATION_BY_COMMIT_CHURN"
    assert rows["ERR-20260926-021"]["effective_status"] == "CONTROLLED"
