from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_core_image_installs_workspace_packages_as_physical_wheels() -> None:
    dockerfile = (ROOT / "apps/core/Dockerfile").read_text(encoding="utf-8")

    assert "uv build --package soaiacore-runtime --wheel" in dockerfile
    assert "uv build --package soaiacore-core --wheel" in dockerfile
    assert "uv pip install --python /src/.venv/bin/python --no-deps" in dockerfile
    assert "_editable_impl_soaiacore_*.pth" in dockerfile
    assert "import pathlib, site, soaiacore_core, soaiacore_runtime" in dockerfile


def test_web_image_exposes_a_startup_aware_live_healthcheck() -> None:
    dockerfile = (ROOT / "apps/web/Dockerfile").read_text(encoding="utf-8")

    assert "test -s /app/.next/standalone/server.js" in dockerfile
    assert "HEALTHCHECK --interval=5s" in dockerfile
    assert "http://127.0.0.1:3000/api/health/live" in dockerfile
    assert "CORE_API_BASE_URL" not in dockerfile
