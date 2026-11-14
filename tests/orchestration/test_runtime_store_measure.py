"""The cost of ``dispatch status`` (with and without ``--batch``) and ``dispatch heartbeat`` before
and after the cutover, on a ledger the size of this repository's (ADR 0020, section 3; criterion
carried from #778).

The test is optional: it runs only when ``HARNESS_MEASURE_STATE_DIR`` names a copy of a state
directory that was taken while no dispatch was live. The directory is read, never changed. A
file-ledger source is copied twice into the temporary directory of the test: in the first copy the
file ledger answers; the second is cut over with ``harness-runtime migrate`` and served by a real
runtime. A runtime-store source has already been cut over, so it is copied in place — ``runtime.db``
through the SQLite backup API, the small JSON pointers beside it — and served without a migrate
phase; its size is counted from the store instead of the file ledger. Each command runs
``HARNESS_MEASURE_RUNS`` times (30 by default; ``HARNESS_MEASURE_FILE_RUNS`` sets the runs of the
file ledger, whose commands read the whole history and take minutes) as the CLI process that a user
starts, and the wall clock of each run gives the percentiles. ``dispatch status`` must answer within
2 s and ``dispatch status --batch`` within 0.5 s (``BUDGETS``). A file-ledger source must hold at
least 478 dispatches (``MIN_DISPATCHES``); a runtime-store source records the store's actual size,
because that threshold is the ticket's 2026-11-03 figure and not a property of the store. The result
is printed as one JSON document, with the file-ledger and runtime-store numbers side by side, and
written to the file named by ``HARNESS_MEASURE_OUT`` when it is set.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import sqlite3
import sys
import time
from pathlib import Path

import pytest

from .runtime_store_support import (
    STATE_REL,
    ServingRuntime,
    coordinator_repository,
    coordinator_with,
    migrate,
    write_coordinator_state,
)

STATE_DIR = os.environ.get("HARNESS_MEASURE_STATE_DIR")
RUNS = int(os.environ.get("HARNESS_MEASURE_RUNS", "30"))
# A command of the file ledger reads the whole history: minutes on a ledger of this size, so its
# runs may be fewer than those of the runtime store.
FILE_RUNS = int(os.environ.get("HARNESS_MEASURE_FILE_RUNS", str(RUNS)))

pytestmark = [
    pytest.mark.skipif(not STATE_DIR, reason="set HARNESS_MEASURE_STATE_DIR to measure"),
    pytest.mark.skipif(sys.platform == "win32", reason="the seam tests drive a Unix-socket runtime"),
]


def _percentile(sorted_samples: list[float], percent: float) -> float:
    """The nearest-rank percentile of samples that are sorted."""
    rank = max(1, math.ceil(percent / 100 * len(sorted_samples)))
    return sorted_samples[rank - 1]


def _summary(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    return {
        "p50": round(_percentile(ordered, 50), 3),
        "p95": round(_percentile(ordered, 95), 3),
        "p99": round(_percentile(ordered, 99), 3),
        "min": round(ordered[0], 3),
        "max": round(ordered[-1], 3),
    }


def _working_dispatch(repo: Path, runtime: ServingRuntime | None, dispatch: str) -> None:
    """Send the approved dispatch and let its worker report itself: the dispatch is working."""
    sent = coordinator_with(repo, runtime, "dispatch", "send", "--dispatch", dispatch)
    assert sent.returncode == 0, sent.stderr
    reported = coordinator_with(
        repo,
        runtime,
        "dispatch",
        "self-report",
        "--dispatch",
        dispatch,
        "--model",
        "sonnet",
        "--worktree",
        json.loads(sent.stdout)["worker_worktree"],
    )
    assert reported.returncode == 0, reported.stderr


# The budget of ADR 0020, section 3: the whole liveness view, and the same view of one batch.
BUDGETS = {"dispatch status": 2.0, "dispatch status --batch": 0.5}
# The size of the ledger this repository had when the budgets were accepted (T26 base #795).
MIN_DISPATCHES = 478


def _measure(
    repo: Path,
    runtime: ServingRuntime | None,
    dispatch: str | None,
    batch: str,
    runs: int,
) -> dict[str, dict[str, float]]:
    """The wall clock of each command, ``runs`` times. A runtime-store command runs once before
    the measured runs, so the first request of the runtime does not count; the file ledger has no
    process to warm up, and each of its runs reads the whole history anyway. ``dispatch`` names the
    working dispatch of ``dispatch heartbeat``; a store-epoch copy measures the read commands only,
    because no worker of the copy is live."""
    commands = {
        "dispatch status": ["dispatch", "status"],
        "dispatch status --batch": ["dispatch", "status", "--batch", batch],
    }
    if dispatch is not None:
        commands["dispatch heartbeat"] = ["dispatch", "heartbeat", "--dispatch", dispatch]
    found: dict[str, dict[str, float]] = {}
    for name, arguments in commands.items():
        if runtime is not None:
            warm = coordinator_with(repo, runtime, *arguments)
            assert warm.returncode == 0, warm.stderr
        samples = []
        for _ in range(runs):
            started = time.perf_counter()
            result = coordinator_with(repo, runtime, *arguments)
            samples.append(time.perf_counter() - started)
            assert result.returncode == 0, result.stderr
        found[name] = {**_summary(samples), "runs": float(runs)}
    return found


def _size(state: Path) -> dict[str, int]:
    """What the ledger holds: the records of the selected generation and the bytes of the state."""
    pointer = json.loads((state / "ledger.json").read_text(encoding="utf-8"))
    generation = state / "generations" / pointer["generation"]

    def count(directory: str) -> int:
        return sum(1 for _ in (generation / directory).glob("*.json"))

    return {
        "batches": count("batches"),
        "dispatches": count("dispatches"),
        "audit_files": count("audit"),
        "reports": count("reports"),
        "bytes": sum(path.stat().st_size for path in state.rglob("*") if path.is_file()),
    }


def _epoch(state: Path) -> str:
    """The epoch the state directory selects: ``ledger.json`` is its selector (ADR 0020, section 1)."""
    pointer = json.loads((state / "ledger.json").read_text(encoding="utf-8"))
    return "runtime-store" if pointer.get("version") == 4 else "file-ledger"


def _copy_store_state(source: Path, state: Path) -> None:
    """A consistent read-only copy of a runtime-store state directory.

    The SQLite backup API takes the ``runtime.db`` snapshot, WAL included, of the live store; the
    small JSON files beside it are the epoch pointers, not records, and are copied as they are. So
    are the ``teardown.json`` records of the executions: without them the runtime of the copy
    repeats, through the container engine, the removal of every exited container execution at
    each reconcile and each ``execution.observe``, which the runtime of the source does not. The
    source is opened ``mode=ro`` and is never written."""
    state.mkdir(parents=True)
    for name in ("ledger.json", "AUTHORITY.json"):
        (state / name).write_bytes((source / name).read_bytes())
    for record in source.glob("executions/*/teardown.json"):
        target = state / record.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(record.read_bytes())
    with (
        contextlib.closing(
            sqlite3.connect(f"file:{source / 'runtime.db'}?mode=ro", uri=True)
        ) as live,
        contextlib.closing(sqlite3.connect(state / "runtime.db")) as copy,
    ):
        live.backup(copy)


def _store_size(database: Path) -> dict[str, int]:
    """What the store holds: the rows of its record tables and the bytes of the database."""

    def count(store: sqlite3.Connection, table: str) -> int:
        return int(store.execute(f"SELECT count(*) FROM {table}").fetchone()[0])

    with contextlib.closing(sqlite3.connect(database)) as store:
        return {
            "batches": count(store, "batch"),
            "dispatches": count(store, "dispatch"),
            "statuses": count(store, "dispatch_status"),
            "audit_records": count(store, "audit"),
            "bytes": database.stat().st_size,
        }


def _largest_batch(database: Path) -> str:
    """The batch of the store with the most dispatches: the ``--batch`` view of the measurement."""
    with contextlib.closing(sqlite3.connect(database)) as store:
        row = store.execute(
            "SELECT batch_id FROM dispatch GROUP BY batch_id "
            "ORDER BY count(*) DESC, batch_id LIMIT 1"
        ).fetchone()
    assert row is not None, "the store holds no dispatch"
    return str(row[0])


def _check_budgets(after: dict[str, dict[str, float]]) -> None:
    """The accepted budgets of ADR 0020, section 3, on the p95 of the measured runs."""
    for name, budget in BUDGETS.items():
        assert after[name]["p95"] <= budget, f"{name}: {after[name]} exceeds {budget} s"


def _measure_store_epoch(tmp_path: Path, source: Path) -> None:
    """A store-epoch copy measured where it stands: the cutover already ran, so this phase has no
    migrate step and records the store's own size instead of the file ledger's."""
    repo = coordinator_repository(tmp_path / "store")
    state = repo / STATE_REL
    _copy_store_state(source, state)
    batch = _largest_batch(state / "runtime.db")
    runtime = ServingRuntime(repo)
    try:
        after = _measure(repo, runtime, None, batch, RUNS)
    finally:
        runtime.stop()
    result: dict[str, object] = {
        "source_epoch": "runtime-store",
        "runs": {"runtime_store": RUNS},
        "ledger": _store_size(state / "runtime.db"),
        "budgets": BUDGETS,
        "seconds": {"runtime_store": after},
    }
    _write(result)
    _check_budgets(after)
    print(json.dumps(result, indent=2, sort_keys=True))


def _measure_file_epoch(tmp_path: Path, source: Path) -> None:
    """A file-ledger copy: the file ledger answers first, the second copy is cut over and served
    by a real runtime, and both are measured side by side."""
    (tmp_path / "file").mkdir()
    (tmp_path / "store").mkdir()
    file_repo, file_ids = write_coordinator_state(
        tmp_path / "file", report=False, ticket="#99901", state_from=source
    )
    store_repo, store_ids = write_coordinator_state(
        tmp_path / "store", report=False, ticket="#99902", state_from=source
    )
    size = _size(file_repo / STATE_REL)
    assert size["dispatches"] >= MIN_DISPATCHES, size
    result: dict[str, object] = {
        "source_epoch": "file-ledger",
        "runs": {"file_ledger": FILE_RUNS, "runtime_store": RUNS},
        "ledger": size,
        "budgets": BUDGETS,
    }

    started = time.perf_counter()
    cut_over = migrate(store_repo)
    result["migrate_seconds"] = round(time.perf_counter() - started, 1)
    assert cut_over.returncode == 0, cut_over.stderr
    runtime = ServingRuntime(store_repo)
    try:
        _working_dispatch(store_repo, runtime, store_ids["dispatch_id"])
        after = _measure(
            store_repo,
            runtime,
            store_ids["dispatch_id"],
            store_ids["batch_id"],
            RUNS,
        )
    finally:
        runtime.stop()
    result["seconds"] = {"runtime_store": after}
    _write(result)
    _check_budgets(after)

    _working_dispatch(file_repo, None, file_ids["dispatch_id"])
    before = _measure(
        file_repo, None, file_ids["dispatch_id"], file_ids["batch_id"], FILE_RUNS
    )
    result["seconds"] = {"file_ledger": before, "runtime_store": after}
    _write(result)
    print(json.dumps(result, indent=2, sort_keys=True))


def test_dispatch_status_before_and_after_the_cutover_is_within_its_budget(
    tmp_path: Path,
) -> None:
    assert STATE_DIR is not None
    source = Path(STATE_DIR)
    if _epoch(source) == "runtime-store":
        _measure_store_epoch(tmp_path, source)
    else:
        _measure_file_epoch(tmp_path, source)


def _write(document: dict[str, object]) -> None:
    """The result so far, in the file named by ``HARNESS_MEASURE_OUT``: a run of the file ledger
    takes minutes, so what is measured is kept as soon as it is known."""
    destination = os.environ.get("HARNESS_MEASURE_OUT")
    if destination:
        Path(destination).write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
