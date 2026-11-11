"""Real rootful Docker smoke of the container executor (#710; ADR 0022, ADR 0025).

The coordinator CLI runs as its own process against the real ``harness-runtime``, real Git
worktrees, the real store and the real ``docker`` on the host ``PATH``. Nothing is scripted: the
worker and the QA commands run in containers of the images the CI docker-smoke job builds from
``harness/container/Dockerfile.sandbox`` (a project worker image ``FROM`` it) and
``harness/container/Dockerfile.proxy``.

The ``docker_smoke`` marker keeps this module out of every default pytest run: pyproject.toml
deselects it through ``addopts``, so even a node id of this module runs only together with
``-m docker_smoke`` (without it pytest deselects the node and exits 5). Without a reachable
rootful engine or the smoke images every test skips with its reason; ``HARNESS_REQUIRE_DOCKER_SMOKE=1``
turns that skip into a failure, as ``HARNESS_REQUIRE_RUNTIME=1`` does for the runtime binary.
The smoke needs the network: ``github.com`` is the allowed host and ``example.com`` the denied one.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness.json_types import JsonObject
from tests.orchestration.runtime_store_support import Supervised
from tests.orchestration.test_qa_container import ContainerQa, _stage_evidence

pytestmark = [
    pytest.mark.docker_smoke,
    pytest.mark.skipif(
        not sys.platform.startswith("linux"),
        reason="the docker executor runs only on Linux",
    ),
]

REQUIRE_ENV = "HARNESS_REQUIRE_DOCKER_SMOKE"
# The tags the CI docker-smoke job builds; the harness itself never builds or pulls an image.
WORKER_TAG = "harness-worker:smoke"
PROXY_TAG = "harness-proxy:smoke"
ALLOWED_HOST = "github.com"
DENIED_HOST = "example.com"
LABEL_DISPATCH = "harness.dispatch"
ENGINE_TIMEOUT_SECONDS = 120
EVIDENCE = "smoke-evidence.json"
POLICY: JsonObject = {
    "defaults": {
        "mode": "sandbox",
        "container": {
            "engine": "docker",
            "worker_image": WORKER_TAG,
            "proxy_image": PROXY_TAG,
        },
        "network": {"hosts": [ALLOWED_HOST]},
    }
}

# The worker the runtime starts as the container entrypoint. It records who it runs as and what
# its egress reaches, then exits 0. Each probe prints the curl exit code, the HTTP status and the
# status of a proxy CONNECT ("000" when there is none).
ADAPTER = f"""#!/bin/sh
probe() {{
    codes=$(curl --silent --output /dev/null --max-time 20 --write-out '%{{http_code}} %{{http_connect}}' "$@")
    status=$?
    set -- $codes
    printf '{{"exit": %d, "http": "%s", "connect": "%s"}}' "$status" "${{1:-000}}" "${{2:-000}}"
}}
evidence="$(dirname "$0")/{EVIDENCE}"
{{
    printf '{{"uid": "%s", "gid": "%s", ' "$(id -u)" "$(id -g)"
    printf '"executor": "%s", "proxy": "%s", ' "${{HARNESS_EXECUTOR:-}}" "${{HTTPS_PROXY:-}}"
    printf '"allowed_https": %s, ' "$(probe https://{ALLOWED_HOST}/)"
    printf '"allowed_http": %s, ' "$(probe http://{ALLOWED_HOST}/)"
    printf '"denied_https": %s, ' "$(probe https://{DENIED_HOST}/)"
    printf '"denied_http": %s, ' "$(probe http://{DENIED_HOST}/)"
    printf '"direct": %s}}\\n' "$(probe --noproxy '*' https://{ALLOWED_HOST}/)"
}} > "$evidence.partial"
mv "$evidence.partial" "$evidence"
"""


def _docker(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *arguments],
        capture_output=True,
        text=True,
        check=False,
        timeout=ENGINE_TIMEOUT_SECONDS,
    )


def _engine_problem() -> str | None:
    """Why this host cannot run the smoke, or ``None`` when it can."""
    if shutil.which("docker") is None:
        return "no docker CLI on PATH"
    try:
        info = _docker("info", "--format", "{{json .SecurityOptions}}")
        if info.returncode != 0:
            return f"docker info failed: {info.stderr.strip()[:300]}"
        if "rootless" in info.stdout:
            return "the smoke verifies rootful Docker only, and this engine is rootless"
        for tag in (WORKER_TAG, PROXY_TAG):
            if _docker("image", "inspect", "--format", "{{.Id}}", tag).returncode:
                return f"the smoke image {tag} is missing; build it as the docker-smoke CI job does"
    except subprocess.TimeoutExpired:
        return f"docker did not answer within {ENGINE_TIMEOUT_SECONDS} seconds"
    return None


def require_engine() -> None:
    """Skip without a usable engine, or fail when ``HARNESS_REQUIRE_DOCKER_SMOKE=1``."""
    problem = _engine_problem()
    if problem is None:
        return
    if os.environ.get(REQUIRE_ENV) == "1":
        pytest.fail(f"{REQUIRE_ENV}=1, but {problem}")
    pytest.skip(problem)


def labelled_objects(dispatch_id: str) -> tuple[list[str], list[str]]:
    """The containers and the networks that carry the label of ``dispatch_id``."""
    selector = f"label={LABEL_DISPATCH}={dispatch_id}"
    containers = _docker("ps", "--all", "--quiet", "--filter", selector)
    networks = _docker("network", "ls", "--quiet", "--filter", selector)
    assert containers.returncode == 0, containers.stderr
    assert networks.returncode == 0, networks.stderr
    return containers.stdout.split(), networks.stdout.split()


def wait_removed(
    dispatch_id: str, timeout: float = 60.0
) -> tuple[list[str], list[str]]:
    """What still carries the dispatch label once the runtime had ``timeout`` seconds to remove it."""
    deadline = time.monotonic() + timeout
    while True:
        left = labelled_objects(dispatch_id)
        if left == ([], []) or time.monotonic() > deadline:
            return left
        time.sleep(1)


@pytest.fixture
def labelled() -> Iterator[list[str]]:
    """Dispatch ids whose labelled containers and networks are removed after the test, so a failed
    smoke leaves nothing on the engine."""
    dispatches: list[str] = []
    yield dispatches
    for dispatch_id in dispatches:
        containers, networks = labelled_objects(dispatch_id)
        if containers:
            _docker("rm", "--force", *containers)
        if networks:
            _docker("network", "rm", *networks)


# The worker of the attested round trip (#1014): it prints the stream-json init event of the
# brief's model, stages the report the host prepared, and runs until the host releases it, so the
# host observes it running. It never reaches the ledger: the host records its self-report.
ATTESTED_ADAPTER = """#!/bin/sh
set -eu
dir=$(dirname "$0")
brief=""
while [ $# -gt 0 ]; do
    case "$1" in
        --brief) brief=$2; shift 2 ;;
        *) shift ;;
    esac
done
field() { python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$brief" "$1"; }
printf '{"type": "system", "subtype": "init", "model": "%s"}\\n' "$(field resolved_model)"
cp "$dir/smoke-report.json" "$(field report_staging_path)"
waited=0
while [ ! -e "$dir/smoke-release" ] && [ "$waited" -lt 240 ]; do
    sleep 1
    waited=$((waited + 1))
done
"""

OFFLINE: JsonObject = {"mode": "sandbox", "network": {"hosts": []}}


def attested_round_trip(repo: Supervised, engine: str) -> None:
    """For the created dispatch of ``repo``: ``dispatch send`` → the host-side self-report → ``report submit`` of the staged report →
    ``reported``, with a real engine and no runtime socket in the container (#1014)."""
    from tests.orchestration.runtime_store_support import architect_report_file

    scratch = repo.repo / ".harness/.sandboxes/scratch"
    adapter = scratch / "attested-adapter.sh"
    adapter.write_text(ATTESTED_ADAPTER, encoding="utf-8")
    adapter.chmod(0o755)
    prepared = architect_report_file(repo.repo, repo.dispatch, repo.brief)
    (scratch / "smoke-report.json").write_bytes(prepared.read_bytes())

    sent = repo.run(
        "dispatch", "send", "--dispatch", repo.dispatch, "--adapter", str(adapter)
    )

    assert sent.returncode == 0, sent.stderr
    assert json.loads(sent.stdout)["execution"]["engine"] == engine
    deadline = time.monotonic() + ENGINE_TIMEOUT_SECONDS
    status: JsonObject = {}
    while time.monotonic() < deadline:
        viewed = repo.run("dispatch", "status", "--dispatch", repo.dispatch)
        assert viewed.returncode == 0, viewed.stderr
        status = repo.status()
        if status.get("model_self_report"):
            break
        time.sleep(1)
    reported = status.get("model_self_report")
    attestation = status.get("worktree_attestation")
    assert isinstance(reported, dict) and isinstance(attestation, dict), status
    assert (reported["match"], reported["source"]) == (True, "container-host"), status
    assert (attestation["match"], attestation["source"]) == (True, "container-host")
    assert attestation["container"]["executor"] == "docker"
    observed = repo.run("dispatch", "observe", "--dispatch", repo.dispatch)
    assert observed.returncode == 0, observed.stderr
    assert json.loads(observed.stdout)["stream_state"] == "connected", observed.stdout
    staged = Path(str(repo.brief["report_staging_path"]))
    deadline = time.monotonic() + ENGINE_TIMEOUT_SECONDS
    while not staged.is_file() and time.monotonic() < deadline:
        time.sleep(1)
    # While the container runs, the report waits for its exit.
    submitted = repo.run("report", "submit", "--file", str(staged))
    assert submitted.returncode == 0, submitted.stderr
    (scratch / "smoke-release").write_text("", encoding="utf-8")
    ended = repo.wait_execution("exited", timeout=300)
    exit_record = ended.get("exit")
    assert isinstance(exit_record, dict) and exit_record.get("exit_code") == 0, _logs(
        ended
    )
    viewed = repo.run("dispatch", "status", "--dispatch", repo.dispatch)
    assert viewed.returncode == 0, viewed.stderr
    assert repo.status()["state"] == "reported", repo.status()


def _logs(execution: JsonObject) -> str:
    """The saved worker streams of an ended execution, for an assertion message."""
    receipt = execution.get("receipt")
    logs = receipt.get("logs") if isinstance(receipt, dict) else None
    if not isinstance(logs, dict):
        return f"no saved logs: {execution}"
    return "\n".join(
        f"{name}: {Path(str(logs[name])).read_text(encoding='utf-8', errors='replace')}"
        for name in ("stdout", "stderr")
        if name in logs and Path(str(logs[name])).is_file()
    )


def test_a_worker_reaches_only_its_allowed_host_and_writes_as_the_host_user(
    tmp_path: Path, labelled: list[str]
) -> None:
    if sys.platform == "win32":
        pytest.skip("os.getuid and os.getgid are POSIX-only")
    require_engine()
    repo = Supervised(tmp_path / "worker", access_policy=POLICY, create=False)
    try:
        repo.create()
        labelled.append(repo.dispatch)
        # The artifacts root is mounted read-write at the same path, so the entrypoint is there.
        adapter = repo.repo / ".harness/.sandboxes/scratch/smoke-adapter.sh"
        adapter.write_text(ADAPTER, encoding="utf-8")
        adapter.chmod(0o755)

        sent = repo.run(
            "dispatch", "send", "--dispatch", repo.dispatch, "--adapter", str(adapter)
        )

        assert sent.returncode == 0, sent.stderr
        execution = json.loads(sent.stdout)["execution"]
        assert (execution["kind"], execution["engine"]) == ("container", "docker")
        ended = repo.wait_execution("exited", timeout=300)
        exit_record = ended.get("exit")
        assert isinstance(exit_record, dict), ended
        assert exit_record.get("exit_code") == 0, _logs(ended)
        evidence_file = adapter.parent / EVIDENCE
        assert evidence_file.is_file(), _logs(ended)
        evidence = json.loads(evidence_file.read_text(encoding="utf-8"))
        stat = evidence_file.stat()
        host = (os.getuid(), os.getgid())
        assert (stat.st_uid, stat.st_gid) == host, evidence
        assert (evidence["uid"], evidence["gid"]) == tuple(str(item) for item in host)
        assert evidence["executor"] == "docker"
        assert evidence["proxy"].startswith(f"http://harness-{repo.dispatch}-proxy:")
        # The allowed host answers through the sidecar over HTTPS and HTTP.
        allowed_https = evidence["allowed_https"]
        assert (allowed_https["exit"], allowed_https["connect"]) == (0, "200"), evidence
        assert 200 <= int(allowed_https["http"]) < 400, evidence
        assert evidence["allowed_http"]["exit"] == 0, evidence
        assert 200 <= int(evidence["allowed_http"]["http"]) < 400, evidence
        # Another host gets the sidecar's 403, for a tunnel and for a plain request.
        denied_https = evidence["denied_https"]
        assert denied_https["exit"] != 0, evidence
        assert "403" in (denied_https["connect"], denied_https["http"]), evidence
        denied_http = evidence["denied_http"]
        assert (denied_http["exit"], denied_http["http"]) == (0, "403"), evidence
        # Past the proxy the internal network has no route out.
        direct = evidence["direct"]
        assert direct["exit"] != 0 and direct["http"] == "000", evidence
        assert wait_removed(repo.dispatch) == ([], [])
    finally:
        repo.close()


def test_a_container_qa_run_reports_the_real_exit_code_of_a_failing_gate(
    tmp_path: Path, labelled: list[str]
) -> None:
    if sys.platform == "win32":
        pytest.skip("os.getuid and os.getgid are POSIX-only")
    require_engine()
    identity = f"{os.getuid()}:{os.getgid()}"
    gate = [f'test "$(id -u):$(id -g)" = "{identity}"', "exit 3"]
    repo = ContainerQa(
        tmp_path / "qa",
        engine="docker",
        worker_tag=WORKER_TAG,
        proxy_tag=PROXY_TAG,
        gate=gate,
        hosts=[ALLOWED_HOST],
        scripted_engine=False,
    )
    try:
        labelled.append(repo.dispatch)

        code, result, err = repo.qa_run()

        assert code == 0 and result is not None, err
        report = repo.report()
        assert report["outcome"] == "failed", report
        assert [(c["command"], c["result"]) for c in report["checks_run"]] == [
            (gate[0], "pass"),
            (gate[1], "fail"),
        ]
        records = repo.execution()["exit"]["commands"]
        assert [(r["stage_id"], r["result"], r["exit_code"]) for r in records] == [
            ("gate-1", "ran", 0),
            ("gate-2", "ran", 3),
        ]
        stages = _stage_evidence(repo, report)["stages"]
        assert [(s["stage_id"], s["result"], s["exit_code"]) for s in stages] == [
            ("gate-1", "pass", 0),
            ("gate-2", "fail", 3),
        ]
        assert wait_removed(repo.dispatch) == ([], [])
    finally:
        repo.close()


def test_a_container_worker_is_attested_on_the_host_and_its_report_accepted(
    tmp_path: Path, labelled: list[str]
) -> None:
    """#1014: the full route of a writer role under rootful Docker without a manual bypass."""
    require_engine()
    policy: JsonObject = {
        "defaults": {
            **OFFLINE,
            "container": {"engine": "docker", "worker_image": WORKER_TAG},
        }
    }
    repo = Supervised(tmp_path / "attested", access_policy=policy, create=False)
    try:
        repo.create()
        labelled.append(repo.dispatch)
        attested_round_trip(repo, "docker")
        assert wait_removed(repo.dispatch) == ([], [])
    finally:
        repo.close()
