from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from app.core.config import settings
from app.core.models import JobRecord, JobStatus, local_now_iso


class Database:
    """Thin SQLite wrapper for persisting job state."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def set_db_path(self, db_path: Path) -> None:
        """Update the database file location."""

        self._db_path = db_path

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Open a SQLite connection with Row access enabled."""

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def init_db(self) -> None:
        """Create tables if this is the first application start."""

        with self.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    job_name TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    status TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    workspace TEXT,
                    log_file TEXT,
                    pid INTEGER,
                    return_code INTEGER,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at)"
            )

    def insert_job(self, record: JobRecord) -> None:
        """Insert a new job row."""

        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, job_name, tool, status, params_json, workspace, log_file,
                    pid, return_code, error_message, created_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.job_id,
                    record.job_name,
                    record.tool,
                    record.status.value,
                    json.dumps(record.params, ensure_ascii=True),
                    record.workspace,
                    record.log_file,
                    record.pid,
                    record.return_code,
                    record.error_message,
                    record.created_at,
                    record.started_at,
                    record.finished_at,
                ),
            )

    def update_job(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        workspace: str | None = None,
        log_file: str | None = None,
        pid: int | None = None,
        return_code: int | None = None,
        error_message: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        """Update mutable job columns."""

        updates: dict[str, Any] = {}
        if status is not None:
            updates["status"] = status.value
        if workspace is not None:
            updates["workspace"] = workspace
        if log_file is not None:
            updates["log_file"] = log_file
        if pid is not None:
            updates["pid"] = pid
        if return_code is not None:
            updates["return_code"] = return_code
        if error_message is not None:
            updates["error_message"] = error_message
        if started_at is not None:
            updates["started_at"] = started_at
        if finished_at is not None:
            updates["finished_at"] = finished_at
        if not updates:
            return

        assignments = ", ".join(f"{column} = ?" for column in updates)
        values = list(updates.values())
        values.append(job_id)
        with self.connection() as connection:
            connection.execute(f"UPDATE jobs SET {assignments} WHERE id = ?", values)

    def get_job(self, job_id: str) -> JobRecord | None:
        """Fetch a single job row."""

        with self.connection() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def list_jobs(self, status: str | None = None) -> list[JobRecord]:
        """List jobs ordered by creation time descending."""

        query = "SELECT * FROM jobs"
        params: tuple[Any, ...] = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY created_at DESC"
        with self.connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_record(row) for row in rows]

    def mark_incomplete_jobs_failed(self) -> int:
        """Mark jobs left unfinished before a service restart as failed."""

        finished_at = local_now_iso()
        with self.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = ?, finished_at = ?, error_message = ?
                WHERE status IN (?, ?)
                """,
                (
                    JobStatus.FAILED.value,
                    finished_at,
                    "Service restarted before job completion.",
                    JobStatus.PENDING.value,
                    JobStatus.RUNNING.value,
                ),
            )
            return cursor.rowcount

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> JobRecord:
        """Convert a SQLite row into a typed job record."""

        return JobRecord(
            job_id=row["id"],
            job_name=row["job_name"],
            tool=row["tool"],
            status=JobStatus(row["status"]),
            params=json.loads(row["params_json"]),
            workspace=row["workspace"],
            log_file=row["log_file"],
            pid=row["pid"],
            return_code=row["return_code"],
            error_message=row["error_message"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )


db = Database(settings.database_path)
