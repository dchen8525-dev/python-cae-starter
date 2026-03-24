from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import WebSocket

from app.core.config import settings


class LogStreamer:
    """Incrementally stream appended log file content over WebSocket."""

    async def stream_job_log(self, websocket: WebSocket, log_path: Path) -> None:
        """Push new log content until the client disconnects."""

        await websocket.accept()
        if not log_path.exists():
            await websocket.send_json({"error": "Log file does not exist yet."})
            await websocket.close()
            return

        position = 0
        try:
            while True:
                if log_path.exists():
                    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
                        handle.seek(position)
                        chunk = handle.read()
                        position = handle.tell()
                    if chunk:
                        await websocket.send_text(chunk)
                await asyncio.sleep(settings.log_poll_interval_seconds)
        except Exception:
            await websocket.close()


log_streamer = LogStreamer()
