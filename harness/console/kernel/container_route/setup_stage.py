"""The Setup stage: the authored configuration and the effective plan the core reports."""

from __future__ import annotations


from ..coordinator_api import ApiResult
from ..json_fields import items as _items
from ..json_fields import mapping as _obj
from .model import (
    NEED_BATCH,
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
    env_names,
)
from .config import Authored
from .preflight_stage import _packet


def _component_rows(group: str, component: object) -> list[Row]:
    data = _obj(component)
    rows: list[Row] = []
    if "mode" in data:
        rows.append(Row("Режим", _text(data["mode"]), None, group))
    container = _obj(data.get("container"))
    if container:
        rows.append(
            Row(
                "Движок",
                _text(container.get("engine"), "docker (по умолчанию)"),
                None,
                group,
            )
        )
        rows.append(
            Row("Образ worker", _text(container.get("worker_image"), "—"), None, group)
        )
        rows.append(
            Row(
                "Образ proxy",
                _text(container.get("proxy_image"), "не задан"),
                None,
                group,
            )
        )
    if "environment" in data:
        names = env_names(data["environment"])
        rows.append(
            Row("Переменные окружения (имена)", ", ".join(names) or "нет", None, group)
        )
    hosts = [str(item) for item in _items(_obj(data.get("network")).get("hosts"))]
    if "network" in data:
        rows.append(Row("Сетевые хосты", ", ".join(hosts) or "нет", None, group))
    return rows


def authored_rows(authored: Authored) -> list[Row]:
    if authored.document is None:
        return [Row("Авторская конфигурация", authored.problem, State.FAILED)]
    extension = _text(
        _obj(authored.document.get("extensions")).get("runtime_access"), "none"
    )
    rows = [
        Row(
            "extensions.runtime_access",
            extension,
            State.OK if extension == "docker" else State.WARN,
        )
    ]
    if extension != "docker":
        rows.append(
            Row(
                "Контейнерный исполнитель",
                "не включён: worker не будет запущен в контейнере",
                State.WARN,
            )
        )
    policy = _obj(authored.document.get("access_policy"))
    if not policy:
        rows.append(Row("access_policy", "не задана", State.INFO))
    rows.extend(_component_rows("access_policy.defaults", policy.get("defaults")))
    for section in ("roles", "operations"):
        for name, component in sorted(_obj(policy.get(section)).items()):
            rows.extend(_component_rows(f"access_policy.{section}.{name}", component))
    return rows


def _plan_rows(plan: JsonObject) -> list[Row]:
    group = "Эффективный план"
    container = _obj(plan.get("container"))
    rows = [
        Row("Режим", _text(plan.get("mode"), "—"), None, group),
        Row("Движок", _text(container.get("engine"), "—"), None, group),
        Row("Образ worker", _text(container.get("worker_image"), "—"), None, group),
        Row(
            "Образ proxy", _text(container.get("proxy_image"), "не задан"), None, group
        ),
        Row(
            "Переменные окружения (имена)",
            ", ".join(env_names(plan.get("environment"))) or "нет",
            None,
            group,
        ),
        Row(
            "Сетевые хосты",
            ", ".join(
                str(item) for item in _items(_obj(plan.get("network")).get("hosts"))
            )
            or "нет",
            None,
            group,
        ),
        Row("plan_digest", _text(plan.get("plan_digest"), "—"), None, group),
    ]
    sources = _obj(plan.get("sources"))
    for key, source in sorted(sources.items()):
        text = _text(source)
        rows.append(Row("Источник", f"{key}: {text}", None, group))
        if text.startswith(("roles.", "operations.")):
            rows.append(
                Row(
                    "Переопределение заменяет слой целиком",
                    f"{key}: {text}",
                    State.WARN,
                    group,
                )
            )
    return rows


def setup_view(
    authored: Authored, preflight: ApiResult | None, selection: Selection
) -> StageView:
    rows = authored_rows(authored)
    plan, _ = _packet(preflight)
    if preflight is None:
        rows.append(
            Row(
                "Эффективный план",
                "не проверено: выберите batch и роль и выполните Preflight"
                if not selection.batch
                else "не проверено: выполните Preflight",
                State.NOT_CHECKED,
            )
        )
    elif not preflight.ok:
        rows.append(_call_failure("Эффективный план", preflight))
    elif plan:
        rows.extend(_plan_rows(plan))
    else:
        rows.append(Row("Эффективный план", "не сообщается", State.NOT_REPORTED))
    can_refresh = bool(selection.batch and selection.role)
    actions = (
        Action("edit-config", "Изменить в мастере настройки"),
        Action(
            "recheck",
            "Обновить эффективный план",
            can_refresh,
            "" if can_refresh else NEED_BATCH,
            Effect.OBSERVE,
        ),
    )
    notes = (
        "Запись идёт только через мастер настройки: черновик, проверка, diff, подтверждение, "
        "резервная копия. Сохранение не запускает worker.",
    )
    return StageView(Stage.SETUP, tuple(rows), actions, notes=notes)
