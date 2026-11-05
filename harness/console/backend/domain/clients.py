"""The surfaces that start console jobs."""

from __future__ import annotations

from typing import Literal

ClientKind = Literal["tui", "browser", "unknown"]
# Older clients that do not name themselves are recorded as `unknown`.
CLIENT_KINDS: tuple[ClientKind, ...] = ("tui", "browser", "unknown")
