"""The built-in docker executor at seam 1: the coordinator CLI as its own process, the real
``harness-runtime`` and a scripted ``podman`` (ADR 0022, ADR 0025).

The runtime's ``PATH`` holds only the scripted engine, so no ``docker`` is reachable: every engine
command recorded here is one the runtime ran, and Python never builds an engine argv or starts an
engine itself.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol, cast

import pytest

from harness.json_types import JsonObject
from harness.orchestration import container_executor, runtime_access
from tests.orchestration.runtime_store_support import Supervised
from tests.orchestration.scripted_engine import WORKER_ID as WORKER_CONTAINER
from tests.orchestration.scripted_engine import PROXY_ID, ScriptedEngine, docker_info

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="the docker executor runs only on Linux",
)

WORKER_TAG = "harness-worker:local"
# Podman prints a bare image id; the brief pins ``sha256:<id>`` as Docker prints it.
WORKER_BARE = "a" * 64
WORKER_ID = f"sha256:{WORKER_BARE}"
PROXY_TAG = "harness-proxy:local"
PROXY_BARE = "b" * 64
PROXY_IMAGE_ID = f"sha256:{PROXY_BARE}"
SECRET_NAME = "HARNESS_TEST_API_KEY"
SECRET = "synthetic-secret-value-5d1e"
# The runtime stops after the engine created and started the worker, before its receipt.
PAUSE_AT_LAUNCHED = {"HARNESS_RUNTIME_TEST_PAUSE_AT": "execution.launch:launched"}


def policy(**defaults: object) -> JsonObject:
    return {
        "defaults": {
            "mode": "sandbox",
            "container": {"engine": "podman", "worker_image": WORKER_TAG},
            "environment": [SECRET_NAME],
            **defaults,
        }
    }


class Podman(Protocol):
    def __call__(
        self,
        *,
        access_policy: JsonObject | None = ...,
        env: dict[str, str] | None = ...,
        create: bool = ...,
        binary: str = ...,
        rootless: bool = ...,
    ) -> tuple[Supervised, ScriptedEngine]: ...


def engine_env(engine: ScriptedEngine) -> dict[str, str]:
    """The runtime environment whose only engine is ``engine``, without debug hooks."""
    return {"PATH": str(engine.bin), SECRET_NAME: SECRET}


@pytest.fixture
def podman(tmp_path: Path) -> Iterator[Podman]:
    """A cut-over repository under the docker executor, served by a runtime whose only engine is
    a scripted ``binary`` (rootful ``podman`` by default) that holds the worker and proxy images."""
    made: list[Supervised] = []

    def make(
        *,
        access_policy: JsonObject | None = None,
        env: dict[str, str] | None = None,
        create: bool = True,
        binary: str = "podman",
        rootless: bool = False,
    ) -> tuple[Supervised, ScriptedEngine]:
        root = tmp_path / f"s{len(made)}"
        engine = ScriptedEngine(root / "engine", binary)
        if rootless:
            engine.update(lambda state: state.update(info=docker_info(rootless=True)))
        # Podman prints a bare image id, Docker ``sha256:<id>``.
        images = (
            {WORKER_TAG: WORKER_BARE, PROXY_TAG: PROXY_BARE}
            if binary == "podman"
            else {WORKER_TAG: WORKER_ID, PROXY_TAG: PROXY_IMAGE_ID}
        )
        engine.update(lambda state: state["images"].update(images))
        repo = Supervised(
            root,
            env={**engine_env(engine), **(env or {})},
            access_policy=access_policy
            or policy(container={"engine": binary, "worker_image": WORKER_TAG}),
            create=create,
        )
        made.append(repo)
        return repo, engine

    yield make
    for repo in made:
        repo.close()


def answer(result: object) -> JsonObject:
    assert getattr(result, "returncode") == 0, getattr(result, "stderr")
    parsed: JsonObject = json.loads(getattr(result, "stdout"))
    return parsed


def dig(value: object, *keys: str) -> object:
    """The member at ``keys`` of nested JSON objects."""
    for key in keys:
        assert isinstance(value, dict), value
        value = value[key]
    return value


def flag_values(argv: list[str], flag: str) -> list[str]:
    return [value for name, value in zip(argv, argv[1:]) if name == flag]


def assert_only_podman(engine: ScriptedEngine) -> None:
    calls = engine.calls()
    assert calls and all(call[0] == "podman" for call in calls), calls
    assert not any("volume" in call for call in calls), calls
    assert SECRET not in json.dumps(calls)


def test_the_runtime_launches_the_approved_worker_with_the_adr_0025_argv(
    podman: Podman,
) -> None:
    repo, engine = podman()
    brief = repo.brief
    assert brief["runtime_images"] == {"worker": WORKER_ID, "proxy": None}
    runtime_access.validate_binding(brief)

    sent = answer(repo.send())

    execution = sent["execution"]
    assert isinstance(execution, dict)
    assert execution["kind"] == "container"
    assert execution["engine"] == "podman"
    assert execution["container_id"] == WORKER_CONTAINER
    assert repo.launches() == [], "the adapter ran on the host"
    [create] = [call for call in engine.calls() if call[1] == "create"]
    assert create[:4] == ["podman", "create", "--pull", "never"]
    assert flag_values(create, "--network") == ["none"]
    assert flag_values(create, "--cap-drop") == ["ALL"]
    assert flag_values(create, "--security-opt") == ["no-new-privileges"]
    requirements = dig(brief, "runtime_access", "requirements")
    assert isinstance(requirements, list)
    roots = {str(dig(item, "path")) for item in requirements}
    mounted = {
        value.split(",")[1].removeprefix("source=")
        for value in flag_values(create, "--mount")
    }
    assert mounted == roots
    assert SECRET_NAME in flag_values(create, "--env")
    assert flag_values(create, "--entrypoint") == [sys.executable]
    assert create[create.index(WORKER_ID) + 1] == str(repo.adapter)
    assert ["podman", "start", WORKER_CONTAINER] in engine.calls()
    assert_only_podman(engine)
    assert repo.wait_execution("running")["container_id"] == WORKER_CONTAINER


def test_status_follows_the_container_and_its_exit_removes_it_with_podman(
    podman: Podman,
) -> None:
    repo, engine = podman()
    answer(repo.send())
    repo.wait_execution("running")

    status = answer(repo.run("dispatch", "status", "--dispatch", repo.dispatch))
    [entry] = status["dispatches"]
    assert entry["execution"]["state"] == "running"
    assert "worker" not in entry

    def exit_worker(state: JsonObject) -> None:
        state["objects"][WORKER_CONTAINER].update(status="exited", exit_code=3)

    engine.update(exit_worker)
    ended = repo.wait_execution("exited")

    assert dig(ended, "exit", "exit_code") == 3
    stdout = Path(str(dig(ended, "receipt", "logs", "stdout")))
    assert stdout.read_text(encoding="utf-8") == "worker stdout\n"
    assert engine.state()["objects"] == {}
    assert any(
        call[1] == "logs" and call[-1] == WORKER_CONTAINER for call in engine.calls()
    )
    assert_only_podman(engine)


def test_an_image_rebuilt_after_approval_refuses_the_send_before_any_launch(
    podman: Podman,
) -> None:
    repo, engine = podman()
    engine.update(lambda state: state["images"].update({WORKER_TAG: "c" * 64}))

    refused = repo.send()

    assert refused.returncode != 0
    assert "changed after dispatch propose" in refused.stderr
    assert not any(call[1] in {"create", "start"} for call in engine.calls())
    assert repo.execution() is None
    assert repo.status()["state"] == "approved"


@pytest.mark.fault_injection
def test_an_image_rebuilt_after_the_coordinator_check_is_approval_mismatch_in_the_runtime_before_any_create(
    podman: Podman,
) -> None:
    repo, engine = podman(
        env={"HARNESS_RUNTIME_TEST_PAUSE_AT": "execution.launch:before-begin"}
    )
    send = repo.start_send()
    repo.runtime.wait_paused("execution.launch:before-begin")

    # The coordinator checked the pinned image already; the image changes before the runtime does.
    engine.update(lambda state: state["images"].update({WORKER_TAG: "c" * 64}))
    repo.runtime.resume()
    _, err = send.communicate(timeout=60)

    assert send.returncode == 2, err
    remedy = next(line for line in err.splitlines() if line.startswith("REMEDY:"))
    assert remedy.startswith("REMEDY: [approval_mismatch] "), err
    assert not any(
        call[1] in {"create", "start"} or call[1:3] == ["network", "create"]
        for call in engine.calls()
    )
    assert repo.execution() is None


def test_a_name_missing_from_the_runtime_environment_blocks_propose_by_its_name(
    podman: Podman,
) -> None:
    repo, engine = podman(
        access_policy=policy(environment=[SECRET_NAME, "HARNESS_TEST_UNSET_NAME"]),
        create=False,
    )

    refused = repo.propose()

    assert refused.returncode != 0
    assert "no variable named: HARNESS_TEST_UNSET_NAME" in refused.stderr
    assert not any(call[1] in {"create", "start"} for call in engine.calls())


def test_a_plan_root_that_holds_the_runtime_directory_is_policy_denied_before_the_engine(
    podman: Podman,
) -> None:
    repo, engine = podman(create=False)
    config_path = repo.repo / ".harness" / "orchestration.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["access_policy"] = policy(
        filesystem=[
            {"resource": "cache", "path": str(repo.runtime.xdg), "access": "write"}
        ]
    )
    config_path.write_text(json.dumps(config), encoding="utf-8")

    refused = repo.propose()

    assert refused.returncode != 0
    assert "policy_denied" in refused.stderr
    assert engine.calls() == []


@pytest.mark.fault_injection
@pytest.mark.parametrize("form", ["direct", "symlink"])
def test_a_plan_root_holding_an_engine_socket_is_policy_denied_before_any_engine_call(
    podman: Podman, tmp_path: Path, form: str
) -> None:
    repo, engine = podman(create=False)
    # Rootless Podman keeps its socket below $XDG_RUNTIME_DIR/podman of the runtime's user.
    sockets = repo.runtime.xdg / "podman"
    sockets.mkdir()
    root = sockets
    if form == "symlink":
        root = tmp_path / "engine-link"
        root.symlink_to(sockets, target_is_directory=True)
    config_path = repo.repo / ".harness" / "orchestration.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["access_policy"] = policy(
        filesystem=[{"resource": "cache", "path": str(root), "access": "write"}]
    )
    config_path.write_text(json.dumps(config), encoding="utf-8")

    refused = repo.propose()

    assert refused.returncode == 2, refused.stderr
    remedy = next(
        line for line in refused.stderr.splitlines() if line.startswith("REMEDY:")
    )
    assert remedy.startswith("REMEDY: [policy_denied] "), refused.stderr
    assert str(sockets) in refused.stderr
    assert engine.calls() == []


def test_the_executor_has_no_engine_boundary_of_its_own() -> None:
    source = Path(container_executor.__file__).read_text(encoding="utf-8")

    assert "run_engine" not in source
    assert "subprocess" not in source
    assert not hasattr(container_executor.DockerExecutor, "handoff")


def _stream(*records: JsonObject) -> str:
    return "".join(json.dumps(record) + "\n" for record in records)


def _script_stream(engine: ScriptedEngine, stream: str) -> None:
    engine.update(lambda state: state.update(worker_stdout=stream))


def test_a_running_container_streams_its_events_to_dispatch_observe(
    podman: Podman,
) -> None:
    """#1014, criterion 4: the runtime keeps a snapshot of the running worker's stdout, and
    ``dispatch observe`` reads its stream-json events from it."""
    repo, engine = podman()
    _script_stream(
        engine,
        _stream(
            {"type": "system", "subtype": "init", "model": "sonnet"},
            {"type": "result", "subtype": "success", "result": "done"},
        ),
    )
    answer(repo.send())
    repo.wait_execution("running")

    observed = answer(repo.run("dispatch", "observe", "--dispatch", repo.dispatch))

    assert observed["stream_state"] == "connected", observed
    texts = json.dumps(observed["events"])
    assert "Runtime session connected" in texts


def test_a_running_container_writer_is_attested_on_the_host_and_its_report_accepted(
    podman: Podman,
) -> None:
    """#1014, criterion 2: no runtime socket in the container, yet the host records the
    self-report from the init event and the plan's checkout, so ``report submit`` passes."""
    from tests.orchestration.runtime_store_support import architect_report_file

    repo, engine = podman()
    _script_stream(
        engine, _stream({"type": "system", "subtype": "init", "model": "sonnet"})
    )
    answer(repo.send())
    repo.wait_execution("running")

    answer(repo.run("dispatch", "status", "--dispatch", repo.dispatch))

    status = repo.status()
    assert status["state"] == "working", status
    assert dig(status, "model_self_report", "match") is True
    assert dig(status, "model_self_report", "source") == "container-host"
    attestation = status["worktree_attestation"]
    assert isinstance(attestation, dict)
    assert attestation["match"] is True
    assert attestation["source"] == "container-host"
    evidence = attestation["container"]
    assert evidence == {
        "container_id": WORKER_CONTAINER,
        "images": {"worker": WORKER_ID, "proxy": None},
        "checkout": next(
            dig(item, "path")
            for item in cast(
                list[object], dig(repo.brief, "runtime_access", "requirements")
            )
            if dig(item, "resource") == "checkout"
        ),
        "executor": "docker",
    }
    # A repeat records nothing new.
    answer(repo.run("dispatch", "status", "--dispatch", repo.dispatch))
    assert dig(repo.status(), "model_self_report", "reported_at") == dig(
        status, "model_self_report", "reported_at"
    )

    report = architect_report_file(repo.repo, repo.dispatch, repo.brief)
    submitted = answer(repo.run("report", "submit", "--file", str(report)))
    assert submitted["awaiting"] == "execution-exit"
    engine.update(
        lambda state: state["objects"][WORKER_CONTAINER].update(status="exited")
    )
    repo.wait_execution("exited")
    answer(repo.run("dispatch", "status", "--dispatch", repo.dispatch))
    assert repo.status()["state"] == "reported"


def test_a_container_init_event_of_another_model_blocks_the_dispatch(
    podman: Podman,
) -> None:
    repo, engine = podman()
    _script_stream(
        engine, _stream({"type": "system", "subtype": "init", "model": "opus"})
    )
    answer(repo.send())
    repo.wait_execution("running")

    waited = answer(
        repo.run("dispatch", "wait", "--dispatch", repo.dispatch, "--timeout", "5")
    )

    assert waited["event"] == "model_mismatch", waited
    status = repo.status()
    assert dig(status, "model_self_report", "source") == "container-host"
    assert dig(status, "model_self_report", "match") is False
    # The store refuses ``blocked`` while the execution runs; its exit blocks the dispatch.
    assert status["state"] == "dispatched"
    engine.update(
        lambda state: state["objects"][WORKER_CONTAINER].update(status="exited")
    )
    repo.wait_execution("exited")
    answer(repo.run("dispatch", "status", "--dispatch", repo.dispatch))
    assert repo.status()["state"] == "blocked"


def test_a_container_without_an_init_event_gets_heartbeats_but_no_self_report(
    podman: Podman,
) -> None:
    repo, engine = podman()
    answer(repo.send())
    repo.wait_execution("running")
    before = repo.status()["heartbeat_at"]

    answer(repo.run("dispatch", "status", "--dispatch", repo.dispatch))

    status = repo.status()
    assert "model_self_report" not in status
    assert status["state"] == "dispatched"
    assert status["heartbeat_at"] != before
    assert status["heartbeat_note"] == "container running"


def test_a_container_writer_that_exits_before_report_submit_keeps_its_staged_report(
    podman: Podman,
) -> None:
    """#1014, criterion 2: the worker stages its report and exits before the coordinator submits
    it. The exit does not block the dispatch: dispatch wait names the staged report, and report
    submit records it."""
    from tests.orchestration.runtime_store_support import architect_report_file

    repo, engine = podman()
    _script_stream(
        engine, _stream({"type": "system", "subtype": "init", "model": "sonnet"})
    )
    answer(repo.send())
    repo.wait_execution("running")
    answer(repo.run("dispatch", "status", "--dispatch", repo.dispatch))
    staged = Path(str(repo.brief["report_staging_path"]))
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(
        architect_report_file(repo.repo, repo.dispatch, repo.brief).read_bytes()
    )
    engine.update(
        lambda state: state["objects"][WORKER_CONTAINER].update(status="exited")
    )
    repo.wait_execution("exited")

    waited = answer(
        repo.run("dispatch", "wait", "--dispatch", repo.dispatch, "--timeout", "5")
    )

    assert waited["event"] == "report_staged", waited
    assert waited["report_staging_path"] == str(staged)
    assert repo.status()["state"] == "working"
    answer(repo.run("report", "submit", "--file", str(staged)))
    answer(repo.run("dispatch", "status", "--dispatch", repo.dispatch))
    assert repo.status()["state"] == "reported"


def test_a_container_that_exits_without_a_staged_report_is_blocked(
    podman: Podman,
) -> None:
    repo, engine = podman()
    _script_stream(
        engine, _stream({"type": "system", "subtype": "init", "model": "sonnet"})
    )
    answer(repo.send())
    repo.wait_execution("running")
    answer(repo.run("dispatch", "status", "--dispatch", repo.dispatch))
    engine.update(
        lambda state: state["objects"][WORKER_CONTAINER].update(status="exited")
    )
    repo.wait_execution("exited")

    answer(repo.run("dispatch", "status", "--dispatch", repo.dispatch))

    status = repo.status()
    assert status["state"] == "blocked"
    assert dig(status, "runtime_failure", "kind") == "worker-exited-without-report"


def killed_at_launch(
    repo: Supervised,
    engine: ScriptedEngine,
    edit: Callable[[JsonObject], None] | None = None,
) -> tuple[int, str, str]:
    """``dispatch send`` whose runtime is SIGKILLed after the engine started the worker and
    before the receipt; ``edit`` changes the engine state while no runtime runs, and a new
    runtime in the same directory serves the repeated request. The send's code and streams."""
    send = repo.start_send()
    repo.runtime.wait_paused("execution.launch:launched")
    repo.runtime.kill()
    if edit is not None:
        engine.update(edit)
    repo.restart_runtime(env=engine_env(engine))
    out, err = send.communicate(timeout=60)
    return send.returncode, out, err


def verbs(engine: ScriptedEngine, verb: str) -> list[list[str]]:
    return [call for call in engine.calls() if call[1] == verb]


def assert_adopted(
    repo: Supervised,
    engine: ScriptedEngine,
    sent: tuple[int, str, str],
    *,
    binary: str = "podman",
    proxy_id: str | None = None,
) -> None:
    """The repeated send answers a receipt of the existing worker: no second create or start,
    no removal, and the lease belongs to the new runtime."""
    code, out, err = sent
    assert code == 0, err
    receipt = json.loads(out)["execution"]
    assert receipt["adopted"] is True, receipt
    assert receipt["container_id"] == WORKER_CONTAINER
    assert receipt["engine"] == binary
    assert receipt["proxy_id"] == proxy_id
    containers = 1 if proxy_id is None else 2
    assert len(verbs(engine, "create")) == containers, engine.calls()
    assert len(verbs(engine, "start")) == containers, engine.calls()
    assert engine.removals() == []
    assert all(call[0] == binary for call in engine.calls())
    assert (
        dig(repo.execution(), "lease", "owner", "identity", "pid")
        == repo.runtime.process.pid
    )


@pytest.mark.fault_injection
@pytest.mark.parametrize(
    ("binary", "rootless"),
    [("podman", False), ("docker", False), ("docker", True)],
    ids=["podman", "docker-rootful", "docker-rootless"],
)
def test_a_runtime_killed_between_container_launch_and_receipt_adopts_the_running_worker_without_a_second_create(
    podman: Podman, binary: str, rootless: bool
) -> None:
    repo, engine = podman(env=PAUSE_AT_LAUNCHED, binary=binary, rootless=rootless)

    sent = killed_at_launch(repo, engine)

    assert_adopted(repo, engine, sent, binary=binary)


@pytest.mark.fault_injection
@pytest.mark.parametrize("status", ["paused", "restarting"])
def test_a_runtime_killed_at_container_launch_adopts_a_paused_or_restarting_worker(
    podman: Podman, status: str
) -> None:
    repo, engine = podman(env=PAUSE_AT_LAUNCHED)

    def worker_status(state: JsonObject) -> None:
        state["objects"][WORKER_CONTAINER].update(status=status)

    sent = killed_at_launch(repo, engine, worker_status)

    assert_adopted(repo, engine, sent)


def proxy_policy() -> JsonObject:
    """A plan that reaches one host through the egress proxy of the worker."""
    return policy(
        container={
            "engine": "podman", "worker_image": WORKER_TAG, "proxy_image": PROXY_TAG,
        },
        network={"hosts": ["api.example.com"]},
    )


@pytest.mark.fault_injection
def test_a_runtime_killed_at_container_launch_adopts_the_worker_and_its_egress_proxy(
    podman: Podman,
) -> None:
    repo, engine = podman(access_policy=proxy_policy(), env=PAUSE_AT_LAUNCHED)
    assert repo.brief["runtime_images"] == {"worker": WORKER_ID, "proxy": PROXY_IMAGE_ID}

    sent = killed_at_launch(repo, engine)

    assert_adopted(repo, engine, sent, proxy_id=PROXY_ID)


@pytest.mark.fault_injection
def test_a_worker_that_exited_before_its_receipt_keeps_its_logs_and_its_launch_is_lost_without_a_second_create(
    podman: Podman,
) -> None:
    repo, engine = podman(access_policy=proxy_policy(), env=PAUSE_AT_LAUNCHED)

    def worker_exited(state: JsonObject) -> None:
        state["objects"][WORKER_CONTAINER].update(status="exited", exit_code=0)

    code, _, err = killed_at_launch(repo, engine, worker_exited)

    assert code == 2, err
    assert "left no running labelled worker; never relaunched" in err, err
    assert dig(repo.execution(), "state") == "lost"
    [(state, result)] = repo.rows(
        "SELECT state, result_json FROM operations WHERE operation = 'execution.launch'"
    )
    assert state == "failed"
    assert json.loads(str(result))["code"] == "engine_unavailable", result
    calls = engine.calls()
    created = sorted(
        create[create.index("--name") + 1] for create in verbs(engine, "create")
    )
    [worker_name, proxy_name] = created
    assert proxy_name == f"{worker_name}-proxy", created
    roles = {
        worker_name: "worker", WORKER_CONTAINER: "worker",
        proxy_name: "proxy", PROXY_ID: "proxy",
    }
    removals = engine.removals()
    assert [roles.get(call[-1], "network") for call in removals] == [
        "worker", "proxy", "network", "network",
    ], removals
    assert all(call[1] == "network" for call in removals[2:]), removals
    assert calls.index(["podman", "logs", WORKER_CONTAINER]) < calls.index(removals[0])
    assert engine.state()["objects"] == {}
