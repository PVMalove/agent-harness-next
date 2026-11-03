"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

from pathlib import Path

from harness.console.runner import HarnessRuns, capturing_runner


def test_cancelled_pending_run_cannot_start_later(tmp_path: Path) -> None:
    runs = HarnessRuns()
    run = runs.reserve("pending", "pending", ["missing"], {})
    assert run is not None
    runs.abandon_pending(run)
    replacement = runs.reserve("new", "new", [], {})
    assert replacement is not None
    runs.execute(run, capturing_runner, tmp_path)
    assert run.phase == "cancelled" and replacement.phase == "pending" and runs.busy
