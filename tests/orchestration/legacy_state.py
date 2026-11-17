"""The file ledger of installation 1.x as a test source (ADR 0036).

Since #1146 no coordinator command creates a ledger of versions 1-3 on a repository without
orchestration state. The tests of the migration and of the file epoch still need such a ledger as
their source: ``seed_file_ledger`` writes it with the primitives the coordinator used before."""

from __future__ import annotations

from pathlib import Path

from harness.orchestration.ledger.lifecycle import LifecycleLedger


def seed_file_ledger(state: Path) -> LifecycleLedger:
    """An empty file ledger of version 3 in ``state``, unless it already holds one."""
    ledger = LifecycleLedger(state)
    if not ledger.pointer_path.exists():
        ledger._select(ledger._new_generation("initialize"))
    return ledger


def file_ledger_source[T](test: T) -> T:
    """Mark a test that runs on a file ledger of installation 1.x instead of the runtime store
    (ADR 0036, section 5): it reaches publish, whose QA evidence only a full QA run recorded by the
    runtime gives, or it checks the file ledger itself. Fixtures that honour the mark read it as the
    ``file_ledger`` attribute of the test method."""
    setattr(test, "file_ledger", True)
    return test


def runs_on_file_ledger(case: object) -> bool:
    """Whether ``case``, a ``unittest`` case, runs on a 1.x file ledger: the case itself or its
    test method carries ``file_ledger``."""
    if getattr(case, "file_ledger", False):
        return True
    method = getattr(case, getattr(case, "_testMethodName", ""), None)
    return bool(getattr(method, "file_ledger", False))
