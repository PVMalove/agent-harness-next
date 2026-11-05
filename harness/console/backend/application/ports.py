"""What the console use cases need from the outside world; `backend/composition.py` supplies the
infrastructure that implements each port."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ...kernel.home_snapshot import HomeSnapshot


class Clock(Protocol):
    """Monotonic seconds."""

    def __call__(self) -> float: ...


class HomeCollector(Protocol):
    """Collect the Home snapshot of a project; blocks until the checks are done."""

    def __call__(self, repo: Path, /) -> HomeSnapshot: ...
