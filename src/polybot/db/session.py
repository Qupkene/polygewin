"""Database session management."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from polybot.config import get_settings


def get_engine():
    """Create async SQLAlchemy engine."""
    settings = get_settings()
    return create_async_engine(settings.database_url, echo=(settings.env == "development"))


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create async session factory."""
    engine = get_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    """Get a new async database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
