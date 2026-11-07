"""Current state and usage statistics for the Harness and Orchestration sections.

Stdlib-only, like the rest of the textual-free seam: the installation state comes from
`.harness/harness.lock` and the skills directory, the pipeline statistics from a `LedgerView`
already read by harness.console.kernel.reports."""

from __future__ import annotations

from collections import Counter

from ..kernel.harness_facts import HarnessState as HarnessState
from ..kernel.harness_facts import harness_state as harness_state
from ..kernel import brand, i18n
from ..kernel.pipeline_kpi import (
    AGING_BUCKETS,
    PipelineAnalytics,
    PipelineKpi,
    ReportsKpi,
    duration_text,
)
from ..kernel.pipeline_stats import PipelineStats as PipelineStats
from ..kernel.pipeline_stats import pipeline_stats as pipeline_stats
from ..kernel.reports import BatchSummary, LedgerView

# The batch lifecycle in order: planned → awaiting-approval ↔ active → a terminal state.
BATCH_STATES = (
    "planned",
    "awaiting-approval",
    "active",
    "blocked",
    "completed",
    "failed",
    "not-required",
    "abandoned",
)
STATE_LABELS = {
    "planned": "запланирован",
    "awaiting-approval": "ждёт подтверждения",
    "active": "в работе",
    "blocked": "заблокирован",
    "completed": "завершён",
    "failed": "провален",
    "not-required": "не требуется",
    "abandoned": "отменён",
}
ALL_STATES = "all"


def short_time(value: str) -> str:
    """An ISO timestamp as `YYYY-MM-DD HH:MM`; anything else is returned unchanged."""
    return (
        value[:16].replace("T", " ") if len(value) >= 16 and value[10] == "T" else value
    )


def _counts(counts: dict[str, int]) -> str:
    return (
        ", ".join(f"{name} {count}" for name, count in sorted(counts.items())) or "нет"
    )


def pipeline_stats_text(stats: PipelineStats) -> str:
    if not stats.batches:
        return "Пайплайн ещё не запускался: batch в леджере нет."
    states = ", ".join(
        f"{STATE_LABELS.get(state, state)} {stats.by_state[state]}"
        for state in state_order(stats.by_state)
    )
    period = f"{short_time(stats.first_at) or '?'} — {short_time(stats.last_at) or '?'}"
    return "\n".join(
        (
            f"Запусков (batch): {stats.batches}, тикетов: {stats.tickets}",
            f"По состояниям: {states}",
            f"Диспатчи по ролям: {_counts(stats.dispatches_by_role)}",
            f"Отчёты по итогам: {_counts(stats.reports_by_outcome)}",
            f"QA-прогонов: {stats.qa_runs}, неудачных попыток qa-lane: {stats.qa_attempts_failed}",
            f"Период: {period}",
        )
    )


def pipeline_stats_fields(stats: PipelineStats) -> list[tuple[str, str]]:
    """(label, value) for each line of `pipeline_stats_text`, so a screen can show the label and its
    value apart."""
    if not stats.batches:
        return []
    return [
        (label, value)
        for label, _, value in (
            line.partition(": ") for line in pipeline_stats_text(stats).split("\n")
        )
    ]


def state_order(by_state: dict[str, int]) -> list[str]:
    """Known lifecycle states in lifecycle order, then any unknown state the ledger holds."""
    known = [state for state in BATCH_STATES if by_state.get(state)]
    return known + sorted(state for state in by_state if state not in BATCH_STATES)


def state_filter_items(view: LedgerView) -> list[tuple[str, str]]:
    """(key, label) for the state filter: every lifecycle state with its count, "all" first."""
    counts = Counter(batch.state for batch in view.batches)
    items = [(ALL_STATES, f"все ({len(view.batches)})")]
    states = list(BATCH_STATES) + sorted(s for s in counts if s not in BATCH_STATES)
    items.extend(
        (state, f"{STATE_LABELS.get(state, state)} ({counts.get(state, 0)})")
        for state in states
    )
    return items


def batches_in_state(view: LedgerView, state: str) -> list[BatchSummary]:
    """The batches in one state, newest first; `ALL_STATES` returns every batch."""
    if state == ALL_STATES:
        return list(view.batches)
    return [batch for batch in view.batches if batch.state == state]


def batch_label(batch: BatchSummary) -> str:
    state = STATE_LABELS.get(batch.state, batch.state)
    return f"{batch.ticket} · {state} · {short_time(batch.created_at) or 'дата неизвестна'}\n  {batch.batch_id}"


def harness_state_text(state: HarnessState, harness_version: str) -> str:
    if not state.installed:
        return "Харнесс не установлен: нет читаемого .harness/harness.lock."
    version = state.installed_version
    if version != harness_version:
        version += f" (версия пакета харнесса: {harness_version})"
    return "\n".join(
        (
            f"Установлена версия: {version}",
            f"Capability: {', '.join(state.capabilities) or 'нет'}",
            f"Скилов: {state.skills}, управляемых файлов: {state.managed_files}",
            f"Lock обновлён: {state.updated_at}",
            f"Оркестрация: {'подключена' if state.orchestration else 'не подключена'}",
        )
    )


def usage_text(view: LedgerView) -> str:
    """Pipeline usage for the Harness section: a one-line summary of the ledger."""
    if view.unavailable:
        return f"Использование пайплайна: {view.unavailable}"
    stats = pipeline_stats(view)
    return (
        f"Использование пайплайна: запусков {stats.batches}, тикетов {stats.tickets}, "
        f"диспатчей {sum(stats.dispatches_by_role.values())}, отчётов "
        f"{sum(stats.reports_by_outcome.values())}"
    )


def harness_summary_fields(
    state: HarnessState, package_version: str
) -> list[tuple[str, str]]:
    """Compact facts for Harness, retaining the verbose shared state renderer unchanged."""
    if not state.installed:
        return [
            ("Состояние", "Харнесс не установлен: нет читаемого .harness/harness.lock.")
        ]
    mismatch = state.installed_version != package_version
    return [
        (
            "Версия",
            state.installed_version + (f" ⚠ ({package_version})" if mismatch else " ✔"),
        ),
        ("Состав", ", ".join(state.capabilities) or "нет"),
        ("Скилов", str(state.skills)),
        ("файлов", str(state.managed_files)),
        ("Lock", state.updated_at),
        ("Оркестрация", "✔ подключена" if state.orchestration else "○ не подключена"),
    ]


def kpi_tiles(kpi: PipelineKpi, language: str) -> list[tuple[str, str, str, str]]:
    """(label, figure, hint, colour) of each KPI tile of the Orchestration screen. A figure that
    needs attention starts with its status symbol, so the colour is never the only signal."""

    def tr(text: str) -> str:
        return i18n.tr(language, text)

    def flagged(count: int, level: str) -> tuple[str, str]:
        if not count:
            return str(count), ""
        return f"{brand.STATUS_ICONS[level]} {count}", {"warn": "warning", "fail": "error"}[level]

    def duration(seconds: int | None) -> str:
        return duration_text(seconds, language)

    stale, stale_colour = flagged(kpi.stale, "warn")
    blocked, blocked_colour = flagged(kpi.blocked, "warn")
    first_pass = (
        f"{kpi.qa_first_pass} / {kpi.qa_tickets}  ({round(100 * kpi.qa_first_pass / kpi.qa_tickets)}%)"
        if kpi.qa_tickets
        else "—"
    )
    return [
        (tr("В работе (WIP)"), str(kpi.wip), f"{tr('старейший')} {duration(kpi.oldest_wip_seconds)}", ""),
        (
            tr("Ждёт подтверждения"),
            str(kpi.awaiting_approval),
            f"{tr('старейший')} {duration(kpi.oldest_approval_seconds)}",
            "",
        ),
        (tr("Заблокировано"), blocked, "", blocked_colour),
        (tr("Без движения"), stale, tr("активные > 6 ч"), stale_colour),
        (tr("QA с первого раза"), first_pass, tr("по тикетам"), ""),
        (tr("Доработки"), str(kpi.rework), tr("повторные диспатчи"), ""),
        (
            tr("Цикл до PR"),
            f"{duration(kpi.cycle_p50_seconds)} / {duration(kpi.cycle_p95_seconds)}",
            "p50 / p95",
            "",
        ),
        (
            tr("PR за 7 дней"),
            str(kpi.throughput_7d),
            f"{brand.STATUS_ICONS['fail']} {tr('провалено')} {kpi.failed}" if kpi.failed else "",
            "",
        ),
    ]


def reports_kpi_tiles(kpi: ReportsKpi, language: str) -> list[tuple[str, str, str, str]]:
    """(label, figure, hint, colour) of each KPI tile of the Reports screen; a figure that needs
    attention starts with its status symbol."""

    def tr(text: str) -> str:
        return i18n.tr(language, text)

    def share(part: int, total: int) -> str:
        return f"{part} / {total}  ({round(100 * part / total)}%)" if total else "—"

    def flagged(count: int) -> tuple[str, str]:
        if not count:
            return str(count), ""
        return f"{brand.STATUS_ICONS['warn']} {count}", "warning"

    risks, risks_colour = flagged(kpi.attention)
    blockers, blockers_colour = flagged(kpi.blocked)
    latency = (
        f"{duration_text(kpi.latency_p50_seconds, language)} / "
        f"{duration_text(kpi.latency_p95_seconds, language)}"
    )
    return [
        (tr("Отчётов"), str(kpi.reports), "", ""),
        (tr("Evidence полно"), share(kpi.evidence_complete, kpi.reports), tr("output, risks, blockers"), ""),
        (tr("Задержка отчёта"), latency, "p50 / p95", ""),
        (tr("QA с первого раза"), share(kpi.qa_first_pass, kpi.qa_tickets), tr("по тикетам"), ""),
        (tr("С рисками"), risks, tr("отчёты с записанным риском"), risks_colour),
        (tr("С блокерами"), blockers, tr("отчёты с блокером"), blockers_colour),
    ]


_SPARK = "▁▂▃▄▅▆▇█"
_AGING_LABELS = {"lt_1d": "< 1 дн", "d1_3": "1–3 дн", "d3_7": "3–7 дн", "gt_7d": "> 7 дн"}
_AGING_LABELS_EN = {"lt_1d": "< 1 d", "d1_3": "1–3 d", "d3_7": "3–7 d", "gt_7d": "> 7 d"}


def _count_text(counts: object, labels: dict[str, str] | None = None) -> str:
    """`name 3 · other 1`, the largest first; `—` for none."""
    if not isinstance(counts, dict) or not counts:
        return "—"
    items = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return " · ".join(f"{(labels or {}).get(name, name)} {count}" for name, count in items)


def _spark(values: object) -> str:
    """The seven daily counts as bars and numbers; `—` without any."""
    if not isinstance(values, list) or not any(values):
        return "—"
    peak = max(values)
    bars = "".join(_SPARK[round((len(_SPARK) - 1) * value / peak)] if value else " " for value in values)
    return f"{bars}  ({' '.join(str(value) for value in values)})"


def _seconds(value: object, language: str) -> str:
    return duration_text(value if isinstance(value, int) else None, language)


def analytics_rows(
    section: str, analytics: PipelineAnalytics, language: str
) -> list[tuple[str, str]]:
    """(label, value) rows of one analytics tab: `flow`, `quality`, `runtime` or `gates`. Only the
    figures the ledger gave are shown; an empty section says so in one row."""

    def tr(text: str) -> str:
        return i18n.tr(language, text)

    figures = getattr(analytics, section)
    if not figures:
        return [(tr("Данные"), tr("в ledger нет данных"))]
    aging = _AGING_LABELS if language == "ru" else _AGING_LABELS_EN
    if section == "flow":
        buckets = figures.get("aging", {})
        return [
            (tr("Батчи по состояниям"), _count_text(figures.get("by_state"), {k: tr(v) for k, v in STATE_LABELS.items()})),
            (
                tr("Возраст незавершённых"),
                " · ".join(f"{aging[name]} {buckets.get(name, 0)}" for name in AGING_BUCKETS) if isinstance(buckets, dict) else "—",
            ),
            (tr("PR по дням, 7 дней"), _spark(figures.get("pr_per_day"))),
            (
                tr("Цикл до PR p50 / p95"),
                f"{_seconds(figures.get('cycle_p50_seconds'), language)} / {_seconds(figures.get('cycle_p95_seconds'), language)}",
            ),
        ]
    if section == "quality":
        passed, total = figures.get("qa_first_pass", 0), figures.get("qa_tickets", 0)
        return [
            (tr("Доработки по ролям"), _count_text(figures.get("rework_by_role"))),
            (tr("Отчёты по ролям"), _count_text(figures.get("reports_by_role"))),
            (tr("Итоги отчётов"), _count_text(figures.get("outcomes"))),
            (tr("Неудачные попытки QA"), str(figures.get("qa_attempts_failed", 0))),
            (tr("QA с первого раза"), f"{passed} / {total}" if total else "—"),
        ]
    if section == "runtime":
        return [
            (tr("Состояния стадий"), _count_text(figures.get("stage_states"))),
            (tr("Не завершено"), str(figures.get("unfinished", 0))),
            (tr("Старейшая не завершённая"), _seconds(figures.get("oldest_unfinished_seconds"), language)),
            (tr("Без движения"), str(figures.get("stale", 0))),
        ]
    return [
        (tr("Ждут подтверждения"), str(figures.get("awaiting", 0))),
        (
            tr("Ожидание p50 / p95"),
            f"{_seconds(figures.get('approval_p50_seconds'), language)} / {_seconds(figures.get('approval_p95_seconds'), language)}",
        ),
        (tr("Старейшее ожидание"), _seconds(figures.get("approval_oldest_seconds"), language)),
        (tr("PR по состояниям"), _count_text(figures.get("pr_states"))),
    ]
