"""The screen snapshot service and its protocol, with injected facts; no transport."""

from __future__ import annotations

import asyncio
import json

import pytest

from harness.console.backend.api.protocol.screens import respond
from harness.console.backend.application.screens import ScreenService
from harness.console.backend.domain.snapshots import PAGE_BYTES, TextPages
from harness.console.kernel.batch_history import History
from harness.console.kernel.container_route import Authored
from harness.console.kernel.coordinator_api import ApiResult
from harness.console.kernel.protocol import MESSAGE_LIMIT
from harness.console.kernel.reports import ledger_from_payload, timeline_from_payload

from ._screen_facts import BODY, Clock, Facts, service


def _ask(screens: ScreenService, **request: object) -> dict[str, object]:
    raw = asyncio.run(respond(json.dumps({"id": 1, **request}), screens))
    assert len(raw.encode("utf-8")) < MESSAGE_LIMIT
    reply = json.loads(raw)
    assert isinstance(reply, dict)
    return reply


def _read(screens: ScreenService, **request: object) -> tuple[object, int]:
    """The whole JSON payload, from the first reply and every `snapshot.page`, with the number
    of replies it took."""
    reply = _ask(screens, **request)
    assert reply["ok"] is True, reply
    snapshot_id, text, replies = reply["snapshot_id"], str(reply["text"]), 1
    while not reply["done"]:
        reply = _ask(
            screens, type="snapshot.page", snapshot_id=snapshot_id, offset=reply["next"]
        )
        assert reply["ok"] is True, reply
        text += str(reply["text"])
        replies += 1
    return json.loads(text), replies


def test_text_pages_keep_a_bounded_number_of_texts() -> None:
    pages = TextPages(limit=2)
    first = pages.keep("a" * (PAGE_BYTES + 1))
    assert pages.page(first, 0) == ("a" * PAGE_BYTES, PAGE_BYTES, False)
    assert pages.page(first, PAGE_BYTES) == ("a", PAGE_BYTES + 1, True)
    with pytest.raises(ValueError):
        pages.page(first, PAGE_BYTES + 2)
    pages.keep("b")
    pages.keep("c")
    with pytest.raises(LookupError):
        pages.page(first, 0)


def test_a_report_body_far_above_the_message_limit_is_paged_below_it() -> None:
    screens = service(Facts())
    body, replies = _read(screens, type="reports.report", dispatch_id="d-1")
    assert body == {"output": BODY} and replies > 2


def test_the_reports_snapshot_carries_the_ledger_without_bodies_and_is_cached() -> None:
    facts, clock = Facts(), Clock()
    screens = service(facts, clock)
    first = _ask(screens, type="reports.snapshot")
    assert first["cached"] is False and first["done"] is True
    view = ledger_from_payload(json.loads(str(first["text"])))
    assert view.reports[0].report == {} and view.stages[0].report is not None
    clock.now += 5
    second = _ask(screens, type="reports.snapshot")
    assert second["cached"] is True and second["age_seconds"] == 5.0
    assert facts.calls["ledger"] == 1
    assert _ask(screens, type="reports.snapshot", force=True)["cached"] is False
    clock.now += 60
    assert _ask(screens, type="reports.snapshot")["cached"] is False
    assert facts.calls["ledger"] == 3


def test_an_online_reports_snapshot_is_always_rebuilt_and_never_cached() -> None:
    facts = Facts()
    screens = service(facts)
    for _ in range(2):
        assert _ask(screens, type="reports.snapshot", online=True)["cached"] is False
    assert facts.calls["ledger_online"] == 2 and "ledger" not in facts.calls


def test_a_timeline_and_unknown_ids_are_answered_from_the_cached_ledger() -> None:
    facts = Facts()
    screens = service(facts)
    payload, _ = _read(screens, type="reports.timeline", batch_id="b-1")
    assert timeline_from_payload(payload).batch.batch_id == "b-1"
    for request in (
        {"type": "reports.timeline", "batch_id": "b-9"},
        {"type": "reports.report", "dispatch_id": "d-9"},
    ):
        assert _ask(screens, **request)["error"] == {
            "code": "not_found",
            "message": "The ledger has no such report or batch.",
        }
    assert facts.calls["ledger"] == 1


def test_the_orchestration_snapshot_and_the_lock_poll() -> None:
    facts = Facts()
    screens = service(facts)
    payload, _ = _read(screens, type="orchestration.snapshot")
    assert isinstance(payload, dict)
    assert payload["lock"] == {"lock": {"locked": False}, "error": None}
    assert ledger_from_payload(payload["ledger"]).batches[0].batch_id == "b-1"
    facts.lock_error = OSError("занят")
    reply = _ask(screens, type="orchestration.lock")
    assert reply["ok"] is True and reply["lock"] is None and reply["error"] == "занят"
    assert "snapshot_id" not in reply


def test_the_recovery_snapshot_reads_the_status_only_for_a_selected_batch() -> None:
    facts = Facts()
    screens = service(facts)
    payload, _ = _read(screens, type="recovery.snapshot")
    assert isinstance(payload, dict) and payload["status"] is None
    assert History.from_payload(payload["history"]).batches[0].batch_id == "b-1"
    payload, _ = _read(screens, type="recovery.snapshot", batch="b-1", skip=["x"])
    assert isinstance(payload, dict)
    assert ApiResult.from_payload(payload["status"]).document == {"batch_id": "b-1"}
    assert facts.statuses == [("b-1", ("x",))] and facts.calls["history"] == 1


def test_the_container_route_snapshot_reads_the_preflight_only_for_a_batch() -> None:
    facts = Facts()
    screens = service(facts)
    payload, _ = _read(screens, type="container_route.snapshot")
    assert isinstance(payload, dict) and payload["preflight"] is None
    assert Authored.from_payload(payload["authored"]) == Authored({"roles": {}})
    payload, _ = _read(
        screens, type="container_route.snapshot", batch="b-1", role="qa", runtime="r"
    )
    assert isinstance(payload, dict)
    assert not ApiResult.from_payload(payload["preflight"]).ok
    assert facts.preflights == [("b-1", "qa", "r")]


@pytest.mark.parametrize(
    "request_body",
    [
        {"type": "reports.snapshot", "force": "yes"},
        {"type": "reports.snapshot", "extra": 1},
        {"type": "reports.report"},
        {"type": "reports.report", "dispatch_id": ""},
        {"type": "reports.report", "dispatch_id": "d" * 65},
        {"type": "reports.timeline", "batch_id": 7},
        {"type": "orchestration.lock", "force": True},
        {"type": "recovery.snapshot", "skip": "x"},
        {"type": "recovery.snapshot", "skip": ["x"] * 33},
        {"type": "recovery.snapshot", "skip": [""]},
        {"type": "container_route.snapshot", "role": ""},
        {"type": "container_route.snapshot", "runtime": "r" * 65},
        {"type": "snapshot.page", "snapshot_id": 1},
        {"type": "snapshot.page", "snapshot_id": True, "offset": 0},
        {"type": "snapshot.page", "snapshot_id": 1, "offset": -1},
    ],
)
def test_a_missing_invalid_or_extra_field_is_a_bad_request(
    request_body: dict[str, object],
) -> None:
    reply = _ask(service(Facts()), **request_body)
    assert reply["ok"] is False and reply["type"] == request_body["type"]
    assert isinstance(reply["error"], dict) and reply["error"]["code"] == "bad_request"


def test_an_expired_page_and_an_offset_beyond_the_text() -> None:
    screens = service(Facts())
    first = _ask(screens, type="orchestration.lock")
    assert first["ok"] is True
    expired = _ask(screens, type="snapshot.page", snapshot_id=99, offset=0)
    assert isinstance(expired["error"], dict)
    assert expired["error"]["code"] == "snapshot_expired"
    reply = _ask(screens, type="reports.snapshot")
    beyond = _ask(
        screens, type="snapshot.page", snapshot_id=reply["snapshot_id"], offset=10**9
    )
    assert isinstance(beyond["error"], dict) and beyond["error"]["code"] == "bad_request"


def test_a_failed_collect_names_only_the_exception_class() -> None:
    facts = Facts()

    def broken(repo: object, /) -> object:
        raise RuntimeError("secret path /home/x")

    facts.ledger = broken  # type: ignore[method-assign,assignment]
    reply = _ask(service(facts), type="reports.snapshot")
    assert reply["error"] == {"code": "collect_failed", "message": "RuntimeError"}
