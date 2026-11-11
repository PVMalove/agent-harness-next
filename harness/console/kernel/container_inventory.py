"""A read-only inventory of the container engine the project's access policy names, for the
Containers tab of the Harness screen.

The engine is the one `harness cleanup` would ask about: the first engine the access policy of
`.harness/orchestration.json` names, `docker` by default. Three commands run, each with a short
timeout and nothing else: `<engine> info --format '{{json .}}'` (version, cgroup driver and
version, SELinux, rootless), `<engine> images -q` and `<engine> volume ls -q` (counts). Nothing
here writes, pulls, starts a container or uses the network. A fact a command cannot give is None
with the reason beside it; the screen shows it as no data. Standard library only."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

TIMEOUT_SECONDS = 5.0

# (exit code, standard output, standard error); None when the program cannot run or times out.
type Run = Callable[[Sequence[str]], tuple[int, str, str] | None]


def _run(argv: Sequence[str]) -> tuple[int, str, str] | None:
    try:
        found = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return found.returncode, found.stdout, found.stderr


@dataclass(frozen=True)
class ContainerInventory:
    """The engine facts; each None fact has its reason in `info_problem`, `images_problem` or
    `volumes_problem`."""

    engine: str
    version: str | None
    cgroup_driver: str | None
    cgroup_version: str | None
    selinux: bool | None
    rootless: bool | None
    info_problem: str | None
    images: int | None
    images_problem: str | None
    volumes: int | None
    volumes_problem: str | None

    def to_payload(self) -> dict[str, object]:
        return asdict(self)


def configured_engine(storage: Path) -> str:
    """The engine `harness cleanup` asks about: the first one the access policy of
    `<storage>/orchestration.json` names (`storage` is the project's `.harness`, see
    `harness.storage.storage_root`), `docker` by default."""
    from harness.cleanup import _container_engines

    return _container_engines(storage)[0]


def _problem(label: str, found: tuple[int, str, str] | None) -> str | None:
    """Why a probe gave nothing: the program did not run, or it exited with an error."""
    if found is None:
        return f"{label}: не запускается или не ответил за {TIMEOUT_SECONDS:g} с"
    code, _, error = found
    if code != 0:
        line = next((item.strip() for item in error.splitlines() if item.strip()), "")
        return f"{label}: код {code}" + (f": {line}" if line else "")
    return None


def _text(value: object) -> str | None:
    return str(value) if isinstance(value, (str, int)) and str(value) else None


def _info_facts(info: dict[str, object]) -> tuple[str | None, str | None, str | None, bool | None, bool | None]:
    """(version, cgroup driver, cgroup version, SELinux, rootless) of a Docker or Podman info."""
    host = info.get("host")
    if isinstance(host, dict):  # Podman: {"host": {...}, "version": {...}}
        version = info.get("version")
        security = host.get("security")
        security = security if isinstance(security, dict) else {}
        selinux = security.get("selinuxEnabled")
        rootless = security.get("rootless")
        return (
            _text(version.get("Version")) if isinstance(version, dict) else None,
            _text(host.get("cgroupManager")),
            _text(host.get("cgroupVersion")),
            selinux if isinstance(selinux, bool) else None,
            rootless if isinstance(rootless, bool) else None,
        )
    options = info.get("SecurityOptions")
    names = (
        {
            part.removeprefix("name=")
            for item in options
            if isinstance(item, str)
            for part in item.split(",")
            if part.startswith("name=")
        }
        if isinstance(options, list)
        else None
    )
    cgroup = _text(info.get("CgroupVersion"))
    return (
        _text(info.get("ServerVersion")),
        _text(info.get("CgroupDriver")),
        f"v{cgroup}" if cgroup and cgroup.isdigit() else cgroup,
        None if names is None else "selinux" in names,
        None if names is None else "rootless" in names,
    )


def _count(argv: Sequence[str], run: Run) -> tuple[int | None, str | None]:
    found = run(argv)
    problem = _problem(" ".join(argv[:-1]), found)
    if problem is not None or found is None:
        return None, problem
    return sum(1 for line in found[1].splitlines() if line.strip()), None


def container_inventory(engine: str, run: Run = _run) -> ContainerInventory:
    """The inventory of `engine`; every probe that fails leaves its facts None with a reason."""
    found = run([engine, "info", "--format", "{{json .}}"])
    info_problem = _problem(f"{engine} info", found)
    facts: tuple[str | None, str | None, str | None, bool | None, bool | None] = (
        None,
        None,
        None,
        None,
        None,
    )
    if info_problem is None and found is not None:
        try:
            info = json.loads(found[1])
        except ValueError:
            info = None
        errors = info.get("ServerErrors") if isinstance(info, dict) else None
        if not isinstance(info, dict):
            info_problem = f"{engine} info: ответ не JSON-объект"
        elif isinstance(errors, list) and errors:
            info_problem = f"{engine} info: {errors[0]}"
        else:
            facts = _info_facts(info)
    images, images_problem = _count([engine, "images", "-q"], run)
    volumes, volumes_problem = _count([engine, "volume", "ls", "-q"], run)
    version, driver, cgroup, selinux, rootless = facts
    return ContainerInventory(
        engine=engine,
        version=version,
        cgroup_driver=driver,
        cgroup_version=cgroup,
        selinux=selinux,
        rootless=rootless,
        info_problem=info_problem,
        images=images,
        images_problem=images_problem,
        volumes=volumes,
        volumes_problem=volumes_problem,
    )
