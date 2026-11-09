"""The ticket status writer: its argv guard admits only the status-label writes and the blocker
state reads, and the local tracker rewrites only the `**Workflow:**` line inside `.scratch/`."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness.console.backend.domain.task_board import TrackerTicket
from harness.console.backend.infrastructure.ticket_status_writer import (
    StatusWriteError,
    TrackerStatusWriter,
    status_command,
)
from harness.health.project_tracker import ProjectTracker


@pytest.mark.parametrize(
    "argv",
    [
        ["gh", "issue", "edit", "5", "--repo", "github.com/o/r", "--add-label", "status::ready"],
        ["gh", "issue", "edit", "5", "--repo", "github.com/o/r",
         "--remove-label", "status::blocked", "--add-label", "status::ready"],
        ["glab", "issue", "update", "5", "-R", "https://h/g/p", "--label", "status::ready"],
        ["glab", "issue", "update", "5", "-R", "https://h/g/p",
         "--label", "status::ready", "--unlabel", "status::blocked"],
        ["gh", "issue", "view", "77", "--repo", "github.com/o/r", "--json", "state"],
        ["glab", "api", "projects/g%2Fp/issues/77"],
    ],
)  # fmt: skip
def test_the_guard_admits_the_status_commands(argv: list[str]) -> None:
    assert status_command(argv)


@pytest.mark.parametrize(
    "argv",
    [
        ["gh", "issue", "edit", "5", "--repo", "github.com/o/r", "--add-label", "priority::p0"],
        ["gh", "issue", "edit", "5", "--repo", "github.com/o/r",
         "--add-label", "status::ready", "--add-label", "status::blocked"],
        ["gh", "issue", "edit", "5", "--repo", "github.com/o/r",
         "--add-label", "status::ready", "--body", "x"],
        ["gh", "issue", "edit", "-5", "--repo", "github.com/o/r", "--add-label", "status::ready"],
        ["gh", "issue", "close", "5"],
        ["glab", "issue", "update", "5", "-R", "https://h/g/p", "--label", "hitl"],
        ["glab", "issue", "update", "5", "-R", "https://h/g/p",
         "--label", "status::ready", "--title", "x"],
        ["glab", "api", "-X", "PUT", "projects/x"],
        ["gh", "issue", "view", "77", "--repo", "github.com/o/r", "--json", "body"],
    ],
)  # fmt: skip
def test_the_guard_refuses_every_other_command(argv: list[str]) -> None:
    assert not status_command(argv)


def _ticket(ref: str, labels: tuple[str, ...] = ()) -> TrackerTicket:
    return TrackerTicket(ref, 1, "T", None, False, labels, "")


def _writer(tracker: ProjectTracker, calls: list[list[str]], code: int = 0) -> TrackerStatusWriter:
    def run(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, code, "", "boom" if code else "")

    return TrackerStatusWriter(runner=run, resolve=lambda _repo: tracker)


def test_local_write_replaces_only_the_first_workflow_line(tmp_path: Path) -> None:
    ticket = tmp_path / ".scratch" / "f" / "issues" / "01-a.md"
    ticket.parent.mkdir(parents=True)
    ticket.write_text("# A\n**Workflow:** ready\ntext **Workflow:** keep\n", encoding="utf-8")
    writer = _writer(ProjectTracker("local", None, None, "config"), [])

    writer.write(tmp_path, _ticket(".scratch/f/issues/01-a.md"), (), "status::in-progress")

    assert ticket.read_text(encoding="utf-8") == (
        "# A\n**Workflow:** status::in-progress\ntext **Workflow:** keep\n"
    )


def test_local_write_refuses_a_file_outside_scratch(tmp_path: Path) -> None:
    (tmp_path / ".scratch").mkdir()
    outside = tmp_path / "x.md"
    outside.write_text("# X\n", encoding="utf-8")
    writer = _writer(ProjectTracker("local", None, None, "config"), [])

    with pytest.raises(StatusWriteError):
        writer.write(tmp_path, _ticket("x.md"), (), "status::ready")
    with pytest.raises(StatusWriteError):
        writer.write(tmp_path, _ticket(".scratch/../x.md"), (), "status::ready")
    assert outside.read_text(encoding="utf-8") == "# X\n"


def test_local_write_refuses_a_symlink(tmp_path: Path) -> None:
    issues = tmp_path / ".scratch" / "f" / "issues"
    issues.mkdir(parents=True)
    target = tmp_path / "real.md"
    target.write_text("# R\n", encoding="utf-8")
    (issues / "01-a.md").symlink_to(target)
    writer = _writer(ProjectTracker("local", None, None, "config"), [])

    with pytest.raises(StatusWriteError):
        writer.write(tmp_path, _ticket(".scratch/f/issues/01-a.md"), (), "status::ready")
    assert target.read_text(encoding="utf-8") == "# R\n"


def test_a_failed_github_write_raises_with_the_tool_message(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    writer = _writer(ProjectTracker("github", "github.com", "o/r", "config"), calls, code=1)

    with pytest.raises(StatusWriteError, match="boom"):
        writer.write(tmp_path, _ticket("#5"), ("status::ready",), "status::in-progress")
    assert calls[0][:4] == ["gh", "issue", "edit", "5"]


def test_a_ticket_ref_that_is_not_a_number_is_never_passed_to_the_tracker(
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []
    writer = _writer(ProjectTracker("github", "github.com", "o/r", "config"), calls)

    with pytest.raises(StatusWriteError):
        writer.write(tmp_path, _ticket("--help"), (), "status::ready")
    assert calls == []


def test_blocker_state_reads_github_and_gitlab(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def run(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        out = '{"state": "CLOSED"}' if argv[0] == "gh" else '{"state": "opened"}'
        return subprocess.CompletedProcess(argv, 0, out, "")

    github = TrackerStatusWriter(
        runner=run, resolve=lambda _r: ProjectTracker("github", "github.com", "o/r", "config")
    )
    gitlab = TrackerStatusWriter(
        runner=run, resolve=lambda _r: ProjectTracker("gitlab", "h", "g/p", "config")
    )

    assert github.blocker_closed(tmp_path, "#77") is True
    assert gitlab.blocker_closed(tmp_path, "77") is False
    assert github.blocker_closed(tmp_path, "!3") is None
    assert calls == [
        ["gh", "issue", "view", "77", "--repo", "github.com/o/r", "--json", "state"],
        ["glab", "api", "projects/g%2Fp/issues/77"],
    ]
