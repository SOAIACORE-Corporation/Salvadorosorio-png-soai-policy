from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from bundle import bundle_records  # noqa: E402
from correlate import correlate  # noqa: E402
from identity_audit import identity_aliases  # noqa: E402
from normalize import normalize  # noqa: E402
from safety import assess_action_safety  # noqa: E402


def test_no_data_health_becomes_visibility_gap_not_healthy():
    obs=normalize("monitoring",{
        "observation_id":"obs:nodata","asset_id":"asset:test",
        "metric":"health","state":"NoData","value":0,
        "observed_at":"2026-09-26T03:30:00Z"
    })
    result=correlate([obs])
    assert len(result["findings"])==1
    finding=result["findings"][0]["payload"]
    assert finding["adjudication"]=="VISIBILITY_GAP"
    assert finding["severity"]=="UNKNOWN"
    assert result["impacts"][0]["payload"]["score"]=="UNKNOWN"


def test_same_canonical_asset_with_two_names_becomes_alias_pattern_not_duplicate_identity():
    a1=normalize("azure-resource",{
        "subscription_id":"sub","resource_id":"rid","name":"old-name",
        "resource_type":"generic","environment":"prod","owner":"team",
        "observed_at":"2026-09-26T03:00:00Z"
    })
    a2=normalize("azure-resource",{
        "subscription_id":"sub","resource_id":"rid","name":"new-name",
        "resource_type":"generic","environment":"prod","owner":"team",
        "observed_at":"2026-09-26T03:30:00Z"
    })
    assert a1["payload"]["asset_id"]==a2["payload"]["asset_id"]
    aliases=identity_aliases([a1,a2])
    assert len(aliases)==1
    assert aliases[0]["aliases"]==["new-name","old-name"]


def test_trivial_remove_without_rollback_requires_explicit_approval():
    action={
        "schema_version":"0.1","record_id":"action:delete:1","record_type":"action",
        "source":{
            "source_id":"test","system":"other","source_type":"derived",
            "location":None,"collected_at":"2026-09-26T03:30:00Z",
            "hash":None,"freshness":"current","trust_level":"derived"
        },
        "observed_at":"2026-09-26T03:30:00Z",
        "payload":{
            "action_id":"action:delete:1","decision_id":"decision:1",
            "action_type":"remove","executor":None,"scope":"derived-object",
            "preconditions":[],"rollback":None,"status":"PLANNED"
        }
    }
    result=assess_action_safety(action)
    assert result["gate"]=="EXPLICIT_APPROVAL_REQUIRED"
    assert result["reversible"] is False


def test_remove_with_rollback_does_not_use_irreversible_gate():
    action={
        "record_type":"action",
        "payload":{
            "action_type":"remove",
            "rollback":{"procedure":"recreate from manifest"}
        }
    }
    result=assess_action_safety(action)
    assert result["gate"]=="STANDARD_CONTROL"
