"""Store-aware batch history for the 'Open recovery' entry. Textual-free.

The file-ledger view the Orchestration screen reads is empty on the runtime-store epoch, where
recovery lives. This source lists batches from `batch list` (which reads both epochs through the
core) and, for the one batch the operator selected, asks `recovery status` once whether the core
reports a suspension or an unfinished operation. Nothing is probed for unselected batches, and a
status the core did not give is shown as not checked, never as 'no recovery needed'.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .container_route import JsonObject, State, _items, _obj, _text
from .coordinator_api import ApiResult, CoordinatorApi, Outcome
from .home_snapshot import _bool, _fields, _int, _list, _str
from .runner import CommandRunner, capturing_runner


@dataclass(frozen=True)
class HistoryBatch:
    batch_id: str
    ticket: str
    branch: str
    state: str
    created_at: str
    terminal: bool
    dispatches: int
    open_dispatches: int
    next_action: str

    @classmethod
    def of(cls, item: JsonObject) -> "HistoryBatch":
        return cls(
            batch_id=_text(item.get("batch_id")),
            ticket=_text(item.get("ticket"), "—"),
            branch=_text(item.get("branch")),
            state=_text(item.get("state"), "не сообщается"),
            created_at=_text(item.get("created_at")),
            terminal=item.get("terminal") is True,
            dispatches=_count(item.get("dispatches")),
            open_dispatches=_count(item.get("open_dispatches")),
            next_action=_text(item.get("next_action")),
        )

    @property
    def label(self) -> str:
        """`#711 · active · batch-1 · 2 открытых`: one line for the history list."""
        parts = [self.ticket, self.state, self.batch_id]
        if self.open_dispatches:
            parts.append(f"{self.open_dispatches} открытых")
        return " · ".join(parts)


def _count(value: object) -> int:
    if isinstance(value, list):
        return len(value)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


@dataclass(frozen=True)
class History:
    batches: tuple[HistoryBatch, ...] = ()
    unavailable: str = ""  # the core's own text when the list could not be read

    def find(self, batch_id: str) -> HistoryBatch | None:
        return next((item for item in self.batches if item.batch_id == batch_id), None)

    def to_payload(self) -> dict[str, object]:
        """The JSON-safe form a console server reply carries."""
        return {
            "batches": [asdict(item) for item in self.batches],
            "unavailable": self.unavailable,
        }

    @classmethod
    def from_payload(cls, payload: object) -> History:
        """The history a `to_payload` result describes; any schema break is `ValueError`."""
        found = _fields(payload, cls)
        return cls(
            batches=tuple(_history_batch_from(item) for item in _list(found["batches"])),
            unavailable=_str(found["unavailable"]),
        )


def _history_batch_from(value: object) -> HistoryBatch:
    found = _fields(value, HistoryBatch)
    return HistoryBatch(
        batch_id=_str(found["batch_id"]),
        ticket=_str(found["ticket"]),
        branch=_str(found["branch"]),
        state=_str(found["state"]),
        created_at=_str(found["created_at"]),
        terminal=_bool(found["terminal"]),
        dispatches=_int(found["dispatches"]),
        open_dispatches=_int(found["open_dispatches"]),
        next_action=_str(found["next_action"]),
    )


@dataclass(frozen=True)
class RecoveryEntry:
    """Whether 'Open recovery' is offered for a batch, and why."""

    batch_id: str
    enabled: bool
    state: State
    reason: str


def load_history(api: CoordinatorApi) -> History:
    """`batch list`, newest first. A failed or unreadable answer is `unavailable` text."""
    result = api.call(("batch", "list"))
    if not result.ok or result.document is None:
        return History(unavailable=result.problem_text or result.outcome.value)
    items = [
        HistoryBatch.of(_obj(item)) for item in _items(result.document.get("batches"))
    ]
    items = [item for item in items if item.batch_id]
    items.sort(key=lambda item: item.created_at, reverse=True)
    return History(tuple(items))


def recovery_reason(document: JsonObject) -> str:
    """Why the core wants recovery for this batch, or `` `` when it reports nothing unfinished:
    a hold, an unfinished or interrupted action, a stopped batch or one needing attention, or any
    diagnostic."""
    hold = _obj(document.get("hold"))
    if hold:
        return _text(
            hold.get("message"), _text(hold.get("reason"), "удержание runtime")
        )
    intent = _obj(document.get("intent"))
    if _text(intent.get("status")) in ("pending", "interrupted"):
        return f"незавершённое действие recovery: {_text(intent.get('action'), '—')} ({_text(intent.get('status'))})"
    lifecycle = _obj(document.get("lifecycle"))
    if lifecycle.get("stopped") is True:
        return "batch остановлен"
    if lifecycle.get("needs_attention") is True:
        return _text(lifecycle.get("attention_reason"), "batch требует внимания")
    for item in _items(document.get("diagnostics")):
        data = _obj(item)
        return _text(data.get("message"), _text(data.get("code"), "есть диагностика"))
    return ""


class BatchHistorySource:
    """The history and a lazy, per-batch recovery gate over one client."""

    def __init__(
        self,
        repo: Path,
        runner: CommandRunner = capturing_runner,
        *,
        api: CoordinatorApi | None = None,
    ) -> None:
        self.api = api or CoordinatorApi(repo, runner)
        self._entries: dict[str, RecoveryEntry] = {}
        self.history = History()

    def reload(self) -> History:
        self.history = load_history(self.api)
        self._entries.clear()
        return self.history

    def recovery_entry(self, batch_id: str) -> RecoveryEntry:
        """Asks `recovery status` for `batch_id` on first use and remembers the answer."""
        cached = self._entries.get(batch_id)
        if cached is not None:
            return cached
        result = self.api.call(
            ("recovery", "status"), {"batch": batch_id, "json": True}
        )
        entry = self._entry_from(batch_id, result)
        self._entries[batch_id] = entry
        return entry

    def forget(self, batch_id: str) -> None:
        self._entries.pop(batch_id, None)

    @staticmethod
    def _entry_from(batch_id: str, result: ApiResult) -> RecoveryEntry:
        # A refusal is a document too: the core printed its findings and exited 2.
        if (
            result.outcome not in (Outcome.DOCUMENT, Outcome.REFUSED)
            or result.document is None
        ):
            text = result.problem_text or result.outcome.value
            return RecoveryEntry(
                batch_id, False, State.NOT_CHECKED, f"не проверено: {text}"
            )
        reason = recovery_reason(result.document)
        if reason:
            return RecoveryEntry(batch_id, True, State.WARN, reason)
        return RecoveryEntry(
            batch_id,
            False,
            State.OK,
            "ядро не сообщает приостановки или незавершённой операции",
        )
