#!/usr/bin/env python3
# Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
# SPDX-License-Identifier: BUSL-1.1
# Licensed under the Business Source License 1.1 (BSL-1.1).
# Commercial use, sale, or use in commercial application development is strictly
# prohibited without prior written permission from the copyright holder.
# Removing or altering this header is prohibited and voids all license rights.

"""Read-only check of the canonical license header in the core source files.

`LICENSE` forbids removing or altering the header, so this check fails on a missing or edited
line instead of repairing anything. The registry is explicit rather than a glob: the header
marks the process entry points and the core modules of the harness, never vendored code,
target-project templates, generated files or tests. A file that becomes a protected entry
point must be listed here, otherwise the check does not see it.

Every protected file starts with the header, optionally after a `#!` line; the check compares
exactly those lines and never rewrites the file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HEADER = (
    "Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)",
    "SPDX-License-Identifier: BUSL-1.1",
    "Licensed under the Business Source License 1.1 (BSL-1.1).",
    "Commercial use, sale, or use in commercial application development is strictly",
    "prohibited without prior written permission from the copyright holder.",
    "Removing or altering this header is prohibited and voids all license rights.",
)

COMMENT_PREFIX = {
    ".py": "#",
    ".rs": "//",
}

# Process entry points and core modules only: hooks and documents under `harness/project/` are
# seeded into target projects, `skills/vendor/` is an upstream snapshot, and tests are excluded.
PROTECTED_FILES = (
    # Python package root, configuration, storage and error seams.
    "harness/__init__.py",
    "harness/configuration.py",
    "harness/diagnostics.py",
    "harness/errors.py",
    "harness/runtime_adapters.py",
    "harness/storage.py",
    # Python process entry points and subsystem roots.
    "bin/install-global.py",
    "harness/bin/harness.py",
    "harness/console/backend/composition.py",
    "harness/console/backend/server.py",
    "harness/console/launcher.py",
    "harness/gate_runner/gate_runner.py",
    "harness/orchestration/coordinator.py",
    "harness/orchestration/coordinator_cli.py",
    "scripts/build_registry.py",
    "scripts/build_release.py",
    "scripts/check_license_headers.py",
    "scripts/test_clean_room.py",
    "scripts/verify.py",
    # Rust runtime entry point and crate roots.
    "native/harness-runtime/crates/contracts/src/lib.rs",
    "native/harness-runtime/crates/engine/src/lib.rs",
    "native/harness-runtime/crates/harness-runtime/src/main.rs",
    "native/harness-runtime/crates/ipc/src/lib.rs",
    "native/harness-runtime/crates/platform-ffi/src/lib.rs",
    "native/harness-runtime/crates/qa/src/lib.rs",
    "native/harness-runtime/crates/state/src/lib.rs",
    "native/harness-runtime/crates/supervisor/src/lib.rs",
)


def expected_lines(relative: str) -> tuple[str, ...]:
    """Return the header of one file, commented in the syntax of its language."""
    prefix = COMMENT_PREFIX.get(Path(relative).suffix)
    if prefix is None:
        raise ValueError(f"{relative}: no comment prefix for this file type")
    return tuple(f"{prefix} {line}" for line in HEADER)


def header_problems(root: Path, relative: str) -> list[str]:
    """Compare the beginning of one protected file with the canonical header."""
    path = root / relative
    if not path.is_file():
        return [f"{relative}: protected file is missing"]
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as error:
        return [f"{relative}: not UTF-8 text ({error})"]
    expected = expected_lines(relative)
    offset = 1 if lines and lines[0].startswith("#!") else 0
    found = tuple(lines[offset : offset + len(expected)])
    if found == expected:
        return []
    if not found or found[0] != expected[0]:
        return [f"{relative}: missing license header"]
    problems = []
    for index, (want, have) in enumerate(zip(expected, found), start=1):
        if want != have:
            problems.append(
                f"{relative}:{offset + index}: header line differs; "
                f"expected {want!r}, found {have!r}"
            )
    if len(found) < len(expected):
        problems.append(
            f"{relative}:{offset + len(found) + 1}: header is truncated; "
            f"expected {len(expected)} lines, found {len(found)}"
        )
    return problems


def registry_problems() -> list[str]:
    """Validate the registry itself: no duplicates and only supported file types."""
    problems = []
    seen: set[str] = set()
    for relative in PROTECTED_FILES:
        if relative in seen:
            problems.append(f"{relative}: listed twice in the registry")
        seen.add(relative)
        if Path(relative).suffix not in COMMENT_PREFIX:
            problems.append(f"{relative}: no comment prefix for this file type")
    return problems


def check(root: Path) -> list[str]:
    """Return every registry or header problem under `root`."""
    problems = registry_problems()
    for relative in PROTECTED_FILES:
        problems.extend(header_problems(root, relative))
    return problems


def main(argv: list[str] | None = None) -> int:
    """Check every protected file and return a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="repository root to check (default: the checkout containing this script)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    problems = [f"{root}: not a directory"] if not root.is_dir() else check(root)
    if problems:
        print("License header check failed:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print(f"License header check passed ({len(PROTECTED_FILES)} core files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
