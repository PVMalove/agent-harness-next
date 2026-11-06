"""When a console decision needs an explicit human confirmation, and which native permission
answers are well formed."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field

from ...kernel.i18n import tr_text
from ...kernel.json_fields import text
from ...kernel.protocol import _LONE_SURROGATE, ID_BYTES, MESSAGE_BYTES, _clip

# What a cancel of a mutation warns: the Russian source a client translates, and its English
# translation the unconfirmed-cancel refusal carries.
CANCEL_REASON = "Отмена останавливает команду; уже внесённые изменения не откатываются."
CANCEL_KEEPS_CHANGES = tr_text("en", CANCEL_REASON)
NATIVE_ANSWER_FIELDS = ("dispatch", "request_id", "request_sha256")
_DISPATCH = re.compile(r"dispatch-[0-9a-f-]+")
_SHA256 = re.compile(r"[0-9a-f]{64}")
# The runtime stages request ids of up to 256 characters (`runtime_permissions.stage_request`).
_MAX_ID_CHARS = 256


def start_confirmed(
    *,
    needs_confirmation: bool,
    typed_confirmation: str | None,
    confirmed: bool,
    confirmation: object,
) -> bool:
    """A start carries every confirmation its command asks for: the flag, and the typed text when
    the command has one."""
    return not (
        (needs_confirmation and not confirmed)
        or (typed_confirmation is not None and confirmation != typed_confirmation)
    )


def cancel_confirmation_message(*, holds_mutation_slot: bool) -> str | None:
    """What an unconfirmed cancel says: a mutation is warned that its changes stay."""
    return CANCEL_KEEPS_CHANGES if holds_mutation_slot else None


def native_answer_accepts(values: Mapping[str, str]) -> bool:
    """Exactly the dispatch, the request id and its digest, each non-empty and bounded."""
    if set(values) != set(NATIVE_ANSWER_FIELDS):
        return False
    if any(
        not value.strip() or len(value) > _MAX_ID_CHARS for value in values.values()
    ):
        return False
    return bool(
        _DISPATCH.fullmatch(values["dispatch"])
        and _SHA256.fullmatch(values["request_sha256"])
    )


SCHEMA_VERSION = 1
MAX_DECISIONS = 32
# Items stop at this encoded size, so a reply stays well below the server's 64 KiB message limit.
_PAYLOAD_BUDGET = 48 * 1024
_CLOSED_BATCHES = frozenset({"completed", "abandoned", "failed", "not-required"})

Record = Mapping[str, object]


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


def _wire_size(item: DecisionItem) -> int:
    """The UTF-8 size of the item as a reply encodes it."""
    encoded = json.dumps(asdict(item), separators=(",", ":"), ensure_ascii=False)
    encoded = _LONE_SURROGATE.sub(lambda found: f"\\u{ord(found.group()):04x}", encoded)
    return len(encoded.encode("utf-8"))


def bounded_decisions(found: Sequence[DecisionItem]) -> DecisionsSnapshot:
    """At most ``MAX_DECISIONS`` items within the payload budget; ``total`` counts them all."""
    kept: list[DecisionItem] = []
    size = 0
    for item in found[:MAX_DECISIONS]:
        size += _wire_size(item)
        if size > _PAYLOAD_BUDGET:
            break
        kept.append(item)
    return DecisionsSnapshot(items=tuple(kept), total=len(found))


def _status(value: object) -> str:
    return text(value.get("status")) if isinstance(value, dict) else ""


def decision_item(
    kind: str,
    batch: Record,
    commands: list[str],
    values: dict[str, str],
    reversibility: Mapping[str, str],
    *,
    dispatch_id: str | None = None,
    role: str | None = None,
    ticket: str | None = None,
    details: dict[str, str] | None = None,
) -> DecisionItem:
    """One decision; `reversibility` maps every command key to its class."""
    return DecisionItem(
        kind=kind,
        batch_id=text(batch.get("batch_id")),
        dispatch_id=dispatch_id,
        ticket=_clip(ticket or text(batch.get("ticket"), "?"), ID_BYTES),
        role=role,
        # The class of the command that records the decision: the last one of the sequence.
        reversibility=reversibility[commands[-1]],
        command_ids=commands,
        values=values,
        details={
            name: _clip(value, MESSAGE_BYTES) for name, value in (details or {}).items()
        },
    )


def batch_items(
    batch: Record,
    reports: Mapping[str, Record],
    active_dispatches: Callable[[Record], Iterable[Record]],
    reversibility: Mapping[str, str],
) -> list[DecisionItem]:
    """The decisions a batch waits for: its approval, the reports without a coordinator
    decision, its attention and the approval of its next dispatch."""
    batch_id = text(batch.get("batch_id"))
    state = text(batch.get("state"))
    if not batch_id or state in _CLOSED_BATCHES:
        return []
    values = {"batch": batch_id}
    if state == "planned":
        details = {"state": state}
        return [
            decision_item(
                "batch-approval",
                batch,
                ["batch-approve"],
                values,
                reversibility,
                details=details,
            )
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
            decision_item(
                "report-decision",
                batch,
                ["batch-decide"],
                values,
                reversibility,
                dispatch_id=dispatch_id,
                role=text(entry.get("role")) or None,
                details=details,
            )
        )
    if batch.get("needs_attention") is True:
        items.append(
            decision_item(
                "attention", batch, ["batch-attention-resolve"], values, reversibility
            )
        )
    if state == "awaiting-approval" and not items:
        # `dispatch propose` chooses the role: the console prefills only the batch.
        items.append(
            decision_item(
                "dispatch-approval",
                batch,
                ["dispatch-propose", "dispatch-create"],
                values,
                reversibility,
                details={"state": state},
            )
        )
    return items


def native_permission_item(
    batch: Record,
    dispatch: Record,
    request: Record,
    commands: list[str],
    reversibility: Mapping[str, str],
) -> DecisionItem:
    """The answer to a permission request a live worker's runtime staged."""
    return decision_item(
        "native-permission",
        batch,
        commands,
        {
            "dispatch": text(dispatch.get("dispatch_id")),
            "request_id": text(request.get("request_id")),
            "request_sha256": text(request.get("request_sha256")),
        },
        reversibility,
        dispatch_id=text(dispatch.get("dispatch_id")),
        role=text(dispatch.get("role")) or None,
        ticket=text(dispatch.get("ticket")) or None,
        details={
            "tool_name": text(request.get("tool_name")),
            "input_preview": text(request.get("input_preview")),
        },
    )
