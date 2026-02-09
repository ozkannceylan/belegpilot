"""
Generate a new API key for BelegPilot.

Usage:
    docker compose exec app python scripts/generate_api_key.py --name "My Key"
    docker compose exec app python scripts/generate_api_key.py --name "Test Key" --description "For development testing"
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.database import async_session, init_db
from app.services.auth import create_api_key


async def main(name: str, description: str | None = None) -> None:
    await init_db()

    async with async_session() as session:
        plaintext_key, db_key = await create_api_key(
            session=session,
            name=name,
            description=description,
        )

    print("\n" + "=" * 60)
    print("  NEW API KEY GENERATED")
    print("=" * 60)
    print(f"  Name:        {db_key.name}")
    print(f"  Key:         {plaintext_key}")
    print(f"  Prefix:      {db_key.key_prefix}")
    print(f"  Created:     {db_key.created_at}")
    print("=" * 60)
    print("  SAVE THIS KEY NOW - it cannot be retrieved later!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate BelegPilot API key")
    parser.add_argument("--name", required=True, help="Name for this API key")
    parser.add_argument("--description", help="Optional description")
    args = parser.parse_args()

    asyncio.run(main(name=args.name, description=args.description))
