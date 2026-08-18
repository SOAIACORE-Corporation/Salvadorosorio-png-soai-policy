# SOAiaCore · Deployment Runbook

## Golden rule
No ejecutar bloques pegados desde transcripts. Ejecutar únicamente archivos versionados desde Git.

## Stage 0 · clone/update

```bash
git clone https://github.com/SOAIACORE-Corporation/Salvadorosorio-png-soai-policy.git
cd Salvadorosorio-png-soai-policy
git fetch --all --prune
git checkout soaia/as-is-hardening-2026-08-17
```

## Stage 1 · PRECHECK (read-mostly)

```bash
chmod +x deploy/precheck.sh deploy/receipt.sh deploy/bootstrap_stage.sh
sudo ./deploy/precheck.sh | tee PRECHECK.txt
```

Do not continue if:
- OS is not Ubuntu 24.04;
- unexpected listeners exist on 8940;
- filesystem/memory is critically constrained;
- DNS results contradict intended routing;
- Nginx config exists but `nginx -t` fails.

## Stage 2 · non-destructive bootstrap

```bash
sudo ./deploy/bootstrap_stage.sh
```

This stage:
- creates `soaia` service identity;
- creates `/opt/soaia`, `/var/lib/soaia`, `/var/log/soaia`, `/etc/soaia`;
- creates a Python venv;
- installs minimal FastAPI/OpenAI runtime inside the venv;
- creates `soaia-api.service` on `127.0.0.1:8940`;
- does NOT stop or delete historical Flask;
- does NOT issue TLS certificates;
- does NOT place secrets in Git.

## Stage 3 · secret setup

Use the secure OpenAI Platform key flow. Store the resulting key only on the server in `/etc/soaia/soaia.env` with:

```bash
sudo install -o root -g soaia -m 0640 /dev/null /etc/soaia/soaia.env
sudoedit /etc/soaia/soaia.env
sudo systemctl restart soaia-api
```

Never paste API keys into tickets, GitHub, chat transcripts, URLs, screenshots, frontend JavaScript, or Nginx config.

## Stage 4 · receipt

```bash
sudo ./deploy/receipt.sh /var/lib/soaia/receipts
```

Review the receipt before any migration of traffic.

## Stage 5 · DNS/Nginx/TLS gate

Only after receipt PASS:
1. confirm `soaia.mx`/subdomain DNS points to intended host;
2. configure Nginx HTTP proxy to `127.0.0.1:8940`;
3. validate `nginx -t`;
4. test HTTP health externally;
5. request certificate with Certbot;
6. validate HTTPS and redirect;
7. retain rollback config.

## Stage 6 · messaging bridges

Not included in bootstrap. Build separately behind `OBSERVE_ONLY=true` and approval gates. Node.js 24 LTS is the target runtime for new Node bridges.

## State vocabulary

- PROPOSED: written only.
- CREATED: persisted in Git/Drive.
- EXECUTED: ran on target host.
- VERIFIED: health/receipt evidence exists.
- FAILED: execution attempted and failed.
- ROLLED_BACK: reverted and verified.
