"""Проверка `hooks.policy`: профиль hooks, наличие, исполняемость, проводка и дрейф hooks проекта."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from harness.json_types import JsonObject

from ..context import HealthContext
from ..hook_settings import (
    ADAPTERS,
    HOOK_CATALOG,
    HookSpec,
    RuntimeAdapter,
    canonical_integration_id,
    critical_wiring,
    is_wired,
    merge_hooks,
    supported_tools,
    template_digests,
)
from ..model import CheckResult, Fix, Status
from ..process import run_tool
from ..test_author import ADAPTERS as AUTHOR_ADAPTERS
from ..test_author import AuthorUnavailable, adapter_for, read_author, preflight_reason
from ..project_files import (
    BACKEND_ORCHESTRATION_CAPABILITY,
    HOOK_POLICY_REL,
    HOOK_PROFILES,
    INTEGRATIONS_REL,
    JSON_READ_ERRORS,
    canonical_capability,
    hook_policy_problems,
)

GROUP = "hooks"
CHECK_ID = "hooks.policy"
HOOK_CAPABILITIES = ("engineering-suite", BACKEND_ORCHESTRATION_CAPABILITY)
HOOKS_DIR = ".claude/hooks"
TEST_AUTHOR_AGENT = ".claude/agents/test-author.md"
DEFAULT_SOURCE = "по умолчанию"
PROJECT_JSON_SOURCE = ".harness/project.json"


def check_test_author(context: HealthContext) -> CheckResult:
    """Resolve the planned executor and probe its protected adapter without starting its runtime.

    The preflight's isolation probe creates and removes a disposable sandbox. Trust is checked
    before executing any project script, independently of the script's own trust check.
    """
    reason, status, selection = _test_author_readiness(context)
    executor = (
        f"runtime={selection['runtime']}, model={selection['model']}, "
        f"effort={selection['effort']}, источник={selection['source']}"
        if selection
        else "исполнитель не выбран"
    )
    hint = (
        f" (поддержан runtime: {', '.join(sorted(AUTHOR_ADAPTERS))}; добавьте его с model и "
        "effort в assignment_plans.developer.runtimes файла .harness/orchestration.json и, "
        "если runtime несколько, выберите в assignment_plans.developer.default_runtime; "
        "без плана developer — test_author.runtime в .harness/project.json)"
        if reason == "runtime_unsupported"
        else ""
    )
    return CheckResult(
        id="hooks.test_author",
        group=GROUP,
        status=status,
        message=(
            f"Тест-автор {executor} — preflight: {reason} (основной checkout){hint}; "
            "/implement: external в доверенном worker checkout, "
            "in-process developer в worker worktree — обычный TDD (штатно); "
            "/fast-implement: текущий checkout; "
            "live-срабатывание hook проверяет make test-author-probe. "
            "Неподдерживаемый защищённый адаптер даёт runtime_unsupported; Rust этим решением не поддержан"
        ),
    )


def _test_author_readiness(
    context: HealthContext,
) -> tuple[str, Status, dict[str, object] | None]:
    repo = context.repo.resolve()
    if context.lock is None:
        return context.no_lock_message(), "skipped", None
    try:
        config = json.loads((repo / PROJECT_JSON_SOURCE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "test_paths_missing", "skipped", None
    except JSON_READ_ERRORS:
        return "config_invalid", "warn", None
    if not isinstance(config, dict):
        return "config_invalid", "warn", None
    for field in ("test_paths", "test_runner"):
        if field not in config:
            return f"{field}_missing", "skipped", None
    try:
        selection = read_author(repo, planned=True)
    except AuthorUnavailable as exc:
        return (
            exc.reason,
            "skipped" if exc.reason == "test_author_missing" else "warn",
            None,
        )
    try:
        preflight = adapter_for(selection)
    except AuthorUnavailable as exc:
        return exc.reason, "warn", selection
    # A readiness check targets this checkout, even when health is called from another runtime.
    # Setting its identity is not granting trust: the exact path must already be accepted.
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    state = (
        Path(config_dir).expanduser() / ".claude.json"
        if config_dir
        else Path.home() / ".claude.json"
    )
    try:
        document = json.loads(state.read_text(encoding="utf-8"))
        projects = document.get("projects") if isinstance(document, dict) else None
        entry = projects.get(str(repo)) if isinstance(projects, dict) else None
    except JSON_READ_ERRORS:
        entry = None
    if not isinstance(entry, dict) or entry.get("hasTrustDialogAccepted") is not True:
        return "project_untrusted", "warn", selection
    if shutil.which(str(selection["runtime"])) is None:
        return "runtime_unavailable", "warn", selection
    script = repo / preflight
    bash = shutil.which("bash")
    if bash is None or not script.is_file() or script.is_symlink():
        return "preflight_unavailable", "warn", selection
    result = run_tool(
        [bash, str(script), "--worktree", str(repo), "--planned"],
        cwd=repo,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo)},
        timeout=135,
    )
    if result is None:
        return "preflight_unavailable", "warn", selection
    reason = preflight_reason(result)
    return reason, "ok" if reason == "ok" else "warn", selection


def recorded_managed_entries(repo: Path, identifier: str) -> list[str] | None:
    """Отпечатки managed hook-записей из .harness/integrations.json; None — поля нет или файл не читается."""
    try:
        data = json.loads((repo / INTEGRATIONS_REL).read_text(encoding="utf-8"))
    except JSON_READ_ERRORS:
        return None
    entries = data.get("integrations") if isinstance(data, dict) else None
    for entry in entries if isinstance(entries, list) else []:
        if (
            isinstance(entry, dict)
            and canonical_integration_id(entry.get("id")) == identifier
        ):
            recorded = entry.get("managed_entries")
            if isinstance(recorded, list) and all(
                isinstance(item, str) for item in recorded
            ):
                return recorded
    return None


def _result(
    context: HealthContext,
    fails: list[str],
    warns: list[str],
    advisory: list[str],
    notes: list[str],
) -> CheckResult:
    """Собрать результат: fail важнее warn, warn важнее ok; части сообщения разделены `; `.

    `advisory` — предупреждения, которые `harness update` не исправляет (у runtime нет события):
    они дают статус warn, но не подсказку исправления. Первая заметка — профиль. Символ без
    UTF-8 формы (одиночный суррогат из project.json) попадает в сообщение как escape `\\udXXX`,
    чтобы вывод отчёта не падал."""
    status: Status = "fail" if fails else "warn" if warns or advisory else "ok"
    fix = None
    if fails or warns:
        fix = Fix(
            text="верните managed hooks: harness update восстановит недостающие файлы и записи; "
            "изменённый файл после просмотра заменяет --force-seed-file <путь>",
            command=context.harness_command("update", str(context.repo)),
        )
    return CheckResult(
        id=CHECK_ID,
        group=GROUP,
        status=status,
        message="; ".join([notes[0], *fails, *warns, *advisory, *notes[1:]])
        .encode("utf-8", "backslashreplace")
        .decode("utf-8"),
        fix=fix,
    )


def _profile_part(repo: Path) -> tuple[str, str | None]:
    """(описание профиля, причина fail). Профиль читают только из hook_policy в project.json."""
    path = repo / ".harness/project.json"
    if not path.is_file():
        return f"профиль standard ({DEFAULT_SOURCE})", None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except JSON_READ_ERRORS:
        data = None
    if not isinstance(data, dict):
        return "профиль не определён", (
            "project.json не читается или не объект: hooks применяют strict"
        )
    if "hook_policy" not in data:
        return f"профиль standard ({DEFAULT_SOURCE})", None
    policy = data["hook_policy"]
    problems = hook_policy_problems(policy)
    if problems:
        return "профиль не определён", (
            f"hook_policy некорректен ({'; '.join(problems)}): hooks применяют strict"
        )
    base = str(policy["profile"])
    escalations = policy.get("escalations", [])
    effective = max(
        [base, *(str(item["profile"]) for item in escalations)],
        key=HOOK_PROFILES.index,
    )
    source = PROJECT_JSON_SOURCE
    if effective != base:
        source += f"; базовый {base}"
    text = f"профиль {effective} ({source})"
    if escalations:
        text += "; эскалации: " + " | ".join(
            _escalation_text(item) for item in escalations
        )
    return text, None


def _escalation_text(item: JsonObject) -> str:
    """`<профиль>: roles=...; paths=...` — только заданные поля эскалации."""
    parts = [
        f"{key}={','.join(item[key])}" for key in ("roles", "paths") if key in item
    ]
    return f"{item['profile']}: {'; '.join(parts)}"


def _script_problem(repo: Path, spec: HookSpec) -> str | None:
    """Причина, по которой скрипт hook-а непригоден: нет файла или нет бита исполнения."""
    relative = f"{HOOKS_DIR}/{spec.script}"
    path = repo / relative
    if not path.is_file():
        return f"{relative}: файл отсутствует"
    if os.name != "nt" and not os.access(path, os.X_OK):
        return f"{relative}: нет бита исполнения"
    return None


def _agent_wiring_problem(repo: Path, spec: HookSpec) -> str | None:
    """Подключён ли hook во frontmatter установленного агента; None — подключён или агента нет."""
    agent = repo / TEST_AUTHOR_AGENT
    if not agent.is_file():
        return None
    try:
        text = agent.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return f"{TEST_AUTHOR_AGENT} не читается"
    frontmatter = text.split("---", 2)[1] if text.startswith("---") else ""
    if spec.script not in frontmatter:
        return (
            f"не подключён критический hook {spec.hook_id} (агент {TEST_AUTHOR_AGENT})"
        )
    return None


def _lacking(adapter: RuntimeAdapter) -> tuple[list[str], list[str]]:
    """(без проверки вне hook, остальные): hooks, чьих событий или payload у runtime нет."""
    unprotected: list[str] = []
    others: list[str] = []
    for spec in HOOK_CATALOG:
        if spec.wiring == "agent":
            continue  # subagent test-author есть только у первого runtime: не применимо
        delivered = supported_tools(spec, adapter.support)
        missing = tuple(tool for tool in spec.tools if tool not in delivered)
        if not missing:
            continue
        detail = [] if not delivered else [", ".join(missing)]
        if spec.out_of_hook is not None:
            detail.append(f"вне hook: {spec.out_of_hook}")
        elif spec.critical:
            detail.append("нет проверки вне hook")
        text = spec.hook_id + (f" ({'; '.join(detail)})" if detail else "")
        if spec.critical and spec.out_of_hook is None:
            unprotected.append(text)
        else:
            others.append(text)
    return unprotected, others


def _runtime_parts(
    context: HealthContext,
    adapter: RuntimeAdapter,
    fails: list[str],
    warns: list[str],
    advisory: list[str],
    notes: list[str],
) -> None:
    """Проводка, нехватка событий и дрейф файла hooks одного runtime."""
    repo = context.repo
    path = repo / adapter.config
    if not path.is_file():
        if adapter.runtime == "claude":
            fails.append(
                f"{adapter.config} отсутствует: критические hooks не подключены"
            )
        else:
            warns.append(
                f"{adapter.config} отсутствует: критические hooks runtime {adapter.runtime} "
                "не подключены, защиту дают только проверки Rust runtime и coordinator"
            )
        return
    try:
        document: object = json.loads(path.read_text(encoding="utf-8"))
    except JSON_READ_ERRORS:
        document = None
    if not isinstance(document, dict):
        fails.append(f"{adapter.config} не читается как JSON-объект")
        return

    wired, total, missing = critical_wiring(document, adapter.support)
    notes.append(f"{adapter.runtime}: критических hooks подключено {wired}/{total}")
    for spec in HOOK_CATALOG:
        if spec.wiring == "agent":
            if adapter.runtime == "claude" and (
                problem := _agent_wiring_problem(repo, spec)
            ):
                fails.append(problem)
            continue
        tools = supported_tools(spec, adapter.support)
        if not tools or all(is_wired(document, spec, tool) for tool in tools):
            continue
        if spec.critical:
            fails.append(
                f"не подключён критический hook {spec.hook_id} ({adapter.runtime})"
            )
        elif (
            text := f"не подключён hook {spec.hook_id} ({adapter.runtime})"
        ) not in warns:
            warns.append(text)  # hook нескольких событий называется один раз

    unprotected, others = _lacking(adapter)
    lacking = [*unprotected, *others]
    if lacking:
        notes.append(
            f"{adapter.runtime}: нет события или payload: {', '.join(lacking)}"
        )
    if unprotected:
        advisory.append(
            f"ограничение адаптера {adapter.runtime}: критический hook без события "
            "и без проверки вне hook: "
            + ", ".join(item.split(" (")[0] for item in unprotected)
        )
    if context.hook_templates is None:
        return
    template = context.hook_templates.get(adapter.config)
    if template is None:
        return
    template_document = json.loads(template.decode("utf-8"))
    baseline = set(template_digests(template_document)) | set(
        recorded_managed_entries(repo, adapter.integration_id) or []
    )
    merge = merge_hooks(document, template_document, baseline)
    if merge.conflicts:
        warns.append(
            f"дрейф: конфликтов managed hooks {len(merge.conflicts)} ({adapter.runtime})"
        )
    if merge.added or merge.replaced:
        warns.append(
            "дрейф: managed hooks отличаются от шаблона: "
            f"добавить {merge.added}, заменить {merge.replaced} ({adapter.runtime})"
        )


def _script_drift(context: HealthContext, warns: list[str]) -> None:
    """Скрипты `.claude/hooks/` проекта, отличающиеся от шаблона."""
    for relative, expected in sorted((context.hook_templates or {}).items()):
        if not relative.startswith(HOOKS_DIR + "/"):
            continue
        path = context.repo / relative
        if path.is_file() and path.read_bytes() != expected:
            warns.append(
                f"дрейф: {relative} отличается от шаблона (после просмотра: "
                f"--force-seed-file {relative})"
            )


def _policy_file(
    context: HealthContext, policy_reported: bool, fails: list[str], warns: list[str]
) -> None:
    """Сгенерированный `.harness/hook-policy.json`: отказ резолвера, отсутствие и дрейф.

    Health только сообщает, файл пишет установка (`harness init|adopt|update`). При шаблонах hooks
    политику считает тот же резолвер, что и установка; его `PolicyError` даёт fail с текстом
    ошибки, если `_profile_part` не сообщил о hook_policy сам (`policy_reported` ложно: так
    проходит, например, путь эскалации без UTF-8 формы), и сверка тогда пропускается. Содержимое
    сверяется по разобранному JSON (CRLF после клона — не дрейф)."""
    path = context.repo / HOOK_POLICY_REL
    relative = HOOK_POLICY_REL.as_posix()
    expected: dict[str, object] | None = None
    if context.hook_templates is not None:
        from harness.errors import PolicyError
        from harness.orchestration.hook_policy import effective_policy, load_policy

        try:
            expected = effective_policy(
                load_policy(context.repo), context.hook_templates
            )
        except PolicyError as exc:
            if not policy_reported:
                fails.append(
                    f"резолвер политики отклоняет hook_policy ({exc.message}): "
                    "harness init|adopt|update и dispatch create отказывают"
                )
    if not path.is_file():
        warns.append(f"{relative} отсутствует: effective policy hooks не записана")
        return
    if expected is None:
        return
    try:
        actual: object = json.loads(path.read_text(encoding="utf-8"))
    except JSON_READ_ERRORS:
        actual = None
    if actual != expected:
        warns.append(
            f"дрейф: {relative} не совпадает с effective policy текущей конфигурации"
        )


def check_policy(context: HealthContext) -> CheckResult:
    """Профиль hooks и его источник, эскалации, скрипты, проводка по runtime, нехватка событий и дрейф."""
    if context.lock is None:
        return CheckResult(
            id=CHECK_ID,
            group=GROUP,
            status="skipped",
            message=context.no_lock_message(),
        )
    if not {
        canonical_capability(name) for name in context.lock.get("capabilities") or []
    } & set(HOOK_CAPABILITIES):
        return CheckResult(
            id=CHECK_ID,
            group=GROUP,
            status="skipped",
            message="hooks проекта не ставились (нет engineering-suite и backend-orchestration)",
        )
    fails: list[str] = []
    warns: list[str] = []
    advisory: list[str] = []
    notes: list[str] = []

    profile, problem = _profile_part(context.repo)
    if problem:
        fails.append(problem)
    notes.append(profile)

    checked: set[str] = set()
    for spec in HOOK_CATALOG:
        if spec.wiring == "agent" and not (context.repo / TEST_AUTHOR_AGENT).is_file():
            continue
        if spec.script in checked:
            continue  # один скрипт на нескольких событиях проверяется один раз
        checked.add(spec.script)
        script_problem = _script_problem(context.repo, spec)
        if script_problem is None:
            continue
        (fails if spec.critical else warns).append(script_problem)

    for adapter in ADAPTERS:
        _runtime_parts(context, adapter, fails, warns, advisory, notes)

    if context.hook_templates is None:
        notes.append("дрейф не проверен (нет шаблонов проекта)")
    else:
        _script_drift(context, warns)
    _policy_file(context, problem is not None, fails, warns)
    return _result(context, fails, warns, advisory, notes)
