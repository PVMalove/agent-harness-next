"""Pending human decisions read from a temporary project's ledger files.

Every test writes its own ledger records into a temporary Git repository; nothing reads the real
project ledger, runs the coordinator or reaches a live runtime.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from harness.console.decisions import (
    MAX_DECISIONS,
    DecisionService,
    DecisionsSnapshot,
    collect_decisions,
    respond,
)
from harness.console.server import MESSAGE_LIMIT
from harness.orchestration.core.constants import STATE_REL
from harness.orchestration.worker_observation import PROTOCOL
from harness.storage import storage_path

SHA = "0123456789abcdef" * 4


def _write(repo: Path, directory: str, name: str, record: dict[str, object]) -> None:
    path = repo / STATE_REL / directory / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record), encoding="utf-8")


def _batch(repo: Path, batch_id: str, state: str, **fields: object) -> None:
    _write(
        repo,
        "batches",
        batch_id,
        {
            "batch_id": batch_id,
            "ticket": f"#{batch_id}",
            "state": state,
            "dispatches": [],
            **fields,
        },
    )


def _live_worker(repo: Path, dispatch_id: str, preview: str = '{"cmd": "ls"}') -> str:
    """A working dispatch whose runtime staged one native permission request; returns its digest."""
    launch = "launch-1"
    log = storage_path(repo, "logs", "workers") / launch / "worker.log"
    (log.parent / "control" / "pending").mkdir(parents=True)
    log.write_text("")
    _write(
        repo,
        "dispatches",
        dispatch_id,
        {
            "dispatch_id": dispatch_id,
            "batch_id": "batch-live",
            "state": "working",
            "role": "developer",
            "ticket": "#5",
        },
    )
    _write(
        repo,
        "dispatch-status",
        dispatch_id,
        {
            "dispatch_id": dispatch_id,
            "state": "working",
            "adapter_receipt": {
                "protocol": PROTOCOL,
                "dispatch_id": dispatch_id,
                "launch_id": launch,
                "log_path": str(log),
            },
        },
    )
    raw = json.dumps(
        {
            "dispatch_id": dispatch_id,
            "launch_id": launch,
            "request_id": "request-1",
            "request": {
                "subtype": "can_use_tool",
                "tool_name": "Bash",
                "input_preview": preview,
            },
        }
    ).encode()
    (log.parent / "control" / "pending" / "request.json").write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def _by_kind(snapshot: DecisionsSnapshot) -> dict[str, dict[str, object]]:
    return {item.kind: asdict(item) for item in snapshot.items}


def test_each_pending_decision_kind_is_listed_with_its_context(project: Path) -> None:
    _batch(project, "batch-plan", "planned")
    _batch(
        project,
        "batch-wait",
        "awaiting-approval",
        dispatches=[
            {"dispatch_id": "dispatch-01", "role": "architect", "state": "reported"}
            | {"decision": {"decision": "accept"}}
        ],
    )
    _batch(
        project,
        "batch-report",
        "active",
        dispatches=[
            {"dispatch_id": "dispatch-aa", "role": "code-review", "state": "reported"}
        ],
    )
    _write(
        project,
        "reports",
        "dispatch-aa",
        {
            "dispatch_id": "dispatch-aa",
            "outcome": "completed",
            "blockers": {"status": "none", "details": ""},
            "risks": {"status": "present", "details": "a risk"},
        },
    )
    _batch(project, "batch-attn", "active", needs_attention=True)
    _batch(
        project,
        "batch-live",
        "active",
        dispatches=[
            {"dispatch_id": "dispatch-bb", "role": "developer", "state": "working"}
        ],
    )
    digest = _live_worker(project, "dispatch-bb")
    _batch(
        project,
        "batch-done",
        "completed",
        dispatches=[{"dispatch_id": "dispatch-cc", "role": "qa", "state": "reported"}],
    )

    snapshot = collect_decisions(project)
    found = _by_kind(snapshot)

    assert snapshot.unavailable is False
    assert snapshot.total == len(found) == 5
    assert found["batch-approval"] == {
        "kind": "batch-approval",
        "batch_id": "batch-plan",
        "dispatch_id": None,
        "ticket": "#batch-plan",
        "role": None,
        "reversibility": "terminal-coordinator-action",
        "command_ids": ["batch-approve"],
        "values": {"batch": "batch-plan"},
        "details": {"state": "planned"},
    }
    approval = found["dispatch-approval"]
    assert approval["batch_id"] == "batch-wait"
    assert approval["command_ids"] == ["dispatch-propose", "dispatch-create"]
    assert approval["reversibility"] == "terminal-coordinator-action"
    assert approval["values"] == {"batch": "batch-wait"}
    report = found["report-decision"]
    assert (report["batch_id"], report["dispatch_id"], report["role"]) == (
        "batch-report",
        "dispatch-aa",
        "code-review",
    )
    assert report["command_ids"] == ["batch-decide"]
    assert report["details"] == {
        "outcome": "completed",
        "blockers": "none",
        "risks": "present",
    }
    attention = found["attention"]
    assert attention["batch_id"] == "batch-attn"
    assert attention["command_ids"] == ["batch-attention-resolve"]
    native = found["native-permission"]
    assert (native["batch_id"], native["dispatch_id"], native["role"]) == (
        "batch-live",
        "dispatch-bb",
        "developer",
    )
    assert native["ticket"] == "#5"
    assert native["reversibility"] == "external-change"
    assert native["command_ids"] == [
        "native-permission-allow",
        "native-permission-deny",
    ]
    assert native["values"] == {
        "dispatch": "dispatch-bb",
        "request_id": "request-1",
        "request_sha256": digest,
    }
    assert native["details"] == {"tool_name": "Bash", "input_preview": '{"cmd": "ls"}'}


def test_a_blocked_approval_shows_only_what_blocks_it(project: Path) -> None:
    _batch(
        project,
        "batch-wait",
        "awaiting-approval",
        needs_attention=True,
        dispatches=[
            {"dispatch_id": "dispatch-aa", "role": "developer", "state": "reported"}
        ],
    )
    kinds = sorted(_by_kind(collect_decisions(project)))
    assert kinds == ["attention", "report-decision"]


def test_a_project_without_a_ledger_is_unavailable(project: Path) -> None:
    snapshot = collect_decisions(project)
    assert snapshot.unavailable is True
    assert (snapshot.items, snapshot.total) == ((), 0)


def test_malformed_records_are_skipped(project: Path) -> None:
    _batch(project, "batch-plan", "planned")
    broken = project / STATE_REL / "batches" / "broken.json"
    broken.write_text("{not json")
    _write(project, "batches", "list", {"batch_id": 7, "dispatches": "x"})
    assert [item.kind for item in collect_decisions(project).items] == [
        "batch-approval"
    ]


def test_the_list_is_bounded_and_counts_every_decision(project: Path) -> None:
    for index in range(MAX_DECISIONS + 8):
        _batch(project, f"batch-{index:03d}", "planned")
    snapshot = collect_decisions(project)
    assert len(snapshot.items) == MAX_DECISIONS
    assert snapshot.total == MAX_DECISIONS + 8


def test_a_long_request_preview_is_clipped_below_the_message_limit(
    project: Path,
) -> None:
    _batch(project, "batch-live", "active")
    _live_worker(project, "dispatch-bb", preview="\x01" * 100_000)
    reply = asyncio.run(
        respond(json.dumps({"id": 1, "type": "decisions.snapshot"}), _service(project))
    )
    assert len(reply.encode("utf-8")) < MESSAGE_LIMIT
    [item] = json.loads(reply)["snapshot"]["items"]
    assert 0 < len(item["details"]["input_preview"]) < 1000


def _service(project: Path) -> DecisionService:
    return DecisionService(project)


def test_respond_answers_and_rejects_like_the_snapshot_protocol(project: Path) -> None:
    _batch(project, "batch-plan", "planned")

    def ask(**fields: object) -> str:
        raw = json.dumps({"id": "q", "type": "decisions.snapshot", **fields})
        return asyncio.run(respond(raw, _service(project)))

    reply = json.loads(ask())
    assert (reply["ok"], reply["type"], reply["id"]) == (
        True,
        "decisions.snapshot",
        "q",
    )
    assert reply["snapshot"]["version"] == 1
    assert reply["snapshot"]["total"] == 1
    assert json.loads(ask(force=True))["error"]["code"] == "bad_request"


def test_a_failed_collect_names_only_the_exception_type(project: Path) -> None:
    def fail(repo: Path) -> DecisionsSnapshot:
        raise OSError("/private/path")

    raw = json.dumps({"id": 2, "type": "decisions.snapshot"})
    reply = asyncio.run(respond(raw, DecisionService(project, collect=fail)))
    assert "private" not in reply
    assert json.loads(reply)["error"] == {
        "code": "collect_failed",
        "message": "OSError",
    }
