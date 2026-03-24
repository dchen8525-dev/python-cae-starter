from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.adapters.base import BaseCAEAdapter
from app.core.config import settings
from app.core.models import JobRecord


class DummySolverParams(BaseModel):
    """Validated parameters for the dummy solver."""

    duration: int = Field(default=10, ge=1, le=3600)
    fail: bool = False


class DummySolverAdapter(BaseCAEAdapter):
    """Adapter that simulates a CAE solver via a Python helper script."""

    tool_name = "dummy_solver"

    def validate_params(self, params: dict[str, Any]) -> None:
        """Validate duration and fail options."""

        try:
            DummySolverParams.model_validate(params)
        except ValidationError as exc:
            raise ValueError(exc.json()) from exc

    def prepare_workspace(self, job: JobRecord) -> str:
        """Create the job workspace and return its path."""

        workspace = settings.workspace_root / job.job_id
        workspace.mkdir(parents=True, exist_ok=True)
        return str(workspace)

    def build_command(self, job: JobRecord) -> list[str]:
        """Run the dummy solver through the current Python interpreter."""

        params = DummySolverParams.model_validate(job.params)
        script_path = Path(__file__).resolve().parents[2] / "scripts" / "dummy_solver.py"
        return [
            sys.executable,
            str(script_path),
            "--duration",
            str(params.duration),
            "--fail",
            "true" if params.fail else "false",
        ]

    def parse_result(
        self,
        job: JobRecord,
        return_code: int,
        log_text: str,
    ) -> dict[str, Any]:
        """Map process exit code into a status summary."""

        if return_code == 0:
            return {
                "status": "success",
                "error_message": None,
                "summary": f"Dummy solver completed for job {job.job_id}.",
            }
        return {
            "status": "failed",
            "error_message": "Dummy solver reported a non-zero exit code.",
            "summary": log_text[-500:],
        }
