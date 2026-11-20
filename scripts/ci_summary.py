#!/usr/bin/env python3
"""Сводка CI для страницы запуска GitHub Actions: результаты pytest и общий дашборд.

`tests` превращает JUnit XML одного задания в Markdown: итоги, упавшие тесты с причиной, свёрнутым
traceback и командой повтора, самые медленные тесты. `dashboard` собирает все отчёты запуска и
результаты заданий на одну страницу: что прошло, что упало, где именно и сколько это заняло.
`annotate` печатает команды workflow `::error`, и GitHub показывает упавший тест на его строке во
вкладке «Files changed»; `clippy` делает то же для JSON-сообщений `cargo clippy --message-format=json`. Скрипт использует только стандартную библиотеку и пишет в stdout; workflow
добавляет Markdown в `$GITHUB_STEP_SUMMARY`."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

SLOWEST = 10
MESSAGE_CHARS = 300
# The tail of a traceback the summary folds under its test: the end names the failed line.
DETAILS_CHARS = 6000
# The tests one repeat command names; more would not fit a terminal line anyone copies.
REPEATED = 20
# `path/to/test.py:42: AssertionError`, the location pytest prints at the end of a failure.
LOCATION = re.compile(r"^(?P<path>[^\s:]+\.py):(?P<line>\d+): ", re.MULTILINE)
ICONS = {
    "success": "✅",
    "failure": "❌",
    "cancelled": "🚫",
    "skipped": "⏭️",
    "passed": "✅",
    "failed": "❌",
}


@dataclass
class TestResult:
    name: str
    seconds: float
    outcome: str  # passed, failed, skipped
    message: str = ""
    details: str = ""
    # The pytest node id, and the file and line where the test failed, when the report names them.
    nodeid: str = ""
    file: str = ""
    line: int = 0

    @property
    def label(self) -> str:
        return self.nodeid or self.name


@dataclass
class Report:
    """The results of one pytest run (one JUnit file)."""

    title: str
    results: list[TestResult] = field(default_factory=list)
    seconds: float = 0.0

    def count(self, outcome: str) -> int:
        return sum(1 for result in self.results if result.outcome == outcome)

    @property
    def failed(self) -> list[TestResult]:
        return [result for result in self.results if result.outcome == "failed"]


def _first_line(text: str) -> str:
    for line in text.strip().splitlines():
        if line.strip():
            return line.strip()[:MESSAGE_CHARS]
    return ""


def _module_file(dotted: list[str], root: Path) -> tuple[str, list[str]] | None:
    """The longest dotted prefix that is a Python file under ``root``, and the remaining parts."""
    for length in range(len(dotted), 0, -1):
        relative = "/".join(dotted[:length]) + ".py"
        if (root / relative).is_file():
            return relative, dotted[length:]
    return None


def _nodeid(classname: str, name: str, root: Path) -> str:
    """The pytest node id of a JUnit case, or "" when its module is not a file under ``root``."""
    found = _module_file(classname.split("."), root) if classname else None
    if found is None:
        return ""
    module, classes = found
    return "::".join([module, *classes, name])


def _location(text: str, module: str) -> tuple[str, int]:
    """The file and line where a failure happened: the last location in its own test module, else
    the last location the traceback names."""
    found = [
        (match["path"].replace("\\", "/"), int(match["line"]))
        for match in LOCATION.finditer(text)
    ]
    own = [place for place in found if place[0] == module]
    return (own or found or [("", 0)])[-1]


def read_report(
    path: Path, title: str | None = None, root: Path | None = None
) -> Report:
    """Parse one JUnit XML file; a missing or broken file is an empty report named in `title`.

    ``root`` is the checkout the tests ran in (the current directory by default): it turns a
    case into its pytest node id."""
    root = root or Path.cwd()
    report = Report(title or path.stem.removeprefix("junit-"))
    try:
        document = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return report
    suites = (
        [document] if document.tag == "testsuite" else list(document.iter("testsuite"))
    )
    for suite in suites:
        report.seconds += float(suite.get("time") or 0)
        for case in suite.iter("testcase"):
            name = f"{case.get('classname', '')}::{case.get('name', '')}".strip(":")
            seconds = float(case.get("time") or 0)
            problem = case.find("failure")
            if problem is None:
                problem = case.find("error")
            skipped = case.find("skipped")
            if problem is not None:
                message = problem.get("message") or problem.text or ""
                details = problem.text or message
                nodeid = _nodeid(case.get("classname", ""), case.get("name", ""), root)
                file, line = _location(details, nodeid.split("::", 1)[0])
                report.results.append(
                    TestResult(
                        name,
                        seconds,
                        "failed",
                        _first_line(message),
                        details.strip(),
                        nodeid,
                        file,
                        line,
                    )
                )
            elif skipped is not None:
                report.results.append(TestResult(name, seconds, "skipped"))
            else:
                report.results.append(TestResult(name, seconds, "passed"))
    return report


def _minutes(seconds: float) -> str:
    return (
        f"{int(seconds // 60)} мин {int(seconds % 60):02d} с"
        if seconds >= 60
        else f"{seconds:.0f} с"
    )


def _escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def escape_data(text: str) -> str:
    """The message of a workflow command, as GitHub reads it."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(text: str) -> str:
    """A property (`file`, `title`) of a workflow command, as GitHub reads it."""
    return escape_data(text).replace(":", "%3A").replace(",", "%2C")


def _fenced(text: str) -> str:
    """``text`` in a code fence longer than any backtick run inside it."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{text}\n{fence}"


def _folded(result: TestResult) -> list[str]:
    """One failed test, its traceback folded under its name."""
    details = result.details or result.message or "—"
    if len(details) > DETAILS_CHARS:
        details = "…\n" + details[-DETAILS_CHARS:]
    where = f" — {result.file}:{result.line}" if result.file else ""
    return [
        f"<details><summary><code>{html.escape(result.label)}</code>{html.escape(where)}"
        "</summary>",
        "",
        _fenced(details),
        "",
        "</details>",
        "",
    ]


def _repeat(failed: list[TestResult]) -> list[str]:
    """A GitHub tip with the command that repeats the failed tests locally."""
    ids = [result.nodeid for result in failed if result.nodeid][:REPEATED]
    if not ids:
        return [
            "> [!TIP]",
            "> Повторить локально: `make verify`; в CI упавшие тесты запускаются первыми.",
            "",
        ]
    quoted = " ".join(f"'{nodeid}'" for nodeid in ids)
    return [
        "> [!TIP]",
        "> Повторить упавшие тесты локально:",
        ">",
        "> ```bash",
        f"> .harness/.venv/bin/python -m pytest {quoted}",
        "> ```",
        "",
    ]


def _failures(failed: list[TestResult]) -> list[str]:
    """The failed tests of a report: a warning, how to repeat them and each traceback folded."""
    lines = [
        "> [!WARNING]",
        f"> Упало тестов: {len(failed)}. Traceback каждого свёрнут ниже.",
        "",
        *_repeat(failed),
    ]
    for result in failed:
        lines += _folded(result)
    return lines


def render_tests(report: Report) -> str:
    """Markdown for one pytest run."""
    verdict = "❌ есть падения" if report.failed else "✅ всё прошло"
    lines = [
        f"### {report.title}: {verdict}",
        "",
        "| Тестов | Прошло | Упало | Пропущено | Время тестов (сумма по воркерам) |",
        "|---:|---:|---:|---:|---:|",
        f"| {len(report.results)} | {report.count('passed')} | {report.count('failed')} "
        f"| {report.count('skipped')} | {_minutes(report.seconds)} |",
        "",
    ]
    if not report.results:
        lines += [
            "_Отчёт pytest не найден: прогон остановился до тестов или упал раньше._",
            "",
        ]
    if report.failed:
        lines += ["#### Упавшие тесты", "", "| Тест | Причина |", "|---|---|"]
        lines += [
            f"| `{_escape(result.label)}` | {_escape(result.message) or '—'} |"
            for result in report.failed
        ]
        lines.append("")
        lines += _failures(report.failed)
    slow = sorted(report.results, key=lambda result: -result.seconds)[:SLOWEST]
    if slow and slow[0].seconds >= 1:
        lines += [
            "<details><summary>Самые медленные тесты</summary>",
            "",
            "| Тест | Время |",
            "|---|---:|",
        ]
        lines += [
            f"| `{_escape(result.name)}` | {result.seconds:.1f} с |" for result in slow
        ]
        lines += ["", "</details>", ""]
    return "\n".join(lines)


def render_dashboard(
    reports: list[Report], jobs: dict[str, str], run_url: str | None = None
) -> str:
    """One page for the whole run: job results, tests per job, every failed test."""
    failed_jobs = [name for name, result in jobs.items() if result == "failure"]
    lines = [
        "## Дашборд проверки",
        "",
        *(
            [
                "> [!CAUTION]",
                "> ❌ **Есть падения:** "
                + ", ".join(f"`{name}`" for name in failed_jobs),
            ]
            if failed_jobs
            else ["✅ **Все задания прошли**"]
        ),
        "",
        "### Задания",
        "",
        "| Задание | Результат |",
        "|---|---|",
    ]
    lines += [
        f"| `{name}` | {ICONS.get(result, '❔')} {result} |"
        for name, result in jobs.items()
    ]
    lines.append("")
    outcomes = {
        label: sum(report.count(outcome) for report in reports)
        for label, outcome in (
            ("Прошло", "passed"),
            ("Упало", "failed"),
            ("Пропущено", "skipped"),
        )
    }
    if any(outcomes.values()):
        lines += [
            "```mermaid",
            f"pie title Тесты запуска: {sum(outcomes.values())}",
            *(f'    "{label}" : {count}' for label, count in outcomes.items()),
            "```",
            "",
        ]
    if reports:
        lines += [
            "### Тесты по заданиям",
            "",
            "| Задание | Тестов | Прошло | Упало | Пропущено | Время тестов (сумма по воркерам) |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for report in reports:
            icon = "❌" if report.failed else "✅"
            lines.append(
                f"| {icon} {report.title} | {len(report.results)} | {report.count('passed')} "
                f"| {report.count('failed')} | {report.count('skipped')} | {_minutes(report.seconds)} |"
            )
        lines.append("")
    failures = [
        (report.title, result) for report in reports for result in report.failed
    ]
    if failures:
        lines += [
            "### Все упавшие тесты",
            "",
            "| Задание | Тест | Причина |",
            "|---|---|---|",
        ]
        lines += [
            f"| {title} | `{_escape(result.label)}` | {_escape(result.message) or '—'} |"
            for title, result in failures
        ]
        lines.append("")
        lines += _failures([result for _, result in failures])
    if run_url:
        lines += [f"[Запуск и полные журналы]({run_url})", ""]
    return "\n".join(lines)


def failure_annotations(report: Report) -> list[str]:
    """One workflow command `::error` per failed test, on its line when the report names it."""
    commands = []
    for result in report.failed:
        where = (
            f"file={escape_property(result.file)},line={result.line},"
            if result.file
            else ""
        )
        commands.append(
            f"::error {where}title={escape_property(result.label)}"
            f"::{escape_data(result.message or 'failed')}"
        )
    return commands


def clippy_lines(lines: Iterable[str], prefix: str = "") -> Iterator[str]:
    """The log and the annotations of `cargo clippy --message-format=json`: each compiler message
    as cargo would print it, then `::error` or `::warning` on its primary span. ``prefix`` is the
    workspace directory: span paths are relative to it, annotation paths to the repository."""
    for raw in lines:
        try:
            event = json.loads(raw)
        except ValueError:
            yield raw.rstrip("\n")
            continue
        if not isinstance(event, dict) or event.get("reason") != "compiler-message":
            continue
        message = event.get("message") or {}
        rendered = str(message.get("rendered") or "").rstrip("\n")
        if rendered:
            yield rendered
        level = message.get("level")
        primary = next(
            (span for span in message.get("spans") or [] if span.get("is_primary")),
            None,
        )
        if level not in {"error", "warning"} or primary is None:
            continue
        path = "/".join(part for part in (prefix.rstrip("/"), primary["file_name"]) if part)
        code = (message.get("code") or {}).get("code") or level
        yield (
            f"::{level} file={escape_property(path)},line={primary['line_start']},"
            f"endLine={primary['line_end']},col={primary['column_start']},"
            f"endColumn={primary['column_end']},title={escape_property(f'clippy {code}')}"
            f"::{escape_data(str(message.get('message', '')))}"
        )


def _load_jobs(raw: str) -> dict[str, str]:
    """`needs` of a workflow as JSON ({job: {result: ...}}) -> {job: result}."""
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return {
        str(name): str(value.get("result", "unknown"))
        for name, value in data.items()
        if isinstance(value, dict)
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0] if __doc__ else None
    )
    commands = parser.add_subparsers(dest="command", required=True)
    tests = commands.add_parser("tests", help="Markdown for JUnit XML files")
    tests.add_argument("junit", nargs="+", type=Path)
    tests.add_argument("--title")
    tests.add_argument("--root", type=Path, help="the checkout the tests ran in")
    annotate = commands.add_parser(
        "annotate", help="workflow commands `::error` for the failed tests"
    )
    annotate.add_argument("junit", nargs="+", type=Path)
    annotate.add_argument("--root", type=Path, help="the checkout the tests ran in")
    clippy = commands.add_parser(
        "clippy", help="log and annotations of `cargo clippy --message-format=json` on stdin"
    )
    clippy.add_argument("--prefix", default="", help="the workspace directory")
    dashboard = commands.add_parser("dashboard", help="one page for the whole run")
    dashboard.add_argument("--junit-dir", type=Path, required=True)
    dashboard.add_argument("--needs-json", default="{}", help="JSON of `needs`")
    dashboard.add_argument("--run-url")
    dashboard.add_argument("--root", type=Path, help="the checkout the tests ran in")
    args = parser.parse_args(argv)
    # The summary has Cyrillic and emoji; a Windows console or pipe defaults to cp1252.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")
    if args.command == "tests":
        for path in args.junit:
            print(render_tests(read_report(path, args.title, args.root)))
        return 0
    if args.command == "clippy":
        for line in clippy_lines(sys.stdin, args.prefix):
            print(line, flush=True)
        return 0
    if args.command == "annotate":
        for path in args.junit:
            for command in failure_annotations(read_report(path, root=args.root)):
                print(command)
        return 0
    reports = [
        read_report(path, root=args.root)
        for path in sorted(args.junit_dir.rglob("junit-*.xml"))
    ]
    print(render_dashboard(reports, _load_jobs(args.needs_json), args.run_url))
    return 0


if __name__ == "__main__":
    sys.exit(main())
