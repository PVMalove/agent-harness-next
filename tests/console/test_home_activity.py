"""Per-link activity of the Home contour: counters and the age of the last event, from the events
the console observed."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from harness.console.backend import composition
from harness.console.backend.api import schemas
from harness.console.backend.api.protocol.snapshots import respond
from harness.console.backend.application.home_activity import HomeActivityQuery
from harness.console.backend.application.ports import ActivitySource
from harness.console.kernel.home_activity import (
    ACTIVITY_LINKS,
    WINDOW_SECONDS,
    HomeActivity,
    LinkActivity,
    build_activity,
)
from harness.console.kernel.home_snapshot import (
    HomeSnapshot,
    RecentSession,
    RouteStep,
    build_home_snapshot,
)

from .test_snapshots import DATA, FULL_CONTEXT, CountingCollect, FakeClock

NOW = datetime(2026, 11, 13, 12, 0, 0, tzinfo=timezone.utc)


def _event(kind: str, ago: float, **fields: object) -> dict[str, object]:
    return {
        "seq": 1,
        "observed_at": (NOW - timedelta(seconds=ago)).isoformat(),
        "event": kind,
        **fields,
    }


def _link(activity: HomeActivity, name: str) -> LinkActivity:
    return next(link for link in activity.links if link.link == name)


def test_empty_journal_gives_zero_counters_and_no_age() -> None:
    activity = build_activity([], NOW)
    assert activity.window_seconds == WINDOW_SECONDS
    assert activity.events_total_window == 0
    assert activity.last_event_age_seconds is None
    assert [link.link for link in activity.links] == list(ACTIVITY_LINKS)
    for link in activity.links:
        assert link.events_per_minute == 0
        assert link.last_event_age_seconds is None


def test_events_outside_the_window_are_not_counted() -> None:
    activity = build_activity([_event("gate.decision", WINDOW_SECONDS + 1)], NOW)
    assert activity.events_total_window == 0
    assert activity.last_event_age_seconds is None
    assert all(link.last_event_age_seconds is None for link in activity.links)


def test_event_on_the_window_boundary_is_counted() -> None:
    activity = build_activity([_event("gate.decision", WINDOW_SECONDS)], NOW)
    assert activity.events_total_window == 1
    assert _link(activity, "decision").events_per_minute == 0.2


def test_each_kind_feeds_its_links() -> None:
    events = [
        _event("gate.decision", 10),
        _event("batch.transition", 20, to="active"),
        _event("dispatch.transition", 30, to="working"),
        _event("dispatch.transition", 40, to="reported"),
        _event("qa.run", 50),
        _event("qa.attempt", 60),
    ]
    activity = build_activity(events, NOW)
    assert activity.events_total_window == 6
    assert activity.last_event_age_seconds == 10
    # gate.decision only.
    assert _link(activity, "decision").events_per_minute == 0.2
    assert _link(activity, "decision").last_event_age_seconds == 10
    # batch + dispatch (two) + gate.decision.
    assert _link(activity, "typed").events_per_minute == 0.8
    # batch + dispatch (two).
    assert _link(activity, "write").events_per_minute == 0.6
    assert _link(activity, "write").last_event_age_seconds == 20
    # dispatch.transition to working only.
    assert _link(activity, "launch").events_per_minute == 0.2
    assert _link(activity, "launch").last_event_age_seconds == 30
    # every event.
    assert _link(activity, "audit").events_per_minute == 1.2
    # qa.run + qa.attempt + dispatch.transition to reported.
    assert _link(activity, "receipts").events_per_minute == 0.6
    assert _link(activity, "receipts").last_event_age_seconds == 40


def test_age_is_never_negative_and_unparsable_times_are_skipped() -> None:
    activity = build_activity(
        [
            _event("gate.decision", -5),
            {"event": "gate.decision", "observed_at": "not a time"},
            {"event": "gate.decision"},
        ],
        NOW,
    )
    assert activity.events_total_window == 1
    assert activity.last_event_age_seconds == 0


def test_naive_times_are_read_as_utc() -> None:
    naive = (NOW - timedelta(seconds=30)).replace(tzinfo=None).isoformat()
    activity = build_activity([{"event": "qa.run", "observed_at": naive}], NOW)
    assert activity.last_event_age_seconds == 30


def test_payload_is_json_plain() -> None:
    activity = build_activity([_event("qa.run", 12.34)], NOW)
    payload = activity.to_payload()
    assert payload["window_seconds"] == WINDOW_SECONDS
    assert payload["last_event_age_seconds"] == 12.3
    assert isinstance(payload["links"], list)
    assert payload["links"][0] == {
        "link": "decision",
        "events_per_minute": 0,
        "last_event_age_seconds": None,
    }
    assert payload["events_per_minute"] == 0.2
    json.dumps(payload)


def test_the_wire_schema_names_exactly_the_links_the_kernel_counts() -> None:
    from typing import get_args

    from harness.console.backend.api.schemas import LinkActivityPayload

    assert (
        get_args(LinkActivityPayload.model_fields["link"].annotation) == ACTIVITY_LINKS
    )


def test_old_client_still_parses_the_snapshot_without_activity() -> None:
    snapshot = build_home_snapshot(DATA, FULL_CONTEXT)
    wire = json.loads(json.dumps(snapshot.to_payload()))
    assert "activity" not in wire
    assert HomeSnapshot.from_payload(wire) == snapshot


def test_snapshot_keeps_the_updated_at_of_recent_sessions() -> None:
    context = replace(
        FULL_CONTEXT,
        recent_sessions=(
            RecentSession(
                "b-1",
                "#1",
                "active",
                "feature/x",
                "2026-11-01T10:00:00+00:00",
                (RouteStep("developer", "working"),),
                updated_at="2026-11-01T10:30:00+00:00",
            ),
        ),
    )
    snapshot = build_home_snapshot(DATA, context)
    assert snapshot.recent_sessions[0].updated_at == "2026-11-01T10:30:00+00:00"
    payload = snapshot.to_payload()
    assert payload["recent_sessions"][0]["updated_at"] == "2026-11-01T10:30:00+00:00"  # type: ignore[index]


# The reply of `home.snapshot` carries the activity beside the cached snapshot.


def _ask(
    activity: ActivitySource | None, collect: CountingCollect | None = None
) -> dict[str, object]:
    service = composition.snapshot_service(
        Path("."), clock=FakeClock(), collect=collect or CountingCollect()
    )
    raw = asyncio.run(
        respond('{"id": "a", "type": "home.snapshot"}', service, activity)
    )
    reply = json.loads(raw)
    assert isinstance(reply, dict)
    schemas.REPLIES.validate_python(reply)
    return reply


def test_reply_carries_the_activity_counted_for_it() -> None:
    activity = build_activity([_event("qa.run", 5)], NOW)
    reply = _ask(lambda: activity)
    assert reply["activity"] == activity.to_payload()


def test_reply_activity_is_null_without_a_source_or_when_it_has_no_data() -> None:
    assert _ask(None)["activity"] is None
    assert _ask(lambda: None)["activity"] is None


def test_reply_activity_is_null_when_the_source_fails() -> None:
    def broken() -> HomeActivity:
        raise RuntimeError("journal")

    reply = _ask(broken)
    assert reply["ok"] is True and reply["activity"] is None


def test_the_snapshot_itself_is_the_same_with_and_without_activity() -> None:
    plain = _ask(None)
    live = _ask(lambda: build_activity([_event("qa.run", 5)], NOW))
    assert plain["snapshot"] == live["snapshot"]


def test_each_reply_counts_the_activity_again_while_the_snapshot_is_cached() -> None:
    collect = CountingCollect()
    service = composition.snapshot_service(
        Path("."), clock=FakeClock(), collect=collect
    )
    counts = iter([1, 2])

    def source() -> HomeActivity:
        return build_activity([_event("qa.run", 5)] * next(counts), NOW)

    async def scenario() -> list[dict[str, dict[str, object]]]:
        replies = []
        for _ in range(2):
            raw = await respond('{"id": 1, "type": "home.snapshot"}', service, source)
            replies.append(json.loads(raw))
        return replies

    first, second = asyncio.run(scenario())
    assert (first["cached"], second["cached"]) == (False, True)  # type: ignore[comparison-overlap]
    assert collect.calls == 1
    assert first["activity"]["events_total_window"] == 1
    assert second["activity"]["events_total_window"] == 2


class _Recent:
    def __init__(self, events: list[dict[str, object]] | None) -> None:
        self.events = events

    def recent(self, limit: int) -> list[dict[str, object]] | None:
        return self.events


def test_query_counts_against_the_wall_clock() -> None:
    query = HomeActivityQuery(
        _Recent([_event("gate.decision", 20)]),
        now=lambda: NOW.isoformat(),
    )
    activity = query()
    assert activity is not None
    assert activity.last_event_age_seconds == 20


def test_query_without_a_journal_has_no_data() -> None:
    assert HomeActivityQuery(_Recent(None), now=lambda: NOW.isoformat())() is None


def test_recent_events_of_the_journal_are_bounded_and_oldest_first(
    tmp_path: Path,
) -> None:
    from harness.console.backend.domain.events import BatchFacts, Observation

    states = iter(["active", "paused", "active", "paused"])

    class Reader:
        def read(self) -> Observation:
            return Observation(
                store="file",
                batches={"b": BatchFacts("#1", next(states, "paused"), (), ())},
            )

    events = composition.orchestration_events(
        tmp_path, reader=Reader(), interval=0.01, journal_path=tmp_path / "j.jsonl"
    )
    assert events.recent(10) is None

    async def scenario() -> list[dict[str, object]]:
        await events.ensure_started()
        kept: list[dict[str, object]] = []
        for _ in range(100):
            kept = events.recent(10) or []
            if len(kept) >= 2:
                break
            await asyncio.sleep(0.02)
        await events.close()
        return kept

    kept = asyncio.run(scenario())
    assert [event["seq"] for event in kept] == sorted(event["seq"] for event in kept)  # type: ignore[type-var]
    assert all(event["event"] == "batch.transition" for event in kept)
    assert 2 <= len(kept) <= 10
