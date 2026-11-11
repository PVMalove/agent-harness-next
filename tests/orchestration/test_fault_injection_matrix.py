"""The registry of the fault-injection matrix, its markers and its strict mode (#813).

The registry names exactly the scenarios of the ticket; each registered test exists and carries the
``fault_injection`` marker, and no other test does. pyproject.toml registers the marker without
deselecting it, so every default run keeps the matrix, and no rerun plugin is a dependency. With
``HARNESS_REQUIRE_FAULT_INJECTION=1`` a skipped scenario fails, and a run that misses a registered
scenario ends before any test runs.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from tests.orchestration.fault_injection_matrix import (
    MARKER,
    REQUIRE_ENV,
    SCENARIOS,
    Scenario,
    registry_problems,
)

ROOT = Path(__file__).resolve().parents[2]

# Definition of Done items 2 and 3 of #813: the reliability matrix of #784, then the security
# boundaries the ticket names. The container cases of the runtime SIGKILL come from #1057.
EXPECTED_LABELS = [
    "SIGKILL of the coordinator",
    "SIGKILL of the runtime",
    "SIGKILL of the runtime: running container adopted",
    "lost IPC reply",
    "orphan worker",
    "double start",
    "PID reuse",
    "stale lease",
    "partial artifact",
    "OCI image mismatch",
    "SELinux EPERM",
    "offline dependency install",
    "conflicting batches",
    "tampered audit record",
    "engine socket in a mount",
    "foreign lease release",
]
RERUN_PLUGINS = {"pytest-rerunfailures", "flaky", "pytest-retry"}


def _is_marker(node: ast.expr) -> bool:
    return ast.unparse(node) == f"pytest.mark.{MARKER}"


def _marked_nodeids() -> set[str]:
    """Every test, class or module below tests/ that carries the marker, as a node id."""
    found: set[str] = set()
    for path in sorted((ROOT / "tests").rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                if any(_is_marker(decorator) for decorator in node.decorator_list):
                    found.add(f"{relative}::{node.name}")
            elif isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "pytestmark"
                for target in node.targets
            ):
                if MARKER in ast.unparse(node.value):
                    found.add(relative)
    return found


def test_the_registry_names_exactly_the_matrix_scenarios_and_the_security_boundaries() -> None:
    assert [scenario.label for scenario in SCENARIOS] == EXPECTED_LABELS
    nodeids = [scenario.nodeid for scenario in SCENARIOS]
    assert len(set(nodeids)) == len(nodeids)


def test_every_registered_test_exists_and_carries_the_marker() -> None:
    for scenario in SCENARIOS:
        path, name = scenario.nodeid.split("::")
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        functions = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
        assert len(functions) == 1, scenario.nodeid
        assert any(_is_marker(d) for d in functions[0].decorator_list), scenario.nodeid


def test_no_unregistered_test_carries_the_marker() -> None:
    assert _marked_nodeids() == {scenario.nodeid for scenario in SCENARIOS}


def test_pyproject_registers_the_marker_and_never_deselects_it() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    options = config["tool"]["pytest"]["ini_options"]

    assert any(str(marker).startswith(f"{MARKER}:") for marker in options["markers"])
    assert MARKER not in " ".join(options["addopts"])


def test_no_rerun_plugin_is_a_dependency_or_locked() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))

    dev = {
        re.split(r"[\s=<>!~;\[]", str(item), maxsplit=1)[0].lower()
        for item in config["dependency-groups"]["dev"]
    }
    locked = {str(package["name"]).lower() for package in lock["package"]}
    assert dev and locked
    assert RERUN_PLUGINS & dev == set()
    assert RERUN_PLUGINS & locked == set()


def test_the_registry_check_ignores_parameters_and_names_a_missing_and_an_extra_test() -> None:
    scenarios = [Scenario("one", "t.py::test_one"), Scenario("two", "t.py::test_two")]

    matched = registry_problems(
        ["t.py::test_one[a]", "t.py::test_one[b]", "t.py::test_two"], scenarios
    )
    problems = registry_problems(["t.py::test_one", "t.py::test_three"], scenarios)

    assert matched == []
    assert len(problems) == 2
    assert "'two'" in problems[0] and "t.py::test_two" in problems[0]
    assert "t.py::test_three" in problems[1]


PROBE = """\
import pytest


@pytest.mark.fault_injection
def test_marked():
    pytest.skip("the runtime binary is missing")
"""

# The hooks of the repository's conftest over a registry of the probe's own scenarios.
STRICT_CONFTEST = """\
from tests.orchestration import fault_injection_matrix
from tests.orchestration.conftest import (
    pytest_collection_finish as pytest_collection_finish,
    pytest_runtest_makereport as pytest_runtest_makereport,
)

fault_injection_matrix.SCENARIOS = tuple(
    fault_injection_matrix.Scenario(label, nodeid) for label, nodeid in {scenarios!r}
)
"""


def _probe_run(
    tmp_path: Path, scenarios: list[tuple[str, str]], *, required: bool
) -> subprocess.CompletedProcess[str]:
    """One pytest run of the probe under the repository's configuration and the strict hooks."""
    probe = tmp_path / "test_probe.py"
    probe.write_text(PROBE, encoding="utf-8")
    (tmp_path / "conftest.py").write_text(
        STRICT_CONFTEST.format(scenarios=scenarios), encoding="utf-8"
    )
    environ = {name: value for name, value in os.environ.items() if name != REQUIRE_ENV}
    if required:
        environ[REQUIRE_ENV] = "1"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            str(ROOT / "pyproject.toml"),
            "--rootdir",
            str(tmp_path),
            "-p",
            "no:cacheprovider",
            str(probe),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        env={**environ, "PYTHONPATH": str(ROOT)},
    )


def test_the_strict_mode_fails_a_skipped_scenario_and_without_it_the_skip_stays(
    tmp_path: Path,
) -> None:
    scenarios = [("a probe scenario", "test_probe.py::test_marked")]

    strict = _probe_run(tmp_path, scenarios, required=True)
    relaxed = _probe_run(tmp_path, scenarios, required=False)

    assert strict.returncode == pytest.ExitCode.TESTS_FAILED, strict.stdout + strict.stderr
    assert "1 failed" in strict.stdout
    assert "a scenario of the fault-injection matrix may not skip" in strict.stdout
    assert "the runtime binary is missing" in strict.stdout
    assert relaxed.returncode == pytest.ExitCode.OK, relaxed.stdout + relaxed.stderr
    assert "1 skipped" in relaxed.stdout


def test_the_strict_mode_ends_a_run_that_misses_a_registered_scenario(
    tmp_path: Path,
) -> None:
    scenarios = [
        ("a probe scenario", "test_probe.py::test_marked"),
        ("a removed scenario", "test_probe.py::test_removed"),
    ]

    strict = _probe_run(tmp_path, scenarios, required=True)

    output = strict.stdout + strict.stderr
    assert strict.returncode == pytest.ExitCode.TESTS_FAILED, output
    assert "'a removed scenario' has no selected test test_probe.py::test_removed" in output
    assert "may not skip" not in output
