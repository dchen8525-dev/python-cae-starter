from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys
from typing import Any


def local_now_iso() -> str:
    """Return the current system-local timestamp as ISO 8601."""

    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser used by ANSA batch execution."""

    parser = argparse.ArgumentParser(
        description="Minimal ANSA batch script template for local job execution."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default="",
        help="Optional ANSA model file path.",
    )
    parser.add_argument(
        "--deck",
        default="NASTRAN",
        help="Target deck name for your workflow, e.g. NASTRAN or ABAQUS.",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory for generated artifacts relative to cwd unless absolute.",
    )
    parser.add_argument(
        "--job-tag",
        default="",
        help="Optional custom tag written into the report file.",
    )
    return parser


def resolve_output_dir(path_text: str) -> Path:
    """Resolve output directory from either relative or absolute path."""

    path = Path(path_text)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def write_report(output_dir: Path, args: argparse.Namespace) -> Path:
    """Write a small execution report to help validate the integration chain."""

    output_dir.mkdir(parents=True, exist_ok=True)
    report_file = output_dir / "run_ansa_report.txt"
    lines = [
        f"timestamp={local_now_iso()}",
        f"cwd={Path.cwd()}",
        f"input_file={args.input_file}",
        f"deck={args.deck}",
        f"job_tag={args.job_tag}",
        f"argv={sys.argv}",
    ]
    report_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_file


def try_import_ansa() -> tuple[bool, Any | None]:
    """Try to import the ANSA Python module inside the embedded interpreter."""

    try:
        import ansa  # type: ignore

        return True, ansa
    except Exception:
        return False, None


def main() -> int:
    """Run a minimal ANSA batch script with verbose diagnostics."""

    parser = build_parser()
    args = parser.parse_args()

    print(f"[run_ansa] started_at={local_now_iso()}", flush=True)
    print(f"[run_ansa] cwd={Path.cwd()}", flush=True)
    print(f"[run_ansa] argv={sys.argv}", flush=True)
    print(f"[run_ansa] input_file={args.input_file or '<empty>'}", flush=True)
    print(f"[run_ansa] deck={args.deck}", flush=True)
    print(f"[run_ansa] output_dir={args.output_dir}", flush=True)

    if args.input_file:
        input_path = Path(args.input_file)
        if not input_path.exists():
            print(f"[run_ansa] ERROR: input_file not found: {input_path}", flush=True)
            return 2
        print(f"[run_ansa] input_file exists: {input_path}", flush=True)

    ansa_available, ansa_module = try_import_ansa()
    if ansa_available:
        print(
            f"[run_ansa] ansa module imported successfully: {getattr(ansa_module, '__name__', 'ansa')}",
            flush=True,
        )
    else:
        print(
            "[run_ansa] ansa module not available in this interpreter. "
            "This is acceptable only for dry-run validation outside ANSA.",
            flush=True,
        )

    output_dir = resolve_output_dir(args.output_dir)
    report_file = write_report(output_dir, args)
    print(f"[run_ansa] wrote report: {report_file}", flush=True)

    print(
        "[run_ansa] placeholder script completed successfully. "
        "Add your real ANSA API logic in scripts/run_ansa.py.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
