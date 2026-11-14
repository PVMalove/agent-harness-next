"""The read-only container engine inventory of the Harness screen, with a fake command runner."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from harness.console.kernel.container_inventory import (
    ContainerInventory,
    configured_engine,
    container_inventory,
)

DOCKER_INFO = {
    "ServerVersion": "27.4.1",
    "CgroupDriver": "systemd",
    "CgroupVersion": "2",
    "SecurityOptions": ["name=seccomp,profile=builtin", "name=rootless", "name=selinux"],
}
PODMAN_INFO = {
    "host": {
        "cgroupManager": "systemd",
        "cgroupVersion": "v2",
        "security": {"rootless": True, "selinuxEnabled": False},
    },
    "version": {"Version": "5.2.0"},
}


class Fake:
    def __init__(self, answers: dict[str, tuple[int, str, str] | None]) -> None:
        self.answers = answers
        self.calls: list[list[str]] = []

    def __call__(self, argv: Sequence[str]) -> tuple[int, str, str] | None:
        self.calls.append(list(argv))
        return self.answers[argv[1]]


def test_docker_info_and_counts_are_read_without_side_effects() -> None:
    run = Fake(
        {
            "info": (0, json.dumps(DOCKER_INFO), ""),
            "images": (0, "a1\nb2\nc3\n", ""),
            "volume": (0, "cache\n", ""),
        }
    )
    assert container_inventory("docker", run) == ContainerInventory(
        engine="docker",
        version="27.4.1",
        cgroup_driver="systemd",
        cgroup_version="v2",
        selinux=True,
        rootless=True,
        info_problem=None,
        images=3,
        images_problem=None,
        volumes=1,
        volumes_problem=None,
    )
    assert run.calls == [
        ["docker", "info", "--format", "{{json .}}"],
        ["docker", "images", "-q"],
        ["docker", "volume", "ls", "-q"],
    ]


def test_podman_info_has_its_own_shape() -> None:
    run = Fake(
        {
            "info": (0, json.dumps(PODMAN_INFO), ""),
            "images": (0, "", ""),
            "volume": (0, "", ""),
        }
    )
    found = container_inventory("podman", run)
    assert (found.version, found.cgroup_driver, found.cgroup_version) == ("5.2.0", "systemd", "v2")
    assert (found.selinux, found.rootless, found.images, found.volumes) == (False, True, 0, 0)


def test_every_failed_probe_leaves_its_facts_unknown_with_a_reason() -> None:
    socket = "Cannot connect to the Docker daemon at unix:///var/run/docker.sock."
    run = Fake(
        {
            "info": (1, "", f"{socket}\nIs the docker daemon running?\n"),
            "images": None,
            "volume": (125, "", ""),
        }
    )
    found = container_inventory("docker", run)
    assert (found.version, found.cgroup_driver, found.selinux, found.rootless) == (
        None,
        None,
        None,
        None,
    )
    assert found.info_problem == f"docker info: код 1: {socket}"
    assert found.images is None and found.images_problem is not None
    assert found.images_problem.startswith("docker images: не запускается")
    assert (found.volumes, found.volumes_problem) == (None, "docker volume ls: код 125")


def test_an_info_reply_with_server_errors_or_without_json_is_a_problem() -> None:
    ok = (0, "", "")
    errors = Fake({"info": (0, json.dumps({"ServerErrors": ["daemon down"]}), ""), "images": ok, "volume": ok})
    assert container_inventory("docker", errors).info_problem == "docker info: daemon down"
    garbage = Fake({"info": (0, "not json", ""), "images": ok, "volume": ok})
    assert container_inventory("docker", garbage).info_problem == "docker info: ответ не JSON-объект"


def test_the_engine_is_the_one_the_access_policy_names(tmp_path: Path) -> None:
    assert configured_engine(tmp_path) == "docker"
    policy = {"access_policy": {"defaults": {"container": {"engine": "podman"}}}}
    (tmp_path / "orchestration.json").write_text(json.dumps(policy), encoding="utf-8")
    assert configured_engine(tmp_path) == "podman"
