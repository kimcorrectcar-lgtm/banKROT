from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import DATABASE_URL

engine = None
SessionLocal = None


def normalize_database_url(url: str | None) -> str | None:
    if not url:
        return None

    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]

    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]

    return url


DATABASE_URL = normalize_database_url(DATABASE_URL)


if DATABASE_URL:
    engine = create_async_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

    SessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def init_db() -> None:
    if engine is None:
        return

    from models import Base

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    if engine is not None:
        await engine.dispose()
