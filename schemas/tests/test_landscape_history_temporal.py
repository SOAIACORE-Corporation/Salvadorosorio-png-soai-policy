from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from bundle import bundle_records  # noqa: E402
from history import diff_snapshots, list_snapshots, load_snapshot, persist_snapshot  # noqa: E402
from temporal import infer_temporal_patterns  # noqa: E402


def _record(record_id, record_type, payload):
    return {
        "schema_version":"0.1",
        "record_id":record_id,
        "record_type":record_type,
        "source":{
            "source_id":"test","system":"other","source_type":"derived",
            "location":None,"collected_at":"2026-09-26T03:00:00Z",
            "hash":None,"freshness":"current","trust_level":"derived"
        },
        "observed_at":"2026-09-26T03:00:00Z",
        "payload":payload,
    }


def _snapshot(cost, finding=True):
    records = [
        _record("cost:soa","cost_snapshot",{
            "cost_id":"cost:soa","scope_id":"SOAiaCore","period":"2026-09",
            "amount":cost,"currency":"USD","cost_type":"observed",
            "formula":None,"confidence":1.0
        })
    ]
    bundle = bundle_records(records)
    findings = []
    if finding:
        findings.append(_record("finding:gap","finding",{
            "finding_id":"finding:gap","asset_id":None,"type":"visibility_gap",
            "adjudication":"VISIBILITY_GAP","severity":"UNKNOWN",
            "status":"VISIBILITY_GAP","evidence_refs":[],"confidence":1.0
        }))
    analysis = {
        "finding_count":len(findings),"impact_count":0,"decision_case_count":0,
        "findings":findings,"impacts":[],"decision_cases":[]
    }
    return {"bundle":bundle,"analysis":analysis}


def test_append_only_history_persists_and_lists(tmp_path):
    snap = _snapshot(10)
    path = persist_snapshot(tmp_path,bundle=snap["bundle"],analysis=snap["analysis"],observed_at="2026-09-26T03:00:00Z")
    assert path.exists()
    manifests = list_snapshots(tmp_path)
    assert len(manifests) == 1
    loaded = load_snapshot(tmp_path, manifests[0]["snapshot_id"])
    assert loaded["manifest"]["bundle_record_count"] == 1


def test_history_refuses_same_snapshot_directory_overwrite(tmp_path):
    snap = _snapshot(10)
    persist_snapshot(tmp_path,bundle=snap["bundle"],analysis=snap["analysis"],observed_at="2026-09-26T03:00:00Z")
    try:
        persist_snapshot(tmp_path,bundle=snap["bundle"],analysis=snap["analysis"],observed_at="2026-09-26T03:00:00Z")
    except FileExistsError:
        pass
    else:
        raise AssertionError("append-only history must reject overwrite")


def test_diff_detects_changed_cost_and_resolved_finding():
    previous = _snapshot(10, finding=True)
    current = _snapshot(12, finding=False)
    diff = diff_snapshots(previous,current)
    assert diff["changed_record_ids"] == ["cost:soa"]
    assert diff["resolved_finding_ids"] == ["finding:gap"]
    assert diff["unchanged"] is False


def test_temporal_patterns_find_cost_increase_and_repeated_visibility_gap():
    snaps=[_snapshot(10,True),_snapshot(12,True),_snapshot(15,True)]
    patterns=infer_temporal_patterns(snaps)
    kinds={p["pattern_type"] for p in patterns}
    assert "MONOTONIC_COST_INCREASE" in kinds
    assert "PERSISTENT_FINDING" in kinds
    assert "REPEATED_VISIBILITY_GAP" in kinds


def test_temporal_inference_does_not_exist_with_single_snapshot():
    assert infer_temporal_patterns([_snapshot(10,True)]) == []
