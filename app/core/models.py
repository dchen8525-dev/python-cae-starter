from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_job_id() -> str:
    """Generate a unique job identifier."""

    return uuid4().hex


class JobStatus(str, Enum):
    """Supported job lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobCreateRequest(BaseModel):
    """Request payload for creating a new job."""

    job_name: str = Field(min_length=1, max_length=200)
    tool: str = Field(min_length=1, max_length=100)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("job_name")
    @classmethod
    def validate_job_name(cls, value: str) -> str:
        """Reject blank names after trimming."""

        stripped = value.strip()
        if not stripped:
            raise ValueError("job_name must not be empty")
        return stripped

    @field_validator("tool")
    @classmethod
    def validate_tool(cls, value: str) -> str:
        """Normalize tool names for lookup."""

        stripped = value.strip().lower()
        if not stripped:
            raise ValueError("tool must not be empty")
        return stripped


class JobResponse(BaseModel):
    """Response payload returned after job creation or cancellation."""

    job_id: str
    status: str
    message: str


class JobDetailResponse(BaseModel):
    """Detailed job information returned to clients."""

    job_id: str
    job_name: str
    tool: str
    status: str
    pid: int | None
    return_code: int | None
    error_message: str | None
    workspace: str | None
    log_file: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    params: dict[str, Any]


@dataclass(slots=True)
class JobRecord:
    """In-memory representation of a job row."""

    job_id: str
    job_name: str
    tool: str
    status: JobStatus
    params: dict[str, Any]
    workspace: str | None
    log_file: str | None
    pid: int | None
    return_code: int | None
    error_message: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None

    def to_detail_response(self) -> JobDetailResponse:
        """Convert this record into the public API shape."""

        return JobDetailResponse(
            job_id=self.job_id,
            job_name=self.job_name,
            tool=self.tool,
            status=self.status.value,
            pid=self.pid,
            return_code=self.return_code,
            error_message=self.error_message,
            workspace=self.workspace,
            log_file=self.log_file,
            created_at=self.created_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
            params=self.params,
        )
