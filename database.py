from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.engine import make_url
from sqlalchemy import text

from config import DATABASE_URL


def normalize_database_url(url: str) -> str:
    parsed = make_url(url)
    if parsed.drivername in {"postgresql", "postgres"}:
        parsed = parsed.set(drivername="postgresql+asyncpg")
    return parsed.render_as_string(hide_password=False)


DB_URL = normalize_database_url(DATABASE_URL)
engine = create_async_engine(
    DB_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={"ssl": "require"},
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    from models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # create_all() does not add new columns to an existing PostgreSQL table.
        # These idempotent ALTERs keep old installations compatible after upgrade.
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS name TEXT"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT"))


async def close_db() -> None:
    await engine.dispose()
