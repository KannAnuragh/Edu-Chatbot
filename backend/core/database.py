"""
AI Course Assistant Backend — Database Engine & Session Management.

Provides async SQLAlchemy engine and session factory.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from core.config import settings


# Async engine for FastAPI
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=3,
    max_overflow=2,
    pool_pre_ping=True,
)

# Async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


async def get_db() -> AsyncSession:
    """Dependency that provides a database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
