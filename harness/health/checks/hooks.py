"""Проверка `hooks.policy`: профиль hooks, наличие, исполняемость, проводка и дрейф hooks проекта."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from harness.json_types import JsonObject

from ..context import HealthContext, shell_join
from ..hook_settings import (
    ADAPTERS,
    HOOK_CATALOG,
    HookSpec,
    RuntimeAdapter,
    canonical_integration_id,
    critical_wiring,
    envelope_hook_ids,
    is_wired,
    merge_hooks,
    script_envelope_id,
    script_name,
    supported_tools,
    template_digests,
)
from ..model import CheckResult, Fix, Status
from ..process import run_tool
from ..test_author import ADAPTERS as AUTHOR_ADAPTERS
from ..test_author import (
    PREFLIGHT_REASONS,
    AuthorUnavailable,
    adapter_for,
    preflight_reason,
    profile_problems,
    read_author,
)
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
ENVELOPE_REL = f"{HOOKS_DIR}/hook_response.py"
ENVELOPE_SOURCE_REL = f"{HOOKS_DIR}/hook-envelope.sh"
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
    line = REASON_LINES.get(reason)
    return CheckResult(
        id="hooks.test_author",
        group=GROUP,
        status=status,
        message=(
            f"Тест-автор {executor} — preflight: {reason} (этот checkout){hint}; "
            "/implement: субагент developer в его worktree — external через Agent(test-author), "
            "in-process developer — launcher своего worktree (python3 -I -B "
            "<worktree>/.harness/health/test_author.py run --repo <worktree> --brief <brief> "
            "--prompt-file <файл>); "
            "/fast-implement: текущий checkout; "
            "live-срабатывание hook проверяет make test-author-probe. "
            "Неподдерживаемый защищённый адаптер даёт runtime_unsupported; Rust этим решением не поддержан"
        ),
        fix=Fix(text=f"выполните шаг строки {line}")
        if status == "warn" and line
        else None,
    )


# Each condition of the test author is its own Health line with its own fix step (#1122).
CONFIG_ID = "hooks.test_author_config"
ROOT_ID = "hooks.test_author_root"
TRUST_ID = "hooks.test_author_trust"
GUARD_ID = "hooks.test_author_guard"
RUNNER_ID = "hooks.test_author_runner"
PROBE_ID = "hooks.test_author_probe"
GUARD_REL = f"{HOOKS_DIR}/test-author-guard.py"
RUNNER_REL = f"{HOOKS_DIR}/run-test.sh"
REASON_LINES = {
    "test_author_missing": CONFIG_ID,
    "test_author_config_invalid": CONFIG_ID,
    "project_dir_mismatch": ROOT_ID,
    "project_untrusted": f"{ROOT_ID} и {TRUST_ID}",
    "agent_missing": GUARD_ID,
    "scoped_hook_unsupported": GUARD_ID,
    "guard_hook_unavailable": GUARD_ID,
    "config_invalid": GUARD_ID,
    "write_zone_rejected": GUARD_ID,
    "runner_unavailable": RUNNER_ID,
    "isolation_unavailable": PROBE_ID,
}
CONFIG_STEP = (
    "исправьте test_paths и test_runner в .harness/project.json: ошибку показывает строка "
    "files.project_json; test_paths принимает только зоны вида <каталог>/**"
)
CONFIG_REASONS = (
    "config_invalid",
    "write_zone_rejected",
    "test_paths_missing",
    "test_runner_missing",
)
AGENT_STEP = "после просмотра верните агент: harness update --force-seed-file .claude/agents/test-author.md"
GUARD_STEPS = {
    "scoped_hook_unsupported": f"агент {TEST_AUTHOR_AGENT} изменён: {AGENT_STEP}",
    "test_author_config_invalid": f"агент {TEST_AUTHOR_AGENT} задаёт свои model или effort: "
    f"{AGENT_STEP}",
    **dict.fromkeys(CONFIG_REASONS, CONFIG_STEP),
}
ISOLATION_STEPS = {
    "platform": "runner изолирует тесты только в Linux с bubblewrap: запускайте проект в Linux "
    "или WSL2",
    "bwrap_missing": "установите bubblewrap 0.9.0+ (Debian и Ubuntu: sudo apt-get install "
    "bubblewrap)",
    "checkout_masked": "перенесите checkout из /tmp, /run, /dev или /proc: песочница подменяет "
    "эти каталоги",
    "sandbox_failed": "bwrap не поднял песочницу: проверьте bwrap --ro-bind / / true и включите "
    "непривилегированные user namespaces",
    "probe_failed": "/var/run должен быть ссылкой на /run или пустым; вывод probe — в log.txt "
    "последнего каталога .harness/.sandboxes/runs/isolated-test-*",
}


def _line(
    check_id: str, status: Status, message: str, fix: Fix | None = None
) -> CheckResult:
    return CheckResult(
        id=check_id, group=GROUP, status=status, message=message, fix=fix
    )


def _opted_in(
    context: HealthContext, check_id: str
) -> tuple[JsonObject, CheckResult | None]:
    """The project config of a project that opted in to the author, or the skipped line."""
    if context.lock is None:
        return {}, _line(check_id, "skipped", context.no_lock_message())
    try:
        config = json.loads(
            (context.repo / PROJECT_JSON_SOURCE).read_text(encoding="utf-8")
        )
    except FileNotFoundError:
        config = {}
    except JSON_READ_ERRORS:
        config = None
    if not isinstance(config, dict):
        return {}, _line(
            check_id,
            "skipped",
            ".harness/project.json не читается — см. files.project_json",
        )
    missing = [field for field in ("test_paths", "test_runner") if field not in config]
    if missing:
        return config, _line(
            check_id,
            "skipped",
            f"Тест-автор не включён: нет {' и '.join(missing)} в .harness/project.json",
        )
    return config, None


def _update_fix(context: HealthContext, what: str) -> Fix:
    return Fix(
        text=f"верните {what}: harness update восстановит managed-файлы тест-автора",
        command=context.harness_command("update", str(context.repo)),
    )


def _git(checkout: Path, *arguments: str) -> str | None:
    result = run_tool(["git", "-C", str(checkout), *arguments], timeout=30)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip()


def _main_checkout(repo: Path) -> Path | None:
    """The main checkout of the repository when `repo` is its linked worktree (ADR 0033)."""
    common = _git(repo, "rev-parse", "--git-common-dir")
    if not common:
        return None
    directory = (repo / common).resolve()
    main = directory.parent
    return main if directory.name == ".git" and main != repo else None


def _trusted_by(repo: Path) -> Path | None:
    """The trusted checkout that vouches for `repo`, the same rule as the preflight (ADR 0033).

    An entry for the exact path counts, and so does an entry for the main checkout when that
    checkout lists `repo` in `git worktree list --porcelain`. A parent directory does not count.
    """
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    state = (
        Path(config_dir).expanduser() / ".claude.json"
        if config_dir
        else Path.home() / ".claude.json"
    )
    try:
        document = json.loads(state.read_text(encoding="utf-8"))
    except JSON_READ_ERRORS:
        return None
    projects = document.get("projects") if isinstance(document, dict) else None
    if not isinstance(projects, dict):
        return None

    def accepted(path: Path) -> bool:
        entry = projects.get(str(path))
        return isinstance(entry, dict) and entry.get("hasTrustDialogAccepted") is True

    if accepted(repo):
        return repo
    main = _main_checkout(repo)
    if main is None or not accepted(main):
        return None
    top = _git(main, "rev-parse", "--show-toplevel")
    listing = _git(main, "worktree", "list", "--porcelain") or ""
    listed = any(
        Path(line[len("worktree ") :]).resolve() == repo
        for line in listing.splitlines()
        if line.startswith("worktree ")
    )
    return main if top is not None and Path(top).resolve() == main and listed else None


def _block(profile: dict[str, object]) -> str:
    return '"test_author": ' + json.dumps(
        {field: profile[field] for field in ("runtime", "model", "effort")},
        ensure_ascii=False,
    )


def _planned_profile(repo: Path) -> dict[str, object] | None:
    """runtime, model and effort of the developer plan in .harness/orchestration.json, if any."""
    try:
        selection = read_author(repo, planned=True)
    except AuthorUnavailable:
        return None
    return (
        selection
        if selection.get("source") == "orchestration.developer (planned)"
        else None
    )


def check_test_author_config(context: HealthContext) -> CheckResult:
    """The short-route `test_author` block; the fix fragment comes from the developer plan."""
    config, skipped = _opted_in(context, CONFIG_ID)
    if skipped is not None:
        return skipped
    repo = context.repo.resolve()
    plan = _planned_profile(repo)
    if plan is not None:
        fragment = _block(plan)
        source = "из плана developer в .harness/orchestration.json"
    else:
        fragment = _block(
            {"runtime": "claude", "model": "<модель>", "effort": "<усилие>"}
        )
        source = (
            "плана developer в .harness/orchestration.json нет — подставьте значения"
        )
    if "test_author" in config:
        problems = profile_problems(config["test_author"])
        if not problems:
            return _line(
                CONFIG_ID,
                "ok",
                f"Блок test_author: {_block(config['test_author'])} "
                "(/fast-implement; /implement берёт исполнителя developer из brief)",
            )
        return _line(
            CONFIG_ID,
            "warn",
            f"Блок test_author неверен (test_author_config_invalid): {problems[0]}",
            Fix(text=f"замените блок в .harness/project.json на {fragment} ({source})"),
        )
    return _line(
        CONFIG_ID,
        "warn",
        "В .harness/project.json нет блока test_author (test_author_missing): "
        "/fast-implement не запускает тест-автора",
        Fix(
            text=f"добавьте в .harness/project.json {fragment} ({source})"
            + ("; это делает harness health --fix" if plan is not None else ""),
            command=context.harness_command("health", "--fix", str(context.repo))
            if plan is not None
            else None,
        ),
    )


def fix_test_author_config(context: HealthContext, result: CheckResult) -> str | None:
    """`harness health --fix`: add a missing `test_author` block from the developer plan.

    An existing block, valid or not, is never overwritten; without a plan nothing is written.
    """
    if result.status != "warn":
        return None
    path = context.repo / PROJECT_JSON_SOURCE
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except JSON_READ_ERRORS:
        return None
    if not isinstance(config, dict) or "test_author" in config:
        return None
    plan = _planned_profile(context.repo.resolve())
    if plan is None:
        return None
    config["test_author"] = {
        field: plan[field] for field in ("runtime", "model", "effort")
    }
    path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return f"в {PROJECT_JSON_SOURCE} добавлен {_block(plan)} из плана developer"


def check_test_author_root(context: HealthContext) -> CheckResult:
    """The project root comes from Git; a set CLAUDE_PROJECT_DIR must name the same root."""
    _, skipped = _opted_in(context, ROOT_ID)
    if skipped is not None:
        return skipped
    repo = context.repo.resolve()
    top = _git(repo, "rev-parse", "--show-toplevel")
    if top is None:
        return _line(
            ROOT_ID,
            "warn",
            f"Корень проекта: {repo} — не рабочее дерево Git (project_untrusted)",
            Fix(
                text="установите harness в checkout Git и запустите health в его корне; "
                "проверка:",
                command=shell_join(
                    ["git", "-C", str(repo), "rev-parse", "--show-toplevel"]
                ),
            ),
        )
    root = Path(top).resolve()
    if root != repo:
        return _line(
            ROOT_ID,
            "warn",
            f"Корень проекта по Git — {root}, а не {repo} (project_untrusted)",
            Fix(
                text="запустите health для корня Git",
                command=context.harness_command("health", str(root)),
            ),
        )
    variable = os.environ.get("CLAUDE_PROJECT_DIR")
    if variable:
        named = Path(variable).resolve()
        if named != root:
            return _line(
                ROOT_ID,
                "warn",
                f"CLAUDE_PROJECT_DIR={named} не совпадает с корнем Git {root} "
                "(project_dir_mismatch): Agent(test-author) этой сессии привязан к другому checkout",
                Fix(
                    text=f"запустите сессию Claude Code в {root} или уберите переменную: "
                    "unset CLAUDE_PROJECT_DIR"
                ),
            )
    return _line(ROOT_ID, "ok", f"Корень проекта по Git: {root}")


def check_test_author_trust(context: HealthContext) -> CheckResult:
    """Claude Code trust for this checkout: the exact path or the main checkout of its repository."""
    _, skipped = _opted_in(context, TRUST_ID)
    if skipped is not None:
        return skipped
    repo = context.repo.resolve()
    trusted = _trusted_by(repo)
    if trusted == repo:
        return _line(TRUST_ID, "ok", f"Доверие Claude Code: {repo}")
    if trusted is not None:
        return _line(
            TRUST_ID, "ok", f"Доверие Claude Code: через основной checkout {trusted}"
        )
    target = _main_checkout(repo) or repo
    return _line(
        TRUST_ID,
        "warn",
        f"Claude Code не доверяет {repo} (project_untrusted): нет hasTrustDialogAccepted "
        f"для {target} в ~/.claude.json",
        Fix(
            text=f"один раз откройте Claude Code в {target} и примите диалог доверия; "
            "worktree доверенного репозитория отдельного доверия не требуют",
            command=f"cd {shell_join([str(target)])} && claude",
        ),
    )


def check_test_author_guard(context: HealthContext) -> CheckResult:
    """The test-author agent, its scoped guard and the guard's view of the project config."""
    _, skipped = _opted_in(context, GUARD_ID)
    if skipped is not None:
        return skipped
    repo = context.repo.resolve()
    agent, guard = repo / TEST_AUTHOR_AGENT, repo / GUARD_REL
    if agent.is_symlink() or not agent.is_file():
        return _line(
            GUARD_ID,
            "warn",
            f"Нет агента {TEST_AUTHOR_AGENT} (agent_missing)",
            _update_fix(context, TEST_AUTHOR_AGENT),
        )
    if not guard.is_file() or not os.access(guard, os.X_OK):
        return _line(
            GUARD_ID,
            "warn",
            f"Guard {GUARD_REL} отсутствует или не исполняемый (guard_hook_unavailable)",
            _update_fix(context, GUARD_REL),
        )
    if _trusted_by(repo) is None:
        return _line(
            GUARD_ID,
            "skipped",
            f"Guard {GUARD_REL} на месте; его конфигурацию health проверит после доверия — "
            f"см. {TRUST_ID}",
        )
    result = run_tool(
        [sys.executable, str(guard), "--validate-config"],
        cwd=repo,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo)},
        timeout=30,
    )
    answer = _answer(result.stdout if result is not None else "")
    if answer == ("ok", None):
        return _line(
            GUARD_ID, "ok", f"Guard {GUARD_REL}: конфигурация тест-автора принята"
        )
    reason = answer[0]
    if reason not in GUARD_STEPS and reason != "agent_missing":
        return _line(
            GUARD_ID,
            "warn",
            f"Guard {GUARD_REL} не ответил на --validate-config (guard_hook_unavailable)",
            _update_fix(context, GUARD_REL),
        )
    return _line(
        GUARD_ID,
        "warn",
        f"Guard {GUARD_REL} отклонил конфигурацию: {reason}",
        Fix(text=GUARD_STEPS[reason])
        if reason in GUARD_STEPS
        else _update_fix(context, TEST_AUTHOR_AGENT),
    )


def check_test_author_runner(context: HealthContext) -> CheckResult:
    """The protected runner entry point and its module, without running a test."""
    _, skipped = _opted_in(context, RUNNER_ID)
    if skipped is not None:
        return skipped
    repo = context.repo.resolve()
    runner = repo / RUNNER_REL
    if not runner.is_file() or not os.access(runner, os.X_OK):
        return _line(
            RUNNER_ID,
            "warn",
            f"Runner {RUNNER_REL} отсутствует или не исполняемый (runner_unavailable)",
            _update_fix(context, RUNNER_REL),
        )
    return _line(RUNNER_ID, "ok", f"Runner: {RUNNER_REL}")


def check_test_author_probe(context: HealthContext) -> CheckResult:
    """The runner's isolation probe; it creates and removes a disposable sandbox."""
    _, skipped = _opted_in(context, PROBE_ID)
    if skipped is not None:
        return skipped
    repo = context.repo.resolve()
    runner = repo / RUNNER_REL
    if not runner.is_file() or not os.access(runner, os.X_OK):
        return _line(
            PROBE_ID, "skipped", f"Probe не запускается без runner — см. {RUNNER_ID}"
        )
    if _trusted_by(repo) is None:
        return _line(
            PROBE_ID,
            "skipped",
            f"Probe запускается только после доверия — см. {TRUST_ID}",
        )
    bash = shutil.which("bash")
    result = (
        run_tool(
            [bash, str(runner), "--probe"],
            cwd=repo,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo)},
            timeout=135,
        )
        if bash is not None
        else None
    )
    reason, detail = _answer(result.stdout if result is not None else "", "unavailable")
    if reason == "ok":
        return _line(PROBE_ID, "ok", "Probe изоляции runner: ok")
    manual = Fix(
        text="ответ probe не разобран: запустите его вручную",
        command=shell_join([str(runner), "--probe"]),
    )
    if reason == "runner_unavailable":
        step: Fix = _update_fix(context, RUNNER_REL)
    elif reason in CONFIG_REASONS:
        step = Fix(text=CONFIG_STEP)
    elif reason == "isolation_unavailable" and detail in ISOLATION_STEPS:
        step = Fix(text=ISOLATION_STEPS[detail])
    else:
        reason, detail, step = "isolation_unavailable", None, manual
    return _line(
        PROBE_ID,
        "warn",
        f"Probe изоляции runner: {reason}" + (f" ({detail})" if detail else ""),
        step,
    )


def _answer(text: str, refusal: str = "disabled") -> tuple[str | None, str | None]:
    """(reason, isolation detail) of a fixed-shape answer; ("ok", None) for an ok answer.

    Only reasons and details from the fixed sets pass, so no free text reaches the report.
    """
    try:
        value = json.loads(text) if len(text) <= 512 else None
    except (ValueError, RecursionError):
        value = None
    if value == {"status": "ok"}:
        return "ok", None
    if not isinstance(value, dict) or value.get("status") != refusal:
        return None, None
    reason = value.get("reason")
    detail = value.get("detail")
    return (
        reason if isinstance(reason, str) and reason in PREFLIGHT_REASONS else None,
        detail if isinstance(detail, str) and detail in ISOLATION_STEPS else None,
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
    # Setting its identity is not granting trust: the checkout or its main checkout must be trusted.
    if _trusted_by(repo) is None:
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


def unregistered_envelope_scripts(repo: Path) -> tuple[str, ...] | None:
    """Скрипты `.claude/hooks/*.sh`, чей hook_id не зарегистрирован в установленном конверте.

    Нет конверта — `()`: скрипты тогда работают без него. Конверт не разбирается — None."""
    hooks_dir = repo / HOOKS_DIR
    envelope = repo / ENVELOPE_REL
    if not envelope.is_file():
        return ()
    try:
        known = envelope_hook_ids(envelope.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        known = None
    if known is None:
        return None
    unknown: list[str] = []
    for script in sorted(hooks_dir.glob("*.sh")):
        try:
            hook_id = script_envelope_id(script.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if hook_id is not None and hook_id not in known:
            unknown.append(script.name)
    return tuple(unknown)


def _result(
    context: HealthContext,
    fails: list[str],
    warns: list[str],
    advisory: list[str],
    notes: list[str],
    fix: Fix | None = None,
) -> CheckResult:
    """Собрать результат: fail важнее warn, warn важнее ok; части сообщения разделены `; `.

    `fix` заменяет общую подсказку `harness update`, когда находку чинит другая команда.

    `advisory` — предупреждения, которые `harness update` не исправляет (у runtime нет события):
    они дают статус warn, но не подсказку исправления. Первая заметка — профиль. Символ без
    UTF-8 формы (одиночный суррогат из project.json) попадает в сообщение как escape `\\udXXX`,
    чтобы вывод отчёта не падал."""
    status: Status = "fail" if fails else "warn" if warns or advisory else "ok"
    if fix is None and (fails or warns):
        fix = Fix(
            text="верните managed hooks: harness update восстановит недостающие файлы и записи; "
            "изменённый файл после просмотра заменяет --force-seed-file <путь>, "
            "прежние байты сохраняются в .harness/.sandboxes/seed-backups/<UTC-время>/",
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
        if spec.wiring == "agent" or adapter.runtime not in spec.runtimes:
            continue  # hook не поставляется этому runtime: не применимо
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
        tools = supported_tools(spec, adapter.support, adapter.runtime)
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


def _wired_scripts(repo: Path) -> set[str]:
    """Имена скриптов `.claude/hooks/`, подключённых в любом файле hooks runtime."""
    wired: set[str] = set()
    for adapter in ADAPTERS:
        try:
            document: object = json.loads(
                (repo / adapter.config).read_text(encoding="utf-8")
            )
        except JSON_READ_ERRORS:
            continue
        hooks = document.get("hooks") if isinstance(document, dict) else None
        for groups in hooks.values() if isinstance(hooks, dict) else []:
            for group in groups if isinstance(groups, list) else []:
                handlers = group.get("hooks") if isinstance(group, dict) else None
                for handler in handlers if isinstance(handlers, list) else []:
                    if (name := script_name(handler)) is not None:
                        wired.add(name)
    return wired


def _envelope_files_part(repo: Path, fails: list[str], warns: list[str]) -> None:
    """Файлы конверта, которых нет, хотя скрипты hooks его вызывают: такой скрипт молча отвечает
    без JSON-конверта и политики hooks. `hook_response.py` нужен каждому скрипту с hook_id,
    `hook-envelope.sh` — скриптам, которые его подключают. Подключённый скрипт даёт fail."""
    users: dict[str, list[str]] = {ENVELOPE_REL: [], ENVELOPE_SOURCE_REL: []}
    for script in sorted((repo / HOOKS_DIR).glob("*.sh")):
        try:
            source = script.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if script_envelope_id(source) is None:
            continue
        users[ENVELOPE_REL].append(script.name)
        if '/hook-envelope.sh"' in source:
            users[ENVELOPE_SOURCE_REL].append(script.name)
    wired = _wired_scripts(repo)
    for relative, scripts in users.items():
        if not scripts or (repo / relative).is_file():
            continue
        text = (
            f"{relative}: файл отсутствует, скрипты hooks ({len(scripts)}) отвечают "
            "без JSON-конверта"
        )
        (fails if wired.intersection(scripts) else warns).append(text)


def _envelope_part(
    context: HealthContext, fails: list[str], warns: list[str]
) -> Fix | None:
    """Скрипты hooks, чей hook_id не регистрирует установленный конверт; Fix — его замена."""
    repo = context.repo
    unknown = unregistered_envelope_scripts(repo)
    if unknown == ():
        return None
    if unknown is None:
        fails.append("hook_response.py: HOOKS не читается")
    else:
        wired = _wired_scripts(repo)
        for script in unknown:
            hook_id = script_envelope_id(
                (repo / HOOKS_DIR / script).read_text(encoding="utf-8")
            )
            text = f"{ENVELOPE_REL} не регистрирует hook_id {hook_id} ({script}"
            if script in wired:
                fails.append(f"{text}, подключён)")
            else:
                warns.append(f"{text})")
    return Fix(
        text=f"замените конверт шаблоном: {ENVELOPE_REL} перезапишется, прежние байты "
        "сохранятся в .harness/.sandboxes/seed-backups/<UTC-время>/, затем update подключит hooks",
        command=context.harness_command(
            "update", str(repo), "--force-seed-file", ENVELOPE_REL
        ),
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
    _envelope_files_part(context.repo, fails, warns)
    envelope_fix = _envelope_part(context, fails, warns)
    return _result(context, fails, warns, advisory, notes, envelope_fix)
