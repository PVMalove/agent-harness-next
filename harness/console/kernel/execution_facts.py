"""What the runtime observes of a supervised execution (#1296), for the console server and the
TUI alike: a worker process or container, or the containers of a QA run. Asking the runtime
makes it reconcile the execution, so callers bound how often they ask; nothing here writes the
ledger, and stderr lines are redacted before they reach a screen."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from pathlib import Path

from harness.orchestration.core.constants import STATE_REL
from harness.orchestration.ledger.lifecycle import store_is_authority

from .execution_view import MAX_STDERR_LINES, ExecutionSummary, execution_summary

__all__ = ["ExecutionSummary", "observe_execution", "stderr_tail", "teardown_record"]

# `execution.observe` makes the runtime reconcile the execution: a short, bounded call.
OBSERVE_SECONDS = 2
_STDERR_READ_BYTES = 8192


def _executions(repo: Path) -> Path:
    return (repo / STATE_REL / "executions").resolve()


def _inside(executions: Path, path: Path) -> Path | None:
    resolved = path.resolve()
    return resolved if resolved.is_relative_to(executions) else None


def stderr_tail(executions: Path, execution: Mapping[str, object]) -> list[str]:
    """The last lines of the execution's stderr, redacted; a log outside the runtime's
    executions directory or a missing one gives none."""
    from harness.orchestration.worker_observation import redact_visible

    identity = execution.get("execution_id")
    if not isinstance(identity, str) or not identity:
        return []
    launch = execution.get("launch")
    logs = launch.get("logs") if isinstance(launch, Mapping) else None
    named = logs.get("stderr") if isinstance(logs, Mapping) else None
    path = _inside(
        executions,
        Path(named) if isinstance(named, str) and named else executions / identity / "stderr.log",
    )
    if path is None:
        return []
    try:
        with path.open("rb") as stream:
            size = stream.seek(0, 2)
            stream.seek(max(0, size - _STDERR_READ_BYTES))
            data = stream.read().decode("utf-8", "replace")
    except OSError:
        return []
    lines = [redact_visible(line) for line in data.splitlines() if line.strip()]
    return lines[-MAX_STDERR_LINES:]


def teardown_record(executions: Path, execution: Mapping[str, object]) -> Mapping[str, object] | None:
    """The ``teardown.json`` the runtime writes when it removed the execution's objects."""
    identity = execution.get("execution_id")
    if not isinstance(identity, str) or not identity:
        return None
    path = _inside(executions, executions / identity / "teardown.json")
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def observe_execution(repo: Path, dispatch_id: str) -> ExecutionSummary | None:
    """What the runtime observes now of the execution of ``dispatch_id``; None on the file
    ledger, for a dispatch without one, or when the runtime does not answer in time."""
    from harness.orchestration.runtime_client import RuntimeClient, RuntimeClientError

    if not store_is_authority(repo / STATE_REL):
        return None
    try:
        reply = RuntimeClient(repo).call(
            "execution.observe",
            operation_id=f"console.execution-{uuid.uuid4().hex}",
            payload={"dispatch_id": dispatch_id},
            timeout_seconds=OBSERVE_SECONDS,
        )
    except RuntimeClientError:
        return None
    execution = reply.result.get("execution")
    if not isinstance(execution, Mapping):
        return None
    executions = _executions(repo)
    return execution_summary(
        execution, teardown_record(executions, execution), stderr_tail(executions, execution)
    )
