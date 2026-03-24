from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.api.jobs import router as jobs_router
from app.core.config import BASE_DIR, settings
from app.services.job_manager import job_manager


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize and gracefully shut down application resources."""

    settings.workspace_root.mkdir(parents=True, exist_ok=True)
    job_manager.startup()
    yield
    await job_manager.shutdown()

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(jobs_router)

frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


@app.middleware("http")
async def log_http_requests(request: Request, call_next: object) -> Response:
    """Log request/response metadata with a lightweight body preview."""

    start = time.perf_counter()
    body = await request.body()
    body_preview = body.decode("utf-8", errors="replace")
    if len(body_preview) > 500:
        body_preview = f"{body_preview[:500]}...({len(body_preview)} chars)"

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(request.scope, receive)
    logger.info(
        "HTTP request method=%s path=%s query=%s body=%s",
        request.method,
        request.url.path,
        request.url.query,
        body_preview,
    )
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "HTTP request failed method=%s path=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "HTTP response method=%s path=%s status_code=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.get("/")
async def healthcheck() -> dict[str, str]:
    """Small health endpoint for local checks."""

    return {
        "message": "Local CAE Job Service is running.",
        "frontend": str(Path("/frontend/index.html")),
    }
