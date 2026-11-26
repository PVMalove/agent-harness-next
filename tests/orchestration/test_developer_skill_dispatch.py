"""Every developer dispatch is told to read the installed developer skill (#1161).

Real ledger and real Git through the coordinator's public commands: ``dispatch send`` and
``dispatch resume`` name the skill the project installed for a developer, refuse before any ledger
change when it is missing, and leave the immutable brief as it was.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from harness.orchestration import coordinator
from harness.orchestration.core import workspace
from harness.orchestration.core.developer_skill import INSTRUCTION
from harness.orchestration.core.utils import CoordinatorError, JsonObject
from harness.orchestration.ledger import ledger_ops
from tests.orchestration import test_coordinator as coordinator_tests

# Never bind the TestCase class to a module name at run time: pytest would collect and run its
# suite again. The alias exists for the type checker only.
if TYPE_CHECKING:
    Routing = coordinator_tests.CoordinatorRetryRoutingTests


@pytest.fixture
def routing() -> Iterator[Routing]:
    """The coordinator routing fixture, by composition so its own suite does not run again."""
    fixture = coordinator_tests.CoordinatorRetryRoutingTests()
    # A 1.x file ledger: these scenarios read the stored dispatch records directly.
    fixture.file_ledger = True
    fixture.setUp()
    try:
        yield fixture
    finally:
        fixture.tearDown()


def _installed(routing: Routing) -> Path:
    return routing.repo / ".harness" / "skills" / "developer" / "SKILL.md"


def _developer_brief(routing: Routing) -> JsonObject:
    batch = routing._create_batch()
    routing._accepted_architect(batch["batch_id"])
    brief: JsonObject = routing._dispatch(batch["batch_id"], "developer")["brief"]
    return brief


def _stored_brief(routing: Routing, dispatch_id: str) -> str:
    root = ledger_ops._state_root(routing._args(), routing.repo)
    record = ledger_ops._load_dispatch(root, dispatch_id)
    return hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()


def _state(routing: Routing, dispatch_id: str) -> str:
    status = coordinator.dispatch_status(
        routing._args(dispatch=dispatch_id, batch=None, stale_after=None)
    )
    return str(status["dispatches"][0]["state"])


def test_developer_send_names_the_installed_skill(routing: Routing) -> None:
    brief = _developer_brief(routing)

    launched = routing._send(brief["dispatch_id"])

    path = str(_installed(routing).resolve())
    assert launched["developer_skill"] == {
        "path": path,
        "instruction": INSTRUCTION.format(path=path),
    }
    assert path in launched["developer_skill"]["instruction"]


def test_architect_send_neither_names_nor_needs_the_skill(routing: Routing) -> None:
    _installed(routing).unlink()
    batch = routing._create_batch()
    brief = routing._dispatch(batch["batch_id"], "architect")["brief"]

    launched = routing._send(brief["dispatch_id"])

    assert "developer_skill" not in launched


def test_developer_send_without_the_skill_refuses_before_any_change(
    routing: Routing,
) -> None:
    brief = _developer_brief(routing)
    before = _stored_brief(routing, brief["dispatch_id"])
    saved = _installed(routing).read_bytes()
    _installed(routing).unlink()

    with pytest.raises(CoordinatorError) as refused:
        routing._send(brief["dispatch_id"])

    assert str(_installed(routing).resolve()) in refused.value.message
    assert "engineering-suite" in refused.value.remedy
    assert "the dispatch is unchanged" in refused.value.remedy
    assert _state(routing, brief["dispatch_id"]) == "approved"
    assert _stored_brief(routing, brief["dispatch_id"]) == before
    _installed(routing).write_bytes(saved)
    launched = routing._send(brief["dispatch_id"])
    assert launched["state"] == "dispatched"
    assert launched["developer_skill"]["path"] == str(_installed(routing).resolve())


def _checkpointed_developer(routing: Routing) -> tuple[JsonObject, JsonObject]:
    brief = _developer_brief(routing)
    routing._start(brief["dispatch_id"])
    candidate, changed = routing._developer_commit("checkpoint")
    return brief, routing._checkpoint_writer(brief, candidate, changed)


def _resume(routing: Routing, brief: JsonObject, checkpoint: JsonObject) -> JsonObject:
    facts = {
        "dispatch_id": brief["dispatch_id"],
        "remaining_definition_of_done": checkpoint["remaining_definition_of_done"],
        "risks": checkpoint["risks"],
        "dependencies": brief["dependencies"],
    }
    path = routing.repo / ".harness/.sandboxes/scratch/inbox/continuation-facts.json"
    path.write_text(json.dumps(facts), encoding="utf-8")
    return coordinator.resume_dispatch(
        routing._args(
            dispatch=brief["dispatch_id"],
            termination_reason=None,
            trigger="vertical-slice",
            measured_value=None,
            file=str(path),
            note="resume the recorded green slice",
            **routing._approval(),
        )
    )


def test_resumed_developer_names_the_installed_skill(routing: Routing) -> None:
    brief, checkpoint = _checkpointed_developer(routing)

    resumed = _resume(routing, brief, checkpoint)

    path = str(_installed(routing).resolve())
    assert resumed["state"] == "dispatched"
    assert resumed["developer_skill"] == {
        "path": path,
        "instruction": INSTRUCTION.format(path=path),
    }


def test_resume_without_the_skill_refuses_before_any_ledger_change(
    routing: Routing,
) -> None:
    brief, checkpoint = _checkpointed_developer(routing)
    batch_before = routing._batch_record(brief["batch_id"])
    saved = _installed(routing).read_bytes()
    _installed(routing).unlink()

    with pytest.raises(CoordinatorError) as refused:
        _resume(routing, brief, checkpoint)

    assert str(_installed(routing).resolve()) in refused.value.message
    assert _state(routing, brief["dispatch_id"]) == "checkpointed"
    assert routing._batch_record(brief["batch_id"]) == batch_before
    _installed(routing).write_bytes(saved)
    assert _resume(routing, brief, checkpoint)["state"] == "dispatched"


def test_the_runtime_snapshot_leaves_out_a_local_npm_install(tmp_path: Path) -> None:
    """A developer checkout holds the console frontend's ``node_modules``; the runtime package,
    its hash and its snapshot never include it, so a checkout and an install pin the same files."""
    package = tmp_path / "harness"
    for relative in (
        "orchestration/__init__.py",
        "console/__init__.py",
        "console/frontend/src/main.ts",
        "console/frontend/node_modules/tool/skills/SKILL.md",
    ):
        path = package / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n", encoding="utf-8")

    files = [
        path.relative_to(package).as_posix()
        for path in workspace._runtime_files(package)
    ]

    assert "console/frontend/src/main.ts" in files
    assert not [path for path in files if "node_modules" in path]


def test_a_pinned_runtime_snapshot_names_the_project_install(routing: Routing) -> None:
    """A batch on a pinned snapshot resolves the skill in the project, not in the snapshot."""
    source = workspace.MODULE_ROOT.parent
    sha256 = workspace._runtime_package_sha256(source)
    state_root = ledger_ops._state_root(routing._args(), routing.repo)
    snapshot = workspace._store_runtime_snapshot(state_root, source, sha256) / "harness"
    assert not list(snapshot.rglob("SKILL.md"))
    script = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from harness.orchestration.core import developer_skill as module\n"
        "assert Path(module.__file__).is_relative_to(Path(sys.argv[1]))\n"
        "print(json.dumps(module.developer_skill(Path(sys.argv[2]))))\n"
    )

    pinned = subprocess.run(
        [sys.executable, "-I", "-c", script, str(snapshot.parent), str(routing.repo)],
        capture_output=True,
        text=True,
        check=True,
    )

    path = str(_installed(routing).resolve())
    assert json.loads(pinned.stdout) == {
        "path": path,
        "instruction": INSTRUCTION.format(path=path),
    }
    assert not Path(path).is_relative_to(state_root)


def test_a_developer_report_records_without_new_fields(routing: Routing) -> None:
    """The completion report keeps its schema: send adds nothing a worker must report."""
    brief = _developer_brief(routing)
    before = _stored_brief(routing, brief["dispatch_id"])
    routing._start(brief["dispatch_id"])
    candidate, changed = routing._developer_commit("skill")

    receipt = routing._submit(
        brief["dispatch_id"], routing._developer_report(brief, candidate, changed)
    )

    assert receipt["state"] == "reported"
    assert _stored_brief(routing, brief["dispatch_id"]) == before


def test_a_blocked_report_naming_the_missing_skill_records_the_ordinary_way(
    routing: Routing,
) -> None:
    """A worker that cannot read the skill stops with an ordinary blocked report."""
    brief = _developer_brief(routing)
    routing._start(brief["dispatch_id"])
    path = str(_installed(routing).resolve())
    report = routing._base_report(
        brief,
        "developer",
        outcome="blocked",
        commit_sha=brief["snapshot_commit"],
        changed_files=[],
        checks_run=routing._checks(brief, "not_run"),
        blockers={
            "status": "present",
            "details": f"установленный developer skill недоступен: {path}",
        },
    )

    receipt = routing._submit(brief["dispatch_id"], report)

    assert receipt["state"] == "reported"
