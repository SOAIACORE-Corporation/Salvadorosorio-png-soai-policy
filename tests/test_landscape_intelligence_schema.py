import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "landscape-intelligence-v0.1.schema.json"
EXAMPLES = ROOT / "schemas" / "examples" / "landscape"


def _validator():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.mark.parametrize(
    "filename",
    [
        "asset-postgresql-p0-v0.1.json",
        "finding-service-health-adopt-v0.1.json",
        "cost-soaiacore-observed-v0.1.json",
        "finding-terraform-global-hold-v0.1.json",
        "cost-unknown-v0.1.json",
    ],
)
def test_reference_fixtures_validate(filename):
    payload = json.loads((EXAMPLES / filename).read_text(encoding="utf-8"))
    _validator().validate(payload)


def test_unknown_cost_is_not_encoded_as_zero():
    payload = json.loads((EXAMPLES / "cost-unknown-v0.1.json").read_text(encoding="utf-8"))
    assert payload["payload"]["amount"] is None
    assert payload["payload"]["cost_type"] == "unknown"
    _validator().validate(payload)


def test_observed_cost_requires_currency_when_amount_exists():
    payload = json.loads((EXAMPLES / "cost-soaiacore-observed-v0.1.json").read_text(encoding="utf-8"))
    payload["payload"]["currency"] = None
    with pytest.raises(ValidationError):
        _validator().validate(payload)


def test_estimated_material_cost_requires_nonempty_formula():
    payload = json.loads((EXAMPLES / "cost-unknown-v0.1.json").read_text(encoding="utf-8"))
    payload["record_id"] = "cost:estimate:test"
    payload["payload"].update(
        {
            "cost_id": "cost:estimate:test",
            "cost_type": "implementation",
            "amount": 10.0,
            "currency": "USD",
            "formula": None,
            "confidence": 0.5,
        }
    )
    with pytest.raises(ValidationError):
        _validator().validate(payload)


def test_decision_without_explicit_authority_is_rejected():
    record = {
        "schema_version": "0.1",
        "record_id": "decision:test",
        "record_type": "decision",
        "source": {
            "source_id": "committee",
            "system": "drive",
            "source_type": "human_decision",
            "location": "COMITE",
            "collected_at": "2026-09-25T22:29:14Z",
            "hash": None,
            "freshness": "current",
            "trust_level": "authoritative",
        },
        "observed_at": "2026-09-25T22:29:14Z",
        "payload": {
            "decision_id": "decision:test",
            "decision_type": "HOLD",
            "rationale": "No global apply until heterogeneous changes are separated.",
            "status": "APPROVED",
        },
    }
    with pytest.raises(ValidationError):
        _validator().validate(record)


def test_finding_can_remain_pending_without_becoming_fix():
    payload = json.loads(
        (EXAMPLES / "finding-terraform-global-hold-v0.1.json").read_text(encoding="utf-8")
    )
    payload["payload"]["adjudication"] = "PENDING"
    payload["payload"]["status"] = "OPEN"
    _validator().validate(payload)
