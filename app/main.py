"""FastAPI application factory and configuration."""

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import extract, health, results
from app.config import settings
from app.models.database import init_db
from app.observability.metrics import metrics_router


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID to each request."""

    async def dispatch(self, request, call_next):
        request_id = str(uuid.uuid4())[:8]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    from app.observability.logging import setup_logging
    from app.observability.tracing import setup_tracing

    setup_logging(settings.log_level, settings.environment)
    setup_tracing(settings.otel_service_name, settings.phoenix_collector_endpoint, app)

    logger = structlog.get_logger()
    logger.info("Starting BelegPilot", environment=settings.environment)
    await init_db()
    logger.info("Database initialized")
    yield
    # Cleanup: close OpenRouter client
    from app.api.routes.extract import pipeline
    await pipeline.close()
    logger.info("Shutting down BelegPilot")


app = FastAPI(
    title="BelegPilot",
    description="Intelligent receipt & invoice data extraction API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Request ID middleware
app.add_middleware(RequestIDMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router, tags=["Health"])
app.include_router(extract.router, prefix="/api/v1", tags=["Extraction"])
app.include_router(results.router, prefix="/api/v1", tags=["Results"])
app.include_router(metrics_router, tags=["Metrics"])

# Static files for demo UI
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/demo")
async def demo_page():
    """Serve the demo HTML page."""
    return FileResponse(str(static_dir / "demo.html"))
