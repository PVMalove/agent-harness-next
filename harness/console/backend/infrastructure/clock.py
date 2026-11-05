"""The server's clocks."""

from __future__ import annotations

import time


def monotonic() -> float:
    """Monotonic seconds for cache ages."""
    return time.monotonic()
