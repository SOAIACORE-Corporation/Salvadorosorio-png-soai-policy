from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from regulatory import (
    applicability_record,
    can_internal_exception_override,
    regulatory_assertion_record,
    regulatory_execution_gate,
    regulatory_source_record,
)  # noqa: E402


REG_DIR=ROOT/"schemas"/"examples"/"regulatory"


def _load(name):
    return json.loads((REG_DIR/name).read_text(encoding="utf-8"))


def test_binding_external_regulation_cannot_be_waived_by_soa():
    source=regulatory_source_record(_load("source-us-21cfr211-v0.1.json"))
    assert source["payload"]["binding_level"]=="binding"
    assert can_internal_exception_override(source,"SOA") is False


def test_current_regulatory_basis_allows_analysis_and_downstream_control_evaluation():
    source=regulatory_source_record(_load("source-us-21cfr211-v0.1.json"))
    gate=regulatory_execution_gate([source],material_action=True)
    assert gate["analysis_allowed"] is True
    assert gate["execution_allowed"] is True
    assert gate["state"]=="REGULATORY_BASIS_CURRENT"


def test_stale_regulatory_source_allows_analysis_but_blocks_material_execution():
    raw=_load("source-us-21cfr211-v0.1.json")
    raw["freshness"]="stale"
    source=regulatory_source_record(raw)
    gate=regulatory_execution_gate([source],material_action=True)
    assert gate["analysis_allowed"] is True
    assert gate["execution_allowed"] is False
    assert gate["state"]=="REGULATORY_REVIEW_REQUIRED"


def test_missing_regulatory_basis_does_not_stop_reasoning():
    gate=regulatory_execution_gate([],material_action=True)
    assert gate["analysis_allowed"] is True
    assert gate["execution_allowed"] is False
    assert gate["state"]=="REGULATORY_VISIBILITY_GAP"


def test_guidance_is_not_silently_promoted_to_binding_law():
    source=regulatory_source_record(_load("source-us-fda-data-integrity-v0.1.json"))
    assert source["payload"]["binding_level"]=="authoritative_guidance"


def test_regulatory_assertion_preserves_source_and_review_requirement():
    assertion=regulatory_assertion_record({
        "assertion_id":"regassert:us:211.68:computer-controls",
        "claim":"Computerized GMP systems require controls that limit record changes to authorized personnel and preserve backup data.",
        "regulatory_source_ids":["regsrc:us:21cfr:part211"],
        "jurisdiction":"US",
        "binding_level":"binding",
        "interpretation":"Applicable to electronic GMP records and computerized production/control systems.",
        "confidence":1.0,
        "legal_review_required":False,
    },observed_at="2026-09-26T04:23:00Z")
    assert assertion["record_type"]=="regulatory_assertion"
    assert assertion["payload"]["regulatory_source_ids"]==["regsrc:us:21cfr:part211"]


def test_scenario_claim_can_require_review_without_becoming_fact():
    app=applicability_record({
        "assessment_id":"app:scenario-ebr:211.68",
        "scenario_id":"ADV-002",
        "assertion_id":"regassert:us:211.68:computer-controls",
        "applies":"PARTIAL",
        "reason":"The scenario implicates computerized GMP controls, but legal adulteration conclusions require separate statutory analysis.",
        "confidence":0.9,
        "decision_state":"REQUIRES_REVIEW",
    },observed_at="2026-09-26T04:23:00Z")
    assert app["payload"]["decision_state"]=="REQUIRES_REVIEW"
