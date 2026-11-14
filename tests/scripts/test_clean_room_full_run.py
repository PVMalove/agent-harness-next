"""The clean-room QA stage stays one full run (issue scope: the scenarios are never split).

``scripts/verify.py`` starts ``scripts/test_clean_room.py`` as one command without arguments, and
that script runs the whole ``SCENARIOS`` tuple in order, whatever its argv: no scenario subset can
be selected, whether the stage runs on the host or in a QA container.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from scripts import verify

ROOT = Path(__file__).resolve().parents[2]
# Imported by name, so the type checker does not follow the untyped clean-room scenarios.
test_clean_room = importlib.import_module("scripts.test_clean_room")


def test_the_clean_room_stage_is_one_command_without_a_scenario_selection() -> None:
    assert verify.clean_room_command() == [
        sys.executable,
        str(ROOT / "scripts" / "test_clean_room.py"),
    ]


def test_one_run_executes_the_whole_scenarios_tuple_in_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ran: list[object] = []
    for scenario in test_clean_room.SCENARIOS:

        def record(context: SimpleNamespace, scenario: object = scenario) -> None:
            ran.append(scenario)

        monkeypatch.setattr(scenario, "run", record)
    # A scenario name on the command line selects nothing.
    monkeypatch.setattr(sys, "argv", ["test_clean_room.py", "install_and_update"])
    monkeypatch.setenv("HARNESS_TEST_RUN_ROOT", str(tmp_path))

    test_clean_room.main()

    assert ran == list(test_clean_room.SCENARIOS)
    assert len(set(map(id, ran))) == len(ran)


def _scenario_name(scenario: ModuleType) -> str:
    return scenario.__name__.rpartition(".")[2]


def test_each_scenario_reports_its_duration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for scenario in test_clean_room.SCENARIOS:
        monkeypatch.setattr(scenario, "run", lambda context: None)
    monkeypatch.setenv("HARNESS_TEST_RUN_ROOT", str(tmp_path))

    test_clean_room.main()

    lines = capsys.readouterr().out.splitlines()
    assert [line.partition(": ")[0] for line in lines] == [
        f"[clean-room] {_scenario_name(scenario)}"
        for scenario in test_clean_room.SCENARIOS
    ]
    for line in lines:
        assert re.fullmatch(r"\[clean-room\] \w+: \d+\.\d\d s", line)


def test_a_failed_scenario_reports_how_long_it_ran_and_stops_the_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first, second, *rest = test_clean_room.SCENARIOS

    def fail(context: SimpleNamespace) -> None:
        sys.exit("broken")

    monkeypatch.setattr(first, "run", lambda context: None)
    monkeypatch.setattr(second, "run", fail)
    for scenario in rest:
        monkeypatch.setattr(scenario, "run", lambda context: pytest.fail("ran"))
    monkeypatch.setenv("HARNESS_TEST_RUN_ROOT", str(tmp_path))

    with pytest.raises(SystemExit, match="broken"):
        test_clean_room.main()

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert re.fullmatch(
        rf"\[clean-room\] {_scenario_name(second)}: failed after \d+\.\d\d s",
        lines[1],
    )
