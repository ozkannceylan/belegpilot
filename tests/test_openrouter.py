"""OpenRouter client tests with mocked httpx."""

from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from app.services.openrouter import BudgetExceededError, OpenRouterClient


@pytest.fixture
def openrouter():
    """Create OpenRouter client."""
    return OpenRouterClient()


@pytest.mark.asyncio
async def test_select_model_default(openrouter, test_db):
    """Under budget returns default model."""
    with (
        patch.object(openrouter, "get_daily_spend", new_callable=AsyncMock) as mock_daily,
        patch.object(openrouter, "get_monthly_spend", new_callable=AsyncMock) as mock_monthly,
    ):
        mock_daily.return_value = 0.0
        mock_monthly.return_value = 0.0

        model = await openrouter.select_model(test_db)
        assert model == settings.openrouter_default_model


@pytest.mark.asyncio
async def test_select_model_fallback(openrouter, test_db):
    """At 80%+ daily budget returns fallback model."""
    daily_limit = settings.openrouter_daily_budget_usd

    with (
        patch.object(openrouter, "get_daily_spend", new_callable=AsyncMock) as mock_daily,
        patch.object(openrouter, "get_monthly_spend", new_callable=AsyncMock) as mock_monthly,
    ):
        mock_daily.return_value = daily_limit * 0.85  # 85% of daily
        mock_monthly.return_value = 1.0  # Well under monthly

        model = await openrouter.select_model(test_db)
        assert model == settings.openrouter_fallback_model


@pytest.mark.asyncio
async def test_select_model_exceeded_daily(openrouter, test_db):
    """At 95%+ daily budget raises BudgetExceededError."""
    daily_limit = settings.openrouter_daily_budget_usd

    with (
        patch.object(openrouter, "get_daily_spend", new_callable=AsyncMock) as mock_daily,
        patch.object(openrouter, "get_monthly_spend", new_callable=AsyncMock) as mock_monthly,
    ):
        mock_daily.return_value = daily_limit * 0.96  # 96% of daily
        mock_monthly.return_value = 1.0  # Well under monthly

        with pytest.raises(BudgetExceededError, match="Daily budget"):
            await openrouter.select_model(test_db)


@pytest.mark.asyncio
async def test_select_model_exceeded_monthly(openrouter, test_db):
    """Monthly budget exceeded raises BudgetExceededError."""
    monthly_limit = settings.openrouter_monthly_budget_usd

    with (
        patch.object(openrouter, "get_daily_spend", new_callable=AsyncMock) as mock_daily,
        patch.object(openrouter, "get_monthly_spend", new_callable=AsyncMock) as mock_monthly,
    ):
        mock_daily.return_value = 0.0
        mock_monthly.return_value = monthly_limit + 0.01

        with pytest.raises(BudgetExceededError, match="Monthly budget"):
            await openrouter.select_model(test_db)


def test_estimate_cost_known_model(openrouter):
    """Cost estimation for known model uses correct rates."""
    cost = openrouter.estimate_cost("qwen/qwen2.5-vl-72b-instruct", 1_000_000, 1_000_000)
    # input: 0.15/1M, output: 0.15/1M → 0.30 total
    assert abs(cost - 0.30) < 0.001


def test_estimate_cost_unknown_model(openrouter):
    """Cost estimation for unknown model uses fallback rates."""
    cost = openrouter.estimate_cost("unknown/model", 1_000_000, 1_000_000)
    # fallback: 1.0/1M each → 2.0 total
    assert abs(cost - 2.0) < 0.001


@pytest.mark.asyncio
async def test_record_cost(openrouter, test_db):
    """record_cost creates CostTracker entry in DB."""
    from sqlalchemy import func, select

    from app.models.database import CostTracker

    await openrouter.record_cost(
        db=test_db,
        model="qwen/qwen2-vl-72b-instruct",
        input_tokens=1000,
        output_tokens=500,
        cost_usd=0.001,
    )

    result = await test_db.execute(
        select(func.count()).select_from(CostTracker)
    )
    count = result.scalar()
    assert count == 1
