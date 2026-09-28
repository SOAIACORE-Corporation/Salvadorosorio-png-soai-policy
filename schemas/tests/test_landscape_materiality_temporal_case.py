from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from materiality import evaluate_cost_materiality  # noqa: E402
from temporal_case import temporal_decision_cases  # noqa: E402


def test_materiality_without_policy_does_not_invent_threshold():
    result=evaluate_cost_materiality(previous_amount=100,current_amount=130,policy=None)
    assert result["state"]=="NO_POLICY"
    assert result["material"] is None
    assert result["delta_percent"]==30.0


def test_materiality_uses_explicit_any_policy():
    result=evaluate_cost_materiality(
        previous_amount=100,current_amount=130,
        policy={"absolute_threshold":50,"percent_threshold":20,"mode":"ANY"}
    )
    assert result["state"]=="EVALUATED"
    assert result["material"] is True


def test_materiality_unknown_if_evidence_incomplete():
    result=evaluate_cost_materiality(previous_amount=None,current_amount=130,policy={"percent_threshold":20})
    assert result["state"]=="UNKNOWN"
    assert result["material"] is None


def test_persistent_finding_becomes_nonranked_temporal_case():
    pattern={
        "pattern_type":"PERSISTENT_FINDING",
        "subject_id":"finding:R-006",
        "occurrences":3,
        "confidence":1.0,
        "interpretation":"Finding persisted."
    }
    case=temporal_decision_cases([pattern])[0]
    assert case["decision_required"] is True
    assert [o["option_id"] for o in case["alternatives"]]==["MAINTAIN","INVESTIGATE","PREPARE_CHANGE"]
    assert case["authority"]["execution_authority"]=="SEPARATE_APPROVAL_REQUIRED"


def test_repeated_visibility_gap_case_can_be_accepted_or_closed():
    pattern={
        "pattern_type":"REPEATED_VISIBILITY_GAP",
        "subject_id":"finding:owner",
        "occurrences":2,
        "confidence":1.0,
        "interpretation":"Gap recurred."
    }
    case=temporal_decision_cases([pattern])[0]
    assert {o["option_id"] for o in case["alternatives"]}=={"ACCEPT_GAP","CLOSE_GAP"}


def test_cost_trend_case_requires_materiality_definition_option():
    pattern={
        "pattern_type":"MONOTONIC_COST_INCREASE",
        "subject_id":"SOAiaCore",
        "occurrences":3,
        "confidence":1.0,
        "interpretation":"Cost increased."
    }
    case=temporal_decision_cases([pattern])[0]
    assert "DEFINE_MATERIALITY" in {o["option_id"] for o in case["alternatives"]}
