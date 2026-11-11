"""The orchestration source of the console events: the project's file ledger, or the runtime
store in the runtime-store epoch. The console only reads it."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from harness.orchestration.core.constants import STATE_REL
from harness.orchestration.ledger.lifecycle import (
    POINTER_NAME,
    JsonObject,
    LifecycleLedger,
    store_is_authority,
)

from ...kernel.json_fields import text
from ..application.ports import SourceUnavailable
from ..domain.events import BatchFacts, Observation

STORE_READ_TIMEOUT_SECONDS = 2
_STORE_COLLECTIONS = ("batches", "dispatch-status", "qa-lane")

# ``state.read`` of the runtime store: the records by path and the store revision.
type StoreFetch = Callable[
    [Sequence[str], Sequence[str]], tuple[Mapping[str, object], int | None]
]


def _list_records(directory: Path) -> list[Path]:
    try:
        return sorted(
            entry for entry in directory.iterdir() if entry.name.endswith(".json")
        )
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise SourceUnavailable(
            "unreadable", f"{directory.name}: {type(exc).__name__}"
        ) from exc


def _observation(
    store: str,
    batches: Mapping[str, JsonObject],
    statuses: Mapping[str, JsonObject],
    attempts: Mapping[str, JsonObject],
    outcome: Callable[[str], str | None],
) -> Observation:
    """The observation of one poll from the batch, dispatch-status and qa-lane attempt records;
    ``outcome`` reads the outcome of a reported QA dispatch."""
    facts: dict[str, BatchFacts] = {}
    for record in batches.values():
        batch_id = record.get("batch_id")
        if not isinstance(batch_id, str) or not batch_id:
            continue
        entries = record.get("dispatches")
        decisions = record.get("coordinator_decisions")
        facts[batch_id] = BatchFacts(
            ticket=text(record.get("ticket")),
            state=text(record.get("state")),
            branch=text(record.get("branch")),
            dispatches=tuple(
                (
                    text(entry.get("dispatch_id")),
                    text(entry.get("role")),
                    text(entry.get("state")),
                )
                for entry in (entries if isinstance(entries, list) else [])
                if isinstance(entry, dict) and text(entry.get("dispatch_id"))
            ),
            decisions=tuple(
                entry
                for entry in (decisions if isinstance(decisions, list) else [])
                if isinstance(entry, dict)
            ),
        )
    dispatch_states = {
        text(record.get("dispatch_id")): text(record.get("state"))
        for record in statuses.values()
        if text(record.get("dispatch_id"))
    }
    qa_outcomes: dict[str, str] = {}
    for batch in facts.values():
        for dispatch_id, role, entry_state in batch.dispatches:
            state = dispatch_states.get(dispatch_id) or entry_state
            if role == "qa" and state == "reported":
                found = outcome(dispatch_id)
                if found is not None:
                    qa_outcomes[dispatch_id] = found
    return Observation(store, facts, dispatch_states, qa_outcomes, dict(attempts))


class ProjectReader:
    """Reads the project's orchestration state. Unchanged files are not read again: a record is
    cached by its file signature, and a record that cannot be read keeps its last value."""

    def __init__(self, repo: Path, *, store_fetch: StoreFetch | None = None) -> None:
        self.repo = repo
        self._store_fetch = store_fetch or self._runtime_fetch
        self._records: dict[Path, tuple[tuple[int, int, int], JsonObject]] = {}
        self._outcomes: dict[str, str] = {}
        self._store_revision: int | None = None
        self._store_view: Observation | None = None

    def _runtime_fetch(
        self, collections: Sequence[str], paths: Sequence[str]
    ) -> tuple[Mapping[str, object], int | None]:
        """``state.read`` of the runtime; the console never starts the runtime itself."""
        from harness.orchestration.runtime_client import (
            RuntimeClient,
            RuntimeClientError,
        )

        try:
            reply = RuntimeClient(self.repo).call(
                "state.read",
                operation_id=f"console.events-{uuid.uuid4().hex}",
                payload={"collections": list(collections), "paths": list(paths)},
                timeout_seconds=STORE_READ_TIMEOUT_SECONDS,
            )
        except RuntimeClientError as exc:
            reason = (
                "runtime_unavailable"
                if exc.code == "runtime_unavailable"
                else "unreadable"
            )
            raise SourceUnavailable(
                reason, f"The runtime store did not answer state.read ({exc.code})."
            ) from exc
        records = reply.result.get("records")
        return (records if isinstance(records, dict) else {}), reply.revision

    def _read_store(self) -> Observation:
        """One probe of the store revision; the collections are read only when it moved."""
        _, revision = self._store_fetch([], [])
        if (
            self._store_view is not None
            and revision is not None
            and revision == self._store_revision
        ):
            return self._store_view
        records, read_revision = self._store_fetch(_STORE_COLLECTIONS, [])

        def section(prefix: str) -> dict[str, JsonObject]:
            return {
                path: record
                for path, record in records.items()
                if path.startswith(prefix) and isinstance(record, dict)
            }

        def outcome(dispatch_id: str) -> str | None:
            if dispatch_id not in self._outcomes:
                path = f"reports/{dispatch_id}.json"
                report = self._store_fetch([], [path])[0].get(path)
                if not isinstance(report, dict):
                    return None
                self._outcomes[dispatch_id] = text(report.get("outcome"), "unknown")
            return self._outcomes[dispatch_id]

        observation = _observation(
            "runtime-store",
            section("batches/"),
            section("dispatch-status/"),
            section("qa-lane/attempts/"),
            outcome,
        )
        self._store_revision = read_revision if read_revision is not None else revision
        self._store_view = observation
        return observation

    def _directory(self, directory: Path) -> dict[str, JsonObject]:
        found: dict[str, JsonObject] = {}
        for path in _list_records(directory):
            try:
                info = path.stat()
            except FileNotFoundError:
                continue
            signature = (info.st_ino, info.st_mtime_ns, info.st_size)
            cached = self._records.get(path)
            if cached is not None and cached[0] == signature:
                found[path.name] = cached[1]
                continue
            record = LifecycleLedger.read_record_lenient(path)
            if record is not None:
                self._records[path] = (signature, record)
                found[path.name] = record
            elif cached is not None:
                # A record that is being rewritten keeps its last readable value.
                found[path.name] = cached[1]
        return found

    def _outcome(self, root: Path, dispatch_id: str) -> str | None:
        if dispatch_id not in self._outcomes:
            report = LifecycleLedger.read_record_lenient(
                root / "reports" / f"{dispatch_id}.json"
            )
            if report is None:
                return None
            # A report is immutable, so its outcome is read once.
            self._outcomes[dispatch_id] = text(report.get("outcome"), "unknown")
        return self._outcomes[dispatch_id]

    def read(self) -> Observation:
        state = self.repo / STATE_REL
        if not state.is_dir():
            raise SourceUnavailable(
                "missing", "The project has no orchestration ledger."
            )
        if store_is_authority(state):
            return self._read_store()
        root = LifecycleLedger(state).records_root_lenient()
        if root is None:
            if not (state / POINTER_NAME).exists():
                raise SourceUnavailable(
                    "missing", "The project has no orchestration ledger."
                )
            raise SourceUnavailable(
                "unreadable", "The ledger pointer or its generation is not readable."
            )
        return _observation(
            "ledger",
            self._directory(root / "batches"),
            self._directory(root / "dispatch-status"),
            {
                f"qa-lane/attempts/{name}": record
                for name, record in self._directory(
                    root / "qa-lane" / "attempts"
                ).items()
            },
            lambda dispatch_id: self._outcome(root, dispatch_id),
        )
