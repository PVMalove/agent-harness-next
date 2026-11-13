"""Per-link activity of the Home contour, counted from the orchestration events the console
observed: how many events per minute each link of the contour saw in the last window and how long
ago the last one was. A pure function of the events and the time; nothing here reads a file."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, fields
from datetime import datetime, timezone

# The window the counters cover. Events per minute = events in the window * 60 / window.
WINDOW_SECONDS = 300

type EventPredicate = Callable[[Mapping[str, object]], bool]


def _kind(*kinds: str) -> EventPredicate:
    return lambda event: event.get("event") in kinds


def _moved_to(state: str) -> EventPredicate:
    return lambda event: (
        event.get("event") == "dispatch.transition" and event.get("to") == state
    )


def _any_of(*predicates: EventPredicate) -> EventPredicate:
    return lambda event: any(predicate(event) for predicate in predicates)


# The links of the contour with the events each one sees; this is the one place of the mapping.
# decision: Python policy -> IPC; typed: IPC -> Rust runtime; write: runtime -> SQLite WAL;
# launch: runtime -> Supervisor; audit: runtime -> audit chain; receipts: Supervisor -> receipts.
_LINK_EVENTS: tuple[tuple[str, EventPredicate], ...] = (
    ("decision", _kind("gate.decision")),
    ("typed", _kind("batch.transition", "dispatch.transition", "gate.decision")),
    ("write", _kind("batch.transition", "dispatch.transition")),
    ("launch", _moved_to("working")),
    ("audit", lambda _event: True),
    ("receipts", _any_of(_kind("qa.run", "qa.attempt"), _moved_to("reported"))),
)
ACTIVITY_LINKS: tuple[str, ...] = tuple(link for link, _ in _LINK_EVENTS)


@dataclass(frozen=True)
class LinkActivity:
    link: str
    events_per_minute: float
    # None: the link saw no event in the window.
    last_event_age_seconds: float | None


@dataclass(frozen=True)
class HomeActivity:
    window_seconds: int
    links: tuple[LinkActivity, ...]
    last_event_age_seconds: float | None
    events_total_window: int

    def to_payload(self) -> dict[str, object]:
        return {
            "window_seconds": self.window_seconds,
            "links": [
                {
                    "link": link.link,
                    "events_per_minute": link.events_per_minute,
                    "last_event_age_seconds": link.last_event_age_seconds,
                }
                for link in self.links
            ],
            "last_event_age_seconds": self.last_event_age_seconds,
            "events_total_window": self.events_total_window,
        }

    @staticmethod
    def from_payload(value: object) -> HomeActivity:
        found = _fields(value, HomeActivity)
        links = found["links"]
        if not isinstance(links, list):
            raise ValueError("links must be a list")
        return HomeActivity(
            window_seconds=_int(found["window_seconds"]),
            links=tuple(_link_from(item) for item in links),
            last_event_age_seconds=_age(found["last_event_age_seconds"]),
            events_total_window=_int(found["events_total_window"]),
        )


def _fields(payload: object, kind: type) -> dict[str, object]:
    """The object's fields when its keys are exactly those of the dataclass `kind`."""
    if not isinstance(payload, dict):
        raise ValueError(f"{kind.__name__}: not an object")
    if set(payload) != {field.name for field in fields(kind)}:
        raise ValueError(f"{kind.__name__}: fields {sorted(map(str, payload))}")
    return {str(key): value for key, value in payload.items()}


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("expected an integer")
    return value


def _age(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected a number or null")
    return float(value)


def _link_from(value: object) -> LinkActivity:
    found = _fields(value, LinkActivity)
    name = found["link"]
    if not isinstance(name, str):
        raise ValueError("link must be a string")
    rate = _age(found["events_per_minute"])
    return LinkActivity(
        name, 0.0 if rate is None else rate, _age(found["last_event_age_seconds"])
    )


def _observed(event: Mapping[str, object]) -> datetime | None:
    value = event.get("observed_at")
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def _round(value: float) -> float:
    return round(value, 1)


def build_activity(
    events: Iterable[Mapping[str, object]], now: datetime
) -> HomeActivity:
    """The activity of the last `WINDOW_SECONDS` before `now`. An event with no readable time is
    skipped; an event stamped after `now` counts as age 0. No event in the window gives zero
    counters and no age, never an age made up."""
    seen: list[tuple[Mapping[str, object], float]] = []
    for event in events:
        moment = _observed(event)
        if moment is None:
            continue
        age = max(0.0, (now - moment).total_seconds())
        if age <= WINDOW_SECONDS:
            seen.append((event, age))
    links = []
    for name, accepts in _LINK_EVENTS:
        ages = [age for event, age in seen if accepts(event)]
        links.append(
            LinkActivity(
                name,
                _round(len(ages) * 60 / WINDOW_SECONDS),
                _round(min(ages)) if ages else None,
            )
        )
    return HomeActivity(
        WINDOW_SECONDS,
        tuple(links),
        _round(min(age for _, age in seen)) if seen else None,
        len(seen),
    )
