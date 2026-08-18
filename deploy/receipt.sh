#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

OUT_DIR="${1:-./receipts}"
mkdir -p "$OUT_DIR"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$OUT_DIR/SOAIA_RECEIPT_${TS}.txt"

{
  echo "SOAIA_DEPLOYMENT_RECEIPT_V1"
  echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "host=$(hostname -f 2>/dev/null || hostname)"
  echo "kernel=$(uname -srmo)"
  if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "git_commit=$(git rev-parse HEAD)"
    echo "git_branch=$(git rev-parse --abbrev-ref HEAD)"
    echo "git_dirty=$(test -n "$(git status --porcelain)" && echo true || echo false)"
  fi
  echo "--- services ---"
  for svc in flask_soa_weblite soaia-api nginx; do
    printf '%s=' "$svc"
    systemctl is-active "$svc" 2>/dev/null || true
  done
  echo "--- ports ---"
  ss -ltnp 2>/dev/null | grep -E ':(80|443|5000|8940)\b' || true
  echo "--- health ---"
  printf 'soaia_live='; curl -fsS --max-time 5 http://127.0.0.1:8940/health/live 2>/dev/null || echo UNAVAILABLE
  printf 'soaia_ready='; curl -fsS --max-time 5 http://127.0.0.1:8940/health/ready 2>/dev/null || echo UNAVAILABLE
  echo "--- dns ---"
  for d in soaia.mx media.soaia.mx; do
    printf '%s=' "$d"
    getent ahostsv4 "$d" 2>/dev/null | awk 'NR==1{print $1}' || true
  done
  echo "--- critical checksums ---"
  for f in /etc/systemd/system/soaia-api.service /opt/soaia/app.py /etc/soaia/soaia.env.example; do
    [[ -f "$f" ]] && sha256sum "$f"
  done
} > "$OUT"

chmod 0640 "$OUT"
printf '%s\n' "$OUT"
