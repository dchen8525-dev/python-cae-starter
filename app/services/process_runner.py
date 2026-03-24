from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import subprocess
from typing import Callable

from app.adapters.base import BaseCAEAdapter
from app.core.models import JobRecord, local_now_iso


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ProcessRunResult:
    """Result returned after a job process finishes."""

    return_code: int
    workspace: str
    log_file: str
    log_text: str


class ProcessRunner:
    """Launch and monitor subprocess-based solver jobs."""

    def run(
        self,
        job: JobRecord,
        adapter: BaseCAEAdapter,
        on_started: Callable[[subprocess.Popen[str], str, str], None],
    ) -> ProcessRunResult:
        """Run the configured command and block until completion."""

        workspace = adapter.prepare_workspace(job)
        workspace_path = Path(workspace)
        log_file = workspace_path / "run.log"
        command = adapter.build_command(job)
        logger.info(
            "Job %s prepared workspace=%s log_file=%s command=%s",
            job.job_id,
            workspace_path,
            log_file,
            command,
        )
        command_line = self._format_command(command)

        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        with log_file.open("a", encoding="utf-8") as handle:
            started_at = local_now_iso()
            handle.write(f"# started_at={started_at}\n")
            handle.write(f"# cwd={workspace_path}\n")
            handle.write(f"$ {command_line}\n")
            handle.flush()
            process = subprocess.Popen(
                command,
                cwd=str(workspace_path),
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                shell=False,
                creationflags=creationflags,
            )
            logger.info(
                "Job %s spawned process pid=%s cwd=%s",
                job.job_id,
                process.pid,
                workspace_path,
            )
            on_started(process, str(workspace_path), str(log_file))
            return_code = process.wait()
            logger.info(
                "Job %s process pid=%s exited with return_code=%s",
                job.job_id,
                process.pid,
                return_code,
            )

        log_text = log_file.read_text(encoding="utf-8", errors="replace")
        return ProcessRunResult(
            return_code=return_code,
            workspace=str(workspace_path),
            log_file=str(log_file),
            log_text=log_text,
        )

    @staticmethod
    def _format_command(command: list[str]) -> str:
        """Format a subprocess argument list as a shell-like command line."""

        return subprocess.list2cmdline(command)

    @staticmethod
    def terminate_process(process: subprocess.Popen[str]) -> None:
        """Attempt graceful termination, then force kill if needed."""

        if process.poll() is not None:
            return
        logger.warning("Terminating process pid=%s", process.pid)
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("Killing process pid=%s after terminate timeout", process.pid)
            process.kill()
            process.wait(timeout=5)
