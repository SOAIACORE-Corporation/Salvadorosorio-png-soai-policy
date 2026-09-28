import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from memory_cycle import run_memory_cycle_from_sources  # noqa: E402

FIXTURE = ROOT / "schemas" / "examples" / "landscape" / "live-memory-recovery-sources-20260926.json"


def test_live_durable_sources_reconstruct_memory_without_manual_manifest():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = run_memory_cycle_from_sources(
        payload["sources"],
        as_of=payload["observed_at"],
        controls=[
            {"control_id":"live-source-adaptation","executed":True,"changed_outcome":True},
            {"control_id":"manifest-generation","executed":True,"changed_outcome":True},
            {"control_id":"context-integrity","executed":True,"changed_outcome":True},
        ],
    )
    assert result["resolve"]["canonicalization_status"] == "ELIGIBLE"
    assert result["understand"]["context_integrity_score_pct"] == 100
    assert result["generated_manifest"]["generated_from_durable_evidence"] is True
    assert len(result["adapted_evidence"]) == 5
    refs = {
        ref
        for item in result["generated_manifest"]["requirements"]
        for ref in item["source_refs"]
    }
    assert "github-actions:36233893774" in refs
    assert "receipts/SOAIACORE_MEMORY_AUTOMATION_PILOT_AUTHORITY_2026-09-26.md" in refs
