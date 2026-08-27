from __future__ import annotations

from pathlib import Path

from validation.prod_hardening_gate import EVIDENCE_KEYS, evaluate, plan_has_destructive_change


ROOT = Path(__file__).resolve().parents[1]


def all_evidence(value: bool) -> dict[str, bool]:
    return {key: value for keys in EVIDENCE_KEYS.values() for key in keys}


def test_repository_scaffold_is_complete_but_live_gate_remains_blocked():
    result = evaluate(ROOT, all_evidence(False))
    assert result["status"] == "BLOCKED"
    assert all(family["status"] == "CONDITIONAL" for family in result["families"].values())


def test_complete_provider_evidence_closes_every_family():
    result = evaluate(ROOT, all_evidence(True))
    assert result["status"] == "PASS"
    assert all(family["status"] == "PASS" for family in result["families"].values())


def test_destroy_or_replace_plan_is_rejected():
    delete_plan = {"resource_changes": [{"change": {"actions": ["delete", "create"]}}]}
    update_plan = {"resource_changes": [{"change": {"actions": ["update"]}}]}
    assert plan_has_destructive_change(delete_plan) is True
    assert plan_has_destructive_change(update_plan) is False
    result = evaluate(ROOT, all_evidence(True), delete_plan)
    assert result["status"] == "BLOCKED"
    assert result["families"]["terraform_state_change_control"]["status"] == "CONDITIONAL"
