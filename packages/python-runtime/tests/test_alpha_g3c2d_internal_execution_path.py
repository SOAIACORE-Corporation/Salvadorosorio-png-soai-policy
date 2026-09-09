from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "soa-intelligence-g3c2d-governed-internal-batch.yml"
R1_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "soa-intelligence-g3c2d-r1-validation.yml"

EXPECTED_MAIN_BASELINE = "185b3018e7cdc053b125b1c368db59858403b28d"
EXPECTED_INTERNAL_BUNDLE_SHA256 = "d814a6090fda02ad0f87b95a3e860017372c31219007775a4751850c2075d69b"
EXPECTED_BINDING_SHA256 = "3c839b730981556510ac67bbac58e8afcf4e1432f7fd63a6f6cb244639705bf2"
EXPECTED_CONFIRMATION = "I_UNDERSTAND_NINE_INTERNAL_PREHOLDOUT_CALLS_ONLY"
EXPECTED_CASE_IDS = {
    "FRT-SCOPE-012",
    "FRT-UNKNOWN-009",
    "SOC-DECISION-007",
    "SOC-DECISION-008",
    "SOC-MEMADM-013",
    "SOC-MEMADM-014",
    "SOC-SUPERSEDE-009",
    "SOC-TCUT-001",
    "SOC-TCUT-005",
}


def _live_text() -> str:
    return LIVE_WORKFLOW.read_text(encoding="utf-8")


def _r1_text() -> str:
    return R1_WORKFLOW.read_text(encoding="utf-8")


def _dispatch_inputs_block(text: str) -> str:
    start = text.index("    inputs:\n")
    end = text.index("\npermissions:\n")
    return text[start:end]


def test_live_workflow_is_dispatch_only_and_has_no_private_payload_input():
    text = _live_text()
    assert "on:\n  workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text

    inputs = _dispatch_inputs_block(text)
    assert "expected_main_sha:" in inputs
    assert "r2_authority_ref:" in inputs
    assert "one_batch_confirmation:" in inputs
    assert "bundle" not in inputs.lower()
    assert "payload" not in inputs.lower()
    assert "evidence" not in inputs.lower()


def test_live_workflow_uses_only_opaque_secret_handles_for_private_bundle_and_provider_key():
    text = _live_text()
    assert "PRIVATE_BUNDLE_B64: ${{ secrets.SOAIACORE_G3C2D_INTERNAL_BUNDLE_B64 }}" in text
    assert "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}" in text
    assert "OPENAI_API_KEY_HANDLE: ${{ secrets.OPENAI_API_KEY }}" in text
    assert "echo \"$PRIVATE_BUNDLE_B64\"" not in text
    assert "printf '%s' \"$PRIVATE_BUNDLE_B64\"" not in text
    assert "cat \"$PRIVATE_BUNDLE_PATH\"" not in text
    assert "private bundle secret is not valid base64" in text
    assert "rm -f \"$PRIVATE_BUNDLE_PATH\"" in text


def test_live_workflow_pins_exact_internal_bundle_binding_and_nine_case_set():
    text = _live_text()
    assert EXPECTED_INTERNAL_BUNDLE_SHA256 in text
    assert EXPECTED_BINDING_SHA256 in text
    assert "EXPECTED_INTERNAL_CASE_COUNT: '9'" in text
    assert "bundle.get(\"sensitivity_scope\") != \"INTERNAL\"" in text
    assert "len(cases) != 9" in text
    assert "Holdout case present in INTERNAL private bundle" in text
    for case_id in EXPECTED_CASE_IDS:
        assert f'"{case_id}"' in text


def test_live_workflow_binds_exact_main_r2_confirmation_and_replay_claim_before_outbound():
    text = _live_text()
    assert "test \"$(git rev-parse HEAD)\" = \"$EXPECTED_MAIN_SHA\"" in text
    assert "test \"$(git rev-parse origin/main)\" = \"$EXPECTED_MAIN_SHA\"" in text
    assert EXPECTED_CONFIRMATION in text
    assert "G3C2D_INTENT_SHA256=$governed_intent_sha" in text
    assert "G3C2D_R2_AUTHORITY_REF=$R2_AUTHORITY_REF" in text
    assert "R2 authority reference has already been claimed" in text

    claim = text.index("- name: Claim non-replay INTERNAL batch intent in Issue 67")
    execute = text.index("- name: Execute bounded nine-case INTERNAL Provider A batch")
    assert claim < execute


def test_live_workflow_keeps_preflight_no_outbound_and_enables_outbound_only_in_execute_step():
    text = _live_text()
    validate = text.index("- name: Validate bundle against sealed manifest and sensitivity binding with zero outbound")
    preflight = text.index("- name: Prepare exact batch intent with zero credential read and zero provider I/O")
    execute = text.index("- name: Execute bounded nine-case INTERNAL Provider A batch")

    assert "export SOAIACORE_G3C2B0_NO_OUTBOUND=1" in text[validate:execute]
    assert "unset OPENAI_API_KEY || true" in text[validate:execute]
    assert "SOAIACORE_G3C2B0_NO_OUTBOUND: '0'" in text[execute:]
    assert text.count("SOAIACORE_G3C2B0_NO_OUTBOUND: '0'") == 1


def test_live_workflow_preserves_quality_continue_and_governance_stop_contract_via_existing_runner():
    text = _live_text()
    assert "python -m soaiacore_runtime.preholdout_live execute" in text
    assert "--one-batch-confirmation \"$ONE_BATCH_CONFIRMATION\"" in text
    assert "--intent-lock \"$RUNNER_TEMP/g3c2d-local-intent.lock\"" in text
    assert "--receipt-out \"$RUNNER_TEMP/g3c2d-internal-receipt.json\"" in text
    assert "data[\"planned_case_count\"] == 9" in text
    assert "0 <= data[\"external_provider_calls\"] <= 9" in text
    assert "0 <= data[\"transport_attempt_count\"] <= 9" in text
    assert "data[\"holdout\"] is False" in text
    assert "data[\"full_dataset\"] is False" in text
    assert "data[\"tools_enabled\"] is False" in text
    assert "data[\"g3_quality_pass_claimed\"] is False" in text
    assert "continue-on-error: true" in text
    assert "steps.execute.outcome != 'success'" in text


def test_live_workflow_does_not_make_confidential_or_holdout_scope_selectable():
    text = _live_text()
    inputs = _dispatch_inputs_block(text)
    assert "sensitivity" not in inputs.lower()
    assert "partition" not in inputs.lower()
    assert "case_id" not in inputs.lower()
    assert "model" not in inputs.lower()
    assert "provider" not in inputs.lower()
    assert "retry" not in inputs.lower()
    assert "INTERNAL" in text
    assert "CONFIDENTIAL" not in inputs
    assert "holdout" not in inputs.lower()


def test_r1_validation_is_no_outbound_and_cannot_read_real_secrets():
    text = _r1_text()
    assert "SOAIACORE_G3C2B0_NO_OUTBOUND: '1'" in text
    assert "unset OPENAI_API_KEY || true" in text
    assert "unset SOAIACORE_G3C2D_INTERNAL_BUNDLE_B64 || true" in text
    assert "secrets.OPENAI_API_KEY" not in text
    assert "secrets.SOAIACORE_G3C2D_INTERNAL_BUNDLE_B64" not in text
    assert "external provider calls: 0" in text
    assert "credential read: false" in text


def test_r1_scope_keeps_sealed_dataset_runner_and_private_payload_immutable():
    text = _r1_text()
    assert "soa-alpha-golden-v0.2.json" in text
    assert "soa-alpha-golden-v0.2.holdout-seal.json" in text
    assert "soa-alpha-golden-v0.2.preholdout-sensitivity.json" in text
    assert "preholdout_live.py" in text
    assert "Private bundle or env payload must never be committed" in text
    assert "test_alpha_g3c2d_internal_execution_path.py" in text


def test_authorized_r1_baseline_constant_is_documented_for_reconciliation():
    # This test intentionally carries the exact R1 starting baseline as audit metadata.
    # The future LIVE workflow does not hard-code it because execution must bind to the
    # post-merge protected main supplied by a fresh R2 authorization.
    assert EXPECTED_MAIN_BASELINE == "185b3018e7cdc053b125b1c368db59858403b28d"
