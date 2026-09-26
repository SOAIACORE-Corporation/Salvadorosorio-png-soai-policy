from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from collect import collect_manifest  # noqa: E402
from history import persist_snapshot, load_snapshot  # noqa: E402
from pipeline import analyze  # noqa: E402


def test_first_live_multisource_snapshot_is_drive_plus_github_and_read_only(tmp_path):
    manifest_path=ROOT/"schemas"/"examples"/"landscape"/"live-multisource-manifest-v0.1.json"
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle=collect_manifest(manifest,base_dir=manifest_path.parent)

    assert bundle["record_count"]==2
    systems={r["source"]["system"] for r in bundle["records"]}
    assert systems=={"drive","github"}

    analysis=analyze(bundle["records"])
    assert analysis["finding_count"]==0
    assert analysis["decision_case_count"]==0

    path=persist_snapshot(
        tmp_path,
        bundle=bundle,
        analysis=analysis,
        observed_at="2026-09-26T03:12:00Z",
    )
    loaded=load_snapshot(tmp_path,path.name)
    assert loaded["manifest"]["bundle_record_count"]==2
    assert loaded["manifest"]["finding_count"]==0


def test_live_github_branch_state_is_observation_not_decision():
    manifest_path=ROOT/"schemas"/"examples"/"landscape"/"live-multisource-manifest-v0.1.json"
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle=collect_manifest(manifest,base_dir=manifest_path.parent)
    branch=[r for r in bundle["records"] if r["source"]["system"]=="github"][0]
    assert branch["record_type"]=="observation"
    assert branch["payload"]["fact_type"]=="state"
    assert branch["payload"]["value"]["ahead_by"]==78
    assert branch["payload"]["value"]["behind_by"]==0


def test_live_drive_decision_remains_separate_from_github_observation():
    manifest_path=ROOT/"schemas"/"examples"/"landscape"/"live-multisource-manifest-v0.1.json"
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle=collect_manifest(manifest,base_dir=manifest_path.parent)
    decisions=[r for r in bundle["records"] if r["record_type"]=="decision"]
    observations=[r for r in bundle["records"] if r["record_type"]=="observation"]
    assert len(decisions)==1
    assert len(observations)==1
    assert decisions[0]["source"]["system"]=="drive"
    assert observations[0]["source"]["system"]=="github"
