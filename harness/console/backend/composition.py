"""The composition root of the console server: the one place that wires the infrastructure
adapters into the use cases."""

from __future__ import annotations

import functools
from pathlib import Path

from .application.ports import Clock, HomeCollector
from .application.snapshots import SnapshotService
from .domain.snapshots import HOME_TTL_SECONDS
from .infrastructure.clock import monotonic
from .infrastructure.home_facts import collect_home


def snapshot_service(
    repo: Path,
    *,
    ttl: float = HOME_TTL_SECONDS,
    clock: Clock | None = None,
    collect: HomeCollector | None = None,
    collect_online: HomeCollector | None = None,
) -> SnapshotService:
    """The Home snapshot service; a port left out gets its infrastructure adapter."""
    return SnapshotService(
        repo,
        ttl=ttl,
        clock=monotonic if clock is None else clock,
        collect=collect_home if collect is None else collect,
        collect_online=(
            functools.partial(collect_home, online=True)
            if collect_online is None
            else collect_online
        ),
    )
