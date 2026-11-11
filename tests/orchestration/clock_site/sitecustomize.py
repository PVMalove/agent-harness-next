"""The test clock of a CLI process a test starts; only a test puts this directory on ``PYTHONPATH``.

``HARNESS_TEST_CLOCK_FILE`` names a file that holds a whole number of milliseconds: the wall clock
and the monotonic clock of this process run that far ahead, and ``time.sleep`` and the timeout of
``threading.Event.wait`` end as soon as the moved clock passes their end; with ``HARNESS_TEST_SLEEP_LOG`` each ``time.sleep`` also writes its
duration to that file. The debug runtime reads
the same file
(``HARNESS_RUNTIME_TEST_CLOCK_FILE``), so a test moves time for every process at once instead of
waiting for it (``tests/orchestration/fake_clock.py``).
"""

from __future__ import annotations

import datetime as _datetime
import os
import threading
import time
from typing import SupportsIndex

_FILE = os.environ.get("HARNESS_TEST_CLOCK_FILE")

if _FILE:
    _clock_file = _FILE
    _real_time = time.time
    _real_monotonic = time.monotonic
    _real_sleep = time.sleep
    _RealDatetime = _datetime.datetime

    def _offset() -> float:
        try:
            with open(_clock_file, encoding="utf-8") as handle:
                return int(handle.read().strip() or 0) / 1000
        except (OSError, ValueError):
            return 0.0

    def _time() -> float:
        return _real_time() + _offset()

    def _monotonic() -> float:
        return _real_monotonic() + _offset()

    _sleep_log = os.environ.get("HARNESS_TEST_SLEEP_LOG")

    def _sleep(duration: float | SupportsIndex) -> None:
        seconds = float(duration)
        if _sleep_log:
            # A line per pause: a test sees that the process waits, without waiting itself.
            with open(_sleep_log, "a", encoding="utf-8") as log:
                log.write(f"{seconds}\n")
        end = _monotonic() + seconds
        while (left := end - _monotonic()) > 0:
            _real_sleep(min(left, 0.01))

    class _MovedDatetime(_RealDatetime):
        @classmethod
        def now(cls, tz: _datetime.tzinfo | None = None) -> _MovedDatetime:
            return cls.fromtimestamp(_time(), tz)

    _real_event_wait = threading.Event.wait

    def _event_wait(event: threading.Event, timeout: float | None = None) -> bool:
        """``Event.wait`` that also ends when the moved clock passes its timeout."""
        if timeout is None:
            return _real_event_wait(event)
        end = _monotonic() + timeout
        while (left := end - _monotonic()) > 0:
            if _real_event_wait(event, min(left, 0.01)):
                return True
        return event.is_set()

    time.time = _time
    time.monotonic = _monotonic
    time.sleep = _sleep
    _datetime.datetime = _MovedDatetime  # type: ignore[misc]
    threading.Event.wait = _event_wait  # type: ignore[method-assign, assignment]
