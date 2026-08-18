#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

export LC_ALL=C

say(){ printf '%s\n' "$*"; }
pass(){ say "PASS  $*"; }
warn(){ say "WARN  $*"; }
fail(){ say "FAIL  $*"; exit 1; }

[[ ${EUID:-$(id -u)} -eq 0 ]] || fail "Run as root for complete inspection."

say "SOAIA_PRECHECK_V1"
say "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
say "host=$(hostname -f 2>/dev/null || hostname)"

source /etc/os-release
[[ "${ID:-}" == "ubuntu" ]] || fail "Unsupported OS: ${ID:-unknown}"
[[ "${VERSION_ID:-}" == "24.04" ]] || warn "Expected Ubuntu 24.04; found ${VERSION_ID:-unknown}"
pass "os=${PRETTY_NAME}"

for cmd in systemctl ss curl getent openssl sha256sum; do
  command -v "$cmd" >/dev/null 2>&1 || fail "Missing required base command: $cmd"
done

say "disk_root=$(df -P / | awk 'NR==2{print $5}')"
say "memory=$(free -h | awk '/Mem:/{print $3"/"$2}')"

for svc in nginx flask_soa_weblite soaia-api soaia-wa-bridge; do
  if systemctl list-unit-files "${svc}.service" --no-legend 2>/dev/null | grep -q "${svc}.service"; then
    say "service_${svc}=$(systemctl is-active "$svc" 2>/dev/null || true)"
  else
    say "service_${svc}=absent"
  fi
done

for port in 80 443 5000 8940; do
  owner=$(ss -ltnp "sport = :$port" 2>/dev/null | tail -n +2 || true)
  if [[ -n "$owner" ]]; then
    say "port_${port}=LISTEN"
    printf '%s\n' "$owner"
  else
    say "port_${port}=free"
  fi
done

if command -v nginx >/dev/null 2>&1; then
  if nginx -t; then
    pass "nginx_config"
  else
    fail "nginx_config"
  fi
else
  warn "nginx not installed"
fi

if command -v python3 >/dev/null 2>&1; then
  say "python=$(python3 --version 2>&1)"
fi
if command -v node >/dev/null 2>&1; then
  say "node=$(node --version 2>&1)"
else
  warn "node absent"
fi

for d in soaia.mx media.soaia.mx; do
  if getent ahostsv4 "$d" >/dev/null 2>&1; then
    ip=$(getent ahostsv4 "$d" | awk 'NR==1{print $1}')
    say "dns_${d}=$ip"
  else
    say "dns_${d}=UNRESOLVED"
  fi
done

if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  pass "OPENAI_API_KEY present in environment (value not printed)"
else
  warn "OPENAI_API_KEY not present in current environment"
fi

pass "precheck_completed"
