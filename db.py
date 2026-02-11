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


# Columns that may need adding to existing tables (schema drift from new features)
# Format: (table_name, column_name, column_type, default)
REQUIRED_COLUMNS = [
    ("content_creations", "video_status", "VARCHAR(32)", "'idle'"),
    ("content_creations", "video_url", "TEXT", "NULL"),
    ("content_creations", "video_error", "TEXT", "NULL"),
    ("content_creations", "video_started_at", "DATETIME", "NULL"),
]


async def _ensure_columns(conn):
    """Add missing columns to existing tables (SQLite ALTER TABLE ADD COLUMN)."""
    for table_name, col_name, col_type, default in REQUIRED_COLUMNS:
        # Check if column exists via PRAGMA
        result = await conn.execute(text(f"PRAGMA table_info({table_name})"))
        columns = [row[1] for row in result.fetchall()]
        if col_name not in columns:
            default_clause = f" DEFAULT {default}" if default != "NULL" else ""
            await conn.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}{default_clause}")
            )


async def create_tables():
    """Create all tables defined in models.py and ensure indexes exist."""
    from models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Fix schema drift: create any missing indexes and columns
        await _ensure_indexes(conn)
        await _ensure_columns(conn)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
