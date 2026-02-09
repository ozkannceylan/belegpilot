"""Shared fixtures for all tests."""

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.dependencies import get_db, verify_api_key
from app.main import app
from app.models.database import APIKey, Base

# Use in-memory SQLite for tests
TEST_DB_URL = "sqlite+aiosqlite:///test.db"


@pytest.fixture
async def test_db():
    """Create fresh test database for each test."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def mock_api_key():
    """Mock authenticated API key."""
    key = MagicMock(spec=APIKey)
    key.id = "test-key-id"
    key.name = "test-key"
    key.key_prefix = "riq_live_test1234..."
    key.is_active = True
    return key


@pytest.fixture
async def client(test_db, mock_api_key):
    """FastAPI test client with mocked auth and DB."""
    async def override_get_db():
        yield test_db

    async def override_verify_api_key():
        return mock_api_key

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_api_key] = override_verify_api_key

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sample_receipt_bytes():
    """Minimal JPEG bytes for testing."""
    # 1x1 white pixel JPEG
    import io

    from PIL import Image
    img = Image.new("RGB", (100, 50), "white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def mock_vlm_response():
    """Mock successful VLM extraction response."""
    return {
        "vendor": "REWE",
        "date": "2026-02-07",
        "total_amount": 47.83,
        "currency": "EUR",
        "tax_amount": 7.63,
        "tax_rate": 19.0,
        "line_items": [
            {"description": "Bio Vollmilch", "quantity": 2, "unit_price": 1.29, "total": 2.58},
            {"description": "Olivenoel", "quantity": 1, "unit_price": 5.99, "total": 5.99},
        ],
        "payment_method": "Visa ****1234",
        "receipt_number": "R-2026-0207-001",
    }
