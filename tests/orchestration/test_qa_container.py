"""Container QA at seam 1 (ADR 0022, section 3; ADR 0025): ``qa run`` of the coordinator CLI as
its own process, the real ``harness-runtime``, real Git worktrees and the real store; only the
container engine is the scripted ``podman`` on the runtime's ``PATH``.

Every QA command runs in its own foreground ``run --rm --init`` container that the runtime starts;
Python builds no engine argv. The streams of each command come back as separate stage evidence
with the command's real exit code, and the classified outcome decides the report: a failed gate is
``failed``, tooling, timeout and unknown endings are ``blocked`` with their domain, and an
infrastructure ending leaves no report but a new attempt of the same dispatch.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import pytest

from harness.json_types import JsonObject
from tests.orchestration import test_coordinator as coordinator_tests
from tests.orchestration.runtime_store_support import (
    STATE_REL,
    ServingRuntime,
    coordinator_popen,
    coordinator_with,
    migrate,
    store_call,
    store_records,
)
from tests.orchestration.scripted_engine import ScriptedEngine, podman_info

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="container QA runs only on Linux",
)

WORKER_TAG = "harness-worker:local"
WORKER_BARE = "a" * 64
GATE = ["make lint", "make test", "make docs"]
PREPARATION = ["make bootstrap"]
SECRET_NAME = "HARNESS_TEST_QA_TOKEN"
SECRET = "synthetic-qa-secret-7f3a"
PROXY_TAG = "harness-proxy:local"


def _git(repo: Path, *arguments: str) -> None:
    coordinator_tests._git(repo, *arguments)


class ContainerQa:
    """A cut-over repository whose approved QA dispatch pins a container ``operations.qa`` plan,
    the runtime that serves it and the scripted engine on its ``PATH``.

    ``engine``, the image tags and ``gate`` default to the scripted Podman setup; with
    ``scripted_engine=False`` the runtime keeps the host ``PATH`` and its real engine (#710)."""

    def __init__(
        self,
        tmp: Path,
        *,
        preparation: list[str] | None = None,
        timeout: int = 600,
        hosts: list[str] | None = None,
        cache: Path | None = None,
        lease_ttl: int | None = None,
        engine: str = "podman",
        worker_tag: str = WORKER_TAG,
        proxy_tag: str = PROXY_TAG,
        gate: list[str] | None = None,
        scripted_engine: bool = True,
        selinux: bool = False,
    ) -> None:
        gate = GATE if gate is None else gate
        self.fx = coordinator_tests.CoordinatorRetryRoutingTests()
        self.fx.setUp()
        repo = self.repo = self.fx.repo
        (repo / ".harness/project.json").write_text(
            json.dumps({"qa_gate_commands": gate}), encoding="utf-8"
        )
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "declare the QA gate")
        _git(repo, "push", "origin", "master")
        self.fx.state_dir = repo / STATE_REL
        self.batch = str(self.fx._create_batch()["batch_id"])
        self.fx._accepted_architect(self.batch)
        self.candidate = self.fx._accepted_candidate(self.batch)
        self.fx._reported_review(self.batch, self.candidate)
        self.fx._decide(self.batch, "accept")
        container: JsonObject = {"engine": engine, "worker_image": worker_tag}
        if hosts:
            container["proxy_image"] = proxy_tag
        qa: JsonObject = {"container": container, "environment": [SECRET_NAME]}
        if hosts is not None:
            qa["network"] = {"hosts": hosts}
        if cache is not None:
            qa["filesystem"] = [{"resource": "cache", "path": str(cache), "access": "write"}]
        config: JsonObject = {
            "access_policy": {
                "defaults": {"mode": "sandbox", "container": container},
                "operations": {"qa": qa},
            },
            "extensions": {"runtime_access": "docker"},
            "verification_commands": gate,
            "execution_policy": {
                "qa_command_timeout_seconds": timeout,
                "stop_grace_seconds": 1,
                "dispatch_poll_interval_seconds": 1,
            },
        }
        if lease_ttl is not None:
            config["lease_ttl_seconds"] = lease_ttl
        if preparation is not None:
            config["qa_preparation"] = preparation
            config["qa_environment_probes"] = ["probe registry"]
            config["qa_project_file_checks"] = ["check lock"]
        (repo / ".harness/orchestration.json").write_text(
            json.dumps(config), encoding="utf-8"
        )
        (repo / ".harness/.sandboxes/scratch").mkdir(parents=True, exist_ok=True)
        self.engine = ScriptedEngine(tmp / "engine", engine)
        self.engine.update(
            lambda state: state["images"].update({worker_tag: WORKER_BARE, proxy_tag: "b" * 64})
        )
        if selinux:
            # The engine facts the plan pins are those before propose.
            self.engine.update(lambda state: state.update(info=podman_info(selinux=True)))
        assert migrate(repo).returncode == 0
        engine_path = {"PATH": str(self.engine.bin)} if scripted_engine else {}
        self.environ = {**engine_path, SECRET_NAME: SECRET}
        self.runtime = ServingRuntime(repo, env=self.environ)
        self.dispatch = self.create()

    def run(self, *command: str) -> tuple[int, JsonObject | None, str]:
        result = coordinator_with(self.repo, self.runtime, *command)
        parsed = json.loads(result.stdout) if result.returncode == 0 else None
        return result.returncode, parsed, result.stderr

    def create(self) -> str:
        fields = [
            "--batch", self.batch, "--role", "qa", "--candidate-commit", self.candidate,
            "--runtime", "claude", "--model", "sonnet", "--effort", "high",
        ]  # fmt: skip
        code, proposal, err = self.run("dispatch", "propose", *fields)
        assert code == 0 and proposal is not None, err
        code, created, err = self.run(
            "dispatch", "create", *fields,
            "--transition-digest", str(proposal["transition_digest"]),
            "--approved-by", "Malove", "--approved-at", self.fx.APPROVED_AT,
        )  # fmt: skip
        assert code == 0 and created is not None, err
        self.brief: JsonObject = created["brief"]
        assert "qa_execution" in self.brief, self.brief
        return str(self.brief["dispatch_id"])

    def qa_run(self) -> tuple[int, JsonObject | None, str]:
        return self.run("qa", "run", "--dispatch", self.dispatch)

    def attempts(self) -> list[JsonObject]:
        """The ``qa-lane/attempts`` records of the dispatch, read from the store."""
        answer = store_call(self.repo, self.runtime, "state.read", {"collections": ["qa-lane"]})
        records = answer["records"]
        assert isinstance(records, dict)
        return [
            record
            for path, record in records.items()
            if path.startswith("qa-lane/attempts/")
            and isinstance(record, dict)
            and record.get("dispatch_id") == self.dispatch
        ]

    def status(self) -> JsonObject:
        path = f"dispatch-status/{self.dispatch}.json"
        return store_records(self.repo, self.runtime, path)[path]

    def report(self) -> JsonObject:
        path = f"reports/{self.dispatch}.json"
        return store_records(self.repo, self.runtime, path)[path]

    def lane(self) -> JsonObject:
        code, lane, err = self.run("qa", "status")
        assert code == 0 and lane is not None, err
        return lane

    def execution(self) -> JsonObject:
        answer = store_call(
            self.repo, self.runtime, "execution.observe", {"dispatch_id": self.dispatch}
        )
        execution = answer["execution"]
        assert isinstance(execution, dict), answer
        return execution

    def close(self) -> None:
        self.runtime.stop()
        self.fx.tearDown()


class Make(Protocol):
    def __call__(
        self,
        *,
        preparation: list[str] | None = ...,
        timeout: int = ...,
        hosts: list[str] | None = ...,
        cache: Path | None = ...,
        lease_ttl: int | None = ...,
        selinux: bool = ...,
    ) -> ContainerQa: ...


@pytest.fixture
def qa(tmp_path: Path) -> Iterator[Make]:
    made: list[ContainerQa] = []

    def make(
        *,
        preparation: list[str] | None = None,
        timeout: int = 600,
        hosts: list[str] | None = None,
        cache: Path | None = None,
        lease_ttl: int | None = None,
        selinux: bool = False,
    ) -> ContainerQa:
        root = tmp_path / f"q{len(made)}"
        options = {
            "timeout": timeout,
            "hosts": hosts,
            "cache": cache,
            "lease_ttl": lease_ttl,
            "selinux": selinux,
        }
        made.append(ContainerQa(root, preparation=preparation, **options))  # type: ignore[arg-type]
        return made[-1]

    yield make
    for item in made:
        item.close()


def _flag(argv: list[str], flag: str) -> list[str]:
    return [value for name, value in zip(argv, argv[1:]) if name == flag]


def test_each_command_runs_in_its_own_container_and_a_failed_gate_fails_the_report(
    qa: Make,
) -> None:
    repo = qa()
    repo.engine.script("gate-1", stdout="lint ok\n", stderr="lint warn\n", exit_code=0)
    repo.engine.script("gate-2", stdout="2 failed\n", stderr="trace\n", exit_code=1)

    code, result, err = repo.qa_run()

    assert code == 0 and result is not None, err
    report = repo.report()
    assert report["outcome"] == "failed"
    assert [(c["command"], c["result"]) for c in report["checks_run"]] == [
        ("make lint", "pass"), ("make test", "fail"), ("make docs", "not_run"),
    ]
    runs = repo.engine.runs()
    assert len(runs) == 2
    for run in runs:
        assert run[:4] == ["podman", "run", "--rm", "--init"]
        assert _flag(run, "--network") == ["none"]
        assert "--detach" not in run and not any("volume" in part for part in run)
    # The approved command text runs verbatim through /bin/sh -c of the pinned image.
    images = repo.brief["runtime_images"]
    assert isinstance(images, dict)
    assert _flag(runs[0], "--entrypoint") == ["/bin/sh"]
    assert runs[0][-3:] == [images["worker"], "-c", "make lint"]
    assert runs[1][-3:] == [images["worker"], "-c", "make test"]
    assert not any(call[1] in ("commit", "push", "fetch") for call in repo.engine.calls())
    lane = repo.lane()
    assert (lane["lease"], lane["queue"]) == (None, [])
    execution = repo.execution()
    assert (execution["kind"], execution["state"], execution["attempt"]) == ("qa", "exited", 1)
    records = execution["exit"]["commands"]
    assert [(r["stage_id"], r["result"], r["exit_code"]) for r in records] == [
        ("gate-1", "ran", 0), ("gate-2", "ran", 1), ("gate-3", "not_run", None),
    ]


_JUNIT = (
    "<testsuites><testsuite>"
    '<testcase classname="services.x" name="test_value[1]"><failure message="m"/></testcase>'
    '<testcase classname="services.x" name="test_ok"/>'
    "</testsuite></testsuites>"
)


def test_the_failed_nodeids_of_a_container_command_come_from_its_own_junit_report(
    qa: Make,
) -> None:
    repo = qa()
    repo.engine.script("gate-2", stderr="1 failed\n", exit_code=1, junit=_JUNIT)

    code, result, err = repo.qa_run()

    assert code == 0 and result is not None, err
    report = repo.report()
    assert report["outcome"] == "failed"
    reports = [
        [env for env in _flag(run, "--env") if env.startswith("HARNESS_STAGE_JUNIT_XML=")]
        for run in repo.engine.runs()
    ]
    assert [len(found) for found in reports] == [1, 1]
    assert reports[0] != reports[1] and reports[1][0].endswith("/stage-gate-2.junit.xml")
    records = repo.execution()["exit"]["commands"]
    assert records[1]["junit"] == reports[1][0].split("=", 1)[1]
    stages = {stage["stage_id"]: stage for stage in _stage_evidence(repo, report)["stages"]}
    assert stages["gate-2"]["failed_nodeids"] == ["services/x.py::test_value[1]"]
    assert stages["gate-1"]["failed_nodeids"] == []


def _stage_evidence(repo: ContainerQa, report: JsonObject) -> JsonObject:
    """The stage-evidence document the QA artifact of ``report`` links to, read from the store's
    immutable artifacts."""
    log = str(report["output"]).split("full sanitised output: ", 1)[1].split(" ", 1)[0]
    connection = sqlite3.connect(repo.repo / STATE_REL / "runtime.db", timeout=10)
    try:
        artifacts: dict[str, str] = {
            path: bytes(content).decode("utf-8")
            for path, content in connection.execute("SELECT path, bytes FROM artifact")
        }
    finally:
        connection.close()
    trailer = artifacts["qa-artifacts/" + log.rsplit("/qa-artifacts/", 1)[1]].splitlines()[-1]
    document: JsonObject = json.loads(artifacts[trailer.split(" ")[1]])
    return document


def test_an_infrastructure_ending_is_a_new_attempt_without_a_report_or_a_developer_retry(
    qa: Make,
) -> None:
    repo = qa()
    repo.engine.script("gate-1", stderr="Error: OCI runtime error\n", exit_code=125)

    code, _, err = repo.qa_run()

    assert code == 2 and "attempt 2" in err, err
    [attempt] = repo.attempts()
    assert (attempt["attempt"], attempt["domain"]) == (1, "infrastructure")
    assert attempt["stage_evidence"].startswith("stage-evidence: qa-artifacts/")
    assert repo.status() | {"updated_at": None} == {
        "dispatch_id": repo.dispatch, "state": "approved", "attempt": 1, "updated_at": None,
    }
    lane = repo.lane()
    assert (lane["lease"], lane["queue"]) == (None, [])
    first = repo.execution()["execution_id"]

    repo.engine.script("gate-1", exit_code=0)
    code, result, err = repo.qa_run()

    assert code == 0 and result is not None, err
    assert repo.report()["outcome"] == "completed"
    execution = repo.execution()
    assert execution["attempt"] == 2 and execution["execution_id"] != first
    path = f"batches/{repo.batch}.json"
    dispatches = store_records(repo.repo, repo.runtime, path)[path]["dispatches"]
    assert isinstance(dispatches, list)
    assert [d["role"] for d in dispatches if isinstance(d, dict)].count("developer") == 1


_MARKER = "partial-output-of-an-interrupted-command-3b9d"


def _artifact_texts(repo: ContainerQa) -> list[str]:
    """Every immutable artifact of the store, as text."""
    connection = sqlite3.connect(repo.repo / STATE_REL / "runtime.db", timeout=10)
    try:
        return [
            bytes(content).decode("utf-8", "replace")
            for (content,) in connection.execute("SELECT bytes FROM artifact")
        ]
    finally:
        connection.close()


@pytest.mark.fault_injection
def test_a_partial_command_record_left_by_a_killed_runtime_is_not_run_and_never_evidence(
    qa: Make,
) -> None:
    repo = qa()
    repo.engine.script("gate-2", stdout=f"{_MARKER}\n", hang=True)
    run = coordinator_popen(repo.repo, repo.runtime, "qa", "run", "--dispatch", repo.dispatch)
    deadline = time.monotonic() + 60
    while len(repo.engine.runs()) < 2 and time.monotonic() < deadline:
        time.sleep(0.05)
    assert len(repo.engine.runs()) == 2, repo.engine.calls()
    execution_id = str(repo.execution()["execution_id"])

    # SIGKILL while gate-2 runs, and its record half written: what write_record leaves behind.
    repo.runtime.kill()
    commands = repo.repo / STATE_REL / "executions" / execution_id / "commands"
    (commands / "001.json.partial").write_text(
        '{"index":1,"stage_id":"gate-2","result":"ran","exit_code":0,"stdout":{"tail":"'
        + _MARKER,
        encoding="utf-8",
    )
    repo.runtime = ServingRuntime(repo.repo, env=repo.environ, xdg=repo.runtime.xdg)
    _, err = run.communicate(timeout=120)

    assert run.returncode == 2, err
    execution = repo.execution()
    assert execution["state"] == "lost"
    records = execution["exit"]["commands"]
    assert [(r["stage_id"], r["result"], r["exit_code"]) for r in records] == [
        ("gate-1", "ran", 0), ("gate-2", "not_run", None), ("gate-3", "not_run", None),
    ]
    [attempt] = repo.attempts()
    assert attempt["domain"] == "infrastructure"
    report = f"reports/{repo.dispatch}.json"
    assert report not in store_records(repo.repo, repo.runtime, report)
    assert _MARKER not in json.dumps(attempt)
    assert not any(_MARKER in text for text in _artifact_texts(repo))
    assert repo.status()["state"] == "approved"
    lane = repo.lane()
    assert (lane["lease"], lane["queue"]) == (None, [])


@pytest.mark.parametrize(
    ("code", "hang", "domain"), [(127, False, "tooling"), (126, False, "tooling"), (0, True, "timeout")]
)
def test_tooling_and_timeout_endings_block_the_report_with_their_domain(
    qa: Make, code: int, hang: bool, domain: str
) -> None:
    repo = qa(timeout=1)
    repo.engine.script("gate-2", stderr="sh: make: not found\n", exit_code=code, hang=hang)

    status, result, err = repo.qa_run()

    assert status == 0 and result is not None, err
    report = repo.report()
    assert report["outcome"] == "blocked"
    assert domain in report["blockers"]["details"]
    assert [c["result"] for c in report["checks_run"]] == ["pass", "fail", "not_run"]
    records = repo.execution()["exit"]["commands"]
    assert (records[1]["domain"], records[1]["exit_code"]) == (domain, 143 if hang else code)
    if hang:
        stops = [call for call in repo.engine.calls() if call[1] == "stop"]
        assert stops and stops[0][2:4] == ["--time", "1"]
    lane = repo.lane()
    assert (lane["lease"], lane["queue"]) == (None, [])


@pytest.mark.fault_injection
def test_an_selinux_permission_denied_command_blocks_the_report_as_tooling_without_a_new_attempt(
    qa: Make,
) -> None:
    repo = qa(selinux=True)
    denied = "crun: open executable: Permission denied: OCI permission denied\n"
    repo.engine.script("gate-1", stderr=denied, exit_code=126)

    code, result, err = repo.qa_run()

    assert code == 0 and result is not None, err
    report = repo.report()
    assert report["outcome"] == "blocked"
    assert "tooling" in report["blockers"]["details"]
    assert [c["result"] for c in report["checks_run"]] == ["fail", "not_run", "not_run"]
    records = repo.execution()["exit"]["commands"]
    assert (records[0]["domain"], records[0]["exit_code"]) == ("tooling", 126)
    assert repo.attempts() == []
    [run] = repo.engine.runs()
    assert "label=disable" in _flag(run, "--security-opt")
    assert not any(part.endswith((":z", ":Z")) or "relabel" in part for part in run)
    lane = repo.lane()
    assert (lane["lease"], lane["queue"]) == (None, [])


@pytest.mark.fault_injection
def test_an_offline_dependency_install_is_environment_preparation_and_a_new_attempt(
    qa: Make,
) -> None:
    repo = qa(preparation=PREPARATION)
    # `uv sync` of the preparation finds no package index, and the registry probe fails too.
    offline = (
        "error: Failed to fetch: `https://pypi.org/simple/pytest/`\n"
        "  Caused by: Could not connect, are you offline?\n"
    )
    repo.engine.script("preparation-1", stderr=offline, exit_code=2)
    repo.engine.script("environment-probe-1", exit_code=6)

    code, _, err = repo.qa_run()

    assert code == 2, err
    [attempt] = repo.attempts()
    assert attempt["domain"] == "environment_preparation"
    stages = [call[call.index("--name") + 1].rsplit("-qa1-", 1)[1] for call in repo.engine.runs()]
    assert stages == ["preparation-1", "environment-probe-1", "project-file-check-1"]
    assert repo.status()["state"] == "approved"


def test_the_runs_share_one_sidecar_and_network_and_mount_the_pinned_cache(
    qa: Make, tmp_path: Path
) -> None:
    cache = tmp_path / "uv-cache"
    cache.mkdir()
    repo = qa(hosts=["pypi.org"], cache=cache)
    plan = repo.brief["runtime_access"]
    # A config edit after the approval widens nothing: the runtime applies the pinned plan.
    config_path = repo.repo / ".harness/orchestration.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["access_policy"]["operations"]["qa"]["filesystem"].append(
        {"resource": "cache", "path": str(tmp_path), "access": "write"}
    )
    config_path.write_text(json.dumps(config), encoding="utf-8")

    code, result, err = repo.qa_run()

    assert code == 0 and result is not None, err
    assert repo.report()["outcome"] == "completed"
    assert repo.brief["runtime_access"] == plan
    calls = repo.engine.calls()
    runs = repo.engine.runs()
    assert len(runs) == 3
    assert len([c for c in calls if c[1:3] == ["network", "create"]]) == 1
    assert len([c for c in calls if c[1] == "create" and "--name" in c]) == 1
    networks = {tuple(_flag(run, "--network")) for run in runs}
    assert len(networks) == 1 and networks != {("none",)}
    for run in runs:
        mounts = _flag(run, "--mount")
        assert f"type=bind,source={cache},target={cache}" in mounts
        assert not any(f"source={tmp_path}," in mount for mount in mounts)
        assert SECRET not in json.dumps(run) and _flag(run, "--env").count(SECRET_NAME) == 1
    assert not any("volume" in part for call in calls for part in call)
    assert repo.engine.state()["objects"] == {}


@pytest.mark.parametrize("change", ["rebuilt image", "missing environment"])
def test_a_rebuilt_image_or_a_missing_variable_blocks_the_run_before_any_command(
    qa: Make, change: str
) -> None:
    repo = qa()
    if change == "rebuilt image":
        repo.engine.update(lambda state: state["images"].update({WORKER_TAG: "c" * 64}))
    else:
        repo.runtime.stop()
        repo.runtime = ServingRuntime(repo.repo, env={"PATH": str(repo.engine.bin)})

    code, _, err = repo.qa_run()

    assert code == 2, err
    assert ("approval_mismatch" if change == "rebuilt image" else SECRET_NAME) in err
    assert repo.engine.runs() == []
    assert repo.status()["state"] == "approved"
    lane = repo.lane()
    assert (lane["lease"], lane["queue"]) == (None, [])
