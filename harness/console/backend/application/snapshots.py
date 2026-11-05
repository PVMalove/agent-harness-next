"""The Home snapshot use case: serve it from a short cache, rebuild it one collect at a time off
the event loop and page the problems of a kept snapshot."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from ...kernel.home_snapshot import HomeSnapshot, problems_text
from ..domain.snapshots import HOME_TTL_SECONDS, SnapshotWindow
from .ports import Clock, HomeCollector


@dataclass(frozen=True)
class Served:
    """A snapshot as served: whether it came from the cache, how old it is and the id under
    which its problems are paged."""

    snapshot: HomeSnapshot
    cached: bool
    age_seconds: float
    snapshot_id: int


class SnapshotService:
    """Serves the Home snapshot from a short cache so that the expensive checks (health, drift)
    do not rerun on every request. One rebuild runs at a time and never on the event loop."""

    def __init__(
        self,
        repo: Path,
        *,
        ttl: float = HOME_TTL_SECONDS,
        clock: Clock,
        collect: HomeCollector,
        collect_online: HomeCollector,
    ) -> None:
        self._repo = repo
        self._clock = clock
        self._collect = collect
        self._collect_online = collect_online
        self._building: asyncio.Task[Served] | None = None
        self._window: SnapshotWindow[HomeSnapshot] = SnapshotWindow(ttl)

    def _fresh(self) -> Served | None:
        found = self._window.fresh(self._clock())
        if found is None:
            return None
        snapshot, age, snapshot_id = found
        return Served(snapshot, True, age, snapshot_id)

    async def _rebuild(self) -> Served:
        """The collect, as a task of its own: it records its result and ends the rebuild even
        when every request that waited for it was cancelled."""
        try:
            snapshot = await asyncio.to_thread(self._collect, self._repo)
            snapshot_id = self._window.store(snapshot, self._clock())
            return Served(snapshot, False, 0.0, snapshot_id)
        finally:
            self._building = None

    async def home(self, *, force: bool = False) -> Served:
        """The cached snapshot while it is younger than the TTL, else a rebuilt one. `force`
        always rebuilds. A failed collect raises and leaves the cache as it was. A request that
        is cancelled while it waits does not cancel the collect: the next one waits for it."""
        while True:
            # A rebuild that finished while this request waited serves it too.
            if not force and (served := self._fresh()) is not None:
                return served
            if self._building is None:
                break
            await asyncio.wait({self._building})
        task = self._building = asyncio.create_task(self._rebuild())
        # Nobody may be left to read the outcome of a collect whose requester went away.
        task.add_done_callback(lambda done: done.cancelled() or done.exception())
        await asyncio.wait({task})
        return task.result()

    async def home_online(self) -> Served:
        """A snapshot with the online checks, always rebuilt and never cached: the cache keeps
        the offline facts the TTL is about."""
        snapshot = await asyncio.to_thread(self._collect_online, self._repo)
        return Served(snapshot, False, 0.0, self._window.keep(snapshot))

    def problems_page(self, snapshot_id: int, offset: int) -> tuple[str, int, bool]:
        """The `problems_text` of a kept snapshot from `offset` on, at most `PAGE_BYTES` on the
        wire, with the offset of the next page and whether this page is the last. A snapshot
        that is no longer kept is `LookupError`; an offset beyond the text is `ValueError`."""
        return self._window.page(
            snapshot_id, lambda snapshot: problems_text(snapshot.problems), offset
        )
