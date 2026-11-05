"""Unit tests of the store-aware batch history and the lazy recovery gate."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from harness.console.kernel.batch_history import (
    BatchHistorySource,
    HistoryBatch,
    load_history,
    recovery_reason,
)
from harness.console.kernel import i18n
from harness.console.kernel.container_route import State
from harness.console.kernel.coordinator_api import CoordinatorApi

REPO = Path("/work/project")


class Runner:
    def __init__(self) -> None:
        self.replies: dict[str, tuple[str, str, int]] = {}
        self.calls: list[list[str]] = []

    def reply(
        self, key: str, document: object = None, *, stderr: str = "", code: int = 0
    ) -> None:
        self.replies[key] = (
            "" if document is None else json.dumps(document),
            stderr,
            code,
        )

    def __call__(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> "subprocess.CompletedProcess[str]":
        words = list(argv)
        self.calls.append(words)
        at = words.index("--repo") + 2
        key = " ".join(words[at : at + 2])
        out, err, code = self.replies.get(key, ("", f"ERROR: no reply for {key}", 2))
        return subprocess.CompletedProcess(words, code, out, err)

    def commands(self) -> list[str]:
        return [
            " ".join(c[c.index("--repo") + 2 : c.index("--repo") + 4])
            for c in self.calls
        ]


def batch(
    batch_id: str, created: str, state: str = "active", **extra: object
) -> dict[str, object]:
    item: dict[str, object] = {
        "batch_id": batch_id,
        "ticket": "#711",
        "branch": "feature/x",
        "state": state,
        "created_at": created,
        "terminal": False,
        "dispatches": 3,
        "open_dispatches": 1,
        "next_action": "developer",
    }
    item.update(extra)
    return item


def clean_status() -> dict[str, object]:
    return {
        "resumable": True,
        "hold": None,
        "intent": None,
        "lifecycle": {"state": "active", "stopped": False, "needs_attention": False},
        "diagnostics": [],
    }


def test_history_lists_batches_from_batch_list_newest_first() -> None:
    runner = Runner()
    runner.reply(
        "batch list",
        {"batches": [batch("b-old", "2026-01-01"), batch("b-new", "2026-03-01")]},
    )
    history = load_history(CoordinatorApi(REPO, runner))
    assert [item.batch_id for item in history.batches] == ["b-new", "b-old"]
    assert history.unavailable == ""
    assert runner.commands() == ["batch list"]
    assert history.find("b-old") is not None and history.find("none") is None


def test_a_batch_label_is_one_line_with_ticket_state_and_open_dispatches() -> None:
    item = HistoryBatch.of(batch("b-1", "2026-01-01"))
    assert item.label == "#711 · active · b-1 · 1 открытых"
    assert (
        HistoryBatch.of(batch("b-2", "2026-01-01", open_dispatches=0)).label
        == "#711 · active · b-2"
    )


def test_an_unreadable_batch_list_is_unavailable_text_not_an_empty_history() -> None:
    runner = Runner()
    runner.reply(
        "batch list", None, stderr="ERROR: runtime down\nREMEDY: start it", code=2
    )
    history = load_history(CoordinatorApi(REPO, runner))
    assert (
        history.batches == ()
        and history.unavailable == "ERROR: runtime down\nREMEDY: start it"
    )
    runner.reply("batch list", {"unexpected": True})
    assert load_history(CoordinatorApi(REPO, runner)).batches == ()


def test_rows_without_a_batch_id_are_dropped_and_counts_may_be_lists() -> None:
    runner = Runner()
    runner.reply(
        "batch list",
        {
            "batches": [
                {"state": "x"},
                batch("b-1", "2026", dispatches=["d1", "d2"], open_dispatches=[]),
            ]
        },
    )
    history = load_history(CoordinatorApi(REPO, runner))
    assert [(b.batch_id, b.dispatches, b.open_dispatches) for b in history.batches] == [
        ("b-1", 2, 0)
    ]


def test_recovery_is_checked_lazily_only_for_the_selected_batch_and_cached() -> None:
    runner = Runner()
    runner.reply(
        "batch list",
        {"batches": [batch("b-1", "2026-01-01"), batch("b-2", "2026-02-01")]},
    )
    runner.reply("recovery status", clean_status())
    source = BatchHistorySource(REPO, runner)
    source.reload()
    assert runner.commands() == ["batch list"]  # nothing probed for the list
    source.recovery_entry("b-1")
    source.recovery_entry("b-1")
    assert runner.commands() == ["batch list", "recovery status"]
    call = runner.calls[-1]
    assert call[call.index("--batch") + 1] == "b-1"
    source.forget("b-1")
    source.recovery_entry("b-1")
    assert runner.commands().count("recovery status") == 2


def test_open_recovery_is_offered_for_a_hold_with_the_cores_message() -> None:
    runner = Runner()
    status = clean_status()
    status["hold"] = {
        "reason": "unknown-value",
        "message": "batch b-1 holds an unlisted state",
    }
    runner.reply("recovery status", status)
    entry = BatchHistorySource(REPO, runner).recovery_entry("b-1")
    assert (
        entry.enabled
        and entry.state is State.WARN
        and entry.reason == "batch b-1 holds an unlisted state"
    )


def test_open_recovery_is_offered_for_an_unfinished_or_interrupted_operation() -> None:
    for status_name in ("pending", "interrupted"):
        status = clean_status()
        status["intent"] = {"action": "resume", "status": status_name}
        reason = recovery_reason(status)
        assert f"resume ({status_name})" in reason
    done = clean_status()
    done["intent"] = {"action": "resume", "status": "done"}
    assert recovery_reason(done) == ""


def test_open_recovery_is_offered_for_a_stopped_batch_attention_or_a_diagnostic() -> (
    None
):
    stopped = clean_status()
    stopped["lifecycle"] = {"stopped": True}
    assert recovery_reason(stopped) == "batch остановлен"
    attention = clean_status()
    attention["lifecycle"] = {
        "needs_attention": True,
        "attention_reason": "worker lost",
    }
    assert recovery_reason(attention) == "worker lost"
    diagnosed = clean_status()
    diagnosed["diagnostics"] = [{"code": "config-invalid", "message": "bad mode"}]
    assert recovery_reason(diagnosed) == "bad mode"


def test_a_clean_batch_gets_no_open_recovery_entry() -> None:
    runner = Runner()
    runner.reply("recovery status", clean_status())
    entry = BatchHistorySource(REPO, runner).recovery_entry("b-1")
    assert not entry.enabled and entry.state is State.OK


def test_a_status_the_core_did_not_give_is_not_checked_never_no_recovery_needed() -> (
    None
):
    runner = Runner()
    runner.reply(
        "recovery status",
        None,
        stderr="ERROR: the file ledger keeps no recovery records",
        code=2,
    )
    entry = BatchHistorySource(REPO, runner).recovery_entry("b-1")
    assert not entry.enabled and entry.state is State.NOT_CHECKED
    assert (
        entry.reason == "не проверено: ERROR: the file ledger keeps no recovery records"
    )


def test_a_refusal_document_with_a_diagnostic_still_opens_recovery() -> None:
    runner = Runner()
    status = clean_status()
    status["diagnostics"] = [{"code": "config-invalid", "message": "bad mode"}]
    runner.reply("recovery status", status, code=2)  # a refusal: a document plus exit 2
    entry = BatchHistorySource(REPO, runner).recovery_entry("b-1")
    assert entry.enabled and entry.reason == "bad mode"


def test_a_batch_label_translates_to_english_with_no_russian_left() -> None:
    label = HistoryBatch.of(batch("b-1", "2026-01-01")).label
    assert i18n.tr_text("en", label) == "#711 · active · b-1 · 1 open"
    unreported = HistoryBatch.of({"batch_id": "b-3"}).label
    assert "не сообщается" not in i18n.tr_text("en", unreported)
