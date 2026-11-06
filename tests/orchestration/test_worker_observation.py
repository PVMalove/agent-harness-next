"""Read-only worker step pages: allowlisted structure, fail-closed plain logs, typed reasons."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from harness.orchestration.core.utils import JsonObject
from harness.orchestration.worker_observation import (
    external_log_path,
    read_plain_steps,
    read_structured_steps,
    structured_log_path,
)


def _jsonl(path: Path, *records: object) -> Path:
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    return path


def _texts(page: JsonObject) -> str:
    return "\n".join(step["text"] for step in page["steps"])


def test_structured_steps_hide_thinking_tool_inputs_and_raw_json(
    tmp_path: Path,
) -> None:
    log = _jsonl(
        tmp_path / "events.jsonl",
        {"type": "system", "subtype": "init", "session_id": "hidden-session"},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "thinking", "thinking": "SECRET-THOUGHT"},
                    {"type": "text", "text": "Reading the module"},
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {"file_path": "/SECRET-INPUT"},
                    },
                ]
            },
        },
        {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "content": "file body"}]},
        },
        {"type": "stream_event", "event": {"delta": {"thinking": "SECRET-DELTA"}}},
    )
    with log.open("a") as stream:
        stream.write("not json at all SECRET-PLAIN\n")
        stream.write(json.dumps({"type": "result", "result": "done"}) + "\n")

    page = read_structured_steps(log, 0, 48 * 1024)

    assert page["source"] == "structured"
    assert page["structure"] == "available"
    assert page["state"] == "connected"
    assert page["reason"] is None
    assert [(step["kind"], step["text"]) for step in page["steps"]] == [
        ("system", "Runtime session connected"),
        ("output", "Reading the module"),
        ("tool", "Read"),
        ("tool-result", "file body"),
        ("result", "done"),
    ]
    text = _texts(page)
    for hidden in ("SECRET", "{", "file_path", "session_id"):
        assert hidden not in text
    assert page["offset"] == log.stat().st_size
    assert page["reset"] is False
    assert page["more"] is False


def test_structured_steps_continue_from_offset_and_skip_partial_line(
    tmp_path: Path,
) -> None:
    log = _jsonl(tmp_path / "events.jsonl", {"type": "result", "result": "one"})
    first = read_structured_steps(log, 0, 4096)
    with log.open("a") as stream:
        stream.write(json.dumps({"type": "result", "result": "two"}) + "\n")
        stream.write('{"type": "result", "res')

    second = read_structured_steps(log, first["offset"], 4096)

    assert [step["text"] for step in second["steps"]] == ["two"]
    assert second["offset"] < log.stat().st_size
    assert read_structured_steps(log, second["offset"], 4096)["steps"] == []


def test_budget_cuts_the_page_on_a_line_boundary(tmp_path: Path) -> None:
    log = _jsonl(
        tmp_path / "events.jsonl",
        *({"type": "result", "result": "x" * 100} for _ in range(10)),
    )

    page = read_structured_steps(log, 0, 300)

    assert len(page["steps"]) == 2
    assert page["more"] is True
    rest = read_structured_steps(log, page["offset"], 10_000)
    assert len(rest["steps"]) == 8
    assert rest["more"] is False


def test_budget_counts_the_escaped_wire_size_of_each_step(tmp_path: Path) -> None:
    log = _jsonl(
        tmp_path / "events.jsonl",
        *({"type": "result", "result": '"' * 100} for _ in range(4)),
    )

    page = read_structured_steps(log, 0, 480)

    encoded = sum(len(json.dumps(step)) + 1 for step in page["steps"])
    assert len(page["steps"]) == 2
    assert encoded <= 480
    assert page["more"] is True


def test_truncated_log_resets_the_cursor(tmp_path: Path) -> None:
    log = _jsonl(tmp_path / "events.jsonl", {"type": "result", "result": "fresh"})

    page = read_structured_steps(log, 10_000, 4096)

    assert page["reset"] is True
    assert [step["text"] for step in page["steps"]] == ["fresh"]


def test_empty_log_is_waiting(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    log.write_bytes(b"")

    page = read_structured_steps(log, 0, 4096)

    assert page["state"] == "waiting"
    assert page["reason"] is None
    assert page["last_step_age_seconds"] is None


def test_missing_and_unreadable_logs_have_distinct_reasons(tmp_path: Path) -> None:
    missing = read_structured_steps(tmp_path / "absent.jsonl", 0, 4096)
    unreadable = read_plain_steps(tmp_path, 7, 4096)

    assert (missing["state"], missing["reason"]) == ("unavailable", "log_missing")
    assert (unreadable["state"], unreadable["reason"]) == (
        "unavailable",
        "log_unreadable",
    )
    assert unreadable["offset"] == 7
    assert missing["steps"] == [] and missing["message"]
    assert unreadable["source"] == "plain"
    assert unreadable["structure"] == "unavailable"


CODEX_LOG = """\
Codex v0.40.0
model: m
[2026-11-06T08:00:00] User instructions:
[2026-11-06T08:00:01] user
SECRET-PROMPT line
[2026-11-06T08:00:02] thinking
SECRET-REASONING about the task
[2026-11-06T08:00:03] exec bash -lc 'cat SECRET-ARG' in /work
SECRET-COMMAND-OUTPUT
[2026-11-06T08:00:04] codex
I updated the reader.
{"raw": "SECRET-JSON"}
[2026-11-06T08:00:05] apply_patch auto_approved=true: SECRET-PATCH
*** Begin Patch SECRET
[2026-11-06T08:00:06] tokens used: 1200
[2026-11-06T08:00:07] codex
Done.
"""


def test_plain_codex_tail_shows_only_agent_messages_and_tool_names(
    tmp_path: Path,
) -> None:
    log = tmp_path / "dispatch-x.log"
    log.write_text(CODEX_LOG)

    page = read_plain_steps(log, 0, 48 * 1024)

    assert page["source"] == "plain"
    assert page["structure"] == "unavailable"
    assert page["state"] == "connected"
    assert [(step["kind"], step["text"]) for step in page["steps"]] == [
        ("tool", "exec"),
        ("log", "I updated the reader."),
        ("tool", "apply_patch"),
        ("log", "Done."),
    ]
    assert "SECRET" not in _texts(page)


def test_plain_section_at_offset_comes_from_the_last_header_before_it(
    tmp_path: Path,
) -> None:
    log = tmp_path / "dispatch-x.log"
    log.write_text("[t] thinking\nSECRET-1\n[t] codex\nhello\n")
    after_hello = log.stat().st_size
    with log.open("a") as stream:
        stream.write("world\n")
    thinking_offset = len(b"[t] thinking\n")
    with log.open("a") as stream:
        stream.write("[t] thinking\nSECRET-2\n")

    continued = read_plain_steps(log, after_hello, 4096)
    inside_thinking = read_plain_steps(log, thinking_offset, 4096)

    assert [step["text"] for step in continued["steps"]] == ["world"]
    assert [step["text"] for step in inside_thinking["steps"]] == [
        "hello",
        "world",
    ]


def test_plain_lines_before_any_known_header_stay_hidden(tmp_path: Path) -> None:
    log = tmp_path / "dispatch-x.log"
    log.write_text("plain claude text output\nunknown header\n")

    page = read_plain_steps(log, 0, 4096)

    assert page["steps"] == []
    assert page["state"] == "connected"


def test_reading_changes_nothing_and_takes_no_lock(tmp_path: Path) -> None:
    log = _jsonl(tmp_path / "events.jsonl", {"type": "result", "result": "x"})
    before = (log.read_bytes(), log.stat().st_mtime_ns)
    entries = sorted(tmp_path.iterdir())

    read_structured_steps(log, 0, 4096)
    read_plain_steps(log, 0, 4096)

    assert (log.read_bytes(), log.stat().st_mtime_ns) == before
    assert sorted(tmp_path.iterdir()) == entries


def test_observation_starts_no_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("observation must not start a process")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    log = tmp_path / ".harness/.sandboxes/logs/workers/launch-1/events.jsonl"
    log.parent.mkdir(parents=True)
    _jsonl(log, {"type": "result", "result": "x"})
    receipt = {
        "protocol": "harness-worker-v1",
        "dispatch_id": "dispatch-a",
        "log_path": str(log),
    }

    path, _ = structured_log_path(tmp_path, receipt, "dispatch-a")
    external_log_path(
        tmp_path,
        {
            "dispatch_id": "dispatch-a",
            "report_staging_path": str(
                tmp_path / ".harness/.sandboxes/scratch/inbox/x.json"
            ),
        },
    )
    assert path is not None
    assert read_structured_steps(path, 0, 4096)["steps"]


def test_external_log_path_follows_the_adapter_rule(tmp_path: Path) -> None:
    inbox = tmp_path / ".harness/.sandboxes/scratch/inbox"
    dispatch = {
        "dispatch_id": "dispatch-a",
        "report_staging_path": str(inbox / "dispatch-a.json"),
    }

    path, reason = external_log_path(tmp_path, dispatch)

    assert reason is None
    assert (
        path
        == (
            tmp_path / ".harness/.sandboxes/scratch/worker-logs/dispatch-a.log"
        ).resolve()
    )


def test_external_log_path_outside_storage_or_absent_is_typed(tmp_path: Path) -> None:
    outside = {
        "dispatch_id": "dispatch-a",
        "report_staging_path": str(tmp_path / "elsewhere/inbox/dispatch-a.json"),
    }
    escaping = {
        "dispatch_id": "../../../escape",
        "report_staging_path": str(
            tmp_path / ".harness/.sandboxes/scratch/inbox/x.json"
        ),
    }

    assert external_log_path(tmp_path, outside) == (None, "log_outside_storage")
    assert external_log_path(tmp_path, escaping) == (None, "log_outside_storage")
    assert external_log_path(tmp_path, {"dispatch_id": "dispatch-a"}) == (
        None,
        "no_log",
    )


def test_structured_log_path_requires_a_bound_receipt_in_logs_storage(
    tmp_path: Path,
) -> None:
    inside = tmp_path / ".harness/.sandboxes/logs/workers/launch-1/events.jsonl"
    receipt = {
        "protocol": "harness-worker-v1",
        "dispatch_id": "dispatch-a",
        "log_path": str(inside),
    }

    assert structured_log_path(tmp_path, receipt, "dispatch-a") == (
        inside.resolve(),
        None,
    )
    assert structured_log_path(tmp_path, receipt, "dispatch-b") == (None, "no_log")
    assert structured_log_path(tmp_path, None, "dispatch-a") == (None, "no_log")
    assert structured_log_path(
        tmp_path, {**receipt, "log_path": str(tmp_path / "x.jsonl")}, "dispatch-a"
    ) == (None, "log_outside_storage")
