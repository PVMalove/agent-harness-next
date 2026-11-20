"""Installed payload of the recovery contract: the systemFields.v1 registry, the canonical example
config, the recovery commands and no superseded Python store (ADR 0026 section 1)."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from scripts.clean_room.support import ROOT, capture, capture_json

SUPERSEDED_MODULES = ("runtime_state_store", "runtime_intent")
RECOVERY_COMMANDS = ("status", "reload", "resume", "fix", "abort")


def run(ctx: SimpleNamespace) -> None:
    """Check the installed registry, example config, recovery help and payload contents.

    Reads from the context: `coordinator_path`, `orchestration_config`, `orchestration_project`.
    """
    project = ctx.orchestration_project
    harness_dir = project / ".harness"
    installed_registry = harness_dir / "orchestration" / "system_fields.v1.json"
    source_registry = ROOT / "harness" / "orchestration" / "system_fields.v1.json"
    if installed_registry.read_bytes() != source_registry.read_bytes():
        sys.exit("installed system_fields.v1.json differs from the source registry")

    revived = sorted(
        str(path.relative_to(project))
        for path in harness_dir.rglob("*")
        if path.stem in SUPERSEDED_MODULES
    )
    if revived:
        sys.exit(f"installed payload ships superseded store modules: {revived}")

    example = harness_dir / "orchestration.example.json"
    if not example.is_file():
        sys.exit("installed orchestration.example.json is missing")
    config = ctx.orchestration_config
    saved = config.read_bytes()
    config.write_bytes(example.read_bytes())
    try:
        report = capture_json(
            [
                sys.executable,
                str(ctx.coordinator_path),
                "--repo",
                str(project),
                "config",
                "validate",
                "--canonical",
                "--json",
            ]
        )
    finally:
        config.write_bytes(saved)
    if report.get("valid") is not True or report.get("diagnostics"):
        sys.exit(
            "installed orchestration.example.json is not canonical: "
            + json.dumps(report.get("diagnostics"), ensure_ascii=False)
        )

    help_text = capture(
        [
            sys.executable,
            str(ctx.coordinator_path),
            "--repo",
            str(project),
            "recovery",
            "--help",
        ]
    )
    missing = [name for name in RECOVERY_COMMANDS if name not in help_text]
    if missing:
        sys.exit(f"installed recovery --help lacks commands: {missing}")
