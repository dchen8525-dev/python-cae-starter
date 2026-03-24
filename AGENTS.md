# Repository Guidelines

## Project Structure & Module Organization
`app/` contains the FastAPI service. Keep HTTP routes in `app/api/`, shared config and persistence in `app/core/`, solver integrations in `app/adapters/`, and runtime orchestration in `app/services/`. Static demo assets live in `frontend/`. Helper scripts for local CAE execution live in `scripts/`. Tests are in `tests/`. Runtime artifacts such as SQLite files and per-job logs belong in `data/` and `workspaces/` and should not be committed.

## Build, Test, and Development Commands
Install dependencies with `pip install -r requirements.txt`.
Run the service locally with `uvicorn app.main:app --host 127.0.0.1 --port 8765`.
On Windows PowerShell, use `./run.ps1` to start the app and auto-create `.env` from `.env.example`.
Run tests with `pytest`.
Check current changes before committing with `git status --short`.

## Coding Style & Naming Conventions
Use 4-space indentation and standard Python style. Prefer type hints, `pathlib.Path`, and small focused functions. Modules and files use `snake_case.py`; classes use `PascalCase`; functions, variables, and test fixtures use `snake_case`. Keep adapter names aligned with the registered tool name, for example `AnsaAdapter` for `tool="ansa"`. No formatter or linter is configured yet, so keep imports tidy and match the surrounding style.

## Testing Guidelines
This project uses `pytest`, configured by `pytest.ini` to load tests from `tests/`. Name test files `test_*.py` and test functions `test_*`. Add coverage for API behavior, job lifecycle changes, and adapter command construction when changing execution logic. Run `pytest` before opening a pull request.

## Commit & Pull Request Guidelines
Follow concise Conventional Commit style as used in history, for example `feat: bootstrap local CAE job service`. Keep the subject imperative and specific. Pull requests should include a short summary, note any config or API changes, link related issues if available, and include screenshots only when frontend behavior changes.

## Security & Configuration Tips
Do not commit `.env`, local database files, or generated logs. Keep executable paths such as `ANSA_EXECUTABLE` and `ANSA_SCRIPT_FILE` in `.env`. Frontend requests should pass business parameters only; executable selection belongs in server-side adapters.
