"""The command catalog a web client reads with ``job.catalog``: the descriptions of a section's
catalog commands, built by the server from its own catalog, and the ``mutating`` flag of a job."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast

import pytest

from harness.console.backend import composition
from harness.console.backend.api.protocol.jobs import replies
from harness.console.backend.application.jobs import JobService
from harness.console.backend.domain.approvals import CANCEL_KEEPS_CHANGES, CANCEL_REASON
from harness.console.backend.domain.jobs import COMMAND_SECTIONS, JobRejected
from harness.console.kernel import i18n
from harness.console.kernel.catalog import (
    CONFIRMATION_REASONS,
    HARNESS_COMMANDS,
    HARNESS_MENU_HIDDEN,
    REVERSIBILITY_LABELS,
    Reversibility,
)


async def _idle(argv: object, *, cwd: Path, on_output: object, cancel_event: object) -> int:
    return 0


def _served(repo: Path) -> JobService:
    return composition.job_service(repo, executor=_idle)


def test_the_harness_section_lists_the_menu_commands_without_the_update_screen_ones(
    tmp_path: Path,
) -> None:
    listed = _served(tmp_path).commands("harness")
    keys = [command["command_id"] for command in listed]
    assert keys == [
        entry.key for entry in HARNESS_COMMANDS if entry.key not in HARNESS_MENU_HIDDEN
    ]
    assert HARNESS_MENU_HIDDEN == {
        "init",
        "update",
        "update-force-managed",
        "update-force-seed",
        "adopt",
    }
    assert all(command["section"] == "harness" for command in listed)


def test_a_description_carries_what_the_confirmation_dialog_needs(tmp_path: Path) -> None:
    by_key = {
        command["command_id"]: command for command in _served(tmp_path).commands("harness")
    }
    hard = by_key["cleanup-hard-apply"]
    assert hard["typed_confirmation"] == "HARD"
    assert hard["reversibility"] == Reversibility.DELETES_LOCAL_DATA.value
    assert hard["needs_confirmation"] is True and hard["plan_required"] is True
    assert hard["read_only"] is False
    assert by_key["cleanup-apply"]["plan_required"] is True
    diff = by_key["diff"]
    assert diff == {
        "command_id": "diff",
        "title": "Дрейф управляемых файлов",
        "section": "harness",
        "reversibility": "reversible",
        "reversibility_label": REVERSIBILITY_LABELS[Reversibility.REVERSIBLE],
        "needs_confirmation": False,
        "confirmation_reason": None,
        "typed_confirmation": None,
        "read_only": True,
        "inputs": [],
        "plan_required": False,
        "available": True,
    }
    assert by_key["worktree-remove"]["inputs"] == ["worktree"]
    # Every irreversible class the list shows has its confirmation reason.
    for command in by_key.values():
        if command["needs_confirmation"]:
            assert Reversibility(command["reversibility"]) in CONFIRMATION_REASONS


def test_the_label_and_the_confirmation_reason_are_the_kernel_catalog_texts(
    tmp_path: Path,
) -> None:
    served = _served(tmp_path)
    listed = [command for section in COMMAND_SECTIONS for command in served.commands(section)]
    classes = {Reversibility(command["reversibility"]) for command in listed}
    assert classes >= {Reversibility.REVERSIBLE, Reversibility.DELETES_LOCAL_DATA}
    for command in listed:
        reversibility = Reversibility(command["reversibility"])
        assert command["reversibility_label"] == REVERSIBILITY_LABELS[reversibility]
        assert command["confirmation_reason"] == CONFIRMATION_REASONS.get(reversibility)
    by_key = {command["command_id"]: command for command in listed}
    assert by_key["uninstall-apply"]["confirmation_reason"] == (
        "Команда удаляет локальные данные — восстановить их нельзя."
    )
    assert by_key["uninstall-apply"]["reversibility_label"] == "✖ удаление"


def test_availability_is_computed_for_the_served_project(tmp_path: Path) -> None:
    by_key = {
        command["command_id"]: command for command in _served(tmp_path).commands("harness")
    }
    unavailable = [key for key, command in by_key.items() if not command["available"]]
    assert unavailable, "a project without the coordinator script lacks its commands"
    coordinator = tmp_path / ".harness" / "orchestration" / "coordinator.py"
    coordinator.parent.mkdir(parents=True)
    coordinator.write_text("", encoding="utf-8")
    again = {
        command["command_id"]: command for command in _served(tmp_path).commands("harness")
    }
    assert any(again[key]["available"] for key in unavailable)


def test_every_section_lists_only_kernel_catalog_entries(tmp_path: Path) -> None:
    served = _served(tmp_path)
    assert set(COMMAND_SECTIONS) == {
        "harness",
        "diagnostics",
        "repo-map",
        "setup",
        "configuration",
        "memory",
        "decisions",
        "recovery",
        "update",
    }
    listed = {section: served.commands(section) for section in COMMAND_SECTIONS}
    assert [c["command_id"] for c in listed["diagnostics"]] == [
        "diagnostics-fix",
        "diagnostics-online-fix",
    ]
    every = {str(c["command_id"]) for commands in listed.values() for c in commands}
    # Decisions have their own catalog; they are not offered as general section commands.
    assert "update-seed-selected" in every
    decisions = {str(c["command_id"]) for c in listed["decisions"]}
    assert decisions == {
        "batch-approve", "batch-decide", "batch-attention-resolve",
        "dispatch-propose", "dispatch-create", "native-permission-allow", "native-permission-deny",
    }
    assert not any(
        str(c["command_id"]).startswith(("batch-", "dispatch-", "native-"))
        for section, commands in listed.items() if section != "decisions" for c in commands
    )
    recovery = [str(c["command_id"]) for c in listed["recovery"]]
    assert recovery == [
        "recovery-reload",
        "recovery-resume",
        "recovery-fix",
        "recovery-fix-apply",
        "recovery-abort",
    ]
    assert not any(
        str(c["command_id"]).startswith("recovery-")
        for section, commands in listed.items() if section != "recovery" for c in commands
    )
    with pytest.raises(JobRejected) as refused:
        served.commands("coordinator")
    assert refused.value.code == "bad_request"


def test_the_update_section_lists_the_three_update_modes_behind_a_confirmation(
    tmp_path: Path,
) -> None:
    served = _served(tmp_path)
    listed = {section: served.commands(section) for section in COMMAND_SECTIONS}
    update = listed["update"]
    assert [c["command_id"] for c in update] == [
        "update",
        "update-force-managed",
        "update-seed-selected",
    ]
    assert all(c["needs_confirmation"] is True and c["section"] == "update" for c in update)
    assert not any(
        c["command_id"] in {"update", "update-force-managed", "update-seed-selected"}
        for section, commands in listed.items() if section != "update" for c in commands
    )
    with pytest.raises(JobRejected) as refused:
        served.start({"command_id": "update", "client": "browser"})
    assert refused.value.code == "confirmation_required"


def test_a_job_summary_says_whether_the_job_holds_the_mutation_slot(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        # The catalog entries with an in-memory journal: the real one resolves Git.
        served = JobService(
            tmp_path,
            catalog={entry.key: entry for entry in HARNESS_COMMANDS},
            executor=_idle,
            journal=lambda repo, record: None,
            new_id=iter(("job-1", "job-2")).__next__,
            now=lambda: "t",
        )
        read = served.start({"command_id": "diff", "client": "browser"})
        write = served.start({"command_id": "registry", "client": "browser"})
        assert read.summary()["mutating"] is False
        assert write.summary()["mutating"] is True
        await served.close()
        summaries = {job["command_id"]: job for job in served.jobs()}
        assert summaries["registry"]["mutating"] is True

    asyncio.run(scenario())


def _reply(raw: dict[str, object], served: JobService) -> list[dict[str, object]]:
    async def collect() -> list[dict[str, object]]:
        return [json.loads(text) async for text in replies(json.dumps(raw), served)]

    return asyncio.run(collect())


def test_the_catalog_request_answers_once_and_refuses_an_unknown_section_or_field(
    tmp_path: Path,
) -> None:
    served = _served(tmp_path)
    [answer] = _reply({"id": 1, "type": "job.catalog", "section": "harness"}, served)
    assert answer["ok"] is True and answer["type"] == "job.catalog"
    assert answer["commands"] == served.commands("harness")
    # The cancel warning is the server's own text: its English is the refusal message.
    assert answer["cancel_reason"] == CANCEL_REASON
    assert CANCEL_REASON == "Отмена останавливает команду; уже внесённые изменения не откатываются."
    assert i18n.tr_text("en", CANCEL_REASON) == CANCEL_KEEPS_CHANGES
    for broken in (
        {"id": 2, "type": "job.catalog", "section": "harness", "extra": 1},
        {"id": 3, "type": "job.catalog", "section": "nowhere"},
        {"id": 4, "type": "job.catalog"},
    ):
        [refusal] = _reply(broken, served)
        assert refusal["ok"] is False
        error = cast(dict[str, object], refusal["error"])
        assert error["code"] == "bad_request", broken
