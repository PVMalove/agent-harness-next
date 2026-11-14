"""Общие помощники сценариев clean-room: команды harness, запуск процессов и проверка hooks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import IO, TypedDict, Unpack

from harness.gate_runner.gate_runner import sanitise
from harness.storage import storage_path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = [sys.executable, str(ROOT / "harness" / "bin" / "harness.py")]
INSTALL_GLOBAL = [sys.executable, str(ROOT / "bin" / "install-global.py")]


def _find_bash() -> str:
    """Путь к рабочему bash.

    На Windows голый `bash` может найти заглушку WSL в System32, которая без настроенного
    дистрибутива не работает, раньше bash из Git. Поэтому bash ищется от каталога установки Git;
    на остальных платформах достаточно `bash`.
    """
    if sys.platform != "win32":
        return "bash"
    git_exe = shutil.which("git")
    if git_exe:
        # git.exe lives at varying depths under the Git install root (cmd/, bin/, or
        # mingw64/bin/, depending on which one PATH finds first) - walk up rather than
        # assume a fixed depth, and stop at the first real bash.exe found.
        for ancestor in Path(git_exe).resolve().parents:
            for candidate in (
                ancestor / "bin" / "bash.exe",
                ancestor / "usr" / "bin" / "bash.exe",
            ):
                if candidate.is_file():
                    return str(candidate)
    return "bash"


BASH = _find_bash()

# Upper bound for one clean-room step. Every step is a short git, harness CLI or hook command; a
# hung step must fail the run and name the command instead of holding CI until the job timeout.
STEP_TIMEOUT_SECONDS = 300

# One clean-room command: a shell string or an argument list.
Command = str | Sequence[str | Path]
JsonReport = dict[str, object]


class StepOptions(TypedDict, total=False):
    """The ``subprocess.run`` options a clean-room step passes through."""

    timeout: float
    check: bool
    capture_output: bool
    text: bool
    encoding: str
    errors: str
    stdin: int | IO[str] | None
    stdout: int | None
    stderr: int | None
    input: str | bytes
    env: Mapping[str, str]
    cwd: Path | None


def run_step(
    cmd: Command, **kwargs: Unpack[StepOptions]
) -> subprocess.CompletedProcess[str]:
    """`subprocess.run` с ограничением времени: зависший шаг завершает прогон с именем команды.

    Остальные аргументы (`check`, `capture_output`, `input`, `env`, `cwd`) передаются без
    изменений, поэтому каждая проверка сохраняет свою семантику; явный `timeout` вызывающего
    кода имеет приоритет над `STEP_TIMEOUT_SECONDS`.
    """
    kwargs.setdefault("timeout", STEP_TIMEOUT_SECONDS)
    try:
        return subprocess.run(cmd, **kwargs)
    except subprocess.TimeoutExpired:
        shown = cmd if isinstance(cmd, str) else subprocess.list2cmdline(map(str, cmd))
        sys.exit(f"clean-room step timed out after {kwargs['timeout']}s: {shown}")


def run_health(repo: Path) -> None:
    """Сохранить полный health-отчёт, вывести счётчики и причины только при ошибке."""
    command = HARNESS + ["health", str(repo), "--json"]
    result = run_step(
        command,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    logs = storage_path(ROOT, "logs")
    logs.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=logs,
        prefix=f"clean-room-health-{repo.name}-",
        suffix=".log",
        delete=False,
    ) as log:
        log.write(
            sanitise(
                f"$ {subprocess.list2cmdline(command)}\nexit_code={result.returncode}\n"
                + result.stdout
                + ("\nstderr:\n" + result.stderr if result.stderr else "")
            )
        )
        log_path = Path(log.name)

    report = None
    code = result.returncode
    try:
        parsed = json.loads(result.stdout)
        summary = "ok={ok} warn={warn} fail={fail} skipped={skipped}".format(
            **parsed["summary"]
        )
        report = parsed
    except (json.JSONDecodeError, KeyError, TypeError):
        summary = "invalid health JSON report"
        code = code or 1
    print(
        f"[health] {repo.name}: {'FAIL' if code else 'PASS'} {summary}; log: {log_path}",
        flush=True,
    )
    if code:
        if report is not None:
            for check in report["checks"]:
                if check["status"] == "fail":
                    print(
                        sanitise(f"{check['id']}: {check['message']}"), file=sys.stderr
                    )
        if result.stderr.strip():
            print(
                sanitise(result.stderr.strip().splitlines()[-1])[:500], file=sys.stderr
            )
        else:
            print(
                f"health command exited with code {code}; full report: {log_path}",
                file=sys.stderr,
            )
        raise SystemExit(code)


def run_ok(cmd: Command, quiet: bool = False, quiet_all: bool = False) -> None:
    """Запустить команду, которая обязана пройти; при сбое завершиться её кодом выхода, как `set -e`."""
    stdout = subprocess.DEVNULL if (quiet or quiet_all) else None
    stderr = subprocess.DEVNULL if quiet_all else None
    # No stdin: started from a terminal, `init` would otherwise prompt for the tracker.
    result = run_step(
        cmd, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, check=False
    )
    if result.returncode != 0:
        sys.exit(result.returncode)


def run_fails(cmd: Command, quiet: bool = False, quiet_all: bool = False) -> bool:
    """Запустить команду, которая должна упасть; вернуть `True`, если она упала."""
    stdout = subprocess.DEVNULL if (quiet or quiet_all) else None
    stderr = subprocess.DEVNULL if quiet_all else None
    result = run_step(cmd, stdout=stdout, stderr=stderr, check=False)
    return result.returncode != 0


def fail_output(cmd: Command) -> str:
    """Запустить команду, которая обязана упасть, и вернуть её stdout и stderr вместе."""
    result = run_step(cmd, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        sys.exit("command unexpectedly succeeded: " + " ".join(map(str, cmd)))
    return str(result.stdout) + str(result.stderr)


def capture(cmd: Command) -> str:
    """Запустить команду, которая обязана пройти, и вернуть её stdout."""
    return str(run_step(cmd, capture_output=True, text=True, check=True).stdout)


def _report(text: str) -> JsonReport:
    report: object = json.loads(text)
    if not isinstance(report, dict):
        sys.exit("health --json output is not a JSON object")
    return report


def fail_json(cmd: Command) -> JsonReport:
    """Запустить `harness health ... --json`, которая обязана упасть, и разобрать её JSON stdout."""
    result = run_step(cmd, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        sys.exit("command unexpectedly succeeded: " + " ".join(map(str, cmd)))
    return _report(result.stdout)


def capture_json(cmd: Command) -> JsonReport:
    """Запустить `harness health ... --json`, которая обязана пройти, и разобрать её JSON stdout."""
    return _report(capture(cmd))


def find_check(report: JsonReport, check_id: str) -> JsonReport:
    """Найти проверку по стабильному `id` в отчёте `harness health --json`."""
    checks = report.get("checks")
    for check in checks if isinstance(checks, list) else []:
        if isinstance(check, dict) and check.get("id") == check_id:
            return check
    sys.exit(f"health --json report has no check with id {check_id!r}")


def commit_map_for(brief: JsonReport, commit_sha: str) -> list[dict[str, object]]:
    """Обязательный `commit_map` отчёта developer для кандидата из одного коммита."""
    plan = brief.get("commit_plan")
    return [
        {"commit_sha": commit_sha, "plan_entry_id": entry["id"]}
        for entry in (plan if isinstance(plan, list) else [])
        if isinstance(entry, dict)
    ]


def fill_agents(repo: Path) -> None:
    """Заменить незаполненные маркеры `{{...}}` в AGENTS.md проекта на `N/A`."""
    agents = repo / "AGENTS.md"
    agents.write_text(
        re.sub(r"{{[^{}\n]+}}", "N/A", agents.read_text(encoding="utf-8")),
        encoding="utf-8",
    )


def count_skill_files(skills_dir: Path) -> int:
    """Число файлов SKILL.md под каталогом скиллов."""
    return sum(1 for p in skills_dir.rglob("SKILL.md") if p.is_file())


def run_hook(
    hook: Path,
    project_dir: Path,
    command: str,
    *,
    raw_payload: str | None = None,
    env_overrides: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Передать PreToolUse(Bash) hook тот же JSON, что отправляет Claude Code, с `CLAUDE_PROJECT_DIR`.

    Так поведение hook проверяется напрямую, а не выводится из файлов, созданных harness.
    """
    payload = (
        raw_payload
        if raw_payload is not None
        else json.dumps({"tool_input": {"command": command}})
    )
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project_dir))
    if env_overrides:
        env.update(env_overrides)
    return run_step(
        [BASH, str(hook)],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
        timeout=10,
        check=False,
    )


def assert_contract_link(doc: Path, contract: Path, label: str) -> None:
    """Проверить, что документ ровно один раз ссылается на контракт и требует прочитать его до handoff."""
    text = doc.read_text(encoding="utf-8")
    links = re.findall(r"\[[^\]]+\]\(([^)]+technical-english\.md)\)", text)
    if len(links) != 1 or (doc.parent / links[0]).resolve() != contract.resolve():
        sys.exit(f"{label} does not reach the shared technical-English contract")
    paragraph = next(
        part for part in text.split("\n\n") if "technical-english.md" in part
    )
    normalized = " ".join(paragraph.split()).lower()
    if "must read" not in normalized or "before" not in normalized:
        sys.exit(f"{label} technical-English reference is not mandatory")


def apply_patch(patch: str, cwd: Path) -> None:
    """Apply a reviewed patch with `git apply`, whatever line ending the target file has.

    A Windows checkout writes CRLF and a seed copy keeps LF, while the patch text is LF; the
    patch is fed as bytes so Python does not translate it, and context lines are matched with
    `--ignore-whitespace`, which also covers a CR before the line end."""
    run_step(
        ["git", "apply", "--ignore-whitespace", "-"],
        input=patch.encode("utf-8"),
        cwd=cwd,
        check=True,
    )


def starts_with_text(data: bytes, text: str) -> bool:
    """True when `data` starts with `text`, whatever line ending the platform wrote it with.

    A fixture written with `write_text` carries CRLF on Windows, while the expected text is LF."""
    return data.replace(b"\r\n", b"\n").startswith(text.encode("utf-8"))


def check_technical_english(project: Path) -> None:
    """Проверить доставку управляемого контракта и достижимость из новых точек входа."""
    contract = project / ".harness/instructions/technical-english.md"
    if not contract.is_file():
        sys.exit("standard install did not deliver the technical-English contract")
    delivered = contract.read_bytes()
    if delivered != (ROOT / "harness/project/instructions/technical-english.md").read_bytes():
        sys.exit("installed technical-English contract differs from its shared source")
    lock = json.loads((project / ".harness/harness.lock").read_text(encoding="utf-8"))
    if (
        lock["files"].get(".harness/instructions/technical-english.md")
        != hashlib.sha256(delivered).hexdigest()
    ):
        sys.exit("technical-English contract is not managed by the snapshot lock")
    if list((project / ".harness").rglob("technical-english.md")) != [contract]:
        sys.exit("installation contains more than one technical-English contract")
    assert_contract_link(project / "AGENTS.md", contract, "AGENTS.md")
    if "@AGENTS.md" not in (project / "CLAUDE.md").read_text(encoding="utf-8"):
        assert_contract_link(project / "CLAUDE.md", contract, "CLAUDE.md")
