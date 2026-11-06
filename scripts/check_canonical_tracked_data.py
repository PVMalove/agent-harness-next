#!/usr/bin/env python3
"""Read-only canonical check of tracked orchestration configs and their negative fixtures.

Every positive config must pass ``inspect_configuration(canonical=True)``: a value the runtime
normalizer could repair is an error here, not a warning. Each negative fixture is listed in a
manifest with its exact expected diagnostics; a fixture refused for another reason fails the check.
The inventory is complete in both directions: every tracked ``*orchestration*.json`` is a positive
config, a listed negative fixture or a known non-config, and the manifest matches the fixture
directory. The check only reads bytes; it never rewrites or normalizes a file.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from harness.diagnostics import Diagnostic, pointer  # noqa: E402
from harness.orchestration.config_boundary import inspect_configuration  # noqa: E402

POSITIVE = (
    "harness/orchestration.example.json",
    "docs/settings/orchestration.json",
    "scripts/cloud/orchestration.json",
)
NEGATIVE_DIR = "tests/orchestration/fixtures/canonical/negative"
NEGATIVE_MANIFEST = "tests/orchestration/fixtures/canonical/negative_fixtures.json"
# Tracked files the inventory pattern matches which are not orchestration configs.
NOT_CONFIGS = (
    "harness/orchestration/orchestration.schema.json",
    "harness/orchestration/system_fields.v1.json",
    NEGATIVE_MANIFEST,
)
INVENTORY_PATTERN = "*orchestration*.json"


def _line(path: str, item: Diagnostic) -> str:
    data = dataclasses.replace(item, file=path).to_dict()
    allowed = json.dumps(data["expected"], ensure_ascii=False)
    received = json.dumps(data["received_redacted"], ensure_ascii=False)
    return (
        f"{path}:{data['pointer']}: {data['code']}: allowed={allowed}; "
        f"received={received}; {data['message']}"
    )


def _inspect(root: Path, relative: str, roles_root: Path) -> tuple[Diagnostic, ...]:
    raw = (root / relative).read_bytes()
    # An empty repo makes the schema lookup use the shipped source schema, never a stale install.
    with tempfile.TemporaryDirectory() as empty:
        result = inspect_configuration(
            Path(empty), raw, canonical=True, roles_root=roles_root
        )
    return result.diagnostics


def _tracked(root: Path) -> list[str]:
    output = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--", INVENTORY_PATTERN],
        check=True,
        capture_output=True,
    ).stdout.decode()
    return sorted(item for item in output.split("\0") if item)


def _manifest(root: Path) -> tuple[list[dict[str, object]], list[str]]:
    path = root / NEGATIVE_MANIFEST
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        entries = document["fixtures"]
        if not isinstance(entries, list) or not all(
            isinstance(entry, dict)
            and isinstance(entry.get("file"), str)
            and isinstance(entry.get("expected"), list)
            and entry["expected"]
            for entry in entries
        ):
            raise ValueError("every fixture needs a file and a non-empty expected list")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [], [f"{NEGATIVE_MANIFEST}: invalid negative fixture manifest: {exc}"]
    return entries, []


def _negative_problems(
    root: Path, entry: dict[str, object], roles_root: Path
) -> list[str]:
    relative = f"{NEGATIVE_DIR}/{entry['file']}"
    if not (root / relative).is_file():
        return [f"{relative}: listed negative fixture is missing"]
    expected = entry["expected"]
    assert isinstance(expected, list)
    diagnostics = _inspect(root, relative, roles_root)
    actual = Counter((item.code, pointer(item.parts)) for item in diagnostics)
    wanted = Counter((str(item["code"]), str(item["pointer"])) for item in expected)
    problems = []
    if actual != wanted:
        problems.append(
            f"{relative}: expected diagnostics {sorted(wanted.elements())}, "
            f"received {sorted(actual.elements())}"
        )
    for item in expected:
        needle = item.get("message_contains")
        if needle and not any(
            item["code"] == found.code and str(needle) in found.message
            for found in diagnostics
        ):
            problems.append(
                f"{relative}: no {item['code']} diagnostic contains {needle!r}"
            )
    return problems


def check(root: Path = ROOT, roles_root: Path | None = None) -> list[str]:
    """One line per problem; an empty list means the tracked inventory is canonical."""
    roles = roles_root or root / "harness" / "orchestration" / "roles"
    problems: list[str] = []
    for relative in POSITIVE:
        if not (root / relative).is_file():
            problems.append(f"{relative}: listed positive config is missing")
            continue
        problems.extend(
            _line(relative, item) for item in _inspect(root, relative, roles)
        )
    entries, manifest_problems = _manifest(root)
    problems.extend(manifest_problems)
    listed = [f"{NEGATIVE_DIR}/{entry['file']}" for entry in entries]
    for name, count in Counter(listed).items():
        if count > 1:
            problems.append(f"{name}: negative fixture is listed more than once")
    directory = root / NEGATIVE_DIR
    present = (
        sorted(
            f"{NEGATIVE_DIR}/{path.name}"
            for path in directory.iterdir()
            if path.is_file()
        )
        if directory.is_dir()
        else []
    )
    problems.extend(
        f"{name}: unlisted negative fixture; add it to {NEGATIVE_MANIFEST}"
        for name in present
        if name not in listed
    )
    for entry in entries:
        problems.extend(_negative_problems(root, entry, roles))
    known = {*POSITIVE, *NOT_CONFIGS, *listed}
    problems.extend(
        f"{name}: unlisted tracked config; add it to POSITIVE or {NEGATIVE_MANIFEST}"
        for name in _tracked(root)
        if name not in known
    )
    return problems


def main() -> int:
    problems = check()
    for line in problems:
        print(line, file=sys.stderr)
    if problems:
        print(f"canonical-tracked-data: {len(problems)} problem(s)", file=sys.stderr)
        return 1
    print("canonical-tracked-data: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
