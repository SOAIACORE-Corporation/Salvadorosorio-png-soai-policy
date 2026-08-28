# syntax=docker/dockerfile:1.7
FROM --platform=linux/amd64 docker.io/library/python:3.12-slim-trixie@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS builder

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
RUN uv sync --frozen --no-dev --no-editable --package soaiacore-worker

FROM --platform=linux/amd64 docker.io/library/python:3.12-slim-trixie@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS runtime
ARG VCS_REF=uncommitted
LABEL org.opencontainers.image.title="SOAIACORE Worker" \
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
RUN apt-get update \
    && apt-get install --only-upgrade -y --no-install-recommends \
      bsdutils libblkid1 liblastlog2-2 libmount1 libsmartcols1 libuuid1 \
      login mount util-linux libssl3t64 openssl openssl-provider-legacy \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /src/.venv /app/.venv
COPY schemas /app/schemas
COPY contracts /app/contracts
COPY db/migrations /app/db/migrations
COPY packages/mock-fixtures /app/packages/mock-fixtures
USER 65532:65532
CMD ["python", "-m", "soaiacore_worker", "run-one"]
