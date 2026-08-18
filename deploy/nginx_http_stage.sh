#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

DOMAIN="${SOAIA_DOMAIN:-soaia.mx}"
EXPECTED_IP="${SOAIA_EXPECTED_PUBLIC_IP:-}"
CONF="/etc/nginx/sites-available/${DOMAIN}"
ENABLED="/etc/nginx/sites-enabled/${DOMAIN}"
BACKUP_DIR="/etc/nginx/soaia-backups"

fail(){ printf 'FAIL %s\n' "$*" >&2; exit 1; }
pass(){ printf 'PASS %s\n' "$*"; }

[[ ${EUID:-$(id -u)} -eq 0 ]] || fail "Run as root."
command -v nginx >/dev/null 2>&1 || fail "nginx is not installed."
command -v curl >/dev/null 2>&1 || fail "curl is required."
[[ -n "$EXPECTED_IP" ]] || fail "Set SOAIA_EXPECTED_PUBLIC_IP explicitly."

curl -fsS --max-time 5 http://127.0.0.1:8940/health/live >/dev/null || fail "SOAia API is not healthy on 127.0.0.1:8940."

resolved="$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}' || true)"
[[ -n "$resolved" ]] || fail "$DOMAIN does not resolve."
[[ "$resolved" == "$EXPECTED_IP" ]] || fail "$DOMAIN resolves to $resolved, expected $EXPECTED_IP."

install -d -m 0750 "$BACKUP_DIR"
if [[ -f "$CONF" ]]; then
  cp -a "$CONF" "$BACKUP_DIR/${DOMAIN}.$(date -u +%Y%m%dT%H%M%SZ).bak"
fi

cat > "$CONF" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:8940;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 5s;
        proxy_read_timeout 60s;
    }
}
EOF

ln -sfn "$CONF" "$ENABLED"
nginx -t || fail "nginx configuration test failed; inspect backup before reload."
systemctl reload nginx
pass "HTTP reverse proxy staged for $DOMAIN"
printf 'NEXT_GATE=external HTTP validation before Certbot/TLS\n'
