from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, WebSocket

from app.core.models import JobCreateRequest, JobDetailResponse, JobResponse
from app.services.job_manager import job_manager
from app.services.log_stream import log_streamer


router = APIRouter(prefix="", tags=["jobs"])
logger = logging.getLogger(__name__)


@router.post("/jobs", response_model=JobResponse)
async def create_job(request: JobCreateRequest) -> JobResponse:
    """Submit a new job."""

    logger.info("API POST /jobs tool=%s job_name=%s", request.tool, request.job_name)
    return job_manager.create_job(request)


@router.get(
    "/jobs/{job_id}",
    response_model=JobDetailResponse,
)
async def get_job(job_id: str) -> JobDetailResponse:
    """Fetch job details."""

    logger.info("API GET /jobs/%s", job_id)
    return job_manager.get_job(job_id).to_detail_response()


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=JobResponse,
)
async def cancel_job(job_id: str) -> JobResponse:
    """Cancel a pending or running job."""

    logger.info("API POST /jobs/%s/cancel", job_id)
    return await job_manager.cancel_job(job_id)


@router.get(
    "/jobs",
    response_model=list[JobDetailResponse],
)
async def list_jobs(
    status: Annotated[str | None, Query(description="Optional status filter")] = None,
) -> list[JobDetailResponse]:
    """List jobs, optionally filtered by status."""

    logger.info("API GET /jobs status_filter=%s", status)
    return [job.to_detail_response() for job in job_manager.list_jobs(status)]


@router.websocket("/ws/jobs/{job_id}")
async def stream_job_logs(websocket: WebSocket, job_id: str) -> None:
    """Stream job logs incrementally over WebSocket."""

    logger.info("API WS /ws/jobs/%s connect", job_id)
    try:
        log_path = job_manager.get_log_path(job_id)
    except HTTPException as exc:
        await websocket.accept()
        await websocket.send_json({"error": exc.detail})
        await websocket.close()
        logger.warning("API WS /ws/jobs/%s rejected: %s", job_id, exc.detail)
        return

    await log_streamer.stream_job_log(websocket, log_path)
