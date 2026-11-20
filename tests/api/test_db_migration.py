"""Tests for the job.mode column migration on pre-existing databases."""

import sqlite3

from sqlalchemy import create_engine

from db.engine import _ensure_job_mode_column


_LEGACY_JOB_SCHEMA = """
CREATE TABLE job (
    id VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    model VARCHAR NOT NULL,
    total_pages INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message VARCHAR,
    input_filenames JSON NOT NULL DEFAULT '[]',
    has_pdf BOOLEAN NOT NULL DEFAULT 0,
    has_tex BOOLEAN NOT NULL DEFAULT 0,
    PRIMARY KEY (id)
)
"""


def test_legacy_db_gains_mode_column(tmp_path):
    """A database created before job.mode existed is migrated in place."""
    db_path = tmp_path / "notes2latex.db"

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.exec_driver_sql(_LEGACY_JOB_SCHEMA)
        conn.exec_driver_sql(
            "INSERT INTO job (id, status, model, input_filenames) "
            "VALUES ('legacy1', 'completed', 'test/model', '[\"p.png\"]')"
        )
        _ensure_job_mode_column(conn)
    # Idempotent: a second pass (e.g. next server start) must not fail.
    with engine.begin() as conn:
        _ensure_job_mode_column(conn)
    engine.dispose()

    conn = sqlite3.connect(db_path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(job)")}
    assert "mode" in columns
    assert "pipeline" in columns
    (mode,) = conn.execute("SELECT mode FROM job WHERE id = 'legacy1'").fetchone()
    assert mode == "transcribe"
    conn.close()


def test_fresh_db_without_job_table_is_a_noop(tmp_path):
    """No job table yet (fresh database): the migration must not create one."""
    db_path = tmp_path / "fresh.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        _ensure_job_mode_column(conn)
    engine.dispose()

    conn = sqlite3.connect(db_path)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert tables == []
    conn.close()


def test_current_schema_is_left_alone(tmp_path):
    """A database that already has job.mode is untouched."""
    db_path = tmp_path / "current.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.exec_driver_sql(_LEGACY_JOB_SCHEMA)
        conn.exec_driver_sql(
            "ALTER TABLE job ADD COLUMN mode VARCHAR NOT NULL DEFAULT 'transcribe'"
        )
        conn.exec_driver_sql(
            "INSERT INTO job (id, status, model, input_filenames, mode) "
            "VALUES ('new1', 'completed', 'test/model', '[]', 'material')"
        )
        _ensure_job_mode_column(conn)
    engine.dispose()

    conn = sqlite3.connect(db_path)
    (mode,) = conn.execute("SELECT mode FROM job WHERE id = 'new1'").fetchone()
    assert mode == "material"
    conn.close()
