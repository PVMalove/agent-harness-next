"""The Home snapshot cache rules: how long a snapshot stays fresh, which rebuilt snapshots stay
kept for paging their problems and how one page is cut. Pure: the caller passes the time."""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

from ...kernel.protocol import _clip

HOME_TTL_SECONDS = 15.0
# A `home.problems` page: the problems beyond what one Home reply lists, in wire bytes.
PAGE_BYTES = 32768
# How many rebuilt snapshots keep their problems for paging. The cached snapshot is never
# evicted while it is cached, so a Home reply that hands it out can always be paged.
KEPT_SNAPSHOTS = 4

S = TypeVar("S")


class SnapshotWindow(Generic[S]):
    """The cached snapshot with its age and id, and the rebuilt snapshots kept for paging."""

    def __init__(self, ttl: float = HOME_TTL_SECONDS) -> None:
        self._ttl = ttl
        self._snapshot: S | None = None
        self._snapshot_id = 0
        self._stamp = 0.0
        self._kept: dict[int, S] = {}
        self._last_id = 0

    def fresh(self, now: float) -> tuple[S, float, int] | None:
        """The cached snapshot with its age and id while it is younger than the TTL."""
        if self._snapshot is None:
            return None
        age = now - self._stamp
        if age >= self._ttl:
            return None
        return self._snapshot, age, self._snapshot_id

    def keep(self, snapshot: S) -> int:
        """Keep a rebuilt snapshot for paging; beyond the limit the oldest goes, but never the
        cached one, which is still handed out."""
        self._last_id += 1
        self._kept[self._last_id] = snapshot
        while len(self._kept) > KEPT_SNAPSHOTS:
            del self._kept[next(key for key in self._kept if key != self._snapshot_id)]
        return self._last_id

    def store(self, snapshot: S, now: float) -> int:
        """Keep a rebuilt snapshot and cache it as of `now`; its id."""
        snapshot_id = self.keep(snapshot)
        self._snapshot, self._stamp = snapshot, now
        self._snapshot_id = snapshot_id
        return snapshot_id

    def page(
        self, snapshot_id: int, text: Callable[[S], str], offset: int
    ) -> tuple[str, int, bool]:
        """The `text` of a kept snapshot from `offset` on, at most `PAGE_BYTES` on the wire, with
        the offset of the next page and whether this page is the last. A snapshot that is no
        longer kept is `LookupError`; an offset beyond the text is `ValueError`."""
        snapshot = self._kept.get(snapshot_id)
        if snapshot is None:
            raise LookupError(snapshot_id)
        whole = text(snapshot)
        if offset > len(whole):
            raise ValueError(offset)
        page = _clip(whole[offset : offset + PAGE_BYTES], PAGE_BYTES)
        next_offset = offset + len(page)
        return page, next_offset, next_offset == len(whole)
