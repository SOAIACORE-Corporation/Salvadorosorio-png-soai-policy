import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from mocatriz_continuity import (  # noqa: E402
    closure_claim,
    score_continuity,
    verify_resume_snapshot,
)

FIXTURE = ROOT / "schemas" / "examples" / "landscape" / "mocatriz-continuity-test-02-v1.json"


def _load():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_resume_preserves_objective_rules_pending_and_checkpoint_identity():
    data = _load()
    result = verify_resume_snapshot(data["baseline"], data["resumed"])
    assert result["checkpoint_match"] is True
    assert result["memory_continuity"] is True
    assert result["resumption_continuity"] is True
    assert result["execution_continuity"] is True
    assert result["observation_continuity"] is True
    assert result["lost_pending_ids"] == []
    assert result["lost_evidence_refs"] == []


def test_continuity_score_reaches_demonstrated_band_without_nullifier():
    data = _load()
    result = score_continuity(
        dimension_scores=data["dimension_scores"],
        nullifying_failures=data["nullifying_failures"],
    )
    assert result["score"] == 30
    assert result["passed"] is True
    assert result["effective_continuity"] is True
    assert result["band"] == "FUNCTIONAL_CONTINUITY_DEMONSTRATED"


def test_any_nullifying_failure_fails_even_with_high_score():
    data = _load()
    result = score_continuity(
        dimension_scores=data["dimension_scores"],
        nullifying_failures=["FABRICATED_EVIDENCE"],
    )
    assert result["score"] == 30
    assert result["passed"] is False
    assert result["effective_continuity"] is False
    assert result["band"] == "FAIL_NULLIFIED"


def test_execution_success_does_not_imply_functional_completion():
    data = _load()["functional_validation"]
    result = closure_claim(
        build_verified=data["build_verified"],
        security_verified=data["security_verified"],
        deployment_verified=data["deployment_verified"],
        functional_verified=data["functional_verified"],
    )
    assert result["status"] == "COMPLETED_WITH_EXCEPTIONS"
    assert result["functional_closure_allowed"] is False


def test_full_closure_requires_functional_evidence():
    result = closure_claim(
        build_verified=True,
        security_verified=True,
        deployment_verified=True,
        functional_verified=True,
    )
    assert result["status"] == "COMPLETED"
    assert result["functional_closure_allowed"] is True
