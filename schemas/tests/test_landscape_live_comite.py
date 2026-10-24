from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from collect import collect_manifest  # noqa: E402


def test_live_comite_decision_normalizes_with_explicit_authority():
    manifest_path=ROOT/"schemas"/"examples"/"landscape"/"live-comite-manifest-v0.1.json"
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle=collect_manifest(manifest,base_dir=manifest_path.parent)
    assert bundle["record_count"]==1
    record=bundle["records"][0]
    assert record["record_type"]=="decision"
    assert record["source"]["system"]=="drive"
    assert record["source"]["trust_level"]=="authoritative"
    assert record["payload"]["decision_type"]=="HOLD"
    assert record["payload"]["authority"]=="Architecture / Terraform"
