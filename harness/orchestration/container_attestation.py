"""Host-side startup proof of a container worker (#1014, ADR 0025).

A worker that the built-in docker executor runs has no runtime socket and reads shared storage
only, so it cannot run ``dispatch self-report`` or ``dispatch heartbeat`` itself. The runtime
keeps a snapshot of the running container's stdout next to its execution. While the execution
runs, the coordinator on the host reads the model from the first stream-json ``init`` event of
that snapshot and takes the checkout from the approved plan, never from the worker's words, and
records the self-report through the same checks as the worker's own. Until then, and after it,
the observed running container is the dispatch's heartbeat.

The startup deadline is untouched: a container that never prints an ``init`` event still ends
in ``startup_timeout`` with ``model-self-report-missing``. A mismatch is recorded without
blocking, because the store refuses ``blocked`` while the execution runs; ``dispatch wait``
reports it, and the exit blocks the dispatch.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from harness.orchestration import container_executor
from harness.orchestration.core import utils
from harness.orchestration.core.constants import LIVE_DISPATCH_STATES
from harness.orchestration.core.utils import CoordinatorError, JsonObject
from harness.orchestration.ledger.ledger_ops import (
    _ledger_lock,
    _load_dispatch_status,
    _replace_record,
)
from harness.orchestration.ledger.lifecycle import (
    DispatchStatusRecord,
    LifecycleLedger,
)

SOURCE = "container-host"
HEARTBEAT_NOTE = "container running"
# The init event is the first record of a stream-json session; a bounded head finds it.
INIT_SCAN_BYTES = 65536


def stream_root(root: Path) -> Path:
    """Where the runtime keeps the logs of the executions of the store ``root``."""
    return root / "executions"


def stream_path(root: Path, execution: Mapping[str, object]) -> Path | None:
    """The stdout snapshot of a container execution, only inside the store's executions."""
    launch = execution.get("launch")
    logs = launch.get("logs") if isinstance(launch, dict) else None
    stdout = logs.get("stdout") if isinstance(logs, dict) else None
    if execution.get("kind") != "container" or not isinstance(stdout, str):
        return None
    path = Path(stdout).resolve()
    return path if path.is_relative_to(stream_root(root).resolve()) else None


def init_model(path: Path) -> str | None:
    """The model of the first stream-json ``init`` event; output is data, never a command."""
    try:
        with path.open("rb") as stream:
            head = stream.read(INIT_SCAN_BYTES)
    except OSError:
        return None
    for line in head[: head.rfind(b"\n") + 1].splitlines():
        try:
            record = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            continue
        if (
            isinstance(record, dict)
            and record.get("type") == "system"
            and record.get("subtype") == "init"
        ):
            model = record.get("model")
            return model.strip() if isinstance(model, str) and model.strip() else None
    return None


def _checkout(plan: Mapping[str, object]) -> str | None:
    requirements = plan.get("requirements")
    if not isinstance(requirements, list):
        return None
    return next(
        (
            str(item["path"])
            for item in requirements
            if isinstance(item, dict) and item.get("resource") == "checkout"
        ),
        None,
    )


def _heartbeat(ledger: LifecycleLedger, root: Path, dispatch_id: str) -> None:
    with _ledger_lock(ledger):
        status = _load_dispatch_status(root, dispatch_id)
        if status.get("state") not in LIVE_DISPATCH_STATES:
            return
        moment = utils._now()
        status.update(
            {
                "updated_at": moment,
                "heartbeat_at": moment,
                "heartbeat_note": HEARTBEAT_NOTE,
            }
        )
        _replace_record(ledger, DispatchStatusRecord.from_dict(status))


def attest(
    repo: Path,
    root: Path,
    dispatch: Mapping[str, object],
    execution: Mapping[str, object],
) -> None:
    """Record the self-report of a running container worker once, and its heartbeat."""
    from harness.orchestration.workflow.reports import record_self_report

    plan = dispatch.get("runtime_access")
    if not (
        execution.get("state") == "running"
        and isinstance(plan, dict)
        and plan.get("runtime_extension") == container_executor.EXTENSION_NAME
    ):
        return
    path = stream_path(root, execution)
    if path is None:
        return
    dispatch_id = str(dispatch["dispatch_id"])
    ledger = LifecycleLedger(root)
    with _ledger_lock(ledger):
        status = _load_dispatch_status(root, dispatch_id)
    if status.get("state") not in LIVE_DISPATCH_STATES:
        return
    model = None if status.get("model_self_report") else init_model(path)
    if model is None:
        _heartbeat(ledger, root, dispatch_id)
        return
    checkout = _checkout(plan)
    evidence: JsonObject = {
        "container_id": execution.get("container_id"),
        "images": dispatch.get("runtime_images"),
        "checkout": checkout,
        "executor": container_executor.EXTENSION_NAME,
    }
    try:
        record_self_report(
            repo,
            root,
            dispatch_id,
            model,
            checkout,
            source=SOURCE,
            evidence=evidence,
            # The execution runs: the store refuses ``blocked`` until it exits (ADR 0021).
            block=False,
        )
    except CoordinatorError:
        # A mismatch is recorded on the status; dispatch wait reports it, and the exit of the
        # execution blocks the dispatch. Stopping the worker stays the operator's command.
        return
