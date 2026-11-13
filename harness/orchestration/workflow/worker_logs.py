"""``dispatch logs``: the visible events of a worker's log, one page or followed while it runs.

The dispatch and its status are read once, under a short ledger lock; the follow loop reads only
the log and asks the runtime how the execution goes, so a running worker can take the lock for its
self-report, heartbeat and report. Reading never changes the dispatch or decides its outcome.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from pathlib import Path

from harness.orchestration.core.utils import CoordinatorError, JsonObject, _repo
from harness.orchestration.ledger.ledger_ops import (
    _ledger_lock,
    _load_dispatch,
    _load_dispatch_status,
    _state_root,
)
from harness.orchestration.ledger.lifecycle import LifecycleLedger
from harness.orchestration.runtime_client import RuntimeClientError
from harness.orchestration.worker_observation import (
    STEP_REASON_MESSAGES,
    external_log_path,
    read_events,
    supervised_log_path,
)
from harness.orchestration.workflow import execution_reaction
from harness.orchestration.workflow.delivery import (
    IN_PROCESS_STREAM_REASON,
    observed_execution,
)

INTERRUPTED_EXIT = 130

Reader = Callable[[int], JsonObject]


def _unavailable(offset: int, reason: str) -> JsonObject:
    return {
        "events": [],
        "next_offset": offset,
        "stream_state": "unavailable",
        "stream_reason": reason,
    }


def _source(
    repo: Path, root: Path, dispatch: JsonObject, status: JsonObject
) -> tuple[str, Reader]:
    """``execution``: the run log the runtime keeps of a supervised worker; ``adapter``: the
    event log an adapter's receipt names, or a plain worker log that has no visible events;
    ``none``: no log."""
    if execution_reaction.supervised(root, dispatch):
        path, reason = supervised_log_path(root, dispatch)
        if path is None:
            message = STEP_REASON_MESSAGES[reason or "no_log"]
            return "execution", lambda offset: _unavailable(offset, message)
        receipt: JsonObject = {"log_path": str(path)}
        return "execution", lambda offset: read_events(
            repo, receipt, offset, (root / "executions",)
        )
    adapter_receipt = status.get("adapter_receipt")
    if (
        isinstance(adapter_receipt, dict)
        and adapter_receipt.get("dispatch_id") == dispatch["dispatch_id"]
        and isinstance(adapter_receipt.get("log_path"), str)
    ):
        return "adapter", lambda offset: read_events(repo, adapter_receipt, offset)
    plain, _reason = external_log_path(repo, dispatch)
    if plain is not None and plain.is_file():
        message = f"the adapter writes a plain worker log without events: {plain}"
        return "adapter", lambda offset: _unavailable(offset, message)
    reason = (
        IN_PROCESS_STREAM_REASON
        if dispatch.get("resolved_transport") == "in-process"
        else "adapter supplied no structured event log"
    )
    return "none", lambda offset: _unavailable(offset, reason)


def _execution_state(repo: Path, root: Path, dispatch: JsonObject) -> str | None:
    """The state of the execution as the runtime observes it now; ``None`` without one."""
    if not execution_reaction.supervised(root, dispatch):
        return None
    try:
        execution = observed_execution(repo, dispatch["dispatch_id"])
    except RuntimeClientError:
        return "unknown"
    state = execution.get("state") if execution else None
    return state if isinstance(state, str) else None


def dispatch_logs(args: argparse.Namespace) -> JsonObject:
    """One page of visible events from ``--offset``; ``--follow`` prints each event as a JSON
    line until the execution ends and a last read adds nothing, then returns the summary."""
    repo = _repo(args)
    offset = args.offset
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise CoordinatorError(
            "log offset must be nonnegative",
            remedy="pass a nonnegative --offset from the previous next_offset",
        )
    root = _state_root(args, repo)
    with _ledger_lock(LifecycleLedger(root)):
        dispatch = _load_dispatch(root, args.dispatch)
        status = _load_dispatch_status(root, args.dispatch)
    source, read = _source(repo, root, dispatch, status)
    summary: JsonObject = {
        "dispatch_id": dispatch["dispatch_id"],
        "state": status.get("state"),
        "source": source,
    }
    if not args.follow:
        page = read(offset)
        return {
            **summary,
            "execution_state": _execution_state(repo, root, dispatch),
            **_page_fields(page),
            "events": page["events"],
        }
    try:
        return {**summary, **_follow(repo, root, dispatch, read, offset, args)}
    except KeyboardInterrupt:
        raise SystemExit(INTERRUPTED_EXIT) from None


def _page_fields(page: JsonObject) -> JsonObject:
    fields = {key: page[key] for key in ("next_offset", "stream_state")}
    if page.get("stream_reason"):
        fields["stream_reason"] = page["stream_reason"]
    return fields


def _follow(
    repo: Path,
    root: Path,
    dispatch: JsonObject,
    read: Reader,
    offset: int,
    args: argparse.Namespace,
) -> JsonObject:
    poll = max(0.0, float(args.poll_seconds))
    while True:
        state = _execution_state(repo, root, dispatch)
        page = read(offset)
        for event in page["events"]:
            print(json.dumps(event, ensure_ascii=False, sort_keys=True), flush=True)
        advanced = page["next_offset"] != offset
        offset = page["next_offset"]
        if state not in execution_reaction.UNSETTLED_EXECUTION_STATES and not advanced:
            return {"execution_state": state, **_page_fields(page)}
        if not advanced:
            time.sleep(poll)
