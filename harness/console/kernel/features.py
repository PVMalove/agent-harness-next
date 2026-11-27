"""The Harness features of the Diagnostics screen: a read-only registry built from the package
capability catalog, the installed hooks (`.claude/hooks`) and agents (`.claude/agents`), the
runtime hook settings and the keys of `.harness/project.json` and `.harness/orchestration.json`.

Every feature has a category, a state (`working`, `partial`, `not_working`, `disabled`), the
features it depends on and is required by, its sources, its requirements and its settings rows.
Three features have a boolean configuration key that switches them; the console toggles them only
through the confirmed `configuration-apply` job, never here. For each of them the registry also
forecasts the state and requirements after the switch by evaluating the feature again with the
key flipped, so the page never re-implements the state rule. Collecting reads files and asks
`shutil.which`; it never writes, never runs a subprocess and never touches the network. Names,
descriptions, off effects and requirement titles are Russian source strings; `detail` holds paths
and values only."""

from __future__ import annotations

import copy
import json
import shutil
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from harness.configuration import mask_secrets, parse_object, read_config_bundle
from harness.configuration_schema import PACKAGE
from harness.health.hook_settings import ADAPTERS, HOOK_CATALOG, HookSpec, is_wired, supported_tools

from .configuration_snapshot import _pending, config_digest
from .harness_facts import harness_state
from .project_target import capability_options

PROJECT = "project.json"
ORCHESTRATION = "orchestration.json"
CATEGORIES = (
    "execution",
    "roles",
    "hooks",
    "context",
    "process",
    "publication",
    "capabilities",
    "platform",
)
STATES = ("working", "partial", "not_working", "disabled")
VALUE_CHARS = 120

Level = Literal["ok", "warn", "err"]
Document = Mapping[str, object]


@dataclass(frozen=True)
class Config:
    """One configuration file: its parsed document (None when missing or unreadable)."""

    name: str
    exists: bool
    document: Document | None
    error: str

    @property
    def path(self) -> str:
        return f".harness/{self.name}"


@dataclass(frozen=True)
class Facts:
    """What the registry reads once per snapshot."""

    repo: Path
    configs: dict[str, Config]
    capabilities: tuple[str, ...]
    orchestration: bool
    hook_settings: tuple[tuple[str, frozenset[tuple[str, str]] | None, Document], ...]
    which: Callable[[str], str | None]

    def value(self, file: str, path: tuple[str, ...]) -> object:
        """The raw value at `path`, or `_ABSENT`."""
        current: object = self.configs[file].document
        for key in path:
            if not isinstance(current, Mapping) or key not in current:
                return _ABSENT
            current = current[key]
        return current

    def flag(self, file: str, path: tuple[str, ...]) -> bool:
        return self.value(file, path) is True


class _Absent:
    pass


_ABSENT = _Absent()


@dataclass
class _Feature:
    id: str
    name: str
    category: str
    description: str
    off_effect: str
    enabled: bool
    depends_on: tuple[str, ...] = ()
    sources: list[tuple[str, str]] = field(default_factory=list)
    requirements: list[tuple[str, Level, str]] = field(default_factory=list)
    settings: list[tuple[str, tuple[str, ...], str | None]] = field(default_factory=list)
    toggle: tuple[str, tuple[str, ...]] | None = None


def _clip(value: object, key: str) -> str:
    text = json.dumps(mask_secrets(value, key), ensure_ascii=False, separators=(",", ":"))
    return text if len(text) <= VALUE_CHARS else text[: VALUE_CHARS - 1] + "…"


def _state(feature: _Feature) -> str:
    if not feature.enabled:
        return "disabled"
    levels = {level for _, level, _ in feature.requirements}
    if "err" in levels:
        return "not_working"
    if "warn" in levels:
        return "partial"
    return "working"


# --- requirement builders -------------------------------------------------------------------


def _config_rows(facts: Facts, feature: _Feature, *names: str) -> None:
    """An `err` requirement for each configuration file the feature reads that does not parse."""
    for name in names:
        config = facts.configs[name]
        if config.exists and config.document is None:
            feature.requirements.append(("Файл конфигурации не читается", "err", config.path))


def _setting(
    feature: _Feature, file: str, *path: str, default: str | None = None
) -> None:
    feature.settings.append((file, tuple(path), default))
    source = (file, f".harness/{file}")
    if source not in feature.sources:
        feature.sources.append(source)


def _hook_wired(facts: Facts, spec: HookSpec) -> bool:
    for _, support, document in facts.hook_settings:
        tools = supported_tools(spec, support)
        if tools and all(is_wired(dict(document), spec, tool) for tool in tools):
            return True
    return False


def _hooks(facts: Facts, feature: _Feature, *hook_ids: str) -> None:
    """One requirement per catalog hook: its script in `.claude/hooks/` and its wiring in a
    present runtime hook settings file. A missing file is `err`; an unwired hook is `err` when it
    is critical and `warn` otherwise."""
    for hook_id in hook_ids:
        spec = next(item for item in HOOK_CATALOG if item.hook_id == hook_id)
        path = f".claude/hooks/{spec.script}"
        feature.sources.append(("hook", path))
        if not (facts.repo / path).is_file():
            feature.requirements.append(("Файл хука отсутствует", "err", path))
        elif not _hook_wired(facts, spec):
            level: Level = "err" if spec.critical else "warn"
            feature.requirements.append(("Хук не подключён", level, path))
        else:
            feature.requirements.append(("Хук установлен и подключён", "ok", path))


def _agents(facts: Facts, feature: _Feature, *names: str) -> None:
    for name in names:
        path = f".claude/agents/{name}"
        feature.sources.append(("agent", path))
        if (facts.repo / path).is_file():
            feature.requirements.append(("Агент установлен", "ok", path))
        else:
            feature.requirements.append(("Файл агента отсутствует", "err", path))


def _hook_files(facts: Facts, feature: _Feature, *scripts: str) -> None:
    for script in scripts:
        path = f".claude/hooks/{script}"
        feature.sources.append(("hook", path))
        if (facts.repo / path).is_file():
            feature.requirements.append(("Файл установлен", "ok", path))
        else:
            feature.requirements.append(("Файл отсутствует", "err", path))


def _containers(facts: Facts) -> list[tuple[tuple[str, ...], Mapping[str, object]]]:
    """Every `access_policy` entry with a `container` object, with its path."""
    policy = facts.value(ORCHESTRATION, ("access_policy",))
    if not isinstance(policy, Mapping):
        return []
    found: list[tuple[tuple[str, ...], Mapping[str, object]]] = []
    defaults = policy.get("defaults")
    if isinstance(defaults, Mapping) and isinstance(defaults.get("container"), Mapping):
        found.append((("access_policy", "defaults", "container"), defaults["container"]))
    for group in ("roles", "operations"):
        entries = policy.get(group)
        if not isinstance(entries, Mapping):
            continue
        for name in sorted(entries):
            entry = entries[name]
            if isinstance(entry, Mapping) and isinstance(entry.get("container"), Mapping):
                found.append((("access_policy", group, name, "container"), entry["container"]))
    return found


# --- the static features ---------------------------------------------------------------------


def _execution(facts: Facts) -> list[_Feature]:
    orchestration_config = facts.configs[ORCHESTRATION]
    orchestration = _Feature(
        "orchestration",
        "Оркестрация",
        "execution",
        "Batch, dispatch и роли: путь задачи от плана до PR.",
        "Задачи нельзя запускать через batch и dispatch.",
        facts.orchestration,
        ("capability:backend-orchestration",),
    )
    orchestration.sources.append(("harness.lock", ".harness/orchestration/coordinator.py"))
    orchestration.sources.append(("orchestration.json", orchestration_config.path))
    if orchestration_config.document is not None:
        orchestration.requirements.append(
            ("Файл конфигурации на месте", "ok", orchestration_config.path)
        )
    elif orchestration_config.exists:
        orchestration.requirements.append(
            ("Файл конфигурации не читается", "err", orchestration_config.path)
        )
    else:
        orchestration.requirements.append(
            ("Файл конфигурации отсутствует", "err", orchestration_config.path)
        )

    found = _containers(facts)
    containers = _Feature(
        "containers",
        "Контейнерный executor",
        "execution",
        "Worker запускается в изолированном контейнере (Docker или Podman), а не на хосте.",
        "Worker будут запускаться на хосте без изоляции.",
        bool(found),
        ("orchestration",),
    )
    _config_rows(facts, containers, ORCHESTRATION)
    if not found:
        _setting(containers, ORCHESTRATION, "access_policy", "defaults", "container")
    engines: list[str] = []
    for path, container in found:
        for key in ("engine", "worker_image", "proxy_image"):
            _setting(
                containers,
                ORCHESTRATION,
                *path,
                key,
                default="docker (по умолчанию)" if key == "engine" else None,
            )
        engine = container.get("engine", "docker")
        if isinstance(engine, str) and engine not in engines:
            engines.append(engine)
    for engine in engines:
        if facts.which(engine):
            containers.requirements.append(("Движок контейнеров найден", "ok", engine))
        else:
            containers.requirements.append(
                ("Движок контейнеров не найден в PATH", "err", engine)
            )

    attestation = _Feature(
        "attestation",
        "Worker attestation",
        "execution",
        "Worker подтверждает себя через dispatch self-report и heartbeat.",
        "Состояние worker принимается без подтверждения.",
        facts.flag(ORCHESTRATION, ("worker_attestation_required",)),
        ("orchestration",),
        toggle=(ORCHESTRATION, ("worker_attestation_required",)),
    )
    _config_rows(facts, attestation, ORCHESTRATION)
    _setting(
        attestation, ORCHESTRATION, "worker_attestation_required", default="false (по умолчанию)"
    )

    worktrees = _Feature(
        "worktrees",
        "Изолированные worktree",
        "execution",
        "Каждая задача идёт в своём worktree и ветке по шаблону.",
        "Задачи будут идти в общем рабочем дереве.",
        True,
    )
    _config_rows(facts, worktrees, PROJECT)
    _setting(worktrees, PROJECT, "branch_pattern")
    _setting(worktrees, PROJECT, "base_branch")
    _hooks(facts, worktrees, "check-branch-name", "check-worktree-branch-name")
    return [orchestration, containers, attestation, worktrees]


def _roles(facts: Facts) -> list[_Feature]:
    test_author = _Feature(
        "test-author",
        "Test author",
        "roles",
        "Агент пишет один поведенческий тест для шага Red в TDD и запускает его через "
        "защищённый runner.",
        "Тесты для шага Red пишет разработчик сам.",
        facts.value(PROJECT, ("test_author",)) is not _ABSENT,
        ("qa-gate",),
    )
    _config_rows(facts, test_author, PROJECT)
    _setting(test_author, PROJECT, "test_author")
    _setting(test_author, PROJECT, "test_runner")
    _setting(test_author, PROJECT, "test_paths")
    _agents(facts, test_author, "test-author.md")
    _hook_files(
        facts, test_author, "test-author-guard.py", "test-author-preflight.sh", "run-test.sh"
    )

    code_review = _Feature(
        "code-review",
        "Code review",
        "roles",
        "Два ревьюера: по спецификации (code-review-spec) и по стандартам "
        "(code-review-standards).",
        "Ревью выполняется вручную.",
        True,
    )
    _agents(facts, code_review, "code-review-spec.md", "code-review-standards.md")

    pr_composer = _Feature(
        "pr-composer",
        "PR composer",
        "roles",
        "Заполняет тело PR по шаблону из diff, коммитов и результата qa-gate.",
        "Тело PR пишется вручную.",
        True,
        ("qa-gate",),
    )
    _agents(facts, pr_composer, "pr-composer.md")

    roles = _Feature(
        "roles",
        "Роли Architect / Developer / QA",
        "roles",
        "Профили провайдеров и назначение ролей по этапам.",
        "Роли назначаются только вручную.",
        facts.orchestration,
        ("orchestration",),
    )
    _config_rows(facts, roles, ORCHESTRATION)
    _setting(roles, ORCHESTRATION, "provider_profiles")
    _setting(roles, ORCHESTRATION, "assignment_plans")
    return [test_author, code_review, pr_composer, roles]


def _hook_features(facts: Facts) -> list[_Feature]:
    git_guard = _Feature(
        "git-guard",
        "Git-защита",
        "hooks",
        "Блокирует опасные git-команды, прямые коммиты в основную ветку, слияние PR и "
        "неверные имена веток.",
        "Опасные git-операции не блокируются.",
        True,
    )
    _hooks(
        facts,
        git_guard,
        "block-dangerous-git",
        "block-direct-master",
        "block-pr-merge",
        "check-branch-name",
    )

    attribution = _Feature(
        "attribution",
        "Публичная атрибуция",
        "hooks",
        "Отклоняет подписи ассистентов в коммитах и PR.",
        "Подписи ассистентов не проверяются.",
        True,
    )
    _hooks(facts, attribution, "block-public-attribution")

    artifacts = _Feature(
        "artifact-location",
        "Расположение артефактов",
        "hooks",
        "Черновики задач пишутся только в docs/tasks/ и .harness/.sandboxes/.",
        "Черновики можно писать в любой каталог.",
        True,
    )
    _hooks(facts, artifacts, "block-scratch-outside-docs-tasks")

    commands = facts.value(PROJECT, ("qa_gate_commands",))
    qa_gate = _Feature(
        "qa-gate",
        "QA gate",
        "hooks",
        "Полная проверка перед PR: require-qa-gate, ограниченный по времени запуск, запись "
        "результата.",
        "PR можно создать без полной проверки.",
        isinstance(commands, list) and bool(commands),
    )
    _config_rows(facts, qa_gate, PROJECT)
    _setting(qa_gate, PROJECT, "qa_gate_commands")
    _hooks(facts, qa_gate, "require-qa-gate", "require-bounded-check", "mark-qa-gate-passed")

    hook_policy = _Feature(
        "hook-policy",
        "Защита hook-policy",
        "hooks",
        "Запрещает агентам менять политику хуков и перепроверяет чувствительные пути.",
        "Политику хуков может менять любой агент.",
        True,
    )
    _config_rows(facts, hook_policy, PROJECT)
    _setting(hook_policy, PROJECT, "hook_policy", "profile", default="standard (по умолчанию)")
    _hooks(facts, hook_policy, "protect-hook-policy", "sensitive-path-recheck")
    return [git_guard, attribution, artifacts, qa_gate, hook_policy]


def _context(facts: Facts) -> list[_Feature]:
    repo_map = _Feature(
        "repo-map",
        "Repo Map",
        "context",
        "Индекс файлов, символов и связей для поиска и контекста агентов.",
        "Агенты ищут по коду без индекса.",
        True,
    )
    _config_rows(facts, repo_map, ORCHESTRATION)
    _setting(repo_map, ORCHESTRATION, "repo_map_policy")

    memory = _Feature(
        "memory",
        "Память проекта",
        "context",
        "Долговременные заметки и решения, которые подмешиваются в контекст.",
        "Контекст собирается без памяти проекта.",
        facts.flag(PROJECT, ("memory", "enabled")),
        toggle=(PROJECT, ("memory", "enabled")),
    )
    _config_rows(facts, memory, PROJECT)
    _setting(memory, PROJECT, "memory", "enabled", default="false (по умолчанию)")
    _setting(memory, PROJECT, "memory_policy", "source_types")
    _setting(memory, PROJECT, "memory_policy", "allow_paths")
    if memory.enabled:
        sources = facts.value(PROJECT, ("memory_policy", "source_types"))
        paths = facts.value(PROJECT, ("memory_policy", "allow_paths"))
        if not (isinstance(sources, list) and sources and isinstance(paths, list) and paths):
            memory.requirements.append(
                (
                    "Память включена без источников",
                    "warn",
                    "memory_policy.source_types, memory_policy.allow_paths",
                )
            )
        else:
            memory.requirements.append(
                (
                    "Источники памяти заданы",
                    "ok",
                    "memory_policy.source_types, memory_policy.allow_paths",
                )
            )

    package = _Feature(
        "context-package",
        "Пакет контекста",
        "context",
        "Что получает worker: стартовые файлы, граф символов и связанные тесты.",
        "Worker получает минимальный контекст.",
        facts.orchestration,
        ("orchestration", "repo-map"),
    )
    _config_rows(facts, package, ORCHESTRATION)
    _setting(package, ORCHESTRATION, "context_package_policy")
    return [repo_map, memory, package]


def _process(facts: Facts) -> list[_Feature]:
    approval = _Feature(
        "approval",
        "Одобрение человеком",
        "process",
        "Переходы между этапами и публикация требуют решения человека.",
        "Переходы выполняются по политике без запроса.",
        facts.orchestration,
        ("orchestration",),
    )
    _config_rows(facts, approval, ORCHESTRATION)
    _setting(approval, ORCHESTRATION, "approval_policy")
    _setting(approval, ORCHESTRATION, "human_approval_gate")
    _setting(approval, ORCHESTRATION, "approval_ttl_seconds")

    retry = _Feature(
        "retry",
        "Retry и внимание",
        "process",
        "Ограниченные повторы при сбоях инфраструктуры и сигналы «требует внимания».",
        "Сбои инфраструктуры не повторяются автоматически.",
        facts.flag(ORCHESTRATION, ("infrastructure_retry_policy", "enabled")),
        ("orchestration",),
        toggle=(ORCHESTRATION, ("infrastructure_retry_policy", "enabled")),
    )
    _config_rows(facts, retry, ORCHESTRATION)
    _setting(
        retry,
        ORCHESTRATION,
        "infrastructure_retry_policy",
        "enabled",
        default="false (по умолчанию)",
    )
    _setting(retry, ORCHESTRATION, "retry_policy")
    _setting(retry, ORCHESTRATION, "attention_policy")

    preflight = _Feature(
        "preflight",
        "Preflight и подготовка QA",
        "process",
        "Проверка окружения перед запуском роли и подготовка QA.",
        "Роли стартуют без предварительных проверок.",
        facts.orchestration,
        ("orchestration", "qa-gate"),
    )
    _config_rows(facts, preflight, ORCHESTRATION)
    _setting(preflight, ORCHESTRATION, "preflight_policy")
    _setting(preflight, ORCHESTRATION, "qa_environment_probes")
    _setting(preflight, ORCHESTRATION, "qa_project_file_checks")
    return [approval, retry, preflight]


_TRACKER_CLI = {"github": "gh", "gitlab": "glab"}


def _publication(facts: Facts) -> list[_Feature]:
    tracker = _Feature(
        "tracker",
        "Трекер задач",
        "publication",
        "Источник задач, статусы и публикация PR через CLI трекера.",
        "Задачи и PR недоступны из консоли.",
        True,
    )
    _config_rows(facts, tracker, PROJECT)
    _setting(tracker, PROJECT, "tracker", default="по remote (ADR 0011)")
    kind = facts.value(PROJECT, ("tracker", "type"))
    if kind is _ABSENT:
        tracker.requirements.append(("Трекер определяется по remote", "ok", "origin"))
    elif isinstance(kind, str) and kind in _TRACKER_CLI:
        cli = _TRACKER_CLI[kind]
        if facts.which(cli):
            tracker.requirements.append(("CLI трекера найден", "ok", cli))
        else:
            tracker.requirements.append(("CLI трекера не найден в PATH", "warn", cli))

    checks = facts.value(PROJECT, ("ci_required_checks",))
    ci = _Feature(
        "ci-checks",
        "Обязательные CI-проверки",
        "publication",
        "Проверки CI, которые должны пройти, чтобы CI заменил повтор локального QA.",
        "Вместо CI повторяется полное локальное QA.",
        isinstance(checks, list) and bool(checks),
        ("tracker",),
    )
    _config_rows(facts, ci, PROJECT)
    _setting(ci, PROJECT, "ci_required_checks")
    return [tracker, ci]


def _platform(facts: Facts) -> list[_Feature]:
    console = _Feature(
        "web-console",
        "Веб-консоль",
        "platform",
        "Эта консоль: сервер на localhost, токен сессии и WebSocket.",
        "Консоль недоступна, остаётся TUI.",
        True,
    )
    console.sources.append(("runtime", "harness console"))
    console.requirements.append(("Сервер консоли отвечает", "ok", ""))
    return [console]


def _capability_features(facts: Facts) -> list[_Feature]:
    catalog = json.loads((PACKAGE / "CAPABILITIES.json").read_text(encoding="utf-8"))
    labels = dict(capability_options())
    features: list[_Feature] = []
    for name, entry in catalog.items():
        extends = entry.get("extends") if isinstance(entry, dict) else None
        parents = [extends] if isinstance(extends, str) else list(extends or ())
        feature = _Feature(
            f"capability:{name}",
            name,
            "capabilities",
            labels.get(name, name),
            "Файлы этой capability не установлены в проект.",
            name in facts.capabilities,
            tuple(f"capability:{parent}" for parent in parents if isinstance(parent, str)),
        )
        feature.sources.append(("capabilities", "CAPABILITIES.json"))
        feature.sources.append(("harness.lock", ".harness/harness.lock"))
        if feature.enabled:
            feature.requirements.append(
                ("Записана в harness.lock", "ok", ".harness/harness.lock")
            )
        features.append(feature)
    return features


# --- collecting ------------------------------------------------------------------------------


def _read_configs(repo: Path) -> tuple[dict[str, Config], dict[str, str]]:
    try:
        bundle = read_config_bundle(repo)
    except (ValueError, OSError) as exc:
        reason = str(exc) or type(exc).__name__
        return (
            {name: Config(name, False, None, reason) for name in (PROJECT, ORCHESTRATION)},
            {PROJECT: "", ORCHESTRATION: ""},
        )
    configs: dict[str, Config] = {}
    for name in (PROJECT, ORCHESTRATION):
        raw = bundle[name]
        if raw is None:
            configs[name] = Config(name, False, None, "")
            continue
        try:
            configs[name] = Config(name, True, parse_object(raw, name), "")
        except ValueError as exc:
            configs[name] = Config(name, True, None, str(exc))
    return configs, {name: config_digest(bundle[name]) for name in (PROJECT, ORCHESTRATION)}


def _hook_settings(
    repo: Path,
) -> tuple[tuple[str, frozenset[tuple[str, str]] | None, Document], ...]:
    found: list[tuple[str, frozenset[tuple[str, str]] | None, Document]] = []
    for adapter in ADAPTERS:
        try:
            document = json.loads((repo / adapter.config).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(document, dict):
            found.append((adapter.config, adapter.support, document))
    return tuple(found)


def _all(facts: Facts) -> list[_Feature]:
    return [
        *_execution(facts),
        *_roles(facts),
        *_hook_features(facts),
        *_context(facts),
        *_process(facts),
        *_publication(facts),
        *_capability_features(facts),
        *_platform(facts),
    ]


def _settings_rows(
    facts: Facts, rows: Iterable[tuple[str, tuple[str, ...], str | None]]
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for file, path, default in rows:
        value = facts.value(file, path) if facts.configs[file].document is not None else _ABSENT
        present = value is not _ABSENT
        result.append(
            {
                "file": file,
                "path": list(path),
                "present": present,
                "value": _clip(value, path[-1]) if present else default,
            }
        )
    return result


def _requirements(feature: _Feature) -> list[dict[str, str]]:
    return [
        {"title": title, "state": level, "detail": detail}
        for title, level, detail in feature.requirements
    ]


def _toggled(facts: Facts, feature: _Feature) -> _Feature:
    """`feature` evaluated again with its boolean key flipped in the configuration it reads. A
    missing file is read as an empty document; an unreadable one stays unreadable, so the
    switched feature keeps its configuration error."""
    assert feature.toggle is not None
    file, path = feature.toggle
    value = not feature.enabled
    config = facts.configs[file]
    if config.document is not None or not config.exists:
        document: dict[str, object] = copy.deepcopy(dict(config.document or {}))
        node = document
        for key in path[:-1]:
            child = node.get(key)
            if not isinstance(child, dict):
                child = {}
                node[key] = child
            node = child
        node[path[-1]] = value
        facts = replace(facts, configs={**facts.configs, file: replace(config, document=document)})
    after = next(item for item in _all(facts) if item.id == feature.id)
    after.enabled = value
    return after


def feature_payloads(facts: Facts) -> list[dict[str, object]]:
    """Every feature as its wire object, in category order."""
    features = sorted(_all(facts), key=lambda item: CATEGORIES.index(item.category))
    required_by: dict[str, list[str]] = {item.id: [] for item in features}
    for item in features:
        for parent in item.depends_on:
            required_by[parent].append(item.id)
    payloads: list[dict[str, object]] = []
    for item in features:
        toggle = None
        if item.toggle is not None:
            file, path = item.toggle
            after = _toggled(facts, item)
            toggle = {
                "file": file,
                "path": list(path),
                "enabled": item.enabled,
                "state_after": _state(after),
                "requirements_after": _requirements(after),
            }
        payloads.append(
            {
                "id": item.id,
                "name": item.name,
                "category": item.category,
                "state": _state(item),
                "description": item.description,
                "off_effect": item.off_effect,
                "depends_on": list(item.depends_on),
                "required_by": required_by[item.id],
                "sources": [{"kind": kind, "path": path} for kind, path in item.sources],
                "requirements": _requirements(item),
                "settings": _settings_rows(facts, item.settings),
                "toggle": toggle,
            }
        )
    return payloads


def collect_features(
    repo: Path, which: Callable[[str], str | None] = shutil.which
) -> dict[str, object]:
    """The `features.snapshot` facts of `repo` without the cache fields: the features, the
    digests of the configuration files they were read from and whether a configuration write
    left a prepared transaction. Reads files only."""
    repo = repo.expanduser().resolve()
    configs, digests = _read_configs(repo)
    state = harness_state(repo)
    facts = Facts(
        repo, configs, state.capabilities, state.orchestration, _hook_settings(repo), which
    )
    return {
        "features": feature_payloads(facts),
        "config_digests": digests,
        "transaction_pending": _pending(repo),
    }
