"""The board status change on the console server: `board-status` never starts without a
confirmation, runs as the project's one mutating job with the CLI argv of `harness ticket-status`,
and is refused `busy` with the running job while another mutation holds the slot."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from harness.console.backend import composition
from harness.console.backend.application.ports import JobExecutor
from harness.console.backend.domain.jobs import JobRejected
from harness.console.backend.infrastructure import command_journal

VALUES = {"spec": "#900", "ticket": "#915", "to": "progress"}


@pytest.fixture(autouse=True)
def _no_journal(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """The command journal resolves the project through Git; these tests keep its entries."""
    entries: list[object] = []
    monkeypatch.setattr(
        command_journal, "append", lambda *args, **kwargs: entries.append(args)
    )
    return entries


def _holding() -> tuple[JobExecutor, list[list[str]], asyncio.Event]:
    started: list[list[str]] = []
    release = asyncio.Event()

    async def executor(
        argv: Sequence[str],
        *,
        cwd: Path,
        on_output: Callable[[str, str], None],
        cancel_event: threading.Event,
    ) -> int:
        started.append(list(argv))
        await release.wait()
        return 0

    return executor, started, release


def test_the_status_change_is_not_started_without_a_confirmation(tmp_path: Path) -> None:
    service = composition.job_service(tmp_path)
    with pytest.raises(JobRejected) as refused:
        service.start({"command_id": "board-status", "values": VALUES})
    assert refused.value.code == "confirmation_required"
    with pytest.raises(JobRejected) as refused:
        service.start({"command_id": "board-status", "values": VALUES, "confirmed": False})
    assert refused.value.code == "confirmation_required"


def test_a_confirmed_change_runs_the_cli_as_a_mutating_job(tmp_path: Path) -> None:
    async def scenario() -> None:
        executor, started, release = _holding()
        service = composition.job_service(tmp_path, executor=executor)
        job = service.start(
            {"command_id": "board-status", "values": VALUES, "confirmed": True}
        )
        assert job.command_id == "board-status"
        assert job.mutating is True
        await asyncio.sleep(0)
        assert started and started[0][2:] == [
            "ticket-status", str(tmp_path),
            "--spec", "#900", "--ticket", "#915", "--to", "progress",
        ]  # fmt: skip
        release.set()
        await service.close()

    asyncio.run(scenario())


def test_a_move_is_refused_busy_while_another_mutation_runs(tmp_path: Path) -> None:
    async def scenario() -> None:
        executor, _, release = _holding()
        service = composition.job_service(tmp_path, executor=executor)
        running = service.start({"command_id": "memory-build", "values": {}})
        with pytest.raises(JobRejected) as refused:
            service.start(
                {"command_id": "board-status", "values": VALUES, "confirmed": True}
            )
        assert refused.value.code == "busy"
        assert refused.value.job_id == running.id
        assert running.id in str(refused.value.message)
        release.set()
        await service.close()

    asyncio.run(scenario())


def test_the_status_change_is_listed_in_no_command_section(tmp_path: Path) -> None:
    service = composition.job_service(tmp_path)
    for section in ("harness", "diagnostics", "setup", "update", "decisions"):
        assert all(
            command["command_id"] != "board-status" for command in service.commands(section)
        )
