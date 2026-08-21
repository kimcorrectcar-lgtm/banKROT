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

# PostgreSQL session-level advisory lock. It prevents two Render instances
# from polling Telegram with the same bot token at the same time.
POLLING_LOCK_SQL = "SELECT pg_advisory_lock(hashtextextended('bankrot:telegram_polling', 0))"


async def init_db() -> None:
    from models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def acquire_polling_lock():
    conn = await engine.connect()
    try:
        await conn.execute(text(POLLING_LOCK_SQL))
        return conn
    except Exception:
        await conn.close()
        raise


async def release_polling_lock(conn) -> None:
    if conn is None:
        return
    await conn.close()


async def close_db() -> None:
    await engine.dispose()
