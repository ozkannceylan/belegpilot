"""API key generation, hashing, and verification service."""

import uuid
from datetime import UTC, datetime

import bcrypt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import APIKey

KEY_PREFIX = "riq_live_"


def generate_api_key() -> str:
    """Generate a new API key. Returns the full plaintext key."""
    random_part = uuid.uuid4().hex
    return f"{KEY_PREFIX}{random_part}"


def hash_api_key(key: str) -> str:
    """Hash an API key with bcrypt for storage."""
    return bcrypt.hashpw(key.encode(), bcrypt.gensalt()).decode()


def verify_api_key(key: str, key_hash: str) -> bool:
    """Verify a plaintext key against its bcrypt hash."""
    return bcrypt.checkpw(key.encode(), key_hash.encode())


def get_key_prefix(key: str) -> str:
    """Extract identifiable prefix from key (for logging, not auth)."""
    # riq_live_a1b2c3d4... → riq_live_a1b2c3d4...
    return key[:20] + "..."


async def create_api_key(
    session: AsyncSession,
    name: str,
    description: str | None = None,
) -> tuple[str, APIKey]:
    """Create a new API key. Returns (plaintext_key, db_record)."""
    plaintext_key = generate_api_key()
    key_hash = hash_api_key(plaintext_key)
    prefix = get_key_prefix(plaintext_key)

    db_key = APIKey(
        name=name,
        description=description,
        key_hash=key_hash,
        key_prefix=prefix,
        is_active=True,
    )
    session.add(db_key)
    await session.commit()
    await session.refresh(db_key)

    return plaintext_key, db_key


async def validate_api_key(session: AsyncSession, key: str) -> APIKey | None:
    """Validate an API key and return the DB record if valid.

    Performance note: With few keys (<100), fetching all active keys and
    checking bcrypt is fine. For thousands of keys, add a key_prefix index
    and filter first.
    """
    if not key.startswith(KEY_PREFIX):
        return None

    result = await session.execute(
        select(APIKey).where(APIKey.is_active == True)  # noqa: E712
    )
    active_keys = result.scalars().all()

    for db_key in active_keys:
        if verify_api_key(key, db_key.key_hash):
            # Update last_used_at and request count
            await session.execute(
                update(APIKey)
                .where(APIKey.id == db_key.id)
                .values(
                    last_used_at=datetime.now(UTC),
                    total_requests=APIKey.total_requests + 1,
                )
            )
            await session.commit()
            return db_key

    return None
