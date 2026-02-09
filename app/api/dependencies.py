"""FastAPI dependencies for auth and database sessions."""

import time
from collections import defaultdict
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import APIKey, get_session
from app.services.auth import validate_api_key

# API key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Simple in-memory rate limiter (sufficient for single-server demo)
# For production: use Redis
_request_counts: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_REQUESTS = 30  # per minute
RATE_LIMIT_WINDOW = 60  # seconds


async def get_db() -> AsyncSession:
    """Database session dependency."""
    async for session in get_session():
        yield session


async def verify_api_key(
    api_key: Annotated[str | None, Security(api_key_header)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> APIKey:
    """Verify API key from X-API-Key header. Returns the APIKey record."""
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header.",
        )

    db_key = await validate_api_key(db, api_key)
    if db_key is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or inactive API key.",
        )

    return db_key


async def check_rate_limit(api_key: APIKey) -> None:
    """Simple sliding window rate limiter per API key."""
    now = time.time()
    key_id = str(api_key.id)

    # Remove old entries
    _request_counts[key_id] = [
        t for t in _request_counts[key_id] if now - t < RATE_LIMIT_WINDOW
    ]

    if len(_request_counts[key_id]) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_REQUESTS} requests per minute.",
        )

    _request_counts[key_id].append(now)


# Type aliases for cleaner route signatures
DB = Annotated[AsyncSession, Depends(get_db)]
AuthenticatedKey = Annotated[APIKey, Depends(verify_api_key)]
