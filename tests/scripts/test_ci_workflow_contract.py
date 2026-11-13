#!/usr/bin/env python3
"""The two CI paths of .github/workflows/verify.yml (issue #937).

A pull request into an ``integration/**`` branch runs ``verify-light`` and the platform test groups;
a pull request into any other branch, a push to ``master``
and a call from another workflow run the full jobs. The workflow is read as text with the comment
lines removed (no YAML library): a job that exists only in a comment pins nothing.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from harness.orchestration.core import ci_source

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "verify.yml"

LIGHT_JOB = "verify-light"
LIGHT_CONDITION = (
    "github.event_name == 'pull_request' && startsWith(github.base_ref, 'integration/')"
)
FULL_CONDITION = "github.event_name != 'pull_request' || !startsWith(github.base_ref, 'integration/')"
FULL_PULL_REQUEST_CONDITION = "github.event_name == 'pull_request' && !startsWith(github.base_ref, 'integration/')"
# The jobs that run tests: the light path skips every one of them.
FULL_JOBS = {
    "verify": FULL_CONDITION,
    "verify-windows": FULL_CONDITION,
    "diff-coverage": FULL_PULL_REQUEST_CONDITION,
    "repo-map-bundle": FULL_CONDITION,
    "rust": FULL_CONDITION,
    "runtime-ipc-windows": FULL_CONDITION,
    "docker-smoke": FULL_CONDITION,
    "fault-injection": FULL_CONDITION,
}
PLATFORM_GROUP_JOBS = {
    "verify-linux-unit",
    "verify-linux-integration",
    "verify-windows-unit",
    "verify-windows-integration",
}
# The fast gate of the full path: no tests, but every suite waits for it.
GATE_JOB = "lint"
# The jobs without tests keep their own condition on both paths.
UNCHANGED_JOBS = {
    "private-terms": "github.event_name == 'pull_request'",
    "parser-bundle": None,
}
# The jobs that run on both paths without a condition: the console SPA and the public site.
BOTH_PATHS_JOBS = {"console-spa", "docs"}
GROUPS_JOB = "verify-test-groups"
ALL_JOBS = {
    LIGHT_JOB,
    GATE_JOB,
    "dashboard",
    *FULL_JOBS,
    *UNCHANGED_JOBS,
    *BOTH_PATHS_JOBS,
    GROUPS_JOB,
    *PLATFORM_GROUP_JOBS,
}
# What each suite waits for: the fast gate, directly or through `rust`, whose debug build of
# harness-runtime the Linux suites download; the long suites also wait for the public site.
STAGES = {
    "rust": {GATE_JOB},
    "verify": {"docs", "rust", "verify-linux-unit", "verify-linux-integration"},
    "verify-windows": {
        GATE_JOB,
        "docs",
        "verify-windows-unit",
        "verify-windows-integration",
    },
    "verify-linux-unit": {"docs", GATE_JOB, LIGHT_JOB, "rust"},
    "verify-linux-integration": {"docs", GATE_JOB, LIGHT_JOB, "rust"},
    "verify-windows-unit": {"docs", GATE_JOB, LIGHT_JOB},
    "verify-windows-integration": {"docs", GATE_JOB, LIGHT_JOB},
    GROUPS_JOB: PLATFORM_GROUP_JOBS,
    "diff-coverage": {GATE_JOB, "docs"},
    "repo-map-bundle": {"parser-bundle", GATE_JOB},
    "runtime-ipc-windows": {GATE_JOB},
    "docker-smoke": {"rust"},
    "fault-injection": {"rust"},
}
# What the light job must never contain: each of these runs, or measures, the full suite.
FULL_SUITE_MARKERS = (
    "make verify",
    "cargo test",
    "pytest",
    "diff_coverage",
    "-m docker_smoke",
    "-m fault_injection",
)
TRIGGERS = (
    "on:\n"
    "  workflow_call:\n"
    "  pull_request:\n"
    "    types: [opened, synchronize, reopened, edited]\n"
    "  push:\n"
    "    branches: [master]\n"
)


def _code() -> str:
    """The workflow without its comment lines."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#")) + "\n"


def _jobs() -> dict[str, str]:
    """The text of each job, by job name; the blank lines of the stage banners are no job."""
    jobs = _code().split("\njobs:\n", 1)[1]
    return {
        block.strip().split(":", 1)[0]: block
        for block in re.split(r"\n(?=  [a-z][a-z0-9-]*:\n)", jobs)
        if block.strip()
    }


def _needs(job: str) -> set[str]:
    """The `needs` of a job: one name or an inline list."""
    found = re.search(r"^    needs:\s*(\[[^\]]*\]|[a-z][a-z0-9-]*)\s*$", job, flags=re.MULTILINE)
    if found is None:
        return set()
    return {item.strip() for item in found[1].strip("[]").split(",") if item.strip()}


def _condition(job: str) -> str | None:
    """The one-line ``if:`` of a job; a job-level ``if`` that spans lines is not used here."""
    found = re.findall(r"^    if: (.+)$", job, flags=re.MULTILINE)
    assert len(found) <= 1, "a job has one if"
    if not found or str(found[0]).strip() in {">", ">-", "|", "|-"}:
        return None
    return str(found[0]).strip()


def _atom(text: str, event: str, base_ref: str) -> bool:
    text = text.strip()
    negated = text.startswith("!")
    if negated:
        text = text[1:].strip()
    if text == "always()":
        value = True
    elif equal := re.fullmatch(r"github\.event_name (==|!=) '([a-z_]+)'", text):
        value = (event == equal[2]) == (equal[1] == "==")
    elif prefix := re.fullmatch(r"startsWith\(github\.base_ref, '([^']+)'\)", text):
        value = base_ref.startswith(prefix[1])
    else:
        raise AssertionError(f"the contract test cannot evaluate {text!r}")
    return value != negated


def _runs(condition: str | None, event: str, base_ref: str) -> bool:
    """Whether a job with ``condition`` runs for the event, by the grammar the workflow uses."""
    if condition is None:
        return True
    return any(
        all(_atom(atom, event, base_ref) for atom in alternative.split("&&"))
        for alternative in condition.split("||")
    )


def _running(event: str, base_ref: str) -> set[str]:
    running = {
        name for name, job in _jobs().items() if _runs(_condition(job), event, base_ref)
    }
    if event == "pull_request":
        running.update(PLATFORM_GROUP_JOBS | {GROUPS_JOB})
        if base_ref.startswith("integration/"):
            running.discard("verify")
            running.discard("verify-windows")
        else:
            running.update({"verify", "verify-windows"})
    else:
        running.difference_update(PLATFORM_GROUP_JOBS | {GROUPS_JOB})
        running.update({"verify", "verify-windows"})
    return running


class WorkflowTriggersTests(unittest.TestCase):
    def test_the_triggers_are_pinned(self) -> None:
        code = _code()
        triggers = code.split("\npermissions:", 1)[0].split("\non:\n", 1)[1]

        self.assertEqual("on:\n" + triggers.rstrip("\n") + "\n", TRIGGERS)

    def test_the_jobs_are_exactly_the_light_job_and_the_known_full_jobs(self) -> None:
        self.assertEqual(set(_jobs()), ALL_JOBS)


class LightPathTests(unittest.TestCase):
    def test_the_light_job_is_only_for_a_pull_request_into_an_integration_branch(
        self,
    ) -> None:
        self.assertEqual(_condition(_jobs()[LIGHT_JOB]), LIGHT_CONDITION)

    def test_the_light_job_runs_lint_rust_checks_the_diff_tests_and_the_metadata_check(
        self,
    ) -> None:
        job = _jobs()[LIGHT_JOB]

        for step in (
            "run: make lint",
            "cargo fmt --check",
            "cargo clippy --locked --all-targets -- -D warnings",
            "scripts/ci_light_tests.py",
            "--base",
            "github.event.pull_request.base.sha",
            "github.event.pull_request.head.sha",
            "scripts/check_public_metadata.py",
        ):
            with self.subTest(step=step):
                self.assertIn(step, job)

    def test_the_light_job_runs_nothing_of_the_full_suite(self) -> None:
        job = _jobs()[LIGHT_JOB]

        for marker in FULL_SUITE_MARKERS:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, job)

    def test_the_check_name_of_the_light_job_is_what_collect_ci_refuses_for_full(
        self,
    ) -> None:
        names = [
            name for name in _jobs() if name.endswith(ci_source.LIGHT_CHECK_SUFFIX)
        ]

        self.assertEqual(names, [LIGHT_JOB])
        self.assertNotIn("name:", _jobs()[LIGHT_JOB].split("steps:", 1)[0])

    def test_a_pull_request_into_an_integration_branch_runs_only_the_light_path(
        self,
    ) -> None:
        running = _running("pull_request", "integration/web-console")

        self.assertEqual(
            running,
            {
                LIGHT_JOB,
                GROUPS_JOB,
                *PLATFORM_GROUP_JOBS,
                "private-terms",
                "parser-bundle",
                "dashboard",
                *BOTH_PATHS_JOBS,
            },
        )
        self.assertFalse(running & set(FULL_JOBS))

    def test_integration_groups_cover_both_platforms_and_python_test_kinds(
        self,
    ) -> None:
        jobs = _jobs()
        for name in PLATFORM_GROUP_JOBS:
            with self.subTest(job=name):
                job = jobs[name]
                self.assertIn("./.github/actions/verify-test-group", job)
                self.assertIn("group: unit" if name.endswith("unit") else "group: integration", job)
                self.assertIn("windows-latest" if "windows" in name else "ubuntu-latest", job)
        # Each group defines its targets once, in the Linux job; the Windows job reuses the anchor.
        for group, target in (("unit", "tests/core"), ("integration", "tests/orchestration")):
            with self.subTest(group=group):
                self.assertIn(f"targets: &{group}-targets", jobs[f"verify-linux-{group}"])
                self.assertIn(f"--pytest-target {target}", jobs[f"verify-linux-{group}"])
                self.assertIn(f"targets: *{group}-targets", jobs[f"verify-windows-{group}"])


class StageTests(unittest.TestCase):
    def test_the_gate_is_on_the_full_path_and_runs_the_fast_checks(self) -> None:
        job = _jobs()[GATE_JOB]

        self.assertEqual(_condition(job), FULL_CONDITION)
        self.assertEqual(_needs(job), set())
        for step in (
            "make lint",
            "cargo fmt --check",
            "cargo clippy --locked --all-targets --message-format=json -- -D warnings",
            "scripts/check_public_metadata.py",
        ):
            with self.subTest(step=step):
                self.assertIn(step, job)
        for marker in FULL_SUITE_MARKERS:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, job)

    def test_every_suite_waits_for_the_fast_stage(self) -> None:
        jobs = _jobs()

        for name, needs in STAGES.items():
            with self.subTest(job=name):
                self.assertEqual(_needs(jobs[name]), needs)

    def test_the_linux_suites_download_the_one_debug_build_of_the_rust_job(
        self,
    ) -> None:
        jobs = _jobs()

        self.assertIn("name: harness-runtime-linux-debug", jobs["rust"])
        for name in ("verify", "docker-smoke", "fault-injection"):
            with self.subTest(job=name):
                self.assertIn("name: harness-runtime-linux-debug", jobs[name])
                self.assertNotIn("cargo build", jobs[name])

    def test_the_failed_tests_of_each_suite_become_annotations(self) -> None:
        jobs = _jobs()

        self.assertIn("scripts/ci_summary.py annotate", jobs["verify"])
        self.assertIn("Summarize grouped tests", (ROOT / ".github/actions/verify-test-group/action.yml").read_text())


class FullPathTests(unittest.TestCase):
    def test_every_job_that_runs_tests_has_the_full_path_condition(self) -> None:
        jobs = _jobs()

        for name, condition in FULL_JOBS.items():
            with self.subTest(job=name):
                if name in {"verify", "verify-windows"}:
                    self.assertIn("always()", jobs[name])
                else:
                    self.assertEqual(_condition(jobs[name]), condition)

    def test_the_full_jobs_still_run_the_whole_suite(self) -> None:
        jobs = _jobs()

        self.assertIn("make verify", jobs["verify"])
        self.assertIn("cargo test --locked\n", jobs["rust"])
        self.assertIn("scripts/diff_coverage.py", jobs["diff-coverage"])
        self.assertIn("-m docker_smoke", jobs["docker-smoke"])
        self.assertIn("-m fault_injection", jobs["fault-injection"])

    def test_the_windows_job_runs_grouped_tests_and_clean_room_on_a_pull_request(self) -> None:
        job = _jobs()["verify-windows"]

        # The test matrix row confirms the named groups; clean-room remains its own matrix row.
        self.assertNotIn("--platform-subset", job)
        self.assertIn("--fail-fast", job)
        self.assertIn("always()", job)
        self.assertIn("Check Windows test groups", job)
        self.assertIn("matrix.part == 'clean-room'", job)

    def test_the_windows_tests_report_every_failure_of_a_pull_request_in_one_run(
        self,
    ) -> None:
        job = _jobs()["verify-windows"]

        # `--fail-fast` stops the Windows suite at its first failure, and every fix then costs one
        # more run to meet the next; the part that runs the tests is not stopped. The clean-room
        # part keeps it: its scenarios are sequential, and one failure explains the rest.
        self.assertIn("matrix.part != 'tests'", job)
        self.assertRegex(
            job,
            r"github\.event_name == 'pull_request' && matrix\.part != 'tests'\) && '--fail-fast'",
        )

    def test_the_jobs_without_tests_are_unchanged(self) -> None:
        jobs = _jobs()

        for name, condition in UNCHANGED_JOBS.items():
            with self.subTest(job=name):
                self.assertEqual(_condition(jobs[name]), condition)

    def test_a_pull_request_into_master_runs_the_full_jobs_and_not_the_group_jobs(
        self,
    ) -> None:
        running = _running("pull_request", "master")

        self.assertEqual(running, ALL_JOBS - {LIGHT_JOB})

    def test_a_pull_request_into_another_branch_runs_the_full_jobs(self) -> None:
        self.assertEqual(
            _running("pull_request", "release/1.x"),
            ALL_JOBS - {LIGHT_JOB},
        )
        # A branch that only starts with the word is no integration branch.
        self.assertEqual(
            _running("pull_request", "integrations"),
            ALL_JOBS - {LIGHT_JOB},
        )

    def test_a_push_to_master_and_a_call_from_another_workflow_run_the_full_jobs(
        self,
    ) -> None:
        # A called workflow sees the event of its caller; none of them is a pull request here.
        for event in ("push", "workflow_dispatch"):
            with self.subTest(event=event):
                self.assertEqual(
                    _running(event, ""),
                    ALL_JOBS
                    - {LIGHT_JOB, GROUPS_JOB, *PLATFORM_GROUP_JOBS, "diff-coverage", "private-terms"},
                )


class DashboardTests(unittest.TestCase):
    def test_the_dashboard_waits_for_every_other_job_whatever_its_result(self) -> None:
        dashboard = _jobs()["dashboard"]
        needs = re.search(r"needs:\s*\[([^\]]*)\]", dashboard)

        assert needs is not None
        self.assertEqual(
            {item.strip() for item in needs[1].split(",")},
            ALL_JOBS - {"dashboard", *PLATFORM_GROUP_JOBS},
        )
        self.assertEqual(_condition(dashboard), "always()")


if __name__ == "__main__":
    unittest.main()
