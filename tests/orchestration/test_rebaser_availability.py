"""Причина доступности роли rebaser отделена от проверки маршрута."""

from pathlib import Path

import pytest

from harness.orchestration.core import config as core_config
from harness.orchestration.core.utils import JsonObject
from harness.orchestration.workflow import rebaser


def _roles(tmp_path: Path, *, installed: bool = True) -> Path:
    roles = tmp_path / "roles"
    roles.mkdir()
    if installed:
        (roles / "rebaser.md").write_text("# rebaser\n", encoding="utf-8")
    return roles


def test_missing_manifest_is_not_installed_even_when_assigned(tmp_path: Path) -> None:
    roles = _roles(tmp_path, installed=False)

    reason = rebaser.availability(roles, {"assignment_plans": {"rebaser": {}}})

    assert reason == rebaser.UNAVAILABLE_NOT_INSTALLED
    assert reason not in rebaser.AVAILABLE


@pytest.mark.parametrize("config", [{}, {"assignment_plans": {}}, {"assignment_plans": None}])
def test_project_without_assignments_is_zero_config(tmp_path: Path, config: JsonObject) -> None:
    reason = rebaser.availability(_roles(tmp_path), config)

    assert reason == rebaser.AVAILABLE_ZERO_CONFIG
    assert reason in rebaser.AVAILABLE


def test_project_assigning_the_rebaser_has_it_assigned(tmp_path: Path) -> None:
    config: JsonObject = {"assignment_plans": {"developer": {}, "rebaser": {}}}

    reason = rebaser.availability(_roles(tmp_path), config)

    assert reason == rebaser.AVAILABLE_ASSIGNED
    assert reason in rebaser.AVAILABLE


def test_project_assigning_other_roles_leaves_the_rebaser_unassigned(tmp_path: Path) -> None:
    config: JsonObject = {"assignment_plans": {"developer": {}, "qa": {}}}

    reason = rebaser.availability(_roles(tmp_path), config)

    assert reason == rebaser.UNAVAILABLE_NOT_ASSIGNED
    assert reason not in rebaser.AVAILABLE


@pytest.mark.parametrize("plans", [["rebaser"], "rebaser"])
def test_malformed_assignment_plans_leave_the_rebaser_unassigned(
    tmp_path: Path, plans: object
) -> None:
    reason = rebaser.availability(_roles(tmp_path), {"assignment_plans": plans})

    assert reason == rebaser.UNAVAILABLE_NOT_ASSIGNED


@pytest.mark.parametrize(
    ("installed", "config", "expected"),
    [
        (True, {}, True),
        (True, {"assignment_plans": {"rebaser": {}}}, True),
        (True, {"assignment_plans": {"developer": {}}}, False),
        (False, {}, False),
    ],
)
def test_available_wraps_availability_over_the_pinned_roles_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    installed: bool,
    config: JsonObject,
    expected: bool,
) -> None:
    roles = _roles(tmp_path, installed=installed)
    monkeypatch.setattr(core_config, "_roles_dir", lambda repo: roles)

    assert rebaser.available(tmp_path / "repo", config) is expected
