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
# The init event follows hook output at most; a bound keeps one read of a long stream small.
INIT_SCAN_BYTES = 4 * 1024 * 1024


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
    """The model of the first stream-json ``init`` event; output is data, never a command.

    Only complete lines within the first ``INIT_SCAN_BYTES`` count; hook output before the event
    or one long line does not hide it (#1125)."""
    try:
        with path.open("rb") as stream:
            scanned = 0
            while scanned < INIT_SCAN_BYTES:
                line = stream.readline(INIT_SCAN_BYTES - scanned)
                scanned += len(line)
                if not line.endswith(b"\n"):
                    return None
                model = _init_event_model(line)
                if model is not None:
                    return model or None
    except OSError:
        return None
    return None


def _init_event_model(line: bytes) -> str | None:
    """The model of an ``init`` event line ("" for an event without one), ``None`` otherwise."""
    try:
        record = json.loads(line)
    except (ValueError, UnicodeDecodeError):
        return None
    if not (
        isinstance(record, dict)
        and record.get("type") == "system"
        and record.get("subtype") == "init"
    ):
        return None
    model = record.get("model")
    return model.strip() if isinstance(model, str) else ""


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
    """Record the self-report of a container worker once, and the heartbeat of a running one.

    An exited worker is proven from its saved stream: a short worker can stage its report and
    exit before any command observes it running (#1125)."""
    from harness.orchestration.workflow.reports import record_self_report

    plan = dispatch.get("runtime_access")
    running = execution.get("state") == "running"
    if not (
        (running or execution.get("state") == "exited")
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
        if running:
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


def attest_before_submit(repo: Path, root: Path, dispatch_id: object) -> None:
    """Prove a container worker before ``report submit`` checks its model confirmation.

    ``report submit`` may be the first command after the worker exits; without this the
    submit refuses the worker's report for a missing self-report (#1125)."""
    from harness.orchestration.ledger.ledger_ops import _load_dispatch
    from harness.orchestration.workflow.delivery import observed_execution

    if not isinstance(dispatch_id, str) or not dispatch_id:
        return
    try:
        dispatch = _load_dispatch(root, dispatch_id)
    except CoordinatorError:
        # The submit itself reports an unknown dispatch.
        return
    plan = dispatch.get("runtime_access")
    if not (
        isinstance(plan, dict)
        and plan.get("runtime_extension") == container_executor.EXTENSION_NAME
    ):
        return
    execution = observed_execution(repo, dispatch_id)
    if execution is not None:
        attest(repo, root, dispatch, execution)


def staged_report(
    dispatch: Mapping[str, object], status: Mapping[str, object]
) -> Path | None:
    """The report a host-attested container worker staged before it exited, or ``None``.

    Such a worker cannot run ``report submit`` itself, so its exit before the coordinator
    submits the staged report is no failure: the dispatch waits for that submit (#1014)."""
    plan = dispatch.get("runtime_access")
    reported = status.get("model_self_report")
    attestation = status.get("worktree_attestation")
    staging = dispatch.get("report_staging_path")
    if not (
        isinstance(plan, dict)
        and plan.get("runtime_extension") == container_executor.EXTENSION_NAME
        and isinstance(reported, dict)
        and reported.get("source") == SOURCE
        and reported.get("match") is True
        and (not isinstance(attestation, dict) or attestation.get("match") is True)
        and isinstance(staging, str)
    ):
        return None
    path = Path(staging)
    return path if path.is_file() else None
