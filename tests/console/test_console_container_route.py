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


# ----------------------------------------------------------------------------- Preflight


def blocked_facts(**overrides: object) -> dict[str, object]:
    facts: dict[str, object] = {
        "engine": "podman",
        "engine_mode": "not-probed",
        "selinux": False,
        "worker_image": "harness-worker:local",
        "worker_image_id": None,
        "proxy_image": "harness-proxy:local",
        "proxy_image_id": None,
        "blockers": [
            {
                "reason": "the docker executor launches only an external dispatch, not in-process",
                "remedy": "set the role's assignment_plans transport to external",
            },
            {
                "reason": "environment variable API_TOKEN is not set",
                "remedy": "export API_TOKEN",
            },
        ],
    }
    facts.update(overrides)
    return facts


def verified_evidence() -> dict[str, object]:
    return {
        "engine": "podman",
        "engine_mode": "rootless",
        "selinux": True,
        "transport": "external",
        "worker_image": "harness-worker:local",
        "worker_image_id": "sha256:" + "a" * 64,
        "proxy_image": "harness-proxy:local",
        "proxy_image_id": "sha256:" + "b" * 64,
    }


def run_preflight(document: object, **kwargs: object) -> StageView:
    session, scripted = make_session()
    scripted.reply("dispatch preflight", document, **kwargs)  # type: ignore[arg-type]
    session.select("batch-1")
    session.recheck()
    return session.view(Stage.PREFLIGHT)


def test_preflight_before_any_check_reads_not_checked_and_runs_nothing() -> None:
    session, scripted = make_session()
    session.select("batch-1")
    view = session.view(Stage.PREFLIGHT)
    assert view.rows[0].state is State.NOT_CHECKED
    assert scripted.calls == []


def test_preflight_without_a_batch_disables_the_check_with_a_visible_reason() -> None:
    session, _ = make_session()
    action = session.view(Stage.PREFLIGHT).actions[0]
    assert not action.enabled and action.reason == NEED_BATCH


def test_a_verified_preflight_shows_engine_mode_images_and_full_ids() -> None:
    document = preflight_document(
        verified=verification("verified", evidence=verified_evidence())
    )
    view = run_preflight(document)
    assert row_value(view, "Режим движка") == "rootless"
    assert row_value(view, "Транспорт") == "external"
    assert "sha256:" + "a" * 64 in row_value(view, "Образ worker")
    assert "sha256:" + "b" * 64 in row_value(view, "Образ proxy")
    assert next(r for r in view.rows if r.label == "Статус проверки").state is State.OK
    assert view.blockers == ()
    assert "требует отдельного одобрения" in row_value(view, "Запуск")


def test_blocked_preflight_lists_every_core_blocker_verbatim_with_its_remedy() -> None:
    document = preflight_document(
        verified=verification("unverified", environment=blocked_facts())
    )
    view = run_preflight(document)
    assert view.blockers == (
        "the docker executor launches only an external dispatch, not in-process"
        " — set the role's assignment_plans transport to external",
        "environment variable API_TOKEN is not set — export API_TOKEN",
    )
    assert (
        next(r for r in view.rows if r.label == "Статус проверки").state
        is State.BLOCKED
    )
    assert next(r for r in view.rows if r.label == "Запуск").state is State.BLOCKED


def test_dependent_checks_without_an_observation_read_not_checked_never_ok() -> None:
    document = preflight_document(
        verified=verification("unverified", environment=blocked_facts())
    )
    view = run_preflight(document)
    by_label = {row.label: row for row in view.rows}
    assert by_label["Режим движка"].state is State.NOT_CHECKED
    assert by_label["Образ worker"].state is State.NOT_CHECKED
    assert "не проверено: образ не наблюдён" in by_label["Образ worker"].value
    assert by_label["Образ proxy"].state is State.NOT_CHECKED
    assert by_label["Переменные окружения (имена)"].state is State.NOT_CHECKED
    assert by_label["Монтирования"].state is not State.OK
    assert by_label["Сеть"].state is not State.OK
    assert (
        by_label["Транспорт"].state is State.NOT_REPORTED
    )  # in-process facts carry none
    assert not any(row.state is State.OK for row in view.rows)


def test_an_image_without_an_id_is_not_checked_even_when_the_engine_was_probed() -> (
    None
):
    evidence = {**verified_evidence(), "proxy_image_id": None}
    document = preflight_document(verified=verification("verified", evidence=evidence))
    view = run_preflight(document)
    proxy = next(r for r in view.rows if r.label == "Образ proxy")
    assert proxy.state is State.NOT_CHECKED


def test_mounts_and_hosts_are_listed_with_absolute_paths_and_their_check_state() -> (
    None
):
    document = preflight_document(
        verified=verification(
            "verified",
            evidence=verified_evidence(),
            required={
                "hosts": ["api.example.com"],
                "filesystem": [
                    {"resource": "checkout", "path": "/work/wt", "access": "write"},
                    {
                        "resource": "git_common",
                        "path": "/work/project/.git",
                        "access": "read",
                    },
                ],
            },
        )
    )
    view = run_preflight(document)
    mounts = next(r for r in view.rows if r.label == "Монтирования")
    assert mounts.value == "checkout write /work/wt\ngit_common read /work/project/.git"
    assert mounts.state is State.OK
    assert row_value(view, "Сеть") == "api.example.com"


def test_no_hosts_means_the_network_check_is_not_applicable_not_a_pass() -> None:
    document = preflight_document(
        verified=verification(
            "verified",
            evidence=verified_evidence(),
            required={"hosts": [], "filesystem": []},
        )
    )
    network = next(r for r in run_preflight(document).rows if r.label == "Сеть")
    assert network.state is State.INFO and "не применимо" in network.value


def test_legacy_inherit_is_not_a_container_pass_and_keeps_launch_blocked() -> None:
    document = preflight_document(
        verified={
            "status": "legacy-inherit",
            "verified": [],
            "unverified": [],
            "remedy": None,
        }
    )
    view = run_preflight(document)
    assert (
        next(r for r in view.rows if r.label == "Статус проверки").state is State.INFO
    )
    assert next(r for r in view.rows if r.label == "Запуск").state is State.BLOCKED


def test_missing_verification_is_not_reported_not_verified() -> None:
    view = run_preflight({"ticket": "#711"})
    status = next(r for r in view.rows if r.label == "Статус проверки")
    assert status.state is State.NOT_REPORTED and status.value == "не сообщается"
    assert next(r for r in view.rows if r.label == "Запуск").state is State.BLOCKED


def test_a_failed_preflight_call_is_a_blocker_with_its_stderr_and_no_dependent_success() -> (
    None
):
    view = run_preflight(
        None, stderr="ERROR: harness-runtime unreachable\nREMEDY: start it", code=2
    )
    assert view.blockers == ("ERROR: harness-runtime unreachable\nREMEDY: start it",)
    assert view.rows[0].state is State.FAILED
    assert len(view.rows) == 1


def test_recheck_is_one_read_only_preflight_call_and_never_starts_a_worker() -> None:
    session, scripted = make_session()
    scripted.reply("dispatch preflight", preflight_document())
    session.select("batch-1", "qa", "claude")
    session.recheck()
    session.recheck()
    assert scripted.commands() == ["dispatch preflight", "dispatch preflight"]
    assert scripted.calls[0][-6:] == [
        "--batch",
        "batch-1",
        "--role",
        "qa",
        "--runtime",
        "claude",
    ]
    recheck = session.view(Stage.PREFLIGHT).actions[0]
    assert recheck.enabled and not recheck.needs_confirmation


# ----------------------------------------------------------------------------- Plan / approval

TRANSITION = "t" * 64
WORKER_ID = "sha256:" + "c" * 64
PROXY_ID = "sha256:" + "d" * 64


def propose_document(
    transition_digest: str = TRANSITION, plan: dict[str, object] | None = None
) -> dict[str, object]:
    return {
        "batch_id": "batch-1",
        "state": "proposed",
        "transition": {
            "next_role": "developer",
            "purpose": "work",
            "base_sha": "b" * 40,
            "candidate_sha": None,
        },
        "transition_digest": transition_digest,
        "runtime_access": plan if plan is not None else plan_document(),
        "runtime_images": {"worker": WORKER_ID, "proxy": PROXY_ID},
    }


def verified_session() -> tuple[RouteSession, ScriptedCoordinator]:
    session, scripted = make_session()
    scripted.reply(
        "dispatch preflight",
        preflight_document(
            verified=verification("verified", evidence=verified_evidence())
        ),
    )
    session.select("batch-1", "developer")
    session.recheck()
    return session, scripted


def test_propose_is_refused_before_a_verified_preflight_and_runs_nothing() -> None:
    session, scripted = make_session()
    session.select("batch-1")
    view = session.view(Stage.PLAN)
    propose = next(a for a in view.actions if a.key == "propose")
    assert not propose.enabled and "verified" in propose.reason
    try:
        session.propose()
    except PermissionError:
        pass
    else:
        raise AssertionError("propose must fail closed")
    assert scripted.calls == []


def test_a_blocked_preflight_never_reaches_an_approval() -> None:
    session, scripted = make_session()
    scripted.reply(
        "dispatch preflight",
        preflight_document(
            verified=verification("unverified", environment=blocked_facts())
        ),
    )
    session.select("batch-1")
    session.recheck()
    view = session.view(Stage.PLAN)
    assert not next(a for a in view.actions if a.key == "propose").enabled
    assert not next(a for a in view.actions if a.key == "approve").enabled
    assert scripted.commands() == ["dispatch preflight"]


def test_the_plan_view_shows_mounts_hosts_env_names_and_full_digests() -> None:
    session, scripted = verified_session()
    scripted.reply("dispatch propose", propose_document())
    session.propose()
    view = session.view(Stage.PLAN)
    assert row_value(view, "Монтирования") == (
        "checkout write /work/wt\ngit_common write /work/project/.git\n"
        "shared_storage read /work/project/.harness"
    )
    assert row_value(view, "Сетевые хосты") == "api.example.com"
    assert row_value(view, "Переменные окружения (имена)") == "API_TOKEN, HOME_DIR"
    assert row_value(view, "Образ worker") == f"harness-worker:local\n{WORKER_ID}"
    assert row_value(view, "Образ proxy") == f"harness-proxy:local\n{PROXY_ID}"
    assert row_value(view, "plan_digest") == "p" * 64
    assert row_value(view, "transition_digest") == TRANSITION
    assert row_value(view, "Базовый коммит") == "b" * 40
    assert "нового propose" in row_value(view, "Одобрение")
    assert SECRET not in render(view)


def test_approval_passes_only_the_displayed_transition_digest() -> None:
    session, scripted = verified_session()
    scripted.reply("dispatch propose", propose_document())
    scripted.reply(
        "dispatch create", {"dispatch_id": "dispatch-9", "state": "approved"}
    )
    session.propose()
    session.create(" operator ")
    command = scripted.calls[-1]
    assert command[command.index("--transition-digest") + 1] == TRANSITION
    assert command[command.index("--approved-by") + 1] == "operator"
    assert "--approved-at" in command
    assert all(not token.startswith("--auto") for token in command)
    assert session.selection.dispatch == "dispatch-9"
    assert session.proposal is None
    view = session.view(Stage.PLAN)
    assert row_value(view, "Создан dispatch") == "dispatch-9"
    assert "не запущен" in row_value(view, "Worker")


def test_approval_requires_a_live_proposal_and_a_named_approver() -> None:
    session, scripted = verified_session()
    try:
        session.create("operator")
    except PermissionError:
        pass
    else:
        raise AssertionError("create without a proposal must fail closed")
    scripted.reply("dispatch propose", propose_document())
    session.propose()
    try:
        session.create("  ")
    except ValueError:
        pass
    else:
        raise AssertionError("an approval needs a named approver")
    assert "dispatch create" not in scripted.commands()


def test_a_refused_create_invalidates_the_proposal_and_needs_a_new_one() -> None:
    session, scripted = verified_session()
    scripted.reply("dispatch propose", propose_document())
    scripted.reply(
        "dispatch create",
        None,
        stderr="ERROR: approval digest does not match the proposed transition\nREMEDY: propose again",
        code=2,
    )
    session.propose()
    session.create("operator")
    assert session.proposal is not None and session.proposal.stale.startswith(
        "отказ ядра"
    )
    view = session.view(Stage.PLAN)
    approve = next(a for a in view.actions if a.key == "approve")
    assert not approve.enabled and "propose заново" in approve.reason
    assert "approval digest does not match" in view.blockers[0]
    try:
        session.create("operator")
    except PermissionError:
        pass
    else:
        raise AssertionError("a stale proposal must not be approved again")
    assert scripted.commands().count("dispatch create") == 1
    assert {tab.stage: tab for tab in session.tabs()}[Stage.PLAN].state is State.WARN


def test_a_refused_propose_drops_the_previously_held_proposal() -> None:
    session, scripted = verified_session()
    scripted.reply("dispatch propose", propose_document())
    session.propose()
    assert session.proposal is not None
    scripted.reply(
        "dispatch propose",
        None,
        stderr="ERROR: image missing\nREMEDY: build it",
        code=2,
    )
    session.propose()
    assert session.proposal is None
    view = session.view(Stage.PLAN)
    assert view.blockers == ("ERROR: image missing\nREMEDY: build it",)
    assert not next(a for a in view.actions if a.key == "approve").enabled


def test_plan_drift_between_propose_and_approval_requires_a_new_proposal() -> None:
    session, scripted = verified_session()
    scripted.reply("dispatch propose", propose_document())
    session.propose()
    drifted = plan_document(plan_digest="q" * 64)
    scripted.reply(
        "dispatch preflight",
        preflight_document(
            plan=drifted,
            verified=verification("verified", evidence=verified_evidence()),
        ),
    )
    session.recheck()
    assert (
        session.proposal is not None
        and "plan_digest изменился" in session.proposal.stale
    )
    assert not next(
        a for a in session.view(Stage.PLAN).actions if a.key == "approve"
    ).enabled


def test_a_preflight_that_stops_being_verified_stales_the_held_proposal() -> None:
    session, scripted = verified_session()
    scripted.reply("dispatch propose", propose_document())
    session.propose()
    scripted.reply(
        "dispatch preflight",
        preflight_document(
            verified=verification("unverified", environment=blocked_facts())
        ),
    )
    session.recheck()
    assert (
        session.proposal is not None and "больше не verified" in session.proposal.stale
    )


def test_a_new_selection_drops_the_proposal_and_the_old_created_result() -> None:
    session, scripted = verified_session()
    scripted.reply("dispatch propose", propose_document())
    session.propose()
    session.select("batch-2", "developer")
    assert session.proposal is None and session.created is None
    assert session.selection.dispatch == ""


def test_a_proposal_without_a_transition_digest_is_not_held() -> None:
    session, scripted = verified_session()
    scripted.reply("dispatch propose", {"state": "proposed"})
    session.propose()
    assert session.proposal is None
    assert not next(
        a for a in session.view(Stage.PLAN).actions if a.key == "approve"
    ).enabled


def test_creating_a_dispatch_needs_confirmation_and_propose_does_not_start_a_worker() -> (
    None
):
    session, scripted = verified_session()
    scripted.reply("dispatch propose", propose_document())
    session.propose()
    actions = {a.key: a for a in session.view(Stage.PLAN).actions}
    assert (
        actions["approve"].needs_confirmation
        and not actions["propose"].needs_confirmation
    )
    assert scripted.commands() == ["dispatch preflight", "dispatch propose"]
