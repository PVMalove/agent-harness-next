"""The Home contour activity use case: the per-link counters of the events the console observed.

It is computed for every `home.snapshot` reply and is never part of the cached snapshot: the
counters of a 15 second old snapshot would say events flow when they stopped."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from ...kernel.home_activity import HomeActivity, build_activity
from ..domain.events import Event
from .ports import WallClock

# What the journal keeps in memory bounds what one count reads.
EVENTS_READ = 4096


class RecentEvents(Protocol):
    """The kept orchestration events; None while the journal is not loaded."""

    def recent(self, limit: int) -> list[Event] | None: ...


class HomeActivityQuery:
    """Counts the events of the last window; `None` while the journal is not loaded. A failure to read
    it raises: `respond` turns that into a null `activity`."""

    def __init__(self, events: RecentEvents, *, now: WallClock) -> None:
        self._events = events
        self._now = now

    def __call__(self) -> HomeActivity | None:
        events = self._events.recent(EVENTS_READ)
        if events is None:
            return None
        moment = datetime.fromisoformat(self._now())
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return build_activity(events, moment)
