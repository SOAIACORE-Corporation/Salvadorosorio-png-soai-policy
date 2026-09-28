from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from normalize import normalize  # noqa: E402


def test_security_rbac_adapter_preserves_assignment_fact():
    record = normalize("security-rbac", {
        "observation_id":"obs:rbac:1","asset_id":"azure:sub:kv","scope":"/kv",
        "principal_id":"principal-1","role":"Key Vault Secrets User","inherited":False,
        "observed_at":"2026-09-26T02:00:00Z"
    })
    assert record["payload"]["fact_type"] == "identity"
    assert record["payload"]["value"]["role"] == "Key Vault Secrets User"


def test_runtime_adapter_preserves_health_version_and_dependencies():
    record = normalize("runtime", {
        "observation_id":"obs:runtime:core","asset_id":"azure:sub:core",
        "service":"core","environment":"p0","health":"Healthy",
        "version":"sha256:e6564","dependencies":["postgresql","keyvault"],
        "observed_at":"2026-09-26T02:00:00Z"
    })
    assert record["source"]["system"] == "runtime"
    assert record["payload"]["value"]["dependencies"] == ["postgresql","keyvault"]


def test_github_pr_adapter_is_observation_not_implicit_decision():
    record = normalize("github-pr", {
        "observation_id":"obs:pr:84","repo":"SOAIACORE-Corporation/Salvadorosorio-png-soai-policy",
        "pr_number":84,"status":"open","draft":True,
        "observed_at":"2026-09-26T02:00:00Z"
    })
    assert record["record_type"] == "observation"
    assert record["payload"]["fact_type"] == "state"


def test_committee_decision_requires_and_preserves_authority():
    record = normalize("committee-decision", {
        "decision_id":"decision:R-006:HOLD","finding_id":"R-006",
        "decision_type":"HOLD","authority":"Salvador / Comité",
        "rationale":"Do not apply heterogeneous plan globally.",
        "status":"APPROVED","observed_at":"2026-09-26T02:00:00Z"
    })
    assert record["record_type"] == "decision"
    assert record["payload"]["authority"] == "Salvador / Comité"
