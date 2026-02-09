"""
Check current OpenRouter API spend.

Usage:
    docker compose exec app python scripts/check_cost.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, date

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from app.models.database import async_session, CostTracker, init_db
from app.config import settings


async def main():
    await init_db()

    async with async_session() as session:
        today_start = datetime.combine(date.today(), datetime.min.time())
        month_start = datetime.combine(date.today().replace(day=1), datetime.min.time())

        # Daily spend
        daily = await session.execute(
            select(func.coalesce(func.sum(CostTracker.cost_usd), 0.0)).where(
                CostTracker.date >= today_start
            )
        )
        daily_spend = float(daily.scalar())

        # Monthly spend
        monthly = await session.execute(
            select(func.coalesce(func.sum(CostTracker.cost_usd), 0.0)).where(
                CostTracker.date >= month_start
            )
        )
        monthly_spend = float(monthly.scalar())

        # Request counts
        daily_count = await session.execute(
            select(func.coalesce(func.sum(CostTracker.request_count), 0)).where(
                CostTracker.date >= today_start
            )
        )
        monthly_count = await session.execute(
            select(func.coalesce(func.sum(CostTracker.request_count), 0)).where(
                CostTracker.date >= month_start
            )
        )

    print("\n" + "=" * 50)
    print("  BelegPilot - OpenRouter Cost Report")
    print("=" * 50)
    print(f"  Daily  spend:  ${daily_spend:.4f} / ${settings.openrouter_daily_budget_usd:.2f}")
    print(f"  Monthly spend: ${monthly_spend:.4f} / ${settings.openrouter_monthly_budget_usd:.2f}")
    print(f"  Requests today: {daily_count.scalar()}")
    print(f"  Requests this month: {monthly_count.scalar()}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
