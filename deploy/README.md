# BelegPilot — Production Deployment

Slim, self-contained deployment that runs behind the shared **ozkanceylan.dev
Caddy edge**. No Traefik, no shared external stacks — BelegPilot owns its own
network, volumes, and lifecycle.

## Architecture

```
        Internet
           │
           ▼
   Cloudflare DNS  (DNS-only, no proxy)
           │
           ▼
   ┌───────────────────────────────────────────────┐
   │  VPS  89.167.60.182                           │
   │                                                │
   │  ┌─────────────────────────────────────────┐  │
   │  │ website-caddy   (ozkanceylan.dev edge)  │  │
   │  │   ports: 80, 443                        │  │
   │  │   networks: website_web, belegpilot-edge│  │
   │  │   • ozkanceylan.dev      → website:3000 │  │
   │  │   • api.ozkanceylan.dev  → belegpilot-app:8000
   │  └────────────────┬────────────────────────┘  │
   │                   │ belegpilot-edge (external)│
   │  ┌────────────────▼────────────────────────┐  │
   │  │ belegpilot-app  (FastAPI, port 8000)    │  │
   │  │   networks: internal, belegpilot-edge   │  │
   │  └────────────────┬────────────────────────┘  │
   │                   │ internal (bridge)         │
   │  ┌────────────────▼────────────────────────┐  │
   │  │ belegpilot-db   (Postgres 16)           │  │
   │  │   volume: /data/belegpilot/pgdata       │  │
   │  └─────────────────────────────────────────┘  │
   └───────────────────────────────────────────────┘
```

Key properties:

- **`belegpilot-edge`** — external Docker network shared with `website-caddy`.
  Caddy can reach `belegpilot-app:8000` over it; nothing else can.
- **`internal`** — private bridge network for the app↔db link. The DB never
  touches the public-facing network.
- **TLS** — Caddy auto-obtains Let's Encrypt certs for `api.ozkanceylan.dev`
  once Cloudflare DNS resolves to the VPS.
- **Data lives on the host**: `/data/belegpilot/pgdata` for Postgres. Easy
  backups, no Docker volume juggling.
- **Phoenix is not deployed**. The app's OTLP exporter fails silently if no
  collector is reachable, so observability is optional.

## First-time setup (fresh VPS)

```bash
# 1. Clone repo to /opt/belegpilot (owned by deploy:docker)
sudo mkdir -p /opt/belegpilot
sudo chown deploy:docker /opt/belegpilot
git clone git@github.com:ozkannceylan/belegpilot.git /opt/belegpilot
cd /opt/belegpilot

# 2. Host preparation (root) — installs Docker if missing, creates /data dirs,
#    creates the shared belegpilot-edge network
sudo bash deploy/scripts/setup_server.sh

# 3. Generate strong random secrets into deploy/.env
bash deploy/scripts/create_env.sh
#    Edit deploy/.env and set OPENROUTER_API_KEY to a real key
$EDITOR deploy/.env

# 4. Bring the stack up
cd deploy
docker compose -f docker-compose.production.yml up -d

# 5. Wire ozkanceylan.dev's Caddy to belegpilot
#    On /opt/website/docker-compose.yml, the caddy service must include
#    belegpilot-edge in its networks list, and the file must declare:
#
#        networks:
#          belegpilot-edge:
#            external: true
#
#    On /opt/website/Caddyfile, add a host block:
#
#        api.ozkanceylan.dev {
#            reverse_proxy belegpilot-app:8000
#            ...
#        }
#
#    Then reload caddy live (no downtime if the network was already attached):
docker network connect belegpilot-edge website-caddy 2>/dev/null || true
docker compose -f /opt/website/docker-compose.yml restart caddy

# 6. Generate a production API key for callers
docker exec belegpilot-app python scripts/generate_api_key.py --name "production"
```

## Cloudflare DNS

Add these records in the **ozkanceylan.dev** zone (Cloudflare → DNS → Records):

| Type | Name  | Content                   | Proxy status         | TTL  |
|------|-------|---------------------------|----------------------|------|
| A    | `api` | `89.167.60.182`           | **DNS only** (grey)  | Auto |
| AAAA | `api` | `2a01:4f9:c014:d8dc::1`   | **DNS only** (grey)  | Auto |

Use **DNS only** (grey cloud), not proxied. Caddy obtains its own Let's Encrypt
certificate via HTTP-01 challenge directly against the origin — this is the same
pattern the rest of this VPS already uses.

Once the records resolve, Caddy will fetch the cert automatically (watch
`docker logs website-caddy` for `obtained certificate` messages). No further
Cloudflare config (SSL mode, page rules) is needed.

## Day-2 operations

### Update to a new image version

```bash
cd /opt/belegpilot/deploy
docker compose -f docker-compose.production.yml pull app
docker compose -f docker-compose.production.yml up -d
```

CI pushes `ghcr.io/ozkannceylan/belegpilot:latest` on every merge to `main`.

### Tail logs

```bash
docker logs -f belegpilot-app
docker logs -f belegpilot-db
```

### Restart only the app (e.g. after editing `.env`)

```bash
cd /opt/belegpilot/deploy
docker compose -f docker-compose.production.yml restart app
```

### Backup the database

```bash
docker exec belegpilot-db pg_dump -U belegpilot belegpilot \
    | gzip > /data/backups/belegpilot-$(date +%F).sql.gz
```

### Verify Caddy is wired up

```bash
docker exec website-caddy wget -q -O - http://belegpilot-app:8000/health
# expected: {"status":"healthy","service":"BelegPilot","version":"..."}
```

## Files in this directory

| Path                            | Purpose                                              |
|---------------------------------|------------------------------------------------------|
| `docker-compose.production.yml` | Two-service stack (app + db) on the edge network     |
| `.env.production.example`       | Template for `deploy/.env`                           |
| `scripts/setup_server.sh`       | Idempotent host prep (Docker, /data dirs, edge net)  |
| `scripts/create_env.sh`         | Generates `deploy/.env` with random strong secrets   |

## Why this layout

BelegPilot used to be deployed inside the `ozvatan-network` stack via a Traefik
sidecar at `api.ozvatanyapi.com`. That coupling has been removed: BelegPilot
is now a first-class citizen under the ozkanceylan.dev infrastructure and has
no runtime dependency on the ozvatanyapi stack. If ozvatanyapi is taken down,
BelegPilot keeps running, and vice versa.
