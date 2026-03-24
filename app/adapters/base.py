from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.core.models import JobRecord


class BaseCAEAdapter(ABC):
    """Common adapter contract for CAE tools."""

    tool_name: str

    @abstractmethod
    def validate_params(self, params: dict[str, Any]) -> None:
        """Validate frontend-supplied parameters before job creation."""

    @abstractmethod
    def prepare_workspace(self, job: JobRecord) -> str:
        """Prepare and return the workspace path for the job."""

    @abstractmethod
    def build_command(self, job: JobRecord) -> list[str]:
        """Build the subprocess command line without using shell=True."""

    @abstractmethod
    def parse_result(
        self,
        job: JobRecord,
        return_code: int,
        log_text: str,
    ) -> dict[str, Any]:
        """Interpret process output and return normalized result metadata."""
