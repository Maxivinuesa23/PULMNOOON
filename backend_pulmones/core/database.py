from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from core.config import DATABASE_URL


def _async_database_url(url: str) -> str:
    """Use asyncpg explicitly, including with Supabase's postgres URL."""
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    if not url.startswith("postgresql+asyncpg://"):
        raise ValueError(
            "DATABASE_URL debe usar el esquema postgres://, postgresql:// "
            "o postgresql+asyncpg://."
        )
    return url


engine = create_async_engine(
    _async_database_url(DATABASE_URL),
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide one session per request and always close it afterwards."""
    async with AsyncSessionLocal() as session:
        yield session
