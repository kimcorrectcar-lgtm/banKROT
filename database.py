from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import DATABASE_URL


def prepare_database_url(
    url: str,
) -> str:
    if url.startswith("postgres://"):
        return url.replace(
            "postgres://",
            "postgresql+asyncpg://",
            1,
        )

    if url.startswith("postgresql://"):
        return url.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )

    return url


DATABASE_ASYNC_URL = (
    prepare_database_url(
        DATABASE_URL,
    )
)


engine = create_async_engine(
    DATABASE_ASYNC_URL,
    echo=False,
    pool_pre_ping=True,
)


AsyncSessionLocal = (
    async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[
    AsyncSession,
    None,
]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_database() -> None:
    from models import (
        ContactRequest,
        Consent,
        User,
    )

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
        )


async def close_database() -> None:
    await engine.dispose()
