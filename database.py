from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create the current schema and migrate old installations idempotently."""
    from models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # create_all() does not add columns to already existing PostgreSQL tables.
        # Keep these migrations deliberately simple and idempotent so an existing
        # Render database can be upgraded without deleting user data.
        migrations = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS name TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS consented_at TIMESTAMPTZ",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS telegram_id BIGINT",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS name TEXT",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS phone TEXT",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS service VARCHAR(255)",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS status VARCHAR(64) DEFAULT 'Новая'",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS comment TEXT",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
            "ALTER TABLE testers ADD COLUMN IF NOT EXISTS telegram_id BIGINT",
            "ALTER TABLE testers ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
            "ALTER TABLE security_audit ADD COLUMN IF NOT EXISTS actor_telegram_id BIGINT",
            "ALTER TABLE security_audit ADD COLUMN IF NOT EXISTS actor_role VARCHAR(32)",
            "ALTER TABLE security_audit ADD COLUMN IF NOT EXISTS action VARCHAR(128)",
            "ALTER TABLE security_audit ADD COLUMN IF NOT EXISTS target_type VARCHAR(64)",
            "ALTER TABLE security_audit ADD COLUMN IF NOT EXISTS target_id VARCHAR(128)",
            "ALTER TABLE security_audit ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
        ]
        for statement in migrations:
            await conn.execute(text(statement))

        await conn.execute(text("UPDATE leads SET status = 'Новая' WHERE status IS NULL"))
        await conn.execute(text("UPDATE users SET created_at = NOW() WHERE created_at IS NULL"))
        await conn.execute(text("UPDATE users SET updated_at = NOW() WHERE updated_at IS NULL"))
        await conn.execute(text("UPDATE leads SET created_at = NOW() WHERE created_at IS NULL"))
        await conn.execute(text("UPDATE leads SET updated_at = NOW() WHERE updated_at IS NULL"))
        await conn.execute(text("UPDATE testers SET created_at = NOW() WHERE created_at IS NULL"))
        await conn.execute(text("UPDATE security_audit SET created_at = NOW() WHERE created_at IS NULL"))


async def close_db() -> None:
    await engine.dispose()
