from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from correlate import correlate  # noqa: E402
from decision_case import build_decision_cases  # noqa: E402
from normalize import normalize  # noqa: E402


def test_visibility_gap_case_includes_unknown_cost_and_nonexecuting_alternative():
    cost = normalize("cost", {
        "cost_id":"cost:unknown:test","scope_id":"SOAiaCore","period":"2026-09",
        "amount":None,"currency":"USD","observed_at":"2026-09-26T02:00:00Z"
    })
    corr = correlate([cost])
    cases = build_decision_cases([cost], findings=corr["findings"], impacts=corr["impacts"])
    assert len(cases) == 1
    case = cases[0]
    assert case["decision_required"] is True
    assert case["cost_context"][0]["amount"] is None
    assert case["impacts"][0]["score"] == "UNKNOWN"
    assert {o["option_id"] for o in case["alternatives"]} == {"MAINTAIN","CLOSE_VISIBILITY_GAP"}
    assert case["authority"]["execution_authority"] == "SEPARATE_APPROVAL_REQUIRED"


def test_risk_case_offers_nonranked_analysis_and_change_preparation():
    obs = normalize("monitoring", {
        "observation_id":"obs:health:test","asset_id":"asset:test",
        "metric":"health","state":"Unhealthy","observed_at":"2026-09-26T02:00:00Z"
    })
    corr = correlate([obs])
    cases = build_decision_cases([obs], findings=corr["findings"], impacts=corr["impacts"])
    ids = [o["option_id"] for o in cases[0]["alternatives"]]
    assert ids == ["MAINTAIN","INVESTIGATE","PREPARE_CHANGE"]
    assert all("score" not in option for option in cases[0]["alternatives"])


def test_decision_case_does_not_create_a_decision_record():
    obs = normalize("monitoring", {
        "observation_id":"obs:critical:test","asset_id":"asset:test",
        "metric":"health","state":"Critical","observed_at":"2026-09-26T02:00:00Z"
    })
    corr = correlate([obs])
    case = build_decision_cases([obs], findings=corr["findings"], impacts=corr["impacts"])[0]
    assert "decision" not in case
    assert case["finding"]["severity"] == "CRITICAL"
    assert case["finding"]["adjudication"] == "PENDING"
