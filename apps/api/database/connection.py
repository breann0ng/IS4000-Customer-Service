"""Async database engine and session factory for PostgreSQL."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=20,
    max_overflow=10,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for dependency injection.

    Yields:
        An async SQLAlchemy session that is automatically closed after use.
    """
    async with async_session_factory() as session:
        yield session
