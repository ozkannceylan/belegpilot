# BelegPilot

Intelligent receipt and invoice data extraction API powered by Vision Language Models with OCR fallback.

Upload a receipt image → get structured JSON with vendor, date, total, line items, tax, and category.

## Live Demo

**Demo:** [BelegPilot.ozkannceylan.dev/demo](https://BelegPilot.ozkannceylan.dev/demo)

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
    "https://BelegPilot.ozkannceylan.dev/api/v1/extract",
    headers={"X-API-Key": "riq_live_<your-key>"},
    files={"file": open("receipt.jpg", "rb")},
)
print(response.json())
```

## Architecture

```
Client → FastAPI → Image Preprocessing (OpenCV)
                 → VLM Extraction (OpenRouter: Qwen2-VL / GPT-4o-mini)
                 → OCR Fallback (Tesseract) [if VLM fails/low confidence]
                 → Validation & Confidence Scoring
                 → PostgreSQL (results storage)
                 → Phoenix (LLM tracing via OpenTelemetry)
```

## Key Features

- **VLM + OCR Hybrid:** Primary extraction via Vision LLM, automatic OCR fallback
- **Cost Control:** Hard daily/monthly budget limits on OpenRouter spend, automatic model downgrade
- **API Key Auth:** bcrypt-hashed keys, rate limiting
- **Full Observability:** OpenTelemetry traces in Phoenix, Prometheus metrics, structured logging
- **Golden Dataset Evaluation:** Automated accuracy testing in CI

## Tech Stack

FastAPI · Python 3.12 · OpenRouter · Qwen2-VL · Tesseract · OpenCV · PostgreSQL · Phoenix · OpenTelemetry · Docker · Caddy · GitHub Actions · Hetzner Cloud

## Development

```bash
# Run tests
docker compose -f docker/docker-compose.yml exec app pytest -v

# Check OpenRouter spend
docker compose -f docker/docker-compose.yml exec app python scripts/check_cost.py

# Lint
ruff check app/ tests/
```

## License

MIT
