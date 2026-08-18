#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 027

APP_USER="soaia"
APP_GROUP="soaia"
APP_ROOT="/opt/soaia"
DATA_ROOT="/var/lib/soaia"
LOG_ROOT="/var/log/soaia"
VENV="$APP_ROOT/.venv"

log(){ printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die(){ log "FATAL: $*"; exit 1; }

[[ ${EUID:-$(id -u)} -eq 0 ]] || die "Run as root."
[[ -x ./deploy/precheck.sh ]] || die "Run from repository root; deploy/precheck.sh not found."

log "Running PRECHECK before any change"
./deploy/precheck.sh | tee /tmp/soaia-precheck-before.txt

source /etc/os-release
[[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "24.04" ]] || die "This stage bootstrap supports Ubuntu 24.04 only."

log "Installing minimal runtime packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  python3-venv python3-pip nginx curl ca-certificates jq sqlite3 ufw

if ! getent group "$APP_GROUP" >/dev/null; then
  groupadd --system "$APP_GROUP"
fi
if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd --system --gid "$APP_GROUP" --home-dir "$APP_ROOT" --shell /usr/sbin/nologin "$APP_USER"
fi

install -d -o "$APP_USER" -g "$APP_GROUP" -m 0750 "$APP_ROOT" "$DATA_ROOT" "$LOG_ROOT"
install -d -o root -g "$APP_GROUP" -m 0750 /etc/soaia

if [[ ! -x "$VENV/bin/python" ]]; then
  log "Creating Python virtual environment"
  python3 -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install --upgrade pip wheel
"$VENV/bin/pip" install \
  'fastapi>=0.115,<1' \
  'uvicorn[standard]>=0.30,<1' \
  'openai>=1,<3' \
  'pydantic-settings>=2,<3'

cat > /etc/soaia/soaia.env.example <<'ENV'
# Copy to /etc/soaia/soaia.env and chmod 0640 root:soaia.
# Never commit real values.
OPENAI_API_KEY=
SOAIA_BIND=127.0.0.1
SOAIA_PORT=8940
SOAIA_DB=/var/lib/soaia/soaia.db
SOAIA_OBSERVE_ONLY=true
SOAIA_REQUIRE_ANALYSIS_APPROVAL=true
SOAIA_REQUIRE_SEND_APPROVAL=true
SOAIA_OPENAI_STORE=false
ENV
chown root:"$APP_GROUP" /etc/soaia/soaia.env.example
chmod 0640 /etc/soaia/soaia.env.example

cat > "$APP_ROOT/app.py" <<'PY'
from fastapi import FastAPI

app = FastAPI(title="SOAiaCore API", version="0.1.0")

@app.get("/health/live")
def live():
    return {"status": "live"}

@app.get("/health/ready")
def ready():
    return {"status": "ready", "mode": "observe_only"}
PY
chown "$APP_USER:$APP_GROUP" "$APP_ROOT/app.py"
chmod 0640 "$APP_ROOT/app.py"

cat > /etc/systemd/system/soaia-api.service <<EOF
[Unit]
Description=SOAiaCore API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_GROUP
WorkingDirectory=$APP_ROOT
EnvironmentFile=-/etc/soaia/soaia.env
ExecStart=$VENV/bin/uvicorn app:app --host 127.0.0.1 --port 8940 --proxy-headers
Restart=on-failure
RestartSec=3
TimeoutStopSec=15
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$DATA_ROOT $LOG_ROOT
UMask=0027

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

if ss -ltn "sport = :8940" | tail -n +2 | grep -q .; then
  log "Port 8940 already in use; service created but NOT started."
else
  systemctl enable --now soaia-api.service
  sleep 2
  curl --fail --silent http://127.0.0.1:8940/health/live >/dev/null || die "soaia-api healthcheck failed"
  log "soaia-api healthcheck PASS"
fi

log "Configuring firewall without exposing internal application ports"
ufw allow OpenSSH >/dev/null 2>&1 || true
ufw allow 'Nginx Full' >/dev/null 2>&1 || true

log "Stage bootstrap complete. Existing Flask service was not disabled or modified."
log "Next gate: inspect receipt, configure secrets, validate DNS, then configure Nginx/TLS."
