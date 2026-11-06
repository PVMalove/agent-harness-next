"""The configuration writes of «Настройка» as a command the console server runs as a job:
`python -B configuration_cli.py <operation> --repo <repo> [--request <json>]`, see
`configuration_writes.OPERATIONS`. Exit code 0 prints the result to stdout, 3 is a stale file
(`StaleConfiguration`), 2 any other refusal; the reason goes to stderr."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Run as a script, this file's own directory is on sys.path, where its sibling modules would
# shadow top-level names; the package root goes first even when PYTHONPATH lists it later. An
# import as a module leaves sys.path alone.
if not __package__:
    _HERE = Path(__file__).resolve().parent
    _ROOT = _HERE.parents[2]
    sys.path[:] = [
        entry
        for entry in sys.path
        if entry != str(_ROOT) and Path(entry or os.curdir).resolve() != _HERE
    ]
    sys.path.insert(0, str(_ROOT))

from harness.configuration_store import StaleConfiguration  # noqa: E402
from harness.console.kernel.configuration_writes import OPERATIONS  # noqa: E402

STALE_EXIT = 3
REFUSED_EXIT = 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="configuration_cli")
    parser.add_argument("operation", choices=sorted(OPERATIONS))
    parser.add_argument("--repo", required=True)
    parser.add_argument("--request", default="")
    args = parser.parse_args(argv)
    try:
        message = OPERATIONS[args.operation](Path(args.repo), args.request)
    except StaleConfiguration as exc:
        print(str(exc), file=sys.stderr)
        return STALE_EXIT
    except (ValueError, OSError) as exc:
        print(str(exc) or type(exc).__name__, file=sys.stderr)
        return REFUSED_EXIT
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
