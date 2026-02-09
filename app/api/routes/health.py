"""Health check endpoint."""

from fastapi import APIRouter

from app.services.openrouter import AVAILABLE_MODELS

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "BelegPilot", "version": "0.1.0"}


@router.get("/models")
async def list_models() -> dict:
    """List available VLM models for extraction."""
    return {"models": AVAILABLE_MODELS}
