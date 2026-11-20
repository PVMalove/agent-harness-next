"""scripts/ci_summary.py: the Markdown the CI run page shows."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import ci_summary

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="4" time="125.5">
<testcase classname="tests.a" name="test_ok" time="0.5"/>
<testcase classname="tests.a" name="test_slow" time="42.0"/>
<testcase classname="tests.b" name="test_bad" time="1.0">
<failure message="AssertionError: 1 == 2&#10;more">trace</failure></testcase>
<testcase classname="tests.b" name="test_skip" time="0"><skipped message="x"/></testcase>
</testsuite></testsuites>
"""


def _report(tmp_path: Path, name: str = "junit-verify.xml") -> ci_summary.Report:
    path = tmp_path / name
    path.write_text(JUNIT, encoding="utf-8")
    return ci_summary.read_report(path)


def test_a_junit_file_becomes_counts_failures_and_the_slowest_tests(
    tmp_path: Path,
) -> None:
    report = _report(tmp_path)
    assert report.title == "verify"
    assert [report.count(o) for o in ("passed", "failed", "skipped")] == [2, 1, 1]
    text = ci_summary.render_tests(report)
    assert "❌ есть падения" in text
    assert "| 4 | 2 | 1 | 1 | 2 мин 05 с |" in text
    assert "`tests.b::test_bad` | AssertionError: 1 == 2" in text
    assert "`tests.a::test_slow` | 42.0 с" in text


def test_a_missing_report_is_said_not_hidden(tmp_path: Path) -> None:
    report = ci_summary.read_report(tmp_path / "junit-missing.xml")
    assert "Отчёт pytest не найден" in ci_summary.render_tests(report)


def test_the_dashboard_lists_jobs_failures_and_the_way_to_repeat(
    tmp_path: Path,
) -> None:
    jobs = ci_summary._load_jobs(
        '{"verify": {"result": "success"}, "verify-windows": {"result": "failure"}}'
    )
    text = ci_summary.render_dashboard([_report(tmp_path)], jobs, "https://example/run")
    assert "❌ **Есть падения:** `verify-windows`" in text
    assert "| `verify` | ✅ success |" in text
    assert "### Все упавшие тесты" in text and "test_bad" in text
    assert "[Запуск и полные журналы](https://example/run)" in text


def test_a_clean_run_says_so(tmp_path: Path) -> None:
    text = ci_summary.render_dashboard([], {"verify": "success"})
    assert "✅ **Все задания прошли**" in text


def test_the_command_line_writes_markdown(
    tmp_path: Path, capsys: "pytest.CaptureFixture[str]"
) -> None:
    (tmp_path / "junit-windows.xml").write_text(JUNIT, encoding="utf-8")
    assert (
        ci_summary.main(
            ["dashboard", "--junit-dir", str(tmp_path), "--needs-json", "{}"]
        )
        == 0
    )
    assert "windows" in capsys.readouterr().out
    assert ci_summary.main(["tests", str(tmp_path / "junit-windows.xml")]) == 0


def test_the_summary_survives_a_console_that_cannot_encode_cyrillic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io
    import sys

    path = tmp_path / "junit-windows.xml"
    path.write_text(JUNIT, encoding="utf-8")
    raw = io.BytesIO()
    console = io.TextIOWrapper(raw, encoding="cp1252", write_through=True)
    monkeypatch.setattr(sys, "stdout", console)
    assert ci_summary.main(["tests", str(path), "--title", "Windows: тесты"]) == 0
    assert "Windows: тесты" in raw.getvalue().decode("utf-8")


TRACEBACK_JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="3" time="3">
<testcase classname="tests.b" name="test_ok" time="1"/>
<testcase classname="tests.b.Suite" name="test_bad" time="1">
<failure message="AssertionError: assert 1 == 2">def test_bad(self):
&gt;       assert 1 == 2
E       AssertionError: assert 1 == 2

tests{sep}b.py:7: AssertionError</failure></testcase>
<testcase classname="tests.b" name="test_skip" time="0"><skipped message="x"/></testcase>
</testsuite></testsuites>
"""


def _traced(tmp_path: Path, sep: str = "/") -> ci_summary.Report:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "b.py").write_text("", encoding="utf-8")
    path = tmp_path / "junit-verify.xml"
    path.write_text(TRACEBACK_JUNIT.replace("{sep}", sep), encoding="utf-8")
    return ci_summary.read_report(path, root=tmp_path)


@pytest.mark.parametrize("sep", ["/", "\\"])
def test_a_failure_knows_its_node_id_and_the_line_where_it_failed(
    tmp_path: Path, sep: str
) -> None:
    [failure] = _traced(tmp_path, sep).failed
    assert failure.nodeid == "tests/b.py::Suite::test_bad"
    assert (failure.file, failure.line) == ("tests/b.py", 7)


def test_a_failed_test_shows_its_traceback_folded_and_how_to_repeat_it(
    tmp_path: Path,
) -> None:
    text = ci_summary.render_tests(_traced(tmp_path))
    assert "> [!WARNING]" in text
    assert "> [!TIP]" in text
    assert "pytest 'tests/b.py::Suite::test_bad'" in text
    assert "<details><summary><code>tests/b.py::Suite::test_bad</code>" in text
    assert "E       AssertionError: assert 1 == 2" in text


def test_the_dashboard_draws_the_test_outcomes_as_a_pie(tmp_path: Path) -> None:
    text = ci_summary.render_dashboard([_traced(tmp_path)], {"verify": "failure"})
    assert "```mermaid\npie title" in text
    assert '"Прошло" : 1' in text and '"Упало" : 1' in text
    assert '"Пропущено" : 1' in text
    assert "> [!CAUTION]" in text


def test_a_clean_dashboard_draws_no_alert(tmp_path: Path) -> None:
    text = ci_summary.render_dashboard([], {"verify": "success"})
    assert "[!CAUTION]" not in text and "```mermaid" not in text


def test_annotations_point_at_the_failed_line(
    tmp_path: Path, capsys: "pytest.CaptureFixture[str]"
) -> None:
    _traced(tmp_path)
    assert (
        ci_summary.main(
            ["annotate", str(tmp_path / "junit-verify.xml"), "--root", str(tmp_path)]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert out == (
        "::error file=tests/b.py,line=7,title=tests/b.py%3A%3ASuite%3A%3Atest_bad"
        "::AssertionError: assert 1 == 2\n"
    )


def test_an_annotation_escapes_what_the_workflow_command_reserves() -> None:
    assert ci_summary.escape_data("50% done\r\nnext") == "50%25 done%0D%0Anext"
    assert ci_summary.escape_property("a:b,c") == "a%3Ab%2Cc"


CLIPPY = (
    '{"reason":"compiler-artifact","target":{"name":"state"}}\n'
    '{"reason":"compiler-message","message":{"level":"error","message":"unused import: `Foo`",'
    '"code":{"code":"unused_imports"},"rendered":"error: unused import: `Foo`\\n --> src/a.rs:3:5\\n",'
    '"spans":[{"file_name":"crates/state/src/a.rs","line_start":3,"line_end":3,'
    '"column_start":5,"column_end":8,"is_primary":true}]}}\n'
    '{"reason":"compiler-message","message":{"level":"warning","message":"1 warning emitted",'
    '"code":null,"rendered":"warning: 1 warning emitted\\n","spans":[]}}\n'
)


def test_clippy_messages_become_log_lines_and_annotations_on_their_lines(
    monkeypatch: pytest.MonkeyPatch, capsys: "pytest.CaptureFixture[str]"
) -> None:
    import io
    import sys

    monkeypatch.setattr(sys, "stdin", io.StringIO(CLIPPY))
    assert ci_summary.main(["clippy", "--prefix", "native/harness-runtime"]) == 0
    out = capsys.readouterr().out
    assert "error: unused import: `Foo`\n --> src/a.rs:3:5\n" in out
    assert (
        "::error file=native/harness-runtime/crates/state/src/a.rs,line=3,endLine=3,"
        "col=5,endColumn=8,title=clippy unused_imports::unused import: `Foo`\n"
    ) in out
    assert "::warning" not in out  # a message without a span stays a log line only
