#!/bin/bash
set -euo pipefail

cd /opt/belegpilot

SK=$(openssl rand -hex 32)
DP=$(openssl rand -hex 16)
AS=$(openssl rand -hex 16)

cat > .env << EOF
OPENROUTER_API_KEY=PLACEHOLDER_FILL_THIS
DB_PASSWORD=${DP}
SECRET_KEY=${SK}
API_KEY_ADMIN_SECRET=${AS}
OPENROUTER_DEFAULT_MODEL=qwen/qwen2.5-vl-72b-instruct
OPENROUTER_FALLBACK_MODEL=openai/gpt-4o-mini
OPENROUTER_MONTHLY_BUDGET_USD=5.0
OPENROUTER_DAILY_BUDGET_USD=1.0
DB_HOST=db
DB_PORT=5432
DB_NAME=belegpilot
DB_USER=belegpilot
PHOENIX_COLLECTOR_ENDPOINT=http://phoenix:4317
OTEL_SERVICE_NAME=belegpilot
LOG_LEVEL=INFO
ENVIRONMENT=production
ALLOWED_ORIGINS=https://api.ozvatanyapi.com
EOF

echo "=== .env created ==="
cat .env
