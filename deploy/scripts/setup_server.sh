#!/bin/bash
# One-shot host preparation for a fresh VPS that will run BelegPilot
# as a standalone stack behind ozkanceylan.dev's central Caddy.
#
# Idempotent — safe to re-run.

set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
    echo "Run as root (or with sudo)." >&2
    exit 1
fi

echo "==> Installing Docker (if missing)"
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
fi

echo "==> Creating host data dirs under /data/belegpilot"
mkdir -p /data/belegpilot/pgdata /data/belegpilot/phoenix
chown -R 70:70 /data/belegpilot/pgdata     # postgres image uid
chown -R 1000:1000 /data/belegpilot/phoenix

echo "==> Ensuring shared edge network exists"
docker network inspect belegpilot-edge >/dev/null 2>&1 \
    || docker network create belegpilot-edge

echo ""
echo "Host prepared. Next steps (as deploy user):"
echo "  1. bash deploy/scripts/create_env.sh    # creates deploy/.env with random secrets"
echo "  2. edit deploy/.env and set OPENROUTER_API_KEY"
echo "  3. docker compose -f deploy/docker-compose.production.yml --env-file deploy/.env up -d"
echo "  4. Attach website-caddy to belegpilot-edge and add api.ozkanceylan.dev block"
echo "     (see deploy/README.md)"
