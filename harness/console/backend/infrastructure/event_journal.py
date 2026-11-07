"""The console-owned, append-only journal of orchestration events that makes a cursor durable.

The file lives beside the discovery record (``.harness/.sandboxes/runs/console``). Its only
writer is the poller of the console server, which holds the project's ``Discovery`` lock, so no
other lock is needed.

Line 1 is a checkpoint header: ``{format, journal, source, base_seq, view, events}`` with the
compact view at ``base_seq`` and the last kept events. Every later line is one commit record of a
poll, ``{head, events, delta}``, where ``head`` is the previous head plus the number of events and
``delta`` changes the view exactly. A record is written and synced before its events are served,
so the head on disk is never behind a cursor a client holds. Loading stops at the first torn or
invalid line and truncates the file there: nothing after it was ever served. Compaction rewrites
the file as a new header once it keeps more than twice ``_KEPT_EVENTS`` events or records.

Standard library and harness only.
"""

from __future__ import annotations

import json
import os
import secrets
import stat
import sys
from collections.abc import Callable
from pathlib import Path

from harness.orchestration.core.constants import STATE_REL

from ...kernel.discovery import discovery_path
from ..application.ports import JournalUnavailable
from ..domain.events import Event, View
from .discovery import _private_file

JOURNAL_NAME = "orchestration-events.jsonl"
FORMAT = 1
_KEPT_EVENTS = 4096
_MAPS = ("batches", "dispatch_states", "qa_outcomes", "qa_attempts")
_JOURNAL_ID_HEX = 16

def _changes(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def view_delta(old: View | None, new: View) -> dict[str, object]:
    """The changes that turn ``old`` into ``new``: per changed map ``{set, drop}``, and ``store``."""
    base = old or {}
    delta: dict[str, object] = {}
    if base.get("store") != new.get("store"):
        delta["store"] = new.get("store")
    for name in _MAPS:
        before, after = _changes(base.get(name)), _changes(new.get(name))
        changed = {
            key: value for key, value in after.items() if before.get(key) != value
        }
        dropped = sorted(key for key in before if key not in after)
        if changed or dropped:
            delta[name] = {"set": changed, "drop": dropped}
    return delta


def apply_delta(view: View | None, delta: dict[str, object]) -> View:
    base = view or {}
    result: View = {"store": base.get("store")}
    for name in _MAPS:
        result[name] = dict(_changes(base.get(name)))
    if "store" in delta:
        result["store"] = delta["store"]
    for name in _MAPS:
        change = _changes(delta.get(name))
        target = _changes(result[name])
        target.update(_changes(change.get("set")))
        dropped = change.get("drop")
        for key in dropped if isinstance(dropped, list) else []:
            target.pop(key, None)
    return result


def _consecutive(events: object, after: int) -> list[Event] | None:
    """The events when they are objects with the seqs ``after + 1``, ``after + 2``, ..."""
    if not isinstance(events, list):
        return None
    for offset, event in enumerate(events, start=1):
        if not isinstance(event, dict) or event.get("seq") != after + offset:
            return None
    return events


def _int(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _line(value: object) -> bytes:
    """One journal line; ASCII escapes keep a lone surrogate of a ledger field encodable."""
    return json.dumps(value, ensure_ascii=True).encode() + b"\n"


class EventJournal:
    """One journal file and its kept events. ``load`` and ``write`` do file work and run in a
    thread; ``record``, ``accept``, ``checkpoint`` and ``compacted`` run on the event loop."""

    def __init__(self, path: Path, source: str) -> None:
        self.path = path
        self.source = source
        self.journal_id = ""
        self.view: View | None = None
        self.events: list[Event] = []
        self.head = 0
        self._records = 0
        self._fd: int | None = None

    @property
    def floor(self) -> int:
        """The lowest cursor that still gets every later event."""
        if not self.events:
            return self.head
        first = _int(self.events[0].get("seq"))
        return (first or 1) - 1

    def events_after(self, seq: int, limit: int) -> list[Event]:
        start = seq - self.floor
        return self.events[start : start + limit] if start >= 0 else []

    def _open(self) -> int:
        flags = os.O_RDWR | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
        flags |= getattr(os, "O_BINARY", 0)
        fd = os.open(self.path, flags)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise JournalUnavailable("the event journal is not a regular file")
            if sys.platform != "win32" and info.st_uid != os.getuid():
                raise JournalUnavailable("the event journal has a foreign owner")
        except BaseException:
            os.close(fd)
            raise
        return fd

    def load(self) -> None:
        """Restore the journal from its file, or start a new one when there is no valid header."""
        try:
            if self.path.is_symlink() or self.path.is_junction():
                raise JournalUnavailable("the event journal must not be a link")
            try:
                fd = self._open()
            except FileNotFoundError:
                self._start()
                return
            try:
                data = bytearray()
                while chunk := os.read(fd, 1 << 20):
                    data.extend(chunk)
                end = self._restore(bytes(data))
                if end is None:
                    os.close(fd)
                    fd = -1
                    self._start()
                    return
                if end < len(data):
                    # Nothing after the last valid record was ever served.
                    os.ftruncate(fd, end)
                    os.fsync(fd)
            except BaseException:
                if fd >= 0:
                    os.close(fd)
                raise
            self._fd = fd
        except OSError as exc:
            raise JournalUnavailable(type(exc).__name__) from exc

    def _restore(self, data: bytes) -> int | None:
        """Apply the header and every valid record; the offset where the valid part ends, or
        ``None`` when the header is not a valid header of this journal."""
        end = data.find(b"\n")
        if end < 0:
            return None
        try:
            header = json.loads(data[:end])
        except ValueError:
            return None
        if not isinstance(header, dict):
            return None
        journal_id, base, view = (
            header.get("journal"),
            _int(header.get("base_seq")),
            header.get("view"),
        )
        if (
            header.get("format") != FORMAT
            or header.get("source") != self.source
            or not isinstance(journal_id, str)
            or len(journal_id) != _JOURNAL_ID_HEX
            or any(char not in "0123456789abcdef" for char in journal_id)
            or base is None
            or not (view is None or isinstance(view, dict))
        ):
            return None
        kept = header.get("events")
        count = len(kept) if isinstance(kept, list) else 0
        events = _consecutive(kept, base - count)
        if events is None:
            return None
        self.journal_id, self.head, self.view = journal_id, base, view
        self.events = list(events)
        offset = end + 1
        while (end := data.find(b"\n", offset)) >= 0:
            try:
                record = json.loads(data[offset:end])
            except ValueError:
                break
            if not isinstance(record, dict):
                break
            added = _consecutive(record.get("events"), self.head)
            delta = record.get("delta")
            if (
                added is None
                or not isinstance(delta, dict)
                or record.get("head") != self.head + len(added)
            ):
                break
            self.view = apply_delta(self.view, delta)
            self.events.extend(added)
            self.head += len(added)
            self._records += 1
            offset = end + 1
        return offset

    def _start(self) -> None:
        self.journal_id = secrets.token_hex(_JOURNAL_ID_HEX // 2)
        self.view, self.events, self.head, self._records = None, [], 0, 0
        self.rewrite(self.checkpoint())

    def checkpoint(self) -> dict[str, object]:
        """The header of a compacted journal: the view at the head and the last kept events."""
        kept = self.events[-_KEPT_EVENTS:] if _KEPT_EVENTS else []
        return {
            "format": FORMAT,
            "journal": self.journal_id,
            "source": self.source,
            "base_seq": self.head,
            "view": self.view,
            "events": kept,
        }

    def rewrite(self, header: dict[str, object]) -> None:
        """Replace the file with ``header`` alone, atomically, and reopen it for appending."""
        temporary = self.path.with_name(
            ".orchestration-events-" + secrets.token_hex(8) + ".tmp"
        )
        try:
            fd = _private_file(temporary)
            with os.fdopen(fd, "wb") as stream:
                stream.write(_line(header))
                stream.flush()
                os.fsync(stream.fileno())
            # Windows refuses to replace a file this process still holds open; when the
            # replace fails, the previous file is opened again.
            self.close()
            try:
                os.replace(temporary, self.path)
            finally:
                self._fd = self._open()
        except OSError as exc:
            raise JournalUnavailable(type(exc).__name__) from exc
        finally:
            temporary.unlink(missing_ok=True)
        self._records = 0

    def record(self, events: list[Event], view: View) -> bytes | None:
        """The commit line for ``events`` and the new view, or ``None`` when nothing changed."""
        delta = view_delta(self.view, view)
        if not events and not delta:
            return None
        line = {"head": self.head + len(events), "events": events, "delta": delta}
        return _line(line)

    def write(self, line: bytes) -> None:
        """Append and sync one commit line."""
        if self._fd is None:
            raise JournalUnavailable("the event journal is not open")
        try:
            written = 0
            while written < len(line):
                written += os.write(self._fd, line[written:])
            os.fsync(self._fd)
        except OSError as exc:
            raise JournalUnavailable(type(exc).__name__) from exc

    def accept(self, events: list[Event], view: View) -> None:
        """Serve a written commit."""
        self.events.extend(events)
        self.head += len(events)
        self.view = view
        self._records += 1

    def needs_compaction(self) -> bool:
        limit = 2 * _KEPT_EVENTS
        return len(self.events) > limit or self._records > limit

    def compacted(self) -> None:
        """Keep in memory what the new header keeps."""
        self.events = self.events[-_KEPT_EVENTS:] if _KEPT_EVENTS else []

    def close(self) -> None:
        if self._fd is not None:
            fd, self._fd = self._fd, None
            os.close(fd)


def opener(repo: Path, path: Path | None = None) -> Callable[[], EventJournal]:
    """Open the journal of `repo`'s orchestration events, by default beside its discovery record."""

    def open_journal() -> EventJournal:
        where = path if path is not None else discovery_path(repo).with_name(JOURNAL_NAME)
        return EventJournal(where, str((repo / STATE_REL).resolve()))

    return open_journal
