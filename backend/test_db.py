import asyncio
from sqlalchemy import select
from core.database import async_session_factory
from models.user import User

async def main():
    try:
        async with async_session_factory() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()
            print(f"Connection Successful! Found {len(users)} users.")
            for u in users:
                print(f"- {u.email} (Role: {u.role})")
    except Exception as e:
        print(f"Error connecting to DB: {e}")

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
