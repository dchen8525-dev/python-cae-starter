from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import settings
from app.core.database import db
from app.core.models import JobStatus, local_now_iso
from app.services.job_manager import job_manager


@pytest.fixture()
def test_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    """Configure isolated paths and token values for each test."""

    database_path = tmp_path / "data" / "jobs.db"
    workspace_root = tmp_path / "workspaces"

    original_database_path = settings.database_path
    original_workspace_root = settings.workspace_root
    original_origins = list(settings.allowed_origins)

    settings.database_path = database_path
    settings.workspace_root = workspace_root
    settings.allowed_origins = ["http://127.0.0.1:3000", "http://localhost:3000"]
    db.set_db_path(database_path)
    settings.workspace_root.mkdir(parents=True, exist_ok=True)
    job_manager.startup()

    async def fake_run_job(job_id: str) -> None:
        job = db.get_job(job_id)
        if job is None:
            return
        workspace = settings.workspace_root / job_id
        workspace.mkdir(parents=True, exist_ok=True)
        log_file = workspace / "run.log"
        started_at = local_now_iso()
        log_file.write_text(
            f"# started_at={started_at}\n"
            f"# cwd={workspace}\n"
            "$ fake-command --job test\n"
            "[1/1] running...\n"
            "Dummy solver finished successfully.\n",
            encoding="utf-8",
        )
        db.update_job(
            job_id,
            status=JobStatus.RUNNING,
            workspace=str(workspace),
            log_file=str(log_file),
            pid=99999,
            started_at=started_at,
        )
        db.update_job(
            job_id,
            status=JobStatus.SUCCESS,
            workspace=str(workspace),
            log_file=str(log_file),
            return_code=0,
            finished_at=local_now_iso(),
        )

    monkeypatch.setattr(job_manager, "run_job", fake_run_job)
    queued_coroutines: list[object] = []
    monkeypatch.setattr(job_manager, "_schedule_task", queued_coroutines.append)

    yield {
        "tmp_path": tmp_path,
        "queued_coroutines": queued_coroutines,
    }

    settings.database_path = original_database_path
    settings.workspace_root = original_workspace_root
    settings.allowed_origins = original_origins
    db.set_db_path(original_database_path)
