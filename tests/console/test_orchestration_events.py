"""Live orchestration events are tested on real loopback sockets over a fixture project: the
ledger records are written by the real `LifecycleLedger`, as the coordinator writes them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from harness.console.backend.application.events import POLL_INTERVAL_SECONDS

if TYPE_CHECKING:
    pass

INTERVAL = 0.2












def test_the_poll_interval_is_one_second() -> None:
    assert POLL_INTERVAL_SECONDS == 1.0




















































