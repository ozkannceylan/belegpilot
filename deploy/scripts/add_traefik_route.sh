#!/bin/bash
set -euo pipefail

# Add BelegPilot route to Traefik dynamic config
cat > /opt/ozvatan/traefik/dynamic/belegpilot.yml << 'EOF'
# BelegPilot API - Receipt/Invoice Extraction
http:
  routers:
    belegpilot:
      rule: "Host(`api.ozvatanyapi.com`)"
      entryPoints:
        - web
      service: belegpilot
      priority: 100

  services:
    belegpilot:
      loadBalancer:
        servers:
          - url: "http://belegpilot-app:8000"
EOF

echo "Traefik route added for api.ozvatanyapi.com"
cat /opt/ozvatan/traefik/dynamic/belegpilot.yml
