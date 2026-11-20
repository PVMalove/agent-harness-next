"""Pipeline usage counted from a `LedgerView`: the TUI statistics and the Harness overview the
console server sends to the Web console read the same numbers. Standard library only."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .json_fields import text
from .reports import LedgerView


@dataclass(frozen=True)
class PipelineStats:
    """How much the pipeline has been used and how its runs ended."""

    batches: int
    tickets: int
    by_state: dict[str, int] = field(default_factory=dict)
    dispatches_by_role: dict[str, int] = field(default_factory=dict)
    reports_by_outcome: dict[str, int] = field(default_factory=dict)
    qa_runs: int = 0
    qa_attempts_failed: int = 0
    first_at: str = ""
    last_at: str = ""


def pipeline_stats(view: LedgerView) -> PipelineStats:
    dates = sorted(batch.created_at for batch in view.batches if batch.created_at)
    return PipelineStats(
        batches=len(view.batches),
        tickets=len({batch.ticket for batch in view.batches}),
        by_state=dict(Counter(batch.state for batch in view.batches)),
        dispatches_by_role=dict(
            Counter(text(record.get("role"), "?") for record in view.dispatch_records())
        ),
        reports_by_outcome=dict(Counter(entry.outcome for entry in view.reports)),
        qa_runs=len(view.qa_runs),
        qa_attempts_failed=len(view.qa_attempts),
        first_at=dates[0] if dates else "",
        last_at=dates[-1] if dates else "",
    )


def pipeline_usage(view: LedgerView) -> dict[str, object]:
    """The pipeline usage line of the Harness section as numbers: batches, distinct tickets,
    dispatches and reports, or why the ledger is unavailable (every count then 0)."""
    if view.unavailable:
        return {
            "unavailable": view.unavailable,
            "batches": 0,
            "tickets": 0,
            "dispatches": 0,
            "reports": 0,
        }
    stats = pipeline_stats(view)
    return {
        "unavailable": None,
        "batches": stats.batches,
        "tickets": stats.tickets,
        "dispatches": sum(stats.dispatches_by_role.values()),
        "reports": sum(stats.reports_by_outcome.values()),
    }
