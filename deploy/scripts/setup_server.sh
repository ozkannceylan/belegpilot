#!/bin/bash
set -euo pipefail

echo "=== BelegPilot Server Setup ==="

# Update system
apt-get update && apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# Install Docker Compose plugin
apt-get install -y docker-compose-plugin

# Create app directory
mkdir -p /opt/BelegPilot/caddy
cd /opt/BelegPilot

# Create .env file (fill in manually after)
cat > .env.example << 'EOF'
OPENROUTER_API_KEY=sk-or-v1-xxxx
DB_PASSWORD=<generate-strong-password>
SECRET_KEY=<generate-with: openssl rand -hex 32>
OPENROUTER_MONTHLY_BUDGET_USD=5.0
OPENROUTER_DAILY_BUDGET_USD=1.0
ENVIRONMENT=production
LOG_LEVEL=INFO
API_KEY_ADMIN_SECRET=<generate-strong-secret>
DB_HOST=db
DB_PORT=5432
DB_NAME=belegpilot
DB_USER=belegpilot
PHOENIX_COLLECTOR_ENDPOINT=http://phoenix:4317
OTEL_SERVICE_NAME=belegpilot
ALLOWED_ORIGINS=https://api.ozvatanyapi.com
EOF

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "1. cp .env.example .env && nano .env  (fill in real values)"
echo "2. Copy docker-compose.production.yml and Caddyfile"
echo "3. docker compose -f docker-compose.production.yml up -d"
echo "4. docker compose exec app python scripts/generate_api_key.py --name 'production'"
