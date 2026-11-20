"""Watching a sent dispatch: the facts of its worker, read without changing any record.

`delivery.py` hands a brief to a transport; from then on these reads show what the worker and the
runtime report about it. They never run or prompt a model, never change the ledger, and answer a
native permission request only on an explicit operator action.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import cast

from harness.orchestration import (
    container_attestation,
    container_executor,
    runtime_client,
)
from harness.orchestration.core.utils import CoordinatorError, JsonObject, _repo
from harness.orchestration.ledger.ledger_ops import (
    _ledger_lock,
    _load_batch,
    _load_checkpoint,
    _load_dispatch,
    _load_dispatch_status,
    _state_root,
)
from harness.orchestration.ledger.lifecycle import LifecycleLedger
from harness.orchestration.runtime_permissions import pending_requests, respond
from harness.orchestration.worker_observation import (
    checkpoint_view,
    dispatch_checkpoint_ids,
    read_events,
    read_terminal,
    redact_visible,
    supervised_log_path,
)
from harness.orchestration.workflow import execution_reaction, failure_domains
from harness.orchestration.workflow import startup as worker_startup

IN_PROCESS_STREAM_REASON = (
    "an in-process worker runs inside the coordinator session and has no event stream; "
    "follow its progress through self-report, heartbeat and checkpoints"
)


def observed_execution(
    repo: Path, dispatch_id: str, client: runtime_client.RuntimeClient | None = None
) -> JsonObject | None:
    """The execution of a supervised dispatch, as the runtime observes it now; ``client`` is the
    runtime client of the command, so its observations share one connection."""
    reply = (client or runtime_client.RuntimeClient(repo)).call(
        "execution.observe",
        operation_id=f"execution.observe-{dispatch_id}-{time.time_ns()}",
        payload={"dispatch_id": dispatch_id},
    )
    execution = reply.result.get("execution")
    return cast(JsonObject, execution) if isinstance(execution, dict) else None


def observe_dispatch(args: argparse.Namespace) -> JsonObject:
    """Read process/status/event facts locally, without running or prompting any model."""
    repo = _repo(args)
    offset = getattr(args, "offset", 0)
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise CoordinatorError(
            "observation offset must be nonnegative",
            remedy="pass a nonnegative --offset from the previous observation",
        )
    root = _state_root(args, repo)
    with _ledger_lock(LifecycleLedger(root)):
        dispatch = _load_dispatch(root, args.dispatch)
        status = _load_dispatch_status(root, args.dispatch)
        checkpoints = _dispatch_checkpoints(root, dispatch)
    startup = worker_startup.assess_startup(dispatch, status, repo=repo)
    receipt = status.get("adapter_receipt")
    if (
        isinstance(receipt, dict)
        and receipt.get("dispatch_id") != dispatch["dispatch_id"]
    ):
        receipt = None
    return {
        "dispatch_id": dispatch["dispatch_id"],
        "batch_id": dispatch["batch_id"],
        "role": dispatch["role"],
        "ticket": dispatch["ticket"],
        "state": status["state"],
        "worktree": dispatch["worktree"],
        "model": dispatch["resolved_model"],
        "runtime": dispatch["resolved_runtime"],
        "effort": dispatch["resolved_effort"],
        "snapshot_commit": dispatch.get("snapshot_commit"),
        "worktree_attestation": status.get("worktree_attestation"),
        "startup": startup,
        "model_self_report": status.get("model_self_report"),
        "heartbeat_at": status.get("heartbeat_at"),
        "report_staged": Path(dispatch.get("report_staging_path", "")).is_file(),
        "report_recorded": status["state"] == "reported",
        "runtime_exit": read_terminal(repo, receipt),
        "failure": _failure_view(status),
        "access_mode": dispatch.get("runtime_access", {}).get("mode", "inherit"),
        "permission_requests": pending_requests(repo, dispatch, status),
        "launch_id": receipt.get("launch_id") if isinstance(receipt, dict) else None,
        "runtime_session_id": receipt.get("runtime_session_id")
        if isinstance(receipt, dict)
        else None,
        "checkpoints": checkpoints,
        **_events(repo, root, dispatch, receipt, offset),
    }


def _failure_view(status: JsonObject) -> JsonObject | None:
    """The recorded runtime failure of a dispatch, its error redacted for display."""
    if not isinstance(status.get("runtime_failure"), dict):
        return None
    return {
        "kind": status["runtime_failure"].get("kind"),
        "error": redact_visible(str(status["runtime_failure"].get("error", ""))),
        "failure_domain": failure_domains.of_runtime_failure(
            status["runtime_failure"]
        ).to_json(),
    }


def _dispatch_checkpoints(root: Path, dispatch: JsonObject) -> list[JsonObject]:
    """The checkpoints this dispatch recorded, oldest first, as observe shows them."""
    batch = _load_batch(root, dispatch["batch_id"])
    return [
        checkpoint_view(_load_checkpoint(root, checkpoint_id))
        for checkpoint_id in dispatch_checkpoint_ids(batch, dispatch["dispatch_id"])
    ]


def _events(
    repo: Path, root: Path, dispatch: JsonObject, receipt: object, offset: int
) -> JsonObject:
    """The worker's events: its adapter's log, the stream snapshot the runtime keeps of a
    running container worker (#1014), or the run log of any other supervised worker. An
    in-process worker has no stream; its reason names where its progress is seen instead."""
    plan = dispatch.get("runtime_access")
    supervised = execution_reaction.supervised(root, dispatch)
    if (
        isinstance(plan, dict)
        and plan.get("runtime_extension") == container_executor.EXTENSION_NAME
        and supervised
    ):
        try:
            execution = observed_execution(repo, dispatch["dispatch_id"])
        except runtime_client.RuntimeClientError:
            execution = None
        path = container_attestation.stream_path(root, execution) if execution else None
        if path is not None:
            return read_events(
                repo,
                {"log_path": str(path)},
                offset,
                (container_attestation.stream_root(root),),
            )
    if supervised:
        run_log, _reason = supervised_log_path(root, dispatch)
        if run_log is not None:
            return read_events(
                repo, {"log_path": str(run_log)}, offset, (root / "executions",)
            )
    events = read_events(repo, receipt, offset)
    if (
        dispatch.get("resolved_transport") == "in-process"
        and events["stream_state"] == "unavailable"
    ):
        events["stream_reason"] = IN_PROCESS_STREAM_REASON
    return events


def respond_native_permission(
    repo: Path, dispatch_id: str, request_id: str, expected_sha256: str, *, allow: bool
) -> JsonObject:
    """An explicit console/native operator action; never an automatic policy decision."""
    args = argparse.Namespace(repo=str(repo), state_dir=None)
    root = _state_root(args, repo)
    with _ledger_lock(LifecycleLedger(root)):
        dispatch = _load_dispatch(root, dispatch_id)
        status = _load_dispatch_status(root, dispatch_id)
    return respond(repo, dispatch, status, request_id, expected_sha256, allow=allow)
