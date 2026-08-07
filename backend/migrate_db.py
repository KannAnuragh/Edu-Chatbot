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
            print("Adding is_global column...")
            try:
                await conn.execute(text("ALTER TABLE documents ADD COLUMN is_global BOOLEAN NOT NULL DEFAULT FALSE;"))
                print("✅ Successfully added 'is_global' column to 'documents' table!")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    print("✅ Column 'is_global' already exists.")
                else:
                    print(f"❌ Failed to add column: {e}")
                    raise e
                    
    except Exception as e:
        print(f"Migration error: {e}")
        sys.exit(1)
        
if __name__ == "__main__":
    asyncio.run(migrate())
