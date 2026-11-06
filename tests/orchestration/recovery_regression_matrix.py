"""The recovery regression suite: each recovery scenario of #685 and the one test that proves it.

Every test named here runs on the Rust runtime store and the recovery commands (or on the config
boundary that feeds them), never on the superseded Python store or its intent journal (ADR 0026
section 1). ``test_recovery_regression.py`` keeps the registry complete: the labels equal
``LABELS``, every node id exists, and no named module imports a superseded store module. A test the
registry names is collected by the ordinary run, so the CI ``verify`` job with
``HARNESS_REQUIRE_RUNTIME=1`` runs the whole suite on the real binary.
"""

from __future__ import annotations

import ast
import importlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUPERSEDED_MODULES = ("runtime_state_store", "runtime_intent")

_COMMANDS = "tests/orchestration/test_recovery_commands.py"
_API = "tests/orchestration/test_recovery_api.py"
_REGRESSION = "tests/orchestration/test_recovery_regression.py"
_HOLD = "tests/orchestration/test_operational_hold.py"
_CONFIG = "tests/orchestration/test_config_validation.py"
_INGRESS = "tests/orchestration/test_pinned_config_ingress.py"
_SUPERVISOR = "tests/orchestration/test_runtime_supervisor.py"
_WRITE_FAULTS = "tests/orchestration/test_runtime_store_write_faults.py"
_AUDIT = "tests/orchestration/test_runtime_store_audit.py"
_MIGRATE = "tests/orchestration/test_runtime_store_migrate.py"
_MIGRATE_FAULTS = "tests/orchestration/test_runtime_store_migrate_faults.py"
_LEGACY = "tests/orchestration/test_runtime_store_legacy_scenarios.py"
_CONSOLE = "tests/console/test_console_recovery_view.py"


@dataclass(frozen=True)
class Scenario:
    """One scenario and the node id of its module-level test, without a parameter suffix."""

    label: str
    nodeid: str


# The closed list of scenarios from the ticket; a change here is a change of the suite's scope.
LABELS = (
    "invalid config before the first launch",
    "invalid config on the next transition",
    "invalid config during recovery keeps the accepted stage",
    "normalization warnings",
    "pinned evidence after a damaged file",
    "failure at a stage after accepted stages",
    "restart without rerunning accepted stages",
    "record window",
    "audit window",
    "store window",
    "migration generation selection",
    "migration repeat",
    "duplicate resume",
    "concurrent resume",
    "stale approval",
    "live worker",
    "ambiguous external effect",
    "unknown legacy state",
    "legacy file-ledger epoch",
    "unavailable storage",
    "unreadable recovery record",
    "incompatible adapter declaration",
    "incompatible runtime",
    "headless and console parity",
    "fallback without Textual",
    "unknown outcome in the console",
    "no automatic abandon",
)

SCENARIOS: Sequence[Scenario] = (
    Scenario(
        "invalid config before the first launch",
        f"{_SUPERVISOR}::test_an_invalid_config_refuses_dispatch_send_before_any_launch_and_changes_nothing",
    ),
    Scenario(
        "invalid config on the next transition",
        f"{_INGRESS}::test_report_is_persisted_under_pinned_policy_when_live_config_is_invalid",
    ),
    Scenario(
        "invalid config during recovery keeps the accepted stage",
        f"{_REGRESSION}::test_an_invalid_config_refuses_resume_and_a_fixed_one_keeps_the_accepted_stage",
    ),
    Scenario(
        "normalization warnings",
        f"{_CONFIG}::test_runtime_normalizes_config_enum_and_reports_warning_without_writing",
    ),
    Scenario(
        "pinned evidence after a damaged file",
        f"{_INGRESS}::test_corrupt_snapshot_captures_input_without_accepting_report",
    ),
    Scenario(
        "failure at a stage after accepted stages",
        f"{_REGRESSION}::test_a_failure_after_an_accepted_stage_resumes_to_the_next_stage_only",
    ),
    Scenario(
        "restart without rerunning accepted stages",
        f"{_REGRESSION}::test_a_restarted_runtime_resumes_without_rerunning_the_accepted_stage",
    ),
    Scenario(
        "record window",
        f"{_WRITE_FAULTS}::test_a_lost_response_after_the_commit_is_answered_from_the_stored_result",
    ),
    Scenario(
        "audit window",
        f"{_AUDIT}::test_a_record_added_after_the_checkpoint_stops_every_ordinary_command",
    ),
    Scenario(
        "store window",
        f"{_WRITE_FAULTS}::test_a_runtime_killed_inside_the_transaction_leaves_nothing_and_the_client_commits_once",
    ),
    Scenario(
        "migration generation selection",
        f"{_MIGRATE_FAULTS}::test_a_sigkill_at_a_step_then_a_repeat_leaves_exactly_one_authority",
    ),
    Scenario(
        "migration repeat",
        f"{_MIGRATE}::test_a_repeated_migrate_reports_already_cut_over_and_changes_no_byte",
    ),
    Scenario(
        "duplicate resume",
        f"{_COMMANDS}::test_a_repeated_resume_changes_nothing_more",
    ),
    Scenario(
        "concurrent resume",
        f"{_COMMANDS}::test_concurrent_resumes_release_the_hold_once",
    ),
    Scenario(
        "stale approval",
        f"{_COMMANDS}::test_a_stale_approval_is_refused_and_not_reused",
    ),
    Scenario(
        "live worker",
        f"{_COMMANDS}::test_a_live_worker_is_reconciled_and_no_second_one_is_started",
    ),
    Scenario(
        "ambiguous external effect",
        f"{_COMMANDS}::test_an_ambiguous_hand_off_is_refused_and_never_started_again",
    ),
    Scenario(
        "unknown legacy state",
        f"{_LEGACY}::test_a_defective_state_is_refused_as_a_whole_and_nothing_changes",
    ),
    Scenario(
        "legacy file-ledger epoch",
        f"{_COMMANDS}::test_the_file_ledger_epoch_refuses_with_the_migrate_remedy",
    ),
    Scenario(
        "unavailable storage",
        f"{_WRITE_FAULTS}::test_the_runtime_that_is_not_running_is_runtime_unavailable_and_changes_nothing",
    ),
    Scenario(
        "unreadable recovery record",
        f"{_API}::test_an_unreadable_hold_record_blocks_without_a_lifecycle_write",
    ),
    Scenario(
        "incompatible adapter declaration",
        f"{_API}::test_reload_refuses_an_unsupported_runtime_declaration",
    ),
    Scenario(
        "incompatible runtime",
        f"{_API}::test_reload_refuses_a_runtime_without_the_recovery_feature",
    ),
    Scenario(
        "headless and console parity",
        f"{_CONSOLE}::test_action_availability_follows_the_core_and_never_exceeds_it",
    ),
    Scenario(
        "fallback without Textual",
        f"{_COMMANDS}::test_recovery_runs_without_textual",
    ),
    Scenario(
        "unknown outcome in the console",
        f"{_CONSOLE}::test_resume_stays_blocked_in_the_unknown_outcome_even_if_the_core_lists_it_available",
    ),
    Scenario(
        "no automatic abandon",
        f"{_HOLD}::test_auto_decide_on_a_held_batch_records_the_operational_hold_stop_and_never_abandons",
    ),
)


def _module_name(path: str) -> str:
    return path.removesuffix(".py").replace("/", ".")


def registry_problems(
    scenarios: Sequence[Scenario], labels: Sequence[str]
) -> list[str]:
    """Why ``scenarios`` is not the closed suite: a missing, extra or repeated label, a node id
    that names no module-level test, or a named module that imports a superseded store module.
    An empty list means the registry is complete."""
    problems: list[str] = []
    named = [scenario.label for scenario in scenarios]
    problems.extend(
        f"no scenario for {label!r}" for label in labels if label not in named
    )
    problems.extend(
        f"the scenario {label!r} is outside the closed list"
        for label in named
        if label not in labels
    )
    problems.extend(
        f"the scenario {label!r} is registered more than once"
        for label in sorted(set(named))
        if named.count(label) > 1
    )
    for scenario in scenarios:
        path, _, name = scenario.nodeid.partition("::")
        if not name or "::" in name:
            problems.append(f"{scenario.nodeid} is not a module-level test node id")
            continue
        if not (ROOT / path).is_file():
            problems.append(f"{scenario.nodeid}: {path} does not exist")
            continue
        module = importlib.import_module(_module_name(path))
        if not callable(getattr(module, name, None)):
            problems.append(f"{scenario.nodeid}: {path} has no test {name}")
    for path in sorted({scenario.nodeid.partition("::")[0] for scenario in scenarios}):
        if (ROOT / path).is_file() and _imports_superseded(ROOT / path):
            problems.append(f"{path} imports a superseded store module")
    return problems


def _imports_superseded(path: Path) -> bool:
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or "", *(alias.name for alias in node.names)]
        else:
            continue
        if any(
            part in SUPERSEDED_MODULES for item in names for part in item.split(".")
        ):
            return True
    return False
