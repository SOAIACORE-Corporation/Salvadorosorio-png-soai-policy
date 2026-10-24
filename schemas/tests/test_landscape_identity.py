from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from identity import azure_asset_id, normalize_azure_resource_id, same_asset_id  # noqa: E402


def test_azure_asset_id_is_stable_and_display_name_independent():
    assert azure_asset_id("sub", "/subscriptions/sub/resourceGroups/rg/providers/X/y") == (
        "azure:sub:/subscriptions/sub/resourceGroups/rg/providers/X/y"
    )


def test_identity_rejects_empty_inputs():
    for args in [("", "id"), ("sub", "")]:
        try:
            azure_asset_id(*args)
        except ValueError:
            pass
        else:
            raise AssertionError("empty canonical identity input must fail")


def test_resource_id_normalization_removes_only_trailing_slash():
    assert normalize_azure_resource_id("/a/b/") == "/a/b"


def test_same_asset_id_is_exact_after_outer_whitespace_only():
    assert same_asset_id(" azure:sub:id ", "azure:sub:id")
    assert not same_asset_id("azure:sub:ID", "azure:sub:id")
