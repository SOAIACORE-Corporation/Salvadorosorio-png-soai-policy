from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from collect import collect_manifest  # noqa: E402
from reconcile import reconcile  # noqa: E402


def test_p0_baseline_manifest_normalizes_five_sources_without_false_drift():
    manifest_path = ROOT / "schemas" / "examples" / "landscape" / "p0-baseline-manifest-v0.1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle = collect_manifest(manifest, base_dir=manifest_path.parent)

    assert bundle["record_count"] == 5
    assert bundle["source_count"] == 5
    assert set(bundle["record_types"]) == {"asset", "cost_snapshot", "observation"}

    findings = reconcile(bundle["records"])
    assert findings == []


def test_p0_baseline_bundle_has_reproducible_hash():
    manifest_path = ROOT / "schemas" / "examples" / "landscape" / "p0-baseline-manifest-v0.1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    first = collect_manifest(manifest, base_dir=manifest_path.parent)
    second = collect_manifest(manifest, base_dir=manifest_path.parent)
    assert first["sha256"] == second["sha256"]
