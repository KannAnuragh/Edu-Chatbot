import asyncio
import sys
from sqlalchemy import select
from core.database import async_session_factory, engine as async_engine, Base
from core.config import settings
# Import all models to ensure they are registered with Base.metadata
from models import *
from auth.hashing import hash_password

async def create_users():
    # Ensure database schema exists in its own transaction
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("Database schema initialized.")
        
    # --- Auto Migrations in a separate transaction ---
    from sqlalchemy import text
    try:
        async with async_engine.begin() as conn:
            await conn.execute(text("ALTER TABLE documents ADD COLUMN is_global BOOLEAN NOT NULL DEFAULT FALSE;"))
            print("✅ Migration: Successfully added 'is_global' column to 'documents' table!")
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
            pass
        else:
            print(f"⚠️ Migration Error (is_global): {e}")
    async with async_session_factory() as session:
        # Create Admin
        admin_email = settings.DEFAULT_ADMIN_EMAIL
        admin_query = await session.execute(select(User).where(User.email == admin_email))
        admin = admin_query.scalar_one_or_none()
        
        if not admin:
            admin = User(
                name="Admin User",
                email=admin_email,
                password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                role=UserRole.ADMIN
            )
            session.add(admin)
            print(f"Created admin user: {admin_email}")
        else:
            admin.password_hash = hash_password(settings.DEFAULT_ADMIN_PASSWORD)
            admin.role = UserRole.ADMIN
            print(f"Admin user already exists, updated password and role.")

        await session.commit()
        print("Done.")

async def main_with_retry():
    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            await create_users()
            print("Successfully initialized database users.")
            break
        except Exception as e:
            if attempt == max_retries:
                print(f"Failed to initialize database after {max_retries} attempts: {e}")
                sys.exit(1)
            print(f"Database connection attempt {attempt}/{max_retries} failed ({e}). Retrying in 2s...")
            await asyncio.sleep(2)
    await async_engine.dispose()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main_with_retry())

