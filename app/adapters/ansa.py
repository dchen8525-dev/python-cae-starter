from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator

from app.adapters.base import BaseCAEAdapter
from app.core.config import settings
from app.core.models import JobRecord


class AnsaParams(BaseModel):
    """Validated parameters for ANSA batch execution."""

    script_file: str | None = None
    input_file: str | None = None
    script_args: list[str] = Field(default_factory=list)
    extra_args: list[str] = Field(default_factory=list)
    no_gui: bool = True

    @model_validator(mode="after")
    def validate_paths(self) -> "AnsaParams":
        """Ensure local script and optional model paths exist."""

        script_file = self.script_file or settings.ansa_script_file
        if not script_file:
            raise ValueError("ANSA script file is not configured. Set ANSA_SCRIPT_FILE in .env.")
        if not Path(script_file).is_file():
            raise ValueError(f"ANSA script file does not exist: {script_file}")
        self.script_file = script_file
        if self.input_file and not Path(self.input_file).exists():
            raise ValueError(f"input_file does not exist: {self.input_file}")
        return self


class AnsaAdapter(BaseCAEAdapter):
    """Adapter for launching BETA CAE Systems ANSA in batch/script mode."""

    tool_name = "ansa"

    def validate_params(self, params: dict[str, Any]) -> None:
        """Validate ANSA request parameters and executable availability."""

        self._resolve_executable()
        try:
            AnsaParams.model_validate(params)
        except ValidationError as exc:
            raise ValueError(exc.json()) from exc

    def prepare_workspace(self, job: JobRecord) -> str:
        """Create and return a per-job workspace."""

        workspace = settings.workspace_root / job.job_id
        workspace.mkdir(parents=True, exist_ok=True)
        return str(workspace)

    def build_command(self, job: JobRecord) -> list[str]:
        """Build an ANSA batch command using the configured installation."""

        executable = self._resolve_executable()
        params = AnsaParams.model_validate(job.params)
        command = [executable]
        if params.no_gui:
            command.extend(settings.ansa_batch_flags)

        execpy_parts = [
            f"{settings.ansa_execpy_prefix.rstrip()}{self._quote_execpy_arg(params.script_file)}"
        ]
        if params.input_file:
            execpy_parts.append(self._quote_execpy_arg(params.input_file))
        execpy_parts.extend(self._quote_execpy_arg(arg) for arg in params.script_args)
        execpy_value = " ".join(execpy_parts)
        command.extend(["-execpy", execpy_value])
        command.extend(params.extra_args)
        return command

    def parse_result(
        self,
        job: JobRecord,
        return_code: int,
        log_text: str,
    ) -> dict[str, Any]:
        """Map ANSA process completion into normalized job status."""

        if return_code == 0:
            return {
                "status": "success",
                "error_message": None,
                "summary": f"ANSA completed for job {job.job_id}.",
            }
        return {
            "status": "failed",
            "error_message": "ANSA returned a non-zero exit code.",
            "summary": log_text[-500:],
        }

    @staticmethod
    def _resolve_executable() -> str:
        """Resolve the ANSA launcher path from config or common Windows locations."""

        if settings.ansa_executable:
            executable = Path(settings.ansa_executable)
            if executable.exists():
                return str(executable)
            raise ValueError(f"ANSA executable not found: {settings.ansa_executable}")

        for candidate in settings.ansa_candidate_paths:
            path = Path(candidate)
            if path.exists():
                return str(path)

        raise ValueError(
            "ANSA executable is not configured. Set ANSA_EXECUTABLE in .env "
            "to your ANSA v24.1.3 launcher, for example ansa64.bat or ansa64.exe."
        )

    @staticmethod
    def _quote_execpy_arg(value: str) -> str:
        """Quote an -execpy argument so paths with spaces survive ANSA parsing."""

        return subprocess.list2cmdline([value])
