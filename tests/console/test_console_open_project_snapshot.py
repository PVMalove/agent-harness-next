"""The «Открыть проект» and «Справка» snapshots: their wire codecs, the facts the console server
collects for the one project it serves and the installation it runs as a server job."""

from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Literal, cast

import pytest

from harness.console.backend import composition
from harness.console.kernel.help_text import HelpSections, help_sections
from harness.console.kernel.open_project_snapshot import (
    Candidate,
    OpenProjectFacts,
    open_command,
)
from harness.console.kernel.project_target import ProjectTarget


def _git_project(path: Path) -> Path:
    (path / ".git").mkdir(parents=True)
    return path.resolve()


@pytest.fixture
def git_toplevel(monkeypatch: pytest.MonkeyPatch) -> None:
    """`git -C <path> rev-parse --show-toplevel` answers the path itself when it holds `.git`."""
    def rev_parse(
        argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        path = Path(argv[2])
        if (path / ".git").exists():
            return subprocess.CompletedProcess(argv, 0, f"{path}\n", "")
        return subprocess.CompletedProcess(argv, 128, "", "fatal: not a git repository")

    monkeypatch.setattr(subprocess, "run", rev_parse)


def test_the_help_sections_are_the_guide_split_at_its_second_level_headings() -> None:
    sut = help_sections("en")

    assert sut.intro.startswith("# ")
    assert [title for title, _ in sut.sections][:3] == [
        "Console window",
        "Sections",
        "Keys",
    ]
    assert all(body.startswith(f"## {title}\n") for title, body in sut.sections)
    payload = sut.to_payload()
    first = cast(list[dict[str, object]], payload["sections"])[0]
    assert set(first) == {"title", "markdown"} and first["title"] == "Console window"
    assert HelpSections.from_payload(payload) == sut


@pytest.mark.parametrize(
    "payload",
    [
        {"language": "en", "intro": "# x"},
        {"language": "en", "intro": "# x", "sections": [], "extra": 1},
        {"language": "de", "intro": "# x", "sections": []},
        {"language": "en", "intro": 1, "sections": []},
        {"language": "en", "intro": "# x", "sections": [["a", "## a"]]},
        {"language": "en", "intro": "# x", "sections": [{"title": "a", "markdown": 2}]},
        {"language": "en", "intro": "# x", "sections": [{"title": "a"}]},
    ],
)
def test_a_help_snapshot_off_the_schema_is_refused(payload: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        HelpSections.from_payload(payload)


def test_the_command_for_another_project_starts_the_web_console_there() -> None:
    assert open_command("/work/other") == "harness console --web /work/other"


def test_the_open_project_facts_round_trip_and_off_schema_is_refused() -> None:
    sut = OpenProjectFacts(
        repo="/work/project",
        target=ProjectTarget(
            Path("/work/project"),
            "update",
            ("engineering-suite",),
            (".claude/skills",),
            ("AGENTS.md", ".claude/skills"),
        ),
        error="",
        blockers={"engineering-suite": (), "backend-orchestration": ("AGENTS.md",)},
        candidates=(
            Candidate("/work/project", installed=True, current=True),
            Candidate("/work/other", installed=False, current=False),
        ),
    )

    payload = sut.to_payload()

    assert OpenProjectFacts.from_payload(payload) == sut
    candidates = cast(list[dict[str, object]], payload["candidates"])
    assert candidates[1]["command"] == "harness console --web /work/other"
    for broken in (
        {**payload, "extra": 1},
        {
            **payload,
            "target": {**cast(dict[str, object], payload["target"]), "action": "x"},
        },
        {**payload, "candidates": [{"path": "/x", "installed": True}]},
    ):
        with pytest.raises(ValueError):
            OpenProjectFacts.from_payload(broken)


@pytest.mark.usefixtures("git_toplevel")
def test_the_served_project_comes_first_then_its_git_siblings_with_their_installation(
    tmp_path: Path,
) -> None:
    from harness.console.backend.infrastructure.screen_facts import open_project_facts

    project = _git_project(tmp_path / "project")
    installed = _git_project(tmp_path / "alpha")
    (installed / ".harness").mkdir()
    (installed / ".harness" / "harness.lock").write_text("{}", encoding="utf-8")
    worktree = (tmp_path / "beta").resolve()
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")
    (tmp_path / "plain").mkdir()
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")

    sut = OpenProjectFacts.from_payload(open_project_facts(project))

    assert sut.candidates == (
        Candidate(str(project), installed=False, current=True),
        Candidate(str(installed), installed=True, current=False),
        Candidate(str(worktree), installed=False, current=False),
    )
    assert sut.repo == str(project) and sut.error == ""
    assert sut.target is not None and sut.target.action == "init"
    assert sut.target.capabilities == ()
    assert set(sut.blockers) >= {"project-foundation", "engineering-suite"}
    assert sut.blockers["engineering-suite"] == ()
    assert composition.screen_service(project)._collect_open_project is (
        open_project_facts
    )


@pytest.mark.usefixtures("git_toplevel")
def test_a_served_directory_that_is_not_a_git_project_has_no_target_but_a_reason(
    tmp_path: Path,
) -> None:
    from harness.console.backend.infrastructure.screen_facts import open_project_facts

    folder = (tmp_path / "folder").resolve()
    folder.mkdir()

    sut = OpenProjectFacts.from_payload(open_project_facts(folder))

    assert sut.target is None and sut.blockers == {}
    assert sut.error.startswith("Это не Git-проект")
    assert sut.candidates == (Candidate(str(folder), installed=False, current=True),)


@pytest.mark.parametrize("action", ["init", "adopt", "update"])
def test_the_job_service_installs_the_chosen_capability_into_the_served_project(
    tmp_path: Path, action: str
) -> None:
    from harness.console.backend.application.jobs import JobService
    from harness.console.backend.domain.jobs import JobRejected
    from harness.console.kernel.catalog import SETUP_COMMANDS

    ran: list[list[str]] = []

    async def executor(
        argv: object, *, cwd: Path, on_output: object, cancel_event: object
    ) -> int:
        ran.append(list(cast(list[str], argv)))
        cast(Callable[[str, str], None], on_output)("stdout", "ok")
        return 0

    async def scenario() -> None:
        served = composition.job_service(tmp_path, executor=executor)
        start = {
            "command_id": f"setup-{action}",
            "values": {"capability": "engineering-suite"},
            "client": "tui",
        }
        # The served command needs the operator's confirmation: it overwrites managed files.
        with pytest.raises(JobRejected) as refused:
            served.start(start)
        assert refused.value.code == "confirmation_required" and ran == []
        sut = JobService(
            tmp_path,
            catalog={entry.key: entry for entry in SETUP_COMMANDS},
            executor=executor,
            journal=lambda repo, record: None,
            new_id=lambda: "job-1",
            now=lambda: "t",
        )

        job = sut.start({**start, "confirmed": True})
        while job.phase == "running":
            await asyncio.sleep(0.01)

        assert (job.phase, job.returncode) == ("completed", 0)
        assert ran[0][-4:] == [
            action,
            str(tmp_path),
            "--capability",
            "engineering-suite",
        ]
        assert {entry.key for entry in SETUP_COMMANDS} == {
            "setup-init",
            "setup-adopt",
            "setup-update",
        }

    asyncio.run(scenario())


@pytest.mark.parametrize("action", ["init", "adopt", "update"])
def test_the_shown_installation_command_is_the_one_the_server_job_runs(action: str) -> None:
    from harness.console.kernel.catalog import SETUP_COMMANDS
    from harness.console.kernel.project_target import installation_entry

    repo = Path("/work/project")
    target = ProjectTarget(repo, cast(Literal["init", "adopt", "update"], action), (), ())
    served = next(entry for entry in SETUP_COMMANDS if entry.key == f"setup-{action}")

    sut = installation_entry(target, "engineering-suite")

    assert sut.cli_argv(repo) == served.cli_argv(repo, {"capability": "engineering-suite"})
    assert (sut.key, sut.title, sut.reversibility, sut.function) == (
        served.key,
        served.title,
        served.reversibility,
        served.function,
    )
    assert sut.inputs == ()
