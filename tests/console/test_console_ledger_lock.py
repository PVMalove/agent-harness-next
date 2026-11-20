"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

from pathlib import Path

from harness.console.tui import ledger_lock
from harness.json_types import JsonObject
from harness.orchestration.core.constants import LEDGER_LOCK_STALE_SECONDS

STALE = LEDGER_LOCK_STALE_SECONDS


def _status(**overrides: object) -> JsonObject:
    status: JsonObject = {
        "locked": True,
        "held_seconds": 200,
        "remaining_seconds": STALE - 200,
        "owner": {"pid": 5, "host": "fedora", "pid_namespace": "pid:[1]"},
        "operation": "report submit",
        "verdict": "owner-in-other-environment",
        "release_available": False,
    }
    status.update(overrides)
    return status


def test_a_free_lock_says_so() -> None:
    assert ledger_lock.lock_text({"locked": False}) == "Lock ledger свободен."


def test_the_store_epoch_shows_the_qa_lease_with_its_verdict() -> None:
    lease = {
        "owner": {"owner_kind": "dispatch", "owner_id": "dispatch-1"},
        "fencing_token": 7,
        "expires_at": "2026-10-28T00:05:00+00:00",
        "stale_heartbeat": True,
        "verdict": "owner-dead",
        "release_available": True,
    }

    free = ledger_lock.lock_text({"locked": False, "qa_lease": None})
    held = ledger_lock.lock_text({"locked": False, "qa_lease": lease})
    english = ledger_lock.lock_text({"locked": False, "qa_lease": lease}, "en")
    reused = ledger_lock.lock_text(
        {"locked": False, "qa_lease": {**lease, "verdict": "owner-pid-reused"}}
    )
    broken = ledger_lock.lock_text({"locked": False, "qa_lease": {"error": "x: y"}})

    assert free == "Lock ledger свободен.\nLease QA-lane свободен."
    assert "Lease QA-lane: dispatch dispatch-1 · fencing 7" in held
    assert "heartbeat пропущен" in held
    assert "owner-dead" in held
    assert "QA lease: dispatch dispatch-1 · fencing 7" in english
    assert "heartbeat missed" in english
    assert "не доказывает смерть" in reused
    assert "состояние недоступно: x: y" in broken
    # A file-lock panel of the file epoch has no lease line.
    assert "Lease" not in ledger_lock.lock_text(_status())


def test_the_panel_names_the_holder_its_age_and_the_time_left() -> None:
    text = ledger_lock.lock_text(_status())

    assert "Lock ledger занят: report submit" in text
    assert "pid 5 · fedora · pid:[1]" in text
    assert "Держится: 3 мин 20 с" in text
    assert f"до снятия по таймауту: {ledger_lock.duration(STALE - 200)}" in text
    assert "owner-in-other-environment" in text


def test_an_available_release_says_available() -> None:
    for verdict in ("owner-dead", "owner-unknown-stale"):
        text = ledger_lock.lock_text(
            _status(verdict=verdict, remaining_seconds=0, release_available=True)
        )
        assert "до снятия по таймауту: доступно" in text


def test_a_live_owner_is_never_announced_as_released_by_the_timeout() -> None:
    text = ledger_lock.lock_text(
        _status(verdict="owner-alive", remaining_seconds=0, release_available=False)
    )

    assert "доступно" not in text
    assert "таймаут не снимает живого владельца" in text


def test_an_owner_on_another_host_has_no_timeout_countdown() -> None:
    text = ledger_lock.lock_text(_status(verdict="owner-on-another-host"))

    assert "до снятия по таймауту: не применяется (владелец на другом хосте)" in text


def test_the_english_console_gets_an_english_panel() -> None:
    text = ledger_lock.lock_text(_status(), "en")

    assert "Ledger lock held: report submit" in text
    assert "Held for: 3 min 20 s" in text
    assert "until the timeout release:" in text
    assert "another PID namespace" in text
    assert not any("а" <= char <= "я" for char in text.lower())
    assert ledger_lock.lock_text({"locked": False}, "en") == "The ledger lock is free."


def test_durations_read_in_hours_minutes_and_seconds() -> None:
    assert ledger_lock.duration(45) == "45 с"
    assert ledger_lock.duration(200) == "3 мин 20 с"
    assert ledger_lock.duration(3900) == "1 ч 05 мин"
    assert ledger_lock.duration(-3) == "0 с"


def test_an_unreadable_state_is_shown_not_raised(tmp_path: Path) -> None:
    def broken(_repo: Path) -> JsonObject:
        raise OSError("state is unreadable")

    text = ledger_lock.current_lock_text(tmp_path, broken)

    assert text == "Lock ledger: состояние недоступно: state is unreadable"


def test_a_console_server_failure_is_shown_as_the_unavailable_text() -> None:
    from harness.console.tui.client import LockUnavailable, ServerUnavailable

    def refused(repo: Path) -> JsonObject:
        raise LockUnavailable("ledger занят")

    def down(repo: Path) -> JsonObject:
        raise ServerUnavailable("нет сервера")

    assert ledger_lock.current_lock_text(Path("."), refused) == (
        "Lock ledger: состояние недоступно: ledger занят"
    )
    assert "нет сервера" in ledger_lock.current_lock_text(Path("."), down)


def test_the_orchestration_screen_reads_its_lock_and_ledger_through_the_client() -> None:
    import pytest

    from harness.console.tui.client import LockUnavailable
    from harness.console.tui.screens import orchestration

    from ._home_client import FakeHomeClient
    from ._screen_facts import ledger

    client = FakeHomeClient(Path("."), load_ledger=lambda repo: ledger())
    found = orchestration.read_orchestration(client)
    assert found.ledger.batches[0].batch_id == "b-1"
    assert orchestration.first_lock(found) == {"locked": False}
    client.lock = "занят"
    with pytest.raises(LockUnavailable, match="занят"):
        orchestration.first_lock(orchestration.read_orchestration(client))
    with pytest.raises(LockUnavailable):
        client.ledger_lock()

    def down(*, force: bool = False) -> object:
        from harness.console.tui.client import ServerUnavailable

        raise ServerUnavailable("нет сервера")

    client.orchestration = down  # type: ignore[method-assign,assignment]
    failed = orchestration.read_orchestration(client)
    assert failed.ledger.unavailable is not None and "нет сервера" in failed.ledger.unavailable
    assert failed.lock is None and failed.lock_error == "нет сервера"
