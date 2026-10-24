from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from error_control_audit import audit_error_controls  # noqa: E402


def test_error_control_audit_accounts_for_all_errors():
    result = audit_error_controls(ROOT)
    assert result["all_errors_accounted_for"] is True
    assert result["total_errors"] >= 20


def test_environment_errors_are_effectively_controlled():
    result = audit_error_controls(ROOT)
    rows = {row["error_id"]: row for row in result["rows"]}
    assert rows["ERR-20260926-002"]["effective_status"] == "CONTROLLED"
    assert rows["ERR-20260926-003"]["effective_status"] == "CONTROLLED"
    assert rows["ERR-20260926-004"]["effective_status"] == "CONTROLLED"


def test_intent_interpretation_remains_explicit_accepted_gap():
    result = audit_error_controls(ROOT)
    rows = {row["error_id"]: row for row in result["rows"]}
    assert rows["ERR-20260926-014"]["effective_status"] == "ACCEPTED_GAP"
    assert rows["ERR-20260926-014"]["historical_status"] == "MITIGATED"
