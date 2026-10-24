from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from collect import collect_manifest  # noqa: E402
from pipeline import analyze  # noqa: E402


def test_live_multisource_v2_contains_drive_branch_and_iac():
    manifest_path=ROOT/"schemas"/"examples"/"landscape"/"live-multisource-v2-manifest-v0.1.json"
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle=collect_manifest(manifest,base_dir=manifest_path.parent)
    assert bundle["record_count"]==3
    assert [r["record_type"] for r in bundle["records"]].count("decision")==1
    assert [r["record_type"] for r in bundle["records"]].count("observation")==2

    iac=[r for r in bundle["records"] if r["record_id"].startswith("obs:github-iac:")][0]
    intent=iac["payload"]["value"]["intent"]
    assert intent["public_network_access"]=="Disabled"
    assert intent["sku"]=="B_Standard_B1ms"
    assert intent["version"]=="17"

    analysis=analyze(bundle["records"])
    assert analysis["finding_count"]==0


def test_live_iac_is_declarative_intent_not_physical_state():
    manifest_path=ROOT/"schemas"/"examples"/"landscape"/"live-multisource-v2-manifest-v0.1.json"
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle=collect_manifest(manifest,base_dir=manifest_path.parent)
    iac=[r for r in bundle["records"] if r["record_id"].startswith("obs:github-iac:")][0]
    assert iac["source"]["system"]=="github"
    assert iac["source"]["source_type"]=="repo"
    assert iac["payload"]["fact_type"]=="config"
