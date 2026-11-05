"""Unit tests of the container route view-model; a scripted coordinator stands in for every process."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from harness.console.container_route import (
    NEED_BATCH,
    Authored,
    RouteSession,
    Stage,
    State,
    StageView,
    env_names,
    mark,
)

REPO = Path("/work/project")
SECRET = "s3cr3t-value-123"


class ScriptedCoordinator:
    """A CommandRunner that answers by coordinator subcommand and records every call."""

    def __init__(self) -> None:
        self.replies: dict[str, tuple[str, str, int]] = {}
        self.calls: list[list[str]] = []

    def reply(
        self, key: str, document: object = None, *, stderr: str = "", code: int = 0
    ) -> None:
        self.replies[key] = (
            "" if document is None else json.dumps(document),
            stderr,
            code,
        )

    def __call__(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> "subprocess.CompletedProcess[str]":
        self.calls.append(list(argv))
        words = list(argv)
        key = (
            "cleanup"
            if "cleanup" in words
            else " ".join(words[words.index("--repo") + 2 : words.index("--repo") + 4])
        )
        stdout, stderr, code = self.replies.get(
            key, ("", f"ERROR: no scripted reply for {key}", 2)
        )
        return subprocess.CompletedProcess(words, code, stdout, stderr)

    def commands(self) -> list[str]:
        return [
            " ".join(call[call.index("--repo") + 2 : call.index("--repo") + 4])
            for call in self.calls
            if "--repo" in call
        ]


def plan_document(**overrides: object) -> dict[str, object]:
    plan: dict[str, object] = {
        "mode": "sandbox",
        "network": {"hosts": ["api.example.com"]},
        "filesystem": [],
        "sources": {
            "mode": "defaults",
            "network": "defaults",
            "filesystem": "defaults",
            "container": "roles.developer",
            "environment": "roles.developer",
        },
        "requirements": [
            {"resource": "checkout", "path": "/work/wt", "access": "write"},
            {"resource": "git_common", "path": "/work/project/.git", "access": "write"},
            {
                "resource": "shared_storage",
                "path": "/work/project/.harness",
                "access": "read",
            },
        ],
        "runtime_extension": "docker",
        "container": {
            "engine": "podman",
            "worker_image": "harness-worker:local",
            "proxy_image": "harness-proxy:local",
        },
        "environment": ["API_TOKEN", "HOME_DIR"],
        "plan_digest": "p" * 64,
    }
    plan.update(overrides)
    return plan


def verification(status: str = "verified", **overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "status": status,
        "reason": None
        if status == "verified"
        else "native worker access proof is unavailable",
        "required": {"hosts": ["api.example.com"], "filesystem": []},
        "verified": ["mode", "network", "filesystem"] if status == "verified" else [],
        "unverified": [] if status == "verified" else ["mode", "network", "filesystem"],
        "remedy": None if status == "verified" else "repeat preflight",
    }
    value.update(overrides)
    return value


def preflight_document(
    plan: dict[str, object] | None = None, verified: dict[str, object] | None = None
) -> dict[str, object]:
    return {
        "ticket": "#711",
        "decision_packet": {
            "runtime_access": {
                "plan": plan if plan is not None else plan_document(),
                "verification": verified if verified is not None else verification(),
            }
        },
    }


def authored(document: dict[str, object] | None, problem: str = "") -> "object":
    return lambda repo: Authored(document, problem)


AUTHORED_DOCUMENT: dict[str, object] = {
    "extensions": {"runtime_access": "docker"},
    "access_policy": {
        "defaults": {
            "mode": "sandbox",
            "container": {"worker_image": "harness-worker:local"},
            "environment": ["API_TOKEN"],
        },
        "roles": {
            "developer": {
                "container": {
                    "engine": "podman",
                    "worker_image": "harness-worker:local",
                    "proxy_image": "harness-proxy:local",
                },
                "environment": {"API_TOKEN": SECRET},
            }
        },
        "operations": {"qa": {"container": {"worker_image": "harness-qa:local"}}},
    },
}


def make_session(
    coordinator: ScriptedCoordinator | None = None,
    document: dict[str, object] | None = AUTHORED_DOCUMENT,
    problem: str = "",
) -> tuple[RouteSession, ScriptedCoordinator]:
    scripted = coordinator or ScriptedCoordinator()
    session = RouteSession(REPO, scripted, load_authored=authored(document, problem))  # type: ignore[arg-type]
    return session, scripted


def render(view: StageView) -> str:
    """Every visible text of a view, as a screen would draw it."""
    parts = [*view.blockers, *view.notes]
    for row in view.rows:
        parts += [row.label, row.value, row.group, mark(row.state) if row.state else ""]
    for action in view.actions:
        parts += [action.label, action.reason]
    return "\n".join(part for part in parts if part)


def row_value(view: StageView, label: str, group: str = "") -> str:
    for row in view.rows:
        if row.label == label and (not group or row.group == group):
            return row.value
    raise AssertionError(f"no row {label!r} in {[r.label for r in view.rows]}")


# ----------------------------------------------------------------------------- state marks


def test_every_state_is_an_icon_plus_a_label_not_colour_alone() -> None:
    assert mark(State.OK) == "✔ ок"
    assert mark(State.NOT_CHECKED) == "○ не проверено"
    assert mark(State.NOT_REPORTED) == "○ не сообщается"
    assert mark(State.BLOCKED) == "✖ заблокировано"
    assert mark(State.UNKNOWN) == "? неизвестно"
    for state in State:
        icon = mark(state).split(" ")[0]
        assert icon and not icon.isalnum()


# ----------------------------------------------------------------------------- Setup


def test_setup_shows_authored_extension_defaults_roles_and_operations() -> None:
    session, _ = make_session()
    view = session.view(Stage.SETUP)
    assert row_value(view, "extensions.runtime_access") == "docker"
    assert (
        row_value(view, "Образ worker", "access_policy.defaults")
        == "harness-worker:local"
    )
    assert row_value(view, "Движок", "access_policy.roles.developer") == "podman"
    assert (
        row_value(view, "Образ worker", "access_policy.operations.qa")
        == "harness-qa:local"
    )


def test_setup_names_environment_variables_and_never_their_values() -> None:
    session, _ = make_session()
    view = session.view(Stage.SETUP)
    assert (
        row_value(view, "Переменные окружения (имена)", "access_policy.roles.developer")
        == "API_TOKEN"
    )
    assert SECRET not in render(view)
    assert env_names(["A=1", "B"]) == ["A", "B"]
    assert env_names({"TOKEN": SECRET}) == ["TOKEN"]
    assert env_names("not a list") == []


def test_setup_without_a_preflight_says_the_effective_plan_is_not_checked() -> None:
    session, scripted = make_session()
    view = session.view(Stage.SETUP)
    row = next(row for row in view.rows if row.label == "Эффективный план")
    assert row.state is State.NOT_CHECKED and "выберите batch и роль" in row.value
    recheck = next(action for action in view.actions if action.key == "recheck")
    assert not recheck.enabled and recheck.reason == NEED_BATCH
    assert scripted.calls == []  # drawing a view runs nothing


def test_setup_effective_plan_and_replace_override_source_come_from_preflight() -> None:
    session, scripted = make_session()
    scripted.reply("dispatch preflight", preflight_document())
    session.select("batch-1", "developer")
    session.recheck()
    view = session.view(Stage.SETUP)
    assert row_value(view, "plan_digest", "Эффективный план") == "p" * 64
    assert row_value(view, "Образ proxy", "Эффективный план") == "harness-proxy:local"
    assert (
        row_value(view, "Переменные окружения (имена)", "Эффективный план")
        == "API_TOKEN, HOME_DIR"
    )
    overrides = [
        r.value for r in view.rows if r.label == "Переопределение заменяет слой целиком"
    ]
    assert overrides == ["container: roles.developer", "environment: roles.developer"]
    assert all(r.state is State.WARN for r in view.rows if "Переопределение" in r.label)
    command = scripted.calls[0]
    assert "preflight" in command and "--batch" in command and "batch-1" in command
    assert "--approved-by" not in command


def test_setup_shows_a_failed_preflight_verbatim_instead_of_an_invented_plan() -> None:
    session, scripted = make_session()
    scripted.reply(
        "dispatch preflight", None, stderr="ERROR: no batch\nREMEDY: create it", code=2
    )
    session.select("batch-1")
    session.recheck()
    view = session.view(Stage.SETUP)
    row = next(row for row in view.rows if row.label == "Эффективный план")
    assert row.state is State.FAILED and "ERROR: no batch" in row.value
    assert not any(r.group == "Эффективный план" for r in view.rows)


def test_setup_reports_an_unreadable_authored_configuration() -> None:
    session, _ = make_session(
        document=None, problem="конфигурация не прочитана: нет файла"
    )
    view = session.view(Stage.SETUP)
    assert view.rows[0].state is State.FAILED and "нет файла" in view.rows[0].value


def test_setup_warns_when_the_container_extension_is_off() -> None:
    session, _ = make_session(document={"extensions": {"runtime_access": "none"}})
    view = session.view(Stage.SETUP)
    first = view.rows[0]
    assert first.value == "none" and first.state is State.WARN
    assert any("не включён" in row.value for row in view.rows)


def test_setup_writes_only_through_the_existing_wizard_and_saving_starts_no_worker() -> (
    None
):
    session, scripted = make_session()
    view = session.view(Stage.SETUP)
    edit = next(action for action in view.actions if action.key == "edit-config")
    assert edit.enabled and not edit.needs_confirmation
    assert any("не запускает worker" in note for note in view.notes)
    assert scripted.calls == []


# ----------------------------------------------------------------------------- tabs


def test_tabs_name_all_six_stages_with_visible_reasons_and_run_nothing() -> None:
    session, scripted = make_session()
    tabs = {tab.stage: tab for tab in session.tabs()}
    assert [tab.title for tab in session.tabs()] == [
        "Setup",
        "Preflight",
        "Plan / approval",
        "Worker",
        "QA",
        "Cleanup",
    ]
    assert tabs[Stage.PREFLIGHT].reason == NEED_BATCH
    assert (
        tabs[Stage.PLAN].state is State.BLOCKED
        and "verified" in tabs[Stage.PLAN].reason
    )
    assert tabs[Stage.WORKER].reason and tabs[Stage.QA].reason
    assert scripted.calls == []


def test_a_verified_preflight_opens_the_plan_tab_and_a_new_selection_drops_it() -> None:
    session, scripted = make_session()
    scripted.reply("dispatch preflight", preflight_document())
    session.select("batch-1")
    session.recheck()
    tabs = {tab.stage: tab for tab in session.tabs()}
    assert tabs[Stage.PREFLIGHT].state is State.OK
    assert tabs[Stage.PLAN].state is not State.BLOCKED
    session.select("batch-2")
    assert session.preflight is None
    assert {tab.stage: tab for tab in session.tabs()}[Stage.PLAN].state is State.BLOCKED
