"""Candidate-installed memory and health run without the source repository."""

import json
import os
import subprocess
import sys
from pathlib import Path

CLI = Path(__file__).resolve().parents[2] / "harness/bin/harness.py"


def test_installed_search_cli_returns_pointers_without_source_or_writes(
    tmp_path: Path,
) -> None:
    """A target project can run read-only memory search with just its installed payload."""
    from .test_build import configure, source

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    install = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "init",
            str(tmp_path),
            "--capability",
            "engineering-suite",
            "--qa-gate-command",
            "true",
        ],
        capture_output=True,
        text=True,
    )
    assert install.returncode == 0, install.stderr
    configure(tmp_path)
    source(tmp_path, "CONTEXT.md", "# Glossary\nStatus: accepted\ntransaction")
    build = subprocess.run(
        [sys.executable, str(CLI), "memory", "build", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    cache = tmp_path / ".harness/.sandboxes/cache/memory"
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in cache.iterdir()}
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(tmp_path / ".harness/memory/search_cli.py"),
            str(tmp_path),
            "transaction",
        ],
        cwd=tmp_path.parent,
        env={**os.environ, "PYTHONPATH": ""},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["status"] == "ok"
    assert len(data["pointers"]) == 1
    assert data["pointers"][0]["path"] == "CONTEXT.md"
    assert data["pointers"][0]["status"] == "accepted"
    assert {
        p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in cache.iterdir()
    } == before
    assert not (tmp_path / ".harness/bin/harness.py").exists()
