"""The server's clocks."""

from __future__ import annotations

import time
from datetime import datetime, timezone


def monotonic() -> float:
    """Monotonic seconds for cache ages."""
    return time.monotonic()


def utc_now_iso() -> str:
    """The current UTC time for journal records."""
    return datetime.now(timezone.utc).isoformat()
