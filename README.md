# BelegPilot

**Production-grade receipt & invoice data extraction API** powered by Vision Language Models with intelligent OCR fallback.

Upload a receipt image → get structured JSON with vendor, date, total, line items, tax breakdown, and expense category.

[![CI/CD](https://github.com/ozkannceylan/belegpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/ozkannceylan/belegpilot/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Live Demo

**API:** [api.ozvatanyapi.com](https://api.ozvatanyapi.com/docs)  
**Demo UI:** [api.ozvatanyapi.com/demo](https://api.ozvatanyapi.com/demo)

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/ozkannceylan/BelegPilot.git
cd BelegPilot
cp .env.example .env
# Edit .env with your OpenRouter API key

# 2. Start services
docker compose -f docker/docker-compose.yml up --build

# 3. Generate API key
docker compose -f docker/docker-compose.yml exec app python scripts/generate_api_key.py --name "dev"
# Save the key that's printed!

# 4. Extract a receipt
curl -X POST http://localhost:8000/api/v1/extract \
  -H "X-API-Key: riq_live_<your-key>" \
  -F "file=@receipt.jpg"
```

## API

### `POST /api/v1/extract`

Upload a receipt/invoice image and get structured data back.

**Headers:** `X-API-Key: riq_live_<your-key>`

**Body:** Multipart form with `file` (JPEG, PNG, or PDF, max 10MB)

**Response:**
```json
{
  "id": "uuid",
  "status": "success",
  "data": {
    "vendor": "REWE",
    "date": "2026-02-07",
    "total_amount": 47.83,
    "currency": "EUR",
    "tax_amount": 7.63,
    "tax_rate": 19.0,
    "line_items": [...],
    "payment_method": "Visa ****1234",
    "category": "groceries"
  },
  "confidence_score": 0.94,
  "extraction_method": "vlm",
  "processing_time_ms": 3500,
  "cost_usd": 0.002
}
```

### `GET /api/v1/results/{id}`

Retrieve a previous extraction result.

### `GET /health`

Health check (no auth required).

### `GET /docs`

Interactive API documentation (Swagger UI).

## Python Client

```python
import httpx

response = httpx.post(
    "https://api.ozvatanyapi.com/api/v1/extract",
    headers={"X-API-Key": "riq_live_<your-key>"},
    files={"file": open("receipt.jpg", "rb")},
)
print(response.json())
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BelegPilot API                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌──────────────────────────────────────────────────┐    │
│  │   Client    │───▶│              FastAPI (ASGI)                       │    │
│  │  (REST API) │    │  • API Key Authentication                        │    │
│  └─────────────┘    │  • Request Validation (Pydantic)                 │    │
│                     │  • Rate Limiting                                  │    │
│                     └──────────────────┬───────────────────────────────┘    │
│                                        │                                     │
│                     ┌──────────────────▼───────────────────────────────┐    │
│                     │           Image Preprocessor                      │    │
│                     │  • Auto-rotation (EXIF)                          │    │
│                     │  • Contrast enhancement (OpenCV)                 │    │
│                     │  • Noise reduction                               │    │
│                     │  • Resolution optimization                       │    │
│                     └──────────────────┬───────────────────────────────┘    │
│                                        │                                     │
│              ┌─────────────────────────┼─────────────────────────────┐      │
│              │                         │                             │      │
│              ▼                         ▼                             ▼      │
│  ┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐     │
│  │   VLM Extractor   │   │   OCR Extractor   │   │    Validator      │     │
│  │  (Primary Path)   │   │  (Fallback Path)  │   │ & Categorizer     │     │
│  ├───────────────────┤   ├───────────────────┤   ├───────────────────┤     │
│  │ • Qwen2.5-VL-72B  │   │ • Tesseract OCR   │   │ • Field scoring   │     │
│  │ • GPT-4o-mini     │   │ • DE/EN langs     │   │ • Confidence calc │     │
│  │ • OpenRouter API  │   │ • Regex parsing   │   │ • Auto-categorize │     │
│  │ • Cost tracking   │   │                   │   │ • Tax validation  │     │
│  └───────────────────┘   └───────────────────┘   └───────────────────┘     │
│                                        │                                     │
│                     ┌──────────────────▼───────────────────────────────┐    │
│                     │              Data Layer                           │    │
│                     │  • PostgreSQL 16 (async via asyncpg)             │    │
│                     │  • SQLAlchemy 2.0 ORM                            │    │
│                     │  • Result persistence & retrieval                │    │
│                     └──────────────────────────────────────────────────┘    │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                           Observability Stack                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │   Phoenix UI    │  │   Prometheus    │  │    Structlog    │              │
│  │  (LLM Traces)   │  │   (Metrics)     │  │  (JSON Logs)    │              │
│  │ OpenTelemetry   │  │ /metrics        │  │ Request IDs     │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘

                              Infrastructure
┌─────────────────────────────────────────────────────────────────────────────┐
│  Cloudflare (DNS/CDN/SSL) → Traefik (Reverse Proxy) → Docker Containers     │
│                                                                              │
│  CI/CD: GitHub Actions → GHCR → Auto-deploy to Hetzner Cloud                │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Key Features

### 🤖 Hybrid AI Extraction
- **Vision Language Model primary path** using state-of-the-art Qwen2.5-VL-72B via OpenRouter
- **Intelligent OCR fallback** with Tesseract when VLM fails or returns low confidence
- **Automatic model failover** from premium to cost-effective models based on budget

### 💰 Cost Management
- **Hard budget limits** - configurable daily/monthly caps on OpenRouter API spend
- **Real-time cost tracking** - per-request cost calculation and logging
- **Automatic model downgrade** when approaching budget limits

### 🔒 Security
- **API key authentication** with bcrypt hashing (no plaintext storage)
- **Rate limiting** per API key
- **Input validation** with Pydantic v2 schemas
- **Non-root container** execution

### 📊 Full Observability
- **Distributed tracing** via OpenTelemetry to Arize Phoenix
- **Prometheus metrics** at `/metrics` endpoint
- **Structured JSON logging** with request correlation IDs
- **LLM call tracing** with token counts and latency

### 🧪 Quality Assurance
- **56+ automated tests** with pytest-asyncio
- **74% code coverage** with pytest-cov
- **Golden dataset evaluation** for accuracy regression testing
- **Type checking** with mypy strict mode
- **Linting** with Ruff (fast Python linter)

### 🚀 Production-Ready
- **Multi-stage Docker builds** for minimal image size
- **Health checks** with dependency verification
- **Graceful degradation** when external services fail
- **Async throughout** - non-blocking I/O with asyncio

## Tech Stack

### Backend & API
| Technology | Purpose |
|------------|---------|
| **Python 3.12** | Core language with modern type hints |
| **FastAPI** | High-performance async REST API framework |
| **Pydantic v2** | Data validation & serialization |
| **Uvicorn** | ASGI server with HTTP/2 support |
| **SQLAlchemy 2.0** | Async ORM with type-safe queries |
| **asyncpg** | High-performance PostgreSQL async driver |

### AI/ML & Computer Vision
| Technology | Purpose |
|------------|---------|
| **OpenRouter API** | LLM gateway for vision models |
| **Qwen2.5-VL-72B** | Primary Vision Language Model for extraction |
| **GPT-4o-mini** | Fallback VLM with cost optimization |
| **Tesseract OCR** | Open-source OCR engine (German + English) |
| **OpenCV** | Image preprocessing & enhancement |
| **Pillow** | Image format handling |

### Observability & Monitoring
| Technology | Purpose |
|------------|---------|
| **OpenTelemetry** | Distributed tracing instrumentation |
| **Arize Phoenix** | LLM observability & trace visualization |
| **Prometheus** | Metrics collection & alerting |
| **Structlog** | Structured JSON logging |

### Security & Authentication
| Technology | Purpose |
|------------|---------|
| **bcrypt** | Password & API key hashing |
| **python-jose** | JWT token handling |
| **API Key Auth** | Request authentication via X-API-Key header |

### Infrastructure & DevOps
| Technology | Purpose |
|------------|---------|
| **Docker** | Multi-stage containerization |
| **Docker Compose** | Multi-service orchestration |
| **PostgreSQL 16** | Primary datastore with health checks |
| **Traefik v2** | Reverse proxy with automatic TLS |
| **Caddy** | Alternative reverse proxy option |
| **Hetzner Cloud** | Production hosting |
| **Cloudflare** | DNS, CDN & SSL termination |

### CI/CD & Quality
| Technology | Purpose |
|------------|---------|
| **GitHub Actions** | Automated CI/CD pipeline |
| **GHCR** | GitHub Container Registry for images |
| **pytest** | Async test framework with fixtures |
| **pytest-cov** | Code coverage reporting |
| **Ruff** | Fast Python linter & formatter |
| **mypy** | Static type checking |

### Additional Libraries
| Technology | Purpose |
|------------|---------|
| **httpx** | Async HTTP client with retry support |
| **tenacity** | Retry logic with exponential backoff |
| **python-multipart** | Multipart file upload handling |

## Project Highlights

This project demonstrates proficiency in:

- **Backend Engineering**: Async Python, RESTful API design, dependency injection, middleware patterns
- **AI/ML Integration**: Vision Language Models, prompt engineering, multi-model orchestration, cost optimization
- **Database Design**: Async ORMs, connection pooling, migration strategies, query optimization
- **DevOps & Infrastructure**: Docker multi-stage builds, container orchestration, reverse proxies, cloud deployment
- **Observability**: Distributed tracing, metrics collection, structured logging, LLM monitoring
- **Security**: Authentication schemes, secret management, input validation, secure defaults
- **Testing**: Async test patterns, fixtures, mocking external services, coverage analysis
- **CI/CD**: GitHub Actions workflows, container registries, automated deployments

## Development

```bash
# Run tests with coverage
docker compose -f docker/docker-compose.yml exec app pytest -v --cov=app --cov-report=term-missing

# Type checking
mypy app/ --ignore-missing-imports

# Linting & formatting
ruff check app/ tests/
ruff format app/ tests/

# Check OpenRouter spend
docker compose -f docker/docker-compose.yml exec app python scripts/check_cost.py

# Generate new API key
docker compose -f docker/docker-compose.yml exec app python scripts/generate_api_key.py --name "my-key"
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API key (required) | - |
| `OPENROUTER_DEFAULT_MODEL` | Primary VLM model | `qwen/qwen2.5-vl-72b-instruct` |
| `OPENROUTER_FALLBACK_MODEL` | Fallback VLM model | `openai/gpt-4o-mini` |
| `OPENROUTER_DAILY_BUDGET_USD` | Daily spend limit | `1.0` |
| `OPENROUTER_MONTHLY_BUDGET_USD` | Monthly spend limit | `5.0` |
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PASSWORD` | Database password | - |
| `ENVIRONMENT` | `development` / `production` | `development` |

## License

MIT
