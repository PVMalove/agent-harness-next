"""Browser decisions over real FastAPI sockets; only the external command executor is replaced."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import threading
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from websockets.asyncio.client import connect
from websockets.typing import Origin

from harness.console.backend import composition
from harness.console.backend.server import ConsoleServer
from harness.console.kernel import web_catalog
from harness.orchestration.core.constants import STATE_REL
from harness.orchestration.runtime_permissions import stage_request
from harness.orchestration.worker_observation import PROTOCOL
from harness.storage import storage_path


def _project(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    coordinator = repo / ".harness/orchestration/coordinator.py"
    coordinator.parent.mkdir(parents=True)
    coordinator.write_text("", encoding="utf-8")
    root = repo / STATE_REL
    records = {
        "batches/proposal": {
            "batch_id": "batch-proposal",
            "ticket": "#884",
            "state": "awaiting-approval",
        },
        "batches/report": {
            "batch_id": "batch-report",
            "ticket": "#884",
            "state": "active",
            "dispatches": [
                {
                    "dispatch_id": "dispatch-bbbb",
                    "role": "developer",
                    "state": "reported",
                }
            ],
        },
        "reports/report": {
            "dispatch_id": "dispatch-bbbb",
            "outcome": "success",
            "blockers": {"status": "none"},
        },
        "dispatches/native": {
            "batch_id": "batch-proposal",
            "dispatch_id": "dispatch-aaaa",
            "ticket": "#884",
            "role": "developer",
            "state": "working",
        },
        "dispatch-status/native": {
            "dispatch_id": "dispatch-aaaa",
            "state": "working",
            "adapter_receipt": {
                "protocol": PROTOCOL,
                "dispatch_id": "dispatch-aaaa",
                "launch_id": "launch-1",
                "log_path": str(
                    storage_path(repo, "logs", "workers", "launch-1", "worker.log")
                ),
            },
        },
    }
    for name, record in records.items():
        path = root / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record), encoding="utf-8")
    control = storage_path(repo, "logs", "workers", "launch-1", "control")
    (control / "pending").mkdir(parents=True)
    stage_request(
        control,
        {"dispatch_id": "dispatch-aaaa"},
        "launch-1",
        {
            "request_id": "request-7",
            "request": {"tool_name": "Read", "input": {"file_path": "example.py"}},
        },
    )


@pytest.mark.parametrize(
    "command,values",
    [
        (
            "native-permission-deny",
            {
                "dispatch": "dispatch-aaaa",
                "request_id": "request-7",
                "request_sha256": "a" * 64,
            },
        ),
        ("dispatch-create", {"batch": "batch-proposal", "transition_digest": "a" * 64}),
        (
            "batch-decide",
            {
                "batch": "batch-report",
                "decision": "accept",
                "approved_by": "operator",
                "approved_at": "2026-11-06T12:00:00Z",
            },
        ),
    ],
)
def test_browser_decisions_require_confirmation_and_journal_the_bound_command(
    tmp_path: Path,
    command: str,
    values: dict[str, str],
) -> None:
    _project(tmp_path)
    executed: list[list[str]] = []

    async def executor(
        argv: Sequence[str],
        *,
        cwd: Path,
        on_output: Callable[[str, str], None],
        cancel_event: threading.Event,
    ) -> int:
        assert cwd == tmp_path
        executed.append(list(argv))
        return 0

    async def scenario() -> None:
        server = ConsoleServer(
            tmp_path, jobs=composition.job_service(tmp_path, executor=executor)
        )
        await server.start()
        try:
            async with connect(
                f"ws://127.0.0.1:{server.port}/ws",
                additional_headers={
                    "Cookie": f"console_token_{server.port}={server.token}"
                },
                origin=Origin(f"http://127.0.0.1:{server.port}"),
            ) as ws:
                await ws.send(
                    json.dumps(
                        {"id": "catalog", "type": "job.catalog", "section": "decisions"}
                    )
                )
                catalog = json.loads(await ws.recv())
                assert catalog["ok"] is True
                descriptors = {
                    entry["command_id"]: entry for entry in catalog["commands"]
                }
                assert descriptors[command]["needs_confirmation"] is True
                decide_fields = {
                    field["dest"]: field
                    for field in descriptors["batch-decide"]["fields"]
                }
                assert decide_fields["decision"]["choices"] == [
                    "abandon",
                    "accept",
                    "accept-conditional",
                    "block",
                    "fail",
                    "override-warning",
                    "retry",
                ]
                assert decide_fields["approved_by"]["required"] is True
                await ws.send(
                    json.dumps({"id": "decisions", "type": "decisions.snapshot"})
                )
                snapshot = json.loads(await ws.recv())["snapshot"]
                assert {item["kind"] for item in snapshot["items"]} == {
                    "dispatch-approval",
                    "report-decision",
                    "native-permission",
                }
                assert all(item["ticket"] == "#884" for item in snapshot["items"])
                request = {
                    "id": "choice",
                    "type": "job.start",
                    "command_id": command,
                    "values": values,
                    "client": "browser",
                }
                await ws.send(json.dumps(request))
                refused = json.loads(await ws.recv())
                assert refused["error"]["code"] == "confirmation_required"
                assert executed == []
                await ws.send(
                    json.dumps({**request, "id": "confirmed", "confirmed": True})
                )
                started = json.loads(await ws.recv())
                assert started["ok"] is True
                await ws.send(
                    json.dumps(
                        {
                            "id": "follow",
                            "type": "job.subscribe",
                            "job_id": started["job"]["id"],
                            "cursor": 0,
                        }
                    )
                )
                while True:
                    reply = json.loads(await ws.recv())
                    if reply["job"]["done"]:
                        assert reply["job"]["returncode"] == 0
                        break
        finally:
            await server.close()

    asyncio.run(asyncio.wait_for(scenario(), timeout=15))
    assert len(executed) == 1
    journal = tmp_path / ".harness/console/commands.jsonl"
    records = [
        json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 1 and records[0]["client"] == "browser"
    assert records[0]["returncode"] == 0
    assert "request-7" not in json.dumps(records) and "operator" not in json.dumps(
        records
    )
    english = json.loads(web_catalog.render())["en"]
    assert english["Ожидающие решения"] == "Pending decisions"
    assert english["Подтвердите решение"] == "Confirm decision"


@pytest.mark.skipif(
    sys.platform == "win32", reason="the runtime fixture uses a Unix socket"
)
def test_pending_decisions_survive_runtime_store_cutover(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from harness.console.backend.infrastructure.ledger import collect_decisions
    from tests.orchestration.runtime_store_support import (
        ServingRuntime,
        coordinator_with,
        migrate,
        write_coordinator_state,
    )

    repo, ids = write_coordinator_state(tmp_path, ticket="#884")
    before = collect_decisions(repo).to_payload()
    assert before["items"]
    migrated = migrate(repo)
    assert migrated.returncode == 0, migrated.stderr
    runtime = ServingRuntime(repo)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime.xdg))
    try:

        async def scenario() -> None:
            server = ConsoleServer(repo)
            await server.start()
            try:
                async with connect(
                    f"ws://127.0.0.1:{server.port}/ws",
                    additional_headers={
                        "Cookie": f"console_token_{server.port}={server.token}"
                    },
                    origin=Origin(f"http://127.0.0.1:{server.port}"),
                ) as ws:
                    await ws.send(
                        json.dumps({"id": "store", "type": "decisions.snapshot"})
                    )
                    reply = json.loads(await ws.recv())
                    assert reply["ok"] is True
                    assert reply["snapshot"] == before
                    decided = await asyncio.to_thread(
                        coordinator_with,
                        repo,
                        runtime,
                        "batch",
                        "decide",
                        "--batch",
                        ids["batch_id"],
                        "--decision",
                        "block",
                        "--approved-by",
                        "operator",
                        "--approved-at",
                        "2026-11-06T12:00:00+00:00",
                        "--note",
                        "fixture decision",
                    )
                    assert decided.returncode == 0, decided.stderr
                    await ws.send(
                        json.dumps({"id": "after-choice", "type": "decisions.snapshot"})
                    )
                    after = json.loads(await ws.recv())
                    assert after["snapshot"]["items"] == []
                    assert after["snapshot"]["unavailable"] is False
            finally:
                await server.close()

        asyncio.run(asyncio.wait_for(scenario(), timeout=15))
    finally:
        runtime.stop()
    # An absent authority cannot be replaced by archived legacy records.
    assert collect_decisions(repo).unavailable is True
    assert collect_decisions(repo).to_payload().get("error_code") == "runtime_unavailable"
