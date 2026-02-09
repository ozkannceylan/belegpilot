"""Prometheus metrics for monitoring."""

from fastapi import APIRouter
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

# Counters
EXTRACTION_TOTAL = Counter(
    "belegpilot_extractions_total",
    "Total extraction requests",
    ["status", "method"],  # status=success/partial/failed, method=vlm/ocr/hybrid
)
EXTRACTION_ERRORS = Counter(
    "belegpilot_extraction_errors_total",
    "Total extraction errors",
    ["error_type"],
)
LLM_TOKENS = Counter(
    "belegpilot_llm_tokens_total",
    "Total LLM tokens used",
    ["model", "direction"],  # direction=input/output
)
LLM_COST = Counter(
    "belegpilot_llm_cost_usd_total",
    "Total LLM cost in USD",
    ["model"],
)

# Histograms
EXTRACTION_DURATION = Histogram(
    "belegpilot_extraction_duration_seconds",
    "Extraction processing time",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)
CONFIDENCE_SCORE = Histogram(
    "belegpilot_confidence_score",
    "Extraction confidence scores",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# Gauges
DAILY_SPEND = Gauge(
    "belegpilot_daily_spend_usd",
    "Current daily OpenRouter spend in USD",
)

# Metrics endpoint
metrics_router = APIRouter()


@metrics_router.get("/metrics")
async def metrics() -> Response:
    """Return Prometheus metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
