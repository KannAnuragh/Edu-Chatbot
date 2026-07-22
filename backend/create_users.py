import asyncio
import sys
from sqlalchemy import select
from core.database import async_session_factory, engine as async_engine, Base
# Import all models to ensure they are registered with Base.metadata
from models.user import User, UserRole
from models.course import Course
from models.document import Document
from models.enrollment import Enrollment
from models.conversation import Conversation, Message
from auth.hashing import hash_password

async def create_users():
    # Ensure database schema exists
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("Database schema initialized.")
    async with async_session_factory() as session:
        # Create Admin
        admin_email = "admin@gmail.com"
        admin_query = await session.execute(select(User).where(User.email == admin_email))
        admin = admin_query.scalar_one_or_none()
        
        if not admin:
            admin = User(
                name="Admin User",
                email=admin_email,
                password_hash=hash_password("admin123"),
                role=UserRole.ADMIN
            )
            session.add(admin)
            print(f"Created admin user: {admin_email}")
        else:
            admin.password_hash = hash_password("admin123")
            admin.role = UserRole.ADMIN
            print(f"Admin user already exists, updated password and role.")

        # Create Student
        student_email = "student@example.com"
        student_query = await session.execute(select(User).where(User.email == student_email))
        student = student_query.scalar_one_or_none()
        
        if not student:
            student = User(
                name="Student User",
                email=student_email,
                password_hash=hash_password("password123"),
                role=UserRole.STUDENT
            )
            session.add(student)
            print(f"Created student user: {student_email}")
        else:
            print(f"Student user already exists.")

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

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main_with_retry())

