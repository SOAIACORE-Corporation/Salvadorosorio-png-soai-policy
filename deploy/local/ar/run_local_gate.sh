#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
COMPOSE="$HERE/docker-compose.persistence.yml"

command -v docker >/dev/null || { echo 'BLOCKED: docker not installed'; exit 20; }
docker compose version >/dev/null || { echo 'BLOCKED: docker compose unavailable'; exit 21; }

cleanup() {
  docker compose -f "$COMPOSE" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

docker compose -f "$COMPOSE" up -d postgres
for i in $(seq 1 60); do
  if docker compose -f "$COMPOSE" exec -T postgres pg_isready -U soaiacore -d soaiacore >/dev/null 2>&1; then break; fi
  sleep 2
  if [ "$i" -eq 60 ]; then echo 'FAIL: PostgreSQL did not become ready'; exit 30; fi
done

# docker-entrypoint applies migrations on fresh volume. Verify extension and tables.
docker compose -f "$COMPOSE" exec -T postgres psql -v ON_ERROR_STOP=1 -U soaiacore -d soaiacore \
  -c "SELECT extname FROM pg_extension WHERE extname='vector';" \
  -c "SELECT count(*) AS canonical_tables FROM information_schema.tables WHERE table_schema IN ('soa_core','soa_identity','soa_evidence','soa_intelligence','soa_adjudication','soa_ops');"

docker compose -f "$COMPOSE" exec -T postgres psql -v ON_ERROR_STOP=1 -U soaiacore -d soaiacore < "$ROOT/db/tests/seed_minimal.sql"
docker compose -f "$COMPOSE" exec -T postgres psql -v ON_ERROR_STOP=1 -U soaiacore -d soaiacore < "$ROOT/db/tests/architecture_invariants.sql"
docker compose -f "$COMPOSE" exec -T postgres psql -v ON_ERROR_STOP=1 -U soaiacore -d soaiacore < "$ROOT/db/tests/integrity_checks.sql"

echo 'SOAIACORE_LOCAL_POSTGRES_GATE=PASS'
