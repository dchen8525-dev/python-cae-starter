from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.adapters.ansa import AnsaAdapter
from app.core.models import JobCreateRequest
from app.services.job_manager import job_manager
from fastapi import HTTPException

def test_list_jobs_without_token(test_environment: dict[str, object]) -> None:
    jobs = job_manager.list_jobs()
    assert jobs == []


def test_submit_dummy_solver_job(test_environment: dict[str, object]) -> None:
    response = job_manager.create_job(
        JobCreateRequest(
            job_name="pytest-job",
            tool="dummy_solver",
            params={"duration": 1, "fail": False},
        )
    )

    assert response.status == "pending"
    assert response.job_id

    queued_coroutines = test_environment["queued_coroutines"]
    assert isinstance(queued_coroutines, list)
    assert len(queued_coroutines) == 1

    asyncio.run(queued_coroutines[0])
    job = job_manager.get_job(response.job_id)
    assert job.status.value == "success"
    assert job.workspace
    assert job.log_file
    log_lines = Path(job.log_file).read_text(encoding="utf-8").splitlines()
    assert log_lines[0].startswith("# started_at=")
    assert log_lines[1].startswith("# cwd=")
    assert log_lines[2].startswith("$ ")


def test_query_job_status(test_environment: dict[str, object]) -> None:
    response = job_manager.create_job(
        JobCreateRequest(
            job_name="status-job",
            tool="dummy_solver",
            params={"duration": 1, "fail": False},
        )
    )

    queued_coroutines = test_environment["queued_coroutines"]
    assert isinstance(queued_coroutines, list)
    assert len(queued_coroutines) == 1

    asyncio.run(queued_coroutines[0])
    job = job_manager.get_job(response.job_id)

    assert job.job_id == response.job_id
    assert job.tool == "dummy_solver"
    assert job.status.value == "success"
    assert job.return_code == 0


def test_ansa_adapter_builds_command(test_environment: dict[str, object]) -> None:
    tmp_path = test_environment["tmp_path"]
    assert isinstance(tmp_path, Path)

    launcher = tmp_path / "ansa64.bat"
    launcher.write_text("@echo off\n", encoding="utf-8")
    script_file = tmp_path / "ansa_batch.py"
    script_file.write_text("print('ansa batch script')\n", encoding="utf-8")
    input_file = tmp_path / "model.ansa"
    input_file.write_text("dummy ansa content\n", encoding="utf-8")

    from app.core.config import settings
    original_executable = settings.ansa_executable
    original_script_file = settings.ansa_script_file
    settings.ansa_executable = str(launcher)
    settings.ansa_script_file = str(script_file)
    try:
        adapter = AnsaAdapter()
        job_response = job_manager.create_job(
            JobCreateRequest(
                job_name="ansa-job",
                tool="ansa",
                params={
                    "input_file": str(input_file),
                    "script_args": ["--deck", "NASTRAN"],
                    "extra_args": ["-mesa"],
                    "no_gui": True,
                },
            )
        )

        queued_coroutines = test_environment["queued_coroutines"]
        assert isinstance(queued_coroutines, list)
        assert len(queued_coroutines) == 1
        asyncio.run(queued_coroutines[0])

        record = job_manager.get_job(job_response.job_id)
        command = adapter.build_command(record)
    finally:
        settings.ansa_executable = original_executable
        settings.ansa_script_file = original_script_file

    assert command[0].endswith("ansa64.bat")
    assert "-execpy" in command
    assert any(str(script_file) in item for item in command)
    assert any(str(input_file) in item for item in command)
    assert any("load_script:" in item for item in command)
    assert "-mesa" in command


def test_ansa_adapter_quotes_execpy_paths_with_spaces(test_environment: dict[str, object]) -> None:
    tmp_path = test_environment["tmp_path"]
    assert isinstance(tmp_path, Path)

    tools_dir = tmp_path / "Program Files"
    tools_dir.mkdir(parents=True, exist_ok=True)
    launcher = tools_dir / "ansa64.bat"
    launcher.write_text("@echo off\n", encoding="utf-8")

    scripts_dir = tmp_path / "batch scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    script_file = scripts_dir / "run ansa.py"
    script_file.write_text("print('ansa batch script')\n", encoding="utf-8")

    models_dir = tmp_path / "input models"
    models_dir.mkdir(parents=True, exist_ok=True)
    input_file = models_dir / "demo model.ansa"
    input_file.write_text("dummy ansa content\n", encoding="utf-8")

    from app.core.config import settings
    original_executable = settings.ansa_executable
    original_script_file = settings.ansa_script_file
    settings.ansa_executable = str(launcher)
    settings.ansa_script_file = str(script_file)
    try:
        adapter = AnsaAdapter()
        job_response = job_manager.create_job(
            JobCreateRequest(
                job_name="ansa-job-spaces",
                tool="ansa",
                params={
                    "input_file": str(input_file),
                    "script_args": ["--deck", "NASTRAN SOL 101"],
                    "extra_args": ["-mesa"],
                    "no_gui": True,
                },
            )
        )

        queued_coroutines = test_environment["queued_coroutines"]
        assert isinstance(queued_coroutines, list)
        assert len(queued_coroutines) == 1
        asyncio.run(queued_coroutines[0])

        record = job_manager.get_job(job_response.job_id)
        command = adapter.build_command(record)
    finally:
        settings.ansa_executable = original_executable
        settings.ansa_script_file = original_script_file

    execpy_value = command[command.index("-execpy") + 1]
    assert f'load_script:"{script_file}"' in execpy_value
    assert f'"{input_file}"' in execpy_value
    assert '"NASTRAN SOL 101"' in execpy_value


def test_unknown_tool_returns_400(test_environment: dict[str, object]) -> None:
    with pytest.raises(HTTPException) as exc_info:
        job_manager.create_job(
            JobCreateRequest(
                job_name="bad-tool-job",
                tool="not_supported",
                params={},
            )
        )

    assert exc_info.value.status_code == 400
    assert "Unknown tool" in str(exc_info.value.detail)
