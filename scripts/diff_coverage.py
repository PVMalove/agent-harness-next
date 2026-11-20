#!/usr/bin/env python3
"""Гейт diff-coverage: покрытие тестами изменённых строк Python относительно базовой ветки."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
THRESHOLD_PERCENT = 70.0
MAX_UNCOVERED_LINES = 25
# GitHub shows at most ten warnings of one step: the first ranges are the ones a reviewer sees.
MAX_ANNOTATIONS = 10
BAR_CELLS = 10
COVERAGE_DATA_FILE = ROOT / ".coverage"
COVERAGE_JSON_FILE = ROOT / ".coverage.diff-coverage.json"
# Bound for the helper commands (git, `coverage json`); the measured test run itself is unbounded.
HELPER_TIMEOUT_SECONDS = 300
# `pytest` reports "no tests collected" as exit code 5.
PYTEST_NO_TESTS_COLLECTED = 5
# Verified by the clean-room run (scripts/verify.py), not by the unittest suite this gate measures,
# so their changed lines could never count as covered. The real Docker and Podman smokes run only
# in their own CI job and workflow: the default pytest run this gate measures deselects the
# `docker_smoke` and `podman_smoke` markers.
EXCLUDED_FROM_GATE = frozenset(
    {
        "scripts/test_clean_room.py",
        "tests/orchestration/test_docker_smoke.py",
        "tests/orchestration/test_podman_smoke.py",
        "harness/project/hooks/qa-gate-state.py",
        "harness/project/hooks/tracker-issue.py",
        "harness/project/hooks/pr_commands.py",
        "harness/project/hooks/direct_commits.py",
        "harness/project/hooks/hook_response.py",
        "harness/project/hooks/protect_hook_policy.py",
    }
)
# The clean-room scenarios `scripts/test_clean_room.py` runs, split into their own package.
EXCLUDED_PREFIXES = ("scripts/clean_room/",)


def _base_branch() -> str:
    """Определить базовую ветку проекта из .harness/project.json или вернуть master по умолчанию."""
    project_json = ROOT / ".harness" / "project.json"
    if project_json.is_file():
        try:
            data = json.loads(project_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        branch = data.get("base_branch") if isinstance(data, dict) else None
        if isinstance(branch, str) and branch.strip():
            return branch.strip()
    return "master"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    """Выполнить git в корне репозитория; зависание или сбой запуска git завершает гейт."""
    try:
        return subprocess.run(
            # quotePath off: a quoted non-ASCII path would hide its Python file from the gate.
            ["git", "-C", str(ROOT), "-c", "core.quotePath=false", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            # A diff may hold any bytes (a non-UTF-8 fixture is still text to Git); only the
            # *.py hunks are read, so undecodable bytes elsewhere must not stop the gate.
            errors="surrogateescape",
            check=False,
            timeout=HELPER_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        sys.exit(f"diff-coverage: git {args[0]} failed: {exc}")


def _merge_base() -> str:
    """Вычислить коммит merge-base относительно базовой ветки проекта или переменной окружения."""
    override = os.environ.get("DIFF_COVERAGE_BASE")
    if override:
        return override
    branch = _base_branch()
    for ref in (f"origin/{branch}", branch):
        result = _git("merge-base", "HEAD", ref)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    sys.exit(
        f"diff-coverage: could not resolve a merge-base against {branch!r} or origin/{branch!r}"
    )


_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def _changed_lines(base: str) -> dict[str, set[int]]:
    """Вернуть словарь {относительный_путь: {номера_добавленных_строк}} для изменившихся файлов *.py."""
    diff = _git("diff", "--find-renames", "--unified=0", "--no-color", base)
    if diff.returncode != 0:
        sys.exit(f"diff-coverage: git diff failed: {diff.stderr.strip()}")

    changed: dict[str, set[int]] = {}
    current_path: str | None = None
    next_line = 0
    for line in diff.stdout.splitlines():
        if line.startswith("+++ "):
            path = line[len("+++ ") :]
            path = path.removeprefix("b/")
            is_gated = (
                path.endswith(".py")
                and path not in EXCLUDED_FROM_GATE
                and not path.startswith(EXCLUDED_PREFIXES)
            )
            current_path = path if is_gated else None
            continue
        if line.startswith("@@"):
            match = _HUNK_RE.match(line)
            if match:
                next_line = int(match.group(1))
            continue
        if current_path is None:
            continue
        if line.startswith("+"):
            changed.setdefault(current_path, set()).add(next_line)
            next_line += 1
        elif not line.startswith("-"):
            next_line += 1
    return changed


def _repo_relative(path: str) -> str:
    """Привести путь из отчёта покрытия к относительному пути репозитория с прямыми слешами."""
    normalized = path.replace("\\", "/")
    root_prefix = ROOT.as_posix().rstrip("/") + "/"
    return normalized.removeprefix(root_prefix)


def source_dirs(changed: Mapping[str, set[int]]) -> list[str]:
    """Каталоги изменившихся файлов — источники покрытия (`--cov`) для pytest."""
    return sorted({str(ROOT / Path(rel_path).parent) for rel_path in changed})


def own_tests(changed: Mapping[str, set[int]]) -> list[str]:
    """Тестовые модули среди изменённых файлов под `tests/` — собственные тесты diff.

    Правило то же, что у `ticket_diff_selection`: `test_*.py` или `*_test.py`, без расширения по
    графу импортов (parser bundle в задании покрытия не установлен). Только `tests/`: полный прогон
    не собирает тесты вне него, и их покрытие не должно засчитываться."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from harness.repo_map.change_impact import is_test_path

    return sorted(
        path for path in changed if path.startswith("tests/") and is_test_path(path)
    )


def _pytest(changed: Mapping[str, set[int]], *args: str) -> int:
    """Прогон pytest под coverage с источниками `source_dirs`; код возврата pytest."""
    return subprocess.run(
        [
            sys.executable,
            # pytest, not `unittest discover`: it also collects the function-style tests that
            # unittest silently skips, which left their code counted as uncovered.
            "-m",
            "pytest",
            "-q",
            # xdist workers, as in scripts/verify.py: one process under coverage exceeds the CI
            # job limit. pytest-cov combines the workers' data into COVERAGE_DATA_FILE.
            "-n",
            str(min(4, os.cpu_count() or 1)),
            *(f"--cov={directory}" for directory in source_dirs(changed)),
            "--cov-report=",
            *args,
        ],
        cwd=ROOT,
        check=False,
    ).returncode


def _coverage_files() -> dict[str, Mapping[str, Sequence[int]]] | int:
    """Отчёт по файлам из COVERAGE_DATA_FILE с путями репозитория или код ошибки `coverage json`."""
    try:
        json_run = subprocess.run(
            # --ignore-errors: some tests exec a copy of a module from a temp directory (simulating a
            # deployed .harness/ checkout) that no longer exists by report time -- skip it rather than
            # abort the whole report, since we only care about coverage of files under this repo.
            [
                sys.executable,
                "-m",
                "coverage",
                "json",
                "-o",
                str(COVERAGE_JSON_FILE),
                "-q",
                "--ignore-errors",
            ],
            cwd=ROOT,
            check=False,
            timeout=HELPER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        sys.exit(f"diff-coverage: coverage json failed: {exc}")
    if json_run.returncode != 0:
        return json_run.returncode

    report = json.loads(COVERAGE_JSON_FILE.read_text(encoding="utf-8"))
    # coverage.json keys files by OS-native path (backslashes on Windows); git diff paths are
    # always forward-slash. Normalize both sides to match regardless of platform.
    return {
        _repo_relative(key): value for key, value in report.get("files", {}).items()
    }


def measure(
    changed: Mapping[str, set[int]],
) -> dict[str, Mapping[str, Sequence[int]]] | int:
    """Покрытие изменённых строк: сначала собственные тесты diff, остальной набор — только при нужде.

    Если собственные тесты исполнили каждую изменённую строку-инструкцию, полный прогон дал бы тот же
    отчёт: множество инструкций файла статично, а исполненные строки только добавляются. Иначе
    остальной набор (`tests` без уже прогнанных модулей) дописывается к тем же данным через
    `--cov-append`, и отчёт строится по полному набору, как без выбора. Код ошибки pytest или
    `coverage json` возвращается как есть."""
    COVERAGE_DATA_FILE.unlink(missing_ok=True)
    selected = own_tests(changed)
    if selected:
        code = _pytest(changed, *(str(ROOT / path) for path in selected))
        if code not in (0, PYTEST_NO_TESTS_COLLECTED):
            return code
        if code == 0:
            files = _coverage_files()
            if isinstance(files, int):
                return files
            _, _, uncovered = summarize_coverage(changed, files)
            if not uncovered:
                print(
                    f"diff-coverage: the diff's own {len(selected)} test module(s) cover every "
                    "changed line; the rest of the suite is not run"
                )
                return files
            print(
                f"diff-coverage: {len(uncovered)} changed line(s) not covered by the diff's own "
                "tests; running the rest of the suite"
            )
    code = _pytest(
        changed,
        *(("--cov-append",) if selected else ()),
        *(f"--ignore={ROOT / path}" for path in selected),
        str(ROOT / "tests"),
    )
    if code != 0:
        return code
    return _coverage_files()


def summarize_coverage(
    changed: Mapping[str, set[int]], files: Mapping[str, Mapping[str, Sequence[int]]]
) -> tuple[int, int, list[str]]:
    """Подсчитать число покрытых и непокрытых строк-инструкций среди изменений."""
    total = 0
    covered = 0
    uncovered: list[str] = []
    for rel_path, lines in sorted(changed.items()):
        file_report = files.get(rel_path)
        if file_report is None:
            executed: set[int] = set()
            relevant = set(lines)
        else:
            executed = set(file_report["executed_lines"])
            relevant = lines & (executed | set(file_report["missing_lines"]))
        total += len(relevant)
        for lineno in sorted(relevant):
            if lineno in executed:
                covered += 1
            else:
                uncovered.append(f"{rel_path}:{lineno}")
    return covered, total, uncovered


def meets_threshold(covered: int, total: int) -> bool:
    """Проверить, достигает ли процент покрытия установленного порога."""
    return covered * 100 >= total * THRESHOLD_PERCENT


def compact_uncovered(
    uncovered: Sequence[str], *, max_lines: int = MAX_UNCOVERED_LINES
) -> tuple[list[str], int]:
    """Сформировать компактную сводку непокрытых строк с группировкой по диапазонам."""
    selected = uncovered[:max_lines]
    by_path: dict[str, list[int]] = {}
    for entry in selected:
        path, separator, line_text = entry.rpartition(":")
        if not separator or not line_text.isdecimal():
            raise ValueError(f"invalid uncovered coverage location: {entry!r}")
        by_path.setdefault(path, []).append(int(line_text))

    rendered: list[str] = []
    for path, lines in by_path.items():
        ranges: list[str] = []
        start = previous = lines[0]
        for line_number in lines[1:]:
            if line_number == previous + 1:
                previous = line_number
                continue
            ranges.append(str(start) if start == previous else f"{start}-{previous}")
            start = previous = line_number
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        rendered.append(f"{path}:{', '.join(ranges)}")
    return rendered, len(uncovered) - len(selected)


def bar(percent: float) -> str:
    """A text progress bar of ``percent`` in tenths, as the step summary shows it."""
    filled = min(BAR_CELLS, max(0, round(percent / 100 * BAR_CELLS)))
    return f"`{'█' * filled}{'░' * (BAR_CELLS - filled)}` {percent:.0f}%"


def _ranges(uncovered: Sequence[str]) -> list[tuple[str, int, int]]:
    """Uncovered ``path:line`` locations as consecutive ranges ``(path, first, last)``."""
    ranges: list[tuple[str, int, int]] = []
    for entry in uncovered:
        path, _, line_text = entry.rpartition(":")
        line = int(line_text)
        if ranges and ranges[-1][0] == path and ranges[-1][2] == line - 1:
            ranges[-1] = (path, ranges[-1][1], line)
        else:
            ranges.append((path, line, line))
    return ranges


def render_summary(
    changed: Mapping[str, set[int]], files: Mapping[str, Mapping[str, Sequence[int]]]
) -> str:
    """Compact directory rollup with per-file coverage available in collapsed details."""
    covered, total, _ = summarize_coverage(changed, files)
    percent = 100.0 * covered / total if total else 100.0
    passed = meets_threshold(covered, total)
    verdict = (
        f"порог {THRESHOLD_PERCENT:.0f}% пройден"
        if passed
        else f"ниже порога {THRESHOLD_PERCENT:.0f}%"
    )
    lines = [
        "## diff-coverage",
        "",
        "> [!TIP]" if passed else "> [!WARNING]",
        f"> **{covered}/{total}** изменённых строк покрыто ({percent:.1f}%) — {verdict}.",
        "",
        "| Каталог | Покрытие | Файлы | Непокрытые строки |",
        "|---|---:|---:|---:|",
    ]
    file_rows: list[tuple[str, int, int, list[str]]] = []
    directories: dict[str, list[int]] = {}
    for path in sorted(changed):
        file_covered, file_total, file_uncovered = summarize_coverage(
            {path: changed[path]}, files
        )
        if not file_total:
            continue
        directory = PurePosixPath(path).parent.as_posix()
        totals = directories.setdefault(directory, [0, 0, 0, 0])
        totals[0] += file_covered
        totals[1] += file_total
        totals[2] += 1
        totals[3] += len(file_uncovered)
        file_rows.append((path, file_covered, file_total, file_uncovered))

    for directory, (dir_covered, dir_total, file_count, missing_count) in sorted(
        directories.items()
    ):
        lines.append(
            f"| `{directory}/` | {dir_covered}/{dir_total} "
            f"({100.0 * dir_covered / dir_total:.1f}%) | {file_count} | {missing_count} |"
        )

    if file_rows:
        lines.extend(
            [
                "",
                "<details>",
                f"<summary>Разбивка по файлам ({len(file_rows)})</summary>",
                "",
                "| Файл | Покрыто | Доля | Непокрытые строки |",
                "|---|---:|---|---|",
            ]
        )
    for path, file_covered, file_total, file_uncovered in file_rows:
        missing = ", ".join(
            str(first) if first == last else f"{first}-{last}"
            for _, first, last in _ranges(file_uncovered)
        )
        lines.append(
            f"| `{path}` | {file_covered}/{file_total} "
            f"| {bar(100.0 * file_covered / file_total)} | {missing or '—'} |"
        )
    if file_rows:
        lines.extend(["", "</details>"])
    return "\n".join([*lines, ""])


def uncovered_annotations(uncovered: Sequence[str]) -> list[str]:
    """One workflow command `::warning` per uncovered range: GitHub shows it on those lines in the
    "Files changed" tab of the pull request."""
    commands = []
    for path, first, last in _ranges(uncovered)[:MAX_ANNOTATIONS]:
        message = (
            f"Изменённая строка {first} не покрыта тестами"
            if first == last
            else f"Изменённые строки {first}-{last} не покрыты тестами"
        )
        commands.append(
            f"::warning file={path},line={first},endLine={last},title=diff-coverage::{message}"
        )
    return commands


def publish(
    changed: Mapping[str, set[int]], files: Mapping[str, Mapping[str, Sequence[int]]]
) -> None:
    """The step summary and the line annotations of a GitHub Actions run; nothing elsewhere."""
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(render_summary(changed, files))
    if os.environ.get("GITHUB_ACTIONS") == "true":
        _, _, uncovered = summarize_coverage(changed, files)
        for command in uncovered_annotations(uncovered):
            print(command)


def main() -> int:
    """Точка входа CLI: запуск coverage, анализ диффа и проверка порога покрытия."""
    os.environ["PYTHONPATH"] = str(ROOT)
    base = _merge_base()
    changed = _changed_lines(base)
    if not changed:
        print(f"diff-coverage: no changed Python lines since {base}")
        return 0

    files = measure(changed)
    if isinstance(files, int):
        return files
    COVERAGE_DATA_FILE.unlink(missing_ok=True)
    COVERAGE_JSON_FILE.unlink(missing_ok=True)

    total_covered, total_changed, uncovered = summarize_coverage(changed, files)

    if total_changed == 0:
        print(f"diff-coverage: no coverable changed lines since {base}")
        return 0

    publish(changed, files)
    percent = 100.0 * total_covered / total_changed
    print(
        f"diff-coverage: {total_covered}/{total_changed} changed lines covered ({percent:.1f}%)"
    )
    if not meets_threshold(total_covered, total_changed):
        compact, omitted = compact_uncovered(uncovered)
        print(
            f"diff-coverage: below the {THRESHOLD_PERCENT:.0f}% threshold; "
            f"uncovered changed lines (showing {len(uncovered) - omitted}/{len(uncovered)}):"
        )
        for entry in compact:
            print(f"  {entry}")
        if omitted:
            print(f"  … and {omitted} more uncovered changed lines")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
