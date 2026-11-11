"""The fault-injection and security matrix at seam 1: each scenario of the #784 "Reliability and
correctness" matrix and each security boundary, and the one test that proves it.

Every registered test carries the ``fault_injection`` marker and runs the coordinator CLI (or a
coordinator process) against the real ``harness-runtime`` binary. The CI fault-injection job selects
the marker with ``HARNESS_REQUIRE_FAULT_INJECTION=1``: ``conftest.py`` then fails the session when
the selected marked tests differ from this registry, and turns a skip of a marked test into a
failure. ``test_fault_injection_matrix.py`` keeps the registry and the markers in step.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

MARKER = "fault_injection"
REQUIRE_ENV = "HARNESS_REQUIRE_FAULT_INJECTION"

_SUPERVISOR = "tests/orchestration/test_runtime_supervisor.py"
_QA_CONTAINER = "tests/orchestration/test_qa_container.py"
_CONTAINER = "tests/orchestration/test_container_runtime.py"
_QA_LANE = "tests/orchestration/test_runtime_store_qa_lane.py"
_PARALLEL = "tests/orchestration/test_runtime_store_parallel.py"


@dataclass(frozen=True)
class Scenario:
    """One scenario and the node id of its test, without a parameter suffix."""

    label: str
    nodeid: str


SCENARIOS: Sequence[Scenario] = (
    # The reliability matrix.
    Scenario(
        "SIGKILL of the coordinator",
        f"{_SUPERVISOR}::test_a_coordinator_killed_after_the_launch_intent_gets_the_same_receipt_on_repeat_with_one_launch",
    ),
    Scenario(
        "SIGKILL of the runtime",
        f"{_SUPERVISOR}::test_a_runtime_killed_between_launch_and_receipt_adopts_the_process_without_a_second_launch",
    ),
    Scenario(
        "SIGKILL of the runtime: running container adopted",
        f"{_CONTAINER}::test_a_runtime_killed_between_container_launch_and_receipt_adopts_the_running_worker_without_a_second_create",
    ),
    Scenario(
        "lost IPC reply",
        f"{_SUPERVISOR}::test_a_lost_response_after_the_receipt_is_answered_from_the_stored_receipt_with_one_launch",
    ),
    Scenario(
        "orphan worker",
        f"{_SUPERVISOR}::test_an_orphan_worker_of_a_killed_runtime_is_supervised_by_its_successor_until_the_deadline",
    ),
    Scenario(
        "double start",
        f"{_SUPERVISOR}::test_a_second_send_during_a_launch_returns_the_same_receipt",
    ),
    Scenario(
        "PID reuse",
        f"{_SUPERVISOR}::test_a_reused_pid_is_lost_and_the_live_process_is_never_signalled",
    ),
    Scenario(
        "stale lease",
        f"{_QA_LANE}::test_a_stopped_owner_keeps_its_expired_lease_and_the_next_admission_is_lease_held",
    ),
    Scenario(
        "partial artifact",
        f"{_QA_CONTAINER}::test_a_partial_command_record_left_by_a_killed_runtime_is_not_run_and_never_evidence",
    ),
    Scenario(
        "OCI image mismatch",
        f"{_CONTAINER}::test_an_image_rebuilt_after_the_coordinator_check_is_approval_mismatch_in_the_runtime_before_any_create",
    ),
    Scenario(
        "SELinux EPERM",
        f"{_QA_CONTAINER}::test_an_selinux_permission_denied_command_blocks_the_report_as_tooling_without_a_new_attempt",
    ),
    Scenario(
        "offline dependency install",
        f"{_QA_CONTAINER}::test_an_offline_dependency_install_is_environment_preparation_and_a_new_attempt",
    ),
    Scenario(
        "conflicting batches",
        f"{_PARALLEL}::test_two_dispatch_creates_under_a_budget_with_one_free_slot_admit_one",
    ),
    # The security boundaries.
    Scenario(
        "tampered audit record",
        f"{_SUPERVISOR}::test_a_broken_audit_chain_refuses_the_launch_before_any_process_starts",
    ),
    Scenario(
        "engine socket in a mount",
        f"{_CONTAINER}::test_a_plan_root_holding_an_engine_socket_is_policy_denied_before_any_engine_call",
    ),
    Scenario(
        "foreign lease release",
        f"{_QA_LANE}::test_a_release_by_another_holder_is_fencing_mismatch_and_the_owner_keeps_the_lane",
    ),
)


def registry_problems(marked: Iterable[str], scenarios: Sequence[Scenario]) -> list[str]:
    """Why the node ids of the selected marked tests differ from ``scenarios``: a scenario
    without a selected test, and a marked test no scenario names. A parameter suffix ``[...]`` of
    a node id is ignored; an empty list means they match."""
    selected = {nodeid.split("[", 1)[0] for nodeid in marked}
    registered = {scenario.nodeid for scenario in scenarios}
    problems = [
        f"the scenario {scenario.label!r} has no selected test {scenario.nodeid}"
        for scenario in scenarios
        if scenario.nodeid not in selected
    ]
    problems.extend(
        f"{nodeid} carries the {MARKER} marker but no scenario names it"
        for nodeid in sorted(selected - registered)
    )
    return problems
