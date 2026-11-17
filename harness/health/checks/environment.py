"""Группа 'environment': кроссплатформенные проверки утилит и настроек репозитория (задача #343).

Включает проверку Git и автора коммитов, переводов строк, Python, uv, версии glab для
GitLab-трекера проекта, dev-окружения канонического репозитория и кодировки вывода, а также
готовность среды к обязательным QA-командам (#1050): исполняемые файлы qa_gate_commands,
C-компоновщик для Rust и длина пути сокета runtime.

Каждая внешняя утилита разрешается через `shutil.which` и вызывается по полному пути,
благодаря чему shim-файлы `.cmd` в Windows PATH находятся так же, как в шелле. Отсутствующая
или неработающая утилита возвращает статус `fail`/`skipped`, никогда не вызывая исключений.
"""

from __future__ import annotations

import codecs
import locale
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from harness.configuration import read_config_json

from ..context import HealthContext
from ..model import CheckResult, Fix
from ..process import run_tool
from ..project_tracker import resolve_project_tracker

GROUP = "environment"

MIN_PYTHON: tuple[int, int] = (3, 12)
# The minimum glab for a GitLab project tracker (docs/adr/0011): older releases miss flags or
# mishandle a host with a port that delivery relies on.
MIN_GLAB: tuple[int, int, int] = (1, 117, 0)
_GLAB_INSTALL_URL = "https://gitlab.com/gitlab-org/cli#installation"
_VERSION_NUMBER = re.compile(r"(\d+)\.(\d+)\.(\d+)")
# The canonical harness source repository: the only project whose dev environment health syncs.
HARNESS_PROJECT_NAME = "claude-agent-harness"
DEV_VENV_REL = Path(".harness/.venv")

_TOOL_TIMEOUT_SECONDS = 60
_MAX_LISTED_FILES = 20
_TEXT_EOLS = frozenset({"lf", "crlf"})

_GIT_INSTALL_FIX = Fix(text="установите git: https://git-scm.com/downloads")
_UV_INSTALL_FIX = Fix(
    text="установите uv: https://docs.astral.sh/uv/getting-started/installation/"
)


def _run(
    argv: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str] | None:
    """Запустить локальную утилиту с таймаутом группы environment; None при ошибке запуска или таймауте."""
    return run_tool(argv, timeout=_TOOL_TIMEOUT_SECONDS, cwd=cwd, env=env)


def _git(
    context: HealthContext, *arguments: str
) -> subprocess.CompletedProcess[str] | None:
    """Вызвать команду git исключительно для явного репозитория."""
    executable = shutil.which("git")
    if executable is None:
        return None
    checkout = context.repo.resolve()
    return _run(
        [
            executable,
            "-c",
            f"safe.directory={checkout}",
            "-C",
            str(checkout),
            *arguments,
        ]
    )


def _first_line(text: str) -> str:
    """Получить первую непустую строку переданного текста."""
    return text.strip().splitlines()[0] if text.strip() else ""


def _last_line(text: str) -> str:
    """Получить последнюю непустую строку переданного текста."""
    return text.strip().splitlines()[-1] if text.strip() else ""


def _tool_version(name: str) -> str | None:
    """Получить первую строку вывода `<name> --version` или None при отсутствии/сбое утилиты."""
    executable = shutil.which(name)
    if executable is None:
        return None
    result = _run([executable, "--version"])
    if result is None or result.returncode != 0:
        return None
    return _first_line(result.stdout) or name


def _is_git_worktree(context: HealthContext) -> bool:
    """Проверить, находится ли путь внутри рабочего дерева Git."""
    result = _git(context, "rev-parse", "--is-inside-work-tree")
    return (
        result is not None
        and result.returncode == 0
        and result.stdout.strip() == "true"
    )


# --- git ---------------------------------------------------------------------------------------


def check_os(_context: HealthContext) -> CheckResult:
    """Информационная проверка: операционная система и её версия для контекста применимости правил."""
    release = platform.release()
    version = platform.version()
    details = " ".join(part for part in (platform.system() or os.name, release) if part)
    if version and version != release:
        details = f"{details} ({version})"
    return CheckResult(
        id="environment.os", group=GROUP, status="ok", message=f"ОС: {details}"
    )


def check_git(_context: HealthContext) -> CheckResult:
    """Проверить наличие и версию утилиты git."""
    version = _tool_version("git")
    if version is None:
        return CheckResult(
            id="environment.git",
            group=GROUP,
            status="fail",
            message="git не найден в PATH или не запускается",
            fix=_GIT_INSTALL_FIX,
        )
    return CheckResult(id="environment.git", group=GROUP, status="ok", message=version)


def _git_config(context: HealthContext, key: str) -> str | None:
    """Получить значение конфигурационного параметра git по ключу или None."""
    result = _git(context, "config", "--get", key)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip() or None


def check_git_identity(context: HealthContext) -> CheckResult:
    """Проверить настройку параметров автора коммитов user.name и user.email в git."""
    if shutil.which("git") is None:
        return CheckResult(
            id="environment.git_identity",
            group=GROUP,
            status="skipped",
            message="git недоступен: user.name/user.email не проверены",
        )
    placeholders = {"user.name": "Имя Фамилия", "user.email": "you@example.com"}
    missing = [key for key in placeholders if _git_config(context, key) is None]
    if not missing:
        return CheckResult(
            id="environment.git_identity",
            group=GROUP,
            status="ok",
            message="git user.name и user.email заданы",
        )
    return CheckResult(
        id="environment.git_identity",
        group=GROUP,
        status="warn",
        message=f"в git не заданы: {', '.join(missing)}",
        fix=Fix(
            text="задайте автора коммитов",
            command=" && ".join(
                f'git config --global {key} "{placeholders[key]}"' for key in missing
            ),
        ),
    )


# --- line endings ------------------------------------------------------------------------------


def check_gitattributes(context: HealthContext) -> CheckResult:
    """Проверить наличие файла .gitattributes для нормализации переводов строк."""
    if (context.repo / ".gitattributes").is_file():
        return CheckResult(
            id="environment.gitattributes",
            group=GROUP,
            status="ok",
            message=".gitattributes есть",
        )
    return CheckResult(
        id="environment.gitattributes",
        group=GROUP,
        status="warn",
        message="нет .gitattributes: переводы строк зависят от core.autocrlf каждой машины",
        fix=Fix(
            text="добавьте .gitattributes с явной нормализацией, например строку `* text=auto eol=lf`, "
            "и закоммитьте его"
        ),
    )


def eol_mismatch(index_eol: str, worktree_eol: str, attributes: str) -> bool:
    """Проверить, расходится ли запись `git ls-files --eol` с объявленными gitattributes.

    Оцениваются только файлы, которые git по атрибутам считает текстовыми. Расхождением считаются:
    смешанные переводы строк, CRLF в индексе нормализованного текстового файла либо перевод строк
    в рабочем дереве, отличающийся от явного `eol=`.
    """
    tokens = attributes.split()
    if not tokens or "-text" in tokens or "binary" in tokens:
        return False
    declared_eol = next(
        (token.removeprefix("eol=") for token in tokens if token.startswith("eol=")),
        None,
    )
    is_text = declared_eol is not None or any(
        token == "text" or token.startswith("text=") for token in tokens
    )
    if not is_text:
        return False
    if "mixed" in (index_eol, worktree_eol):
        return True
    if index_eol == "crlf":
        return True
    return (
        declared_eol is not None
        and worktree_eol in _TEXT_EOLS
        and worktree_eol != declared_eol
    )


def parse_ls_files_eol(output: str) -> list[tuple[str, str, str, str]]:
    """Разобрать вывод команды `git ls-files --eol -z` на кортежи (index_eol, worktree_eol, attributes, path)."""
    entries: list[tuple[str, str, str, str]] = []
    for record in output.split("\0"):
        if "\t" not in record:
            continue
        info, path = record.split("\t", 1)
        fields = info.split(None, 2)
        index_eol = worktree_eol = attributes = ""
        for field in fields:
            if field.startswith("i/"):
                index_eol = field[2:]
            elif field.startswith("w/"):
                worktree_eol = field[2:]
            elif field.startswith("attr/"):
                attributes = field[5:].strip()
        entries.append((index_eol, worktree_eol, attributes, path))
    return entries


def check_line_endings(context: HealthContext) -> CheckResult:
    """Проверить соответствие переводов строк в репозитории заданным gitattributes."""
    if shutil.which("git") is None:
        return CheckResult(
            id="environment.line_endings",
            group=GROUP,
            status="skipped",
            message="git недоступен: переводы строк не проверены",
        )
    if not _is_git_worktree(context):
        return CheckResult(
            id="environment.line_endings",
            group=GROUP,
            status="skipped",
            message="не git-репозиторий: переводы строк не проверены",
        )
    autocrlf = _git_config(context, "core.autocrlf") or "не задан"
    info = f"core.autocrlf={autocrlf} (информация)"
    result = _git(context, "ls-files", "--eol", "-z")
    if result is None or result.returncode != 0:
        detail = (
            _last_line(result.stderr) if result is not None else "git не запустился"
        )
        return CheckResult(
            id="environment.line_endings",
            group=GROUP,
            status="skipped",
            message=f"git ls-files --eol не выполнился ({detail}); {info}",
        )
    diverged = [
        path
        for index_eol, worktree_eol, attributes, path in parse_ls_files_eol(
            result.stdout
        )
        if eol_mismatch(index_eol, worktree_eol, attributes)
    ]
    if not diverged:
        return CheckResult(
            id="environment.line_endings",
            group=GROUP,
            status="ok",
            message=f"переводы строк не расходятся с атрибутами git; {info}",
        )
    listed = ", ".join(diverged[:_MAX_LISTED_FILES])
    if len(diverged) > _MAX_LISTED_FILES:
        listed += f" и ещё {len(diverged) - _MAX_LISTED_FILES}"
    return CheckResult(
        id="environment.line_endings",
        group=GROUP,
        status="warn",
        message=f"переводы строк расходятся с атрибутами git в {len(diverged)} файл(ах): {listed}; {info}",
        fix=Fix(
            text="нормализуйте файлы в индексе и закоммитьте результат; рабочие копии с чужими "
            "переводами строк извлеките заново после сохранения своих изменений",
            command="git add --renormalize .",
        ),
    )


# --- Python and uv -----------------------------------------------------------------------------


def _python_version() -> tuple[int, int, int]:
    """Получить кортеж версии текущего интерпретатора Python (major, minor, micro)."""
    return (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)


def check_python(_context: HealthContext) -> CheckResult:
    """Проверить версию интерпретатора Python на соответствие минимально требуемой."""
    version = _python_version()
    shown = ".".join(str(part) for part in version)
    required = ".".join(str(part) for part in MIN_PYTHON)
    if version[:2] < MIN_PYTHON:
        return CheckResult(
            id="environment.python",
            group=GROUP,
            status="fail",
            message=f"Python {shown} ({sys.executable}) ниже требуемого {required}",
            fix=Fix(
                text=f"установите Python {required} или новее и запускайте harness этим интерпретатором"
            ),
        )
    return CheckResult(
        id="environment.python",
        group=GROUP,
        status="ok",
        message=f"Python {shown} ({sys.executable})",
    )


def check_uv(_context: HealthContext) -> CheckResult:
    """Проверить наличие и версию утилиты uv."""
    version = _tool_version("uv")
    if version is None:
        return CheckResult(
            id="environment.uv",
            group=GROUP,
            status="fail",
            message="uv не найден в PATH или не запускается",
            fix=_UV_INSTALL_FIX,
        )
    return CheckResult(id="environment.uv", group=GROUP, status="ok", message=version)


def check_glab(context: HealthContext) -> CheckResult:
    """Проверить, что glab не старше MIN_GLAB, если трекер проекта — GitLab; иначе пропустить.

    Проверка локальная: только `glab --version`, без сети и без `--online`.
    """
    check_id = "environment.glab"
    if resolve_project_tracker(context.repo).effective.type != "gitlab":
        return CheckResult(
            id=check_id,
            group=GROUP,
            status="skipped",
            message="glab: не проверено (трекер проекта не GitLab)",
        )
    required = ".".join(str(part) for part in MIN_GLAB)
    upgrade = Fix(
        text=f"установите или обновите glab до {required} или новее: {_GLAB_INSTALL_URL}"
    )
    version = _tool_version("glab")
    if version is None:
        return CheckResult(
            id=check_id,
            group=GROUP,
            status="warn",
            message="glab не найден в PATH или не запускается: он нужен для GitLab-трекера проекта",
            fix=upgrade,
        )
    match = _VERSION_NUMBER.search(version)
    if match is None:
        return CheckResult(
            id=check_id,
            group=GROUP,
            status="warn",
            message=f"не удалось разобрать версию glab: {version}",
            fix=upgrade,
        )
    if tuple(int(part) for part in match.groups()) < MIN_GLAB:
        return CheckResult(
            id=check_id,
            group=GROUP,
            status="fail",
            message=f"{version}: glab старше минимальной версии {required} для GitLab-трекера проекта",
            fix=upgrade,
        )
    return CheckResult(id=check_id, group=GROUP, status="ok", message=version)


def is_harness_source_repo(repo: Path) -> bool:
    """Проверить, является ли репозиторий каноническим репозиторием харнесса (по pyproject.toml и uv.lock)."""
    pyproject = repo / "pyproject.toml"
    if not pyproject.is_file() or not (repo / "uv.lock").is_file():
        return False
    try:
        import tomllib

        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (ImportError, OSError, ValueError):
        return False
    project = data.get("project")
    return isinstance(project, dict) and project.get("name") == HARNESS_PROJECT_NAME


def _dev_sync_command() -> str:
    """Сформировать команду синхронизации dev-окружения для текущей платформы."""
    if os.name == "nt":
        return "$env:UV_PROJECT_ENVIRONMENT='.harness\\.venv'; uv sync --locked"
    return "UV_PROJECT_ENVIRONMENT=.harness/.venv uv sync --locked"


def check_dev_environment(context: HealthContext) -> CheckResult:
    """Проверить синхронизацию локального dev-окружения .harness/.venv с файлом uv.lock."""
    if not is_harness_source_repo(context.repo):
        return CheckResult(
            id="environment.dev_env",
            group=GROUP,
            status="skipped",
            message=f"не репозиторий {HARNESS_PROJECT_NAME}: синхронность dev-окружения не проверяется",
        )
    executable = shutil.which("uv")
    if executable is None:
        return CheckResult(
            id="environment.dev_env",
            group=GROUP,
            status="skipped",
            message="uv недоступен: синхронность dev-окружения не проверена",
        )
    venv = context.repo / DEV_VENV_REL
    argv = [executable, "sync", "--locked", "--check"]
    if not context.online:
        argv.append("--offline")
    env = dict(os.environ, UV_PROJECT_ENVIRONMENT=str(venv))
    result = _run(argv, cwd=context.repo, env=env)
    if result is not None and result.returncode == 0:
        return CheckResult(
            id="environment.dev_env",
            group=GROUP,
            status="ok",
            message=f"{DEV_VENV_REL.as_posix()} синхронизировано с uv.lock",
        )
    detail = (
        _last_line(result.stderr) or _last_line(result.stdout)
        if result is not None
        else "uv sync --check не завершился"
    )
    return CheckResult(
        id="environment.dev_env",
        group=GROUP,
        status="warn",
        message=f"{DEV_VENV_REL.as_posix()} не синхронизировано с uv.lock: {detail or 'без подробностей'}",
        fix=Fix(
            text="синхронизируйте dev-окружение по uv.lock (или выполните make bootstrap)",
            command=_dev_sync_command(),
        ),
    )


# --- QA commands (#1050) -----------------------------------------------------------------------
# These checks only read the environment; no QA command is run.

# Shell builtins are not files on PATH, so a command that starts with one is not checked.
_SHELL_BUILTINS = frozenset({".", ":", "cd", "export", "set", "source", "test", "true", "["})
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


def _qa_gate_commands(repo: Path) -> list[str] | None:
    """Строки qa_gate_commands из .harness/project.json; None, если файл не читается как JSON-объект."""
    try:
        data = read_config_json(repo / ".harness" / "project.json")
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    commands = data.get("qa_gate_commands")
    if not isinstance(commands, list):
        return []
    return [command for command in commands if isinstance(command, str) and command.strip()]


def _executable(command: str) -> str | None:
    """Исполняемый файл, который запускает QA-команда: первое слово после присваиваний VAR=...

    None, если команда начинается со встроенной команды shell или пуста.
    """
    try:
        words = shlex.split(command)
    except ValueError:
        words = command.split()
    while words and _ASSIGNMENT.match(words[0]):
        words = words[1:]
    if not words or words[0] in _SHELL_BUILTINS:
        return None
    return words[0]


def _executable_found(repo: Path, executable: str) -> bool:
    """Найти исполняемый файл: путь с разделителем — от корня репозитория, иначе — в PATH."""
    if "/" in executable or os.sep in executable:
        path = Path(executable) if Path(executable).is_absolute() else repo / executable
        return path.is_file() and os.access(path, os.X_OK)
    return shutil.which(executable) is not None


def _no_qa_commands(check_id: str, commands: list[str] | None) -> CheckResult:
    """Пропуск проверки: project.json не читается (см. files.project_json) или в нём нет QA-команд."""
    reason = (
        "не проверено: .harness/project.json не читается (см. files.project_json)"
        if commands is None
        else "в .harness/project.json нет qa_gate_commands"
    )
    return CheckResult(id=check_id, group=GROUP, status="skipped", message=reason)


def check_qa_executables(context: HealthContext) -> CheckResult:
    """Проверить, что исполняемый файл каждой команды из qa_gate_commands доступен в среде агента."""
    check_id = "environment.qa_executables"
    commands = _qa_gate_commands(context.repo)
    if not commands:
        return _no_qa_commands(check_id, commands)
    executables = list(
        dict.fromkeys(name for name in map(_executable, commands) if name is not None)
    )
    missing = [name for name in executables if not _executable_found(context.repo, name)]
    if not missing:
        return CheckResult(
            id=check_id,
            group=GROUP,
            status="ok",
            message=f"исполняемые файлы QA-команд найдены: {', '.join(executables) or 'нет'}",
        )
    names = ", ".join(missing)
    return CheckResult(
        id=check_id,
        group=GROUP,
        status="warn",
        message=f"QA-команды не выполнятся: не найдены исполняемые файлы {names}",
        fix=Fix(
            text=(
                f"установите {names} в среду, где агент запускает QA, или добавьте их каталог "
                "в PATH; путь с '/' ищется от корня репозитория"
            )
        ),
    )


_CARGO_WORD = re.compile(r"(?<![\w./-])cargo(?![\w.-])")


def _has_native_cargo_manifest(repo: Path) -> bool:
    """Есть ли Cargo.toml под native/; каталоги сборки target/ не обходятся."""
    for _root, dirs, files in os.walk(repo / "native"):
        if "Cargo.toml" in files:
            return True
        dirs[:] = [name for name in dirs if name != "target"]
    return False


def check_c_linker(context: HealthContext) -> CheckResult:
    """Проверить, что для сборки Rust в среде агента есть C-компоновщик cc.

    Проект собирает Rust, если слово cargo есть в любой QA-команде (в том числе после `&&`)
    или под native/ лежит Cargo.toml.
    """
    check_id = "environment.c_linker"
    builds_rust = any(
        _CARGO_WORD.search(command) for command in _qa_gate_commands(context.repo) or []
    ) or _has_native_cargo_manifest(context.repo)
    if not builds_rust:
        return CheckResult(
            id=check_id,
            group=GROUP,
            status="skipped",
            message="проект не собирает Rust: нет cargo в qa_gate_commands и native/**/Cargo.toml",
        )
    linker = shutil.which("cc")
    if linker is not None:
        return CheckResult(
            id=check_id,
            group=GROUP,
            status="ok",
            message=f"C-компоновщик для Rust найден: {linker}",
        )
    return CheckResult(
        id=check_id,
        group=GROUP,
        status="warn",
        message="проект собирает Rust, но C-компоновщика cc нет в PATH: cargo не скомпонует бинарники",
        fix=Fix(
            text=(
                "установите C-компилятор с компоновщиком cc (gcc или clang) в среду, где агент "
                "запускает QA, например в контейнер или distrobox"
            )
        ),
    )


def check_runtime_socket_path(context: HealthContext) -> CheckResult:
    """Проверить, что путь сокета runtime этого репозитория укладывается в лимит Unix-сокета.

    Путь строится по правилу ADR 0021, как в runtime_client.runtime_paths: `$XDG_RUNTIME_DIR/harness`
    или `/tmp/harness-<uid>`; TMPDIR на него не влияет. Runtime при этом не запускается.
    """
    check_id = "environment.runtime_socket_path"
    if not context.orchestration_enabled():
        return CheckResult(
            id=check_id,
            group=GROUP,
            status="skipped",
            message=context.no_orchestration_message(),
        )
    if sys.platform == "win32":
        return CheckResult(
            id=check_id,
            group=GROUP,
            status="skipped",
            message="в Windows runtime слушает именованный канал, лимит пути сокета не действует",
        )
    from harness.orchestration.runtime_client import (
        MAX_SOCKET_PATH_BYTES,
        RuntimeClientError,
        git_common_dir,
        repo_id,
        runtime_directory,
    )

    try:
        identity = repo_id(git_common_dir(context.repo.resolve()))
    except (RuntimeClientError, OSError, UnicodeDecodeError) as error:
        return CheckResult(
            id=check_id,
            group=GROUP,
            status="skipped",
            message=f"не проверено: не удалось определить Git-репозиторий ({error})",
        )
    directory = runtime_directory(
        sys.platform, os.environ.get("XDG_RUNTIME_DIR"), None, os.getuid()
    )
    socket = Path(str(directory)) / f"{identity}.sock"
    size = len(os.fsencode(socket))
    if size <= MAX_SOCKET_PATH_BYTES:
        return CheckResult(
            id=check_id,
            group=GROUP,
            status="ok",
            message=f"путь сокета runtime в пределах {MAX_SOCKET_PATH_BYTES} байт: {socket}",
        )
    return CheckResult(
        id=check_id,
        group=GROUP,
        status="warn",
        message=(
            f"путь сокета runtime {socket} занимает {size} байт, больше лимита "
            f"{MAX_SOCKET_PATH_BYTES}: runtime не запустится"
        ),
        fix=Fix(
            text=(
                "задайте XDG_RUNTIME_DIR короткому существующему абсолютному каталогу и "
                "перезапустите runtime"
            )
        ),
    )


# --- output encoding ---------------------------------------------------------------------------


def _is_utf8(encoding: str | None) -> bool:
    """Проверить, нормализуется ли имя кодировки в каноническое utf-8."""
    if not encoding:
        return False
    try:
        return codecs.lookup(encoding).name == "utf-8"
    except LookupError:
        return False


def check_output_encoding(context: HealthContext) -> CheckResult:
    """Проверить кодировку потока вывода и локали на совместимость с UTF-8.

    Учитывает кодировку потока, зафиксированную вызывающей стороной до внутренней перенастройки
    (см. HealthContext.output_encoding), и кодировку локали, наследуемую дочерними процессами.
    """
    stream = context.output_encoding
    if stream is None:
        stream = getattr(sys.stdout, "encoding", None)
    preferred = locale.getpreferredencoding(False)
    shown = f"вывод: {stream or 'неизвестна'}, локаль: {preferred or 'неизвестна'}"
    # Неизвестная кодировка потока не доказывает проблему: харнесс сам форсирует UTF-8 на выводе.
    if (stream is None or _is_utf8(stream)) and _is_utf8(preferred):
        return CheckResult(
            id="environment.output_encoding",
            group=GROUP,
            status="ok",
            message=f"кодировка UTF-8 ({shown})",
        )
    return CheckResult(
        id="environment.output_encoding",
        group=GROUP,
        status="warn",
        message=f"кодировка не UTF-8 ({shown}): кириллица и метки статуса могут искажаться",
        fix=Fix(
            text="включите UTF-8 режим Python для пользователя и перезапустите терминал",
            command="setx PYTHONUTF8 1" if os.name == "nt" else "export PYTHONUTF8=1",
        ),
    )
