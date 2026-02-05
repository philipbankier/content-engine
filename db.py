"""Async SQLAlchemy engine and session factory for SQLite."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Indexes that may be missing due to schema drift (added after initial table creation)
# Format: (index_name, table_name, column_name)
REQUIRED_INDEXES = [
    ("ix_content_agent_runs_provider", "content_agent_runs", "provider"),
]


async def _ensure_indexes(conn):
    """Create any missing indexes that weren't created by create_all()."""
    for index_name, table_name, column_name in REQUIRED_INDEXES:
        # Check if index exists
        result = await conn.execute(
            text(f"SELECT name FROM sqlite_master WHERE type='index' AND name='{index_name}'")
        )
        if result.fetchone() is None:
            # Create the missing index
            await conn.execute(
                text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})")
            )


async def create_tables():
    """Create all tables defined in models.py and ensure indexes exist."""
    from models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Fix schema drift: create any missing indexes
        await _ensure_indexes(conn)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
