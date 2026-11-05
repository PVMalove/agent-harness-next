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


# ----------------------------------------------------------------------------- Worker


def status_document(
    execution: dict[str, object] | None = None, **entry: object
) -> dict[str, object]:
    item: dict[str, object] = {
        "dispatch_id": "dispatch-9",
        "batch_id": "batch-1",
        "role": "developer",
        "state": "working",
        "adapter_receipt": {"launch_id": "launch-123"},
        "silent_seconds": 12,
        "stale": False,
    }
    if execution is not None:
        item["execution"] = execution
    item.update(entry)
    return {"stale_after_seconds": 7200, "stale": [], "dispatches": [item]}


def running_execution(**overrides: object) -> dict[str, object]:
    execution: dict[str, object] = {
        "state": "running",
        "engine": "podman",
        "container_id": "c" * 12,
        "launch": {
            "images": {"worker": WORKER_ID, "proxy": PROXY_ID},
            "labels": {"harness.repo": "project", "harness.dispatch": "dispatch-9"},
            "logs": "/work/project/.harness/logs/dispatch-9",
        },
        "observation": {"observed_at": "2026-11-05T15:00:00+00:00"},
    }
    execution.update(overrides)
    return execution


def worker_session(
    document: object = None, **kwargs: object
) -> tuple[RouteSession, ScriptedCoordinator]:
    session, scripted = make_session()
    session.select("batch-1")
    session.selection.dispatch = "dispatch-9"
    scripted.reply("dispatch status", document, **kwargs)  # type: ignore[arg-type]
    return session, scripted


def test_worker_stage_without_a_dispatch_is_pending_and_actions_say_why() -> None:
    session, scripted = make_session()
    view = session.view(Stage.WORKER)
    assert view.rows[0].state is State.PENDING
    assert all(not a.enabled and a.reason for a in view.actions)
    assert scripted.calls == []
    try:
        session.refresh_worker()
    except PermissionError:
        pass
    else:
        raise AssertionError("no dispatch, no observation")


def test_worker_stage_shows_each_fact_as_its_own_row_and_runs_nothing_on_draw() -> None:
    session, scripted = worker_session(status_document(running_execution()))
    drawn = session.view(Stage.WORKER)
    assert scripted.calls == [] and drawn.rows[1].state is State.NOT_CHECKED
    session.refresh_worker()
    view = session.view(Stage.WORKER)
    assert row_value(view, "Receipt / launch_id") == "launch-123"
    assert row_value(view, "Движок") == "podman"
    assert WORKER_ID in row_value(view, "Образы запуска") and PROXY_ID in row_value(
        view, "Образы запуска"
    )
    assert row_value(view, "Liveness (inspect)").startswith("running")
    assert row_value(view, "Наблюдалось") == "2026-11-05T15:00:00+00:00"
    assert "harness.dispatch: dispatch-9" in row_value(view, "Метки")
    assert row_value(view, "Код выхода").startswith("не сообщается")
    assert row_value(view, "Отчёт") == "не сообщается"
    assert (
        row_value(view, "Terminal evidence") == "/work/project/.harness/logs/dispatch-9"
    )
    assert scripted.commands() == ["dispatch status"]


def test_exit_zero_is_a_code_not_an_accepted_report_or_a_closed_task() -> None:
    execution = running_execution(
        state="exited",
        exit={
            "exit_code": 0,
            "stopped_by": None,
            "source": "inspect",
            "logs": "/logs/x",
        },
    )
    session, _ = worker_session(status_document(execution))
    session.refresh_worker()
    view = session.view(Stage.WORKER)
    assert row_value(view, "Код выхода") == "0"
    assert next(r for r in view.rows if r.label == "Код выхода").state is State.INFO
    assert row_value(view, "Отчёт") == "не сообщается"
    assert next(r for r in view.rows if r.label == "Отчёт").state is State.NOT_REPORTED
    assert (
        row_value(view, "Состояние в ledger") == "working"
    )  # still not closed or accepted
    assert any("не принимают отчёт" in note for note in view.notes)
    assert row_value(view, "Terminal evidence") == "/logs/x"


def test_a_held_report_is_a_warning_fact_not_an_acceptance() -> None:
    session, _ = worker_session(
        status_document(running_execution(), held_report={"outcome": "completed"})
    )
    session.refresh_worker()
    report = next(r for r in session.view(Stage.WORKER).rows if r.label == "Отчёт")
    assert report.state is State.WARN and "удержан" in report.value


def test_a_detached_launch_without_an_observed_execution_is_not_reported_alive() -> (
    None
):
    session, _ = worker_session(
        status_document(None, adapter_receipt={"launch_id": "launch-1"})
    )
    session.refresh_worker()
    view = session.view(Stage.WORKER)
    live = next(r for r in view.rows if r.label == "Liveness (inspect)")
    assert live.state is State.NOT_REPORTED and "не сообщается" in live.value
    assert row_value(view, "Receipt / launch_id") == "launch-1"


def test_a_missing_receipt_is_not_reported_and_a_lost_execution_is_a_warning() -> None:
    session, _ = worker_session(
        status_document(running_execution(state="lost"), adapter_receipt=None)
    )
    session.refresh_worker()
    view = session.view(Stage.WORKER)
    assert (
        next(r for r in view.rows if r.label == "Receipt / launch_id").state
        is State.NOT_REPORTED
    )
    assert (
        next(r for r in view.rows if r.label == "Liveness (inspect)").state
        is State.WARN
    )
    assert {tab.stage: tab for tab in session.tabs()}[Stage.WORKER].state is State.WARN


def test_an_unknown_execution_is_unknown_never_alive_or_stopped() -> None:
    session, _ = worker_session(status_document(running_execution(state="unknown")))
    session.refresh_worker()
    live = next(
        r for r in session.view(Stage.WORKER).rows if r.label == "Liveness (inspect)"
    )
    assert live.state is State.UNKNOWN and "не знает" in live.value


def test_silence_is_shown_as_a_fact_and_never_as_a_stop() -> None:
    session, _ = worker_session(
        status_document(running_execution(), silent_seconds=9000, stale=True)
    )
    session.refresh_worker()
    silent = next(
        r for r in session.view(Stage.WORKER).rows if r.label == "Тишина worker"
    )
    assert silent.state is State.WARN and silent.value == "9000 сек; stale"


def test_a_reaction_error_is_a_blocker_shown_verbatim() -> None:
    session, _ = worker_session(
        status_document(
            running_execution(state="exited"),
            reaction_error={
                "error": "the batch is held",
                "remedy": "run recovery resume",
            },
        )
    )
    session.refresh_worker()
    assert session.view(Stage.WORKER).blockers == (
        "the batch is held — run recovery resume",
    )


def test_a_busy_ledger_is_pending_and_a_failed_status_keeps_its_stderr() -> None:
    session, scripted = worker_session(
        {"ledger_busy": True, "remedy": "repeat dispatch status"}
    )
    session.refresh_worker()
    busy = session.view(Stage.WORKER).rows[-1]
    assert busy.state is State.PENDING and "repeat dispatch status" in busy.value
    scripted.reply(
        "dispatch status", None, stderr="ERROR: runtime down\nREMEDY: start it", code=2
    )
    session.refresh_worker()
    view = session.view(Stage.WORKER)
    assert view.blockers == ("ERROR: runtime down\nREMEDY: start it",)
    assert {tab.stage: tab for tab in session.tabs()}[
        Stage.WORKER
    ].state is State.FAILED


def test_a_dispatch_the_core_did_not_return_is_not_reported() -> None:
    document = status_document(running_execution())
    session, _ = worker_session(document)
    session.selection.dispatch = "dispatch-other"
    session.refresh_worker()
    assert session.view(Stage.WORKER).rows[-1].state is State.NOT_REPORTED


def test_refresh_is_an_observation_and_send_needs_confirmation() -> None:
    session, _ = worker_session(status_document(running_execution()))
    actions = {a.key: a for a in session.view(Stage.WORKER).actions}
    assert actions["refresh"].enabled and not actions["refresh"].needs_confirmation
    assert actions["send"].enabled and actions["send"].needs_confirmation


def test_executor_context_shows_worker_qa_and_labels_without_secrets() -> None:
    session, _ = worker_session(status_document(running_execution()))
    session.refresh_worker()
    context = dict(session.executor_context())
    assert context["Worker"] == "dispatch-9" and context["QA"] == "не создан"
    assert "harness.repo: project" in context["Метки"]
    assert SECRET not in "".join(context.values())


# ----------------------------------------------------------------------------- QA

QA_TRANSITION = "q" * 64


def qa_propose_document() -> dict[str, object]:
    document = propose_document(
        QA_TRANSITION,
        plan_document(
            container={"engine": "podman", "worker_image": "harness-qa:local"},
            plan_digest="z" * 64,
        ),
    )
    document["runtime_images"] = {"worker": "sha256:" + "e" * 64, "proxy": None}
    document["qa_execution"] = {
        "supervisor": "harness-runtime",
        "command_timeout_seconds": 900,
        "stop_grace_seconds": 10,
        "poll_interval_seconds": 2,
    }
    return document


def qa_report(**overrides: object) -> dict[str, object]:
    report: dict[str, object] = {
        "outcome": "completed",
        "qa_stages": {
            "stages": [
                {
                    "stage": "prepare",
                    "command": "make bootstrap",
                    "result": "pass",
                    "exit_code": 0,
                },
                {
                    "stage": "gate",
                    "command": "make lint",
                    "result": "fail",
                    "exit_code": 2,
                    "domain": "code",
                    "diagnostics": "ruff: 3 errors",
                },
            ],
            "failed_stage": "gate",
            "code_checks_started": "yes",
        },
        "checks_run": [
            {"command": "make lint", "result": "fail", "evidence": "exit 2"},
            {"command": "make test", "result": "not_run", "evidence": ""},
        ],
    }
    report.update(overrides)
    return report


def qa_session(
    report: dict[str, object] | None = None,
) -> tuple[RouteSession, ScriptedCoordinator]:
    scripted = ScriptedCoordinator()
    session = RouteSession(
        REPO,
        scripted,
        load_authored=authored(AUTHORED_DOCUMENT),  # type: ignore[arg-type]
        load_report=lambda path: report,
    )
    session.select("batch-1", "developer")
    return session, scripted


def test_qa_has_its_own_proposal_and_worker_approval_does_not_enable_it() -> None:
    session, scripted = verified_session()
    scripted.reply("dispatch propose", propose_document())
    scripted.reply(
        "dispatch create", {"dispatch_id": "dispatch-9", "state": "approved"}
    )
    session.propose()
    session.create("operator")
    assert session.selection.dispatch == "dispatch-9"
    view = session.view(Stage.QA)
    actions = {a.key: a for a in view.actions}
    assert (
        not actions["qa-run"].enabled
        and "одобренный dispatch QA" in actions["qa-run"].reason
    )
    assert not actions["qa-approve"].enabled
    assert "не заменяет одобрение QA" in row_value(view, "Одобрение")
    try:
        session.run_qa()
    except PermissionError:
        pass
    else:
        raise AssertionError("a worker approval must not run QA")
    assert "qa run" not in scripted.commands()


def test_qa_proposal_is_for_role_qa_and_approval_carries_the_qa_digest_only() -> None:
    session, scripted = verified_session()
    scripted.reply("dispatch propose", propose_document())
    session.propose()  # the worker's own proposal stays held
    scripted.reply("dispatch propose", qa_propose_document())
    scripted.reply(
        "dispatch create", {"dispatch_id": "dispatch-qa-1", "state": "approved"}
    )
    session.propose_qa()
    qa_command = scripted.calls[-1]
    assert qa_command[qa_command.index("--role") + 1] == "qa"
    session.create_qa("operator")
    create = scripted.calls[-1]
    assert create[create.index("--transition-digest") + 1] == QA_TRANSITION
    assert create[create.index("--role") + 1] == "qa"
    assert TRANSITION not in create
    assert session.selection.qa_dispatch == "dispatch-qa-1"
    assert (
        session.proposal is not None
        and session.proposal.transition_digest == TRANSITION
    )


def test_qa_view_shows_the_binding_pinned_image_and_planned_limits() -> None:
    session, scripted = verified_session()
    scripted.reply("dispatch propose", qa_propose_document())
    session.propose_qa()
    view = session.view(Stage.QA)
    assert row_value(view, "transition_digest") == QA_TRANSITION
    assert row_value(view, "plan_digest") == "z" * 64
    assert row_value(view, "Образ QA") == "harness-qa:local"
    assert row_value(view, "Digest образа") == "sha256:" + "e" * 64
    assert row_value(view, "Лимит команды, с (по плану)") == "900"
    assert row_value(view, "Grace остановки, с (по плану)") == "10"


def test_a_refused_qa_approval_makes_the_qa_proposal_stale_without_touching_the_worker() -> (
    None
):
    session, scripted = verified_session()
    scripted.reply("dispatch propose", qa_propose_document())
    scripted.reply("dispatch create", None, stderr="ERROR: image drifted", code=2)
    session.propose_qa()
    session.create_qa("operator")
    assert session.qa.proposal is not None and session.qa.proposal.stale
    view = session.view(Stage.QA)
    assert view.blockers == ("ERROR: image drifted",)
    assert not next(a for a in view.actions if a.key == "qa-approve").enabled


def test_qa_run_shows_each_command_exit_code_domain_diagnostics_and_not_run() -> None:
    session, scripted = qa_session(qa_report())
    session.selection.qa_dispatch = "dispatch-qa-1"
    scripted.reply(
        "qa run",
        {"dispatch_id": "dispatch-qa-1", "state": "reported", "report": "/r.json"},
    )
    session.run_qa()
    view = session.view(Stage.QA)
    rows = {row.label: row for row in view.rows}
    assert (
        rows["1. prepare"].state is State.OK
        and "exit_code: 0" in rows["1. prepare"].value
    )
    gate = rows["2. gate"]
    assert gate.state is State.FAILED
    assert (
        "exit_code: 2" in gate.value
        and "domain: code" in gate.value
        and "ruff: 3 errors" in gate.value
    )
    assert rows["Остановилась на стадии"].value == "gate"
    checks = [row for row in view.rows if row.label == "Проверка"]
    assert [row.state for row in checks] == [State.FAILED, State.NOT_CHECKED]
    assert "not_run" in checks[1].value
    assert scripted.commands() == ["qa run"]
    assert {tab.stage: tab for tab in session.tabs()}[Stage.QA].state is State.FAILED


def test_a_negative_exit_code_is_a_signal_or_interruption_never_a_pass() -> None:
    report = qa_report()
    report["qa_stages"] = {
        "stages": [
            {"stage": "gate", "command": "make test", "result": "fail", "exit_code": -9}
        ],
        "failed_stage": "gate",
    }
    session, scripted = qa_session(report)
    session.selection.qa_dispatch = "dispatch-qa-1"
    scripted.reply(
        "qa run",
        {"dispatch_id": "dispatch-qa-1", "state": "reported", "report": "/r.json"},
    )
    session.run_qa()
    gate = next(r for r in session.view(Stage.QA).rows if r.label == "1. gate")
    assert gate.state is State.FAILED and "сигналом или прервана" in gate.value


def test_what_the_core_does_not_report_is_not_reported_never_invented() -> None:
    session, scripted = qa_session(qa_report())
    session.selection.qa_dispatch = "dispatch-qa-1"
    scripted.reply(
        "qa run",
        {"dispatch_id": "dispatch-qa-1", "state": "reported", "report": "/r.json"},
    )
    session.run_qa()
    view = session.view(Stage.QA)
    for label in (
        "Контейнер команды",
        "stdout и stderr раздельно",
        "Сигнал, таймаут и grace по факту",
    ):
        row = next(r for r in view.rows if r.label == label)
        assert row.state is State.NOT_REPORTED and row.value == "не сообщается ядром"


def test_an_unreadable_report_is_not_reported_and_a_blocked_transition_is_a_blocker() -> (
    None
):
    session, scripted = qa_session(None)
    session.selection.qa_dispatch = "dispatch-qa-1"
    scripted.reply(
        "qa run",
        {
            "dispatch_id": "dispatch-qa-1",
            "state": "reported",
            "report": "/missing.json",
            "transition_blocked": True,
            "diagnostic": "configuration changed since dispatch approval",
            "remedy": "review the pending report",
        },
    )
    session.run_qa()
    view = session.view(Stage.QA)
    assert view.blockers == (
        "configuration changed since dispatch approval — review the pending report",
    )
    assert next(r for r in view.rows if r.label == "Отчёт").state is State.NOT_REPORTED
    assert {tab.stage: tab for tab in session.tabs()}[
        Stage.QA
    ].state is State.NOT_REPORTED


def test_a_failed_qa_run_keeps_stderr_and_an_auto_acceptance_is_labelled_the_cores() -> (
    None
):
    session, scripted = qa_session(
        qa_report(qa_stages={"stages": [], "failed_stage": None}, checks_run=[])
    )
    session.selection.qa_dispatch = "dispatch-qa-1"
    scripted.reply("qa run", None, stderr="ERROR: lane is leased", code=2)
    session.run_qa()
    assert session.view(Stage.QA).blockers == ("ERROR: lane is leased",)
    scripted.reply(
        "qa run",
        {
            "dispatch_id": "dispatch-qa-1",
            "state": "reported",
            "report": "/r.json",
            "auto_accepted": True,
        },
    )
    session.run_qa()
    row = next(
        r
        for r in session.view(Stage.QA).rows
        if r.label == "Автопринятие по политике ядра"
    )
    assert row.state is State.INFO
    assert {tab.stage: tab for tab in session.tabs()}[Stage.QA].state is State.OK


def test_lane_release_follows_the_actual_lease_not_a_guess() -> None:
    session, scripted = qa_session()
    view = session.view(Stage.QA)
    assert next(r for r in view.rows if r.label == "Lane").state is State.NOT_CHECKED
    scripted.reply("qa status", {"lease": None, "lease_stale": False, "queue": []})
    session.refresh_qa()
    lane = next(r for r in session.view(Stage.QA).rows if r.label == "Lane")
    assert lane.state is State.OK and "свободен" in lane.value
    scripted.reply(
        "qa status",
        {
            "lease": {"dispatch_id": "dispatch-qa-1", "pid": 7},
            "lease_stale": True,
            "queue": [{"d": 1}],
        },
    )
    session.refresh_qa()
    view = session.view(Stage.QA)
    lane = next(r for r in view.rows if r.label == "Lane")
    assert (
        lane.state is State.WARN
        and "просрочен" in lane.value
        and "dispatch-qa-1" in lane.value
    )
    assert row_value(view, "Очередь") == "1"
    scripted.reply("qa status", None, stderr="ERROR: store busy", code=2)
    session.refresh_qa()
    assert (
        next(r for r in session.view(Stage.QA).rows if r.label == "Lane").state
        is State.FAILED
    )


def test_qa_run_needs_confirmation_and_status_does_not() -> None:
    session, _ = qa_session()
    actions = {a.key: a for a in session.view(Stage.QA).actions}
    assert (
        actions["qa-run"].needs_confirmation
        and actions["qa-approve"].needs_confirmation
    )
    assert (
        not actions["qa-status"].needs_confirmation
        and not actions["qa-propose"].needs_confirmation
    )


# ----------------------------------------------------------------------------- Cleanup


def cleanup_plan(**overrides: object) -> dict[str, object]:
    plan: dict[str, object] = {
        "mode": "soft",
        "root": "/work/project/.harness",
        "min_age_hours": 24,
        "remove": [
            {
                "kind": "container",
                "path": "harness-dispatch-9-worker",
                "dispatch": "dispatch-9",
                "engine": "podman",
                "engine_id": "abc123",
            },
            {
                "kind": "network",
                "path": "harness-dispatch-9-net",
                "dispatch": "dispatch-9",
                "engine": "podman",
                "engine_id": "net123",
            },
            {
                "kind": "container",
                "path": "harness-dispatch-old-worker",
                "dispatch": "dispatch-old",
                "engine": "podman",
                "engine_id": "old123",
            },
            {"kind": "directory", "path": "/work/project/.harness/.sandboxes/runs/r1"},
            {"kind": "worktree", "path": "/work/wt-old", "branch": "feature/old"},
        ],
        "skipped": [
            {
                "path": "harness-dispatch-live",
                "reason": "worker is not stopped; harness never stops it: stop it explicitly (podman stop x) first",
            },
            {
                "path": "/work/project/.harness/.sandboxes/runs/young",
                "reason": "too young",
            },
        ],
    }
    plan.update(overrides)
    return plan


def expected_digest(plan: dict[str, object]) -> str:
    import hashlib

    payload = {key: plan[key] for key in ("mode", "root", "min_age_hours", "remove")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def cleanup_session() -> tuple[RouteSession, ScriptedCoordinator]:
    session, scripted = worker_session(
        status_document(
            running_execution(
                state="exited", exit={"exit_code": 0, "logs": "/logs/dispatch-9"}
            )
        )
    )
    session.refresh_worker()
    return session, scripted


def test_cleanup_without_a_preview_runs_nothing_and_apply_says_why() -> None:
    session, scripted = make_session()
    view = session.view(Stage.CLEANUP)
    apply = next(a for a in view.actions if a.key == "cleanup-apply")
    assert not apply.enabled and "превью" in apply.reason
    assert scripted.calls == []
    try:
        session.apply_cleanup()
    except PermissionError:
        pass
    else:
        raise AssertionError("apply needs a preview")


def test_cleanup_preview_is_one_soft_dry_run_with_no_apply_flag() -> None:
    session, scripted = cleanup_session()
    scripted.reply("cleanup", {"plan": cleanup_plan()})
    session.preview_cleanup()
    command = scripted.calls[-1]
    assert command[-4:] == ["cleanup", str(REPO), "--mode", "soft"]
    assert "--apply" not in command and "--confirm" not in command


def test_cleanup_shows_container_items_marks_the_current_dispatch_and_discloses_the_rest() -> (
    None
):
    session, scripted = cleanup_session()
    scripted.reply("cleanup", {"plan": cleanup_plan()})
    session.preview_cleanup()
    view = session.view(Stage.CLEANUP)
    assert row_value(view, "К удалению") == "5: контейнеры и сети 3, прочее 2"
    assert (
        row_value(view, "Не контейнерные пункты того же плана")
        == "2: directory 1, worktree 1"
    )
    containers = [r for r in view.rows if r.label in ("Контейнер", "Сеть")]
    assert len(containers) == 3
    assert (
        "текущий dispatch" in containers[0].value
        and "текущий dispatch" in containers[1].value
    )
    assert "текущий dispatch" not in containers[2].value
    assert row_value(view, "plan-digest") == expected_digest(cleanup_plan())
    assert any(
        "весь репозиторий" in note or "всего репозитория" in note for note in view.notes
    )
    assert any("не останавливается" in note for note in view.notes)


def test_protected_resources_keep_the_core_reason_verbatim() -> None:
    session, scripted = cleanup_session()
    scripted.reply("cleanup", {"plan": cleanup_plan()})
    session.preview_cleanup()
    view = session.view(Stage.CLEANUP)
    protected = next(r for r in view.rows if r.label == "Защищён")
    assert protected.state is State.WARN
    assert protected.value.startswith(
        "harness-dispatch-live\nworker is not stopped; harness never stops it"
    )
    assert row_value(view, "Прочие пропущенные пункты") == "1"


def test_saved_terminal_evidence_comes_from_execution_exit() -> None:
    session, _ = cleanup_session()
    view = session.view(Stage.CLEANUP)
    assert (
        row_value(view, "Сохранённые доказательства (execution.exit)")
        == "код выхода: 0\n/logs/dispatch-9"
    )
    fresh, _ = make_session()
    row = next(
        r for r in fresh.view(Stage.CLEANUP).rows if r.label.startswith("Сохранённые")
    )
    assert row.state is State.NOT_REPORTED


def test_apply_is_bound_to_the_previewed_plan_digest_and_reflects_the_real_result() -> (
    None
):
    session, scripted = cleanup_session()
    plan = cleanup_plan()
    scripted.reply("cleanup", {"plan": plan})
    session.preview_cleanup()
    scripted.reply(
        "cleanup",
        None,
    )
    scripted.replies["cleanup"] = (
        json.dumps({"plan": plan})
        + json.dumps(
            {
                "result": {
                    "removed": ["a", "b"],
                    "failed": [{"path": "/x", "reason": "busy"}],
                    "skipped": [],
                }
            }
        ),
        "",
        1,
    )
    result = session.apply_cleanup()
    command = scripted.calls[-1]
    assert command[-3:] == ["--apply", "--plan-digest", expected_digest(plan)]
    assert result.section("result") is not None
    view = session.view(Stage.CLEANUP)
    assert row_value(view, "Удалено").startswith("2")
    failed = next(r for r in view.rows if r.label == "Не удалось")
    assert failed.state is State.FAILED and "busy" in failed.value
    apply = next(a for a in view.actions if a.key == "cleanup-apply")
    assert not apply.enabled and "превью" in apply.reason  # the digest is spent


def test_a_plan_that_changed_refuses_the_apply_and_needs_a_new_preview() -> None:
    session, scripted = cleanup_session()
    scripted.reply("cleanup", {"plan": cleanup_plan()})
    session.preview_cleanup()
    scripted.reply(
        "cleanup",
        None,
        stderr="ERROR: cleanup plan changed; preview again before applying",
        code=2,
    )
    session.apply_cleanup()
    view = session.view(Stage.CLEANUP)
    assert view.blockers == (
        "ERROR: cleanup plan changed; preview again before applying",
    )
    assert session.cleanup.stale
    assert sum("cleanup" in call for call in scripted.calls) == 2
    try:
        session.apply_cleanup()
    except PermissionError:
        pass
    else:
        raise AssertionError("a spent digest must not be applied twice")


def test_a_failed_preview_is_shown_and_enables_no_apply() -> None:
    session, scripted = cleanup_session()
    scripted.reply(
        "cleanup", None, stderr="ERROR: storage root must not be a symlink", code=2
    )
    session.preview_cleanup()
    view = session.view(Stage.CLEANUP)
    assert view.blockers == ("ERROR: storage root must not be a symlink",)
    assert not next(a for a in view.actions if a.key == "cleanup-apply").enabled
    assert {tab.stage: tab for tab in session.tabs()}[
        Stage.CLEANUP
    ].state is State.FAILED


def test_an_empty_plan_has_nothing_to_apply() -> None:
    session, scripted = cleanup_session()
    scripted.reply("cleanup", {"plan": cleanup_plan(remove=[], skipped=[])})
    session.preview_cleanup()
    apply = next(
        a for a in session.view(Stage.CLEANUP).actions if a.key == "cleanup-apply"
    )
    assert not apply.enabled and "нечего удалять" in apply.reason


def test_apply_is_blocked_until_the_workers_terminal_evidence_is_saved() -> None:
    session, scripted = worker_session(
        status_document(running_execution(state="exited"))
    )
    session.refresh_worker()  # exit evidence is not reported
    scripted.reply("cleanup", {"plan": cleanup_plan()})
    session.preview_cleanup()
    apply = next(
        a for a in session.view(Stage.CLEANUP).actions if a.key == "cleanup-apply"
    )
    assert not apply.enabled and "доказательства worker не сохранены" in apply.reason
    scripted.reply(
        "dispatch status",
        status_document(
            running_execution(state="exited", exit={"exit_code": 1, "logs": "/l"})
        ),
    )
    session.refresh_worker()
    assert next(
        a for a in session.view(Stage.CLEANUP).actions if a.key == "cleanup-apply"
    ).enabled


def test_a_live_worker_is_never_offered_for_deletion_or_stopped() -> None:
    session, scripted = worker_session(status_document(running_execution()))
    session.refresh_worker()
    scripted.reply(
        "cleanup",
        {
            "plan": cleanup_plan(
                remove=[],
                skipped=[
                    {
                        "path": "harness-dispatch-9",
                        "reason": "its execution is running in the runtime",
                    }
                ],
            )
        },
    )
    session.preview_cleanup()
    view = session.view(Stage.CLEANUP)
    live = next(r for r in view.rows if r.label == "Worker текущего dispatch")
    assert live.state is State.WARN and "не будет остановлен" in live.value
    assert any(
        "its execution is running" in r.value for r in view.rows if r.label == "Защищён"
    )
    assert not any(
        "stop" in command
        for call in scripted.calls
        for command in call
        if command in ("stop", "kill", "rm")
    )


def test_cleanup_apply_needs_confirmation_and_preview_does_not() -> None:
    session, _ = make_session()
    actions = {a.key: a for a in session.view(Stage.CLEANUP).actions}
    assert (
        actions["cleanup-apply"].needs_confirmation
        and not actions["cleanup-preview"].needs_confirmation
    )


# ----------------------------------------------------------------------------- contract (#711)

from harness.console.coordinator_api import forbidden_in  # noqa: E402


def full_route() -> tuple[RouteSession, ScriptedCoordinator]:
    """A session that has used every call of the route with fixtures that carry a secret value."""
    session, scripted = verified_session()
    scripted.reply("dispatch propose", propose_document())
    scripted.reply(
        "dispatch create", {"dispatch_id": "dispatch-9", "state": "approved"}
    )
    scripted.reply("dispatch status", status_document(running_execution()))
    scripted.reply("qa status", {"lease": None, "lease_stale": False, "queue": []})
    scripted.reply("cleanup", {"plan": cleanup_plan()})
    session.propose()
    session.create("operator")
    session.refresh_worker()
    session.refresh_qa()
    scripted.reply("dispatch propose", qa_propose_document())
    scripted.reply(
        "dispatch create", {"dispatch_id": "dispatch-qa-1", "state": "approved"}
    )
    session.propose_qa()
    session.create_qa("operator")
    session.preview_cleanup()
    return session, scripted


def test_no_secret_value_reaches_any_rendered_view_or_argv_of_the_route() -> None:
    session, scripted = full_route()
    shown = "\n".join(render(session.view(stage)) for stage in Stage)
    shown += "\n".join(f"{t.title} {t.reason}" for t in session.tabs())
    shown += "\n".join(f"{k} {v}" for k, v in session.executor_context())
    assert SECRET not in shown
    assert all(SECRET not in token for call in scripted.calls for token in call)


def test_no_call_of_the_route_carries_a_forbidden_flag_or_an_engine_command() -> None:
    _, scripted = full_route()
    assert scripted.calls
    for call in scripted.calls:
        assert forbidden_in(call) is None, call
        assert not {"docker", "podman", "--docker", "--confirm"} & set(call)


def test_a_call_that_gave_no_document_never_yields_a_successful_dependent_row() -> None:
    cases = (
        (Stage.PREFLIGHT, "dispatch preflight"),
        (Stage.WORKER, "dispatch status"),
        (Stage.CLEANUP, "cleanup"),
    )
    for stage, key in cases:
        for stderr, code in (
            ("ERROR: boom", 2),
            ("", 0),
        ):  # a failure, and a silent success
            session, scripted = make_session()
            session.select("batch-1")
            session.selection.dispatch = "dispatch-9"
            scripted.reply(key, None, stderr=stderr, code=code)
            session.recheck() if stage is Stage.PREFLIGHT else session.refresh_worker() if stage is Stage.WORKER else session.preview_cleanup()
            view = session.view(stage)
            assert not any(
                row.state is State.OK for row in view.rows if row.label != "Dispatch"
            ), (stage, stderr)


def test_unparsed_and_unavailable_outcomes_are_shown_as_such() -> None:
    session, scripted = make_session()
    session.select("batch-1")
    scripted.replies["dispatch preflight"] = ("{not json", "", 0)
    session.recheck()
    first = session.view(Stage.PREFLIGHT).rows[0]
    assert first.state is State.FAILED and first.value.startswith("unparsed")

    def broken(*args: object, **kwargs: object) -> "subprocess.CompletedProcess[str]":
        raise OSError("no interpreter")

    down = RouteSession(REPO, broken)
    down.select("batch-1")
    down.recheck()
    assert (
        down.view(Stage.PREFLIGHT)
        .rows[0]
        .value.startswith("unavailable: no interpreter")
    )


def test_pending_unknown_and_stale_states_are_distinct_marks() -> None:
    marks = {
        mark(s)
        for s in (
            State.PENDING,
            State.UNKNOWN,
            State.WARN,
            State.NOT_CHECKED,
            State.NOT_REPORTED,
        )
    }
    assert len(marks) == 5


def test_a_long_digest_path_and_log_line_are_kept_whole_in_every_stage() -> None:
    long_path = "/work/" + "deep-directory/" * 20 + "file.log"
    digest = "sha256:" + "9" * 64
    execution = running_execution(
        launch={"images": {"worker": digest}, "labels": {}, "logs": long_path},
        exit={"exit_code": 3, "logs": long_path},
        state="exited",
    )
    session, scripted = worker_session(status_document(execution))
    session.refresh_worker()
    text = render(session.view(Stage.WORKER))
    assert long_path in text and digest in text and "…" not in text
