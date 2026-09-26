import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "schemas" / "examples" / "landscape" / "operating-error-register-v0.1.json"
POLICY = ROOT / "docs" / "landscape-intelligence" / "PROACTIVE_ERROR_LEARNING_POLICY_v0.1.md"

REQUIRED_FIELDS = {
    "error_id", "detected_at", "class", "phase", "symptom", "root_cause",
    "early_signals", "human_cost", "avoidable", "prevention_rule",
    "automated_detection", "evidence_refs", "control_status", "regression_test",
}

ALLOWED_STATUS = {"OPEN", "MITIGATED", "CONTROLLED", "ACCEPTED_GAP"}


def _load():
    return json.loads(REGISTER.read_text(encoding="utf-8"))


def test_error_learning_policy_declares_precheck_and_human_efficiency():
    text = POLICY.read_text(encoding="utf-8")
    assert "PRECHECK_MISS" in text
    assert "Avoidable Human Interaction Rate" in text
    assert "Mandatory pre-action gate" in text
    assert "Proactivity never grants execution authority" in text


def test_error_register_entries_have_required_fields_and_unique_ids():
    data = _load()
    entries = data["entries"]
    assert len(entries) >= 14
    ids = [entry["error_id"] for entry in entries]
    assert len(ids) == len(set(ids))
    for entry in entries:
        assert REQUIRED_FIELDS <= set(entry)
        assert entry["control_status"] in ALLOWED_STATUS
        assert isinstance(entry["avoidable"], bool)
        assert entry["early_signals"]
        assert entry["evidence_refs"]


def test_error_register_contains_precheck_miss_and_required_fields():
    entries = _load()["entries"]
    misses = [e for e in entries if e["class"] == "PRECHECK_MISS"]
    assert misses
    assert all(e["avoidable"] for e in misses)
    assert all(e["prevention_rule"] for e in misses)


def test_error_register_tracks_avoidable_human_cost():
    entries = _load()["entries"]
    avoidable = [e for e in entries if e["avoidable"]]
    assert len(avoidable) >= 10
    assert all(e["human_cost"] for e in avoidable)


def test_error_register_includes_priority_drift():
    entries = _load()["entries"]
    assert any(e["class"] == "PRIORITY_DRIFT" for e in entries)


def test_policy_requires_task_level_execution():
    text = POLICY.read_text(encoding="utf-8")
    assert "Execution granularity" in text
    assert "tasks and objectives" in text
    assert "OBJECTIVE → PLAN INTERNALLY → EXECUTE SAFE SUBSTEPS" in text
    assert "Success is measured by objective completion" in text


def test_scenario_pack_contains_task_level_execution():
    scenario = (ROOT / "docs" / "landscape-intelligence" / "SCENARIO_PACK_v0.1.md").read_text(encoding="utf-8")
    assert "SCN-024 · Task-level execution versus unit execution" in scenario
    assert "Treat the task objective as the execution unit." in scenario


def test_policy_executes_by_objective_not_microstep():
    text = POLICY.read_text(encoding="utf-8")
    assert "The canonical unit of execution is an **objective**" in text
    assert "OBJECTIVE" in text
    assert "REQUIRED TASK SET" in text
    assert "INTEGRATED VALIDATION" in text
    assert "Technical curiosity never outranks the declared objective" in text
    assert "capability to act is not itself a reason to act" in text
