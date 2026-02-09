"""
Initialize BelegPilot database tables.

Usage:
    docker compose exec app python scripts/setup_db.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.database import init_db


async def main() -> None:
    print("Initializing database...")
    await init_db()
    print("Database tables created successfully.")


if __name__ == "__main__":
    asyncio.run(main())
