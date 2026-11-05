"""Pending human decisions for the console server's ``decisions.snapshot`` request.

The list reads the ledger's JSON records without the ledger lock, which a coordinator command can
hold for minutes, like the Reports section does. A listed decision can therefore be stale: the
console never decides from it. Each item names the job commands that execute it through
``job.start`` with prefilled ``values``; the coordinator and the runtime recheck the live state
(the transition digest, the batch state, the request digest) when the command runs.

Kinds: ``batch-approval`` (a planned batch), ``dispatch-approval`` (a batch awaiting approval with
nothing else open: ``dispatch-propose`` shows the transition, ``dispatch-create`` approves it),
``report-decision`` (a completion report without a coordinator decision), ``attention`` (a batch
that needs attention) and ``native-permission`` (a request a live worker's runtime staged).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from harness.orchestration.core.constants import LIVE_DISPATCH_STATES, STATE_REL
from harness.orchestration.ledger.lifecycle import JsonObject, LifecycleLedger
from harness.orchestration.ledger.recovery_chain import active_dispatches

from ...kernel.coordinator_catalog import COORDINATOR_COMMANDS
from ...kernel.json_fields import text
from ..infrastructure.native_permission import NATIVE_PERMISSION_COMMANDS
from .snapshots import (
    ID_BYTES,
    MAX_ID_CHARS,
    MESSAGE_BYTES,
    PROTOCOL_VERSION,
    Rejected,
    _clip,
    encode,
    error_reply,
    parse_envelope,
)

DECISIONS_REQUEST = "decisions.snapshot"
SCHEMA_VERSION = 1
MAX_DECISIONS = 32
# Items stop at this encoded size, so a reply stays well below the server's 64 KiB message limit.
_PAYLOAD_BUDGET = 48 * 1024
_CLOSED_BATCHES = frozenset({"completed", "abandoned", "failed", "not-required"})
_REVERSIBILITY = {
    **{entry.key: entry.reversibility.value for entry in COORDINATOR_COMMANDS},
    **{entry.key: entry.reversibility.value for entry in NATIVE_PERMISSION_COMMANDS},
}
_NATIVE_COMMANDS = [entry.key for entry in NATIVE_PERMISSION_COMMANDS]


@dataclass(frozen=True)
class DecisionItem:
    """One pending decision: its context and the job commands, with values, that execute it."""

    kind: str
    batch_id: str
    dispatch_id: str | None
    ticket: str
    role: str | None
    reversibility: str
    command_ids: list[str]
    values: dict[str, str]
    details: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionsSnapshot:
    items: tuple[DecisionItem, ...] = ()
    total: int = 0
    # True when the project has no readable ledger.
    unavailable: bool = False
    version: int = SCHEMA_VERSION

    def to_payload(self) -> dict[str, object]:
        return {
            "version": self.version,
            "items": [asdict(item) for item in self.items],
            "total": self.total,
            "unavailable": self.unavailable,
        }


def _records(root: Path, directory: str) -> list[JsonObject]:
    records: list[JsonObject] = []
    for path in sorted((root / directory).glob("*.json")):
        record = LifecycleLedger.read_record_lenient(path)
        if record is not None:
            records.append(record)
    return records


def _status(value: object) -> str:
    return text(value.get("status")) if isinstance(value, dict) else ""


def _item(
    kind: str,
    batch: JsonObject,
    commands: list[str],
    values: dict[str, str],
    *,
    dispatch_id: str | None = None,
    role: str | None = None,
    ticket: str | None = None,
    details: dict[str, str] | None = None,
) -> DecisionItem:
    return DecisionItem(
        kind=kind,
        batch_id=text(batch.get("batch_id")),
        dispatch_id=dispatch_id,
        ticket=_clip(ticket or text(batch.get("ticket"), "?"), ID_BYTES),
        role=role,
        # The class of the command that records the decision: the last one of the sequence.
        reversibility=_REVERSIBILITY[commands[-1]],
        command_ids=commands,
        values=values,
        details={
            name: _clip(value, MESSAGE_BYTES) for name, value in (details or {}).items()
        },
    )


def _batch_items(
    batch: JsonObject, reports: dict[str, JsonObject]
) -> list[DecisionItem]:
    batch_id = text(batch.get("batch_id"))
    state = text(batch.get("state"))
    if not batch_id or state in _CLOSED_BATCHES:
        return []
    values = {"batch": batch_id}
    if state == "planned":
        details = {"state": state}
        return [
            _item("batch-approval", batch, ["batch-approve"], values, details=details)
        ]
    items: list[DecisionItem] = []
    for entry in active_dispatches(batch):
        if entry.get("state") != "reported" or "decision" in entry:
            continue
        dispatch_id = text(entry.get("dispatch_id"))
        report = reports.get(dispatch_id, {})
        details = {
            "outcome": text(report.get("outcome")),
            "blockers": _status(report.get("blockers")),
            "risks": _status(report.get("risks")),
        }
        items.append(
            _item(
                "report-decision",
                batch,
                ["batch-decide"],
                values,
                dispatch_id=dispatch_id,
                role=text(entry.get("role")) or None,
                details=details,
            )
        )
    if batch.get("needs_attention") is True:
        items.append(_item("attention", batch, ["batch-attention-resolve"], values))
    if state == "awaiting-approval" and not items:
        # `dispatch propose` chooses the role: the console prefills only the batch.
        items.append(
            _item(
                "dispatch-approval",
                batch,
                ["dispatch-propose", "dispatch-create"],
                values,
                details={"state": state},
            )
        )
    return items


def _native_items(
    repo: Path,
    root: Path,
    batches: dict[str, JsonObject],
    dispatches: dict[str, JsonObject],
) -> list[DecisionItem]:
    from harness.orchestration.runtime_permissions import pending_requests

    live = {state.value for state in LIVE_DISPATCH_STATES}
    items: list[DecisionItem] = []
    for status in _records(root, "dispatch-status"):
        dispatch = dispatches.get(text(status.get("dispatch_id")))
        if (
            dispatch is None
            or status.get("state") not in live
            or not isinstance(status.get("adapter_receipt"), dict)
        ):
            continue
        batch = batches.get(text(dispatch.get("batch_id")), {})
        batch = {**batch, "batch_id": text(dispatch.get("batch_id"))}
        try:
            requests = pending_requests(repo, dispatch, status)
        except ValueError:
            continue  # the receipt points outside the project's worker log storage
        for request in requests:
            items.append(
                _item(
                    "native-permission",
                    batch,
                    _NATIVE_COMMANDS,
                    {
                        "dispatch": text(dispatch.get("dispatch_id")),
                        "request_id": text(request.get("request_id")),
                        "request_sha256": text(request.get("request_sha256")),
                    },
                    dispatch_id=text(dispatch.get("dispatch_id")),
                    role=text(dispatch.get("role")) or None,
                    ticket=text(dispatch.get("ticket")) or None,
                    details={
                        "tool_name": text(request.get("tool_name")),
                        "input_preview": text(request.get("input_preview")),
                    },
                )
            )
    return items


def collect_decisions(repo: Path) -> DecisionsSnapshot:
    """The project's pending decisions, at most ``MAX_DECISIONS``; ``total`` counts them all."""
    root = LifecycleLedger(repo / STATE_REL).records_root_lenient()
    if root is None:
        return DecisionsSnapshot(unavailable=True)
    batches: dict[str, JsonObject] = {}
    for record in _records(root, "batches"):
        batch_id = record.get("batch_id")
        if isinstance(batch_id, str) and isinstance(record.get("dispatches", []), list):
            batches[batch_id] = record
    reports = {
        text(report.get("dispatch_id")): report for report in _records(root, "reports")
    }
    dispatches = {
        text(record.get("dispatch_id")): record
        for record in _records(root, "dispatches")
    }
    found: list[DecisionItem] = []
    for batch in batches.values():
        try:
            found.extend(_batch_items(batch, reports))
        except (KeyError, TypeError, AttributeError):
            continue  # a malformed record is not a decision the console can offer
    found.extend(_native_items(repo, root, batches, dispatches))
    kept: list[DecisionItem] = []
    size = 0
    for item in found[:MAX_DECISIONS]:
        size += len(encode(asdict(item)).encode("utf-8"))
        if size > _PAYLOAD_BUDGET:
            break
        kept.append(item)
    return DecisionsSnapshot(items=tuple(kept), total=len(found))


class DecisionService:
    """Builds the decision list off the event loop on every request; nothing is cached."""

    def __init__(
        self,
        repo: Path,
        *,
        collect: Callable[[Path], DecisionsSnapshot] = collect_decisions,
    ) -> None:
        self.repo = repo.resolve()
        self._collect = collect

    async def snapshot(self) -> DecisionsSnapshot:
        return await asyncio.to_thread(self._collect, self.repo)


def is_decisions_request(raw: str) -> bool:
    """True for a request of type ``decisions.snapshot``, malformed or not."""
    try:
        _, _, kind = parse_envelope(raw)
    except Rejected:
        return False
    return kind == DECISIONS_REQUEST


async def respond(raw: str, service: DecisionService) -> str:
    """The reply to one ``decisions.snapshot`` frame. Never raises: every failure is an error reply."""
    try:
        body, request_id, kind = parse_envelope(raw)
    except Rejected as rejected:
        return error_reply(rejected.code, rejected.id, rejected.type)
    if kind != DECISIONS_REQUEST:
        return error_reply("unknown_type", request_id, kind[:MAX_ID_CHARS])
    if set(body) - {"id", "type"}:
        return error_reply("bad_request", request_id, kind)
    try:
        snapshot = await service.snapshot()
    except Exception as exc:
        return error_reply("collect_failed", request_id, kind, type(exc).__name__)
    return encode(
        {
            "v": PROTOCOL_VERSION,
            "id": request_id,
            "type": kind,
            "ok": True,
            "snapshot": snapshot.to_payload(),
        }
    )
