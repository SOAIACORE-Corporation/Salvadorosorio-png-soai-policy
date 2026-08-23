# syntax=docker/dockerfile:1.7
FROM --platform=linux/amd64 docker.io/library/python:3.12.10-slim-bookworm@sha256:97983fa8cc88343512862c62307159a82261c3528dc025f79e5a3f7af43e50b4 AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /src
RUN python -m pip install --no-cache-dir uv==0.12.5
COPY pyproject.toml uv.lock .python-version ./
COPY packages/python-runtime/pyproject.toml packages/python-runtime/pyproject.toml
COPY packages/python-runtime/src packages/python-runtime/src
COPY apps/core/pyproject.toml apps/core/pyproject.toml
COPY apps/core/src apps/core/src
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
COPY apps/worker/src apps/worker/src
RUN uv sync --frozen --no-dev --no-editable --package soaiacore-core

FROM --platform=linux/amd64 docker.io/library/python:3.12.10-slim-bookworm@sha256:97983fa8cc88343512862c62307159a82261c3528dc025f79e5a3f7af43e50b4 AS runtime
ARG VCS_REF=uncommitted
LABEL org.opencontainers.image.title="SOAIACORE Core" \
      org.opencontainers.image.revision="$VCS_REF" \
      org.opencontainers.image.source="https://github.com/SOAIACORE-Corporation/Salvadorosorio-png-soai-policy"
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SOAIACORE_ROOT=/app \
    SOAIACORE_SCHEMA_DIR=/app/schemas \
    SOAIACORE_MIGRATION_DIR=/app/db/migrations \
    SOAIACORE_FIXTURE_DIR=/app/packages/mock-fixtures/v1 \
    SOAIACORE_PROVIDER_MODE=MOCK
WORKDIR /app
COPY --from=builder /src/.venv /app/.venv
COPY schemas /app/schemas
COPY contracts /app/contracts
COPY db/migrations /app/db/migrations
COPY packages/mock-fixtures /app/packages/mock-fixtures
USER 65532:65532
EXPOSE 8000
CMD ["python", "-m", "soaiacore_core"]
