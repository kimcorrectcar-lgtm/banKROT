from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import DATABASE_URL


engine = None
SessionLocal = None


if DATABASE_URL:
    engine = create_async_engine(
        DATABASE_URL,
        pool_pre_ping=True,
    )

    SessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
