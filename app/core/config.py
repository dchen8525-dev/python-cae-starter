from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


@dataclass(slots=True)
class Settings:
    """Application configuration loaded from environment variables."""

    app_name: str = "Local CAE Job Service"
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8765"))
    database_path: Path = BASE_DIR / os.getenv("DATABASE_PATH", "data/jobs.db")
    workspace_root: Path = BASE_DIR / os.getenv("WORKSPACE_ROOT", "workspaces")
    ansa_executable: str | None = os.getenv("ANSA_EXECUTABLE")
    ansa_script_file: str | None = os.getenv("ANSA_SCRIPT_FILE")
    ansa_execpy_prefix: str = os.getenv("ANSA_EXECPY_PREFIX", "load_script:")
    ansa_batch_flags: list[str] = field(
        default_factory=lambda: [
            value.strip()
            for value in os.getenv("ANSA_BATCH_FLAGS", "-b").split(",")
            if value.strip()
        ]
    )
    ansa_candidate_paths: list[str] = field(
        default_factory=lambda: [
            r"C:\Program Files\BETA_CAE_Systems\ansa_v24.1.3\win64\ansa64.bat",
            r"C:\Program Files\BETA_CAE_Systems\ansa_v24.1.3\win64\ansa64.exe",
            r"C:\BETA_CAE_Systems\ansa_v24.1.3\win64\ansa64.bat",
            r"C:\BETA_CAE_Systems\ansa_v24.1.3\win64\ansa64.exe",
        ]
    )
    allowed_origins: list[str] = field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv(
                "ALLOWED_ORIGINS",
                "http://127.0.0.1:3000,http://localhost:3000",
            ).split(",")
            if origin.strip()
        ]
    )
    log_poll_interval_seconds: float = float(
        os.getenv("LOG_POLL_INTERVAL_SECONDS", "0.5")
    )


settings = Settings()
