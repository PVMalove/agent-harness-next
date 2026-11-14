"""The pending decisions use case: the list is rebuilt off the event loop on every request."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

from ..domain.approvals import DecisionsSnapshot


class DecisionService:
    """Builds the decision list off the event loop on every request; nothing is cached."""

    def __init__(
        self,
        repo: Path,
        *,
        collect: Callable[[Path], DecisionsSnapshot],
    ) -> None:
        self.repo = repo.resolve()
        self._collect = collect

    async def snapshot(self) -> DecisionsSnapshot:
        return await asyncio.to_thread(self._collect, self.repo)
