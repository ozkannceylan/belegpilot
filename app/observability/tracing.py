"""OpenTelemetry instrumentation with Phoenix as the trace backend."""

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup_tracing(service_name: str, phoenix_endpoint: str, app=None) -> None:
    """Initialize OpenTelemetry with Phoenix backend.

    Args:
        service_name: Name of the service for resource identification
        phoenix_endpoint: OTLP gRPC endpoint URL
        app: FastAPI app instance (optional)
    """
    try:
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        exporter = OTLPSpanExporter(endpoint=phoenix_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)

        if app:
            FastAPIInstrumentor.instrument_app(app)
    except Exception:
        # Don't crash the app if tracing setup fails (e.g. Phoenix not available)
        import structlog
        logger = structlog.get_logger()
        logger.warning("Failed to setup tracing, continuing without it")


def get_tracer(name: str = "BelegPilot") -> trace.Tracer:
    """Get a tracer instance.

    Args:
        name: Tracer name

    Returns:
        OpenTelemetry tracer
    """
    return trace.get_tracer(name)
