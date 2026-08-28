"""
One-off migration: add the quiz_state JSON column to the conversations table.

Mirrors the pattern used by migrate_db.py for environments where Alembic
hasn't been run yet. Safe to run multiple times — it short-circuits if the
column already exists.
"""
import asyncio
import sys
import os

# Ensure backend is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from core.database import engine


async def migrate():
    print("Connecting to database...")
    try:
        async with engine.begin() as conn:
            print("Adding quiz_state column to conversations table...")
            try:
                await conn.execute(
                    text("ALTER TABLE conversations ADD COLUMN quiz_state JSON NULL;")
                )
                print("✅ Successfully added 'quiz_state' column to 'conversations' table!")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    print("✅ Column 'quiz_state' already exists.")
                else:
                    print(f"❌ Failed to add column: {e}")
                    raise e

    except Exception as e:
        print(f"Migration error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(migrate())
