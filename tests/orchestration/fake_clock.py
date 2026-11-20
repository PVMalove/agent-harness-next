"""A clock a test moves forward instead of sleeping (``clock_site/sitecustomize.py``).

The CLI processes a test starts with ``FakeClock.env`` and a debug ``harness-runtime`` read one
file of milliseconds; ``advance`` replaces it atomically, so no reader sees a partial offset.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

SITE = Path(__file__).resolve().parent / "clock_site"


class FakeClock:
    def __init__(self, directory: Path) -> None:
        self.file = directory / "clock-offset-ms"
        self.millis = 0
        self._write()

    @property
    def env(self) -> dict[str, str]:
        """The environment of a CLI process and of the runtime that share this clock."""
        path = os.pathsep.join(
            part for part in (str(SITE), os.environ.get("PYTHONPATH", "")) if part
        )
        return {
            "PYTHONPATH": path,
            "HARNESS_TEST_CLOCK_FILE": str(self.file),
            "HARNESS_RUNTIME_TEST_CLOCK_FILE": str(self.file),
        }

    def advance(self, seconds: float) -> None:
        self.millis += round(seconds * 1000)
        self._write()

    def now(self) -> datetime:
        return datetime.now(UTC) + timedelta(milliseconds=self.millis)

    def time(self) -> float:
        """Seconds since the Unix epoch on this clock, as ``time.time``."""
        return time.time() + self.millis / 1000

    def _write(self) -> None:
        staging = self.file.with_suffix(".tmp")
        staging.write_text(str(self.millis), encoding="utf-8")
        os.replace(staging, self.file)
