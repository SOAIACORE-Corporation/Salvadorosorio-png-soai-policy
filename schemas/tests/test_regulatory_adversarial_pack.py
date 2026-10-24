from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "schemas" / "examples" / "regulatory" / "adversarial-scenario-registry-v0.1.json"


def _registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_adversarial_pack_has_fifteen_scenarios():
    data=_registry()
    assert data["pack_version"]=="0.1"
    assert len(data["scenarios"])==15


def test_scenario_legal_claims_default_to_unverified():
    data=_registry()
    assert data["legal_claim_default_state"]=="UNVERIFIED"


def test_each_scenario_declares_jurisdiction_and_required_source_classes():
    for scenario in _registry()["scenarios"]:
        assert scenario["jurisdictions"]
        assert scenario["required_source_classes"]


def test_external_obligations_are_never_internally_waived():
    for scenario in _registry()["scenarios"]:
        if scenario["exception_rule"]=="external obligations non-waivable":
            assert scenario["exception_rule"]!="SOA may waive law"


def test_ebr_scenario_requires_data_integrity_and_cgmp_sources():
    scenario=next(s for s in _registry()["scenarios"] if s["id"]=="ADV-002")
    assert "data_integrity" in scenario["required_source_classes"]
    assert "cgmp" in scenario["required_source_classes"]
