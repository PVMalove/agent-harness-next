"""The Cleanup stage: a previewed `harness cleanup` plan and the apply bound to its digest."""

from __future__ import annotations

from dataclasses import dataclass

from ..coordinator_api import ApiResult
from ..json_fields import items_or_empty
from ..json_fields import mapping_or_empty
from .model import (
    Action,
    Effect,
    JsonObject,
    Row,
    Selection,
    Stage,
    StageView,
    State,
    _call_failure,
    _text,
)
from .worker_stage import worker_entry


CONTAINER_KINDS = frozenset({"container", "network"})
LIVE_EXECUTION_STATES = frozenset({"launching", "running", "stopping", "unknown"})


@dataclass
class CleanupState:
    """One previewed plan, the digest an apply is bound to, and the last apply's answer."""

    preview: ApiResult | None = None
    plan: JsonObject | None = None
    digest: str = ""
    stale: str = ""  # why the digest can no longer be applied
    apply: ApiResult | None = None


def plan_digest_of(plan: JsonObject) -> str:
    """The digest `harness cleanup --plan-digest` binds an apply to: the core's own function over
    the whole previewed plan, never a console rule."""
    from harness.cleanup import plan_digest

    return plan_digest(plan)  # type: ignore[arg-type]


def _item_dispatch(item: JsonObject) -> str:
    return _text(item.get("dispatch"))


def _is_container_skip(entry: JsonObject) -> bool:
    path = _text(entry.get("path"))
    return path.startswith("harness-") or path == "container resources"


def cleanup_view(
    state: CleanupState, selection: Selection, worker: ApiResult | None
) -> StageView:
    mine = {value for value in (selection.dispatch, selection.qa_dispatch) if value}
    rows: list[Row] = []
    blockers: list[str] = []
    notes = (
        "Живой worker не останавливается: harness его не останавливает, а остановка требует "
        "отдельной явной авторизации вне Cleanup. Чужие ресурсы не удаляются.",
        "Превью строится ядром по меткам этого репозитория для всего репозитория, а не для "
        "одного dispatch; apply удаляет весь показанный план.",
    )
    entry = worker_entry(worker, selection.dispatch) if selection.dispatch else None
    exit_ = mapping_or_empty(
        mapping_or_empty(mapping_or_empty(entry).get("execution")).get("exit")
    )
    live = (
        _text(mapping_or_empty(mapping_or_empty(entry).get("execution")).get("state"))
        in LIVE_EXECUTION_STATES
    )
    evidence = _text(exit_.get("logs"))
    rows.append(
        Row(
            "Сохранённые доказательства (execution.exit)",
            f"код выхода: {_text(exit_.get('exit_code'), 'не сообщается')}\n{evidence}"
            if exit_
            else "не сообщается: обновите Worker, чтобы получить execution.exit",
            State.INFO if exit_ else State.NOT_REPORTED,
            "Доказательства",
        )
    )
    if live:
        rows.append(
            Row(
                "Worker текущего dispatch",
                "жив или неизвестен по runtime: он не будет остановлен и не будет удалён",
                State.WARN,
                "Доказательства",
            )
        )
    plan = state.plan
    removable = 0
    if state.preview is None:
        rows.append(Row("Превью", "не запрошено: выполните превью", State.NOT_CHECKED))
    elif not state.preview.ok:
        rows.append(_call_failure("Превью", state.preview))
        blockers.append(state.preview.problem_text or state.preview.outcome.value)
    elif plan is None:
        rows.append(
            Row("Превью", "не сообщается: ядро не вернуло план", State.NOT_REPORTED)
        )
    else:
        items = [mapping_or_empty(item) for item in items_or_empty(plan.get("remove"))]
        containers = [
            item for item in items if _text(item.get("kind")) in CONTAINER_KINDS
        ]
        others = [
            item for item in items if _text(item.get("kind")) not in CONTAINER_KINDS
        ]
        removable = len(items)
        group = "План (весь репозиторий)"
        rows.append(Row("Режим", _text(plan.get("mode"), "—"), None, group))
        rows.append(
            Row(
                "К удалению",
                f"{len(items)}: контейнеры и сети {len(containers)}, прочее {len(others)}",
                State.INFO,
                group,
            )
        )
        for item in containers:
            owned = _item_dispatch(item) in mine
            rows.append(
                Row(
                    "Контейнер" if _text(item.get("kind")) == "container" else "Сеть",
                    f"{_text(item.get('path'))}\n{_text(item.get('engine'))} {_text(item.get('engine_id'))}\n"
                    f"dispatch {_item_dispatch(item) or '—'}"
                    + ("; текущий dispatch" if owned else ""),
                    State.INFO,
                    group,
                )
            )
        kinds: dict[str, int] = {}
        for item in others:
            kind = _text(item.get("kind"), "—")
            kinds[kind] = kinds.get(kind, 0) + 1
        if others:
            rows.append(
                Row(
                    "Не контейнерные пункты того же плана",
                    f"{len(others)}: "
                    + ", ".join(
                        f"{kind} {count}" for kind, count in sorted(kinds.items())
                    ),
                    State.WARN,
                    group,
                )
            )
        skipped = [
            mapping_or_empty(item) for item in items_or_empty(plan.get("skipped"))
        ]
        protected = [item for item in skipped if _is_container_skip(item)]
        for item in protected:
            rows.append(
                Row(
                    "Защищён",
                    f"{_text(item.get('path'))}\n{_text(item.get('reason'), 'причина не сообщается')}",
                    State.WARN,
                    "Защищённые ресурсы",
                )
            )
        if len(skipped) > len(protected):
            rows.append(
                Row(
                    "Прочие пропущенные пункты",
                    str(len(skipped) - len(protected)),
                    None,
                    "Защищённые ресурсы",
                )
            )
        if state.digest:
            rows.append(Row("plan-digest", state.digest, State.INFO, "Привязка"))
        if state.stale:
            rows.append(
                Row("Превью", f"устарело: {state.stale}", State.WARN, "Привязка")
            )
    if state.apply is not None:
        group = "Результат применения"
        if state.apply.documents:
            result = mapping_or_empty(state.apply.section("result"))
            removed = [str(item) for item in items_or_empty(result.get("removed"))]
            failed = [
                mapping_or_empty(item) for item in items_or_empty(result.get("failed"))
            ]
            rows.append(
                Row(
                    "Удалено",
                    f"{len(removed)}\n" + "\n".join(removed),
                    State.OK if removed else State.INFO,
                    group,
                )
            )
            for item in failed:
                rows.append(
                    Row(
                        "Не удалось",
                        f"{_text(item.get('path'))}\n{_text(item.get('reason'))}",
                        State.FAILED,
                        group,
                    )
                )
        if not state.apply.ok:
            if not state.apply.documents:
                rows.append(_call_failure("Применение", state.apply))
            blockers.append(state.apply.problem_text or state.apply.outcome.value)
    protects_evidence = (
        bool(selection.dispatch)
        and bool(plan)
        and any(
            _item_dispatch(mapping_or_empty(item)) == selection.dispatch
            for item in items_or_empty(mapping_or_empty(plan).get("remove"))
        )
    )
    if not state.digest:
        apply_reason = "сначала выполните превью"
    elif state.stale:
        apply_reason = "превью устарело: выполните его заново"
    elif removable == 0:
        apply_reason = "в плане нечего удалять"
    elif protects_evidence and not exit_:
        apply_reason = "доказательства worker не сохранены: обновите Worker до удаления его ресурсов"
    else:
        apply_reason = ""
    can_apply = not apply_reason
    actions = (
        Action("cleanup-preview", "Превью очистки", True, "", Effect.OBSERVE),
        Action(
            "cleanup-apply",
            "Применить показанный план",
            can_apply,
            apply_reason,
            Effect.DELETE,
        ),
    )
    return StageView(Stage.CLEANUP, tuple(rows), actions, tuple(blockers), notes)
