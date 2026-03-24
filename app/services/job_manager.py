from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import logging
from pathlib import Path
import subprocess
from typing import Any

from fastapi import HTTPException, status

from app.adapters.registry import adapter_registry
from app.core.database import db
from app.core.models import (
    JobCreateRequest,
    JobRecord,
    JobResponse,
    JobStatus,
    local_now_iso,
    new_job_id,
)
from app.services.process_runner import ProcessRunner


logger = logging.getLogger(__name__)


class JobManager:
    """Coordinate job persistence, subprocess execution, and cancellation."""

    def __init__(self) -> None:
        self._runner = ProcessRunner()
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._tasks: set[asyncio.Task[Any]] = set()
        self._lock = asyncio.Lock()

    def create_job(self, request: JobCreateRequest) -> JobResponse:
        """Validate and persist a new job, then schedule background execution."""

        logger.info(
            "Create job request received job_name=%s tool=%s params=%s",
            request.job_name,
            request.tool,
            self._summarize_params(request.params),
        )
        adapter = adapter_registry.get(request.tool)
        if adapter is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown tool '{request.tool}'. Supported tools: {adapter_registry.supported_tools()}",
            )

        try:
            adapter.validate_params(request.params)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid params: {exc}",
            ) from exc

        job_id = new_job_id()
        record = JobRecord(
            job_id=job_id,
            job_name=request.job_name,
            tool=request.tool,
            status=JobStatus.PENDING,
            params=request.params,
            workspace=None,
            log_file=None,
            pid=None,
            return_code=None,
            error_message=None,
            created_at=local_now_iso(),
            started_at=None,
            finished_at=None,
        )
        db.insert_job(record)
        logger.info(
            "Job %s persisted status=%s tool=%s created_at=%s",
            job_id,
            record.status.value,
            record.tool,
            record.created_at,
        )
        self._schedule_task(self.run_job(job_id))
        return JobResponse(
            job_id=job_id,
            status=JobStatus.PENDING.value,
            message="Job accepted and scheduled.",
        )

    def _schedule_task(self, coroutine: Coroutine[Any, Any, None]) -> None:
        """Track a background asyncio task until it completes."""

        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def run_job(self, job_id: str) -> None:
        """Execute a pending job in the background."""

        job = db.get_job(job_id)
        if job is None or job.status != JobStatus.PENDING:
            logger.warning(
                "Skipping job execution job_id=%s because record missing or not pending",
                job_id,
            )
            return

        adapter = adapter_registry.get(job.tool)
        if adapter is None:
            logger.error("No adapter registered for tool=%s job_id=%s", job.tool, job_id)
            db.update_job(
                job_id,
                status=JobStatus.FAILED,
                error_message=f"No adapter registered for tool '{job.tool}'.",
                finished_at=local_now_iso(),
            )
            return

        started_at = local_now_iso()
        logger.info(
            "Starting job execution job_id=%s tool=%s params=%s",
            job_id,
            job.tool,
            self._summarize_params(job.params),
        )

        def on_started(
            process: subprocess.Popen[str],
            workspace: str,
            log_file: str,
        ) -> None:
            latest = db.get_job(job_id)
            if latest is not None and latest.status == JobStatus.CANCELLED:
                logger.warning(
                    "Job %s already cancelled before process registration; terminating pid=%s",
                    job_id,
                    process.pid,
                )
                self._runner.terminate_process(process)
                return
            self._processes[job_id] = process
            db.update_job(
                job_id,
                status=JobStatus.RUNNING,
                workspace=workspace,
                log_file=log_file,
                pid=process.pid,
                started_at=started_at,
            )
            logger.info(
                "Job %s status transition pending->running pid=%s workspace=%s log_file=%s",
                job_id,
                process.pid,
                workspace,
                log_file,
            )

        try:
            result = await asyncio.to_thread(self._runner.run, job, adapter, on_started)
            latest = db.get_job(job_id)
            if latest is None:
                logger.warning("Job %s disappeared from database before completion write", job_id)
                return
            if latest.status == JobStatus.CANCELLED:
                db.update_job(
                    job_id,
                    workspace=result.workspace,
                    log_file=result.log_file,
                    return_code=result.return_code,
                )
                logger.info(
                    "Job %s completed after cancellation return_code=%s",
                    job_id,
                    result.return_code,
                )
                return
            parsed = adapter.parse_result(latest, result.return_code, result.log_text)
            final_status = JobStatus(parsed["status"])
            db.update_job(
                job_id,
                status=final_status,
                workspace=result.workspace,
                log_file=result.log_file,
                return_code=result.return_code,
                error_message=parsed.get("error_message"),
                finished_at=local_now_iso(),
            )
            logger.info(
                "Job %s status transition running->%s return_code=%s error_message=%s",
                job_id,
                final_status.value,
                result.return_code,
                parsed.get("error_message"),
            )
        except Exception as exc:
            logger.exception("Job %s failed unexpectedly: %s", job_id, exc)
            db.update_job(
                job_id,
                status=JobStatus.FAILED,
                error_message=str(exc),
                finished_at=local_now_iso(),
            )
        finally:
            self._processes.pop(job_id, None)

    def get_job(self, job_id: str) -> JobRecord:
        """Return a single job or raise 404."""

        job = db.get_job(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )
        logger.info("Fetched job detail job_id=%s status=%s", job_id, job.status.value)
        return job

    def list_jobs(self, status_filter: str | None = None) -> list[JobRecord]:
        """List jobs, optionally filtering by status."""

        if status_filter:
            try:
                JobStatus(status_filter)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported status '{status_filter}'.",
                ) from exc
        jobs = db.list_jobs(status_filter)
        logger.info("Listed jobs status_filter=%s count=%s", status_filter, len(jobs))
        return jobs

    async def cancel_job(self, job_id: str) -> JobResponse:
        """Cancel a pending or running job."""

        async with self._lock:
            job = self.get_job(job_id)
            logger.info("Cancel request received job_id=%s current_status=%s", job_id, job.status.value)
            if job.status == JobStatus.CANCELLED:
                return JobResponse(
                    job_id=job_id,
                    status=job.status.value,
                    message="Job already cancelled.",
                )
            if job.status in {JobStatus.SUCCESS, JobStatus.FAILED}:
                return JobResponse(
                    job_id=job_id,
                    status=job.status.value,
                    message="Job already finished and cannot be cancelled.",
                )

            process = self._processes.get(job_id)
            if process is None:
                db.update_job(
                    job_id,
                    status=JobStatus.CANCELLED,
                    error_message="Job cancelled before process start.",
                    finished_at=local_now_iso(),
                )
                return JobResponse(
                    job_id=job_id,
                    status=JobStatus.CANCELLED.value,
                    message="Job cancelled.",
                )

            await asyncio.to_thread(self._runner.terminate_process, process)
            db.update_job(
                job_id,
                status=JobStatus.CANCELLED,
                return_code=process.returncode,
                error_message="Job cancelled by user.",
                finished_at=local_now_iso(),
            )
            logger.info("Cancelled job %s", job_id)
            return JobResponse(
                job_id=job_id,
                status=JobStatus.CANCELLED.value,
                message="Cancellation requested.",
            )

    def startup(self) -> None:
        """Initialize persistent state at application boot."""

        db.init_db()
        affected = db.mark_incomplete_jobs_failed()
        if affected:
            logger.warning("Marked %s incomplete jobs as failed after restart", affected)

    async def shutdown(self) -> None:
        """Wait briefly for background tasks to settle during app shutdown."""

        if not self._tasks:
            return
        pending = list(self._tasks)
        done, still_pending = await asyncio.wait(pending, timeout=10)
        for task in done:
            try:
                task.result()
            except Exception:
                logger.exception("Background job task finished with an exception")
        for task in still_pending:
            task.cancel()
        if still_pending:
            await asyncio.gather(*still_pending, return_exceptions=True)
        self._tasks.clear()

    def get_log_path(self, job_id: str) -> Path:
        """Resolve the current log path for a job."""

        job = self.get_job(job_id)
        if not job.log_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' has no log file yet.",
            )
        logger.info("Resolved log path job_id=%s log_file=%s", job_id, job.log_file)
        return Path(job.log_file)

    @staticmethod
    def _summarize_params(params: dict[str, Any]) -> dict[str, Any]:
        """Create a log-friendly shallow summary of request parameters."""

        summary: dict[str, Any] = {}
        for key, value in params.items():
            if isinstance(value, str):
                summary[key] = value if len(value) <= 200 else f"{value[:200]}...({len(value)} chars)"
            elif isinstance(value, list):
                summary[key] = {
                    "type": "list",
                    "length": len(value),
                    "preview": value[:5],
                }
            elif isinstance(value, dict):
                summary[key] = {
                    "type": "dict",
                    "keys": sorted(value.keys()),
                }
            else:
                summary[key] = value
        return summary


job_manager = JobManager()
