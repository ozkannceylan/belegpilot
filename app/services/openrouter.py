"""OpenRouter client with cost tracking, budget enforcement, retry logic, and model fallback."""

import time
from datetime import UTC
from datetime import date as DateType  # noqa: N812
from datetime import datetime as DateTimeType  # noqa: N812
from typing import Any

import httpx
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.models.database import CostTracker

logger = structlog.get_logger()

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# Approximate cost per 1M tokens (update as pricing changes)
MODEL_COSTS = {
    "qwen/qwen2-vl-72b-instruct": {"input": 0.40, "output": 0.40},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "openai/gpt-4o": {"input": 2.50, "output": 10.00},
    "qwen/qwen2-vl-7b-instruct": {"input": 0.10, "output": 0.10},
}


class BudgetExceededError(Exception):
    """Raised when OpenRouter budget limit is reached."""
    pass


class OpenRouterClient:
    def __init__(self) -> None:
        self.api_key = settings.openrouter_api_key
        self.default_model = settings.openrouter_default_model
        self.fallback_model = settings.openrouter_fallback_model
        self.client = httpx.AsyncClient(
            base_url=OPENROUTER_BASE,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://api.ozvatanyapi.com",
                "X-Title": "BelegPilot",
            },
            timeout=60.0,
        )

    async def get_daily_spend(self, db: AsyncSession) -> float:
        """Get total USD spent today."""
        today_start = DateTimeType.combine(DateType.today(), DateTimeType.min.time())
        result = await db.execute(
            select(func.coalesce(func.sum(CostTracker.cost_usd), 0.0)).where(
                CostTracker.date >= today_start
            )
        )
        return float(result.scalar())

    async def get_monthly_spend(self, db: AsyncSession) -> float:
        """Get total USD spent this month."""
        month_start = DateTimeType.combine(
            DateType.today().replace(day=1), DateTimeType.min.time()
        )
        result = await db.execute(
            select(func.coalesce(func.sum(CostTracker.cost_usd), 0.0)).where(
                CostTracker.date >= month_start
            )
        )
        return float(result.scalar())

    async def select_model(self, db: AsyncSession) -> str:
        """Select model based on current budget usage.

        - Under 80% daily budget → default model
        - 80-95% daily budget → fallback (cheaper) model
        - Over 95% daily budget → raise BudgetExceededError
        - Over monthly budget → raise BudgetExceededError
        """
        daily_spend = await self.get_daily_spend(db)
        monthly_spend = await self.get_monthly_spend(db)
        daily_limit = settings.openrouter_daily_budget_usd
        monthly_limit = settings.openrouter_monthly_budget_usd

        if monthly_spend >= monthly_limit:
            logger.warning(
                "Monthly budget exceeded",
                monthly_spend=monthly_spend,
                monthly_limit=monthly_limit,
            )
            raise BudgetExceededError(
                f"Monthly budget of ${monthly_limit} exceeded (${monthly_spend:.4f} spent)"
            )

        if daily_spend >= daily_limit * 0.95:
            logger.warning(
                "Daily budget nearly exceeded",
                daily_spend=daily_spend,
                daily_limit=daily_limit,
            )
            raise BudgetExceededError(
                f"Daily budget of ${daily_limit} nearly exceeded (${daily_spend:.4f} spent)"
            )

        if daily_spend >= daily_limit * 0.80:
            logger.info(
                "Switching to fallback model due to budget",
                daily_spend=daily_spend,
                model=self.fallback_model,
            )
            return self.fallback_model

        return self.default_model

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for a given model and token count."""
        costs = MODEL_COSTS.get(model, {"input": 1.0, "output": 1.0})
        input_cost = (input_tokens / 1_000_000) * costs["input"]
        output_cost = (output_tokens / 1_000_000) * costs["output"]
        return input_cost + output_cost

    async def record_cost(
        self,
        db: AsyncSession,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        """Record API cost in database."""
        tracker = CostTracker(
            date=DateTimeType.now(UTC),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            request_count=1,
        )
        db.add(tracker)
        await db.commit()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type(
            (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)
        ),
    )
    async def extract_receipt(
        self,
        image_base64: str,
        db: AsyncSession,
        model_override: str | None = None,
    ) -> dict[str, Any]:
        """Send image to VLM and get structured receipt data.

        Args:
            image_base64: Base64-encoded image
            db: Database session for cost tracking
            model_override: Force specific model (bypasses budget selection)

        Returns:
            Dict with keys: data (parsed JSON), model, input_tokens,
            output_tokens, cost_usd, raw_response

        Raises:
            BudgetExceededError: If budget limits are reached
            httpx.HTTPStatusError: On API errors (retried 3 times)
        """
        model = model_override or await self.select_model(db)

        start_time = time.time()
        response = await self.client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": USER_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                },
                            },
                        ],
                    },
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
                "max_tokens": 2000,
            },
        )
        if response.status_code >= 400:
            logger.error(
                "OpenRouter API error",
                status_code=response.status_code,
                response_body=response.text[:500],
            )
        response.raise_for_status()
        elapsed_ms = int((time.time() - start_time) * 1000)

        result = response.json()
        usage = result.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = self.estimate_cost(model, input_tokens, output_tokens)

        # Record cost
        await self.record_cost(db, model, input_tokens, output_tokens, cost)

        # Parse the VLM response content
        content = result["choices"][0]["message"]["content"]

        logger.info(
            "VLM extraction complete",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            elapsed_ms=elapsed_ms,
        )

        return {
            "raw_content": content,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "elapsed_ms": elapsed_ms,
        }

    async def close(self) -> None:
        await self.client.aclose()


# ============================================================
# PROMPTS
# ============================================================

SYSTEM_PROMPT = """You are a receipt and invoice data extraction specialist.
Given an image of a receipt or invoice, extract all structured information accurately.

Rules:
1. Extract ALL visible text and numbers
2. For amounts, always use decimal point format (47.83, not 47,83)
3. If a field is not visible or unclear, set it to null
4. For line items, extract each distinct product/service
5. Dates must be ISO format (YYYY-MM-DD)
6. Currency must be 3-letter ISO code (EUR, USD, GBP)
7. Tax information: extract both tax amount and rate if visible
8. Be conservative: if unsure about a value, set it to null rather than guessing
9. Payment method: include card type and last 4 digits if visible
10. Receipt/invoice number: extract if visible"""

USER_PROMPT = """Extract structured data from this receipt/invoice image.

Return ONLY valid JSON matching this exact schema:
{
  "vendor": "string or null",
  "date": "YYYY-MM-DD or null",
  "total_amount": number or null,
  "currency": "ISO 4217 code or null",
  "tax_amount": number or null,
  "tax_rate": number (percentage) or null,
  "line_items": [
    {
      "description": "string",
      "quantity": number or null,
      "unit_price": number or null,
      "total": number
    }
  ],
  "payment_method": "string or null",
  "receipt_number": "string or null"
}

Important: Return ONLY the JSON object, no markdown, no explanation."""
