"""Async SQLite database engine."""

from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "notes2latex.db"

engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", echo=False)


def _ensure_job_mode_column(conn) -> None:  # noqa: ANN001
    """Add ``job.mode`` to databases created before the column existed.

    SQLModel's ``create_all`` never migrates, so an existing database would
    break on every query touching ``mode`` after this column was introduced.
    """
    inspector = inspect(conn)
    if "job" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("job")}
    if "mode" not in columns:
        conn.execute(text("ALTER TABLE job ADD COLUMN mode VARCHAR NOT NULL DEFAULT 'transcribe'"))


async def init_db() -> None:
    """Create tables if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(_ensure_job_mode_column)
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncSession:  # type: ignore[misc]
    """Create a new async session."""
    async with AsyncSession(engine) as session:
        yield session  # type: ignore[misc]
