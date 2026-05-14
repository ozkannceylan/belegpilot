#!/bin/bash
# Generate deploy/.env with strong secrets.
# Run from repo root:  bash deploy/scripts/create_env.sh
#
# After running, edit deploy/.env and set OPENROUTER_API_KEY before bringing
# the stack up.

set -euo pipefail

ENV_FILE="$(dirname "$0")/../.env"

if [[ -f "$ENV_FILE" ]]; then
    echo "deploy/.env already exists — aborting to avoid overwrite." >&2
    exit 1
fi

SK=$(openssl rand -hex 32)
DP=$(openssl rand -hex 16)
AS=$(openssl rand -hex 16)

cat > "$ENV_FILE" << EOF
# === REQUIRED ===
OPENROUTER_API_KEY=PLACEHOLDER_FILL_THIS
DB_PASSWORD=${DP}
SECRET_KEY=${SK}
API_KEY_ADMIN_SECRET=${AS}

# === OPENROUTER ===
OPENROUTER_DEFAULT_MODEL=qwen/qwen2.5-vl-72b-instruct
OPENROUTER_FALLBACK_MODEL=openai/gpt-4o-mini
OPENROUTER_MONTHLY_BUDGET_USD=5.0
OPENROUTER_DAILY_BUDGET_USD=1.0

# === DATABASE ===
DB_HOST=db
DB_PORT=5432
DB_NAME=belegpilot
DB_USER=belegpilot

# === OBSERVABILITY ===
PHOENIX_COLLECTOR_ENDPOINT=http://phoenix:4317
OTEL_SERVICE_NAME=belegpilot
LOG_LEVEL=INFO

# === APP ===
ENVIRONMENT=production
ALLOWED_ORIGINS=https://api.ozkanceylan.dev
EOF

chmod 600 "$ENV_FILE"
echo "deploy/.env created with generated secrets."
echo "Edit it now and set OPENROUTER_API_KEY before deploying:"
echo "  nano $ENV_FILE"
