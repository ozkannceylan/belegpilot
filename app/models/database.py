"""SQLAlchemy async models for PostgreSQL."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class ExtractionRecord(Base):
    """Stored extraction results."""
    __tablename__ = "extraction_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String(20), nullable=False, default="success")
    vendor = Column(String(255))
    receipt_date = Column(DateTime(timezone=True))
    total_amount = Column(Float)
    currency = Column(String(3))
    tax_amount = Column(Float)
    tax_rate = Column(Float)
    line_items = Column(JSON, default=list)
    payment_method = Column(String(100))
    receipt_number = Column(String(100))
    category = Column(String(50), default="other")
    confidence_score = Column(Float, nullable=False)
    extraction_method = Column(String(20), nullable=False)
    model_used = Column(String(100))
    processing_time_ms = Column(Integer, nullable=False)
    cost_usd = Column(Float, default=0.0)
    raw_vlm_response = Column(Text)  # Store raw LLM output for debugging
    api_key_prefix = Column(String(30))  # Which API key was used
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class APIKey(Base):
    """API keys for authentication."""
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    key_hash = Column(String(255), nullable=False, unique=True)
    key_prefix = Column(String(30), nullable=False)  # For identification in logs
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    last_used_at = Column(DateTime(timezone=True))
    total_requests = Column(Integer, default=0)


class CostTracker(Base):
    """Track OpenRouter API costs per day."""
    __tablename__ = "cost_tracker"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(DateTime(timezone=True), nullable=False)  # Date of the cost entry
    model = Column(String(100), nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    request_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


# Engine and session factory
engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_size=5,
    max_overflow=10,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting a DB session."""
    async with async_session() as session:
        yield session
