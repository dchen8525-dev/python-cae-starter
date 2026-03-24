from __future__ import annotations

import argparse
import sys
import time


def parse_bool(value: str) -> bool:
    """Parse a strict boolean command-line value."""

    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes"}:
        return True
    if lowered in {"false", "0", "no"}:
        return False
    raise argparse.ArgumentTypeError("Expected true or false.")


def main() -> int:
    """Emit periodic progress logs and optionally fail."""

    parser = argparse.ArgumentParser(description="Dummy CAE solver")
    parser.add_argument("--duration", type=int, default=10)
    parser.add_argument("--fail", type=parse_bool, default=False)
    args = parser.parse_args()

    total = max(args.duration, 1)
    for index in range(1, total + 1):
        print(f"[{index}/{total}] running...", flush=True)
        time.sleep(1)

    if args.fail:
        print("Dummy solver finished with a simulated failure.", flush=True)
        return 1

    print("Dummy solver finished successfully.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
