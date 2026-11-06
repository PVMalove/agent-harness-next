"""The recovery regression suite on the Rust runtime store (#685, ADR 0026 section 1).

The registry in ``recovery_regression_matrix.py`` names one test per scenario of the ticket; the
meta-tests here keep it closed and existing. The end-to-end tests below cover the scenarios no
other test proves: an accepted stage survives a later failure, an invalid configuration and a
runtime restart, and ``recovery resume`` continues to the next stage instead of rerunning it.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness.json_types import JsonObject as Document
from tests.orchestration.recovery_regression_matrix import (
    LABELS,
    SCENARIOS,
    Scenario,
    registry_problems,
)
from tests.orchestration.runtime_store_support import (
    APPROVAL,
    Recovery,
    ServingRuntime,
)

seam = pytest.mark.skipif(
    sys.platform == "win32", reason="the seam tests drive a Unix-socket runtime"
)
APPROVED = (
    "--approved-by",
    APPROVAL["approved_by"],
    "--approved-at",
    APPROVAL["approved_at"],
)


# -- the registry --------------------------------------------------------------------------------


def test_the_registry_is_the_closed_list_of_existing_tests() -> None:
    assert registry_problems(SCENARIOS, LABELS) == []


def test_a_missing_label_an_unknown_test_and_an_extra_label_are_problems() -> None:
    broken = (
        *SCENARIOS[1:],
        Scenario("extra", "tests/orchestration/test_recovery_commands.py::test_absent"),
    )

    problems = registry_problems(broken, LABELS)

    assert f"no scenario for {SCENARIOS[0].label!r}" in problems
    assert "the scenario 'extra' is outside the closed list" in problems
    assert (
        "tests/orchestration/test_recovery_commands.py::test_absent: "
        "tests/orchestration/test_recovery_commands.py has no test test_absent"
    ) in problems


def test_a_class_node_id_and_a_missing_file_are_problems() -> None:
    broken = (
        Scenario(LABELS[0], "tests/orchestration/test_recovery.py::Case::test_x"),
        Scenario(LABELS[1], "tests/orchestration/test_absent.py::test_x"),
    )

    problems = registry_problems(broken, LABELS[:2])

    assert problems == [
        "tests/orchestration/test_recovery.py::Case::test_x is not a module-level test node id",
        "tests/orchestration/test_absent.py::test_x: "
        "tests/orchestration/test_absent.py does not exist",
    ]


# -- an accepted stage is never rerun ------------------------------------------------------------


@pytest.fixture
def accepted(tmp_path: Path) -> Iterator[Recovery]:
    """A cut-over batch whose architect stage reported and was accepted: the next is developer."""
    found = Recovery(tmp_path, report=True)
    try:
        result = found.cli(
            "batch", "decide", "--batch", found.batch, "--decision", "accept", *APPROVED
        )
        assert result.returncode == 0, result.stderr
        yield found
    finally:
        found.stop()


def _status_path(recovery: Recovery) -> str:
    return f"dispatch-status/{recovery.dispatch}.json"


def _dispatches(recovery: Recovery) -> list[Document]:
    result = recovery.cli("dispatch", "status", "--batch", recovery.batch)
    assert result.returncode == 0, result.stderr
    dispatches = json.loads(result.stdout)["dispatches"]
    assert isinstance(dispatches, list)
    return dispatches


def _assert_continues_to_the_developer(
    recovery: Recovery, document: Document | None
) -> None:
    assert document is not None and document["outcome"] == "done"
    assert (document["dispatch_created"], document["worker_started"]) == (False, False)
    assert document["next"]["command"] == (
        f"dispatch propose --batch {recovery.batch} --role developer"
    )
    assert [
        (item["dispatch_id"], item["role"], item["state"])
        for item in _dispatches(recovery)
    ] == [(recovery.dispatch, "architect", "reported")]


@seam
def test_a_failure_after_an_accepted_stage_resumes_to_the_next_stage_only(
    accepted: Recovery,
) -> None:
    path = _status_path(accepted)
    stage = accepted.records(path)[path]
    revision = accepted.revisions(path)[path]
    accepted.hold("unknown-value", "the developer step failed")

    result, document = accepted.recovery("resume")

    assert result.returncode == 0, result.stderr
    assert document is not None and [step["step"] for step in document["steps"]] == [
        "release"
    ]
    _assert_continues_to_the_developer(accepted, document)
    assert accepted.records(path)[path] == stage
    assert accepted.revisions(path)[path] == revision


@seam
def test_an_invalid_config_refuses_resume_and_a_fixed_one_keeps_the_accepted_stage(
    accepted: Recovery,
) -> None:
    path = _status_path(accepted)
    revisions = accepted.revisions(path, accepted.batch_path)
    # The fixture runs on zero project configuration: no file is the valid state to return to.
    config = accepted.repo / ".harness/orchestration.json"
    assert not config.exists()
    config.write_text(json.dumps({"concurrency_budget": "many"}), encoding="utf-8")

    refused, document = accepted.recovery("resume")

    assert refused.returncode == 2
    assert document is not None and document["outcome"] == "refused"
    assert document["dispatch_created"] is False
    config_check = next(
        c for c in document["status"]["checks"] if c["check"] == "config"
    )
    assert config_check["status"] != "passed"
    assert accepted.revisions(path, accepted.batch_path) == revisions

    config.unlink()
    result, resumed = accepted.recovery("resume")

    assert result.returncode == 0, result.stderr
    _assert_continues_to_the_developer(accepted, resumed)
    assert accepted.revisions(path, accepted.batch_path) == revisions


@seam
def test_a_restarted_runtime_resumes_without_rerunning_the_accepted_stage(
    accepted: Recovery,
) -> None:
    path = _status_path(accepted)
    stage = accepted.records(path)[path]
    accepted.hold("unknown-value", "the runtime stopped during the next stage")
    accepted.runtime.stop()
    accepted.runtime = ServingRuntime(accepted.repo)

    result, document = accepted.recovery("resume")

    assert result.returncode == 0, result.stderr
    _assert_continues_to_the_developer(accepted, document)
    assert accepted.records(path)[path] == stage
