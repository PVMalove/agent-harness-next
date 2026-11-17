"""`harness update` to 2.0.0 cuts the state of a project over to the runtime store (#814; ADR 0020,
section 6).

On a state of ledger version 3 the update needs the human approval of the cutover, checks the
preconditions of `harness-runtime migrate` before it installs a file, installs, then migrates. A
project without orchestration state, or already on the runtime store, is updated as before.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from unittest import mock

import pytest

from tests.core.test_uninstall import git, harness

from .release_1x import STATE_REL, build_1x_state
from .runtime_store_support import migrate, runtime_binary

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="the 1.x state driver and the runtime CLI run on Unix here"
)

APPROVAL = (
    "--approved-by",
    "Malove",
    "--approved-at",
    "2026-11-13T09:00:00+00:00",
    "--reason",
    "update to 2.0.0",
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    git(root, "init", "-q")
    result = harness("init", str(root), "--capability", "backend-orchestration")
    assert result.returncode == 0, result.stderr
    return root


@pytest.fixture
def on_path(monkeypatch: pytest.MonkeyPatch) -> Path:
    """The runtime of this tree, found on PATH as an installed one would be."""
    binary = runtime_binary()
    monkeypatch.setenv("PATH", f"{binary.parent}{os.pathsep}{os.environ['PATH']}")
    return binary


def _with_1x_state(project: Path, release_1x: Path, tmp_path: Path) -> Path:
    source, _ = build_1x_state(release_1x, tmp_path / "source")
    state = project / STATE_REL
    shutil.copytree(source / STATE_REL, state, dirs_exist_ok=True)
    return state


def _version(state: Path) -> int:
    version = json.loads((state / "ledger.json").read_text(encoding="utf-8"))["version"]
    assert isinstance(version, int)
    return version


def test_a_version_3_state_without_approval_installs_nothing_and_names_the_command(
    project: Path, release_1x: Path, tmp_path: Path, on_path: Path
) -> None:
    state = _with_1x_state(project, release_1x, tmp_path)
    before = (project / ".harness" / "harness.lock").read_bytes()

    result = harness("update", str(project), "--force-managed-files")

    assert result.returncode != 0
    assert "--approved-by" in result.stderr and "--reason" in result.stderr
    assert (project / ".harness" / "harness.lock").read_bytes() == before
    assert _version(state) == 3


def test_a_refused_precondition_installs_nothing(
    project: Path, release_1x: Path, tmp_path: Path, on_path: Path
) -> None:
    state = _with_1x_state(project, release_1x, tmp_path)
    generation = state / "generations" / json.loads(
        (state / "ledger.json").read_text(encoding="utf-8")
    )["generation"]
    (generation / "qa-lane").mkdir(exist_ok=True)
    (generation / "qa-lane" / "lease.json").write_text(
        json.dumps(
            {
                "dispatch_id": "dispatch-00000000-0000-0000-0000-000000000000",
                "host": "elsewhere",
                "pid": 1,
                "acquired_at": "2026-11-13T08:00:00+00:00",
                "expires_at": "2026-11-13T08:01:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    before = (project / ".harness" / "harness.lock").read_bytes()

    result = harness("update", str(project), *APPROVAL)

    assert result.returncode != 0
    assert "[lease_held]" in result.stderr
    assert (project / ".harness" / "harness.lock").read_bytes() == before
    assert _version(state) == 3


def test_an_approved_update_installs_then_cuts_the_state_over(
    project: Path, release_1x: Path, tmp_path: Path, on_path: Path
) -> None:
    state = _with_1x_state(project, release_1x, tmp_path)

    result = harness("update", str(project), *APPROVAL)

    assert result.returncode == 0, result.stderr
    assert _version(state) == 4
    migrated = json.loads(result.stdout.strip().splitlines()[-1])
    assert migrated["migrated"] is True


def test_a_state_on_the_runtime_store_is_updated_without_a_migrate(
    project: Path, release_1x: Path, tmp_path: Path, on_path: Path
) -> None:
    state = _with_1x_state(project, release_1x, tmp_path)
    assert migrate(project).returncode == 0
    pointer = (state / "ledger.json").read_bytes()

    result = harness("update", str(project))

    assert result.returncode == 0, result.stderr
    assert (state / "ledger.json").read_bytes() == pointer
    assert "migrate" not in result.stdout


def test_a_project_without_state_is_updated_as_before(project: Path) -> None:
    result = harness("update", str(project))

    assert result.returncode == 0, result.stderr
    assert not (project / STATE_REL / "ledger.json").exists()


def test_an_older_ledger_names_the_1x_ledger_migrate_first(
    project: Path, release_1x: Path, tmp_path: Path, on_path: Path
) -> None:
    state = _with_1x_state(project, release_1x, tmp_path)
    pointer = state / "ledger.json"
    pointer.write_text(
        json.dumps({**json.loads(pointer.read_text(encoding="utf-8")), "version": 2}),
        encoding="utf-8",
    )

    result = harness("update", str(project), *APPROVAL)

    assert result.returncode != 0
    assert "ledger migrate" in result.stderr and "1.x" in result.stderr


def test_a_missing_runtime_installs_nothing_and_names_the_build(
    project: Path, release_1x: Path, tmp_path: Path
) -> None:
    _with_1x_state(project, release_1x, tmp_path)
    before = (project / ".harness" / "harness.lock").read_bytes()

    with (
        mock.patch("harness.runtime_cutover.CHECKOUT_BINARY", Path("no/such/binary")),
        mock.patch("harness.runtime_cutover.shutil.which", return_value=None),
    ):
        result = harness("update", str(project), *APPROVAL)

    assert result.returncode != 0
    assert "cargo build --release" in result.stderr
    assert (project / ".harness" / "harness.lock").read_bytes() == before


def test_a_policy_approver_is_refused_by_the_runtime(
    project: Path, release_1x: Path, tmp_path: Path, on_path: Path
) -> None:
    state = _with_1x_state(project, release_1x, tmp_path)
    approval = list(APPROVAL)
    approval[1] = "policy:auto"

    result = harness("update", str(project), *approval)

    assert result.returncode != 0
    assert "[policy_denied]" in result.stderr
    assert _version(state) == 3


def test_approval_flags_come_together(project: Path) -> None:
    result = harness("update", str(project), "--approved-by", "Malove")

    assert result.returncode != 0
    assert "--approved-at" in result.stderr
