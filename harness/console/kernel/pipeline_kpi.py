"""Pipeline KPIs the console server computes from the ledger and the clients only show.

The Web console's Orchestration and Reports screens open with a KPI row (WIP and its oldest item,
rework, QA first-pass, stale batches, cycle time). Every figure here comes from the ledger view the
server already reads; a figure the ledger cannot give stays `None`, never a demo value. Standard
library only, like the rest of the textual-free seam."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Mapping, Sequence

from .json_fields import text
from ...orchestration.core.constants import BatchState
from .reports import BatchSummary, LedgerView, StageEntry, timestamp

# The batch states that still hold work: WIP is their count.
WIP_STATES = ("planned", "awaiting-approval", "active", "blocked")
# An active batch with no stage activity for this long is reported as stale.
STALE_AFTER = timedelta(hours=6)
THROUGHPUT_DAYS = 7
# The report outcome that counts as a pass of the first QA report of a ticket.
PASS_OUTCOME = "completed"
# The batch states the console knows; any other state counts as unknown.
KNOWN_BATCH_STATES = frozenset(state.value for state in BatchState)
# An unfinished dispatch without a heartbeat for this long is stale (the ledger's own default).
STALE_DISPATCH_AFTER = timedelta(hours=2)

KPI_KEYS = frozenset(
    {
        "wip",
        "oldest_wip_seconds",
        "awaiting_approval",
        "oldest_approval_seconds",
        "blocked",
        "stale",
        "rework",
        "qa_first_pass",
        "qa_tickets",
        "cycle_p50_seconds",
        "cycle_p95_seconds",
        "throughput_7d",
        "failed",
        "unknown",
        "batches",
        "rework_batches",
        "flow_efficiency_pct",
    }
)


@dataclass(frozen=True)
class PipelineKpi:
    """The KPI row of the pipeline; a missing figure is `None`."""

    wip: int = 0
    oldest_wip_seconds: int | None = None
    awaiting_approval: int = 0
    oldest_approval_seconds: int | None = None
    blocked: int = 0
    stale: int = 0
    # Dispatches beyond the first of a (batch, role): the work that went round again.
    rework: int = 0
    # Tickets whose first QA report passed, out of the tickets that have a QA report.
    qa_first_pass: int = 0
    qa_tickets: int = 0
    cycle_p50_seconds: int | None = None
    cycle_p95_seconds: int | None = None
    # Batches whose PR was opened in the last seven days.
    throughput_7d: int = 0
    failed: int = 0
    # Batches in a state the console does not know.
    unknown: int = 0
    # Every batch of the ledger, and those with rework: the denominator and numerator of
    # "rework N of M".
    batches: int = 0
    rework_batches: int = 0
    # Worker time (dispatch to report) over the cycle time (batch to PR), in percent; None without
    # a batch that opened its PR.
    flow_efficiency_pct: int | None = None

    def to_payload(self) -> dict[str, int | None]:
        return {key: getattr(self, key) for key in sorted(KPI_KEYS)}


def _percentile(values: Sequence[float], share: float) -> int | None:
    """The nearest-rank percentile of `values`; None without values."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(share * len(ordered)))
    return int(ordered[rank - 1])


def _age(start: str, now: datetime) -> float | None:
    moment = timestamp(start)
    return max(0.0, (now - moment).total_seconds()) if moment else None


def _last_activity(batch: BatchSummary, stages: Sequence[StageEntry]) -> datetime | None:
    moments = [timestamp(stage.at) for stage in stages if stage.batch_id == batch.batch_id]
    moments.append(timestamp(batch.created_at))
    known = [moment for moment in moments if moment is not None]
    return max(known) if known else None


def _qa_first_pass(view: LedgerView) -> tuple[int, int]:
    """(tickets whose first QA report passed, tickets with a QA report)."""
    firsts: dict[str, tuple[str, str]] = {}
    for report in sorted(view.reports, key=lambda item: item.reported_at):
        if report.role == "qa":
            firsts.setdefault(report.ticket, (report.reported_at, report.outcome))
    passed = sum(outcome == PASS_OUTCOME for _, outcome in firsts.values())
    return passed, len(firsts)


def pipeline_kpi(view: LedgerView, now: datetime | None = None) -> PipelineKpi:
    """The KPIs of `view` at `now` (the current time by default); empty when the ledger is
    unavailable."""
    if view.unavailable:
        return PipelineKpi()
    now = now or datetime.now(UTC)
    in_flight = [batch for batch in view.batches if batch.state in WIP_STATES]
    ages = [age for batch in in_flight if (age := _age(batch.created_at, now)) is not None]
    approval = [batch for batch in view.batches if batch.state == "awaiting-approval"]
    approval_ages = [
        age for batch in approval if (age := _age(batch.created_at, now)) is not None
    ]
    stale = 0
    for batch in view.batches:
        if batch.state != "active":
            continue
        last = _last_activity(batch, view.stages)
        if last is not None and now - last > STALE_AFTER:
            stale += 1
    per_role: Mapping[tuple[str, str], int] = Counter(
        (stage.batch_id, stage.role) for stage in view.stages
    )
    rework = sum(count - 1 for count in per_role.values() if count > 1)
    cycles: list[float] = []
    opened = 0
    window = now - timedelta(days=THROUGHPUT_DAYS)
    for batch in view.batches:
        start, pull = timestamp(batch.created_at), timestamp(batch.pr_created_at)
        if start is None or pull is None:
            continue
        cycles.append(max(0.0, (pull - start).total_seconds()))
        if pull >= window:
            opened += 1
    passed, with_qa = _qa_first_pass(view)
    reworked = {batch_id for (batch_id, _), count in per_role.items() if count > 1}
    return PipelineKpi(
        unknown=sum(batch.state not in KNOWN_BATCH_STATES for batch in view.batches),
        batches=len(view.batches),
        rework_batches=len(reworked),
        flow_efficiency_pct=_flow_efficiency(view),
        wip=len(in_flight),
        oldest_wip_seconds=int(max(ages)) if ages else None,
        awaiting_approval=len(approval),
        oldest_approval_seconds=int(max(approval_ages)) if approval_ages else None,
        blocked=sum(batch.state == "blocked" for batch in view.batches),
        stale=stale,
        rework=rework,
        qa_first_pass=passed,
        qa_tickets=with_qa,
        cycle_p50_seconds=_percentile(cycles, 0.5),
        cycle_p95_seconds=_percentile(cycles, 0.95),
        throughput_7d=opened,
        failed=sum(batch.state == "failed" for batch in view.batches),
    )


def _stage_seconds(stage: StageEntry) -> float | None:
    """From the dispatch to its report; None for a stage without both moments."""
    start = timestamp(stage.started_at)
    end = timestamp(stage.report.reported_at) if stage.report else None
    return max(0.0, (end - start).total_seconds()) if start and end else None


def _flow_efficiency(view: LedgerView) -> int | None:
    worked = cycle = 0.0
    for batch in view.batches:
        start, pull = timestamp(batch.created_at), timestamp(batch.pr_created_at)
        if start is None or pull is None:
            continue
        cycle += max(0.0, (pull - start).total_seconds())
        worked += sum(
            seconds
            for stage in view.stages
            if stage.batch_id == batch.batch_id
            and (seconds := _stage_seconds(stage)) is not None
        )
    return min(100, round(100 * worked / cycle)) if cycle > 0 else None


def pipeline_kpi_from_payload(value: object) -> PipelineKpi:
    """The KPIs a `PipelineKpi.to_payload` result describes; `ValueError` when it is outside the
    schema."""
    numbers = _numbers(value, KPI_KEYS, "kpi")
    optional = {
        "oldest_wip_seconds",
        "oldest_approval_seconds",
        "cycle_p50_seconds",
        "cycle_p95_seconds",
        "flow_efficiency_pct",
    }
    if any(numbers[key] is None for key in KPI_KEYS - optional):
        raise ValueError("kpi payload: a count is missing")
    return PipelineKpi(**numbers)  # type: ignore[arg-type]


def duration_text(seconds: int | None, language: str = "ru") -> str:
    """`3 ч 20 мин`, `2 дн 4 ч`; `—` without a figure."""
    if seconds is None:
        return "—"
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    day_unit, hour_unit, minute_unit = (
        ("дн", "ч", "мин") if language == "ru" else ("d", "h", "min")
    )
    if days:
        return f"{days} {day_unit} {hours} {hour_unit}"
    if hours:
        return f"{hours} {hour_unit} {minutes} {minute_unit}"
    return f"{minutes} {minute_unit}"


# -- Reports KPIs ------------------------------------------------------------------------------

REPORTS_KPI_KEYS = frozenset(
    {
        "reports",
        "evidence_complete",
        "latency_p50_seconds",
        "latency_p95_seconds",
        "qa_first_pass",
        "qa_tickets",
        "attention",
        "blocked",
        "stale_evidence",
    }
)


@dataclass(frozen=True)
class ReportsKpi:
    """The KPI row of the Reports screen; a missing figure is `None`."""

    reports: int = 0
    # Reports with an output and valid risk and blocker records, out of `reports`.
    evidence_complete: int = 0
    # From the dispatch to its report.
    latency_p50_seconds: int | None = None
    latency_p95_seconds: int | None = None
    qa_first_pass: int = 0
    qa_tickets: int = 0
    # Reports that carry a recorded risk, and those that carry a blocker.
    attention: int = 0
    blocked: int = 0
    # QA reports without a QA gate log of their own dispatch written at or after the dispatch
    # started: the evidence they cite is older than the run, or missing.
    stale_evidence: int = 0

    def to_payload(self) -> dict[str, int | None]:
        return {key: getattr(self, key) for key in sorted(REPORTS_KPI_KEYS)}


def _evidence_present(value: object) -> bool:
    return isinstance(value, dict) and bool(value.get("status") == "present")


def _evidence_valid(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != {"status", "details"}:
        return False
    details = value["details"]
    if value["status"] == "none":
        return bool(details == "")
    return bool(
        value["status"] == "present" and isinstance(details, str) and details.strip()
    )


def _report_complete(body: Mapping[str, object]) -> bool:
    output = body.get("output")
    return (
        isinstance(output, str)
        and bool(output.strip())
        and _evidence_valid(body.get("risks"))
        and _evidence_valid(body.get("blockers"))
    )


def reports_kpi(view: LedgerView) -> ReportsKpi:
    """The Reports KPIs of `view`, read from the whole report bodies; empty without a ledger."""
    if view.unavailable:
        return ReportsKpi()
    delays: list[float] = []
    for stage in view.stages:
        created = view._dispatches.get(stage.dispatch_id, {}).get("created_at")
        reported, started = (
            timestamp(stage.report.reported_at) if stage.report else None,
            timestamp(created) if isinstance(created, str) else None,
        )
        if reported is not None and started is not None:
            delays.append(max(0.0, (reported - started).total_seconds()))
    passed, with_qa = _qa_first_pass(view)
    return ReportsKpi(
        stale_evidence=_stale_evidence(view),
        reports=len(view.reports),
        evidence_complete=sum(_report_complete(report.report) for report in view.reports),
        latency_p50_seconds=_percentile(delays, 0.5),
        latency_p95_seconds=_percentile(delays, 0.95),
        qa_first_pass=passed,
        qa_tickets=with_qa,
        attention=sum(_evidence_present(report.report.get("risks")) for report in view.reports),
        blocked=sum(_evidence_present(report.report.get("blockers")) for report in view.reports),
    )


def _stale_evidence(view: LedgerView) -> int:
    started = {stage.dispatch_id: timestamp(stage.started_at) for stage in view.stages}
    stale = 0
    for report in view.reports:
        if report.role != "qa":
            continue
        start = started.get(report.dispatch_id)
        fresh = any(
            run.dispatch_id == report.dispatch_id
            and (logged := timestamp(run.logged_at)) is not None
            and (start is None or logged >= start)
            for run in view.qa_runs
        )
        stale += not fresh
    return stale


def reports_kpi_from_payload(value: object) -> ReportsKpi:
    """The KPIs a `ReportsKpi.to_payload` result describes; `ValueError` outside the schema."""
    numbers = _numbers(value, REPORTS_KPI_KEYS, "reports kpi")
    optional = {"latency_p50_seconds", "latency_p95_seconds"}
    if any(numbers[key] is None for key in REPORTS_KPI_KEYS - optional):
        raise ValueError("reports kpi payload: a count is missing")
    return ReportsKpi(**numbers)  # type: ignore[arg-type]


def _numbers(value: object, keys: frozenset[str], what: str) -> dict[str, int | None]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{what} payload: unexpected fields")
    numbers: dict[str, int | None] = {}
    for key, item in value.items():
        if item is not None and (not isinstance(item, int) or isinstance(item, bool)):
            raise ValueError(f"{what}.{key} is not an integer")
        numbers[key] = item
    return numbers


# -- Orchestration analytics -------------------------------------------------------------------

ANALYTICS_SECTIONS = ("flow", "quality", "runtime", "gates")
AGING_BUCKETS = ("lt_1d", "d1_3", "d3_7", "gt_7d")
# The age buckets of an unfinished dispatch; `aging_by_role` keys are "<role>:<bucket>".
STAGE_AGING_BUCKETS = ("lt_15m", "m15_60", "h1_4", "gt_4h")
type Figure = int | None | list[int] | dict[str, int]


@dataclass(frozen=True)
class PipelineAnalytics:
    """The four analytics tabs of the Orchestration screen: flow, quality, runtime and gates.
    Each section maps a figure name to a count, a duration in seconds (`None` when unknown), a list
    of counts or a map of counts."""

    flow: Mapping[str, Figure]
    quality: Mapping[str, Figure]
    runtime: Mapping[str, Figure]
    gates: Mapping[str, Figure]

    def to_payload(self) -> dict[str, Mapping[str, Figure]]:
        return {name: getattr(self, name) for name in ANALYTICS_SECTIONS}


def _bucket(seconds: float) -> str:
    days = seconds / 86400
    if days < 1:
        return "lt_1d"
    if days < 3:
        return "d1_3"
    return "d3_7" if days < 7 else "gt_7d"


def _stage_bucket(seconds: float) -> str:
    minutes = seconds / 60
    if minutes < 15:
        return "lt_15m"
    if minutes < 60:
        return "m15_60"
    return "h1_4" if minutes < 240 else "gt_4h"


def _by_role_percentile(
    values: Mapping[str, list[float]], share: float
) -> dict[str, int]:
    return {
        role: found
        for role, items in sorted(values.items())
        if (found := _percentile(items, share)) is not None
    }


def _role_flow_figures(view: LedgerView, now: datetime) -> dict[str, Figure]:
    """Per-role flow figures: unfinished dispatches and their age buckets, the dispatch-to-report
    p50/p95, and the p50 wait from the previous report of the batch to the dispatch."""
    current: Counter[str] = Counter()
    aging: Counter[str] = Counter()
    durations: dict[str, list[float]] = {}
    waits: dict[str, list[float]] = {}
    by_batch: dict[str, list[StageEntry]] = {}
    for stage in view.stages:
        by_batch.setdefault(stage.batch_id, []).append(stage)
        if not stage.finished:
            current[stage.role] += 1
            age = _age(stage.started_at or stage.at, now)
            if age is not None:
                aging[f"{stage.role}:{_stage_bucket(age)}"] += 1
        seconds = _stage_seconds(stage)
        if seconds is not None:
            durations.setdefault(stage.role, []).append(seconds)
    for stages in by_batch.values():
        reported = sorted(
            moment
            for stage in stages
            if stage.report and (moment := timestamp(stage.report.reported_at))
        )
        for stage in stages:
            start = timestamp(stage.started_at)
            before = [moment for moment in reported if start and moment <= start]
            if start is not None and before:
                waits.setdefault(stage.role, []).append(
                    (start - before[-1]).total_seconds()
                )
    return {
        "current_by_role": dict(current),
        "aging_by_role": dict(aging),
        "stage_p50_by_role": _by_role_percentile(durations, 0.5),
        "stage_p95_by_role": _by_role_percentile(durations, 0.95),
        "wait_p50_by_role": _by_role_percentile(waits, 0.5),
    }


def _findings_by_severity(view: LedgerView) -> dict[str, int]:
    found: Counter[str] = Counter()
    for report in view.reports:
        review = report.report.get("review")
        if not isinstance(review, dict):
            continue
        for axis in ("standards", "spec"):
            evidence = review.get(axis)
            findings = evidence.get("findings") if isinstance(evidence, dict) else None
            for item in findings if isinstance(findings, list) else []:
                if isinstance(item, dict):
                    found[text(item.get("severity"), "unknown")] += 1
    return dict(found)


def _runtime_figures(view: LedgerView, now: datetime) -> dict[str, Figure]:
    """Heartbeat age p95 and stale dispatches of the unfinished stages, and the oldest
    unfinished stage per role."""
    beats: list[float] = []
    stale = 0
    oldest: dict[str, int] = {}
    for stage in view.stages:
        if stage.finished:
            continue
        beat = _age(stage.heartbeat_at, now) if stage.heartbeat_at else None
        if beat is not None:
            beats.append(beat)
        silence = beat if beat is not None else _age(stage.started_at or stage.at, now)
        if silence is not None and silence > STALE_DISPATCH_AFTER.total_seconds():
            stale += 1
        age = _age(stage.started_at or stage.at, now)
        if age is not None:
            oldest[stage.role] = max(oldest.get(stage.role, 0), int(age))
    return {
        "heartbeat_age_p95_seconds": _percentile(beats, 0.95),
        "stale_dispatches": stale,
        "open_age_by_role": oldest,
    }


def _gate_figures(view: LedgerView) -> dict[str, Figure]:
    """Coordinator decisions by verdict, and the p50/p95 latency from the report a decision
    follows to the decision, keyed by the role of that report."""
    verdicts: Counter[str] = Counter()
    latency: dict[str, list[float]] = {}
    for batch_id, record in view._batch_records.items():
        reports = sorted(
            (moment, stage.role)
            for stage in view.stages
            if stage.batch_id == batch_id
            and stage.report
            and (moment := timestamp(stage.report.reported_at))
        )
        decisions = record.get("coordinator_decisions")
        for decision in decisions if isinstance(decisions, list) else []:
            if not isinstance(decision, dict):
                continue
            verdicts[text(decision.get("decision"), "unknown")] += 1
            at = timestamp(text(decision.get("approved_at")))
            before = [item for item in reports if at and item[0] <= at]
            if at is not None and before:
                moment, role = before[-1]
                latency.setdefault(role, []).append((at - moment).total_seconds())
    return {
        "decisions_by_verdict": dict(verdicts),
        "latency_p50_by_gate": _by_role_percentile(latency, 0.5),
        "latency_p95_by_gate": _by_role_percentile(latency, 0.95),
    }


def pipeline_analytics(view: LedgerView, now: datetime | None = None) -> PipelineAnalytics:
    """The analytics of `view` at `now`, from the ledger only; empty sections without a ledger."""
    if view.unavailable:
        return PipelineAnalytics({}, {}, {}, {})
    now = now or datetime.now(UTC)
    aging = {name: 0 for name in AGING_BUCKETS}
    for batch in view.batches:
        age = _age(batch.created_at, now) if batch.state in WIP_STATES else None
        if age is not None:
            aging[_bucket(age)] += 1
    today = now.date()
    per_day = [0] * THROUGHPUT_DAYS
    cycles: list[float] = []
    for batch in view.batches:
        start, pull = timestamp(batch.created_at), timestamp(batch.pr_created_at)
        if start is None or pull is None:
            continue
        cycles.append(max(0.0, (pull - start).total_seconds()))
        offset = (today - pull.date()).days
        if 0 <= offset < THROUGHPUT_DAYS:
            per_day[THROUGHPUT_DAYS - 1 - offset] += 1
    flow: dict[str, Figure] = {
        "by_state": dict(Counter(batch.state for batch in view.batches)),
        "aging": aging,
        "pr_per_day": per_day,
        "cycle_p50_seconds": _percentile(cycles, 0.5),
        "cycle_p95_seconds": _percentile(cycles, 0.95),
        **_role_flow_figures(view, now),
    }
    per_role: Counter[tuple[str, str]] = Counter(
        (stage.batch_id, stage.role) for stage in view.stages
    )
    rework_by_role: Counter[str] = Counter()
    for (_, role), count in per_role.items():
        if count > 1:
            rework_by_role[role] += count - 1
    passed, with_qa = _qa_first_pass(view)
    quality: dict[str, Figure] = {
        "rework_by_role": dict(rework_by_role),
        "reports_by_role": dict(Counter(report.role for report in view.reports)),
        "outcomes": dict(Counter(report.outcome for report in view.reports)),
        "qa_attempts_failed": len(view.qa_attempts),
        "qa_first_pass": passed,
        "qa_tickets": with_qa,
        "findings_by_severity": _findings_by_severity(view),
        "returns_by_role": dict(
            Counter(
                report.role for report in view.reports if report.outcome != PASS_OUTCOME
            )
        ),
    }
    open_ages = [
        age
        for stage in view.stages
        if not stage.finished and (age := _age(stage.at, now)) is not None
    ]
    runtime: dict[str, Figure] = {
        "stage_states": dict(Counter(stage.state for stage in view.stages)),
        "unfinished": sum(not stage.finished for stage in view.stages),
        "oldest_unfinished_seconds": int(max(open_ages)) if open_ages else None,
        "stale": pipeline_kpi(view, now).stale,
        **_runtime_figures(view, now),
    }
    waiting = [
        age
        for batch in view.batches
        if batch.state == "awaiting-approval"
        and (age := _age(batch.created_at, now)) is not None
    ]
    gates: dict[str, Figure] = {
        "awaiting": len(waiting),
        "approval_p50_seconds": _percentile(waiting, 0.5),
        "approval_p95_seconds": _percentile(waiting, 0.95),
        "approval_oldest_seconds": int(max(waiting)) if waiting else None,
        "pr_states": dict(Counter(batch.pr_state for batch in view.batches)),
        **_gate_figures(view),
    }
    return PipelineAnalytics(flow, quality, runtime, gates)


def _figure(value: object, where: str) -> Figure:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, list) and all(
        isinstance(item, int) and not isinstance(item, bool) for item in value
    ):
        return list(value)
    if isinstance(value, dict) and all(
        isinstance(key, str) and isinstance(item, int) and not isinstance(item, bool)
        for key, item in value.items()
    ):
        return dict(value)
    raise ValueError(f"{where} is not a figure")


def pipeline_analytics_from_payload(value: object) -> PipelineAnalytics:
    """The analytics a `PipelineAnalytics.to_payload` result describes; `ValueError` outside the
    schema."""
    if not isinstance(value, dict) or set(value) != set(ANALYTICS_SECTIONS):
        raise ValueError("analytics payload: unexpected sections")
    sections: dict[str, dict[str, Figure]] = {}
    for name in ANALYTICS_SECTIONS:
        section = value[name]
        if not isinstance(section, dict):
            raise ValueError(f"analytics.{name} is not an object")
        sections[name] = {
            str(key): _figure(item, f"analytics.{name}.{key}")
            for key, item in section.items()
        }
    return PipelineAnalytics(**sections)
