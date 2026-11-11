"""The parameter catalog of the Settings wizard: the scalar settings of project.json and
orchestration.json the console asks about, grouped like the mockup (Orchestrator, Project, QA,
Dispatch, Hooks). The type, the choices, the default, the lower bound and the description come
from the installed schema; only the Russian label and the group are the console's. The wizard
writes nothing itself: its answers become a configuration draft of the confirmed write path."""

from __future__ import annotations

from pathlib import Path

from ...configuration_schema import load_schema
from ...json_types import JsonObject

# (group id, Russian group label), in the mockup order.
GROUPS: tuple[tuple[str, str], ...] = (
    ("orchestrator", "Оркестратор"),
    ("project", "Проект"),
    ("qa", "QA"),
    ("dispatch", "Dispatch"),
    ("hooks", "Хуки"),
)

# (group, file, path, Russian label).
_PARAMETERS: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    ("orchestrator", "orchestration.json", ("approval_policy",), "Политика согласования"),
    ("orchestrator", "orchestration.json", ("human_approval_gate",), "Проверка согласования человеком"),
    ("orchestrator", "orchestration.json", ("concurrency_budget",), "Одновременных batch"),
    ("orchestrator", "orchestration.json", ("worker_attestation_required",), "Аттестация всех воркеров"),
    ("orchestrator", "orchestration.json", ("auto_retry_min_severity",), "Минимальная серьёзность для повтора"),
    ("orchestrator", "orchestration.json", ("retry_policy", "max_developer_retries"), "Повторов разработчика"),
    ("orchestrator", "orchestration.json", ("infrastructure_retry_policy", "enabled"), "Инфраструктурные повторы"),
    ("orchestrator", "orchestration.json", ("attention_policy", "max_infrastructure_retries"), "Инфраструктурных повторов до остановки"),
    ("project", "project.json", ("language",), "Язык отчётов"),
    ("project", "project.json", ("base_branch",), "Базовая ветка"),
    ("qa", "project.json", ("shell",), "Оболочка qa-gate"),
    ("qa", "orchestration.json", ("execution_policy", "qa_lease_seconds"), "Аренда QA lane, с"),
    ("dispatch", "orchestration.json", ("execution_policy", "dispatch_wait_timeout_seconds"), "Ожидание dispatch, с"),
    ("dispatch", "orchestration.json", ("execution_policy", "dispatch_poll_interval_seconds"), "Интервал опроса dispatch, с"),
    ("dispatch", "orchestration.json", ("attention_policy", "stale_dispatch_seconds"), "Молчание воркера до зависания, с"),
    ("dispatch", "orchestration.json", ("attention_policy", "heartbeat_interval_seconds"), "Интервал heartbeat, с"),
    ("hooks", "project.json", ("branch_pattern",), "Шаблон имени ветки"),
)


def _node(schema: JsonObject, path: tuple[str, ...]) -> JsonObject | None:
    node: object = schema
    for key in path:
        properties = node.get("properties") if isinstance(node, dict) else None
        if not isinstance(properties, dict) or not isinstance(properties.get(key), dict):
            return None
        node = properties[key]
    return node if isinstance(node, dict) else None


def wizard_parameters(repo: Path) -> list[dict[str, object]]:
    """The wizard parameters the installed schemas define, in the mockup group order; a schema
    that cannot be read contributes none, and a path it lacks is left out."""
    schemas: dict[str, JsonObject | None] = {}
    found: list[dict[str, object]] = []
    for group, file, path, label in _PARAMETERS:
        if file not in schemas:
            try:
                schemas[file] = load_schema(repo, file)
            except (OSError, ValueError):
                schemas[file] = None
        schema = schemas[file]
        node = None if schema is None else _node(schema, path)
        if node is None:
            continue
        choices = node.get("enum")
        found.append(
            {
                "group": group,
                "file": file,
                "path": list(path),
                "label": label,
                "type": "enum" if isinstance(choices, list) else node.get("type"),
                "choices": list(choices) if isinstance(choices, list) else [],
                "default": node.get("default"),
                "minimum": node.get("minimum"),
                "description": node.get("description", ""),
            }
        )
    return found
