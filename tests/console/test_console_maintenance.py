"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

from pathlib import Path

from harness.console.kernel.runner import HarnessRuns, capturing_runner


def test_cancelled_pending_run_cannot_start_later(tmp_path: Path) -> None:
    runs = HarnessRuns()
    run = runs.reserve("pending", "pending", ["missing"], {})
    assert run is not None
    runs.abandon_pending(run)
    replacement = runs.reserve("new", "new", [], {})
    assert replacement is not None
    runs.execute(run, capturing_runner, tmp_path)
    assert run.phase == "cancelled" and replacement.phase == "pending" and runs.busy


def test_the_maintenance_view_survives_its_json_payload(tmp_path: Path) -> None:
    import json

    import pytest

    from harness.cleanup import CleanupPlan, WorktreeFact, plan_digest
    from harness.console.kernel.maintenance import (
        CleanupSummary,
        MaintenanceView,
        Size,
    )

    def plan(mode: str) -> CleanupPlan:
        return {
            "mode": mode,
            "root": str(tmp_path),
            "min_age_hours": 24.0,
            "remove": [
                {"kind": "file", "path": str(tmp_path / "runs" / "x")},
                {"kind": "worktree", "path": str(tmp_path / "wt"), "branch": None},
            ],
            "skipped": [{"path": str(tmp_path / "y"), "reason": "Git unavailable"}],
        }

    soft = CleanupSummary(plan("soft"), {"runs": Size(10, 1)})
    hard = CleanupSummary(plan("hard"), {})
    tree = tmp_path / "wt"
    view = MaintenanceView(
        soft,
        hard,
        [WorktreeFact(tree, "feature/x", 2, ""), WorktreeFact(tmp_path, None, None, "x")],
        tree_sizes={tree: Size(5, 2)},
    )
    payload = json.loads(json.dumps(view.to_payload()))
    assert payload["soft"]["digest"] == plan_digest(soft.plan)
    assert MaintenanceView.from_payload(payload) == view
    broken: dict[str, object]
    for broken in (
        {**payload, "worktrees": [{"path": "p"}]},
        {**payload, "soft": {**payload["soft"], "digest": "forged"}},
        {**payload, "extra": 1},
    ):
        with pytest.raises(ValueError):
            MaintenanceView.from_payload(broken)


def test_a_streaming_runner_gets_the_live_output_callback(tmp_path: Path) -> None:
    import subprocess
    from collections.abc import Callable, Mapping, Sequence

    seen: list[str] = []

    class Streaming:
        streams_output = True

        def __call__(
            self,
            argv: Sequence[str],
            *,
            env: Mapping[str, str] | None = None,
            cwd: Path | None = None,
            on_output: Callable[[str, str], None] | None = None,
        ) -> "subprocess.CompletedProcess[str]":
            assert on_output is not None and run is not None
            on_output("stdout", "part")
            seen.append(run.output)
            return subprocess.CompletedProcess(list(argv), 0, "part", "")

    runs = HarnessRuns()
    run = runs.reserve("health", "harness health", ["harness"], {})
    assert run is not None
    runs.execute(run, Streaming(), tmp_path)
    assert seen == ["part"] and (run.phase, run.stdout) == ("completed", "part")
